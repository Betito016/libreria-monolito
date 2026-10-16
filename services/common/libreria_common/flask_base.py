"""
Piezas comunes de una app Flask de la Libreria:

    - CORS solo para los origenes configurados (CORS_ORIGINS)
    - Log de cada peticion: metodo, ruta, si es publica o protegida y el
      header Authorization enmascarado; al final el codigo y la duracion
    - Errores -> respuestas: 400 validacion, 401/403 JWT, 404, 405, 409, 503 Redis
    - GET /metrics: contadores del servicio y estado de Redis

    servicio = ServicioBase.crear('books', __name__)
    app, auth, cache = servicio.app, servicio.auth, servicio.cache
"""
import logging
import sys
import time
from dataclasses import dataclass

from flask import Flask, g, request

from libreria_common.bd import BaseDatosNoDisponible
from libreria_common.cache import CacheJSON
from libreria_common.config import ConfigComun
from libreria_common.metricas import Metricas
from libreria_common.redis_capa import CapaRedis, RedisNoDisponible
from libreria_common.respuestas import api_response, error_response
from libreria_common.seguridad import AuthError, ValidadorJWT, describir_authorization
from libreria_common.validacion import Conflicto, NoEncontrado, ValidacionError

SIN_LOG = ('/health', '/metrics', '/docs', '/openapi.json')


def configurar_logs() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] (%(name)s) %(message)s',
                            handlers=[logging.StreamHandler(sys.stdout)])


@dataclass
class ServicioBase:
    nombre: str
    app: Flask
    config: ConfigComun
    redis: CapaRedis
    metricas: Metricas
    auth: ValidadorJWT
    cache: CacheJSON
    logger: logging.Logger

    @classmethod
    def crear(cls, nombre: str, import_name: str, config: ConfigComun = None,
              redis_cliente=None) -> 'ServicioBase':
        configurar_logs()
        logger = logging.getLogger(f'{nombre.capitalize()}Microservice')
        config = config or ConfigComun.desde_entorno()
        config.validar(logger)
        metricas = Metricas(nombre)
        capa = CapaRedis(config.redis_url, timeout=config.redis_timeout, cliente=redis_cliente, metricas=metricas)
        servicio = cls(nombre, Flask(import_name), config, capa, metricas,
                       ValidadorJWT(config, capa, metricas), CacheJSON(capa, config.cache_ttl, metricas), logger)
        servicio._instalar()
        return servicio

    # ------------------------------------------------------------------
    def _instalar(self) -> None:
        app, logger, metricas, config = self.app, self.logger, self.metricas, self.config

        @app.before_request
        def _inicio():
            g.inicio = time.perf_counter()
            if request.method == 'OPTIONS' or request.path in SIN_LOG:
                return
            vista = app.view_functions.get(request.endpoint)
            if getattr(vista, 'requiere_jwt', False):
                roles = getattr(vista, 'roles', None)
                tipo = f"PROTEGIDO (requiere JWT{', role_id ' + str(roles) if roles else ''})"
            else:
                tipo = 'publico (sin JWT)'
            logger.info(f"--> {request.method} {request.path} | {tipo} | "
                        f"{describir_authorization(request.headers.get('Authorization'))}")

        @app.after_request
        def _fin(respuesta):
            origen = request.headers.get('Origin')
            if origen and origen in config.cors_origins:          # nunca '*'
                respuesta.headers['Access-Control-Allow-Origin'] = origen
                respuesta.headers['Access-Control-Allow-Credentials'] = 'true'
                respuesta.headers['Vary'] = 'Origin'
            respuesta.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            respuesta.headers['Access-Control-Allow-Headers'] = 'Content-Type, Accept, Authorization'
            ms = (time.perf_counter() - g.get('inicio', time.perf_counter())) * 1000
            ruta = request.url_rule.rule if request.url_rule else request.path
            metricas.registrar_peticion(request.method, ruta, respuesta.status_code, ms)
            if request.method != 'OPTIONS' and request.path not in SIN_LOG:
                logger.info(f"<-- {respuesta.status_code} {request.method} {request.path} ({ms:.0f} ms)")
            return respuesta

        @app.errorhandler(ValidacionError)
        def _validacion(exc):
            return error_response(exc.codigo, exc.mensaje, status=400, **exc.extra)

        @app.errorhandler(AuthError)
        def _auth(exc):
            respuesta = error_response(exc.codigo, exc.mensaje, status=exc.status)
            if exc.status == 401:
                respuesta.headers['WWW-Authenticate'] = f'Bearer error="invalid_token", error_description="{exc.codigo}"'
            return respuesta

        @app.errorhandler(RedisNoDisponible)
        def _redis(exc):
            logger.error(f"    503: {exc} -> operacion rechazada (falla segura)")
            return error_response('ERR_REDIS_NO_DISPONIBLE',
                                  'No se pudo verificar la sesión o el token: Redis no está disponible. '
                                  'Intenta de nuevo en unos segundos.', status=503)

        @app.errorhandler(BaseDatosNoDisponible)
        def _bd(exc):
            logger.error(f"    PostgreSQL no disponible: {exc}")
            return error_response('ERR_BASE_DATOS', 'El servicio de base de datos no está disponible.', status=503)

        @app.errorhandler(NoEncontrado)
        def _no_encontrado(exc):
            return error_response('ERR_NO_ENCONTRADO', str(exc), status=404)

        @app.errorhandler(Conflicto)
        def _conflicto(exc):
            return error_response(exc.codigo, exc.mensaje, status=409)

        @app.errorhandler(404)
        def _ruta(_exc):
            return error_response('ERR_RUTA_NO_ENCONTRADA', f"No existe el recurso {request.path}.", status=404)

        @app.errorhandler(405)
        def _metodo(_exc):
            return error_response('ERR_METODO_NO_PERMITIDO',
                                  f"El método {request.method} no está permitido en {request.path}.", status=405)

        @app.route('/metrics', methods=['GET'])
        def metrics():
            return api_response('metricas', {**metricas.resumen(), 'redis': self.redis.estado()})
