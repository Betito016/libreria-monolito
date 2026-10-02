"""
Pruebas del manejo del JWT en el cliente HTTP de la app (sin red: se
sustituye la llamada de requests y se revisan los headers que se enviarian).

    cd apps/Python_app
    venv\\Scripts\\python -m pytest -q
"""
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libreria_app.api.http_client import ApiClient  # noqa: E402
from libreria_app.config.settings import AppConfig  # noqa: E402

TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.firma-de-prueba-abcd'


class RespuestaFalsa:
    status_code = 200

    def json(self):
        return {'estado': 'exito', 'mensaje': 'ok'}


@pytest.fixture
def api(monkeypatch):
    cliente = ApiClient(lambda: AppConfig())
    cliente.enviados = []

    def falso(metodo, url, **kwargs):
        cliente.enviados.append((metodo, url, kwargs.get('headers') or {}))
        return RespuestaFalsa()

    monkeypatch.setattr(cliente.session, 'request', falso)
    return cliente


@pytest.mark.parametrize('metodo', ['POST', 'PUT', 'PATCH', 'DELETE'])
def test_escrituras_a_libros_llevan_bearer(api, metodo):
    api.token = TOKEN
    api.request('books', metodo, '/api/books/123', json_body={'precio': 1} if metodo != 'DELETE' else None)
    assert api.enviados[-1][2]['Authorization'] == f'Bearer {TOKEN}'


@pytest.mark.parametrize('servicio,metodo,ruta', [
    ('books', 'GET', '/api/books'),
    ('books', 'GET', '/api/books/123'),
    ('login', 'POST', '/login'),
    ('login', 'PATCH', '/profile'),
])
def test_lecturas_y_login_sin_bearer(api, servicio, metodo, ruta):
    api.token = TOKEN
    api.request(servicio, metodo, ruta)
    assert 'Authorization' not in api.enviados[-1][2]


def test_sin_token_la_escritura_viaja_sin_authorization(api):
    api.token = None
    api.request('books', 'POST', '/api/books', json_body={'isbn': '1'})
    assert 'Authorization' not in api.enviados[-1][2]


def test_logs_marcan_el_bearer_sin_revelarlo(api, caplog):
    api.token = TOKEN
    with caplog.at_level(logging.INFO, logger='libreria.http'):
        api.request('books', 'PATCH', '/api/books/123', json_body={'precio': 150})
    texto = caplog.text
    assert 'PATCH' in texto and '/api/books/123' in texto
    assert 'Authorization: Bearer [JWT PRESENTE' in texto
    assert 'REQUERIDA (JWT)' in texto
    assert '"precio": 150' in texto
    assert 'HTTP 200' in texto
    assert TOKEN not in texto


class RespuestaLogin(RespuestaFalsa):
    def json(self):
        return {'estado': 'exito', 'mensaje': 'ok',
                'usuario': {'id': '1', 'nombre': 'Admin', 'email': 'admin@libreria.test', 'rol': 'administrador'},
                'sesion': {'segundos_restantes': 1800, 'duracion_minutos': 30},
                'token': {'access_token': TOKEN, 'token_type': 'Bearer', 'algoritmo': 'HS256', 'expires_in': 1800}}


class AlmacenEnMemoria:
    """SessionStore falso: no toca %APPDATA%."""

    def __init__(self):
        self.datos = {}

    def guardar(self, url, cookies, usuario, token=None):
        self.datos[url] = token

    def borrar(self, url):
        self.datos.pop(url, None)

    def token(self, url):
        return self.datos.get(url)


def test_logout_elimina_el_jwt_y_ya_no_se_envia(monkeypatch):
    from libreria_app.services.auth_service import AuthService

    api = ApiClient(lambda: AppConfig())
    enviados = []

    def falso(metodo, url, **kwargs):
        enviados.append((metodo, url, kwargs.get('headers') or {}))
        return RespuestaLogin() if url.split('?')[0].endswith('/login') else RespuestaFalsa()

    monkeypatch.setattr(api.session, 'request', falso)
    almacen = AlmacenEnMemoria()
    auth = AuthService(api, almacen, lambda: AppConfig())

    auth.iniciar_sesion('admin@libreria.test', 'x')
    assert api.token == TOKEN                                     # recibido y conservado
    assert almacen.token(AppConfig().login_url) == TOKEN          # y guardado para reabrir la app
    api.request('books', 'PATCH', '/api/books/1', json_body={'precio': 1})
    assert enviados[-1][2]['Authorization'] == f'Bearer {TOKEN}'  # se envia mientras hay sesion

    auth.cerrar_sesion()
    assert enviados[-1][1].split('?')[0].endswith('/logout')
    assert 'Authorization' not in enviados[-1][2]                 # /logout no lleva Bearer
    assert api.token is None                                      # borrado de memoria
    assert almacen.token(AppConfig().login_url) is None           # y de disco
    assert auth.sesion is None

    for metodo in ('POST', 'PUT', 'PATCH', 'DELETE', 'GET'):
        api.request('books', metodo, '/api/books/1', json_body={'precio': 1} if metodo != 'GET' else None)
        assert 'Authorization' not in enviados[-1][2], metodo     # ninguna peticion posterior lo lleva


def test_registro_http_indica_autenticacion(api):
    api.token = TOKEN
    api.request('books', 'DELETE', '/api/books/123')
    api.request('books', 'GET', '/api/books')
    historial = api.historial()
    assert historial[0].autenticacion == 'Bearer'
    assert historial[1].autenticacion == '—'
