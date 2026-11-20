"""
Pruebas de rendimiento con Locust: monolito web vs. microservicios de la Librería.

==========================================================================
1. QUÉ SE MIDE
==========================================================================
Cuánto tardan y cuántos errores dan las operaciones de LECTURA más comunes de la
tienda (ver el catálogo, buscar, ver el detalle de un libro, ver autores) en los
dos sistemas del monorepo, con la misma carga y las mismas pausas:

    Operación               Monolito (:3000, HTML)         Microservicios (JSON)
    ---------------------   ----------------------------   -----------------------------------------
    Catálogo completo       GET /libros                    books   GET /api/books?page_size=100
    Búsqueda por título     GET /libros?q=<texto>          books   GET /api/books?titulo=<texto>
    Detalle de un libro     GET /libros/{id}               books   GET /api/books/{isbn}
    Lista de autores        GET /admin/autores (admin)     authors GET /authors
    Portada                 GET /                          —
    Lecturas con JWT        —                              users GET /users, pedidos GET /orders,
                                                           pagos GET /payments, login GET /session

No se crean, modifican ni borran datos (el enunciado pide preferir lecturas y
evitar escrituras repetidas). Las únicas peticiones POST son el inicio y el
cierre de sesión de cada usuario virtual: una vez al empezar y una al terminar.

==========================================================================
2. QUÉ HACE UN USUARIO VIRTUAL, PASO A PASO
==========================================================================
    a) Locust crea el usuario (según el perfil: 1, 5, 20…).
    b) on_start(): inicia sesión UNA vez con el correo y la contraseña del
       administrador (leídos de variables de entorno) y guarda lo que necesita:
       la cookie de sesión (monolito) o el JWT (microservicios), y la lista de
       libros reales para pedir detalles que existen.
    c) Bucle mientras dure la prueba:
         - elige UNA tarea (@task) al azar, respetando los pesos;
         - hace la petición y la VALIDA (código HTTP + contenido correcto);
         - espera wait_time (1 a 3 s) y vuelve a elegir.
    d) on_stop(): cierra la sesión (POST /logout).

==========================================================================
3. CÓMO SE EJECUTA (detalle en README.md)
==========================================================================
    $env:LOCUST_EMAIL = '<correo admin>'; $env:LOCUST_PASSWORD = '<contraseña>'   # no se guardan aquí
    $env:PERFIL = 'load'                                     # smoke|load|stress|spike|soak|quiebre
    locust -f locustfile.py --host http://34.135.84.31 MonolitoUser        (o MicroserviciosUser)

--host es SOLO la IP de la instancia GCP; los puertos de cada sistema están abajo.
Las pruebas deben apuntar a la IP externa de la instancia: si --host es localhost
o 127.x, el archivo se niega a correr.

==========================================================================
4. CONCEPTOS DE LOCUST USADOS
==========================================================================
- User (HttpUser): un "usuario virtual". Locust crea N copias y cada una repite
  sus tareas en bucle con su propia sesión HTTP (cookies propias), como si
  fueran N personas distintas con su propio navegador.
- self.client: el "navegador" de cada usuario (una requests.Session). Cada
  petición que hace se mide y se registra en las estadísticas con su `name`.
- @task(peso): una acción del usuario. El peso es la probabilidad relativa de
  elegirla: con @task(4) y @task(1), la primera ocurre ~4 veces más.
- wait_time: pausa entre una tarea y la siguiente de un mismo usuario (simula a
  una persona leyendo la página). Sin pausa, cada usuario dispararía sin parar.
- catch_response=True: permite decidir NOSOTROS si una respuesta es éxito o
  falla (r.success() / r.failure("motivo")). Sin esto, Locust solo mira el
  código HTTP, y un 200 con la página equivocada contaría como éxito.
- usuarios: cuántos usuarios virtuales concurrentes hay en un momento dado.
- spawn_rate: cuántos usuarios por segundo se agregan (o quitan) hasta llegar al
  número objetivo.
- duración: cuánto dura la prueba.
- LoadTestShape: permite programar cómo cambian usuarios y spawn_rate en el
  tiempo (rampas, picos). Aquí TODOS los perfiles se definen como shapes, así
  que -u, -r y -t (o los campos de la GUI) se ignoran: el perfil manda.
- Estadísticas: por cada nombre de petición Locust calcula número de
  peticiones, fallas, mediana, percentiles (p95 = el 95 % de las peticiones
  tardó eso o menos) y RPS (peticiones por segundo).
"""
import json
import logging
import os
import random
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

