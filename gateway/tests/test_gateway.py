"""
Pruebas funcionales del Library API Gateway (contra la instancia real).

    $env:GATEWAY_URL = 'http://34.135.84.31:8080'     # o 'http://34.135.84.31' (puerto 80)
    $env:GATEWAY_EMAIL = '<correo admin>'; $env:GATEWAY_PASSWORD = '<contraseña>'   # no se guardan aquí
    python -m pytest -v tests/test_gateway.py

Cada prueba dice qué requisito (RF) comprueba. Las que escriben datos crean un
libro de prueba con ISBN único y lo borran al final.
"""
import os
import random
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

import pytest
import requests

GW = os.environ.get('GATEWAY_URL', 'http://34.135.84.31:8080').rstrip('/')
T = 15
SERVICIOS = {'login': 'login', 'books': 'books', 'pagos': 'pagos', 'pedidos': 'pedidos',
             'users': 'users', 'autores': 'authors'}


@pytest.fixture(scope='module')
def sesion():
    """Login de administrador A TRAVÉS del gateway; devuelve (requests.Session, jwt)."""
    correo, clave = os.environ.get('GATEWAY_EMAIL'), os.environ.get('GATEWAY_PASSWORD')
    if not correo or not clave:
        pytest.skip('Define GATEWAY_EMAIL y GATEWAY_PASSWORD')
    s = requests.Session()
    r = s.post(f'{GW}/api/login/login?format=json', json={'email': correo, 'password': clave}, timeout=T)
    assert r.status_code == 200, r.text[:200]
    assert 'Set-Cookie' in r.headers, 'la cookie de sesión no atravesó el gateway'
    yield s, r.json()['token']['access_token']
    s.post(f'{GW}/api/login/logout?format=json', headers={'Authorization': f"Bearer {r.json()['token']['access_token']}"},
           timeout=T)


# ---------------------------------------------------------------- RF1 rutas
@pytest.mark.parametrize('prefijo,nombre', SERVICIOS.items())
def test_rf1_cada_prefijo_llega_a_su_servicio(prefijo, nombre):
    """/api/<prefijo>/health llega al /health del servicio correcto (el prefijo se quita)."""
    r = requests.get(f'{GW}/api/{prefijo}/health?format=json', timeout=T)
    assert r.status_code == 200
    assert r.json()['microservicio'] == nombre


def test_rf1_soap_para_electron():
    """La app Electron consume XML del servicio SOAP/REST a través del gateway."""
    r = requests.get(f'{GW}/api/soap/books', headers={'Accept': 'application/xml'}, timeout=T)
    assert r.status_code == 200
    ET.fromstring(r.content)                          # XML bien formado


def test_rf1_ruta_desconocida_404():
    assert requests.get(f'{GW}/api/inexistente/algo', timeout=T).status_code == 404


def test_raiz_segun_el_puerto():
    """:8080 es solo API (la raíz es 404). :80 publica además el monolito en la raíz,
    como la demo de clase: http://IP/ -> monolito, http://IP/api/... -> microservicios."""
    r = requests.get(f'{GW}/', timeout=T)
    if urlsplit(GW).port in (None, 80):
        assert r.status_code == 200 and '<html' in r.text.lower()
        viejo = requests.get(f'{GW}/library/login', timeout=T, allow_redirects=False)
        assert viejo.status_code == 301 and viejo.headers['Location'].endswith('/login')
    else:
        assert r.status_code == 404


# ---------------------------------------------------------------- RF3, RF5, RF6, RF7
def test_rf3_round_robin_entre_dos_instancias_de_libros():
    """Peticiones seguidas al catálogo alternan entre :5001 y :6001 (cabecera X-Gateway-Instancia)."""
    instancias = [requests.get(f'{GW}/api/books/books?format=json&page_size=1', timeout=T)
                  .headers.get('X-Gateway-Instancia') for _ in range(4)]
    assert set(instancias) == {'127.0.0.1:5001', '127.0.0.1:6001'}, instancias


