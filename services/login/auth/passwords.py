"""
Hash y verificacion de contrasenas.

Se usa bcrypt deliberadamente, no por costumbre: la tabla `usuarios` ya
contiene hashes generados por el monolito Node.js (bcrypt costo 10, prefijo
$2b$) y por el seed de PostgreSQL (pgcrypto `crypt()/gen_salt('bf')`,
prefijo $2a$). La libreria bcrypt de Python verifica ambos formatos, asi que
un usuario puede autenticarse indistintamente en el monolito o en este
microservicio, y los usuarios creados aqui funcionan tambien alla.

Cambiar de algoritmo (pbkdf2, argon2, etc.) romperia esa interoperabilidad.
"""
from typing import Optional

import bcrypt

# Mismo costo que usa el monolito Node (bcrypt.hash(password, 10)).
BCRYPT_ROUNDS = 10

# Limite duro de bcrypt: solo considera los primeros 72 bytes.
BCRYPT_MAX_BYTES = 72

PASSWORD_MIN_LENGTH = 8


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode('utf-8')[:BCRYPT_MAX_BYTES], salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Compara en tiempo constante. Devuelve False ante un hash con formato
    invalido en vez de propagar la excepcion, para no filtrar detalles de
    implementacion al cliente."""
    try:
        return bcrypt.checkpw(
            password.encode('utf-8')[:BCRYPT_MAX_BYTES],
            password_hash.encode('utf-8'),
        )
    except (ValueError, TypeError):
        return False


def validate_password_strength(password: str) -> Optional[str]:
    """Devuelve un mensaje de error, o None si la contrasena es aceptable."""
    if not password:
        return "La contraseña es obligatoria."
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"La contraseña debe tener al menos {PASSWORD_MIN_LENGTH} caracteres."
    return None
