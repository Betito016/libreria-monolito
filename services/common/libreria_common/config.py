"""
Configuracion comun a todos los microservicios, leida de variables de entorno.

Cada servicio carga primero su propio .env (load_dotenv) y despues construye
`ConfigComun.desde_entorno()`. Los secretos nunca tienen valor por defecto:
si faltan, el servicio no arranca (`validar`).

    JWT_SECRET_KEY           Clave HS256 compartida por los 6 servicios (>= 32 bytes)
    JWT_ALGORITHM            HS256
    JWT_ISSUER               Emisor esperado en el claim 'iss' (libreria-login)
    ACCESS_TOKEN_MINUTES     Vida del JWT de acceso (20)
    REDIS_URL                redis://:password@host:6379/0
    REDIS_TIMEOUT_SECONDS    Timeout de conexion y de cada comando (1.5)
    CACHE_TTL_SECONDS        TTL de la cache de lecturas publicas (60)
    CORS_ORIGINS             Origenes permitidos, separados por coma
"""
import os
from dataclasses import dataclass, field
from typing import List

MINIMO_BYTES_CLAVE = 32          # HS256: la clave debe medir al menos lo que el hash (RFC 7518, 3.2)


def _lista(nombre: str, defecto: str = '') -> List[str]:
    return [v.strip() for v in os.getenv(nombre, defecto).split(',') if v.strip()]


@dataclass(frozen=True)
class ConfigComun:
    jwt_secret_key: str
    jwt_algorithm: str = 'HS256'
    jwt_issuer: str = 'libreria-login'
    access_token_minutos: int = 20
    redis_url: str = ''
    redis_timeout: float = 1.5
    cache_ttl: int = 60
    cors_origins: List[str] = field(default_factory=list)

    @classmethod
    def desde_entorno(cls) -> 'ConfigComun':
        return cls(
            jwt_secret_key=os.getenv('JWT_SECRET_KEY', ''),
            jwt_algorithm=os.getenv('JWT_ALGORITHM', 'HS256'),
            jwt_issuer=os.getenv('JWT_ISSUER', 'libreria-login'),
            access_token_minutos=int(os.getenv('ACCESS_TOKEN_MINUTES', '20')),
            redis_url=os.getenv('REDIS_URL', ''),
            redis_timeout=float(os.getenv('REDIS_TIMEOUT_SECONDS', '1.5')),
            cache_ttl=int(os.getenv('CACHE_TTL_SECONDS', '60')),
            cors_origins=_lista('CORS_ORIGINS'),
        )

    def errores(self) -> List[str]:
        errores = []
        if len(self.jwt_secret_key.encode()) < MINIMO_BYTES_CLAVE:
            errores.append(f'JWT_SECRET_KEY no esta definida o mide menos de {MINIMO_BYTES_CLAVE} bytes')
        if self.jwt_algorithm != 'HS256':
            errores.append('JWT_ALGORITHM debe ser HS256')
        if not self.redis_url.startswith(('redis://', 'rediss://')):
            errores.append('REDIS_URL no esta definida (redis://:password@host:6379/0)')
        if not (1 <= self.access_token_minutos <= 20):
            errores.append('ACCESS_TOKEN_MINUTES debe estar entre 1 y 20')
        return errores

    def validar(self, logger) -> None:
        """Detiene el servicio si falta configuracion de seguridad."""
        errores = self.errores()
        for error in errores:
            logger.critical(error)
        if errores:
            raise SystemExit(1)
