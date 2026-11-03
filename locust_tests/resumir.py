"""
Resume las corridas de Locust guardadas en evidencias/ (nada se escribe a mano):

  evidencias/tablas_resultados.md   tabla por prueba y sistema + tabla por ruta
  evidencias/graficas/*.png         usuarios, p95 y RPS en el tiempo por perfil (monolito vs microservicios)
                                    y p95 por operación comparable

    venv\\Scripts\\python resumir.py

Notas sobre los números:
- RPS, p95 y % de errores del sistema salen de la fila "Aggregated" de
  <perfil>_<sistema>_stats.csv, que Locust calcula sobre TODAS las peticiones de
  la corrida (incluye el POST /login y la petición "(preparacion)" que cada usuario
  hace una sola vez al iniciar).
- Las gráficas en el tiempo usan _stats_history.csv: ahí los percentiles son
  "actuales" (ventana móvil de ~10 s), por eso muestran picos que el acumulado suaviza.
- Duración = segundos entre la primera y la última fila del historial.
"""
import csv
import json
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

AQUI = Path(__file__).resolve().parent
EV = AQUI / 'evidencias'
GRAF = EV / 'graficas'
PERFILES = ['smoke', 'load', 'stress', 'spike', 'soak', 'quiebre']
SISTEMAS = ['monolito', 'microservicios']
UMBRAL_P95, UMBRAL_ERR = 1000, 5.0
COLOR = {'monolito': '#c2410c', 'microservicios': '#1d4ed8'}
# Operaciones comparables: (etiqueta, nombre en monolito, nombre en microservicios)
COMPARABLES = [
    ('Catálogo', '[monolito] GET /libros', '[books] GET /api/books?page_size=100'),
    ('Búsqueda', '[monolito] GET /libros?q=', '[books] GET /api/books?titulo='),
    ('Detalle', '[monolito] GET /libros/{id}', '[books] GET /api/books/{isbn}'),
    ('Autores', '[monolito] GET /admin/autores', '[authors] GET /authors'),
]