from locust import HttpUser, LoadTestShape, between, events, task

# Mensajes propios del locustfile (aparecen en la consola donde corre Locust).
logger = logging.getLogger('locust.libreria')

# ======================================================================
# PARÁMETROS COMUNES A LOS DOS SISTEMAS
# Son iguales para el monolito y los microservicios: si cambiaran, la
# comparación ya no sería justa.
# ======================================================================
PAUSA_ENTRE_TAREAS = between(1, 3)   # cada usuario espera entre 1 y 3 s (al azar) entre peticiones
UMBRAL_P95_MS = 1000                  # el servicio se considera degradado si el p95 supera 1 s ...
UMBRAL_ERRORES = 0.05                 # ... o si fallan más del 5 % de las peticiones
TIMEOUT_S = 30                        # si una petición tarda más de 30 s se corta y cuenta como falla

# Puertos de cada sistema en la instancia GCP (la IP llega por --host).
PUERTO_MONOLITO = 3000
PUERTOS = {'login': 5000, 'books': 5001, 'pagos': 5002, 'pedidos': 5003, 'users': 5004, 'authors': 5005}
# Library API Gateway (práctica siguiente): con LOCUST_VIA=gateway los microservicios se
# llaman por http://IP:8080/api/<prefijo>/... en lugar de su puerto directo.
VIA_GATEWAY = os.environ.get('LOCUST_VIA', 'directo').strip().lower() == 'gateway'
PUERTO_GATEWAY = 8080
PREFIJO_GATEWAY = {5000: 'login', 5001: 'books', 5002: 'pagos', 5003: 'pedidos', 5004: 'users', 5005: 'autores'}
# Palabras para las búsquedas por título (las mismas en ambos sistemas).
BUSQUEDAS = ['cloud', 'data', 'the', 'python', 'security', 'arquitectura']
# Carpeta donde se guardan las evidencias (aquí se escribe el resultado del punto de quiebre).
EVIDENCIAS = Path(__file__).resolve().parent / 'evidencias'

# ======================================================================
# PERFILES DE CARGA
# Cada perfil es una lista de etapas (segundo_en_que_termina, usuarios, spawn_rate).
# Ejemplo: (36, 2, 1) = "hasta el segundo 36, mantener 2 usuarios, agregándolos
# de 1 en 1 por segundo". Al pasar el último segundo, la prueba termina sola.
# ======================================================================
PERFILES = {
    # Smoke: carga mínima (1 usuario, 30 s) para comprobar que las rutas responden bien.
    'smoke':  [(30, 1, 1)],
    # Load: carga esperada y estable: 5 usuarios, se agregan de 1 en 1 por segundo, 2 min.
    'load':   [(120, 5, 1)],
    # Stress: rampa por etapas por encima de lo esperado: 2→5→10→15→20, 18 s cada una (90 s).
    # El enunciado dice "hasta 3 minutos"; se usó 90 s por tiempo disponible (anotado en RESULTADOS.md).
    'stress': [(18, 2, 1), (36, 5, 2), (54, 10, 3), (72, 15, 3), (90, 20, 3)],
    # Spike: 2 usuarios, salto brusco a 15 (15 usuarios/s), se mantiene 30 s y vuelve a 2 (2 min).
    'spike':  [(30, 2, 2), (60, 15, 15), (120, 2, 15)],
    # Soak: carga sostenida y baja para ver si algo se degrada con el tiempo (3 usuarios, 4 min).
    'soak':   [(240, 3, 1)],
    # Punto de quiebre: +1 usuario cada 6 s desde 1 hasta 20 (máx. 2 min, dentro del límite de
    # 4 min del enunciado); se detiene al incumplir el umbral (ver PerfilDeCarga._quiebre).
    'quiebre': [(6 * n, n, 1) for n in range(1, 21)],
    # EXPLORATORIA (fuera de los perfiles requeridos, que llegan a 20 usuarios): rampa de
    # 1 usuario/s hasta 100 (100 s) y se mantiene hasta el segundo 280. La rampa gradual es
    # más realista que 100 usuarios de golpe (y no convierte la prueba en una de logins).
    'exploratoria100': [(280, 100, 1)],
}
# El perfil se elige con la variable de entorno PERFIL (por defecto, smoke).
PERFIL = os.environ.get('PERFIL', 'smoke').strip().lower()
if PERFIL not in PERFILES:
    raise SystemExit(f"PERFIL='{PERFIL}' no existe. Usa uno de: {', '.join(PERFILES)}")


