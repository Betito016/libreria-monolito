"""
Pruebas de la proteccion JWT del microservicio de libros.

No necesitan PostgreSQL ni el servicio de login: el repositorio se sustituye
por uno en memoria y los tokens se firman aqui con la clave de prueba, igual
que lo hace services/login/auth/jwt_tokens.py.

    cd services/books
    venv\\Scripts\\python -m pytest -q
"""
import os
import sys
import time
from pathlib import Path

import jwt
import pytest

CLAVE = 'clave-de-prueba-solo-para-tests-0123456789abcdef'
# Antes de importar la app: load_dotenv no pisa variables ya definidas.
os.environ['JWT_SECRET'] = CLAVE
os.environ['JWT_ALGORITHM'] = 'HS256'
os.environ['JWT_ISSUER'] = 'libreria-login'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as modulo_app  # noqa: E402
from db import database  # noqa: E402

ISBN = '9786047750040'
LIBRO = {
    'isbn': ISBN, 'titulo': 'Prueba JWT', 'autores': ['A'], 'generos': ['G'], 'anio': 2026,
    'precio': 10.0, 'stock': 1, 'formato': 'eBook', 'categoria': 'Educación',
    'imagen_principal': None, 'imagenes': [],
}
CUERPO = {'isbn': ISBN, 'titulo': 'Prueba JWT', 'autores': ['A'], 'generos': ['G'], 'anio': 2026,
          'precio': 10, 'stock': 1, 'formato': 'eBook', 'categoria': 'Educación', 'imagenes': []}


@pytest.fixture
def cliente(monkeypatch):
    """Repositorio en memoria: registra que operacion llego a ejecutarse."""
    llamadas = []
    repo = database.BookRepository
    monkeypatch.setattr(repo, 'search', classmethod(
        lambda cls, f, p, s: {'total': 1, 'libros': [LIBRO]}))
    monkeypatch.setattr(repo, 'get', classmethod(lambda cls, isbn: dict(LIBRO, conceptos=[])))
    monkeypatch.setattr(repo, 'create', classmethod(lambda cls, d: llamadas.append('create') or LIBRO))
    monkeypatch.setattr(repo, 'replace', classmethod(lambda cls, i, d: llamadas.append('replace') or LIBRO))
    monkeypatch.setattr(repo, 'update', classmethod(lambda cls, i, d: llamadas.append('update') or LIBRO))
    monkeypatch.setattr(repo, 'delete', classmethod(lambda cls, i: llamadas.append('delete')))
    modulo_app.app.testing = True
    c = modulo_app.app.test_client()
    c.llamadas = llamadas
    return c


def token(rol='administrador', exp_en=1800, clave=CLAVE, alg='HS256', iss='libreria-login', **extra):
    ahora = int(time.time())
    claims = {'sub': '1', 'email': 'admin@libreria.test', 'rol': rol, 'iss': iss,
              'iat': ahora, 'exp': ahora + exp_en, **extra}
    return jwt.encode(claims, clave, algorithm=alg)


def bearer(t):
    return {'Authorization': f'Bearer {t}'}


ESCRITURAS = [
    ('post', '/api/books', CUERPO, 'create'),
    ('put', f'/api/books/{ISBN}', {k: v for k, v in CUERPO.items() if k != 'isbn'}, 'replace'),
    ('patch', f'/api/books/{ISBN}', {'precio': 20}, 'update'),
    ('delete', f'/api/books/{ISBN}', None, 'delete'),
]


# ----------------------------------------------------------------------
# Lectura publica
# ----------------------------------------------------------------------
@pytest.mark.parametrize('ruta', ['/api/books', f'/api/books/{ISBN}', '/books', f'/books/{ISBN}'])
def test_get_publico_sin_token(cliente, ruta):
    r = cliente.get(f'{ruta}?format=json')
    assert r.status_code == 200


def test_get_publico_ignora_token_invalido(cliente):
    """Un GET no valida tokens: aunque llegue uno basura, el catalogo responde."""
    r = cliente.get('/api/books?format=json', headers=bearer('basura'))
    assert r.status_code == 200


# ----------------------------------------------------------------------
# Escrituras
# ----------------------------------------------------------------------
@pytest.mark.parametrize('metodo,ruta,cuerpo,operacion', ESCRITURAS)
def test_escritura_sin_token_401(cliente, metodo, ruta, cuerpo, operacion):
    r = getattr(cliente, metodo)(f'{ruta}?format=json', json=cuerpo)
    assert r.status_code == 401
    assert r.get_json()['codigo_error'] == 'ERR_TOKEN_AUSENTE'
    assert r.headers['WWW-Authenticate'].startswith('Bearer')
    assert operacion not in cliente.llamadas


