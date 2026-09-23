"""
Validacion de sesion delegada al microservicio de login.

Este servicio NO maneja sesiones propias ni conoce la clave con la que
login firma sus cookies. Cuando llega una peticion de escritura, toma la
cookie de sesion que envio el cliente y le pregunta a login, via
GET /session, a quien pertenece. Login sigue siendo la unica autoridad
sobre identidad; books solo decide si ese usuario puede escribir.

Consecuencia deliberada: si login no responde, las escrituras se rechazan
con 503 (no se puede comprobar quien escribe), pero las lecturas siguen
funcionando porque el catalogo es publico.
"""
import logging
from typing import Any, Dict

import requests

from config.config import Config

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Error de autenticacion/autorizacion con su codigo HTTP."""

    def __init__(self, codigo: str, mensaje: str, status: int):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.status = status


def obtener_usuario(cookies) -> Dict[str, Any]:
    """Devuelve el usuario de la sesion o lanza AuthError."""
    cookie = cookies.get(Config.LOGIN_SESSION_COOKIE_NAME)
    if not cookie:
        raise AuthError(
            'ERR_SESION_INVALIDA', 'Debes iniciar sesión para modificar el catálogo.', 401
        )

    try:
        # Solo se reenvia la cookie de sesion de login, no el resto de las
        # cookies que el cliente pudiera traer.
        respuesta = requests.get(
            f"{Config.LOGIN_SERVICE_URL}/session",
            params={'format': 'json'},
            cookies={Config.LOGIN_SESSION_COOKIE_NAME: cookie},
            timeout=Config.LOGIN_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        logger.error(f"No se pudo contactar al microservicio de login: {exc}")
        raise AuthError(
            'ERR_LOGIN_NO_DISPONIBLE',
            'No se pudo validar la sesión: el servicio de autenticación no responde.',
            503,
        ) from exc

    if respuesta.status_code != 200:
        raise AuthError(
            'ERR_LOGIN_NO_DISPONIBLE',
            f'El servicio de autenticación respondió con estado {respuesta.status_code}.',
            503,
        )

    try:
        datos = respuesta.json()
    except ValueError as exc:
        raise AuthError(
            'ERR_LOGIN_NO_DISPONIBLE', 'El servicio de autenticación devolvió una respuesta inválida.', 503
        ) from exc

    if not datos.get('autenticado'):
        if datos.get('motivo') == 'expirada':
            raise AuthError('ERR_SESION_EXPIRADA', 'La sesión expiró. Inicia sesión de nuevo.', 401)
        raise AuthError('ERR_SESION_INVALIDA', 'La sesión no es válida. Inicia sesión de nuevo.', 401)

    return datos['usuario']


def requerir_administrador(cookies) -> Dict[str, Any]:
    """401 si no hay sesion valida; 403 si la hay pero no es administrador."""
    usuario = obtener_usuario(cookies)
    if usuario.get('rol') != Config.ROL_ADMINISTRADOR:
        raise AuthError(
            'ERR_SIN_PERMISOS', 'Solo un administrador puede modificar el catálogo.', 403
        )
    if not usuario.get('email_verificado'):
        raise AuthError(
            'ERR_SIN_PERMISOS', 'La cuenta debe tener el correo verificado para modificar el catálogo.', 403
        )
    return usuario


def estado_login() -> Dict[str, Any]:
    """Para /health: el login es una dependencia de las escrituras."""
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
