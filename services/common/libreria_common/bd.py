"""
Acceso a PostgreSQL compartido por los servicios nuevos (users, authors,
pedidos, pagos): un pool de Psycopg 3 y la traduccion de fallas de conexion a
BaseDatosNoDisponible (que flask_base convierte en 503).

    bd = BaseDatos(dsn)
    with bd.cursor() as cur:                 # una transaccion: commit al salir, rollback si falla
        cur.execute('SELECT ...', (param,))
"""
import logging
from contextlib import contextmanager
from typing import Any, Dict, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

logger = logging.getLogger('libreria.bd')


class BaseDatosNoDisponible(Exception):
    """PostgreSQL no responde: el servicio responde 503."""


def dsn(host: str, puerto: int, nombre: str, usuario: str, password: str) -> str:
    return f"host={host} port={puerto} dbname={nombre} user={usuario} password={password} connect_timeout=5"


class BaseDatos:

    def __init__(self, dsn_texto: str, nombre: str, minimo: int = 1, maximo: int = 5):
        self._dsn = dsn_texto
        self.nombre = nombre
        self._minimo, self._maximo = minimo, maximo
        self._pool = None

    def pool(self) -> ConnectionPool:
        if self._pool is None:
            self._pool = ConnectionPool(self._dsn, min_size=self._minimo, max_size=self._maximo,
                                        timeout=5, open=True, kwargs={'autocommit': False})
            logger.info(f"Pool de conexiones a PostgreSQL ({self.nombre}) inicializado")
        return self._pool

    @contextmanager
    def cursor(self) -> Iterator[psycopg.Cursor]:
        try:
            with self.pool().connection() as conexion:
                with conexion.transaction():
                    with conexion.cursor(row_factory=dict_row) as cur:
                        yield cur
        except (psycopg.OperationalError, PoolTimeout) as exc:
            if isinstance(exc, psycopg.errors.QueryCanceled):
                raise
            raise BaseDatosNoDisponible(str(exc).splitlines()[0]) from exc

    def ping(self) -> Dict[str, Any]:
        try:
            with self.cursor() as cur:
                cur.execute('SELECT current_database() AS base')
                return {'conectado': True, 'base_datos': cur.fetchone()['base']}
        except BaseDatosNoDisponible as exc:
            return {'conectado': False, 'base_datos': self.nombre, 'error': str(exc)[:120]}
