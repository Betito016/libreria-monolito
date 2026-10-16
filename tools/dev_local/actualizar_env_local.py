"""
Pone en los .env LOCALES de los microservicios las variables comunes:
JWT_SECRET_KEY (la misma en todos), REDIS_URL (tunel a la instancia),
ACCESS_TOKEN_MINUTES=20 y CORS_ORIGINS. No imprime ningun valor secreto.

    python actualizar_env_local.py login books users authors pedidos pagos
"""
import re
import secrets
import sys
from pathlib import Path

SERVICIOS = Path(__file__).resolve().parents[2] / 'services'
REDIS_URL = (Path.home() / '.libreria_secretos' / 'redis.env').read_text(encoding='utf-8').split('=', 1)[1].strip()
OBSOLETAS = ('JWT_SECRET', 'SECRET_KEY', 'SESSION_LIFETIME_MINUTES', 'LOGIN_SESSION_COOKIE_NAME')


def leer(ruta: Path) -> dict:
    if not ruta.exists():
        return {}
    return dict(l.split('=', 1) for l in ruta.read_text(encoding='utf-8').splitlines() if '=' in l and not l.startswith('#'))


# La clave JWT existente (login/books ya la comparten); si no hay, se genera.
existentes = [leer(SERVICIOS / s / '.env') for s in ('login', 'books')]
clave = next((e.get('JWT_SECRET_KEY') or e.get('JWT_SECRET') for e in existentes
              if e.get('JWT_SECRET_KEY') or e.get('JWT_SECRET')), None) or secrets.token_urlsafe(48)

comunes = {'JWT_SECRET_KEY': clave, 'JWT_ALGORITHM': 'HS256', 'JWT_ISSUER': 'libreria-login',
           'ACCESS_TOKEN_MINUTES': '20', 'REDIS_URL': REDIS_URL, 'REDIS_TIMEOUT_SECONDS': '3',
           'CORS_ORIGINS': 'http://localhost:5173,http://localhost:8123'}

for nombre in sys.argv[1:]:
    ruta = SERVICIOS / nombre / '.env'
    lineas = ruta.read_text(encoding='utf-8').splitlines() if ruta.exists() else []
    claves = set(comunes) | set(OBSOLETAS)
    lineas = [l for l in lineas if not re.match(rf"^({'|'.join(claves)})=", l)]
    lineas += ['', '# --- Comun a los 6 microservicios (actualizar_env_local.py) ---']
    lineas += [f'{k}={v}' for k, v in comunes.items()]
    ruta.write_text('\n'.join(l for i, l in enumerate(lineas) if l or (i and lineas[i - 1])) + '\n',
                    encoding='utf-8', newline='\n')
    print(f'{nombre}: .env actualizado ({", ".join(comunes)})')
