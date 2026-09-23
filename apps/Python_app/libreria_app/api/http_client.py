"""
Comunicacion HTTP con los microservicios.

Es el UNICO lugar de la aplicacion que habla con la red. Todo lo demas
(servicios, pantallas) recibe un `ApiResult` y nunca una excepcion de
`requests`: una caida de red, un timeout, un puerto equivocado o un error
del servidor se convierten aqui en un resultado con un mensaje comprensible.

Tambien lleva un registro de las ultimas peticiones (metodo, URL, codigo
HTTP, cuerpo enviado) que la interfaz muestra en "Registro HTTP". Las
contrasenas y tokens se enmascaran antes de guardarse en ese registro.
"""
import copy
import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from libreria_app.config.settings import AppConfig

NOMBRES_SERVICIO = {'login': 'login', 'books': 'libros'}
CAMPOS_SENSIBLES = {'password', 'password_actual', 'token'}


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
    """Una sola sesion de `requests` para ambos servicios.

    La sesion conserva la cookie que emite el login y la reenvia
    automaticamente en cada peticion, incluidas las del servicio de libros:
    las cookies se asocian al host, no al puerto, asi que la misma cookie
    viaja a login (5000) y a libros (5001) cuando ambos estan en el mismo
    servidor. Libros la reenvia a login para saber quien esta escribiendo.
    """

    def __init__(self, obtener_config: Callable[[], AppConfig]):
        self._obtener_config = obtener_config
        self.session = requests.Session()
        self.session.headers['Accept'] = 'application/json'
        self._historial: deque = deque(maxlen=200)
        self._lock = threading.Lock()
        self._oyentes: List[Callable[[RegistroPeticion], None]] = []

    # ------------------------------------------------------------------
    def url_base(self, servicio: str) -> str:
        config = self._obtener_config()
        return config.login_url if servicio == 'login' else config.books_url

    def construir_url(self, servicio: str, ruta: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Une la direccion configurada con la ruta del endpoint sin duplicar
        ni perder la '/', y agrega siempre ?format=json."""
        base = self.url_base(servicio).rstrip('/')
        consulta = {'format': 'json', **{k: v for k, v in (params or {}).items() if v not in (None, '')}}
        return f"{base}/{ruta.lstrip('/')}?{urlencode(consulta)}"

    # ------------------------------------------------------------------
    def request(
        self,
        servicio: str,
        metodo: str,
        ruta: str,
        json_body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        con_cookies: bool = True,
        registrar: bool = True,
    ) -> ApiResult:
        nombre = NOMBRES_SERVICIO.get(servicio, servicio)
        base = self.url_base(servicio)
        url = self.construir_url(servicio, ruta, params)
        timeout = self._obtener_config().timeout_segundos
        inicio = time.monotonic()

        try:
            if con_cookies:
                respuesta = self.session.request(metodo, url, json=json_body, timeout=timeout)
            else:
                # /health no necesita la cookie de sesion: no se envia.
                respuesta = requests.request(
                    metodo, url, json=json_body, timeout=timeout, headers={'Accept': 'application/json'}
                )
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

        if registrar:
            self._registrar(servicio, json_body, resultado)
        return resultado

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

        exito = 200 <= respuesta.status_code < 300
        if exito:
            mensaje = (datos.get('mensaje') if isinstance(datos, dict) else None) or 'Operación correcta.'
            return ApiResult(True, respuesta.status_code, datos, None, mensaje, metodo, url, duracion)

        codigo = datos.get('codigo_error') if isinstance(datos, dict) else None
        mensaje = (datos.get('mensaje') if isinstance(datos, dict) else None) or \
            f"El servicio de {nombre} respondió con el código HTTP {respuesta.status_code}."
        return ApiResult(False, respuesta.status_code, datos, codigo, mensaje, metodo, url, duracion)

    # ------------------------------------------------------------------
    # Registro de peticiones
    # ------------------------------------------------------------------
    def _registrar(self, servicio: str, cuerpo: Optional[Dict[str, Any]], r: ApiResult) -> None:
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
