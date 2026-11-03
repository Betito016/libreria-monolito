"""
Arma el .zip de entrega de la práctica de Locust y lo VERIFICA abriéndolo de nuevo.

    venv\\Scripts\\python armar_entrega.py [ruta_del_zip]

Contenido: el monorepo completo según git (archivos versionados + archivos nuevos que el
.gitignore no excluye), dentro de la carpeta libreria-monolito/. Así quedan fuera .git/,
node_modules/, venv/.venv/, __pycache__/, .pytest_cache/, *.egg-info y los .env reales.
También se excluye data/ (copia vieja de la semilla que nunca se versionó; la vigente está en db/).

Al terminar abre el zip y comprueba:
  - que estén locust_tests/locustfile.py, RESULTADOS.md, REFLEXION.md y las evidencias;
  - que no haya rutas prohibidas (.git, node_modules, venv, cachés, .env);
  - que no aparezcan JWT, URLs de Redis con contraseña ni la contraseña usada en las pruebas
    (si está en LOCUST_PASSWORD, se busca su valor sin mostrarlo).
"""
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DESTINO = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO.parent / 'entrega' / 'Locust_Vargas_Vargas.zip'
RAIZ = 'libreria-monolito'
EXCLUIR = re.compile(r'^data/')
PROHIBIDO = re.compile(r'(^|/)(\.git|node_modules|venv|\.venv|__pycache__|\.pytest_cache|[^/]+\.egg-info)(/|$)|(^|/)\.env$')
REQUERIDOS = ['locust_tests/locustfile.py', 'locust_tests/RESULTADOS.md', 'locust_tests/REFLEXION.md',
              'locust_tests/README.md', 'locust_tests/evidencias/']
SOSPECHOSO = [re.compile(rb'eyJ[\w-]{20,}\.[\w-]{20,}\.[\w-]{20,}'),        # JWT completo
              # Redis con contraseña real (el marcador de los .env.example no cuenta). Se arma en
              # dos partes para que este mismo archivo no coincida con el patrón.
              re.compile(rb'redis' + rb'://:(?!cambiar-por)[^@<\s(]{12,}@')]

salida = subprocess.run(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=REPO,
                        capture_output=True, check=True).stdout.decode('utf-8')
archivos = sorted(a for a in salida.split('\0') if a and not EXCLUIR.match(a) and (REPO / a).is_file())

DESTINO.parent.mkdir(parents=True, exist_ok=True)
DESTINO.unlink(missing_ok=True)
with zipfile.ZipFile(DESTINO, 'w', zipfile.ZIP_DEFLATED) as z:
    for a in archivos:
        z.write(REPO / a, f'{RAIZ}/{a}')

# ---------------------------------------------------------------- verificación
problemas = []
clave = os.environ.get('LOCUST_PASSWORD', '').encode()
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
                problemas.append(f'posible secreto ({patron.pattern[:20]}…) en {n}')
        if clave and n.startswith(f'{RAIZ}/locust_tests/') and clave in datos:
            problemas.append(f'la contraseña de LOCUST_PASSWORD aparece en {n}')

evidencias = [n for n in nombres if n.startswith('locust_tests/evidencias/')]
print(f'{DESTINO}  {DESTINO.stat().st_size / 1024 / 1024:.1f} MB  ({len(nombres)} archivos, {len(evidencias)} evidencias)')
print('CSV:', sum(n.endswith('.csv') for n in evidencias), '| HTML:', sum(n.endswith('.html') for n in evidencias),
      '| PNG:', sum(n.endswith('.png') for n in evidencias))
print('VERIFICACION OK' if not problemas else 'PROBLEMAS:\n  ' + '\n  '.join(problemas))
sys.exit(1 if problemas else 0)
