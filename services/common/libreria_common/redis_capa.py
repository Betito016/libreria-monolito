"""
Conexion a Redis compartida por los microservicios.

Dos clases de operaciones, con politicas distintas ante una falla:

    CRITICAS   sesion, refresh token, lista de revocacion, candados.
               Si Redis no responde se lanza RedisNoDisponible y el servicio
               responde 503: es preferible negar el acceso que aceptar un
               token que podria estar revocado (falla segura).

    OPCIONALES cache de lecturas publicas.
               Si Redis no responde se devuelve None y el servicio lee de
               PostgreSQL, que sigue siendo la fuente principal de datos.

Corte rapido: tras una falla, durante `pausa` segundos no se vuelve a esperar
a Redis. Las operaciones opcionales se saltan y las criticas fallan de
inmediato con 503, en vez de que cada peticion espere el timeout completo.

La URL lleva la contrasena (redis://:password@host...): nunca se registra.
"""
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional, TypeVar
from urllib.parse import urlsplit

import redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

T = TypeVar('T')
ERRORES_REDIS = (redis.ConnectionError, redis.TimeoutError, redis.AuthenticationError, redis.BusyLoadingError,
                 OSError)
logger = logging.getLogger('libreria.redis')


class RedisNoDisponible(Exception):
    """Redis no respondio a una operacion critica: el servicio responde 503."""


def destino_seguro(url: str) -> str:
    """host:puerto/db de la URL, sin usuario ni contrasena (apto para logs)."""
    partes = urlsplit(url)
    return f"{partes.hostname}:{partes.port or 6379}{partes.path or '/0'}"


class CapaRedis:

    def __init__(self, url: str, timeout: float = 1.5, pausa: float = 5.0,
                 cliente: Optional[redis.Redis] = None, metricas=None):
        self.destino = destino_seguro(url) if url else '(sin REDIS_URL)'
        self.pausa = pausa
        self.metricas = metricas
        self._abierto_hasta = 0.0
        self._lock = threading.Lock()
        self._ultimo_error: Optional[str] = None
        if cliente is not None:                          # pruebas: fakeredis
            self._cliente = cliente
        elif url:
            self._cliente = redis.Redis.from_url(
                url, decode_responses=True,
                socket_timeout=timeout, socket_connect_timeout=timeout,
                health_check_interval=30,
                # Un reintento rapido SOLO si la conexion se cayo (p. ej. una
                # conexion vieja del pool tras reconectarse el tunel). Nunca por
                # TimeoutError: el comando pudo ejecutarse y solo tardo la
                # respuesta; repetir un GETDEL (refresh de un solo uso), un
                # SET NX (candado) o un MULTI daria un resultado falso.
                retry=Retry(ExponentialBackoff(cap=0.2, base=0.05), 1, supported_errors=(redis.ConnectionError,)),
            )
        else:
            self._cliente = None

    # ------------------------------------------------------------------
    def _en_pausa(self) -> bool:
        return time.monotonic() < self._abierto_hasta

    def _registrar_falla(self, exc: Exception) -> None:
        with self._lock:
            primera = not self._en_pausa()
            self._abierto_hasta = time.monotonic() + self.pausa
            self._ultimo_error = exc.__class__.__name__
        if self.metricas:
            self.metricas.incrementar('redis_errores')
        if primera:
            logger.warning(f"Redis {self.destino} no disponible ({exc.__class__.__name__}); "
                           f"se reintentara en {self.pausa:g} s")

    def ejecutar(self, operacion: Callable[[redis.Redis], T], *, critico: bool) -> Optional[T]:
        """Ejecuta `operacion(cliente)`. Critica: falla con RedisNoDisponible.
        Opcional: devuelve None y la peticion sigue sin Redis."""
        if self._cliente is None or self._en_pausa():
            if critico:
                raise RedisNoDisponible(f'Redis no disponible ({self._ultimo_error or "sin configurar"})')
            return None
        try:
            resultado = operacion(self._cliente)
        except ERRORES_REDIS as exc:
            self._registrar_falla(exc)
            if critico:
                raise RedisNoDisponible(f'Redis no disponible ({exc.__class__.__name__})') from exc
            return None
        if self._ultimo_error:
            logger.info(f"Redis {self.destino} disponible de nuevo")
            self._ultimo_error = None
        return resultado

    def estado(self) -> Dict[str, Any]:
        """Para /health y /metrics: un PING con su latencia."""
        if self._cliente is None:
            return {'disponible': False, 'destino': self.destino, 'error': 'sin REDIS_URL'}
        inicio = time.perf_counter()
        try:
            self._cliente.ping()
        except ERRORES_REDIS as exc:
            self._registrar_falla(exc)
            return {'disponible': False, 'destino': self.destino, 'error': exc.__class__.__name__}
        self._abierto_hasta = 0.0
        self._ultimo_error = None
        return {'disponible': True, 'destino': self.destino,
                'latencia_ms': round((time.perf_counter() - inicio) * 1000, 1)}
