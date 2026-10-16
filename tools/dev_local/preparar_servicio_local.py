"""
Prepara en LOCAL los microservicios nuevos: rol de PostgreSQL con contrasena
aleatoria, permisos (sus migraciones SQL), .env propio y variables comunes.
No imprime contrasenas. Requiere PGPASSWORD (superusuario postgres) en el entorno.

    set PGPASSWORD=...   (solo en esa terminal)
    python preparar_servicio_local.py users authors pedidos pagos
"""
import os
import secrets
import subprocess
import sys
from pathlib import Path

PSQL = r'C:\Program Files\PostgreSQL\18\bin\psql.exe'
REPO = Path(__file__).resolve().parents[2]
SERVICIOS = {
    #  servicio   puerto  base          rol                 migraciones (relativas al repo)
    'users':   (5004, 'library_db',  'users_app_user',    ['db/10_roles.sql', 'db/11_users_service.sql']),
    'authors': (5005, 'libreria_db', 'authors_app_user',  ['services/authors/sql/01_autores.sql']),
    'pedidos': (5003, 'libreria_db', 'orders_app_user',   ['services/pedidos/sql/01_pedidos.sql']),
    'pagos':   (5002, 'libreria_db', 'payments_app_user', ['services/pagos/sql/01_pagos.sql']),
}


def psql(base: str, *args: str) -> str:
    r = subprocess.run([PSQL, '-U', 'postgres', '-h', 'localhost', '-d', base, '-v', 'ON_ERROR_STOP=1', '-X', '-q',
                        '-tA', *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f'psql fallo en {base}: {r.stderr.strip()[:300]}')
    return r.stdout.strip()


if not os.environ.get('PGPASSWORD'):
    raise SystemExit('Define PGPASSWORD con la contrasena de postgres en esta terminal.')

for nombre in sys.argv[1:]:
    puerto, base, rol, migraciones = SERVICIOS[nombre]
    clave = secrets.token_urlsafe(24)
    existe = psql('postgres', '-c', f"SELECT 1 FROM pg_roles WHERE rolname = '{rol}'") == '1'
    psql('postgres', '-c', f"{'ALTER' if existe else 'CREATE'} ROLE {rol} WITH LOGIN PASSWORD '{clave}'")
    for sql in migraciones:
        if (REPO / sql).exists():
            psql(base, '-f', str(REPO / sql))
    env = REPO / 'services' / nombre / '.env'
    prefijo = nombre.upper()
    env.write_text(f"{prefijo}_HOST=127.0.0.1\n{prefijo}_PORT={puerto}\nFLASK_DEBUG=False\n"
                   f"DB_HOST=localhost\nDB_PORT=5432\nDB_NAME={base}\nDB_USER={rol}\nDB_PASSWORD={clave}\n",
                   encoding='utf-8', newline='\n')
    print(f'{nombre}: rol {rol} {"actualizado" if existe else "creado"}, migraciones aplicadas, .env escrito')

subprocess.run([sys.executable, str(Path(__file__).parent / 'actualizar_env_local.py'), *sys.argv[1:]], check=True)
