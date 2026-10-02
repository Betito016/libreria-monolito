"""
Emision de JWT de acceso.

Login es el UNICO que firma tokens. El servicio de libros los valida con la
misma clave (JWT_SECRET) y el mismo algoritmo (JWT_ALGORITHM), sin tener que
preguntarle a login en cada peticion.

Contenido del token (claims):
    sub    id del usuario
    email  correo del usuario
    rol    'administrador' | 'cliente'  (libros exige administrador para escribir)
    iss    emisor: 'libreria-login'
    iat    emitido en (epoch UTC)
    exp    vence en (epoch UTC): el mismo instante que la sesion, para que
           token y sesion expiren juntos y POST /session/extend prorrogue ambos.

El token viaja en la respuesta de /login y de /session/extend, nunca en logs:
en los logs solo aparece su descripcion segura (ver `descripcion_segura`).
"""
import time
from typing import Any, Dict

import jwt

from config.config import Config


JWT_MAX_MINUTOS = 30


def emitir_token(usuario: Dict[str, Any], expira_en: int) -> Dict[str, Any]:
    """Firma un token para `usuario` que vence en `expira_en` (epoch UTC), sin
    pasar nunca de JWT_MAX_MINUTOS aunque la sesion se configure mas larga.
    Devuelve el bloque que se agrega a la respuesta: el token y su metadata."""
    ahora = int(time.time())
    expira_en = min(expira_en, ahora + JWT_MAX_MINUTOS * 60)
    claims = {
        'sub': str(usuario['id']),
        'email': usuario['email'],
        'rol': usuario['rol'],
        'iss': Config.JWT_ISSUER,
        'iat': ahora,
        'exp': expira_en,
    }
    token = jwt.encode(claims, Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM)
    return {
        'access_token': token,
        'token_type': 'Bearer',
        'algoritmo': Config.JWT_ALGORITHM,
        'expira_en_epoch': expira_en,
        'expires_in': max(0, expira_en - ahora),
    }


def descripcion_segura(token: str) -> str:
    """Representacion del token apta para logs: nunca el token completo."""
    if not token:
        return '[SIN JWT]'
    return f"[JWT PRESENTE {token[:10]}…{token[-4:]} ({len(token)} caracteres)]"
