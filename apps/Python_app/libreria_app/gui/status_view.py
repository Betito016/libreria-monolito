"""Estado de los microservicios: semaforo, detalles y ultima comprobacion."""
import tkinter as tk
from tkinter import ttk

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
        self.subtitulo.pack(anchor='w', pady=(0, 12))

        tarjetas = ttk.Frame(self)
        tarjetas.pack(fill='x')
        self.tarjetas = {}
        for servicio, nombre in (('login', 'Microservicio de Login'), ('books', 'Microservicio de Libros')):
            marco = tk.Frame(tarjetas, bg=SUP, padx=20, pady=18, highlightbackground=COLOR['borde'],
                             highlightthickness=1)
            marco.pack(side='left', fill='both', expand=True, padx=(0, 12))

            encabezado = tk.Frame(marco, bg=SUP)
            encabezado.pack(fill='x')
            luz = Semaforo(encabezado, 52, fondo=SUP)
            luz.pack(side='left', padx=(0, 14))
            titulos = tk.Frame(encabezado, bg=SUP)
            titulos.pack(side='left', fill='x')
            tk.Label(titulos, text=nombre, bg=SUP, font=(theme.FUENTE, 13, 'bold')).pack(anchor='w')
            nivel = tk.Label(titulos, text='Sin comprobar', bg=SUP, font=(theme.FUENTE, 11, 'bold'))
            nivel.pack(anchor='w')
            url = tk.Label(titulos, text='', bg=SUP, fg=COLOR['texto_suave'])
            url.pack(anchor='w')

            resumen = tk.Label(marco, text='', bg=SUP, anchor='w', justify='left', wraplength=440)
            resumen.pack(fill='x', pady=(12, 4))
            detalles = tk.Label(marco, text='', bg=SUP, fg=COLOR['texto_suave'], anchor='w', justify='left')
            detalles.pack(fill='x')
            tiempos = tk.Label(marco, text='', bg=SUP, fg=COLOR['texto_suave'], anchor='w')
            tiempos.pack(fill='x', pady=(10, 0))
            self.tarjetas[servicio] = dict(luz=luz, nivel=nivel, url=url, resumen=resumen,
                                           detalles=detalles, tiempos=tiempos)

        acciones = ttk.Frame(self)
        acciones.pack(fill='x', pady=16)
        self.boton = ttk.Button(acciones, text='↻ Comprobar ahora', style='Primario.TButton',
                                command=self._comprobar)
        self.boton.pack(side='left')

        leyenda = ttk.LabelFrame(self, text='Significado de los colores', padding=12)
        leyenda.pack(fill='x')
        for nivel, texto in (
                ('verde', 'Funcionando: responde y tiene acceso a su base de datos (y libros, al login).'),
                ('amarillo', 'Degradado: responde, pero alguna dependencia (su base de datos o el login) '
                             'no está disponible.'),
                ('rojo', 'Inaccesible: no hubo respuesta, se agotó el tiempo o la dirección es incorrecta.')):
            fila = tk.Frame(leyenda, bg=SUP)
            fila.pack(fill='x', pady=2)
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
            t['tiempos'].configure(
                text=f"{http} · {e.duracion_ms} ms · última comprobación: "
                     f"{e.comprobado_en.strftime('%d/%m/%Y %H:%M:%S')}")
