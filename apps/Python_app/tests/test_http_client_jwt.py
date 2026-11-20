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
from libreria_app.config.settings import SERVICIOS, AppConfig  # noqa: E402

TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.firma-de-prueba-abcd'
REFRESH = 'refresh-de-prueba-0123456789abcdef0123456789abcdef'


class RespuestaFalsa:
    status_code = 200
    headers = {}

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


@pytest.mark.parametrize('url,valida', [
    ('http://34.135.84.31:5001', True),
    ('http://34.135.84.31:8080/api/books', True),          # prefijo del API Gateway
    ('http://34.135.84.31:8080/api/autores/', True),
    ('http://34.135.84.31:5001/books', False),             # ruta de un endpoint: error de captura
    ('http://34.135.84.31:8080/api/books/books', False),
])
def test_urls_directas_y_del_gateway(url, valida):
    from libreria_app.config.settings import validar_url
    assert (validar_url(url, 'Libros') == []) is valida


def test_url_del_gateway_se_une_con_la_ruta_del_servicio():
    """Base del gateway + ruta del servicio: /api/books + /api/books/123 -> el gateway
    quita el prefijo /api/books y el servicio recibe /api/books/123, la ruta que ya conoce."""
    config = AppConfig(books_url='http://34.135.84.31:8080/api/books')
    cliente = ApiClient(lambda: config)
    assert cliente.construir_url('books', '/api/books/123').startswith(
        'http://34.135.84.31:8080/api/books/api/books/123?')


def test_configuracion_tiene_los_seis_servicios():
    config = AppConfig()
    assert [s for s, _, _ in SERVICIOS] == ['login', 'books', 'users', 'authors', 'pedidos', 'pagos']
    # Por defecto todo va al API Gateway (un solo punto de entrada, sin puertos).
    esperadas = {'login': 'login', 'books': 'books', 'users': 'users', 'authors': 'autores',
                 'pedidos': 'pedidos', 'pagos': 'pagos'}
    for servicio, prefijo in esperadas.items():
        assert config.url(servicio) == f'http://34.135.84.31/api/{prefijo}'
    assert config.validar() == []


@pytest.mark.parametrize('metodo', ['POST', 'PUT', 'PATCH', 'DELETE'])
def test_escrituras_a_libros_llevan_bearer(api, metodo):
    api.token = TOKEN
    api.request('books', metodo, '/api/books/123', json_body={'precio': 1} if metodo != 'DELETE' else None)
    assert api.enviados[-1][2]['Authorization'] == f'Bearer {TOKEN}'


@pytest.mark.parametrize('servicio,metodo,ruta', [
    ('users', 'GET', '/users'),
    ('users', 'DELETE', '/users/abc'),
    ('authors', 'POST', '/authors'),
    ('pedidos', 'GET', '/orders'),
    ('pedidos', 'POST', '/orders'),
    ('pagos', 'GET', '/payments'),
    ('pagos', 'PATCH', '/payments/1'),
    ('login', 'PATCH', '/profile'),
    ('login', 'POST', '/logout'),
])
def test_rutas_protegidas_llevan_bearer(api, servicio, metodo, ruta):
    api.token = TOKEN
    api.request(servicio, metodo, ruta)
    assert api.enviados[-1][2]['Authorization'] == f'Bearer {TOKEN}'


@pytest.mark.parametrize('servicio,metodo,ruta', [
    ('books', 'GET', '/api/books'),
    ('books', 'GET', '/api/books/123'),
    ('authors', 'GET', '/authors'),
    ('users', 'GET', '/roles'),
    ('pagos', 'GET', '/health'),
    ('pedidos', 'GET', '/metrics'),
    ('login', 'POST', '/login'),
    ('login', 'POST', '/token/refresh'),
    ('login', 'GET', '/session'),
])
def test_rutas_publicas_sin_bearer(api, servicio, metodo, ruta):
    api.token = TOKEN
    api.request(servicio, metodo, ruta)
    assert 'Authorization' not in api.enviados[-1][2]
    assert not ApiClient.requiere_jwt(servicio, metodo, ruta)


