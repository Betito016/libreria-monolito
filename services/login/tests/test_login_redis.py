"""
Flujo de login con sesion, refresh token y revocacion en Redis (fakeredis).
La base de datos se sustituye por un repositorio en memoria.
"""
import os
import sys
import time
from pathlib import Path

import bcrypt
import fakeredis
import jwt
import pytest

CLAVE = 'clave-de-prueba-solo-para-tests-0123456789abcdef'
os.environ.update(JWT_SECRET_KEY=CLAVE, REDIS_URL='redis://:x@127.0.0.1:6379/0', ACCESS_TOKEN_MINUTES='20',
                  SESSION_TTL_MINUTES='60', MAIL_ENABLED='False', VERIFY_EMAIL_MX='False')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as login  # noqa: E402
from db.database import UserRepository  # noqa: E402

PASSWORD = 'Password123'
USUARIO = {'id': 'a1b2', 'nombre': 'Admin', 'apellido_paterno': 'Biblioteca', 'apellido_materno': None,
           'email': 'admin@libreria.test', 'rol': 'administrador', 'role_id': 1, 'activo': True,
           'email_verificado': True, 'password_hash': bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(4)).decode()}


@pytest.fixture
def entorno(monkeypatch):
    servidor = fakeredis.FakeServer()
    redis = fakeredis.FakeRedis(server=servidor, decode_responses=True)
    monkeypatch.setattr(login.servicio.redis, '_cliente', redis)
    login.servicio.redis._abierto_hasta = 0
    usuario = dict(USUARIO)
    monkeypatch.setattr(UserRepository, 'find_by_email', classmethod(lambda c, e: dict(usuario) if e == usuario['email'] else None))
    monkeypatch.setattr(UserRepository, 'find_by_id', classmethod(lambda c, i: dict(usuario) if i == usuario['id'] else None))
    monkeypatch.setattr(UserRepository, 'get_password_hash', classmethod(lambda c, i: usuario['password_hash']))
    monkeypatch.setattr(UserRepository, 'update_profile',
                        classmethod(lambda c, i, cambios: usuario.update(cambios) or dict(usuario)))
    login.app.testing = True
    return login.app.test_client(), redis, servidor, usuario


def iniciar(cliente):
    r = cliente.post('/login?format=json', json={'email': USUARIO['email'], 'password': PASSWORD})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def bearer(t):
    return {'Authorization': f'Bearer {t}'}


def test_login_guarda_sesion_y_refresh_en_redis_con_ttl(entorno):
    cliente, redis, _, _ = entorno
    datos = iniciar(cliente)
    token = datos['token']
    claims = jwt.decode(token['access_token'], CLAVE, algorithms=['HS256'])
    assert claims['exp'] - claims['iat'] == 1200 and claims['role_id'] == 1 and claims['user_id'] == 'a1b2'
    assert token['refresh_token'] and token['refresh_expires_in'] == 3600
    sid = claims['sid']
    assert 3590 <= redis.ttl(f'session:{sid}') <= 3600
    refresh_keys = list(redis.scan_iter('refresh:*'))
    assert len(refresh_keys) == 1 and redis.get(refresh_keys[0]) == sid
    assert token['refresh_token'] not in str(redis.get(f'session:{sid}'))      # en Redis solo la huella
    assert datos['sesion']['segundos_restantes'] <= 1200


def test_credenciales_invalidas_401(entorno):
    cliente, *_ = entorno
    r = cliente.post('/login?format=json', json={'email': USUARIO['email'], 'password': 'mal'})
    assert r.status_code == 401


def test_refresh_rota_tokens_y_revoca_el_anterior(entorno):
    cliente, redis, _, _ = entorno
    viejo = iniciar(cliente)['token']
    time.sleep(1.05)
    r = cliente.post('/token/refresh?format=json', json={'refresh_token': viejo['refresh_token']})
    assert r.status_code == 200
    nuevo = r.get_json()['token']
    assert nuevo['access_token'] != viejo['access_token'] and nuevo['refresh_token'] != viejo['refresh_token']
    jti_viejo = jwt.decode(viejo['access_token'], CLAVE, algorithms=['HS256'])['jti']
    assert redis.exists(f'jwt:revoked:{jti_viejo}')
    # El refresh anterior es de un solo uso.
    r = cliente.post('/token/refresh?format=json', json={'refresh_token': viejo['refresh_token']})
    assert r.status_code == 401 and r.get_json()['codigo_error'] == 'ERR_REFRESH_INVALIDO'


def test_logout_revoca_jwt_y_borra_sesion_y_refresh(entorno):
    cliente, redis, _, _ = entorno
    token = iniciar(cliente)['token']
    claims = jwt.decode(token['access_token'], CLAVE, algorithms=['HS256'])
    r = cliente.post('/logout?format=json', headers=bearer(token['access_token']))
    assert r.status_code == 200 and r.get_json()['jwt_revocado'] is True
    assert redis.exists(f"jwt:revoked:{claims['jti']}")
    assert 0 < redis.ttl(f"jwt:revoked:{claims['jti']}") <= 1200
    assert not redis.exists(f"session:{claims['sid']}")
    assert not list(redis.scan_iter('refresh:*'))
    # El token revocado ya no sirve en un endpoint protegido...
    assert cliente.patch('/profile?format=json', json={'nombre': 'X'}, headers=bearer(token['access_token'])).status_code == 401
    # ...ni el refresh token para renovar.
    assert cliente.post('/token/refresh?format=json', json={'refresh_token': token['refresh_token']}).status_code == 401


def test_session_con_cookie(entorno):
    cliente, *_ = entorno
    iniciar(cliente)                                     # el test client guarda la cookie
    r = cliente.get('/session?format=json')
    assert r.get_json()['autenticado'] is True and r.get_json()['sesion']['almacen'] == 'redis'
    assert cliente.post('/session/extend?format=json').status_code == 200


def test_redis_caido_login_503(entorno):
    cliente, _, servidor, _ = entorno
    servidor.connected = False
    r = cliente.post('/login?format=json', json={'email': USUARIO['email'], 'password': PASSWORD})
    assert r.status_code == 503 and r.get_json()['codigo_error'] == 'ERR_REDIS_NO_DISPONIBLE'


def test_cambio_de_password_revoca_todo(entorno):
    cliente, redis, _, _ = entorno
    token = iniciar(cliente)['token']
    time.sleep(1.05)
    r = cliente.patch('/profile?format=json', headers=bearer(token['access_token']),
                      json={'password': 'OtraPassword456', 'password_actual': PASSWORD})
    assert r.status_code == 200 and r.get_json()['sesiones_cerradas'] is True
    assert redis.exists('jwt:revoked_before:a1b2')
    assert not list(redis.scan_iter('session:*'))
    assert cliente.patch('/profile?format=json', json={'nombre': 'Y'}, headers=bearer(token['access_token'])).status_code == 401


def test_profile_sin_token_401(entorno):
    cliente, *_ = entorno
    assert cliente.patch('/profile?format=json', json={'nombre': 'X'}).status_code == 401


def test_health_reporta_redis(entorno, monkeypatch):
    cliente, *_ = entorno
    monkeypatch.setattr(UserRepository, 'ping', classmethod(lambda c: {'conectado': True}))
    datos = cliente.get('/health?format=json').get_json()
    assert datos['redis']['disponible'] is True and datos['estado'] == 'ok'
