"""
Ventana principal: arma los servicios, decide que pantalla mostrar y
coordina lo que es de TODA la aplicacion:

  - Arranque: valida con el servidor la sesion guardada (GET /session).
  - Monitoreo de salud: GET /health a ambos servicios cada N segundos.
  - Reloj de sesion: cuenta regresiva, aviso antes de expirar y cierre
    controlado cuando el servidor confirma que la sesion ya no es valida.
  - Manejo central del 401: venga de donde venga, un "sesion invalida"
    regresa a la pantalla de login con un mensaje, sin cerrar la app.
  - Errores inesperados: se muestran en un dialogo y se guardan en un
    archivo, en lugar de un traceback en la consola.
"""
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
from libreria_app.services.books_service import BooksService
from libreria_app.services.health_service import EstadoServicio
from libreria_app.services.session_store import SessionStore

RUTA_ERRORES = directorio_datos() / 'errores.log'

# Motivo del 401 segun el codigo de error de los microservicios
TEXTO_SESION = {
    'ERR_SESION_EXPIRADA': 'Tu sesión expiró',
    'ERR_SESION_INVALIDA': 'El servidor ya no reconoce tu sesión',
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
        self.runner = BackgroundRunner(self)
        self.imagenes = ImagenesRemotas(self.runner)

        self.estado_servicios: Dict[str, EstadoServicio] = {}
        self._oyentes_salud: List[Callable[[Dict[str, EstadoServicio]], None]] = []
        self._salud_en_curso = False
        self._trabajo_salud: Optional[str] = None
        self._trabajo_reloj: Optional[str] = None
        self._aviso_expiracion = None
        self._aviso_descartado = False

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
        ttk.Label(cuadro, text='Validando la sesión guardada con el servidor…',
                  style='Suave.TLabel').pack()
        self._cambiar_vista(cuadro)
        self.runner.run(self.auth.restaurar_sesion, al_terminar=self._arranque_listo)

    def _arranque_listo(self, r) -> None:
        if isinstance(r, Exception):
            self.mostrar_login('No se pudo validar la sesión guardada.', 'error')
        elif r is None:
            self.mostrar_login()
        elif r.ok and r.data.get('autenticado'):
            self.mostrar_panel()
        elif r.ok:
            motivo = r.data.get('motivo')
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
            self.mostrar_login('Sesión cerrada.', 'exito')
        self.runner.run(self.auth.cerrar_sesion, al_terminar=listo)

    # ==================================================================
    # Monitoreo de salud (GET /health a ambos servicios)
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

        def comprobar_ambos():
            return {s: health_service.comprobar(self.api, s, registrar=manual) for s in ('login', 'books')}

        def listo(estados):
            self._salud_en_curso = False
            if isinstance(estados, dict):
                self.estado_servicios = estados
                for oyente in list(self._oyentes_salud):
                    oyente(estados)
            intervalo = int(self.config_app.intervalo_salud_segundos) * 1000
            self._trabajo_salud = self.after(intervalo, self.comprobar_salud)

        self.runner.run(comprobar_ambos, al_terminar=listo)

    # ==================================================================
    # Reloj de sesion
    # ==================================================================
    def _iniciar_reloj(self) -> None:
        self._detener_reloj()
        self._aviso_descartado = False
        self._tic()

    def _detener_reloj(self) -> None:
        if self._trabajo_reloj:
            self.after_cancel(self._trabajo_reloj)
            self._trabajo_reloj = None
        self._cerrar_aviso()

    def _tic(self) -> None:
        sesion = self.auth.sesion
        if sesion is None:
            return
        restantes = sesion.segundos_restantes()

        if restantes <= 0:
            # El reloj local dice que vencio: se confirma con el servidor
            # antes de sacar al usuario (el servidor es la autoridad).
            self._trabajo_reloj = None
            self.runner.run(self.auth.consultar_sesion, al_terminar=self._confirmar_expiracion)
            return

        por_expirar = restantes <= int(self.config_app.aviso_expiracion_segundos)
        if por_expirar and not self._aviso_descartado:
            self._mostrar_aviso()
        if self._aviso_expiracion is not None:
            self._aviso_expiracion.actualizar(restantes)
        if hasattr(self.vista, 'actualizar_reloj'):
            self.vista.actualizar_reloj(restantes, por_expirar)

        self._trabajo_reloj = self.after(1000, self._tic)

    def _confirmar_expiracion(self, r) -> None:
        if isinstance(r, ApiResult) and r.ok and r.data.get('autenticado'):
            self._iniciar_reloj()   # el servidor la extendio o el reloj local se adelanto
        elif isinstance(r, ApiResult) and r.ok:
            self.sesion_terminada('Tu sesión expiró.')
        else:
            # Sin respuesta del servidor: por seguridad se cierra la sesion local.
            self.sesion_terminada('Tu sesión expiró y no se pudo confirmar con el servidor.')

    def _mostrar_aviso(self) -> None:
        if self._aviso_expiracion is None:
            from libreria_app.gui.dialogs import AvisoExpiracion
            self._aviso_expiracion = AvisoExpiracion(self, al_extender=self.extender_sesion,
                                                     al_descartar=self._descartar_aviso)

    def _descartar_aviso(self) -> None:
        """El usuario cerro el aviso sin extender: no se vuelve a abrir en
        esta sesion (la barra superior sigue mostrando la cuenta en rojo)."""
        self._aviso_descartado = True
        self._cerrar_aviso()

    def _cerrar_aviso(self) -> None:
        if self._aviso_expiracion is not None:
            self._aviso_expiracion.destroy()
            self._aviso_expiracion = None

    def extender_sesion(self, al_terminar: Optional[Callable[[ApiResult], None]] = None) -> None:
        def listo(r):
            if self.verificar_sesion(r):
                return
            if isinstance(r, ApiResult) and r.ok:
                self._cerrar_aviso()
                self._iniciar_reloj()
            if al_terminar:
                al_terminar(r)
        self.runner.run(self.auth.extender_sesion, al_terminar=listo)

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
