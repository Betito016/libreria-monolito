"""
Autenticacion, sesion y perfil: todo lo que se habla con el microservicio
de login.

    Operacion en la app           Endpoint
    --------------------------    ----------------------
    Registrarse                   POST  /register
    Verificar correo              GET   /verify?token=...
    Iniciar sesion                POST  /login           -> JWT (20 min) + refresh token
    Renovar el JWT                POST  /token/refresh   (rotacion: llega un refresh nuevo)
    Cerrar sesion                 POST  /logout          (Bearer + refresh: el servidor revoca ambos)
    Validar sesion / ver perfil   GET   /session
    Modificar el perfil           PATCH /profile         (Bearer)

JWT: `ApiClient.token` guarda el de acceso y lo agrega donde corresponde.
El refresh token solo lo usa este servicio para renovar antes de que el de
acceso expire (la app lo hace sola, ver gui/app.py). Al cerrar sesion se
olvidan ambos.
"""
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from libreria_app.api.http_client import ApiClient, ApiResult, descripcion_token
from libreria_app.config.settings import AppConfig
from libreria_app.services.session_store import SessionStore

logger = logging.getLogger('libreria.auth')
ROL_ADMINISTRADOR = 1


@dataclass
class EstadoSesion:
    usuario: Dict[str, Any]
    # Vencimiento del JWT de acceso medido con el reloj MONOTONICO local, a
    # partir de los segundos restantes que informa el servidor (no se compara
    # la hora absoluta contra el reloj de la PC).
    vence_monotonic: float
    duracion_minutos: int

    def segundos_restantes(self) -> int:
        return max(0, int(self.vence_monotonic - time.monotonic()))

    @property
    def role_id(self) -> int:
        return int(self.usuario.get('role_id') or (1 if self.usuario.get('rol') == 'administrador' else 2))

    @property
    def es_administrador(self) -> bool:
        return self.role_id == ROL_ADMINISTRADOR

    @property
    def user_id(self) -> str:
        return str(self.usuario.get('user_id') or self.usuario.get('id'))

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
        self.refresh_token: Optional[str] = None

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
            self.store.guardar(self._login_url(), self.api.session.cookies, self.sesion.usuario,
                               {'access': self.api.token, 'refresh': self.refresh_token})

    def _recibir_tokens(self, r: ApiResult, origen: str) -> None:
        """Toma el JWT y el refresh token de la respuesta de login/refresh."""
        bloque = r.data.get('token') if isinstance(r.data, dict) else None
        token = (bloque or {}).get('access_token')
        if not token:
            logger.warning(f"{origen}: la respuesta no trae JWT; las operaciones protegidas responderan 401.")
            return
        self.api.token = token
        self.refresh_token = bloque.get('refresh_token') or self.refresh_token
        logger.info(f"{origen}: JWT recibido {descripcion_token(token)} {bloque.get('algoritmo')} "
                    f"vence en {bloque.get('expires_in')} s; refresh token {descripcion_token(self.refresh_token)} "
                    f"(se renovara solo antes de expirar).")

    def descartar_sesion_local(self) -> None:
        """Olvida la sesion en este equipo (cookie, JWT y refresh, en memoria y en disco)."""
        if self.api.token:
            logger.info("Sesion local descartada: se olvidan el JWT, el refresh token y la cookie.")
        self.sesion = None
        self.api.token = None
        self.refresh_token = None
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
        self.api.token = self.refresh_token = None
        r = self.api.request('login', 'POST', '/login', json_body={'email': email.strip(), 'password': password})
        if r.ok:
            self._actualizar_sesion(r.data['usuario'], r.data.get('sesion', {}))
            self._recibir_tokens(r, 'Login')
            self._persistir()
        return r

    def renovar(self) -> ApiResult:
        """POST /token/refresh con el refresh token (o, si no lo hay, la cookie
        con /session/extend). El servidor rota el refresh y revoca el JWT anterior."""
        if self.refresh_token:
            r = self.api.request('login', 'POST', '/token/refresh', json_body={'refresh_token': self.refresh_token})
        else:
            r = self.api.request('login', 'POST', '/session/extend')
        if r.ok:
            self._actualizar_sesion(r.data.get('usuario') or (self.sesion.usuario if self.sesion else {}),
                                    r.data.get('sesion', {}))
            self._recibir_tokens(r, 'Renovacion')
            self._persistir()
        return r

    def cerrar_sesion(self) -> ApiResult:
        """Envia el Bearer y el refresh token para que el servidor revoque el
        JWT (jwt:revoked:<jti>) y borre la sesion; pase lo que pase, olvida
        la sesion local: el usuario pidio salir."""
        cuerpo = {'refresh_token': self.refresh_token} if self.refresh_token else None
        r = self.api.request('login', 'POST', '/logout', json_body=cuerpo)
        tenia_token = self.api.token is not None
        self.descartar_sesion_local()
        logger.info(f"Logout: JWT {'revocado en el servidor y ' if r.ok else ''}"
                    f"{'eliminado' if tenia_token else '(no habia)'} de la aplicacion. ApiClient.token = {self.api.token}. "
                    f"Las siguientes peticiones iran SIN Authorization.")
        return r

    def restaurar_sesion(self) -> Optional[ApiResult]:
        """Al arrancar: carga la cookie y los tokens guardados y le pregunta al
        servidor si la sesion sigue vigente. Si el JWT guardado ya esta por
        expirar (o expiro con la app cerrada), lo renueva."""
        if self.store.restaurar(self._login_url(), self.api.session.cookies) is None:
            return None
        tokens = self.store.tokens(self._login_url())
        self.api.token, self.refresh_token = tokens.get('access'), tokens.get('refresh')
        r = self.consultar_sesion()
        if r.ok and r.data.get('autenticado') and self.sesion and \
                self.sesion.segundos_restantes() <= self._obtener_config().renovar_antes_segundos:
            logger.info("El JWT guardado esta por expirar o expiro: se renueva al arrancar.")
            renovado = self.renovar()
            if not renovado.ok:
                self.descartar_sesion_local()
                return renovado
        return r

    def consultar_sesion(self) -> ApiResult:
        r = self.api.request('login', 'GET', '/session')
        if r.ok and r.data.get('autenticado'):
            self._actualizar_sesion(r.data['usuario'], r.data.get('sesion', {}))
        elif r.ok:
            # El servidor respondio, y dijo que no hay sesion valida.
            self.descartar_sesion_local()
        return r

    # ------------------------------------------------------------------
    # Perfil
    # ------------------------------------------------------------------
    def actualizar_perfil(self, cambios: Dict[str, Any]) -> ApiResult:
        r = self.api.request('login', 'PATCH', '/profile', json_body=cambios)
        if r.ok and self.sesion:
            if r.data.get('sesiones_cerradas'):
                # Cambio de contrasena/correo: el servidor revoco todo.
                self.descartar_sesion_local()
            else:
                self.sesion.usuario = r.data['usuario']
                self._persistir()
        return r
