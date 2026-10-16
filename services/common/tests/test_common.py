"""
Pruebas de libreria_common con un Redis simulado (fakeredis).

    cd services/common
    venv\\Scripts\\python -m pytest -q
"""
import time
import uuid

import fakeredis
import jwt
import pytest
from flask import g

from libreria_common.cache import CacheJSON, clave_filtros
from libreria_common.config import ConfigComun
from libreria_common.flask_base import ServicioBase
from libreria_common.metricas import Metricas
from libreria_common.redis_capa import CapaRedis, RedisNoDisponible
from libreria_common.respuestas import api_response
from libreria_common.seguridad import (ROL_ADMINISTRADOR, ROL_CLIENTE, descripcion_segura, revocar_jti,
                                       revocar_usuario)

CLAVE = 'clave-de-pruebas-de-al-menos-32-bytes-0123456789'
CONFIG = ConfigComun(jwt_secret_key=CLAVE, redis_url='redis://:x@127.0.0.1:6379/0',
                     cors_origins=['http://cliente.permitido'])


def token(role_id=ROL_ADMINISTRADOR, minutos=20, clave=CLAVE, typ='access', quitar=(), **extra):
    ahora = int(time.time())
    claims = {'sub': 'u1', 'user_id': 'u1', 'role_id': role_id, 'jti': uuid.uuid4().hex, 'typ': typ,
              'iss': 'libreria-login', 'iat': ahora, 'exp': ahora + minutos * 60, **extra}
    for c in quitar:
        claims.pop(c)
    return jwt.encode(claims, clave, algorithm='HS256'), claims


@pytest.fixture
def servidor():
    return fakeredis.FakeServer()


@pytest.fixture
def servicio(servidor):
    s = ServicioBase.crear('prueba', __name__, CONFIG, redis_cliente=fakeredis.FakeRedis(server=servidor,
                                                                                          decode_responses=True))

    @s.app.route('/publico')
    def publico():
        return api_response('ok', {'estado': 'ok'})

    @s.app.route('/escritura', methods=['POST'])
    @s.auth.requiere_jwt()
    def escritura():
        return api_response('ok', {'user_id': g.usuario['user_id']})

    @s.app.route('/admin', methods=['DELETE'])
    @s.auth.requiere_jwt(roles=[ROL_ADMINISTRADOR])
    def admin():
        return api_response('ok', {'estado': 'ok'})

    s.app.testing = True
    s.cliente = s.app.test_client()
    return s


def bearer(t):
    return {'Authorization': f'Bearer {t}'}


# ----------------------------------------------------------------------
# Configuracion
# ----------------------------------------------------------------------
def test_config_rechaza_clave_corta_y_sin_redis():
    errores = ConfigComun(jwt_secret_key='corta').errores()
    assert any('JWT_SECRET_KEY' in e for e in errores)
    assert any('REDIS_URL' in e for e in errores)


def test_config_limita_el_access_token_a_20_minutos():
    assert ConfigComun(jwt_secret_key=CLAVE, redis_url='redis://h', access_token_minutos=30).errores()


# ----------------------------------------------------------------------
# JWT y revocacion
# ----------------------------------------------------------------------
def test_publico_sin_token(servicio):
    assert servicio.cliente.get('/publico?format=json').status_code == 200


@pytest.mark.parametrize('headers,codigo', [
    ({}, 'ERR_TOKEN_AUSENTE'),
    ({'Authorization': 'Basic abc'}, 'ERR_TOKEN_INVALIDO'),
    ({'Authorization': 'Bearer no.es.jwt'}, 'ERR_TOKEN_INVALIDO'),
])
def test_401_sin_token_o_malformado(servicio, headers, codigo):
    r = servicio.cliente.post('/escritura?format=json', headers=headers)
    assert r.status_code == 401
    assert r.get_json()['codigo_error'] == codigo
    assert r.headers['WWW-Authenticate'].startswith('Bearer')


