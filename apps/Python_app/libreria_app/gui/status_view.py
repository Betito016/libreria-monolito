"""Estado de los microservicios: semaforo, detalles y ultima comprobacion."""
import tkinter as tk
from tkinter import ttk

from libreria_app.config.settings import SERVICIOS
from libreria_app.gui import theme
from libreria_app.gui.theme import COLOR, TEXTO_NIVEL
from libreria_app.gui.widgets import Semaforo

SUP = COLOR['superficie']


class StatusView(ttk.Frame):

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        ttk.Label(self, text='Estado de los microservicios', style='Titulo.TLabel').pack(anchor='w')
        self.subtitulo = ttk.Label(self, text='', style='Suave.TLabel')
        self.subtitulo.pack(anchor='w', pady=(0, 8))

        tarjetas = ttk.Frame(self)
        tarjetas.pack(fill='x')
        self.tarjetas = {}
        for indice, (servicio, nombre, puerto) in enumerate(SERVICIOS):
            marco = tk.Frame(tarjetas, bg=SUP, padx=10, pady=6, highlightbackground=COLOR['borde'],
                             highlightthickness=1)
            marco.grid(row=indice // 3, column=indice % 3, sticky='nsew', padx=(0, 8), pady=(0, 8))
            tarjetas.columnconfigure(indice % 3, weight=1, uniform='tarjeta')

            encabezado = tk.Frame(marco, bg=SUP)
            encabezado.pack(fill='x')
            luz = Semaforo(encabezado, 28, fondo=SUP)
            luz.pack(side='left', padx=(0, 10))
            titulos = tk.Frame(encabezado, bg=SUP)
            titulos.pack(side='left', fill='x')
            tk.Label(titulos, text=f'{nombre} :{puerto}', bg=SUP, font=(theme.FUENTE, 11, 'bold')).pack(anchor='w')
            nivel = tk.Label(titulos, text='Sin comprobar', bg=SUP, font=(theme.FUENTE, 10, 'bold'))
            nivel.pack(anchor='w')
            url = tk.Label(titulos, text='', bg=SUP, fg=COLOR['texto_suave'], font=(theme.FUENTE, 8))
            url.pack(anchor='w')

            resumen = tk.Label(marco, text='', bg=SUP, anchor='w', justify='left', wraplength=300, font=(theme.FUENTE, 9))
            resumen.pack(fill='x', pady=(4, 1))
            detalles = tk.Label(marco, text='', bg=SUP, fg=COLOR['texto_suave'], anchor='w', justify='left',
                                font=(theme.FUENTE, 8))
            detalles.pack(fill='x')
            tiempos = tk.Label(marco, text='', bg=SUP, fg=COLOR['texto_suave'], anchor='w', font=(theme.FUENTE, 8))
            tiempos.pack(fill='x', pady=(2, 0))
            self.tarjetas[servicio] = dict(luz=luz, nivel=nivel, url=url, resumen=resumen,
                                           detalles=detalles, tiempos=tiempos)

        abajo = ttk.Frame(self)
        abajo.pack(fill='x', pady=(2, 0))
        self.boton = ttk.Button(abajo, text='↻ Comprobar ahora', style='Primario.TButton',
                                command=self._comprobar)
        self.boton.pack(side='left', anchor='n', padx=(0, 12))

        leyenda = ttk.LabelFrame(abajo, text='Significado de los colores', padding=6)
        leyenda.pack(side='left', fill='x', expand=True)
        for nivel, texto in (
                ('verde', 'Funcionando: responde y tiene acceso a PostgreSQL y a Redis.'),
                ('amarillo', 'Degradado: responde, pero Redis, su base de datos o el login no están disponibles '
                             '(las operaciones con token se rechazan por seguridad).'),
                ('rojo', 'Inaccesible: no hubo respuesta, se agotó el tiempo o la dirección es incorrecta.')):
            fila = tk.Frame(leyenda, bg=SUP)
            fila.pack(fill='x', pady=1)
            luz = Semaforo(fila, 14, fondo=SUP)
            luz.fijar(nivel)
            luz.pack(side='left', padx=(0, 8))
            tk.Label(fila, text=texto, bg=SUP, anchor='w').pack(side='left')

        app.al_cambiar_salud(self._actualizar)
        self.al_mostrar()

    def destroy(self):
        self.app.quitar_oyente_salud(self._actualizar)
        super().destroy()

    def al_mostrar(self) -> None:
        self.subtitulo.configure(
            text=f"GET /health · comprobación automática cada {self.app.config_app.intervalo_salud_segundos} s")

    def _comprobar(self) -> None:
        self.boton.state(['disabled'])
        for t in self.tarjetas.values():
            t['tiempos'].configure(text='Comprobando…')
        self.app.comprobar_salud(manual=True)

    def _actualizar(self, estados) -> None:
        self.boton.state(['!disabled'])
        for servicio, e in estados.items():
            t = self.tarjetas[servicio]
            t['luz'].fijar(e.nivel)
            t['nivel'].configure(text=TEXTO_NIVEL[e.nivel], fg=theme.COLOR_NIVEL[e.nivel])
            t['url'].configure(text=f"{e.url}/health")
            t['resumen'].configure(text=e.resumen)
            t['detalles'].configure(text='\n'.join(e.detalles))
            http = f"HTTP {e.status}" if e.status else 'sin respuesta HTTP'
            t['tiempos'].configure(text=f"{http} · {e.duracion_ms} ms · {e.comprobado_en.strftime('%H:%M:%S')}")
