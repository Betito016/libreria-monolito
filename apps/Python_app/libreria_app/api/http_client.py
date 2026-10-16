"""
Comunicacion HTTP con los microservicios.

Es el UNICO lugar de la aplicacion que habla con la red. Todo lo demas
(servicios, pantallas) recibe un `ApiResult` y nunca una excepcion de
`requests`: una caida de red, un timeout, un puerto equivocado o un error
del servidor se convierten aqui en un resultado con un mensaje comprensible.

Tambien lleva un registro de las ultimas peticiones (metodo, URL, codigo
HTTP, cuerpo enviado) que la interfaz muestra en "Registro HTTP". Las
contrasenas y tokens se enmascaran antes de guardarse en ese registro.

AUTENTICACION (JWT)
    El token que devuelve POST /login se guarda en `ApiClient.token`. Este
    modulo decide, en un solo lugar, cuando agregar "Authorization: Bearer":
        books, authors          solo escrituras (POST, PUT, PATCH, DELETE)
        users, pedidos, pagos   todo, salvo /health y /roles (datos privados)
        login                   PATCH /profile y POST /logout (para revocar el token)
    Ninguna pantalla ni servicio arma el header.

LOGS EN CONSOLA (logger 'libreria.http')
    Cada peticion registra metodo, URL, headers relevantes, si usa JWT, el
    cuerpo enviado, el codigo HTTP y la respuesta. El token nunca se imprime
    completo: se muestra como [JWT PRESENTE eyJhbGciOi…abcd (N caracteres)].
"""
import copy
import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from libreria_app.config.settings import NOMBRE_SERVICIO, AppConfig

NOMBRES_SERVICIO = {k: v.lower() for k, v in NOMBRE_SERVICIO.items()}
CAMPOS_SENSIBLES = {'password', 'password_actual', 'token', 'access_token', 'refresh_token'}

# Metodos de escritura: siempre protegidos con JWT.
METODOS_PROTEGIDOS = {'POST', 'PUT', 'PATCH', 'DELETE'}
# Servicios con lecturas publicas (catalogo); en los demas, todo es privado.
LECTURA_PUBLICA = {'books', 'authors'}
RUTAS_PUBLICAS = {'/health', '/roles', '/metrics'}
RUTAS_LOGIN_CON_JWT = {'/profile', '/logout'}

logger = logging.getLogger('libreria.http')


def descripcion_token(token: Optional[str]) -> str:
    """Representacion del JWT apta para logs: nunca el token completo."""
    if not token:
        return '[SIN JWT]'
    return f"[JWT PRESENTE {token[:10]}…{token[-4:]} ({len(token)} caracteres)]"


def _recortar(texto: str, limite: int) -> str:
    return texto if len(texto) <= limite else texto[:limite] + f"… ({len(texto)} caracteres en total)"


@dataclass
class ApiResult:
    """Resultado de una peticion, exito o fallo, siempre con un mensaje legible."""
    ok: bool
    status: Optional[int]      # None = no hubo respuesta HTTP (red, timeout, URL invalida)
    data: Any
    codigo: Optional[str]      # codigo_error del servidor, o codigo propio del cliente
    mensaje: str
    metodo: str
    url: str
    duracion_ms: int
    cabeceras: Dict[str, str] = field(default_factory=dict)   # p. ej. X-Cache: HIT | MISS

    @property
    def sin_conexion(self) -> bool:
        return self.status is None

    @property
    def sesion_invalida(self) -> bool:
        """El servidor dijo que la sesion no sirve: hay que volver al login."""
        return self.status == 401


@dataclass
class RegistroPeticion:
    hora: datetime
    servicio: str
    metodo: str
    url: str
    status: Optional[int]
    ok: bool
    codigo: Optional[str]
    mensaje: str
    duracion_ms: int
    cuerpo_enviado: Optional[str]
    respuesta: Optional[str]
    autenticacion: str = '—'      # 'Bearer' si viajo el JWT, '—' si no


