"""
Emision del JWT de acceso (sin base de datos ni Redis).

    cd services/login
    venv\\Scripts\\python -m pytest -q
"""
import sys
import time
from pathlib import Path

import jwt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth.jwt_tokens import descripcion_segura, emitir_access_token, huella, nuevo_refresh_token  # noqa: E402
from libreria_common.config import ConfigComun  # noqa: E402

CLAVE = 'clave-de-prueba-solo-para-tests-0123456789abcdef'
CONFIG = ConfigComun(jwt_secret_key=CLAVE, redis_url='redis://x')
USUARIO = {'id': 'u-7', 'email': 'admin@libreria.test', 'rol': 'administrador', 'role_id': 1}


def test_access_token_hs256_20_minutos_con_claims_requeridos():
    bloque = emitir_access_token(CONFIG, USUARIO, sid='s-1')
    claims = jwt.decode(bloque['access_token'], CLAVE, algorithms=['HS256'], issuer='libreria-login')
    assert jwt.get_unverified_header(bloque['access_token'])['alg'] == 'HS256'
    assert claims['user_id'] == claims['sub'] == 'u-7'
    assert claims['role_id'] == 1 and claims['rol'] == 'administrador'
    assert claims['sid'] == 's-1' and claims['typ'] == 'access'
    assert claims['jti'] == bloque['jti'] and len(claims['jti']) == 32
    assert claims['exp'] - claims['iat'] == 20 * 60
    assert bloque['expires_in'] == 20 * 60


def test_cada_token_tiene_jti_distinto():
    assert emitir_access_token(CONFIG, USUARIO, 's')['jti'] != emitir_access_token(CONFIG, USUARIO, 's')['jti']


def test_refresh_token_opaco_y_huella():
    r1, r2 = nuevo_refresh_token(), nuevo_refresh_token()
    assert r1 != r2 and len(r1) >= 60
    assert huella(r1) != r1 and len(huella(r1)) == 64


def test_descripcion_segura():
    t = emitir_access_token(CONFIG, USUARIO, 's')['access_token']
    assert t not in descripcion_segura(t)
