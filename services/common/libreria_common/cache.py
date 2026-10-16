"""
Cache de lecturas publicas en Redis (opcional).

    books:list:<filtros>   GET /books con sus filtros y pagina
    books:<isbn>           GET /books/{isbn}
    authors:list:<...>     GET /authors
    authors:<id>           GET /authors/{id}

Cache-aside: se consulta Redis; si no esta (o Redis falla), se lee de
PostgreSQL y se guarda con un TTL corto. Cualquier escritura invalida las
claves afectadas. Si Redis no esta disponible, la lectura sigue funcionando
desde PostgreSQL: la cache nunca es obligatoria.
"""
import hashlib
import json
import logging
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urlencode

from libreria_common.redis_capa import CapaRedis

logger = logging.getLogger('libreria.cache')


def clave_filtros(prefijo: str, filtros: Dict[str, Any]) -> str:
    """Clave estable para una combinacion de filtros: el orden de los
    parametros no cambia la clave. Valores largos se resumen con sha1."""
    consulta = urlencode(sorted((k, str(v)) for k, v in filtros.items() if v not in (None, '')))
    if len(consulta) > 120:
        consulta = hashlib.sha1(consulta.encode()).hexdigest()
    return f"{prefijo}:{consulta or 'todos'}"


class CacheJSON:

    def __init__(self, capa: CapaRedis, ttl: int, metricas=None):
        self.capa = capa
        self.ttl = ttl
        self.metricas = metricas

    def _contar(self, nombre: str) -> None:
        if self.metricas:
            self.metricas.incrementar(nombre)

    def obtener(self, clave: str) -> Optional[Any]:
        crudo = self.capa.ejecutar(lambda r: r.get(clave), critico=False)
        if crudo is None:
            self._contar('cache_fallos')
            logger.info(f"    CACHE MISS {clave} -> se consulta PostgreSQL")
            return None
        self._contar('cache_aciertos')
        logger.info(f"    CACHE HIT  {clave} (Redis)")
        return json.loads(crudo)

    def guardar(self, clave: str, valor: Any, ttl: Optional[int] = None) -> None:
        ttl = ttl or self.ttl
        guardado = self.capa.ejecutar(
            lambda r: r.set(clave, json.dumps(valor, ensure_ascii=False, default=str), ex=ttl), critico=False)
        if guardado:
            logger.info(f"    CACHE SET  {clave} (TTL {ttl} s)")

    def invalidar(self, patrones: Iterable[str]) -> int:
        """Borra las claves que coinciden con cada patron (SCAN + UNLINK, sin
        bloquear Redis como haria KEYS). Devuelve cuantas se borraron."""
        patrones = list(patrones)

        def borrar(r):
            total = 0
            for patron in patrones:
                lote = []
                for clave in r.scan_iter(match=patron, count=200):
                    lote.append(clave)
                    if len(lote) >= 200:
                        total += r.unlink(*lote); lote = []
                if lote:
                    total += r.unlink(*lote)
            return total
        borradas = self.capa.ejecutar(borrar, critico=False)
        if borradas is None:
            logger.warning(f"    CACHE: no se pudo invalidar {list(patrones)}; expiraran por TTL ({self.ttl} s)")
            return 0
        self._contar('cache_invalidaciones')
        logger.info(f"    CACHE INVALIDADA {list(patrones)}: {borradas} clave(s)")
        return borradas
