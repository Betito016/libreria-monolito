"""
Autenticacion de las escrituras con JWT (Authorization: Bearer <token>).

El token lo emite el microservicio de login al iniciar sesion. Este servicio
lo valida LOCALMENTE con la misma clave (JWT_SECRET) y el mismo algoritmo
(JWT_ALGORITHM): no necesita preguntarle a login en cada peticion.

La proteccion es SELECTIVA: solo las rutas decoradas con
@requiere_jwt_administrador la exigen (POST, PUT, PATCH y DELETE de libros).
El catalogo (GET /books, GET /books/{isbn}), /categories y /health siguen
publicos. No hay middleware global.

Orden de las comprobaciones y su respuesta:
    1. Falta el header Authorization          401 ERR_TOKEN_AUSENTE
    2. El esquema no es "Bearer"              401 ERR_TOKEN_INVALIDO
    3. "Bearer" sin token                     401 ERR_TOKEN_AUSENTE
    4. Algoritmo distinto al configurado      401 ERR_TOKEN_INVALIDO
    5. Firma invalida / token malformado      401 ERR_TOKEN_INVALIDO
    6. Emisor distinto, faltan claims         401 ERR_TOKEN_INVALIDO
    7. Token expirado (exp)                   401 ERR_TOKEN_EXPIRADO
    8. Token valido pero rol != administrador 403 ERR_SIN_PERMISOS

Los logs nunca muestran el token completo: solo `[JWT PRESENTE ...]`.
"""
import functools
import logging
from typing import Any, Dict, Optional

import jwt
import requests
from flask import g, request

from config.config import Config

logger = logging.getLogger("BooksMicroservice.jwt")


class AuthError(Exception):
    """Error de autenticacion/autorizacion con su codigo HTTP."""

    def __init__(self, codigo: str, mensaje: str, status: int):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.status = status


def descripcion_segura(token: Optional[str]) -> str:
    """Representacion del token apta para logs: nunca el token completo."""
    if not token:
        return '[SIN JWT]'
    return f"[JWT PRESENTE {token[:10]}…{token[-4:]} ({len(token)} caracteres)]"


def describir_authorization(valor: Optional[str]) -> str:
    """Describe el header Authorization para los logs sin revelar el token."""
    if not valor:
        return 'Authorization: (ausente)'
    esquema, _, token = valor.strip().partition(' ')
    if esquema.lower() != 'bearer':
        return f"Authorization: esquema '{esquema}' (no es Bearer)"
    return f"Authorization: Bearer {descripcion_segura(token.strip())}"


def _extraer_token(valor: Optional[str]) -> str:
    if not valor or not valor.strip():
        raise AuthError('ERR_TOKEN_AUSENTE',
                        'Falta el header Authorization: Bearer <token>. Inicia sesión para obtener uno.', 401)
    esquema, _, token = valor.strip().partition(' ')
    if esquema.lower() != 'bearer':
        raise AuthError('ERR_TOKEN_INVALIDO',
                        f"El header Authorization debe usar el esquema Bearer (se recibió '{esquema}').", 401)
    token = token.strip()
    if not token:
        raise AuthError('ERR_TOKEN_AUSENTE', 'El header Authorization dice Bearer pero no trae el token.', 401)
    return token


def validar_jwt(valor_authorization: Optional[str]) -> Dict[str, Any]:
    """Valida el header y devuelve los claims del token, o lanza AuthError (401)."""
    token = _extraer_token(valor_authorization)
    try:
        # algorithms=[...] fija el algoritmo aceptado: un token firmado con
        # otro (o con "none") se rechaza aunque diga lo contrario en su header.
        claims = jwt.decode(
            token,
            Config.JWT_SECRET,
            algorithms=[Config.JWT_ALGORITHM],
            issuer=Config.JWT_ISSUER,
            options={'require': ['exp', 'iat', 'sub', 'iss']},
        )
    except jwt.ExpiredSignatureError:
        logger.warning("    JWT rechazado: expirado (exp en el pasado)")
        raise AuthError('ERR_TOKEN_EXPIRADO', 'El token expiró. Inicia sesión de nuevo.', 401)
    except jwt.InvalidAlgorithmError:
        logger.warning(f"    JWT rechazado: algoritmo distinto de {Config.JWT_ALGORITHM}")
        raise AuthError('ERR_TOKEN_INVALIDO', 'El token usa un algoritmo no permitido.', 401)
    except jwt.InvalidSignatureError:
        logger.warning("    JWT rechazado: firma invalida (no lo emitio este login o fue alterado)")
        raise AuthError('ERR_TOKEN_INVALIDO', 'La firma del token no es válida.', 401)
    except jwt.InvalidIssuerError:
        logger.warning(f"    JWT rechazado: emisor distinto de '{Config.JWT_ISSUER}'")
        raise AuthError('ERR_TOKEN_INVALIDO', 'El token no fue emitido por el servicio de login.', 401)
    except jwt.MissingRequiredClaimError as exc:
        logger.warning(f"    JWT rechazado: falta el claim '{exc.claim}'")
        raise AuthError('ERR_TOKEN_INVALIDO', 'El token no trae los datos requeridos.', 401)
    except jwt.InvalidTokenError as exc:
        logger.warning(f"    JWT rechazado: malformado ({exc.__class__.__name__})")
        raise AuthError('ERR_TOKEN_INVALIDO', 'El token no es válido.', 401)

    logger.info(f"    JWT valido: firma OK, alg {Config.JWT_ALGORITHM}, sub={claims['sub']} "
                f"email={claims.get('email')} rol={claims.get('rol')}")
    return claims


def requiere_jwt_administrador(vista):
    """Decorador para las rutas de escritura: exige un JWT valido de un
    administrador. Deja los claims en `g.usuario` para la vista."""

    @functools.wraps(vista)
    def envoltura(*args, **kwargs):
        claims = validar_jwt(request.headers.get('Authorization'))
        if claims.get('rol') != Config.ROL_ADMINISTRADOR:
            logger.warning(f"    JWT valido pero rol '{claims.get('rol')}': sin permiso para escribir (403)")
            raise AuthError('ERR_SIN_PERMISOS', 'Solo un administrador puede modificar el catálogo.', 403)
        g.usuario = claims
        return vista(*args, **kwargs)

    # Marca leida por el log de peticiones para distinguir rutas protegidas.
    envoltura.requiere_jwt = True
    return envoltura


def estado_login() -> Dict[str, Any]:
    """Para /health: con JWT el login ya no es necesario para validar
    escrituras, pero si para que alguien pueda iniciar sesion y obtener uno."""
    try:
        respuesta = requests.get(
            f"{Config.LOGIN_SERVICE_URL}/health", params={'format': 'json'}, timeout=2
        )
        estado = respuesta.json().get('estado')
        return {'disponible': estado == 'ok', 'estado': estado, 'url': Config.LOGIN_SERVICE_URL}
    except (requests.RequestException, ValueError) as exc:
        return {
            'disponible': False,
            'estado': 'inaccesible',
            'url': Config.LOGIN_SERVICE_URL,
            'error': exc.__class__.__name__,
        }
