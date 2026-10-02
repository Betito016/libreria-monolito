"""
Autenticacion, sesion y perfil: todo lo que se habla con el microservicio
de login.

    Operacion en la app           Endpoint
    --------------------------    ----------------------
    Registrarse                   POST  /register
    Verificar correo              GET   /verify?token=...
    Iniciar sesion                POST  /login
    Cerrar sesion                 POST  /logout
    Validar sesion / ver perfil   GET   /session
    Extender la sesion            POST  /session/extend
    Modificar el perfil           PATCH /profile

JWT: POST /login (y POST /session/extend) devuelven `token.access_token`.
Este servicio lo entrega a `ApiClient.token`, que lo agrega como
"Authorization: Bearer <token>" en las escrituras al servicio de libros.
Al cerrar sesion se olvida.
"""
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from libreria_app.api.http_client import ApiClient, ApiResult, descripcion_token

logger = logging.getLogger('libreria.auth')
from libreria_app.config.settings import AppConfig
from libreria_app.services.session_store import SessionStore


@dataclass
class EstadoSesion:
    usuario: Dict[str, Any]
    # Vencimiento medido con el reloj MONOTONICO local, a partir de los
    # segundos restantes que informa el servidor. No se compara la hora
    # absoluta `expira_en` contra el reloj de la PC: si ambos relojes no
    # coinciden, el aviso de expiracion saldria antes o despues de tiempo.
    vence_monotonic: float
    duracion_minutos: int

    def segundos_restantes(self) -> int:
        return max(0, int(self.vence_monotonic - time.monotonic()))

    @property
    def es_administrador(self) -> bool:
        return self.usuario.get('rol') == 'administrador'

    @property
    def nombre_completo(self) -> str:
        partes = [self.usuario.get('nombre'), self.usuario.get('apellido_paterno'),
                  self.usuario.get('apellido_materno')]
        return ' '.join(p for p in partes if p)


class AuthService:

    def __init__(self, api: ApiClient, store: SessionStore, obtener_config: Callable[[], AppConfig]):
        self.api = api
        self.store = store
        self._obtener_config = obtener_config
        self.sesion: Optional[EstadoSesion] = None

    # ------------------------------------------------------------------
    def _login_url(self) -> str:
        return self._obtener_config().login_url

    def _actualizar_sesion(self, usuario: Dict[str, Any], info_sesion: Dict[str, Any]) -> None:
        self.sesion = EstadoSesion(
            usuario=usuario,
            vence_monotonic=time.monotonic() + int(info_sesion.get('segundos_restantes', 0)),
            duracion_minutos=int(info_sesion.get('duracion_minutos', 0)),
        )

    def _persistir(self) -> None:
        if self.sesion:
            self.store.guardar(self._login_url(), self.api.session.cookies, self.sesion.usuario, self.api.token)

    def _recibir_token(self, r: ApiResult, origen: str) -> None:
        """Toma el JWT de la respuesta y lo deja listo para las peticiones protegidas."""
        bloque = r.data.get('token') if isinstance(r.data, dict) else None
        token = (bloque or {}).get('access_token')
        if not token:
            logger.warning(f"{origen}: la respuesta no trae JWT; las escrituras responderan 401.")
            return
        self.api.token = token
        logger.info(f"{origen}: JWT recibido del servicio de login {descripcion_token(token)} "
                    f"tipo={bloque.get('token_type')} alg={bloque.get('algoritmo')} "
                    f"vence en {bloque.get('expires_in')} s. Se conserva en memoria para "
                    f"POST/PUT/PATCH/DELETE al servicio de libros.")

    def descartar_sesion_local(self) -> None:
        """Olvida la sesion en este equipo (cookie y JWT, en memoria y en disco)."""
        if self.api.token:
            logger.info("Sesion local descartada: se olvida el JWT y la cookie.")
        self.sesion = None
        self.api.token = None
        self.api.session.cookies.clear()
        self.store.borrar(self._login_url())

    # ------------------------------------------------------------------
    # Registro y verificacion
    # ------------------------------------------------------------------
    def registrar(self, datos: Dict[str, str]) -> ApiResult:
        return self.api.request('login', 'POST', '/register', json_body=datos)

    def verificar_correo(self, token: str) -> ApiResult:
        return self.api.request('login', 'GET', '/verify', params={'token': token.strip()})

    # ------------------------------------------------------------------
    # Sesion
    # ------------------------------------------------------------------
    def iniciar_sesion(self, email: str, password: str) -> ApiResult:
        self.api.session.cookies.clear()
        self.api.token = None
        r = self.api.request('login', 'POST', '/login',
                             json_body={'email': email.strip(), 'password': password})
        if r.ok:
            self._actualizar_sesion(r.data['usuario'], r.data.get('sesion', {}))
            self._recibir_token(r, 'Login')
            self._persistir()
        return r

    def cerrar_sesion(self) -> ApiResult:
        """Avisa al servidor y, pase lo que pase, olvida la sesion local:
        aunque el servidor no responda, el usuario pidio salir."""
        r = self.api.request('login', 'POST', '/logout')
        tenia_token = self.api.token is not None
        self.descartar_sesion_local()
        logger.info(f"Logout: JWT {'eliminado' if tenia_token else '(no habia)'} de la aplicacion "
                    f"(memoria y sesion.json). ApiClient.token = {self.api.token}. "
                    f"Las siguientes peticiones iran SIN Authorization.")
        return r

    def restaurar_sesion(self) -> Optional[ApiResult]:
        """Al arrancar: carga la cookie guardada y le pregunta al servidor si
        la sesion sigue vigente. None = no habia sesion guardada."""
        if self.store.restaurar(self._login_url(), self.api.session.cookies) is None:
            return None
        self.api.token = self.store.token(self._login_url())
        if self.api.token:
            logger.info(f"JWT restaurado de la sesion guardada {descripcion_token(self.api.token)}")
        return self.consultar_sesion()

    def consultar_sesion(self) -> ApiResult:
        r = self.api.request('login', 'GET', '/session')
        if r.ok and r.data.get('autenticado'):
            self._actualizar_sesion(r.data['usuario'], r.data.get('sesion', {}))
        elif r.ok:
            # El servidor respondio, y dijo que no hay sesion valida.
            self.descartar_sesion_local()
        return r

    def extender_sesion(self) -> ApiResult:
        r = self.api.request('login', 'POST', '/session/extend')
        if r.ok and self.sesion:
            self._actualizar_sesion(self.sesion.usuario, r.data.get('sesion', {}))
            # El servidor emitio una cookie y un JWT nuevos con el vencimiento nuevo.
            self._recibir_token(r, 'Sesion extendida')
            self._persistir()
        return r

    # ------------------------------------------------------------------
    # Perfil
    # ------------------------------------------------------------------
    def actualizar_perfil(self, cambios: Dict[str, Any]) -> ApiResult:
        r = self.api.request('login', 'PATCH', '/profile', json_body=cambios)
        if r.ok and self.sesion:
            self.sesion.usuario = r.data['usuario']
            self._persistir()
        return r
