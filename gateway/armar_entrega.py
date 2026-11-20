"""
Arma el .zip de la entrega del Reverse Proxy / API Gateway y lo VERIFICA abriéndolo.

    python gateway/armar_entrega.py [ruta_del_zip]

Contenido: el monorepo según git (versionados + nuevos no ignorados) en libreria-monolito/,
más el ejecutable de la app Java (libreria-java.jar), que git ignora porque se genera.
Fuera: .git, node_modules, venv, cachés, .env reales y data/ (copia vieja de la semilla).
"""
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DESTINO = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO.parent / 'entrega' / 'ReverseProxy_Vargas_Vargas.zip'
RAIZ = 'libreria-monolito'
EXTRAS = ['apps/java-desktop/libreria-java.jar']
PROHIBIDO = re.compile(r'(^|/)(\.git|node_modules|venv|\.venv|__pycache__|\.pytest_cache|build|[^/]+\.egg-info)(/|$)|(^|/)\.env$')
REQUERIDOS = [
    'ENTREGA_REVERSE_PROXY.md', 'gateway/README.md', 'gateway/REFLEXION.md',
    'gateway/nginx/library-gateway.conf', 'gateway/nginx/library-web.conf', 'gateway/nginx/rutas-api.conf',
    'apps/electron-catalog/src/models/ConfigModel.js', 'apps/Python_app/libreria_app/config/settings.py',
    'apps/java-desktop/src/library/java/LibreriaJavaApp.java', 'apps/java-desktop/libreria-java.jar',
    'gateway/evidencias/capturas_app_python/', 'gateway/evidencias/capturas_app_electron/',
    'gateway/evidencias/capturas_app_java/', 'gateway/evidencias/locust/',
]
SOSPECHOSO = [re.compile(rb'eyJ[\w-]{20,}\.[\w-]{20,}\.[\w-]{20,}'),
              re.compile(rb'redis' + rb'://:(?!cambiar-por)[^@<\s(]{12,}@'),
              re.compile(rb'Forti' + rb'Guard Intrusion Prevention')]   # página de bloqueo de la red escolar, no evidencia

salida = subprocess.run(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=REPO,
                        capture_output=True, check=True).stdout.decode('utf-8')
archivos = sorted({a for a in salida.split('\0') if a and not a.startswith('data/') and (REPO / a).is_file()}
                  | {e for e in EXTRAS if (REPO / e).is_file()})

DESTINO.parent.mkdir(parents=True, exist_ok=True)
DESTINO.unlink(missing_ok=True)
with zipfile.ZipFile(DESTINO, 'w', zipfile.ZIP_DEFLATED) as z:
    for a in archivos:
        z.write(REPO / a, f'{RAIZ}/{a}')

problemas = []
clave = os.environ.get('GATEWAY_PASSWORD', '').encode()
with zipfile.ZipFile(DESTINO) as z:
    nombres = [n[len(RAIZ) + 1:] for n in z.namelist()]
    for req in REQUERIDOS:
        if not any(n == req or (req.endswith('/') and n.startswith(req)) for n in nombres):
            problemas.append(f'falta {req}')
    problemas += [f'ruta prohibida: {n}' for n in nombres if PROHIBIDO.search(n)]
    for n in z.namelist():
        datos = z.read(n)
        for patron in SOSPECHOSO:
            if patron.search(datos):
                problemas.append(f'contenido sospechoso ({patron.pattern[:24]!r}) en {n}')
        if clave and '/gateway/' in n and clave in datos:
            problemas.append(f'la contraseña de GATEWAY_PASSWORD aparece en {n}')

pendientes = (REPO / 'gateway' / 'REFLEXION.md').read_text(encoding='utf-8').count('_(escribe aquí)_')
if pendientes:
    print(f'AVISO: gateway/REFLEXION.md aún tiene {pendientes} sección(es) "_(escribe aquí)_" sin llenar.')

evid = [n for n in nombres if n.startswith('gateway/evidencias/')]
print(f'{DESTINO}  {DESTINO.stat().st_size / 1024 / 1024:.1f} MB  ({len(nombres)} archivos, {len(evid)} de evidencias)')
print('VERIFICACION OK' if not problemas else 'PROBLEMAS:\n  ' + '\n  '.join(problemas))
sys.exit(1 if problemas else 0)