def test_rf5_salud_agregada_por_servicio_e_instancia():
    r = requests.get(f'{GW}/health', timeout=T)
    datos = r.json()
    assert r.status_code == (200 if datos['estado'] == 'ok' else 503)
    assert set(datos['servicios']) >= {'login', 'books', 'pagos', 'pedidos', 'users', 'autores'}
    assert [i['url'] for i in datos['servicios']['books']['instancias']] == \
        ['http://127.0.0.1:5001', 'http://127.0.0.1:6001']


def test_rf6_error_del_gateway_en_json_con_request_id():
    r = requests.get(f'{GW}/api/inexistente/x', timeout=T)
    datos = r.json()
    assert r.status_code == 404 and datos['codigo_error'] == 'ERR_GATEWAY_RUTA'
    assert datos['request_id'] == r.headers['X-Request-ID']


def test_rf7_request_id_generado_y_respetado():
    r = requests.get(f'{GW}/api/autores/health?format=json', timeout=T)
    assert len(r.headers['X-Request-ID']) >= 12                      # generado por el gateway
    r = requests.get(f'{GW}/api/autores/health?format=json', headers={'X-Request-ID': 'prueba-rf7-123'}, timeout=T)
    assert r.headers['X-Request-ID'] == 'prueba-rf7-123'             # el del cliente se conserva


# ---------------------------------------------------------------- RF2 reenvío intacto
def test_rf2_query_intacta():
    r = requests.get(f'{GW}/api/books/api/books?page_size=3&titulo=cloud&format=json', timeout=T)
    datos = r.json()
    assert r.status_code == 200 and datos['page_size'] == 3 and datos['filtros'].get('titulo') == 'cloud'


def test_rf2_ruta_con_alias_de_la_clase():
    """Ruta de la diapositiva 15: /api/books/books -> /books del servicio."""
    r = requests.get(f'{GW}/api/books/books?format=json', timeout=T)
    assert r.status_code == 200 and 'libros' in r.json()


def test_rf2_cookie_atraviesa_el_gateway(sesion):
    """La cookie que dejó POST /login (Set-Cookie) vuelve al servicio en GET /session."""
    s, _ = sesion
    r = s.get(f'{GW}/api/login/session?format=json', timeout=T)
    assert r.status_code == 200 and r.json()['autenticado'] is True


def test_rf2_authorization_llega_al_servicio(sesion):
    s, token = sesion
    assert requests.get(f'{GW}/api/users/users?format=json', timeout=T).status_code == 401
    r = requests.get(f'{GW}/api/users/users?format=json', headers={'Authorization': f'Bearer {token}'}, timeout=T)
    assert r.status_code == 200 and 'usuarios' in r.json()


def test_rf2_post_patch_delete_con_cuerpo(sesion):
    """Escrituras con cuerpo JSON y Bearer a través del gateway (libro de prueba, se borra)."""
    _, token = sesion
    h = {'Authorization': f'Bearer {token}'}
    isbn = '979999' + ''.join(random.choices('0123456789', k=7))
    libro = {'isbn': isbn, 'titulo': f'Prueba gateway {isbn}', 'autores': ['Carlos Vega'], 'anio': 2026,
             'precio': 100, 'stock': 1, 'formato': 'eBook', 'categoria': 'Literatura'}
    try:
        r = requests.post(f'{GW}/api/books/api/books?format=json', json=libro, headers=h, timeout=T)
        assert r.status_code == 201, r.text[:200]
        # El servicio responde Location relativo a ÉL (/api/books/<isbn>); el gateway le
        # antepone su prefijo (nginx la devuelve absoluta, apuntando al propio gateway).
        assert r.headers['Location'] in (f'/api/books/api/books/{isbn}', f'{GW}/api/books/api/books/{isbn}')
        assert requests.get(r.headers['Location'] if r.headers['Location'].startswith('http')
                            else GW + r.headers['Location'], params={'format': 'json'}, timeout=T).status_code == 200
        r = requests.patch(f'{GW}/api/books/api/books/{isbn}?format=json', json={'precio': 150}, headers=h, timeout=T)
        assert r.status_code == 200 and r.json()['libro']['precio'] == 150
    finally:
        r = requests.delete(f'{GW}/api/books/api/books/{isbn}?format=json', headers=h, timeout=T)
        assert r.status_code in (200, 404)