def _url_sin_secretos(url: str) -> str:
    """Enmascara parametros sensibles de la URL (p. ej. ?token=...)."""
    partes = urlsplit(url)
    consulta = [(k, '••••••' if k in CAMPOS_SENSIBLES else v) for k, v in parse_qsl(partes.query)]
    return urlunsplit(partes._replace(query=urlencode(consulta, safe='•')))


def _enmascarar(valor: Any) -> Any:
    if isinstance(valor, dict):
        return {k: ('••••••' if k in CAMPOS_SENSIBLES else _enmascarar(v)) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_enmascarar(v) for v in valor]
    return valor


class ApiClient:
    """Una sola sesion de `requests` para los 6 microservicios.

    - La cookie de sesion del login la conserva `self.session`: la usan
      /session y /session/extend del servicio de login.
    - El JWT lo conserva `self.token` y se envia como "Authorization: Bearer"
      solo donde `requiere_jwt` lo indica (nunca a rutas publicas).
    """

    def __init__(self, obtener_config: Callable[[], AppConfig]):
        self._obtener_config = obtener_config
        self.session = requests.Session()
        self.session.headers['Accept'] = 'application/json'
        self.token: Optional[str] = None
        self._historial: deque = deque(maxlen=200)
        self._lock = threading.Lock()
        self._oyentes: List[Callable[[RegistroPeticion], None]] = []

    # ------------------------------------------------------------------
    def url_base(self, servicio: str) -> str:
        return self._obtener_config().url(servicio)

    def _verificar_tls(self):
        """HTTPS de la instancia con certificado autofirmado: se confia en su CA."""
        ca = self._obtener_config().certificado_ca
        return ca if ca else True

    def construir_url(self, servicio: str, ruta: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Une la direccion configurada con la ruta del endpoint sin duplicar
        ni perder la '/', y agrega siempre ?format=json."""
        base = self.url_base(servicio).rstrip('/')
        consulta = {'format': 'json', **{k: v for k, v in (params or {}).items() if v not in (None, '')}}
        return f"{base}/{ruta.lstrip('/')}?{urlencode(consulta)}"

    # ------------------------------------------------------------------
    @staticmethod
    def requiere_jwt(servicio: str, metodo: str, ruta: str = '') -> bool:
        ruta = '/' + ruta.split('?')[0].strip('/')
        if ruta in RUTAS_PUBLICAS:
            return False
        if servicio == 'login':
            return ruta in RUTAS_LOGIN_CON_JWT
        if servicio in LECTURA_PUBLICA:
            return metodo.upper() in METODOS_PROTEGIDOS
        return True

    def request(
        self,
        servicio: str,
        metodo: str,
        ruta: str,
        json_body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        con_cookies: bool = True,
        registrar: bool = True,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> ApiResult:
        nombre = NOMBRES_SERVICIO.get(servicio, servicio)
        base = self.url_base(servicio)
        url = self.construir_url(servicio, ruta, params)
        timeout = self._obtener_config().timeout_segundos

        headers = {'Accept': 'application/json', **(extra_headers or {})}
        if json_body is not None:
            headers['Content-Type'] = 'application/json'
        usa_jwt = self.requiere_jwt(servicio, metodo, ruta)
        if usa_jwt and self.token:
            headers['Authorization'] = f"Bearer {self.token}"
        # Las comprobaciones periodicas de /health (registrar=False) van a
        # nivel DEBUG para no llenar la consola cada 15 segundos.
        nivel = logging.INFO if registrar else logging.DEBUG
        self._log_peticion(nivel, nombre, metodo, url, headers, usa_jwt, json_body)

        inicio = time.monotonic()
        try:
            verificar = self._verificar_tls()
            if con_cookies:
                respuesta = self.session.request(metodo, url, json=json_body, timeout=timeout, headers=headers,
                                                 verify=verificar)
            else:
                # /health no necesita la cookie de sesion: no se envia.
                respuesta = requests.request(metodo, url, json=json_body, timeout=timeout, headers=headers,
                                             verify=verificar)
        except requests.exceptions.SSLError:
            resultado = self._fallo(metodo, url, inicio, 'TLS_INVALIDO',
                                    f"El certificado HTTPS de {base} no es de confianza. Configura el certificado "
                                    "de la instancia en Configuración.")
        except requests.exceptions.Timeout:
            resultado = self._fallo(metodo, url, inicio, 'TIEMPO_AGOTADO',
                                    f"El servicio de {nombre} no respondió en {timeout:g} segundos.")
        except (requests.exceptions.InvalidURL, requests.exceptions.MissingSchema,
                requests.exceptions.InvalidSchema):
            resultado = self._fallo(metodo, url, inicio, 'URL_INVALIDA',
                                    f"La dirección configurada para el servicio de {nombre} no es válida: {base}")
        except requests.exceptions.ConnectionError:
            resultado = self._fallo(
                metodo, url, inicio, 'SIN_CONEXION',
                f"No se pudo conectar con el servicio de {nombre} en {base}. "
                "Verifica que esté encendido y que la dirección y el puerto sean correctos.",
            )
        except requests.exceptions.RequestException as exc:
            resultado = self._fallo(metodo, url, inicio, 'ERROR_RED',
                                    f"Error de comunicación con el servicio de {nombre}: {exc.__class__.__name__}.")
        else:
            resultado = self._interpretar(respuesta, metodo, url, inicio, nombre, base)

        self._log_respuesta(nivel, resultado)
        if registrar:
            self._registrar(servicio, json_body, resultado, 'Bearer' if 'Authorization' in headers else '—')
        return resultado

    # ------------------------------------------------------------------
    # Logs en consola
    # ------------------------------------------------------------------
    def _log_peticion(self, nivel: int, nombre: str, metodo: str, url: str, headers: Dict[str, str],
                      usa_jwt: bool, cuerpo: Optional[Dict[str, Any]]) -> None:
        if not logger.isEnabledFor(nivel):
            return
        visibles = [f"Accept: {headers['Accept']}"]
        if 'Content-Type' in headers:
            visibles.append(f"Content-Type: {headers['Content-Type']}")
        if 'Authorization' in headers:
            visibles.append(f"Authorization: Bearer {descripcion_token(self.token)}")

        if not usa_jwt:
            auth = 'no requerida (operacion publica / servicio de login): se envia SIN Authorization'
        elif self.token:
            auth = 'REQUERIDA (JWT) -> se envia el Bearer token recibido en el login'
        else:
            auth = 'REQUERIDA (JWT), pero NO hay token: se envia sin Authorization (el servidor respondera 401)'

        lineas = [
            f"--> {metodo} {_url_sin_secretos(url)}   [servicio de {nombre}]",
            f"    Headers: {' | '.join(visibles)}",
            f"    Autenticacion: {auth}",
        ]
        if cuerpo is not None:
            enviado = json.dumps(_enmascarar(copy.deepcopy(cuerpo)), ensure_ascii=False)
            lineas.append(f"    Datos enviados: {_recortar(enviado, 800)}")
        logger.log(nivel, '\n'.join(lineas))

    def _log_respuesta(self, nivel: int, r: ApiResult) -> None:
        if not logger.isEnabledFor(nivel):
            return
        if r.status is None:
            logger.log(nivel, f"<-- SIN RESPUESTA ({r.codigo}) en {r.duracion_ms} ms: {r.mensaje}")
            return
        resultado = 'EXITO' if r.ok else f"ERROR {r.codigo or ''}".strip()
        cache = f" | X-Cache: {r.cabeceras['X-Cache']}" if r.cabeceras.get('X-Cache') else ''
        lineas = [f"<-- HTTP {r.status} en {r.duracion_ms} ms | {resultado}{cache} | {r.mensaje}"]
        if r.data is not None:
            recibido = json.dumps(_enmascarar(r.data), ensure_ascii=False)
            lineas.append(f"    Respuesta: {_recortar(recibido, 400)}")
        logger.log(nivel, '\n'.join(lineas))

    # ------------------------------------------------------------------
    def _fallo(self, metodo: str, url: str, inicio: float, codigo: str, mensaje: str) -> ApiResult:
        return ApiResult(
            ok=False, status=None, data=None, codigo=codigo, mensaje=mensaje,
            metodo=metodo, url=url, duracion_ms=int((time.monotonic() - inicio) * 1000),
        )

    def _interpretar(self, respuesta: requests.Response, metodo: str, url: str,
                     inicio: float, nombre: str, base: str) -> ApiResult:
        duracion = int((time.monotonic() - inicio) * 1000)
        try:
            datos = respuesta.json()
        except ValueError:
            # Algo respondio en esa direccion, pero no es el microservicio:
            # tipicamente un puerto equivocado que apunta a otro programa.
            return ApiResult(
                ok=False, status=respuesta.status_code, data=None, codigo='RESPUESTA_INVALIDA',
                mensaje=(f"La dirección {base} respondió (HTTP {respuesta.status_code}), pero no como el "
                         f"servicio de {nombre}. Revisa que el puerto sea el correcto."),
                metodo=metodo, url=url, duracion_ms=duracion,
            )

        cabeceras = {k: v for k, v in respuesta.headers.items() if k.lower() in ('x-cache', 'location', 'www-authenticate')}
        exito = 200 <= respuesta.status_code < 300
        if exito:
            mensaje = (datos.get('mensaje') if isinstance(datos, dict) else None) or 'Operación correcta.'
            return ApiResult(True, respuesta.status_code, datos, None, mensaje, metodo, url, duracion, cabeceras)

        codigo = datos.get('codigo_error') if isinstance(datos, dict) else None
        mensaje = (datos.get('mensaje') if isinstance(datos, dict) else None) or \
            f"El servicio de {nombre} respondió con el código HTTP {respuesta.status_code}."
        return ApiResult(False, respuesta.status_code, datos, codigo, mensaje, metodo, url, duracion, cabeceras)

    # ------------------------------------------------------------------
    # Registro de peticiones
    # ------------------------------------------------------------------
    def _registrar(self, servicio: str, cuerpo: Optional[Dict[str, Any]], r: ApiResult,
                   autenticacion: str = '—') -> None:
        cuerpo_txt = json.dumps(_enmascarar(copy.deepcopy(cuerpo)), ensure_ascii=False, indent=2) if cuerpo else None
        respuesta_txt = None
        if r.data is not None:
            respuesta_txt = json.dumps(_enmascarar(r.data), ensure_ascii=False, indent=2)
            if len(respuesta_txt) > 6000:
                respuesta_txt = respuesta_txt[:6000] + '\n... (respuesta recortada)'

        registro = RegistroPeticion(
            hora=datetime.now(), servicio=servicio, metodo=r.metodo, url=_url_sin_secretos(r.url),
            status=r.status, ok=r.ok, codigo=r.codigo, mensaje=r.mensaje,
            duracion_ms=r.duracion_ms, cuerpo_enviado=cuerpo_txt, respuesta=respuesta_txt,
            autenticacion=autenticacion,
        )
        with self._lock:
            self._historial.append(registro)
            oyentes = list(self._oyentes)
        for oyente in oyentes:
            oyente(registro)

    def historial(self) -> List[RegistroPeticion]:
        with self._lock:
            return list(self._historial)

    def al_registrar(self, oyente: Callable[[RegistroPeticion], None]) -> None:
        with self._lock:
            self._oyentes.append(oyente)

    def quitar_oyente(self, oyente: Callable[[RegistroPeticion], None]) -> None:
        with self._lock:
            if oyente in self._oyentes:
                self._oyentes.remove(oyente)
