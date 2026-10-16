"""
Validacion de JWT y control de roles, identica en los seis microservicios.

El JWT de acceso lo emite SOLO el servicio de login (HS256, 20 minutos) con:
    sub, user_id, email, role_id, rol, jti, typ='access', iss, iat, exp

Cada servicio lo valida localmente con la misma JWT_SECRET_KEY y, ANTES de
aceptarlo, consulta en Redis la lista de revocacion:

    jwt:revoked:<jti>              el token se revoco (logout)
    jwt:revoked_before:<user_id>   todo token del usuario emitido antes de
                                   ese instante se rechaza (cambio de
                                   contrasena, de rol o baja del usuario)

Si Redis no responde, la peticion protegida se rechaza con 503: no se puede
saber si el token fue revocado (falla segura).

Respuestas:
    401  token ausente, esquema distinto de Bearer, firma/algoritmo/emisor
         invalidos, claims faltantes, expirado o revocado
    403  token valido, pero el rol no esta autorizado
    503  Redis no disponible para comprobar la revocacion

La proteccion es SELECTIVA: solo las vistas decoradas con @requiere_jwt la
exigen. Las lecturas publicas no llevan decorador.
"""
import functools
import logging
import time
from typing import Any, Dict, Iterable, Optional

import jwt
from flask import g, request

from libreria_common.config import ConfigComun
from libreria_common.redis_capa import CapaRedis

ROL_ADMINISTRADOR = 1
ROL_CLIENTE = 2
NOMBRES_ROL = {ROL_ADMINISTRADOR: 'administrador', ROL_CLIENTE: 'cliente'}
CLAIMS_REQUERIDOS = ['sub', 'user_id', 'role_id', 'jti', 'iat', 'exp', 'iss']

logger = logging.getLogger('libreria.jwt')


class AuthError(Exception):
    def __init__(self, codigo: str, mensaje: str, status: int):
        super().__init__(mensaje)
        self.codigo, self.mensaje, self.status = codigo, mensaje, status


def descripcion_segura(token: Optional[str]) -> str:
    """Representacion del token apta para logs: nunca el token completo."""
    if not token:
        return '[SIN JWT]'
    return f"[JWT PRESENTE {token[:10]}…{token[-4:]} ({len(token)} caracteres)]"


def describir_authorization(valor: Optional[str]) -> str:
    if not valor:
        return 'Authorization: (ausente)'
    esquema, _, token = valor.strip().partition(' ')
    if esquema.lower() != 'bearer':
        return f"Authorization: esquema '{esquema}' (no es Bearer)"
    return f"Authorization: Bearer {descripcion_segura(token.strip())}"


def extraer_token(valor: Optional[str]) -> str:
    if not valor or not valor.strip():
        raise AuthError('ERR_TOKEN_AUSENTE',
                        'Falta el header Authorization: Bearer <token>. Inicia sesión para obtener uno.', 401)
    esquema, _, token = valor.strip().partition(' ')
    if esquema.lower() != 'bearer':
        raise AuthError('ERR_TOKEN_INVALIDO',
                        f"El header Authorization debe usar el esquema Bearer (se recibió '{esquema}').", 401)
    if not token.strip():
        raise AuthError('ERR_TOKEN_AUSENTE', 'El header Authorization dice Bearer pero no trae el token.', 401)
    return token.strip()


# ----------------------------------------------------------------------
# Lista de revocacion (escritura: login y users; lectura: todos)
# ----------------------------------------------------------------------
def revocar_jti(capa: CapaRedis, jti: str, exp: int) -> None:
    """Revoca un token hasta su expiracion natural (despues ya no hace falta)."""
    ttl = max(1, int(exp) - int(time.time()))
    capa.ejecutar(lambda r: r.set(f'jwt:revoked:{jti}', '1', ex=ttl), critico=True)
    logger.info(f"    JWT revocado: jwt:revoked:{jti} (TTL {ttl} s)")


def revocar_usuario(capa: CapaRedis, user_id: str, minutos_token: int) -> None:
    """Invalida todos los tokens del usuario emitidos hasta ahora."""
    ahora = int(time.time())
    capa.ejecutar(lambda r: r.set(f'jwt:revoked_before:{user_id}', ahora, ex=minutos_token * 60 + 60),
                  critico=True)
    logger.info(f"    Tokens del usuario {user_id} emitidos antes de {ahora} revocados")


