"""
Registro HTTP: cada peticion que hizo la aplicacion, con su metodo, URL,
codigo de respuesta y el cuerpo enviado. Sirve para ver exactamente que se
mando al servidor (por ejemplo, la diferencia entre un PUT y un PATCH) y que
codigo HTTP devolvio. Contrasenas y tokens aparecen enmascarados.
"""
import tkinter as tk
from tkinter import ttk

from libreria_app.api.http_client import RegistroPeticion
from libreria_app.gui import theme
from libreria_app.gui.theme import COLOR

COLUMNAS = (('hora', 'Hora', 80), ('servicio', 'Servicio', 70), ('metodo', 'Método', 70),
            ('url', 'URL', 430), ('status', 'HTTP', 60), ('resultado', 'Resultado', 260), ('ms', 'ms', 60))


class HttpLogView(ttk.Frame):

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.registros = {}

        ttk.Label(self, text='Registro HTTP', style='Titulo.TLabel').pack(anchor='w')
        ttk.Label(self, text='Peticiones realizadas por esta aplicación · contraseñas y tokens enmascarados',
                  style='Suave.TLabel').pack(anchor='w', pady=(0, 10))

        tabla = ttk.Frame(self)
        tabla.pack(fill='both', expand=True)
        self.arbol = ttk.Treeview(tabla, columns=[c[0] for c in COLUMNAS], show='headings', height=12)
        for clave, titulo, ancho in COLUMNAS:
            self.arbol.heading(clave, text=titulo)
            self.arbol.column(clave, width=ancho, anchor='w', stretch=clave in ('url', 'resultado'))
        barra = ttk.Scrollbar(tabla, orient='vertical', command=self.arbol.yview)
        self.arbol.configure(yscrollcommand=barra.set)
        self.arbol.pack(side='left', fill='both', expand=True)
        barra.pack(side='right', fill='y')
        self.arbol.tag_configure('ok', foreground=COLOR['exito'])
        self.arbol.tag_configure('cliente', foreground=COLOR['aviso'])
        self.arbol.tag_configure('fallo', foreground=COLOR['error'])
        self.arbol.bind('<<TreeviewSelect>>', self._seleccion)

        detalle = ttk.Frame(self)
        detalle.pack(fill='both', expand=True, pady=(10, 0))
        self.enviado = self._panel(detalle, 'Cuerpo enviado')
        self.recibido = self._panel(detalle, 'Respuesta recibida')

        for registro in app.api.historial():
            self._agregar(registro)
        # El cliente HTTP avisa desde el hilo de trabajo; la tabla se toca
        # solo desde el hilo de Tkinter.
        self._oyente = lambda reg: app.runner.post(lambda: self._agregar(reg))
        app.api.al_registrar(self._oyente)

    def destroy(self):
        self.app.api.quitar_oyente(self._oyente)
        super().destroy()

    def _panel(self, parent, titulo: str) -> tk.Text:
        marco = ttk.LabelFrame(parent, text=titulo, padding=6)
        marco.pack(side='left', fill='both', expand=True, padx=(0, 8))
        texto = tk.Text(marco, height=12, wrap='none', font=('Consolas', 9), bg='#0f172a', fg='#e2e8f0',
                        relief='flat', padx=6, pady=6, state='disabled')
        texto.pack(fill='both', expand=True)
        return texto

    def _agregar(self, r: RegistroPeticion) -> None:
        if not self.winfo_exists():
            return
        if r.status is None or r.status >= 500:
            etiqueta = 'fallo'
        elif r.status >= 400:
            etiqueta = 'cliente'
        else:
            etiqueta = 'ok'
        resultado = r.codigo or r.mensaje
        item = self.arbol.insert('', 0, values=(
            r.hora.strftime('%H:%M:%S'), r.servicio, r.metodo, r.url,
            r.status if r.status is not None else '—', resultado, r.duracion_ms,
        ), tags=(etiqueta,))
        self.registros[item] = r

    def _seleccion(self, _evento=None) -> None:
        seleccion = self.arbol.selection()
        if not seleccion:
            return
        r = self.registros[seleccion[0]]
        self._escribir(self.enviado, r.cuerpo_enviado or '(sin cuerpo)')
        self._escribir(self.recibido, r.respuesta or f"(sin respuesta JSON)\n{r.mensaje}")

    @staticmethod
    def _escribir(widget: tk.Text, texto: str) -> None:
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', texto)
        widget.configure(state='disabled')
