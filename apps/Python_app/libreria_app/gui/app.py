"""
Ventana principal: arma los servicios, decide que pantalla mostrar y
coordina lo que es de TODA la aplicacion:

  - Arranque: valida con el servidor la sesion guardada (GET /session) y, si
    el JWT guardado esta por expirar, lo renueva.
  - Monitoreo de salud: GET /health a los 6 microservicios cada N segundos.
  - Reloj del JWT (20 min): cuando le quedan `renovar_antes_segundos`, la app
    lo renueva SOLA con el refresh token (POST /token/refresh). Si el
    servidor ya no acepta el refresh, regresa al login.
  - Manejo central del 401: venga de donde venga, un token invalido, expirado
    o revocado regresa a la pantalla de login con el motivo, sin cerrar la app.
  - Errores inesperados: se muestran en un dialogo y se guardan en un
    archivo, en lugar de un traceback en la consola.
"""
import logging
import time
import traceback
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Callable, Dict, List, Optional

from libreria_app.api.http_client import ApiClient, ApiResult
from libreria_app.config.settings import AppConfig, directorio_datos
from libreria_app.gui import theme
from libreria_app.gui.tasks import BackgroundRunner
from libreria_app.gui.widgets import ImagenesRemotas
from libreria_app.services import health_service
from libreria_app.services.auth_service import AuthService
from libreria_app.services.authors_service import AuthorsService
from libreria_app.services.books_service import BooksService
from libreria_app.services.health_service import EstadoServicio
from libreria_app.services.orders_service import OrdersService
from libreria_app.services.payments_service import PaymentsService
from libreria_app.services.session_store import SessionStore
from libreria_app.services.users_service import UsersService

RUTA_ERRORES = directorio_datos() / 'errores.log'
logger = logging.getLogger('libreria.app')

# Motivo del 401 segun el codigo de error de los microservicios
TEXTO_SESION = {
    'ERR_SESION_EXPIRADA': 'Tu sesión expiró',
    'ERR_SESION_INVALIDA': 'El servidor ya no reconoce tu sesión',
    'ERR_TOKEN_EXPIRADO': 'Tu token de acceso (JWT) expiró',
    'ERR_TOKEN_INVALIDO': 'Un microservicio rechazó tu token de acceso (JWT)',
    'ERR_TOKEN_AUSENTE': 'No hay un token de acceso (JWT) para esta operación',
    'ERR_TOKEN_REVOCADO': 'Tu token fue revocado (se cerró la sesión o cambiaron tus credenciales o tu rol)',
    'ERR_REFRESH_INVALIDO': 'Tu sesión ya no se puede renovar',
}


class LibreriaApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title('Librería en Línea · Cliente de microservicios')
        self.minsize(1000, 640)
        if self.winfo_screenwidth() < 1400 or self.winfo_screenheight() < 900:
            self.state('zoomed')   # en pantallas de laptop (p. ej. 1366x768) 1280x820 no cabe
        else:
            self.geometry('1280x820')
        theme.aplicar(self)

        self.config_app = AppConfig.cargar()
        self.api = ApiClient(lambda: self.config_app)
        self.auth = AuthService(self.api, SessionStore(), lambda: self.config_app)
        self.books = BooksService(self.api)
        self.users = UsersService(self.api)
        self.authors = AuthorsService(self.api)
        self.orders = OrdersService(self.api)
        self.payments = PaymentsService(self.api)
        self.runner = BackgroundRunner(self)
        self.imagenes = ImagenesRemotas(self.runner)

        self.estado_servicios: Dict[str, EstadoServicio] = {}
        self._oyentes_salud: List[Callable[[Dict[str, EstadoServicio]], None]] = []
        self._salud_en_curso = False
        self._trabajo_salud: Optional[str] = None
        self._trabajo_reloj: Optional[str] = None
        self._renovando = False
        self._reintentar_renovacion = 0.0

        self.vista: Optional[tk.Widget] = None
        self.report_callback_exception = self._error_inesperado
        self.protocol('WM_DELETE_WINDOW', self._cerrar)

        self._mostrar_arranque()
        self.comprobar_salud()

    # ==================================================================
    # Pantallas
    # ==================================================================
    def _cambiar_vista(self, nueva: tk.Widget) -> None:
        if self.vista is not None:
            self.vista.destroy()
        self.vista = nueva
        self.vista.pack(fill='both', expand=True)

    def _mostrar_arranque(self) -> None:
        cuadro = ttk.Frame(self)
        ttk.Label(cuadro, text='Librería en Línea', style='Titulo.TLabel').pack(pady=(260, 8))
        ttk.Label(cuadro, text='Validando la sesión guardada con el servidor…', style='Suave.TLabel').pack()
        self._cambiar_vista(cuadro)
        self.runner.run(self.auth.restaurar_sesion, al_terminar=self._arranque_listo)

    def _arranque_listo(self, r) -> None:
        if isinstance(r, Exception):
            self.mostrar_login('No se pudo validar la sesión guardada.', 'error')
        elif r is None:
            self.mostrar_login()
        elif r.ok and self.auth.sesion is not None:
            self.mostrar_panel()
        elif r.ok:
            motivo = r.data.get('motivo') if isinstance(r.data, dict) else None
            texto = ('Tu sesión guardada expiró. Inicia sesión de nuevo.' if motivo == 'expirada'
                     else 'La sesión guardada ya no es válida en el servidor. Inicia sesión de nuevo.')
            self.mostrar_login(texto, 'aviso')
        else:
            # No se pudo preguntar (servicio caido, URL mala): no se borra la
            # sesion guardada, puede seguir siendo valida cuando vuelva.
            self.mostrar_login(f"No se pudo validar tu sesión guardada: {r.mensaje}", 'error')

    def mostrar_login(self, mensaje: Optional[str] = None, tipo: str = 'info') -> None:
        from libreria_app.gui.login_view import LoginView
        self._detener_reloj()
        self._cambiar_vista(LoginView(self, mensaje, tipo))

    def mostrar_panel(self) -> None:
        from libreria_app.gui.dashboard_view import DashboardView
        self._cambiar_vista(DashboardView(self))
        self._iniciar_reloj()

    # ==================================================================
    # Manejo central de respuestas
    # ==================================================================
    def verificar_sesion(self, r: ApiResult) -> bool:
        """Llamar con cada resultado de una operacion que requiere sesion.
        Si el servidor respondio 401, lleva al login y devuelve True."""
        if isinstance(r, ApiResult) and r.sesion_invalida:
            motivo = TEXTO_SESION.get(r.codigo, 'Tu sesión ya no es válida')
            self.sesion_terminada(f"{motivo} (HTTP {r.status}).")
            return True
        return False

    def sesion_terminada(self, mensaje: str = 'Tu sesión expiró.') -> None:
        self.auth.descartar_sesion_local()
        self.mostrar_login(f"{mensaje} Inicia sesión de nuevo.", 'aviso')

    def cerrar_sesion(self) -> None:
        def listo(r):
            self.mostrar_login('Sesión cerrada: el servidor revocó tu token.' if getattr(r, 'ok', False)
                               else 'Sesión cerrada en este equipo.', 'exito')
        self.runner.run(self.auth.cerrar_sesion, al_terminar=listo)

    # ==================================================================
    # Monitoreo de salud (GET /health a los 6 microservicios)
    # ==================================================================
    def al_cambiar_salud(self, oyente: Callable[[Dict[str, EstadoServicio]], None]) -> None:
        self._oyentes_salud.append(oyente)
        if self.estado_servicios:
            oyente(self.estado_servicios)

    def quitar_oyente_salud(self, oyente) -> None:
        if oyente in self._oyentes_salud:
            self._oyentes_salud.remove(oyente)

    def comprobar_salud(self, manual: bool = False) -> None:
        """manual=True: la comprobacion aparece en el Registro HTTP. Las
        automaticas no, para no llenarlo con una entrada cada 15 segundos."""
        if self._trabajo_salud:
            self.after_cancel(self._trabajo_salud)
            self._trabajo_salud = None
        if self._salud_en_curso:
            return
        self._salud_en_curso = True

        def comprobar_todos():
            return {s: health_service.comprobar(self.api, s, registrar=manual) for s in health_service.CLAVES}

        def listo(estados):
            self._salud_en_curso = False
            if isinstance(estados, dict):
                self.estado_servicios = estados
                for oyente in list(self._oyentes_salud):
                    oyente(estados)
            intervalo = int(self.config_app.intervalo_salud_segundos) * 1000
            self._trabajo_salud = self.after(intervalo, self.comprobar_salud)

        self.runner.run(comprobar_todos, al_terminar=listo)

    # ==================================================================
    # Reloj del JWT y renovacion automatica
    # ==================================================================
    def _iniciar_reloj(self) -> None:
        self._detener_reloj()
        self._tic()

    def _detener_reloj(self) -> None:
        if self._trabajo_reloj:
            self.after_cancel(self._trabajo_reloj)
            self._trabajo_reloj = None

    def _tic(self) -> None:
        sesion = self.auth.sesion
        if sesion is None:
            return
        restantes = sesion.segundos_restantes()
        por_renovar = restantes <= int(self.config_app.renovar_antes_segundos)
        if por_renovar and not self._renovando and time.monotonic() >= self._reintentar_renovacion:
            logger.info(f"Al JWT le quedan {restantes} s: renovacion automatica con el refresh token")
            self.renovar_token()
        if hasattr(self.vista, 'actualizar_reloj'):
            self.vista.actualizar_reloj(restantes, por_renovar)
        self._trabajo_reloj = self.after(1000, self._tic)

    def renovar_token(self, al_terminar: Optional[Callable[[ApiResult], None]] = None) -> None:
        """POST /token/refresh. 401: la sesion no puede seguir -> login.
        Sin respuesta: se reintenta en 15 s mientras al token le quede vida."""
        self._renovando = True

        def listo(r):
            self._renovando = False
            if isinstance(r, ApiResult) and r.ok:
                self._reintentar_renovacion = 0.0
            elif isinstance(r, ApiResult) and r.status == 401:
                self.sesion_terminada(f"{TEXTO_SESION.get(r.codigo, 'No se pudo renovar tu sesión')} (HTTP 401).")
                return
            else:
                self._reintentar_renovacion = time.monotonic() + 15
                if self.auth.sesion and self.auth.sesion.segundos_restantes() <= 0:
                    self.sesion_terminada('Tu token expiró y no se pudo renovar (el servicio de login no respondió).')
                    return
            if al_terminar:
                al_terminar(r)
        self.runner.run(self.auth.renovar, al_terminar=listo)

    # ==================================================================
    # Configuracion
    # ==================================================================
    def aplicar_configuracion(self, nueva: AppConfig) -> None:
        """Guarda la configuracion y la aplica sin reiniciar la app."""
        servidor_anterior = self.config_app.login_url
        nueva.guardar()
        self.config_app = nueva
        self.comprobar_salud(manual=True)

        if nueva.login_url != servidor_anterior and self.auth.sesion is not None:
            # La sesion pertenece al servidor anterior: en el nuevo no existe.
            self.auth.sesion = None
            self.api.token = None
            self.auth.refresh_token = None
            self.api.session.cookies.clear()
            self.mostrar_login('Cambiaste de servidor de login: inicia sesión en el nuevo servidor.', 'aviso')

    # ==================================================================
    # Errores inesperados y cierre
    # ==================================================================
    def _error_inesperado(self, tipo, valor, tb) -> None:
        detalle = ''.join(traceback.format_exception(tipo, valor, tb))
        try:
            RUTA_ERRORES.parent.mkdir(parents=True, exist_ok=True)
            with open(RUTA_ERRORES, 'a', encoding='utf-8') as archivo:
                archivo.write(f"\n=== {datetime.now().isoformat(timespec='seconds')} ===\n{detalle}")
        except OSError:
            pass
        messagebox.showerror(
            'Error inesperado',
            f"Ocurrió un error inesperado en la aplicación:\n\n{valor}\n\n"
            f"La aplicación sigue funcionando. El detalle técnico se guardó en:\n{RUTA_ERRORES}",
            parent=self,
        )

    def _cerrar(self) -> None:
        self.runner.detener()
        self.destroy()


def main() -> None:
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)   # texto nitido en pantallas escaladas
    except Exception:
        pass
    LibreriaApp().mainloop()
