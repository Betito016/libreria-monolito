"""
Proteccion JWT, revocacion y cache del microservicio de libros.

Sin PostgreSQL ni Redis reales: el repositorio se sustituye por uno en
memoria y Redis por fakeredis.

    cd services/books
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
os.environ.update(JWT_SECRET_KEY=CLAVE, REDIS_URL='redis://:x@127.0.0.1:6379/0', ACCESS_TOKEN_MINUTES='20')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as modulo_app  # noqa: E402
from db import database  # noqa: E402
from libreria_common.seguridad import revocar_jti  # noqa: E402

ISBN = '9786047750040'
LIBRO = {'isbn': ISBN, 'titulo': 'Prueba JWT', 'autores': ['A'], 'generos': ['G'], 'anio': 2026, 'precio': 10.0,
         'stock': 1, 'formato': 'eBook', 'categoria': 'Educación', 'imagen_principal': None, 'imagenes': []}
CUERPO = {'isbn': ISBN, 'titulo': 'Prueba JWT', 'autores': ['A'], 'generos': ['G'], 'anio': 2026, 'precio': 10,
          'stock': 1, 'formato': 'eBook', 'categoria': 'Educación', 'imagenes': []}


@pytest.fixture
def cliente(monkeypatch):
    servidor = fakeredis.FakeServer()
    redis = fakeredis.FakeRedis(server=servidor, decode_responses=True)
    monkeypatch.setattr(modulo_app.servicio.redis, '_cliente', redis)
    modulo_app.servicio.redis._abierto_hasta = 0
    llamadas = []
    repo = database.BookRepository
    monkeypatch.setattr(repo, 'search', classmethod(lambda c, f, p, s: llamadas.append('search') or {'total': 1, 'libros': [LIBRO]}))
    monkeypatch.setattr(repo, 'get', classmethod(lambda c, i: llamadas.append('get') or dict(LIBRO, conceptos=[])))
    monkeypatch.setattr(repo, 'list_categories', classmethod(lambda c: ['Educación']))
    monkeypatch.setattr(repo, 'create', classmethod(lambda c, d: llamadas.append('create') or LIBRO))
    monkeypatch.setattr(repo, 'replace', classmethod(lambda c, i, d: llamadas.append('replace') or LIBRO))
    monkeypatch.setattr(repo, 'update', classmethod(lambda c, i, d: llamadas.append('update') or LIBRO))
    monkeypatch.setattr(repo, 'delete', classmethod(lambda c, i: llamadas.append('delete')))
    modulo_app.app.testing = True
    c = modulo_app.app.test_client()
    c.llamadas, c.redis, c.servidor = llamadas, redis, servidor
    return c


def token(role_id=1, minutos=20, clave=CLAVE, alg='HS256', iss='libreria-login', **extra):
    ahora = int(time.time())
    claims = {'sub': 'u1', 'user_id': 'u1', 'email': 'admin@libreria.test', 'role_id': role_id, 'sid': 's1',
              'jti': uuid.uuid4().hex, 'typ': 'access', 'iss': iss, 'iat': ahora, 'exp': ahora + minutos * 60, **extra}
    return jwt.encode(claims, clave, algorithm=alg), claims


def bearer(t):
    return {'Authorization': f'Bearer {t}'}


ESCRITURAS = [
    ('post', '/api/books', CUERPO, 'create'),
    ('put', f'/api/books/{ISBN}', {k: v for k, v in CUERPO.items() if k != 'isbn'}, 'replace'),
    ('patch', f'/api/books/{ISBN}', {'precio': 20}, 'update'),
    ('delete', f'/api/books/{ISBN}', None, 'delete'),
]


# ----------------------------------------------------------------------
# Lectura publica y cache
# ----------------------------------------------------------------------
@pytest.mark.parametrize('ruta', ['/api/books', f'/api/books/{ISBN}', '/books', f'/books/{ISBN}', '/categories'])
def test_get_publico_sin_token(cliente, ruta):
    assert cliente.get(f'{ruta}?format=json').status_code == 200


def test_cache_miss_y_luego_hit(cliente):
    r1 = cliente.get('/api/books?format=json&titulo=cloud')
    r2 = cliente.get('/api/books?titulo=cloud&format=xml')        # otro formato, misma clave
    assert r1.headers['X-Cache'] == 'MISS' and r2.headers['X-Cache'] == 'HIT'
    assert cliente.llamadas.count('search') == 1                   # la 2a no toco PostgreSQL
    assert 0 < cliente.redis.ttl('books:list:page=1&page_size=12&titulo=cloud') <= 60
    d1 = cliente.get(f'/api/books/{ISBN}?format=json')
    d2 = cliente.get(f'/api/books/{ISBN}?format=json')
    assert (d1.headers['X-Cache'], d2.headers['X-Cache']) == ('MISS', 'HIT')
    assert cliente.redis.exists(f'books:{ISBN}')


@pytest.mark.parametrize('metodo,ruta,cuerpo,operacion', ESCRITURAS)
def test_escritura_invalida_la_cache(cliente, metodo, ruta, cuerpo, operacion):
    cliente.get('/api/books?format=json')
    cliente.get(f'/api/books/{ISBN}?format=json')
    assert cliente.redis.exists('books:list:page=1&page_size=12', f'books:{ISBN}') == 2
    t, _ = token()
    r = getattr(cliente, metodo)(f'{ruta}?format=json', json=cuerpo, headers=bearer(t))
    assert r.status_code in (200, 201)
    assert cliente.redis.exists('books:list:page=1&page_size=12', f'books:{ISBN}') == 0
    assert cliente.get('/api/books?format=json').headers['X-Cache'] == 'MISS'


def test_redis_caido_lectura_desde_postgresql(cliente):
    cliente.servidor.connected = False
    r = cliente.get('/api/books?format=json')
    assert r.status_code == 200 and r.headers['X-Cache'] == 'MISS'


# ----------------------------------------------------------------------
# Escrituras protegidas
# ----------------------------------------------------------------------
@pytest.mark.parametrize('metodo,ruta,cuerpo,operacion', ESCRITURAS)
def test_escritura_sin_token_401(cliente, metodo, ruta, cuerpo, operacion):
    r = getattr(cliente, metodo)(f'{ruta}?format=json', json=cuerpo)
    assert r.status_code == 401 and r.get_json()['codigo_error'] == 'ERR_TOKEN_AUSENTE'
    assert operacion not in cliente.llamadas


@pytest.mark.parametrize('metodo,ruta,cuerpo,operacion', ESCRITURAS)
def test_escritura_con_jwt_de_admin(cliente, metodo, ruta, cuerpo, operacion):
    t, _ = token()
    r = getattr(cliente, metodo)(f'{ruta}?format=json', json=cuerpo, headers=bearer(t))
    assert r.status_code == (201 if metodo == 'post' else 200)
    assert operacion in cliente.llamadas


@pytest.mark.parametrize('t', [
    'esto.no.es-un-jwt',
    token(clave='otra-clave-que-no-es-la-del-login-0123456789')[0],
    token(minutos=-1)[0],
    token(alg='HS512')[0],
    token(iss='otro-servicio')[0],
    token(typ='refresh')[0],
])
def test_token_invalido_401(cliente, t):
    r = cliente.patch(f'/api/books/{ISBN}?format=json', json={'precio': 20}, headers=bearer(t))
    assert r.status_code == 401
    assert 'update' not in cliente.llamadas


def test_token_revocado_401(cliente):
    t, claims = token()
    revocar_jti(modulo_app.servicio.redis, claims['jti'], claims['exp'])
    r = cliente.delete(f'/api/books/{ISBN}?format=json', headers=bearer(t))
    assert r.status_code == 401 and r.get_json()['codigo_error'] == 'ERR_TOKEN_REVOCADO'
    assert 'delete' not in cliente.llamadas


def test_redis_caido_escritura_503(cliente):
    t, _ = token()
    cliente.servidor.connected = False
    r = cliente.post('/api/books?format=json', json=CUERPO, headers=bearer(t))
    assert r.status_code == 503 and r.get_json()['codigo_error'] == 'ERR_REDIS_NO_DISPONIBLE'
    assert 'create' not in cliente.llamadas


def test_rol_cliente_403(cliente):
    t, _ = token(role_id=2)
    r = cliente.post('/api/books?format=json', json=CUERPO, headers=bearer(t))
    assert r.status_code == 403 and r.get_json()['codigo_error'] == 'ERR_SIN_PERMISOS'


def test_logs_no_muestran_el_token(cliente, caplog):
    t, _ = token()
    with caplog.at_level('INFO'):
        cliente.patch(f'/api/books/{ISBN}?format=json', json={'precio': 20}, headers=bearer(t))
    assert '[JWT PRESENTE' in caplog.text and t not in caplog.text


def test_metrics(cliente):
    cliente.get('/api/books?format=json'); cliente.get('/api/books?format=json')
    m = cliente.get('/metrics?format=json').get_json()
    assert m['contadores']['cache_aciertos'] >= 1 and m['redis']['disponible'] is True
