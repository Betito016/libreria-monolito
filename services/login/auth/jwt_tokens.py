"""
Emision del JWT de acceso. Login es el UNICO servicio que firma tokens; los
otros cinco los validan con la misma JWT_SECRET_KEY (libreria_common.seguridad).

Claims del token de acceso (HS256, 20 minutos como maximo):
    sub, user_id   id del usuario
    email          correo del usuario
    role_id, rol   rol del usuario (1 administrador, 2 cliente)
    sid            id de la sesion en Redis (session:<sid>), para cerrarla en /logout
    jti            id unico del token: clave de la lista de revocacion (jwt:revoked:<jti>)
    typ            'access'
    iss, iat, exp  emisor, emision y vencimiento

El refresh token NO es un JWT: es un valor aleatorio opaco que solo existe en
Redis (refresh:<sha256>), y se rota en cada renovacion.
"""
import hashlib
import secrets
import time
import uuid
from typing import Any, Dict

import jwt

from libreria_common.config import ConfigComun


def emitir_access_token(config: ConfigComun, usuario: Dict[str, Any], sid: str) -> Dict[str, Any]:
    ahora = int(time.time())
    expira = ahora + config.access_token_minutos * 60
    jti = uuid.uuid4().hex
    claims = {
        'sub': str(usuario['id']),
        'user_id': str(usuario['id']),
        'email': usuario['email'],
        'role_id': int(usuario['role_id']),
        'rol': usuario['rol'],
        'sid': sid,
        'jti': jti,
        'typ': 'access',
        'iss': config.jwt_issuer,
        'iat': ahora,
        'exp': expira,
    }
    return {
        'access_token': jwt.encode(claims, config.jwt_secret_key, algorithm=config.jwt_algorithm),
        'token_type': 'Bearer',
        'algoritmo': config.jwt_algorithm,
        'jti': jti,
        'expira_en_epoch': expira,
        'expires_in': expira - ahora,
    }


def nuevo_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def huella(refresh_token: str) -> str:
    """En Redis se guarda la huella SHA-256, nunca el refresh token en claro."""
    return hashlib.sha256(refresh_token.encode()).hexdigest()


def descripcion_segura(token: str) -> str:
    if not token:
        return '[SIN TOKEN]'
    return f"[PRESENTE {token[:10]}…{token[-4:]} ({len(token)} caracteres)]"
