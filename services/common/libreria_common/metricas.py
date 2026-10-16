"""
Metricas simples por proceso, expuestas en GET /metrics de cada servicio.

    peticiones_total, peticiones_por_status, latencia media por ruta
    cache_aciertos / cache_fallos / cache_invalidaciones
    redis_errores, jwt_rechazados, jwt_revocados
"""
import threading
import time
from collections import defaultdict
from typing import Any, Dict


class Metricas:

    def __init__(self, servicio: str):
        self.servicio = servicio
        self.inicio = time.time()
        self._lock = threading.Lock()
        self._contadores: Dict[str, int] = defaultdict(int)
        self._status: Dict[str, int] = defaultdict(int)
        self._latencias: Dict[str, list] = defaultdict(lambda: [0, 0.0])   # ruta -> [n, ms totales]

    def incrementar(self, nombre: str, n: int = 1) -> None:
        with self._lock:
            self._contadores[nombre] += n

    def registrar_peticion(self, metodo: str, ruta: str, status: int, ms: float) -> None:
        with self._lock:
            self._contadores['peticiones_total'] += 1
            self._status[str(status)] += 1
            acumulado = self._latencias[f'{metodo} {ruta}']
            acumulado[0] += 1
            acumulado[1] += ms

    def valor(self, nombre: str) -> int:
        with self._lock:
            return self._contadores.get(nombre, 0)

    def resumen(self) -> Dict[str, Any]:
        with self._lock:
            aciertos, fallos = self._contadores.get('cache_aciertos', 0), self._contadores.get('cache_fallos', 0)
            return {
                'servicio': self.servicio,
                'activo_desde_segundos': int(time.time() - self.inicio),
                'contadores': dict(self._contadores),
                'peticiones_por_status': dict(self._status),
                'cache_tasa_aciertos': round(aciertos / (aciertos + fallos), 3) if aciertos + fallos else None,
                'latencia_media_ms': {ruta: round(total / n, 1) for ruta, (n, total) in self._latencias.items()},
            }