class PerfilDeCarga(LoadTestShape):
    """Controla cuántos usuarios hay en cada segundo según el PERFIL elegido.

    Locust llama a tick() aproximadamente una vez por segundo. tick() responde:
      - (usuarios, spawn_rate): "en este momento quiero N usuarios, agrégalos
        o quítalos a esta velocidad";
      - None: "terminó la prueba".
    """

    VENTANA_QUIEBRE_S = 10        # referencia: el p95 "actual" de Locust cubre más o menos los últimos 10 s

    def __init__(self):
        super().__init__()
        self.etapas = PERFILES[PERFIL]
        self.quiebre = None       # (segundo, usuarios, p95, %errores) cuando se incumple el umbral
        self._previo = (0, 0)     # (peticiones, fallas) acumuladas en la evaluación anterior

    def tick(self):
        t = self.get_run_time()                   # segundos desde que empezó la prueba
        if PERFIL == 'quiebre':
            return self._quiebre(t)               # el punto de quiebre tiene lógica propia
        # Resto de perfiles: buscar la etapa en la que estamos.
        for fin, usuarios, tasa in self.etapas:
            if t < fin:
                return usuarios, tasa
        return None                               # se pasó la última etapa: fin de la prueba

    def _quiebre(self, t):
        """Sube 1 usuario cada 6 s. Cada ~6 s revisa cómo va el sistema EN ESE MOMENTO
        (no el acumulado de toda la prueba):
          - p95 actual (ventana reciente de Locust),
          - % de errores desde la revisión anterior.
        Si el p95 > 1 s o los errores > 5 %, deja de subir, mantiene esos usuarios
        20 s para confirmar y termina. Guarda en evidencias/ en qué punto ocurrió."""
        stats = self.runner.stats.total           # estadísticas de todas las peticiones
        if self.quiebre is None:
            peticiones, fallas = stats.num_requests, stats.num_failures
            nuevas = peticiones - self._previo[0]          # peticiones desde la revisión anterior
            if nuevas >= 20 and int(t) % 6 == 0:          # revisar solo con datos suficientes
                errores = (fallas - self._previo[1]) / nuevas
                p95 = stats.get_current_response_time_percentile(0.95) or 0
                self._previo = (peticiones, fallas)
                if p95 > UMBRAL_P95_MS or errores > UMBRAL_ERRORES:
                    # Se incumplió el umbral: anotar cuándo, con cuántos usuarios y por qué.
                    self.quiebre = (round(t), self.get_current_user_count(), p95, round(errores * 100, 2))
                    logger.warning(f'PUNTO DE QUIEBRE: t={self.quiebre[0]} s, usuarios={self.quiebre[1]}, '
                                   f'p95 reciente={p95} ms, errores recientes={self.quiebre[3]} %')
                    _guardar_quiebre(self.quiebre)
        else:
            # Ya hubo quiebre: mantener los mismos usuarios 20 s más y terminar.
            if t < self.quiebre[0] + 20:
                return self.quiebre[1], 1
            return None
        # Sin quiebre todavía: seguir la rampa (+1 usuario cada 6 s).
        for fin, usuarios, tasa in self.etapas:
            if t < fin:
                return usuarios, tasa
        _guardar_quiebre(None)                    # se llegó a 20 usuarios sin incumplir
        return None


def _guardar_quiebre(quiebre):
    """Escribe evidencias/quiebre_<sistema>.json con el resultado (una sola vez por corrida)."""
    if getattr(_guardar_quiebre, 'hecho', False):
        return
    _guardar_quiebre.hecho = True
    EVIDENCIAS.mkdir(exist_ok=True)
    clase = os.environ.get('LOCUST_SISTEMA', 'sistema')
    datos = ({'incumplido': True, 'segundo': quiebre[0], 'usuarios': quiebre[1], 'p95_reciente_ms': quiebre[2],
              'errores_recientes_pct': quiebre[3]} if quiebre else
             {'incumplido': False, 'nota': 'Se llegó a 20 usuarios (fin de la rampa) sin incumplir el umbral.'})
    (EVIDENCIAS / f'quiebre_{clase}.json').write_text(json.dumps(datos, indent=2), encoding='utf-8')