@pytest.mark.parametrize('metodo,ruta,cuerpo,operacion', ESCRITURAS)
def test_escritura_con_jwt_valido(cliente, metodo, ruta, cuerpo, operacion):
    r = getattr(cliente, metodo)(f'{ruta}?format=json', json=cuerpo, headers=bearer(token()))
    assert r.status_code == (201 if metodo == 'post' else 200)
    assert operacion in cliente.llamadas


@pytest.mark.parametrize('metodo,ruta,cuerpo,operacion', ESCRITURAS)
def test_alias_sin_prefijo_api_tambien_protegido(cliente, metodo, ruta, cuerpo, operacion):
    ruta = ruta.replace('/api', '')
    assert getattr(cliente, metodo)(f'{ruta}?format=json', json=cuerpo).status_code == 401
    r = getattr(cliente, metodo)(f'{ruta}?format=json', json=cuerpo, headers=bearer(token()))
    assert r.status_code in (200, 201)


@pytest.mark.parametrize('headers,codigo', [
    ({'Authorization': 'Bearer esto.no.es-un-jwt'}, 'ERR_TOKEN_INVALIDO'),
    ({'Authorization': f"Basic {token()}"}, 'ERR_TOKEN_INVALIDO'),
    ({'Authorization': 'Bearer'}, 'ERR_TOKEN_AUSENTE'),
    ({'Authorization': 'Bearer   '}, 'ERR_TOKEN_AUSENTE'),
    ({'Authorization': ''}, 'ERR_TOKEN_AUSENTE'),
])
def test_header_mal_formado_401(cliente, headers, codigo):
    r = cliente.patch(f'/api/books/{ISBN}?format=json', json={'precio': 20}, headers=headers)
    assert r.status_code == 401
    assert r.get_json()['codigo_error'] == codigo
    assert 'update' not in cliente.llamadas


def test_firma_invalida_401(cliente):
    otro = token(clave='otra-clave-que-no-es-la-del-login-0123456789')
    r = cliente.patch(f'/api/books/{ISBN}?format=json', json={'precio': 20}, headers=bearer(otro))
    assert r.status_code == 401
    assert r.get_json()['codigo_error'] == 'ERR_TOKEN_INVALIDO'


def test_token_alterado_401(cliente):
    """Cambiar el payload (p. ej. rol) sin volver a firmar invalida la firma."""
    cabecera, payload, firma = token(rol='cliente').split('.')
    admin_payload = token().split('.')[1]
    r = cliente.delete(f'/api/books/{ISBN}?format=json', headers=bearer(f'{cabecera}.{admin_payload}x.{firma}'))
    assert r.status_code == 401


def test_token_expirado_401(cliente):
    r = cliente.patch(f'/api/books/{ISBN}?format=json', json={'precio': 20}, headers=bearer(token(exp_en=-60)))
    assert r.status_code == 401
    assert r.get_json()['codigo_error'] == 'ERR_TOKEN_EXPIRADO'


def test_algoritmo_distinto_401(cliente):
    otro = token(alg='HS512')
    r = cliente.patch(f'/api/books/{ISBN}?format=json', json={'precio': 20}, headers=bearer(otro))
    assert r.status_code == 401


def test_algoritmo_none_401(cliente):
    sin_firma = jwt.encode({'sub': '1', 'rol': 'administrador', 'iss': 'libreria-login',
                            'iat': int(time.time()), 'exp': int(time.time()) + 600}, None, algorithm='none')
    r = cliente.patch(f'/api/books/{ISBN}?format=json', json={'precio': 20}, headers=bearer(sin_firma))
    assert r.status_code == 401


def test_emisor_distinto_401(cliente):
    r = cliente.patch(f'/api/books/{ISBN}?format=json', json={'precio': 20},
                      headers=bearer(token(iss='otro-servicio')))
    assert r.status_code == 401


def test_token_de_cliente_403(cliente):
    r = cliente.post('/api/books?format=json', json=CUERPO, headers=bearer(token(rol='cliente')))
    assert r.status_code == 403
    assert r.get_json()['codigo_error'] == 'ERR_SIN_PERMISOS'
    assert 'create' not in cliente.llamadas


def test_location_respeta_prefijo(cliente):
    r = cliente.post('/api/books?format=json', json=CUERPO, headers=bearer(token()))
    assert r.headers['Location'] == f'/api/books/{ISBN}'


def test_logs_no_muestran_el_token(cliente, caplog):
    t = token()
    with caplog.at_level('INFO'):
        cliente.patch(f'/api/books/{ISBN}?format=json', json={'precio': 20}, headers=bearer(t))
    texto = caplog.text
    assert '[JWT PRESENTE' in texto
    assert 'PROTEGIDO (requiere JWT)' in texto
    assert t not in texto
