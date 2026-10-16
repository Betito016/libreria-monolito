"""
Microservicio users: autorizacion por rol y revocacion de tokens en Redis.
Repositorio en memoria y fakeredis (sin PostgreSQL ni Redis reales).

    cd services/users
    venv\\Scripts\\python -m pytest -q
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

import app as users  # noqa: E402
from libreria_common.validacion import Conflicto, NoEncontrado  # noqa: E402

ADMIN_ID, CLIENTE_ID = str(uuid.uuid4()), str(uuid.uuid4())


class RepoFalso:
    def __init__(self):
        self.usuarios = {ADMIN_ID: {'id': ADMIN_ID, 'email': 'admin@libreria.test', 'role_id': 1, 'activo': True},
                         CLIENTE_ID: {'id': CLIENTE_ID, 'email': 'cliente@x.com', 'role_id': 2, 'activo': True}}
        self.ultimo = None

    def roles(self):
        return [{'role_id': 1, 'nombre': 'administrador'}, {'role_id': 2, 'nombre': 'cliente'}]

    def listar(self, *a):
        return {'total': len(self.usuarios), 'usuarios': list(self.usuarios.values())}

    def obtener(self, uid):
        if uid not in self.usuarios:
            raise NoEncontrado('no')
        return self.usuarios[uid]

    def crear(self, datos):
        if any(u['email'] == datos['email'] for u in self.usuarios.values()):
            raise Conflicto('ERR_EMAIL_DUPLICADO', 'dup')
        uid = str(uuid.uuid4())
        self.ultimo = datos
        self.usuarios[uid] = {'id': uid, 'email': datos['email'], 'role_id': datos['role_id'], 'activo': True}
        return self.usuarios[uid]

    def modificar(self, uid, cambios):
        self.obtener(uid).update({k: v for k, v in cambios.items() if k != 'password_hash'})
        self.ultimo = cambios
        return self.usuarios[uid]

    def eliminar(self, uid):
        self.obtener(uid)                      # 404 si no existe, igual que el repositorio real
        return self.usuarios.pop(uid)


@pytest.fixture
def cliente(monkeypatch):
    redis = fakeredis.FakeRedis(server=fakeredis.FakeServer(), decode_responses=True)
    monkeypatch.setattr(users.servicio.redis, '_cliente', redis)
    users.servicio.redis._abierto_hasta = 0
    repo = RepoFalso()
    monkeypatch.setattr(users, 'repo', repo)
    users.app.testing = True
    c = users.app.test_client()
    c.redis, c.repo = redis, repo
    return c


def bearer(user_id=ADMIN_ID, role_id=1):
    ahora = int(time.time()) - 2
    t = jwt.encode({'sub': user_id, 'user_id': user_id, 'email': 'x@x.com', 'role_id': role_id, 'jti': uuid.uuid4().hex,
                    'typ': 'access', 'iss': 'libreria-login', 'iat': ahora, 'exp': ahora + 1200}, CLAVE, algorithm='HS256')
    return {'Authorization': f'Bearer {t}'}


def test_roles_publico(cliente):
    assert cliente.get('/roles?format=json').get_json()['total'] == 2


def test_listado_es_lectura_administrativa(cliente):
    assert cliente.get('/users?format=json').status_code == 401
    assert cliente.get('/users?format=json', headers=bearer(CLIENTE_ID, 2)).status_code == 403
    assert cliente.get('/users?format=json', headers=bearer()).status_code == 200


def test_detalle_admin_o_propio(cliente):
    assert cliente.get(f'/users/{CLIENTE_ID}?format=json', headers=bearer(CLIENTE_ID, 2)).status_code == 200
    assert cliente.get(f'/users/{ADMIN_ID}?format=json', headers=bearer(CLIENTE_ID, 2)).status_code == 403


def test_crear_requiere_admin_y_hashea(cliente):
    datos = {'nombre': 'Ana', 'apellido_paterno': 'Ruiz', 'email': 'ana@x.com', 'password': 'Secreta123', 'role_id': 2}
    assert cliente.post('/users?format=json', json=datos).status_code == 401
    assert cliente.post('/users?format=json', json=datos, headers=bearer(CLIENTE_ID, 2)).status_code == 403
    r = cliente.post('/users?format=json', json=datos, headers=bearer())
    assert r.status_code == 201
    assert cliente.repo.ultimo['password_hash'].startswith('$2') and 'password' not in cliente.repo.ultimo
    assert cliente.post('/users?format=json', json=datos, headers=bearer()).status_code == 409


@pytest.mark.parametrize('datos,codigo', [
    ({'nombre': 'A', 'apellido_paterno': 'B', 'email': 'malo', 'password': 'Secreta123'}, 'ERR_EMAIL_INVALIDO'),
    ({'nombre': 'A', 'apellido_paterno': 'B', 'email': 'a@b.co', 'password': 'corta'}, 'ERR_PASSWORD_DEBIL'),
    ({'nombre': 'A', 'apellido_paterno': 'B', 'email': 'a@b.co', 'password': 'Secreta123', 'rol': 'x'},
     'ERR_CAMPOS_NO_PERMITIDOS'),
])
def test_validacion_400(cliente, datos, codigo):
    r = cliente.post('/users?format=json', json=datos, headers=bearer())
    assert r.status_code == 400 and r.get_json()['codigo_error'] == codigo


def test_cambio_de_rol_revoca_tokens_del_usuario(cliente):
    r = cliente.patch(f'/users/{CLIENTE_ID}?format=json', json={'role_id': 1}, headers=bearer())
    assert r.status_code == 200 and r.get_json()['tokens_revocados'] is True
    assert cliente.redis.exists(f'jwt:revoked_before:{CLIENTE_ID}')
    # el token anterior del usuario ya no sirve en ningun servicio
    assert cliente.get(f'/users/{CLIENTE_ID}?format=json', headers=bearer(CLIENTE_ID, 2)).status_code == 401


def test_cambio_de_nombre_no_revoca(cliente):
    r = cliente.patch(f'/users/{CLIENTE_ID}?format=json', json={'nombre': 'Otro'}, headers=bearer())
    assert r.get_json()['tokens_revocados'] is False and not cliente.redis.exists(f'jwt:revoked_before:{CLIENTE_ID}')


def test_admin_no_puede_bloquearse_ni_borrarse(cliente):
    assert cliente.patch(f'/users/{ADMIN_ID}?format=json', json={'activo': False}, headers=bearer()).status_code == 400
    assert cliente.delete(f'/users/{ADMIN_ID}?format=json', headers=bearer()).status_code == 400


def test_eliminar(cliente):
    assert cliente.delete(f'/users/{CLIENTE_ID}?format=json', headers=bearer(CLIENTE_ID, 2)).status_code == 403
    assert cliente.delete(f'/users/{CLIENTE_ID}?format=json', headers=bearer()).status_code == 200
    assert cliente.redis.exists(f'jwt:revoked_before:{CLIENTE_ID}')
    assert cliente.delete(f'/users/{CLIENTE_ID}?format=json', headers=bearer()).status_code == 404