def leer(ruta):
    with open(ruta, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def num(valor, defecto=0.0):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto


def historial(perfil, sistema):
    ruta = EV / f'{perfil}_{sistema}_stats_history.csv'
    if not ruta.exists():
        return []
    filas = [f for f in leer(ruta) if f['Name'] == 'Aggregated']
    if not filas:
        return []
    t0 = int(filas[0]['Timestamp'])
    return [{'t': int(f['Timestamp']) - t0, 'usuarios': int(num(f['User Count'])), 'rps': num(f['Requests/s']),
             'fps': num(f['Failures/s']), 'p95': num(f['95%'], None) if f['95%'] not in ('N/A', '') else None,
             'p50': num(f['50%'], None) if f['50%'] not in ('N/A', '') else None} for f in filas]


def resumen(perfil, sistema):
    ruta = EV / f'{perfil}_{sistema}_stats.csv'
    if not ruta.exists():
        return None
    filas = leer(ruta)
    total = next(f for f in filas if f['Name'] == 'Aggregated')
    hist = historial(perfil, sistema)
    n, fallas = int(num(total['Request Count'])), int(num(total['Failure Count']))
    errores = 100 * fallas / n if n else 0.0
    p95 = num(total['95%'])
    quiebre = EV / f'quiebre_{sistema}.json'
    return {
        'perfil': perfil, 'sistema': sistema, 'n': n, 'fallas': fallas,
        'usuarios_max': max((h['usuarios'] for h in hist), default=0),
        'duracion': hist[-1]['t'] if hist else 0,
        'rps': num(total['Requests/s']), 'p50': num(total['50%']), 'p95': p95, 'p99': num(total['99%']),
        'errores': errores, 'cumple': p95 <= UMBRAL_P95 and errores <= UMBRAL_ERR,
        'rutas': {f['Name']: f for f in filas if f['Name'] != 'Aggregated'},
        'quiebre': json.loads(quiebre.read_text(encoding='utf-8')) if perfil == 'quiebre' and quiebre.exists() else None,
        'hist': hist,
    }


def grafica_perfil(perfil, datos):
    if not any(datos.get(s) for s in SISTEMAS):
        return
    fig, ejes = plt.subplots(3, 1, figsize=(10, 8.5), sharex=True)
    for s in SISTEMAS:
        d = datos.get(s)
        if not d:
            continue
        t = [h['t'] for h in d['hist']]
        ejes[0].plot(t, [h['usuarios'] for h in d['hist']], color=COLOR[s], label=s)
        ejes[1].plot(t, [h['p95'] if h['p95'] is not None else float('nan') for h in d['hist']], color=COLOR[s], label=s)
        ejes[2].plot(t, [h['rps'] for h in d['hist']], color=COLOR[s], label=f'{s} RPS')
        if any(h['fps'] for h in d['hist']):
            ejes[2].plot(t, [h['fps'] for h in d['hist']], color=COLOR[s], linestyle=':', label=f'{s} fallas/s')
    ejes[1].axhline(UMBRAL_P95, color='#991b1b', linestyle='--', linewidth=1, label='umbral p95 = 1 s')
    ejes[0].set_ylabel('usuarios')
    ejes[1].set_ylabel('p95 actual (ms)')
    ejes[2].set_ylabel('peticiones/s')
    ejes[2].set_xlabel('segundos desde el inicio')
    for e in ejes:
        e.grid(alpha=.3)
        e.legend(loc='upper left', fontsize=8)
    fig.suptitle(f'Perfil {perfil}: monolito vs microservicios (Locust, IP externa 34.135.84.31)')
    fig.tight_layout()
    fig.savefig(GRAF / f'{perfil}_tiempo.png', dpi=110)
    plt.close(fig)


def grafica_comparables(perfil, datos):
    if not all(datos.get(s) for s in SISTEMAS):
        return
    etiquetas, mono, micro = [], [], []
    for etiqueta, nm, nmi in COMPARABLES:
        rm, rmi = datos['monolito']['rutas'].get(nm), datos['microservicios']['rutas'].get(nmi)
        if rm and rmi:
            etiquetas.append(etiqueta)
            mono.append(num(rm['95%']))
            micro.append(num(rmi['95%']))
    if not etiquetas:
        return
    fig, eje = plt.subplots(figsize=(8, 4.2))
    x = range(len(etiquetas))
    eje.bar([i - .2 for i in x], mono, width=.4, color=COLOR['monolito'], label='monolito')
    eje.bar([i + .2 for i in x], micro, width=.4, color=COLOR['microservicios'], label='microservicios')
    for i, (a, b) in enumerate(zip(mono, micro)):
        eje.text(i - .2, a, f'{a:.0f}', ha='center', va='bottom', fontsize=8)
        eje.text(i + .2, b, f'{b:.0f}', ha='center', va='bottom', fontsize=8)
    eje.set_xticks(list(x), etiquetas)
    eje.set_ylabel('p95 (ms)')
    eje.set_title(f'p95 por operación comparable — perfil {perfil}')
    eje.legend()
    eje.grid(axis='y', alpha=.3)
    fig.tight_layout()
    fig.savefig(GRAF / f'{perfil}_comparables_p95.png', dpi=110)
    plt.close(fig)


def main():
    GRAF.mkdir(parents=True, exist_ok=True)
    todos = {p: {s: resumen(p, s) for s in SISTEMAS} for p in PERFILES}
    out = ['## Resumen por prueba y sistema (fila Aggregated de Locust)', '',
           '| Perfil | Sistema | Usuarios (máx) | Duración (s) | Peticiones | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Errores | Umbral (p95 ≤ 1 s y errores ≤ 5 %) |',
           '|---|---|---|---|---|---|---|---|---|---|---|']
    for p in PERFILES:
        for s in SISTEMAS:
            d = todos[p][s]
            if not d:
                out.append(f'| {p} | {s} | — | — | — | — | — | — | — | — | **no ejecutada** |')
                continue
            out.append(f"| {p} | {s} | {d['usuarios_max']} | {d['duracion']} | {d['n']} | {d['rps']:.2f} | "
                       f"{d['p50']:.0f} | {d['p95']:.0f} | {d['p99']:.0f} | {d['errores']:.2f} % ({d['fallas']}) | "
                       f"{'cumple' if d['cumple'] else '**incumple**'} |")
    out += ['', '## Punto de quiebre', '']
    for s in SISTEMAS:
        q = (todos['quiebre'][s] or {}).get('quiebre')
        out.append(f'- **{s}**: ' + ('sin datos' if not q else
                   (f"incumplió en t={q['segundo']} s con {q['usuarios']} usuarios (p95 reciente {q['p95_reciente_ms']} ms, "
                    f"errores recientes {q['errores_recientes_pct']} %)" if q['incumplido'] else q['nota'])))
    out += ['', '## p95 (ms) por operación comparable', '',
            '| Perfil | ' + ' | '.join(f'{e} mono | {e} micro' for e, _, _ in COMPARABLES) + ' |',
            '|---|' + '---|' * (2 * len(COMPARABLES))]
    for p in PERFILES:
        if not all(todos[p][s] for s in SISTEMAS):
            continue
        celdas = []
        for _, nm, nmi in COMPARABLES:
            for s, nombre in (('monolito', nm), ('microservicios', nmi)):
                r = todos[p][s]['rutas'].get(nombre)
                celdas.append(f"{num(r['95%']):.0f}" if r else '—')
        out.append(f'| {p} | ' + ' | '.join(celdas) + ' |')
    out += ['', '## Detalle por ruta (todas las corridas)', '',
            '| Perfil | Sistema | Petición | Peticiones | Fallas | p50 | p95 | p99 | RPS |', '|---|---|---|---|---|---|---|---|---|']
    for p in PERFILES:
        for s in SISTEMAS:
            d = todos[p][s]
            if not d:
                continue
            for nombre, r in sorted(d['rutas'].items()):
                out.append(f"| {p} | {s} | `{nombre}` | {r['Request Count']} | {r['Failure Count']} | {r['50%']} | "
                           f"{r['95%']} | {r['99%']} | {num(r['Requests/s']):.2f} |")
    out.append(f"\nGenerado por resumir.py el {datetime.now().isoformat(timespec='seconds')}.")
    (EV / 'tablas_resultados.md').write_text('\n'.join(out) + '\n', encoding='utf-8')
    for p in PERFILES:
        grafica_perfil(p, todos[p])
        grafica_comparables(p, todos[p])
    print('\n'.join(out[:20]))
    print(f'\nTablas: {EV / "tablas_resultados.md"}\nGráficas: {GRAF}')


if __name__ == '__main__':
    main()
