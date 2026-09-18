"""
Capa de persistencia del microservicio de login.

Usa Psycopg 3 (`psycopg`) con pool de conexiones (`psycopg_pool`), que tiene
una API distinta a psycopg2: las conexiones se obtienen como context manager
y los cursores pueden devolver filas como diccionarios via `row_factory`.

Opera sobre la tabla `usuarios` de library_db, la misma que usa el monolito
Node.js. No crea tablas propias de usuarios ni duplica el password.
"""
import logging
from typing import Any, Dict, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from config.config import Config

logger = logging.getLogger(__name__)


class EmailAlreadyRegisteredError(Exception):
    """El correo ya existe en la base (violacion de UNIQUE)."""


class DatabaseUnavailableError(Exception):
    """No fue posible contactar a PostgreSQL."""


class UserRepository:
    _pool: Optional[ConnectionPool] = None

    @classmethod
    def pool(cls) -> ConnectionPool:
        if cls._pool is None:
            # open=False + open() explicito evita el warning de apertura
            # implicita de psycopg_pool 3.2.
            cls._pool = ConnectionPool(
                conninfo=Config.dsn(),
                min_size=1,
                max_size=10,
                timeout=5,
                open=False,
            )
            cls._pool.open()
            logger.info("Pool de conexiones a PostgreSQL inicializado (Psycopg 3).")
        return cls._pool

    # ------------------------------------------------------------------
    # /health
    # ------------------------------------------------------------------
    @classmethod
    def ping(cls) -> Dict[str, Any]:
        """Verifica conectividad real contra PostgreSQL (no solo 'OK')."""
        try:
            with cls.pool().connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version(), current_database()")
                    version, database = cur.fetchone()
            return {
                'conectado': True,
                'base_datos': database,
                'version': version.split(',')[0],
            }
        except Exception as exc:
            logger.error(f"Fallo el health check de PostgreSQL: {exc}")
            return {'conectado': False, 'error': str(exc)}

    # ------------------------------------------------------------------
    # /register
    # ------------------------------------------------------------------
    @classmethod
    def create_user(
        cls,
        nombre: str,
        apellido_paterno: str,
        apellido_materno: Optional[str],
        email: str,
        password_hash: str,
        email_verificado: bool,
    ) -> Dict[str, Any]:
        """Inserta un usuario nuevo. Siempre con rol 'cliente': el indice
        parcial ux_un_solo_administrador permite un unico administrador en
        todo el sistema, asi que el registro publico nunca crea admins."""
        try:
            with cls.pool().connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        INSERT INTO usuarios
                            (nombre, apellido_paterno, apellido_materno, email,
                             password_hash, rol, email_verificado)
                        VALUES (%s, %s, %s, %s, %s, 'cliente', %s)
                        RETURNING id, nombre, apellido_paterno, apellido_materno,
                                  email, rol, activo, email_verificado, fecha_registro
                        """,
                        (nombre, apellido_paterno, apellido_materno, email,
                         password_hash, email_verificado),
                    )
                    return cur.fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise EmailAlreadyRegisteredError(
                f"El correo '{email}' ya esta registrado."
            ) from exc
        except psycopg.OperationalError as exc:
            raise DatabaseUnavailableError(str(exc)) from exc

    # ------------------------------------------------------------------
    # /login
    # ------------------------------------------------------------------
    @classmethod
    def find_by_email(cls, email: str) -> Optional[Dict[str, Any]]:
        """Busca por correo sin distinguir mayusculas (indice funcional
        ux_usuarios_email_lower). Devuelve tambien el password_hash porque
        la verificacion ocurre en la capa de autenticacion."""
        try:
            with cls.pool().connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT id, nombre, apellido_paterno, apellido_materno, email,
                               password_hash, rol, activo, email_verificado, fecha_registro
                        FROM usuarios
                        WHERE lower(email) = lower(%s)
                        """,
                        (email,),
                    )
                    return cur.fetchone()
        except psycopg.OperationalError as exc:
            raise DatabaseUnavailableError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Verificacion de correo por token
    # ------------------------------------------------------------------
    @classmethod
    def create_verification_token(
        cls, usuario_id: str, token_hash: str, email_destino: str, ttl_hours: int
    ) -> Dict[str, Any]:
        """Registra un token pendiente. Se guarda el hash, nunca el token."""
        try:
            with cls.pool().connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        INSERT INTO verificaciones_email
                            (usuario_id, token_hash, email_destino, expira_en)
                        VALUES (%s, %s, %s, now() + make_interval(hours => %s))
                        RETURNING id, creado_en, expira_en
                        """,
                        (usuario_id, token_hash, email_destino, ttl_hours),
                    )
                    return cur.fetchone()
        except psycopg.OperationalError as exc:
            raise DatabaseUnavailableError(str(exc)) from exc

    @classmethod
    def mark_token_sent(cls, token_id: int) -> None:
        """Marca que el MTA acepto el mensaje."""
        try:
            with cls.pool().connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE verificaciones_email SET enviado = TRUE WHERE id = %s",
                        (token_id,),
                    )
        except psycopg.OperationalError as exc:
            raise DatabaseUnavailableError(str(exc)) from exc

    @classmethod
    def redeem_token(cls, token_hash: str) -> Dict[str, Any]:
        """Canjea un token y marca el correo como verificado.

        Todo ocurre en una sola transaccion para que no exista un estado
        intermedio en el que el token quede consumido pero el usuario sin
        verificar. Devuelve un dict con `resultado`:
          - 'ok'         : verificado correctamente
          - 'no_existe'  : el token no corresponde a ninguna solicitud
          - 'ya_usado'   : el token ya se habia canjeado
          - 'expirado'   : el token vencio
        """
        try:
            with cls.pool().connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT v.id, v.usuario_id, v.usado_en, v.expira_en,
                               v.expira_en < now() AS vencido, u.email, u.nombre
                        FROM verificaciones_email v
                        JOIN usuarios u ON u.id = v.usuario_id
                        WHERE v.token_hash = %s
                        FOR UPDATE OF v
                        """,
                        (token_hash,),
                    )
                    fila = cur.fetchone()

                    if not fila:
                        return {'resultado': 'no_existe'}
                    if fila['usado_en'] is not None:
                        return {'resultado': 'ya_usado', 'email': fila['email']}
                    if fila['vencido']:
                        return {'resultado': 'expirado', 'email': fila['email']}

                    cur.execute(
                        "UPDATE verificaciones_email SET usado_en = now() WHERE id = %s",
                        (fila['id'],),
                    )
                    cur.execute(
                        """
                        UPDATE usuarios
                        SET email_verificado = TRUE, actualizado_en = now()
                        WHERE id = %s
                        RETURNING id, nombre, apellido_paterno, apellido_materno,
                                  email, rol, activo, email_verificado
                        """,
                        (fila['usuario_id'],),
                    )
                    usuario = cur.fetchone()

            return {'resultado': 'ok', 'usuario': usuario}
        except psycopg.OperationalError as exc:
            raise DatabaseUnavailableError(str(exc)) from exc

    @classmethod
    def find_by_id(cls, user_id: str) -> Optional[Dict[str, Any]]:
        """Recupera al usuario de la sesion activa. No devuelve password_hash."""
        try:
            with cls.pool().connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT id, nombre, apellido_paterno, apellido_materno, email,
                               rol, activo, email_verificado, fecha_registro
                        FROM usuarios
                        WHERE id = %s
                        """,
                        (user_id,),
                    )
                    return cur.fetchone()
        except psycopg.OperationalError as exc:
            raise DatabaseUnavailableError(str(exc)) from exc
