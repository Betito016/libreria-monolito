"""Ventanas secundarias: aviso de expiracion y detalle de un libro."""
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from libreria_app.api.http_client import ApiResult
from libreria_app.gui import theme
from libreria_app.gui.theme import COLOR
from libreria_app.gui.widgets import ImagenesRemotas, Mensaje


def mmss(segundos: int) -> str:
    return f"{segundos // 60:02d}:{segundos % 60:02d}"


# ----------------------------------------------------------------------
# Aviso de expiracion de sesion
# ----------------------------------------------------------------------
class AvisoExpiracion(tk.Toplevel):
    """No es modal: el usuario puede seguir trabajando mientras lo ve."""

    def __init__(self, app, al_extender: Callable, al_descartar: Callable):
        super().__init__(app)
        self.al_extender = al_extender
        self.title('Tu sesión está por expirar')
        self.configure(bg=COLOR['superficie'], padx=24, pady=20)
        self.resizable(False, False)
        self.transient(app)
        self.protocol('WM_DELETE_WINDOW', al_descartar)

        tk.Label(self, text='⏳  Tu sesión está por expirar', bg=COLOR['superficie'],
                 font=(theme.FUENTE, 13, 'bold')).pack(anchor='w')
        self.cuenta = tk.Label(self, text='', bg=COLOR['superficie'], fg=COLOR['aviso'],
                               font=(theme.FUENTE, 22, 'bold'))
        self.cuenta.pack(anchor='w', pady=(8, 4))
        tk.Label(self, text='Si no la extiendes, al llegar a cero tendrás que iniciar sesión de nuevo.',
                 bg=COLOR['superficie'], fg=COLOR['texto_suave']).pack(anchor='w')

        self.mensaje = Mensaje(self, fondo=COLOR['superficie'], ancho=380)
        self.mensaje.pack(anchor='w', pady=(8, 0))

        botones = tk.Frame(self, bg=COLOR['superficie'])
        botones.pack(fill='x', pady=(12, 0))
        self.boton_extender = ttk.Button(botones, text='Extender sesión', style='Primario.TButton',
                                         command=self._extender)
        self.boton_extender.pack(side='left')
        ttk.Button(botones, text='Seguir sin extender', command=al_descartar).pack(side='left', padx=8)

        self.update_idletasks()
        x = app.winfo_rootx() + (app.winfo_width() - self.winfo_width()) // 2
        y = app.winfo_rooty() + 120
        self.geometry(f"+{x}+{y}")
        self.lift()

    def actualizar(self, restantes: int) -> None:
        self.cuenta.configure(text=f"La sesión expira en {mmss(restantes)}")

    def _extender(self) -> None:
        self.boton_extender.state(['disabled'])
        self.mensaje.mostrar('Solicitando la extensión al servidor (POST /session/extend)…')

        def listo(r):
            if isinstance(r, ApiResult) and not r.ok and self.winfo_exists():
                self.boton_extender.state(['!disabled'])
                self.mensaje.mostrar(f"No se pudo extender: {r.mensaje}", 'error')
        self.al_extender(al_terminar=listo)


# ----------------------------------------------------------------------
# Detalle de un libro: GET /api/books/{isbn}
# ----------------------------------------------------------------------
CAMPOS_DETALLE = (
    ('isbn', 'ISBN'), ('titulo', 'Título'), ('autores', 'Autor(es)'), ('generos', 'Género(s)'),
    ('anio', 'Año'), ('precio', 'Precio'), ('stock', 'Existencia'), ('formato', 'Formato'),
    ('categoria', 'Categoría'),
)


def valor_legible(clave: str, valor) -> str:
    if isinstance(valor, list):
        return ', '.join(valor) if valor else '—'
    if clave == 'precio' and valor is not None:
        return f"${valor:,.2f}"
    if clave == 'stock' and valor is not None:
        return f"{valor} unidades"
    return str(valor) if valor not in (None, '') else '—'