@events.init.add_listener
def _no_localhost(environment, **_):
    """Se ejecuta al iniciar Locust. El enunciado exige probar contra la IP externa de
    la instancia GCP: si --host es localhost o 127.x, se detiene antes de generar carga."""
    host = urlsplit(environment.host or '').hostname or ''
    if host in ('localhost', '::1') or host.startswith('127.') or not host:
        raise SystemExit('Usa --host http://<IP externa de la instancia GCP>; no se permite localhost.')


# ======================================================================
# USUARIOS VIRTUALES
# ======================================================================
class _Base(HttpUser):
    """Lo común a los dos tipos de usuario. abstract=True: Locust no crea usuarios
    de esta clase; solo de MonolitoUser y MicroserviciosUser."""
    abstract = True
    wait_time = PAUSA_ENTRE_TAREAS                # misma pausa para ambos sistemas

    def _url(self, puerto: int, ruta: str) -> str:
        """Arma la URL completa: IP de --host + puerto del sistema + ruta.
        Ej.: _url(5001, '/api/books') -> http://34.135.84.31:5001/api/books

        Con LOCUST_VIA=gateway las peticiones a los microservicios pasan por el Library
        API Gateway: http://IP:8080/api/<servicio> + la misma ruta. El escenario y los
        nombres en las estadísticas no cambian, así se compara directo contra gateway."""
        p = urlsplit(self.host)
        if VIA_GATEWAY and puerto in PREFIJO_GATEWAY:
            return f'{p.scheme}://{p.hostname}:{PUERTO_GATEWAY}/api/{PREFIJO_GATEWAY[puerto]}{ruta}'
        return f'{p.scheme}://{p.hostname}:{puerto}{ruta}'

    @staticmethod
    def _credenciales():
        """Correo y contraseña del administrador, desde variables de entorno de la
        terminal (nunca escritos en este archivo ni en la entrega)."""
        correo, clave = os.environ.get('LOCUST_EMAIL'), os.environ.get('LOCUST_PASSWORD')
        if not correo or not clave:
            raise SystemExit('Define LOCUST_EMAIL y LOCUST_PASSWORD (no se guardan en el archivo).')
        return correo, clave

    def _get(self, url: str, nombre: str, validar):
        """GET medido y VALIDADO.
          - name=nombre: con ese nombre aparece en Statistics (p. ej. "[monolito] GET /libros").
            Rutas con id distinto (/libros/7, /libros/12) se agrupan en un solo nombre.
          - Falla si el código no es 200, o si `validar` encuentra que el contenido no es
            el esperado (un 200 con la página equivocada TAMBIÉN es falla)."""
        with self.client.get(url, name=nombre, catch_response=True, timeout=TIMEOUT_S) as r:
            if r.status_code != 200:
                r.failure(f'HTTP {r.status_code}')
                return None
            motivo = validar(r)
            if motivo:
                r.failure(motivo)
                return None
            r.success()
            return r


