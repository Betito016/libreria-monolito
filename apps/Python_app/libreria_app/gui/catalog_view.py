"""
Catalogo: consulta y busqueda de libros (GET /api/books) y acceso al detalle
(GET /api/books/{isbn}). Todo sale del microservicio de libros; la aplicacion
no guarda una copia propia del catalogo.
"""
import tkinter as tk
from tkinter import ttk

from libreria_app.gui import theme
from libreria_app.gui.dialogs import DetalleLibro
from libreria_app.gui.theme import COLOR
from libreria_app.gui.widgets import AreaDesplazable, Mensaje

SUP = COLOR['superficie']


class CatalogView(ttk.Frame):

    POR_PAGINA = 12
    COLUMNAS = 4
    ANCHO_IMG, ALTO_IMG = 130, 195

    def __init__(self, parent, app, panel):
        super().__init__(parent)
        self.app = app
        self.panel = panel
        self.pagina = 1
        self.total_paginas = 1
        self.filtros = {}
        self.cargado = False

        ttk.Label(self, text='Catálogo de libros', style='Titulo.TLabel').pack(anchor='w')
        ttk.Label(self, text='Datos obtenidos del microservicio de libros · GET /api/books?format=json · público, sin JWT',
                  style='Suave.TLabel').pack(anchor='w', pady=(0, 10))

        # --- Busqueda ---
        busqueda = ttk.LabelFrame(self, text='Buscar libros', padding=12)
        busqueda.pack(fill='x')
        self.campos = {}
        for col, (clave, etiqueta, ancho) in enumerate((
                ('isbn', 'ISBN', 16), ('titulo', 'Título', 24), ('anio', 'Año', 7),
                ('precio_min', 'Precio mín.', 9), ('precio_max', 'Precio máx.', 9))):
            tk.Label(busqueda, text=etiqueta, bg=SUP).grid(row=0, column=col, sticky='w', padx=(0, 8))
            entrada = ttk.Entry(busqueda, width=ancho)
            entrada.grid(row=1, column=col, sticky='w', padx=(0, 8))
            entrada.bind('<Return>', lambda e: self._buscar())
            self.campos[clave] = entrada
        ttk.Button(busqueda, text='Buscar', style='Primario.TButton', command=self._buscar).grid(
            row=1, column=5, padx=(8, 4))
        ttk.Button(busqueda, text='Limpiar', command=self._limpiar).grid(row=1, column=6)

        # --- Encabezado de resultados y paginacion ---
        barra = ttk.Frame(self)
        barra.pack(fill='x', pady=(12, 4))
        self.resumen = ttk.Label(barra, text='', style='Subtitulo.TLabel')
        self.resumen.pack(side='left')
        ttk.Button(barra, text='↻ Actualizar', command=self.recargar).pack(side='right')
        self.siguiente = ttk.Button(barra, text='Siguiente ▶', command=lambda: self._consultar(self.pagina + 1))
        self.siguiente.pack(side='right', padx=4)
        self.etiqueta_pagina = ttk.Label(barra, text='')
        self.etiqueta_pagina.pack(side='right', padx=8)
        self.anterior = ttk.Button(barra, text='◀ Anterior', command=lambda: self._consultar(self.pagina - 1))
        self.anterior.pack(side='right')

        self.mensaje = Mensaje(self)
        self.mensaje.pack(fill='x', pady=(0, 6))

        self.area = AreaDesplazable(self)
        self.area.pack(fill='both', expand=True)
        for col in range(self.COLUMNAS):
            self.area.interior.columnconfigure(col, weight=1, uniform='tarjeta')

    # ------------------------------------------------------------------
    def al_mostrar(self) -> None:
        if not self.cargado:
            self.recargar()

    def recargar(self) -> None:
        self._consultar(self.pagina)

    def _limpiar(self) -> None:
        for entrada in self.campos.values():
            entrada.delete(0, 'end')
        self.filtros = {}
        self._consultar(1)

    def _buscar(self) -> None:
        """Arma los filtros. Los numericos se revisan aqui para dar un mensaje
        claro de inmediato; el servidor los valida de todas formas."""
        valores = {k: e.get().strip() for k, e in self.campos.items()}
        filtros = {}
        if valores['isbn']:
            filtros['isbn'] = valores['isbn']
        if valores['titulo']:
            filtros['titulo'] = valores['titulo']
        try:
            if valores['anio']:
                filtros['anio'] = int(valores['anio'])
            for clave in ('precio_min', 'precio_max'):
                if valores[clave]:
                    filtros[clave] = float(valores[clave].replace('$', '').replace(',', ''))
        except ValueError:
            self.mensaje.mostrar('El año debe ser un número entero y los precios, números.', 'aviso')
            return
        if 'precio_min' in filtros and 'precio_max' in filtros and filtros['precio_min'] > filtros['precio_max']:
            self.mensaje.mostrar('El precio mínimo no puede ser mayor que el máximo.', 'aviso')
            return
        self.filtros = filtros
        self._consultar(1)

    def _consultar(self, pagina: int) -> None:
        self.pagina = max(1, pagina)
        self.mensaje.mostrar('Consultando el catálogo…')
        self.anterior.state(['disabled'])
        self.siguiente.state(['disabled'])
        self.app.runner.run(self.app.books.buscar, self.filtros, self.pagina, self.POR_PAGINA,
                            al_terminar=self._resultado)

    def _resultado(self, r) -> None:
        if not self.winfo_exists():
            return
        self.cargado = True
        if isinstance(r, Exception):
            self.mensaje.mostrar(f"Error inesperado: {r}", 'error')
            return
        if not r.ok:
            self._vaciar()
            self.resumen.configure(text='Catálogo no disponible')
            self.etiqueta_pagina.configure(text='')
            self.mensaje.mostrar(f"No se pudo cargar el catálogo. {r.mensaje}", 'error')
            return

        datos = r.data
        self.total_paginas = datos['total_pages']
        filtros = ', '.join(f"{k}={v}" for k, v in datos.get('filtros', {}).items())
        self.resumen.configure(text=f"{datos['total']} libro(s)" + (f" · filtros: {filtros}" if filtros else ''))
        self.etiqueta_pagina.configure(text=f"Página {datos['page']} de {self.total_paginas}")
        self.anterior.state(['!disabled'] if self.pagina > 1 else ['disabled'])
        self.siguiente.state(['!disabled'] if self.pagina < self.total_paginas else ['disabled'])
        self.mensaje.mostrar(f"GET /api/books → HTTP {r.status} en {r.duracion_ms} ms", 'exito')

        self._vaciar()
        if not datos['libros']:
            tk.Label(self.area.interior, text='Ningún libro coincide con la búsqueda.',
                     bg=COLOR['fondo'], fg=COLOR['texto_suave'], font=(theme.FUENTE, 11)).grid(pady=30)
            return
        for i, libro in enumerate(datos['libros']):
            self._tarjeta(libro, i // self.COLUMNAS, i % self.COLUMNAS)
        self.area.al_inicio()

    def _vaciar(self) -> None:
        for hijo in self.area.interior.winfo_children():
            hijo.destroy()

    def _tarjeta(self, libro: dict, fila: int, col: int) -> None:
        tarjeta = tk.Frame(self.area.interior, bg=SUP, padx=10, pady=10, cursor='hand2',
                           highlightbackground=COLOR['borde'], highlightthickness=1)
        tarjeta.grid(row=fila, column=col, sticky='nsew', padx=6, pady=6)

        imagen = tk.Label(tarjeta, bg=SUP)
        imagen.pack()

        def poner(foto, _estado):
            if imagen.winfo_exists():
                imagen.configure(image=foto)
                imagen.image = foto
        self.app.imagenes.obtener(libro.get('imagen_principal'), self.ANCHO_IMG, self.ALTO_IMG, poner)

        def texto(t, **kw):
            tk.Label(tarjeta, text=t, bg=SUP, wraplength=210, justify='left', anchor='w', **kw).pack(fill='x')

        texto(libro['titulo'], font=(theme.FUENTE, 10, 'bold'))
        texto(', '.join(libro['autores']) or 'Autor no registrado', fg=COLOR['texto_suave'])
        texto(f"{libro['anio']} · {libro['formato']} · {libro['categoria']}", fg=COLOR['texto_suave'])
        texto(f"${libro['precio']:,.2f}", font=(theme.FUENTE, 11, 'bold'), fg=COLOR['acento'])
        texto(f"Existencia: {libro['stock']}  ·  ISBN {libro['isbn']}", fg=COLOR['texto_suave'])
        if len(libro.get('imagenes', [])) > 1:
            texto(f"🖼 {len(libro['imagenes'])} imágenes", fg=COLOR['acento'])

        def abrir(_evento=None):
            DetalleLibro(self.app, libro['isbn'], al_editar=self.panel.editar_libro)
        for widget in [tarjeta] + list(tarjeta.winfo_children()):
            widget.bind('<Button-1>', abrir)
