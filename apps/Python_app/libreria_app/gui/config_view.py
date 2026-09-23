"""
Configuracion del servidor: modificar, probar, guardar y restaurar.

Cambiar entre servicios locales y la instancia remota se hace AQUI, no en
el codigo: el mismo programa sirve para ambos escenarios.
"""
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from libreria_app.api.http_client import ApiClient
from libreria_app.config.settings import RUTA_CONFIG, AppConfig
from libreria_app.gui.theme import COLOR, TEXTO_NIVEL
from libreria_app.gui.widgets import Mensaje, Semaforo
from libreria_app.services import health_service
from libreria_app.services.session_store import SessionStore

SUP = COLOR['superficie']

CAMPOS = (
    ('login_url', 'URL del microservicio de login', 'ej. http://127.0.0.1:5000'),
    ('books_url', 'URL del microservicio de libros', 'ej. http://127.0.0.1:5001'),
    ('timeout_segundos', 'Tiempo máximo de espera (s)', '1 a 60'),
    ('intervalo_salud_segundos', 'Comprobar estado cada (s)', '5 a 3600'),
    ('aviso_expiracion_segundos', 'Avisar antes de expirar (s)', '10 a 3600'),
)


class ConfigView(ttk.Frame):

    def __init__(self, parent, app, al_guardar: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.app = app
        self.al_guardar = al_guardar

        ttk.Label(self, text='Configuración del servidor', style='Titulo.TLabel').pack(anchor='w')
        ttk.Label(self, text='Direcciones de los microservicios · se guardan fuera del código fuente',
                  style='Suave.TLabel').pack(anchor='w', pady=(0, 10))

        marco = ttk.LabelFrame(self, text='Conexión', padding=16)
        marco.pack(fill='x')
        marco.columnconfigure(1, weight=1)
        self.entradas = {}
        for fila, (clave, etiqueta, ayuda) in enumerate(CAMPOS):
            tk.Label(marco, text=etiqueta, bg=SUP, anchor='w').grid(row=fila, column=0, sticky='w', pady=4, padx=(0, 12))
            entrada = ttk.Entry(marco, width=40)
            entrada.grid(row=fila, column=1, sticky='we', pady=4)
            tk.Label(marco, text=ayuda, bg=SUP, fg=COLOR['texto_suave']).grid(row=fila, column=2, sticky='w', padx=10)
            self.entradas[clave] = entrada

        botones = tk.Frame(marco, bg=SUP)
        botones.grid(row=len(CAMPOS), column=0, columnspan=3, sticky='w', pady=(14, 0))
        ttk.Button(botones, text='Probar conexión', command=self._probar).pack(side='left')
        ttk.Button(botones, text='Guardar', style='Primario.TButton', command=self._guardar).pack(side='left', padx=8)
        ttk.Button(botones, text='Restaurar predeterminados', command=self._restaurar).pack(side='left')

        self.mensaje = Mensaje(marco, fondo=SUP, ancho=640)
        self.mensaje.grid(row=len(CAMPOS) + 1, column=0, columnspan=3, sticky='w', pady=(10, 0))

        # --- Resultado de la prueba ---
        prueba = ttk.LabelFrame(self, text='Resultado de la prueba', padding=14)
        prueba.pack(fill='x', pady=(12, 0))
        self.resultados = {}
        for servicio, nombre in (('login', 'Login'), ('books', 'Libros')):
            fila = tk.Frame(prueba, bg=SUP)
            fila.pack(fill='x', pady=3)
            luz = Semaforo(fila, 14, fondo=SUP)
            luz.pack(side='left', padx=(0, 8))
            texto = tk.Label(fila, text=f"{nombre}: sin probar", bg=SUP, anchor='w', justify='left', wraplength=700)
            texto.pack(side='left', fill='x')
            self.resultados[servicio] = (nombre, luz, texto)

        # --- Donde se guarda ---
        ubicacion = ttk.LabelFrame(self, text='Dónde se conserva la información local', padding=14)
        ubicacion.pack(fill='x', pady=(12, 0))
        tk.Label(ubicacion, text=f"Configuración:  {RUTA_CONFIG}", bg=SUP, anchor='w').pack(fill='x')
        tk.Label(ubicacion, text=f"Sesión (cookie, nunca la contraseña):  {SessionStore.ruta()}",
                 bg=SUP, anchor='w').pack(fill='x')

        self._llenar(app.config_app)

    # ------------------------------------------------------------------
    def al_mostrar(self) -> None:
        self._llenar(self.app.config_app)

    def _llenar(self, config: AppConfig) -> None:
        for clave, entrada in self.entradas.items():
            entrada.delete(0, 'end')
            entrada.insert(0, str(getattr(config, clave)))

    def _leer(self) -> Optional[AppConfig]:
        texto = {k: e.get().strip() for k, e in self.entradas.items()}
        try:
            config = AppConfig(
                login_url=texto['login_url'], books_url=texto['books_url'],
                timeout_segundos=float(texto['timeout_segundos']),
                intervalo_salud_segundos=int(texto['intervalo_salud_segundos']),
                aviso_expiracion_segundos=int(texto['aviso_expiracion_segundos']),
            ).normalizada()
        except ValueError:
            self.mensaje.mostrar('Los tiempos deben ser números (los intervalos, enteros).', 'aviso')
            return None
        errores = config.validar()
        if errores:
            self.mensaje.mostrar('\n'.join(errores), 'error')
            return None
        return config

    def _probar(self) -> None:
        """Prueba las direcciones ESCRITAS (aunque todavia no se guarden)."""
        config = self._leer()
        if config is None:
            return
        self._llenar(config)   # muestra como quedo la URL normalizada
        self.mensaje.mostrar('Probando GET /health en ambas direcciones…')
        for nombre, luz, texto in self.resultados.values():
            luz.fijar(None)
            texto.configure(text=f"{nombre}: probando…")

        cliente = ApiClient(lambda: config)

        def probar():
            return {s: health_service.comprobar(cliente, s) for s in ('login', 'books')}

        def listo(estados):
            if not isinstance(estados, dict):
                self.mensaje.mostrar(f"Error inesperado: {estados}", 'error')
                return
            for servicio, e in estados.items():
                nombre, luz, texto = self.resultados[servicio]
                luz.fijar(e.nivel)
                texto.configure(text=f"{nombre} ({e.url}): {TEXTO_NIVEL[e.nivel]} — {e.resumen}")
            todos_ok = all(e.nivel == 'verde' for e in estados.values())
            self.mensaje.mostrar('Ambos servicios respondieron correctamente.' if todos_ok
                                 else 'Revisa los servicios marcados antes de guardar.',
                                 'exito' if todos_ok else 'aviso')
        self.app.runner.run(probar, al_terminar=listo)

    def _guardar(self) -> None:
        config = self._leer()
        if config is None:
            return
        self._llenar(config)
        self.app.aplicar_configuracion(config)
        self.mensaje.mostrar(f"Configuración guardada en {RUTA_CONFIG}", 'exito')
        if self.al_guardar:
            self.al_guardar()

    def _restaurar(self) -> None:
        self._llenar(AppConfig.predeterminada())
        self.mensaje.mostrar('Valores predeterminados cargados en el formulario. Presiona «Guardar» para '
                             'aplicarlos.', 'aviso')
