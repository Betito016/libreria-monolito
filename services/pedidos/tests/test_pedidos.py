"""
Microservicio pedidos: JWT obligatorio, pedidos propios vs de administrador,
idempotencia, invalidacion de cache y tarea periodica con candado.
Repositorio en memoria y fakeredis.
"""
import os
import sys
import time
import uuid
from pathlib import Path

import fakeredis
import jwt
import pytest

CLAVE = 'clave-de-prueba-solo-para-tests-0123456789abcdef'
os.environ.update(JWT_SECRET_KEY=CLAVE, REDIS_URL='redis://:x@127.0.0.1:6379/0')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as pedidos  # noqa: E402
from libreria_common.validacion import Conflicto, NoEncontrado  # noqa: E402

CLIENTE, OTRO, ADMIN = 'c1c1c1c1-0000-0000-0000-000000000001', 'c2c2c2c2-0000-0000-0000-000000000002', 'a0a0a0a0-0000-0000-0000-000000000000'


class RepoFalso:
    def __init__(self):
        self.pedidos, self.creados, self.cancelados = {}, 0, []

    def crear(self, user_id, email, items, direccion):
        self.creados += 1
        pid = self.creados
        self.pedidos[pid] = {'id': pid, 'user_id': user_id, 'estado': 'pendiente', 'total': 100.0, 'lineas': items}
        return self.pedidos[pid]

    def obtener(self, pid):
        if pid not in self.pedidos:
            raise NoEncontrado('no')
        return self.pedidos[pid]

    def listar(self, user_id, estado, page, size):
        lista = [p for p in self.pedidos.values() if user_id is None or p['user_id'] == user_id]
        return {'total': len(lista), 'pedidos': lista}

    def modificar(self, pid, cambios):
        if cambios.get('estado') == 'pagado':
            raise Conflicto('ERR_TRANSICION_INVALIDA', 'solo pagos')
        self.obtener(pid).update(cambios)
        return self.pedidos[pid]

    def eliminar(self, pid):
        return self.pedidos.pop(pid)

    def cancelar_vencidos(self, minutos):
        self.cancelados.append(minutos)
        return [99]


@pytest.fixture
def cliente(monkeypatch):
    servidor = fakeredis.FakeServer()
    redis = fakeredis.FakeRedis(server=servidor, decode_responses=True)
    monkeypatch.setattr(pedidos.servicio.redis, '_cliente', redis)
    pedidos.servicio.redis._abierto_hasta = 0
    repo = RepoFalso()
    monkeypatch.setattr(pedidos, 'repo', repo)
    pedidos.app.testing = True
    c = pedidos.app.test_client()
    c.redis, c.repo, c.servidor = redis, repo, servidor
    return c


def bearer(user_id=CLIENTE, role_id=2):
    ahora = int(time.time())
    t = jwt.encode({'sub': user_id, 'user_id': user_id, 'email': f'{user_id[:4]}@x.com', 'role_id': role_id,
                    'jti': uuid.uuid4().hex, 'typ': 'access', 'iss': 'libreria-login', 'iat': ahora, 'exp': ahora + 1200},
                   CLAVE, algorithm='HS256')
    return {'Authorization': f'Bearer {t}'}


PEDIDO = {'items': [{'isbn': '9780451524935', 'cantidad': 2}], 'direccion_envio': 'Av. Siempre Viva 742'}


def test_todo_requiere_jwt(cliente):
    assert cliente.get('/orders?format=json').status_code == 401
    assert cliente.post('/orders?format=json', json=PEDIDO).status_code == 401


def test_crear_invalida_cache_del_catalogo(cliente):
    cliente.redis.set('books:list:todos', '{}')
    r = cliente.post('/orders?format=json', json=PEDIDO, headers=bearer())
    assert r.status_code == 201 and not cliente.redis.exists('books:list:todos')


def test_idempotency_key_no_duplica(cliente):
    h = {**bearer(), 'Idempotency-Key': 'compra-123'}
    r1 = cliente.post('/orders?format=json', json=PEDIDO, headers=h)
    r2 = cliente.post('/orders?format=json', json=PEDIDO, headers=h)
    assert r1.status_code == 201 and r2.status_code == 200 and r2.get_json()['repetido'] is True
    assert cliente.repo.creados == 1
    assert 0 < cliente.redis.ttl(f'order:idem:{CLIENTE}:compra-123') <= 24 * 3600


@pytest.mark.parametrize('datos', [{}, {'items': []}, {'items': [{'isbn': '1', 'cantidad': 0}]},
                                   {'items': [{'isbn': '1', 'cantidad': True}]}, {'items': PEDIDO['items'], 'x': 1}])
def test_validacion(cliente, datos):
    assert cliente.post('/orders?format=json', json=datos, headers=bearer()).status_code == 400


def test_cliente_solo_ve_y_modifica_lo_suyo(cliente):
    cliente.post('/orders?format=json', json=PEDIDO, headers=bearer(CLIENTE))
    cliente.post('/orders?format=json', json=PEDIDO, headers=bearer(OTRO))
    assert cliente.get('/orders?format=json', headers=bearer(CLIENTE)).get_json()['total'] == 1
    assert cliente.get('/orders?format=json', headers=bearer(ADMIN, 1)).get_json()['total'] == 2
    assert cliente.get('/orders/2?format=json', headers=bearer(CLIENTE)).status_code == 403
    assert cliente.patch('/orders/2?format=json', json={'estado': 'cancelado'}, headers=bearer(CLIENTE)).status_code == 403
    assert cliente.patch('/orders/1?format=json', json={'estado': 'enviado'}, headers=bearer(CLIENTE)).status_code == 403
    assert cliente.patch('/orders/1?format=json', json={'estado': 'cancelado'}, headers=bearer(CLIENTE)).status_code == 200


def test_pagado_solo_desde_pagos(cliente):
    cliente.post('/orders?format=json', json=PEDIDO, headers=bearer())
    r = cliente.patch('/orders/1?format=json', json={'estado': 'pagado'}, headers=bearer(ADMIN, 1))
    assert r.status_code == 409


def test_delete_solo_admin(cliente):
    cliente.post('/orders?format=json', json=PEDIDO, headers=bearer())
    assert cliente.delete('/orders/1?format=json', headers=bearer()).status_code == 403
    assert cliente.delete('/orders/1?format=json', headers=bearer(ADMIN, 1)).status_code == 200


def test_barrido_con_candado(cliente):
    assert pedidos.barrer_vencidos() == [99]
    cliente.redis.set('lock:pedidos:barrido', 'otro-proceso', ex=60)       # otra instancia lo tiene
    assert pedidos.barrer_vencidos() == []
    assert len(cliente.repo.cancelados) == 1


def test_redis_caido_503(cliente):
    cliente.servidor.connected = False
    assert cliente.post('/orders?format=json', json=PEDIDO, headers=bearer()).status_code == 503