class MonolitoUser(_Base):
    """Usuario que navega el MONOLITO web (Express + EJS: el servidor arma y devuelve
    páginas HTML completas). Se identifica en las estadísticas con "[monolito]"."""

    def on_start(self):
        """Se ejecuta UNA vez al nacer el usuario: inicia sesión y prepara la lista de libros."""
        os.environ.setdefault('LOCUST_SISTEMA', 'MonolitoUser')
        self.base = self._url(PUERTO_MONOLITO, '')            # http://34.135.84.31:3000
        correo, clave = self._credenciales()

        # 1) Login con el formulario HTML (POST /login, campos email y password).
        #    Si es correcto, el monolito guarda una cookie de sesión en ESTE usuario
        #    virtual y redirige a la portada "/". Si es incorrecto, redirige a "/login".
        with self.client.post(f'{self.base}/login', data={'email': correo, 'password': clave},
                              name='[monolito] POST /login', catch_response=True, timeout=TIMEOUT_S) as r:
            if r.status_code != 200 or urlsplit(r.url).path.rstrip('/') == '/login':
                r.failure('login rechazado')
                logger.error('LOGIN DEL MONOLITO RECHAZADO: revisa LOCUST_EMAIL / LOCUST_PASSWORD. '
                             'Sin sesión, las rutas protegidas redirigen y se cuentan como fallas.')
            else:
                r.success()

        # 2) Leer el catálogo una vez para sacar los id reales de los libros (enlaces
        #    href="/libros/<id>"), así la tarea "detalle" pide libros que existen.
        r = self.client.get(f'{self.base}/libros', name='[monolito] GET /libros (preparacion)', timeout=TIMEOUT_S)
        self.ids = sorted(set(re.findall(r'href="/libros/(\d+)"', r.text)))

    def on_stop(self):
        """Se ejecuta UNA vez al terminar: cierra la sesión en el monolito."""
        self.client.post(f'{self.base}/logout', name='[monolito] POST /logout', timeout=TIMEOUT_S)

    @staticmethod
    def _html(ruta_esperada, marcador='</html>'):
        """Validación de una página del monolito:
          1) que NO haya terminado en /login (eso significa que no hay sesión);
          2) que haya terminado en la ruta pedida: sin permisos, el monolito redirige
             a otra página (p. ej. la portada) y responde 200, y eso es una falla;
          3) que el HTML contenga el `marcador` (p. ej. enlaces '/libros/' en el catálogo)."""
        def validar(r):
            final = urlsplit(r.url).path.rstrip('/') or '/'
            if final == '/login':
                return 'redirigió a /login: no hay sesión (¿credenciales incorrectas?)'
            if final != ruta_esperada:
                return f'redirigió a {final} en lugar de {ruta_esperada} (¿sin permisos?)'
            return None if marcador in r.text else f"la página no contiene '{marcador}'"
        return validar

    # ---- Tareas: Locust elige una al azar según su peso ----

    @task(4)
    def catalogo(self):
        """Ver el catálogo completo (la acción más frecuente). Debe traer enlaces a libros."""
        self._get(f'{self.base}/libros', '[monolito] GET /libros', self._html('/libros', '/libros/'))

    @task(2)
    def busqueda(self):
        """Buscar libros por texto (palabra al azar de BUSQUEDAS)."""
        self._get(f'{self.base}/libros?q={random.choice(BUSQUEDAS)}', '[monolito] GET /libros?q=',
                  self._html('/libros'))

    @task(3)
    def detalle(self):
        """Ver el detalle de un libro real elegido al azar (requiere sesión)."""
        if self.ids:
            libro = random.choice(self.ids)
            self._get(f'{self.base}/libros/{libro}', '[monolito] GET /libros/{id}', self._html(f'/libros/{libro}'))

    @task(2)
    def autores(self):
        """Ver la lista de autores (página de administración: solo funciona si el login fue de admin)."""
        self._get(f'{self.base}/admin/autores', '[monolito] GET /admin/autores', self._html('/admin/autores'))

    @task(1)
    def portada(self):
        """Ver la portada."""
        self._get(f'{self.base}/', '[monolito] GET /', self._html('/'))


