"""
Pruebas de la emision de JWT del microservicio de login (sin base de datos).

    cd services/login
    venv\\Scripts\\python -m pytest -q
"""
import os
import sys
import time
from pathlib import Path

import jwt

CLAVE = 'clave-de-prueba-solo-para-tests-0123456789abcdef'
os.environ['JWT_SECRET'] = CLAVE
os.environ['JWT_ALGORITHM'] = 'HS256'
os.environ['JWT_ISSUER'] = 'libreria-login'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth.jwt_tokens import descripcion_segura, emitir_token  # noqa: E402

USUARIO = {'id': 7, 'email': 'admin@libreria.test', 'rol': 'administrador'}


def test_token_firmado_con_claims_esperados():
    expira = int(time.time()) + 1800
    bloque = emitir_token(USUARIO, expira)
    assert bloque['token_type'] == 'Bearer'
    assert bloque['algoritmo'] == 'HS256'
    claims = jwt.decode(bloque['access_token'], CLAVE, algorithms=['HS256'], issuer='libreria-login')
    assert claims['sub'] == '7'
    assert claims['rol'] == 'administrador'
    assert claims['email'] == 'admin@libreria.test'
    assert claims['exp'] == expira
    assert 1795 <= bloque['expires_in'] <= 1800


def test_vencimiento_maximo_30_minutos():
    bloque = emitir_token(USUARIO, int(time.time()) + 8 * 3600)   # sesion configurada de 8 h
    claims = jwt.decode(bloque['access_token'], CLAVE, algorithms=['HS256'])
    assert claims['exp'] - claims['iat'] <= 30 * 60
    assert bloque['expires_in'] <= 30 * 60


def test_token_no_valida_con_otra_clave():
    bloque = emitir_token(USUARIO, int(time.time()) + 60)
    try:
        jwt.decode(bloque['access_token'], 'otra-clave-0123456789-0123456789-xx', algorithms=['HS256'])
    except jwt.InvalidSignatureError:
        return
    raise AssertionError('Un token debe fallar al validarse con otra clave')


def test_descripcion_segura_no_revela_el_token():
    t = emitir_token(USUARIO, int(time.time()) + 60)['access_token']
    texto = descripcion_segura(t)
    assert texto.startswith('[JWT PRESENTE')
    assert t not in texto
    assert descripcion_segura('') == '[SIN JWT]'
