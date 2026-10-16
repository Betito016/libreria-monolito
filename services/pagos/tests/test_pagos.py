"""
Microservicio pagos: JWT, dueno del pedido, candado distribuido por pedido,
idempotencia y reembolso solo de administrador. Repositorio en memoria y fakeredis.
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

import app as pagos  # noqa: E402
from libreria_common.validacion import Conflicto, NoEncontrado  # noqa: E402

CLIENTE, OTRO, ADMIN = 'c1c1c1c1-0000-0000-0000-000000000001', 'c2c2c2c2-0000-0000-0000-000000000002', 'a0a0a0a0-0000-0000-0000-000000000000'


class RepoFalso:
    def __init__(self):
        self.pedidos = {1: {'id': 1, 'user_id': CLIENTE, 'estado': 'pendiente', 'total': 860.0}}
        self.pagos, self.registros = {}, 0

    def pedido(self, oid):
        if oid not in self.pedidos:
            raise NoEncontrado('no')
        return self.pedidos[oid]

    def registrar(self, oid, user_id, metodo, monto):
        if self.pedidos[oid]['estado'] != 'pendiente':
            raise Conflicto('ERR_PEDIDO_NO_PAGABLE', 'no pendiente')
        self.registros += 1
        self.pedidos[oid]['estado'] = 'pagado'
        self.pagos[self.registros] = {'id': self.registros, 'order_id': oid, 'user_id': user_id, 'metodo': metodo,
                                      'monto': 860.0, 'estado': 'aprobado'}
        return self.pagos[self.registros]

    def obtener(self, pid):
        if pid not in self.pagos:
            raise NoEncontrado('no')
        return self.pagos[pid]

    def listar(self, user_id, *a):
        lista = [p for p in self.pagos.values() if user_id is None or p['user_id'] == user_id]
        return {'total': len(lista), 'pagos': lista}

    def reembolsar(self, pid):
        self.pagos[pid]['estado'] = 'reembolsado'
        return self.pagos[pid]

    def eliminar(self, pid):
        if self.pagos[pid]['estado'] == 'aprobado':
            raise Conflicto('ERR_PAGO_APROBADO', 'reembolsa primero')
        return self.pagos.pop(pid)


@pytest.fixture
def cliente(monkeypatch):
    servidor = fakeredis.FakeServer()
    redis = fakeredis.FakeRedis(server=servidor, decode_responses=True)
    monkeypatch.setattr(pagos.servicio.redis, '_cliente', redis)
    pagos.servicio.redis._abierto_hasta = 0
    repo = RepoFalso()
    monkeypatch.setattr(pagos, 'repo', repo)
    pagos.app.testing = True
    c = pagos.app.test_client()
    c.redis, c.repo, c.servidor = redis, repo, servidor
    return c


def bearer(user_id=CLIENTE, role_id=2):
    ahora = int(time.time())
    t = jwt.encode({'sub': user_id, 'user_id': user_id, 'email': 'x@x.com', 'role_id': role_id, 'jti': uuid.uuid4().hex,
                    'typ': 'access', 'iss': 'libreria-login', 'iat': ahora, 'exp': ahora + 1200}, CLAVE, algorithm='HS256')
    return {'Authorization': f'Bearer {t}'}


PAGO = {'order_id': 1, 'metodo': 'tarjeta', 'monto': 860.0}


def test_requiere_jwt(cliente):
    assert cliente.post('/payments?format=json', json=PAGO).status_code == 401


def test_pagar_pedido_propio_y_candado_liberado(cliente):
    r = cliente.post('/payments?format=json', json=PAGO, headers=bearer())
    assert r.status_code == 201 and cliente.repo.pedidos[1]['estado'] == 'pagado'
    assert not cliente.redis.exists('lock:order:1')                     # se libero al terminar
    assert cliente.post('/payments?format=json', json=PAGO, headers=bearer()).status_code == 409


def test_no_se_paga_pedido_ajeno(cliente):
    assert cliente.post('/payments?format=json', json=PAGO, headers=bearer(OTRO)).status_code == 403


def test_candado_ocupado_409(cliente):
    cliente.redis.set('lock:order:1', 'otro-proceso', ex=30)            # pago en curso en otra peticion
    r = cliente.post('/payments?format=json', json=PAGO, headers=bearer())
    assert r.status_code == 409 and r.get_json()['codigo_error'] == 'ERR_OPERACION_EN_CURSO'
    assert cliente.repo.registros == 0
    assert cliente.redis.get('lock:order:1') == 'otro-proceso'         # no se solto un candado ajeno


def test_idempotency_key(cliente):
    h = {**bearer(), 'Idempotency-Key': 'pago-1'}
    assert cliente.post('/payments?format=json', json=PAGO, headers=h).status_code == 201
    r = cliente.post('/payments?format=json', json=PAGO, headers=h)
    assert r.status_code == 200 and r.get_json()['repetido'] is True and cliente.repo.registros == 1


@pytest.mark.parametrize('datos', [{'order_id': 1}, {'order_id': 1, 'metodo': 'bitcoin'}, {'order_id': 'x', 'metodo': 'tarjeta'},
                                   {'order_id': 1, 'metodo': 'tarjeta', 'monto': -5}])
def test_validacion(cliente, datos):
    assert cliente.post('/payments?format=json', json=datos, headers=bearer()).status_code == 400


def test_reembolso_solo_admin_e_invalida_catalogo(cliente):
    cliente.post('/payments?format=json', json=PAGO, headers=bearer())
    cliente.redis.set('books:list:todos', '{}')
    assert cliente.patch('/payments/1?format=json', json={'estado': 'reembolsado'}, headers=bearer()).status_code == 403
    r = cliente.patch('/payments/1?format=json', json={'estado': 'reembolsado'}, headers=bearer(ADMIN, 1))
    assert r.status_code == 200 and not cliente.redis.exists('books:list:todos')
    assert cliente.patch('/payments/1?format=json', json={'estado': 'aprobado'}, headers=bearer(ADMIN, 1)).status_code == 400


def test_cliente_solo_ve_sus_pagos(cliente):
    cliente.post('/payments?format=json', json=PAGO, headers=bearer())
    assert cliente.get('/payments?format=json', headers=bearer(OTRO)).get_json()['total'] == 0
    assert cliente.get('/payments/1?format=json', headers=bearer(OTRO)).status_code == 403
    assert cliente.get('/payments?format=json', headers=bearer(ADMIN, 1)).get_json()['total'] == 1


def test_redis_caido_503(cliente):
    cliente.servidor.connected = False
    assert cliente.post('/payments?format=json', json=PAGO, headers=bearer()).status_code == 503