class MicroserviciosUser(_Base):
    """Usuario que usa la API de los MICROSERVICIOS (Flask, respuestas JSON con
    ?format=json). Cada petición lleva el servicio entre corchetes ("[books]",
    "[users]"…) para separarlo en las estadísticas."""

    def on_start(self):
        """Se ejecuta UNA vez al nacer el usuario: obtiene un JWT y la lista de ISBN."""
        os.environ.setdefault('LOCUST_SISTEMA', 'MicroserviciosUser')
        correo, clave = self._credenciales()
        self.token = None

        # 1) Login en el microservicio login (POST /login con JSON). Devuelve un JWT
        #    (token de acceso, 20 min) y deja una cookie de sesión. El JWT solo se envía
        #    en las rutas que lo exigen: users, pedidos y pagos.
        with self.client.post(self._url(PUERTOS['login'], '/login?format=json'),
                              json={'email': correo, 'password': clave},
                              name='[login] POST /login', catch_response=True, timeout=TIMEOUT_S) as r:
            if r.status_code == 200:
                self.token = r.json()['token']['access_token']
                r.success()
            else:
                r.failure(f'login HTTP {r.status_code}')
                logger.error(f'LOGIN DE MICROSERVICIOS RECHAZADO (HTTP {r.status_code}): revisa LOCUST_EMAIL / '
                             'LOCUST_PASSWORD. Sin JWT, users/pedidos/pagos responderán 401.')

        # 2) Leer el catálogo una vez para obtener los ISBN reales (para la tarea "detalle").
        r = self.client.get(self._url(PUERTOS['books'], '/api/books?page_size=100&format=json'),
                            name='[books] GET /api/books (preparacion)', timeout=TIMEOUT_S)
        try:
            self.isbns = [libro['isbn'] for libro in r.json().get('libros', [])]
        except ValueError:
            self.isbns = []

    def on_stop(self):
        """Se ejecuta UNA vez al terminar: logout, que revoca el JWT en Redis."""
        if self.token:
            self.client.post(self._url(PUERTOS['login'], '/logout?format=json'), headers=self._auth(),
                             name='[login] POST /logout', timeout=TIMEOUT_S)

    def _auth(self):
        """Cabecera Authorization: Bearer <JWT> (vacía si no hay token)."""
        return {'Authorization': f'Bearer {self.token}'} if self.token else {}

    @staticmethod
    def _json(clave):
        """Validación de una respuesta JSON: que sea JSON y que traiga la `clave` esperada
        (p. ej. 'libros' en el catálogo); si no, es una falla aunque el código sea 200."""
        def validar(r):
            try:
                datos = r.json()
            except ValueError:
                return 'la respuesta no es JSON'
            return None if clave in datos else f"el JSON no tiene '{clave}'"
        return validar

    def _get_jwt(self, servicio, ruta, nombre, clave):
        """GET a una ruta protegida: envía el JWT, exige 200 y valida el JSON.
        Sin token o con token inválido el servicio responde 401 y se cuenta como falla."""
        with self.client.get(self._url(PUERTOS[servicio], ruta), headers=self._auth(), name=nombre,
                             catch_response=True, timeout=TIMEOUT_S) as r:
            if r.status_code != 200:
                r.failure(f'HTTP {r.status_code}')
            elif self._json(clave)(r):
                r.failure(self._json(clave)(r))
            else:
                r.success()

    # ---- Tareas comparables con el monolito (MISMOS pesos que en MonolitoUser) ----

    @task(4)
    def catalogo(self):
        """Catálogo completo (books). Con page_size=100 trae todos los libros, como /libros del monolito."""
        self._get(self._url(PUERTOS['books'], '/api/books?page_size=100&format=json'),
                  '[books] GET /api/books?page_size=100', self._json('libros'))

    @task(2)
    def busqueda(self):
        """Búsqueda por título (books), equivalente a /libros?q= del monolito."""
        self._get(self._url(PUERTOS['books'], f'/api/books?titulo={random.choice(BUSQUEDAS)}&format=json'),
                  '[books] GET /api/books?titulo=', self._json('libros'))

    @task(3)
    def detalle(self):
        """Detalle de un libro real (books), equivalente a /libros/{id} del monolito."""
        if self.isbns:
            self._get(self._url(PUERTOS['books'], f'/api/books/{random.choice(self.isbns)}?format=json'),
                      '[books] GET /api/books/{isbn}', self._json('isbn'))

    @task(2)
    def autores(self):
        """Lista de autores (authors), equivalente a /admin/autores del monolito. Es pública."""
        self._get(self._url(PUERTOS['authors'], '/authors?format=json'), '[authors] GET /authors',
                  self._json('autores'))

    # ---- Lecturas de los demás servicios (con JWT donde la ruta lo exige) ----

    @task(1)
    def usuarios(self):
        """Lista de usuarios (users): lectura administrativa, exige JWT de administrador."""
        self._get_jwt('users', '/users?format=json', '[users] GET /users', 'usuarios')

    @task(1)
    def pedidos(self):
        """Lista de pedidos (pedidos): exige JWT."""
        self._get_jwt('pedidos', '/orders?format=json', '[pedidos] GET /orders', 'pedidos')

    @task(1)
    def pagos(self):
        """Lista de pagos (pagos): exige JWT."""
        self._get_jwt('pagos', '/payments?format=json', '[pagos] GET /payments', 'pagos')

    @task(1)
    def sesion(self):
        """Consultar la sesión (login): usa la cookie que dejó POST /login; la sesión vive en Redis."""
        self._get(self._url(PUERTOS['login'], '/session?format=json'), '[login] GET /session',
                  self._json('autenticado'))