def test_token_valido(servicio):
    t, _ = token()
    r = servicio.cliente.post('/escritura?format=json', headers=bearer(t))
    assert r.status_code == 200 and r.get_json()['user_id'] == 'u1'


@pytest.mark.parametrize('t', [
    token(clave='otra-clave-distinta-de-al-menos-32-bytes-xx')[0],
    token(minutos=-1)[0],
    token(typ='refresh')[0],
    token(quitar=['jti'])[0],
    token(quitar=['role_id'])[0],
    token(iss='otro')[0],
])
def test_401_firma_expiracion_tipo_y_claims(servicio, t):
    assert servicio.cliente.post('/escritura?format=json', headers=bearer(t)).status_code == 401


def test_403_rol_insuficiente(servicio):
    t, _ = token(role_id=ROL_CLIENTE)
    r = servicio.cliente.delete('/admin?format=json', headers=bearer(t))
    assert r.status_code == 403 and r.get_json()['codigo_error'] == 'ERR_SIN_PERMISOS'


def test_jti_revocado_401(servicio):
    t, claims = token()
    revocar_jti(servicio.redis, claims['jti'], claims['exp'])
    r = servicio.cliente.post('/escritura?format=json', headers=bearer(t))
    assert r.status_code == 401 and r.get_json()['codigo_error'] == 'ERR_TOKEN_REVOCADO'
    ttl = servicio.redis.ejecutar(lambda c: c.ttl(f"jwt:revoked:{claims['jti']}"), critico=True)
    assert 0 < ttl <= 20 * 60


def test_revocar_usuario_invalida_tokens_anteriores(servicio):
    viejo, _ = token(iat=int(time.time()) - 5)
    revocar_usuario(servicio.redis, 'u1', 20)
    assert servicio.cliente.post('/escritura?format=json', headers=bearer(viejo)).status_code == 401
    time.sleep(1.1)
    nuevo, _ = token()
    assert servicio.cliente.post('/escritura?format=json', headers=bearer(nuevo)).status_code == 200


def test_redis_caido_protegido_503_y_publico_200(servicio, servidor):
    servidor.connected = False
    t, _ = token()
    r = servicio.cliente.post('/escritura?format=json', headers=bearer(t))
    assert r.status_code == 503 and r.get_json()['codigo_error'] == 'ERR_REDIS_NO_DISPONIBLE'
    assert servicio.cliente.get('/publico?format=json').status_code == 200


def test_corte_rapido_tras_una_falla(servidor):
    servidor.connected = False
    capa = CapaRedis('redis://h', cliente=fakeredis.FakeRedis(server=servidor), pausa=5)
    with pytest.raises(RedisNoDisponible):
        capa.ejecutar(lambda r: r.ping(), critico=True)
    servidor.connected = True
    # Durante la pausa no se vuelve a intentar: falla de inmediato.
    with pytest.raises(RedisNoDisponible):
        capa.ejecutar(lambda r: r.ping(), critico=True)
    assert capa.ejecutar(lambda r: r.ping(), critico=False) is None
    # estado() vuelve a probar y cierra la pausa si Redis respondio.
    assert capa.estado()['disponible'] is True
    assert capa.ejecutar(lambda r: r.ping(), critico=True) is True


def test_logs_no_revelan_el_token(servicio, caplog):
    t, _ = token()
    with caplog.at_level('INFO'):
        servicio.cliente.post('/escritura?format=json', headers=bearer(t))
    assert '[JWT PRESENTE' in caplog.text and 'PROTEGIDO' in caplog.text
    assert t not in caplog.text
    assert descripcion_segura(t) != t


# ----------------------------------------------------------------------
# Cache
# ----------------------------------------------------------------------
def test_clave_filtros_estable():
    a = clave_filtros('books:list', {'titulo': 'cloud', 'page': 1, 'anio': None})
    b = clave_filtros('books:list', {'page': 1, 'titulo': 'cloud'})
    assert a == b == 'books:list:page=1&titulo=cloud'
    assert clave_filtros('books:list', {}) == 'books:list:todos'


