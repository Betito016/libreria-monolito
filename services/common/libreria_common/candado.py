"""
Candado distribuido en Redis para coordinar tareas entre procesos/servicios.

    with Candado(capa, 'lock:order:42', ttl=30):
        ...   # solo un proceso a la vez

- Toma:     SET lock:<...> <token> NX EX <ttl>   (atomico; expira solo si el
            proceso muere a la mitad, para no bloquear para siempre)
- Libera:   WATCH + MULTI: borra la clave SOLO si conserva su token, para no
            soltar el candado de otro proceso si el propio ya expiro.

Es una operacion CRITICA: sin Redis no hay coordinacion -> RedisNoDisponible (503).
Si el candado esta tomado -> Conflicto ERR_OPERACION_EN_CURSO (409).
"""
import logging
import secrets

import redis

from libreria_common.redis_capa import CapaRedis
from libreria_common.validacion import Conflicto

logger = logging.getLogger('libreria.candado')


def _borrar_si_es_mio(cliente, clave: str, token: str) -> bool:
    """Compara y borra de forma atomica: si otro proceso toca la clave entre
    el GET y el DEL, la transaccion se aborta (WatchError) y no se borra."""
    with cliente.pipeline() as tubo:
        try:
            tubo.watch(clave)
            if tubo.get(clave) != token:
                return False
            tubo.multi()
            tubo.delete(clave)
            tubo.execute()
            return True
        except redis.WatchError:
            return False


class Candado:

    def __init__(self, capa: CapaRedis, clave: str, ttl: int = 30, mensaje: str = None):
        self.capa, self.clave, self.ttl = capa, clave, ttl
        self.mensaje = mensaje or 'Ya hay una operación en curso sobre este recurso; intenta de nuevo en unos segundos.'
        self.token = secrets.token_hex(16)
        self.tomado = False

    def intentar(self) -> bool:
        self.tomado = bool(self.capa.ejecutar(lambda r: r.set(self.clave, self.token, nx=True, ex=self.ttl), critico=True))
        if self.tomado:
            logger.info(f"    LOCK tomado {self.clave} (TTL {self.ttl} s)")
        return self.tomado

    def liberar(self) -> None:
        if self.tomado:
            # Opcional: si Redis no responde, el candado expira solo por su TTL.
            self.capa.ejecutar(lambda r: _borrar_si_es_mio(r, self.clave, self.token), critico=False)
            self.tomado = False
            logger.info(f"    LOCK liberado {self.clave}")

    def __enter__(self):
        if not self.intentar():
            logger.warning(f"    LOCK ocupado {self.clave}: operacion rechazada (409)")
            raise Conflicto('ERR_OPERACION_EN_CURSO', self.mensaje)
        return self

    def __exit__(self, *exc):
        self.liberar()
        return False
