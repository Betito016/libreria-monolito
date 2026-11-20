"""
Prueba del límite de tasa del gateway (RF8): manda una ráfaga de peticiones en
paralelo desde esta máquina (una sola IP) y cuenta cuántas reciben 429.

    python prueba_limite.py                       # 120 GET al catálogo, 30 en paralelo
    python prueba_limite.py 200 50 /api/books/categories?format=json

Límite configurado en nginx/library-gateway.conf: 20 peticiones/s por IP con
ráfaga de 40 (zona lim_ip). Una ráfaga mayor que ~40 + 20/s debe producir 429.
"""
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import requests

GW = 'http://34.135.84.31:8080'
TOTAL = int(sys.argv[1]) if len(sys.argv) > 1 else 120
PARALELO = int(sys.argv[2]) if len(sys.argv) > 2 else 30
RUTA = sys.argv[3] if len(sys.argv) > 3 else '/api/books/books?format=json&page_size=1'


def pedir(_):
    try:
        r = requests.get(GW + RUTA, timeout=20)
        return r.status_code, (r.json().get('codigo_error') if r.status_code == 429 else None)
    except requests.RequestException as exc:
        return type(exc).__name__, None


with ThreadPoolExecutor(PARALELO) as pool:
    resultados = list(pool.map(pedir, range(TOTAL)))
conteo = Counter(c for c, _ in resultados)
print(f'{TOTAL} peticiones a {GW}{RUTA} ({PARALELO} en paralelo, una sola IP):')
for codigo, n in sorted(conteo.items(), key=lambda x: str(x[0])):
    print(f'  HTTP {codigo}: {n}')
print('  código de error en las 429:', {e for c, e in resultados if c == 429} or '-')