def test_sin_token_la_escritura_viaja_sin_authorization(api):
    api.token = None
    api.request('books', 'POST', '/api/books', json_body={'isbn': '1'})
    assert 'Authorization' not in api.enviados[-1][2]


def test_logs_marcan_el_bearer_sin_revelarlo(api, caplog):
    api.token = TOKEN
    with caplog.at_level(logging.INFO, logger='libreria.http'):
        api.request('books', 'PATCH', '/api/books/123', json_body={'precio': 150})
        api.request('login', 'POST', '/token/refresh', json_body={'refresh_token': REFRESH})
    texto = caplog.text
    assert 'PATCH' in texto and '/api/books/123' in texto
    assert 'Authorization: Bearer [JWT PRESENTE' in texto
    assert 'REQUERIDA (JWT)' in texto
    assert '"precio": 150' in texto
    assert 'HTTP 200' in texto
    assert TOKEN not in texto
    assert REFRESH not in texto                                   # el refresh token tambien se enmascara


class RespuestaLogin(RespuestaFalsa):
    def json(self):
        return {'estado': 'exito', 'mensaje': 'ok',
                'usuario': {'id': '1', 'nombre': 'Admin', 'email': 'admin@libreria.test', 'rol': 'administrador',
                            'role_id': 1},
                'sesion': {'segundos_restantes': 1200, 'duracion_minutos': 20},
                'token': {'access_token': TOKEN, 'refresh_token': REFRESH, 'token_type': 'Bearer',
                          'algoritmo': 'HS256', 'expires_in': 1200}}


class AlmacenEnMemoria:
    """SessionStore falso: no toca %APPDATA%."""

    def __init__(self):
        self.datos = {}

    def guardar(self, url, cookies, usuario, tokens=None):
        self.datos[url] = dict(tokens or {})

    def borrar(self, url):
        self.datos.pop(url, None)

    def tokens(self, url):
        return dict(self.datos.get(url) or {})

    def token(self, url):
        return self.tokens(url).get('access')


def test_logout_revoca_y_elimina_el_jwt(monkeypatch):
    from libreria_app.services.auth_service import AuthService

    api = ApiClient(lambda: AppConfig())
    enviados = []

    def falso(metodo, url, **kwargs):
        enviados.append((metodo, url, kwargs.get('headers') or {}, kwargs.get('json')))
        return RespuestaLogin() if url.split('?')[0].endswith('/login') else RespuestaFalsa()

    monkeypatch.setattr(api.session, 'request', falso)
    almacen = AlmacenEnMemoria()
    auth = AuthService(api, almacen, lambda: AppConfig())

    auth.iniciar_sesion('admin@libreria.test', 'x')
    assert api.token == TOKEN                                     # recibido y conservado
    assert auth.refresh_token == REFRESH
    assert auth.sesion.es_administrador
    assert almacen.token(AppConfig().login_url) == TOKEN          # y guardado para reabrir la app
    api.request('pedidos', 'GET', '/orders')
    assert enviados[-1][2]['Authorization'] == f'Bearer {TOKEN}'  # se envia mientras hay sesion

    auth.cerrar_sesion()
    metodo, url, headers, cuerpo = enviados[-1]
    assert url.split('?')[0].endswith('/logout')
    assert headers['Authorization'] == f'Bearer {TOKEN}'          # /logout lleva el JWT para revocar su jti
    assert cuerpo == {'refresh_token': REFRESH}                   # y el refresh para borrarlo de Redis
    assert api.token is None                                      # borrado de memoria
    assert auth.refresh_token is None
    assert almacen.token(AppConfig().login_url) is None           # y de disco
    assert auth.sesion is None

    for servicio, ruta in (('books', '/api/books/1'), ('pedidos', '/orders'), ('pagos', '/payments')):
        api.request(servicio, 'PATCH', ruta, json_body={'x': 1})
        assert 'Authorization' not in enviados[-1][2], servicio   # ninguna peticion posterior lo lleva


def test_registro_http_indica_autenticacion(api):
    api.token = TOKEN
    api.request('books', 'DELETE', '/api/books/123')
    api.request('books', 'GET', '/api/books')
    historial = api.historial()
    assert historial[0].autenticacion == 'Bearer'
    assert historial[1].autenticacion == '—'