class DetalleLibro(tk.Toplevel):

    ANCHO_IMG, ALTO_IMG = 240, 360

    def __init__(self, app, isbn: str, al_editar: Optional[Callable[[str], None]] = None):
        super().__init__(app)
        self.app = app
        self.isbn = isbn
        self.al_editar = al_editar
        self.imagenes = []
        self.indice = 0

        self.title(f"Detalle del libro {isbn}")
        self.configure(bg=COLOR['superficie'], padx=20, pady=16)
        self.geometry('860x620')
        self.transient(app)

        self.estado = Mensaje(self, fondo=COLOR['superficie'])
        self.estado.pack(anchor='w')
        self.estado.mostrar(f"Consultando GET /api/books/{isbn}…")

        app.runner.run(app.books.detalle, isbn, al_terminar=self._cargado)

    def _cargado(self, r) -> None:
        if not self.winfo_exists():
            return
        if isinstance(r, Exception):
            self.estado.mostrar(f"Error inesperado: {r}", 'error')
            return
        if not r.ok:
            texto = (f"El libro con ISBN {self.isbn} no existe (HTTP 404)." if r.status == 404
                     else f"No se pudo obtener el detalle: {r.mensaje}")
            self.estado.mostrar(texto, 'error')
            return
        self.estado.mostrar(f"GET /api/books/{self.isbn} → HTTP {r.status} ({r.duracion_ms} ms)", 'exito')
        self._construir(r.data)

    def _construir(self, libro: dict) -> None:
        cuerpo = tk.Frame(self, bg=COLOR['superficie'])
        cuerpo.pack(fill='both', expand=True, pady=(8, 0))

        # --- Imagenes (una o varias) ---
        izquierda = tk.Frame(cuerpo, bg=COLOR['superficie'])
        izquierda.pack(side='left', fill='y', padx=(0, 20))
        self.lienzo = tk.Label(izquierda, bg=COLOR['superficie'])
        self.lienzo.pack()
        navegacion = tk.Frame(izquierda, bg=COLOR['superficie'])
        navegacion.pack(pady=6)
        self.anterior = ttk.Button(navegacion, text='◀', width=3, command=lambda: self._mover(-1))
        self.anterior.pack(side='left')
        self.contador = tk.Label(navegacion, text='', bg=COLOR['superficie'], width=16)
        self.contador.pack(side='left')
        self.siguiente = ttk.Button(navegacion, text='▶', width=3, command=lambda: self._mover(1))
        self.siguiente.pack(side='left')

        self.imagenes = libro.get('imagenes') or []
        self._mostrar_imagen()

        # --- Datos ---
        derecha = tk.Frame(cuerpo, bg=COLOR['superficie'])
        derecha.pack(side='left', fill='both', expand=True)
        tk.Label(derecha, text=libro.get('titulo', ''), bg=COLOR['superficie'], anchor='w',
                 font=(theme.FUENTE, 15, 'bold'), wraplength=520, justify='left').pack(fill='x')

        tabla = tk.Frame(derecha, bg=COLOR['superficie'])
        tabla.pack(fill='x', pady=(8, 10))
        for fila, (clave, etiqueta) in enumerate(CAMPOS_DETALLE):
            tk.Label(tabla, text=etiqueta, bg=COLOR['superficie'], fg=COLOR['texto_suave'],
                     anchor='w').grid(row=fila, column=0, sticky='w', pady=2, padx=(0, 14))
            tk.Label(tabla, text=valor_legible(clave, libro.get(clave)), bg=COLOR['superficie'],
                     anchor='w', wraplength=400, justify='left').grid(row=fila, column=1, sticky='w', pady=2)

        tk.Label(derecha, text='Conceptos asociados', bg=COLOR['superficie'], anchor='w',
                 font=(theme.FUENTE, 11, 'bold')).pack(fill='x')
        conceptos = tk.Text(derecha, height=8, wrap='word', relief='flat', bg='#f8fafc',
                            font=(theme.FUENTE, 10), padx=8, pady=6)
        conceptos.pack(fill='both', expand=True, pady=(4, 8))
        if libro.get('conceptos'):
            for c in libro['conceptos']:
                conceptos.insert('end', f"{c['nombre']}\n", 'nombre')
                conceptos.insert('end', f"{c['definicion']}\n\n")
            conceptos.tag_configure('nombre', font=(theme.FUENTE, 10, 'bold'))
        else:
            conceptos.insert('end', 'Este libro no tiene conceptos asociados en el microservicio.')
        conceptos.configure(state='disabled')

        botones = tk.Frame(derecha, bg=COLOR['superficie'])
        botones.pack(fill='x')
        if self.al_editar and self.app.auth.sesion and self.app.auth.sesion.es_administrador:
            ttk.Button(botones, text='Editar en Administración', style='Primario.TButton',
                       command=lambda: (self.al_editar(libro['isbn']), self.destroy())).pack(side='left')
        ttk.Button(botones, text='Cerrar', command=self.destroy).pack(side='right')

    def _mostrar_imagen(self) -> None:
        total = len(self.imagenes)
        url = self.imagenes[self.indice]['url'] if total else None
        self.contador.configure(text=f"Imagen {self.indice + 1} de {total}" if total else 'Sin imágenes')
        for boton in (self.anterior, self.siguiente):
            boton.state(['!disabled'] if total > 1 else ['disabled'])

        def poner(foto, _estado):
            if self.winfo_exists():
                self.lienzo.configure(image=foto)
                self.lienzo.image = foto
        self.app.imagenes.obtener(url, self.ANCHO_IMG, self.ALTO_IMG, poner)

    def _mover(self, paso: int) -> None:
        if self.imagenes:
            self.indice = (self.indice + paso) % len(self.imagenes)
            self._mostrar_imagen()