class ValidadorJWT:

    def __init__(self, config: ConfigComun, capa: CapaRedis, metricas=None):
        self.config = config
        self.capa = capa
        self.metricas = metricas

    def _rechazo(self, codigo: str, mensaje: str, motivo_log: str, status: int = 401) -> AuthError:
        if self.metricas:
            self.metricas.incrementar('jwt_rechazados')
        logger.warning(f"    JWT rechazado: {motivo_log}")
        return AuthError(codigo, mensaje, status)

    def validar(self, authorization: Optional[str]) -> Dict[str, Any]:
        token = extraer_token(authorization)
        c = self.config
        try:
            claims = jwt.decode(token, c.jwt_secret_key, algorithms=[c.jwt_algorithm], issuer=c.jwt_issuer,
                                options={'require': CLAIMS_REQUERIDOS})
        except jwt.ExpiredSignatureError:
            raise self._rechazo('ERR_TOKEN_EXPIRADO', 'El token expiró. Renueva la sesión o inicia sesión de nuevo.',
                                'expirado (exp en el pasado)')
        except jwt.InvalidAlgorithmError:
            raise self._rechazo('ERR_TOKEN_INVALIDO', 'El token usa un algoritmo no permitido.',
                                f'algoritmo distinto de {c.jwt_algorithm}')
        except jwt.InvalidSignatureError:
            raise self._rechazo('ERR_TOKEN_INVALIDO', 'La firma del token no es válida.',
                                'firma invalida (no lo emitio login o fue alterado)')
        except jwt.InvalidIssuerError:
            raise self._rechazo('ERR_TOKEN_INVALIDO', 'El token no fue emitido por el servicio de login.',
                                f"emisor distinto de '{c.jwt_issuer}'")
        except jwt.MissingRequiredClaimError as exc:
            raise self._rechazo('ERR_TOKEN_INVALIDO', 'El token no trae los datos requeridos.',
                                f"falta el claim '{exc.claim}'")
        except jwt.InvalidTokenError as exc:
            raise self._rechazo('ERR_TOKEN_INVALIDO', 'El token no es válido.', f'malformado ({exc.__class__.__name__})')

        if claims.get('typ') != 'access':
            raise self._rechazo('ERR_TOKEN_INVALIDO', 'Se esperaba un token de acceso.', f"typ={claims.get('typ')!r}")
        if not isinstance(claims['role_id'], int):
            raise self._rechazo('ERR_TOKEN_INVALIDO', 'El token no trae un role_id válido.', 'role_id no entero')

        # Lista de revocacion: critica. Si Redis no responde -> RedisNoDisponible -> 503.
        jti, user_id = claims['jti'], claims['user_id']

        def consultar(r):
            tubo = r.pipeline(transaction=False)
            tubo.exists(f'jwt:revoked:{jti}')
            tubo.get(f'jwt:revoked_before:{user_id}')
            return tubo.execute()

        revocado, revocado_antes = self.capa.ejecutar(consultar, critico=True)
        if revocado:
            if self.metricas:
                self.metricas.incrementar('jwt_revocados')
            raise self._rechazo('ERR_TOKEN_REVOCADO', 'El token fue revocado (se cerró la sesión).',
                                f'revocado en Redis (jwt:revoked:{jti})')
        if revocado_antes and int(claims['iat']) <= int(revocado_antes):
            if self.metricas:
                self.metricas.incrementar('jwt_revocados')
            raise self._rechazo('ERR_TOKEN_REVOCADO', 'El token ya no es válido: cambiaron tus credenciales o permisos.',
                                f'emitido antes de jwt:revoked_before:{user_id}')

        logger.info(f"    JWT valido: firma OK, alg {c.jwt_algorithm}, no revocado; "
                    f"user_id={user_id} role_id={claims['role_id']} jti={jti[:8]}…")
        return claims

    def requiere_jwt(self, roles: Optional[Iterable[int]] = None):
        """Decorador para rutas protegidas. `roles`: role_id permitidos
        (None = cualquier usuario autenticado). Deja los claims en g.usuario."""
        permitidos = set(roles) if roles else None

        def decorador(vista):
            @functools.wraps(vista)
            def envoltura(*args, **kwargs):
                claims = self.validar(request.headers.get('Authorization'))
                if permitidos and claims['role_id'] not in permitidos:
                    nombres = ', '.join(NOMBRES_ROL.get(r, str(r)) for r in sorted(permitidos))
                    raise self._rechazo('ERR_SIN_PERMISOS', f'Tu rol no tiene permiso para esta operación (requiere: {nombres}).',
                                        f"role_id={claims['role_id']} no autorizado (403)", status=403)
                g.usuario = claims
                return vista(*args, **kwargs)

            envoltura.requiere_jwt = True
            envoltura.roles = sorted(permitidos) if permitidos else None
            return envoltura
        return decorador
