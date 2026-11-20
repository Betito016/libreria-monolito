"""
Salud agregada del Library API Gateway (RF5).

nginx enruta y balancea, pero no puede consultar a todas las instancias y armar un
resumen. Este proceso pequeño (solo biblioteca estándar de Python, sin dependencias)
lo hace: nginx publica su respuesta en GET http://<IP>:8080/health.

    GET /health  ->  200 {"estado": "ok", ...}        todas las instancias responden
                     503 {"estado": "degraded", ...}   alguna instancia o servicio no responde

Para cada instancia consulta su /health (en paralelo, con timeout) y reporta:
  - instancia "ok" si responde HTTP 200; "down" si no responde, se agota el tiempo o da 5xx;
  - servicio "ok" si todas sus instancias están ok, "degraded" si solo algunas, "down" si ninguna.
El estado que cada servicio reporta de sí mismo (p. ej. Redis caído) se incluye como "detalle".

No contiene lógica de negocio: solo pregunta y resume. Configuración en variables de
entorno (config/gateway.env), sin editar el código (RF9).
"""
import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def leer_instancias(texto: str) -> dict:
    """'login=http://a;books=http://b,http://c' -> {'login': ['http://a'], 'books': ['http://b', 'http://c']}"""
    servicios = {}
    for parte in filter(None, (p.strip() for p in texto.split(';'))):
        nombre, urls = parte.split('=', 1)
        servicios[nombre.strip()] = [u.strip().rstrip('/') for u in urls.split(',') if u.strip()]
    return servicios


INSTANCIAS = leer_instancias(os.environ.get('GW_INSTANCIAS', ''))
RUTA = os.environ.get('GW_RUTA_SALUD', '/health?format=json')
RUTA_SOAP = os.environ.get('GW_RUTA_SALUD_SOAP', '/')
TIMEOUT = float(os.environ.get('GW_TIMEOUT_SEGUNDOS', '3'))


def revisar_instancia(servicio: str, url: str) -> dict:
    inicio = time.perf_counter()
    resultado = {'url': url}
    try:
        with urllib.request.urlopen(url + (RUTA_SOAP if servicio == 'soap' else RUTA), timeout=TIMEOUT) as r:
            resultado['http'] = r.status
            cuerpo = r.read(65536)
        try:
            resultado['detalle'] = json.loads(cuerpo).get('estado')       # lo que el servicio dice de sí mismo
        except (ValueError, AttributeError):
            pass
        resultado['estado'] = 'ok'
    except urllib.error.HTTPError as exc:                                 # respondió, pero con error
        resultado.update(http=exc.code, estado='ok' if exc.code < 500 else 'down')
    except (urllib.error.URLError, OSError) as exc:                       # no respondió / timeout
        resultado.update(estado='down', error=type(getattr(exc, 'reason', exc)).__name__)
    resultado['ms'] = round((time.perf_counter() - inicio) * 1000)
    return resultado


def salud() -> tuple:
    trabajos = [(s, u) for s, urls in INSTANCIAS.items() for u in urls]
    with ThreadPoolExecutor(max_workers=max(1, len(trabajos))) as pool:
        resultados = list(pool.map(lambda t: (t[0], revisar_instancia(*t)), trabajos))
    servicios = {}
    for servicio, r in resultados:
        servicios.setdefault(servicio, {'instancias': []})['instancias'].append(r)
    for datos in servicios.values():
        vivas = sum(i['estado'] == 'ok' for i in datos['instancias'])
        datos['estado'] = 'ok' if vivas == len(datos['instancias']) else ('degraded' if vivas else 'down')
    estado = 'ok' if all(d['estado'] == 'ok' for d in servicios.values()) else 'degraded'
    return (200 if estado == 'ok' else 503), {
        'estado': estado, 'gateway': 'library-api-gateway', 'servicios': servicios,
        'timestamp': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }


class Manejador(BaseHTTPRequestHandler):
    server_version = 'library-gateway-salud'

    def do_GET(self):
        if self.path.split('?')[0] != '/health':
            codigo, datos = 404, {'estado': 'error', 'codigo_error': 'ERR_GATEWAY_RUTA', 'mensaje': 'Ruta no encontrada.'}
        else:
            codigo, datos = salud()
        rid = self.headers.get('X-Request-ID')
        if rid:
            datos['request_id'] = rid
        cuerpo = json.dumps(datos, ensure_ascii=False).encode('utf-8')
        self.send_response(codigo)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, formato, *args):        # nginx ya registra cada petición
        pass


if __name__ == '__main__':
    host = os.environ.get('GW_SALUD_HOST', '127.0.0.1')
    puerto = int(os.environ.get('GW_SALUD_PUERTO', '8090'))
    print(f'Salud agregada del gateway en http://{host}:{puerto}/health; instancias: {INSTANCIAS}', flush=True)
    ThreadingHTTPServer((host, puerto), Manejador).serve_forever()
