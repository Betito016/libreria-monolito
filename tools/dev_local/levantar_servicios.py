"""
Levanta los 6 microservicios en local, cada uno en su propia ventana de consola
(con sus logs en vivo) o en segundo plano escribiendo a un archivo de log.

    python levantar_servicios.py                 ventanas (para ver y mostrar los logs)
    python levantar_servicios.py --logs <dir>    sin ventanas, logs en <dir>\\<servicio>.log

Requiere el tunel a Redis (tunel_redis.ps1) y PostgreSQL local encendidos.
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2] / 'services'
VENTANA = Path(__file__).resolve().parent / 'ventana_consola.py'
SERVICIOS = [('login', 5000), ('books', 5001), ('pagos', 5002), ('pedidos', 5003), ('users', 5004), ('authors', 5005)]


def escuchando(puerto: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(('127.0.0.1', puerto)) == 0


logs = Path(sys.argv[sys.argv.index('--logs') + 1]) if '--logs' in sys.argv else None
env = {**os.environ, 'PYTHONUNBUFFERED': '1', 'PYTHONIOENCODING': 'utf-8'}
for nombre, puerto in SERVICIOS:
    if escuchando(puerto):
        print(f'{nombre:8} :{puerto} ya estaba encendido')
        continue
    carpeta = REPO / nombre
    python = str(carpeta / 'venv' / 'Scripts' / 'python.exe')
    if logs:
        logs.mkdir(parents=True, exist_ok=True)
        salida = open(logs / f'{nombre}.log', 'w', encoding='utf-8')
        subprocess.Popen([python, 'app.py'], cwd=carpeta, env=env, stdout=salida, stderr=subprocess.STDOUT,
                         creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        titulo = f'MICROSERVICIO {nombre.upper()} :{puerto}'
        subprocess.Popen(['conhost.exe', python, str(VENTANA), titulo, '140', '40', str(carpeta), 'app.py'], env=env,
                         creationflags=subprocess.CREATE_NEW_CONSOLE)

for nombre, puerto in SERVICIOS:
    for _ in range(60):
        if escuchando(puerto):
            break
        time.sleep(0.5)
    print(f'{nombre:8} :{puerto} {"listo" if escuchando(puerto) else "NO RESPONDE (revisa su log)"}')