def test_cache_miss_set_hit_e_invalidacion(servidor):
    metricas = Metricas('t')
    cache = CacheJSON(CapaRedis('redis://h', cliente=fakeredis.FakeRedis(server=servidor, decode_responses=True)),
                      ttl=60, metricas=metricas)
    assert cache.obtener('books:1') is None
    cache.guardar('books:1', {'titulo': 'A'})
    cache.guardar('books:list:todos', {'total': 1})
    cache.guardar('authors:1', {'nombre': 'X'})
    assert cache.obtener('books:1') == {'titulo': 'A'}
    assert cache.invalidar(['books:*']) == 2
    assert cache.obtener('books:1') is None
    assert cache.obtener('authors:1') == {'nombre': 'X'}
    assert metricas.valor('cache_aciertos') == 2 and metricas.valor('cache_fallos') == 2


def test_cache_opcional_si_redis_cae(servidor):
    servidor.connected = False
    cache = CacheJSON(CapaRedis('redis://h', cliente=fakeredis.FakeRedis(server=servidor)), ttl=60)
    assert cache.obtener('books:1') is None          # sin excepcion: se leera de PostgreSQL
    cache.guardar('books:1', {'a': 1})
    assert cache.invalidar(['books:*']) == 0


def test_cliente_real_no_reintenta_por_timeout():
    """Un GETDEL/SET NX/MULTI que tardo en responder pudo ejecutarse: repetirlo
    daria un resultado falso (p. ej. 'refresh ya usado'). Solo se reintenta si
    la conexion se cayo."""
    import redis
    capa = CapaRedis('redis://:x@127.0.0.1:1/0', timeout=0.2)
    errores = capa._cliente.get_retry()._supported_errors
    assert redis.ConnectionError in errores
    assert redis.TimeoutError not in errores


# ----------------------------------------------------------------------
# Candado distribuido
# ----------------------------------------------------------------------
def test_candado_exclusivo_y_liberacion_segura(servidor):
    from libreria_common.candado import Candado
    from libreria_common.validacion import Conflicto
    r = fakeredis.FakeRedis(server=servidor, decode_responses=True)
    capa = CapaRedis('redis://h', cliente=r)
    with Candado(capa, 'lock:order:7', ttl=30):
        assert 0 < r.ttl('lock:order:7') <= 30
        with pytest.raises(Conflicto):
            with Candado(capa, 'lock:order:7'):
                pass
    assert not r.exists('lock:order:7')
    # Si el candado propio expiro y otro proceso tomo uno nuevo, no se borra el ajeno.
    mio = Candado(capa, 'lock:order:8', ttl=30)
    assert mio.intentar()
    r.set('lock:order:8', 'token-de-otro-proceso', ex=30)
    mio.liberar()
    assert r.get('lock:order:8') == 'token-de-otro-proceso'


def test_candado_sin_redis_503(servidor):
    from libreria_common.candado import Candado
    servidor.connected = False
    with pytest.raises(RedisNoDisponible):
        with Candado(CapaRedis('redis://h', cliente=fakeredis.FakeRedis(server=servidor)), 'lock:x'):
            pass


# ----------------------------------------------------------------------
# Metricas y CORS
# ----------------------------------------------------------------------
def test_metrics_y_cors(servicio):
    servicio.cliente.get('/publico?format=json')
    r = servicio.cliente.get('/metrics?format=json', headers={'Origin': 'http://cliente.permitido'})
    datos = r.get_json()
    assert datos['servicio'] == 'prueba' and datos['redis']['disponible'] is True
    assert ':x@' not in str(datos)                   # la URL con contrasena no se expone
    assert r.headers['Access-Control-Allow-Origin'] == 'http://cliente.permitido'
    r = servicio.cliente.get('/publico', headers={'Origin': 'http://malicioso.example'})
    assert 'Access-Control-Allow-Origin' not in r.headers
