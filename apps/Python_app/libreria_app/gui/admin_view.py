"""
Administracion de libros: POST, PUT, PATCH y DELETE.

El mismo formulario sirve para demostrar la diferencia entre PUT y PATCH:

  "Guardar todo (PUT)"          envia los nueve campos del libro, cambien o
                                no. Es un REEMPLAZO: lo que se envia sustituye
                                por completo lo que habia en el servidor.

  "Guardar solo cambios (PATCH)" compara el formulario contra el libro tal
                                como llego del servidor y envia UNICAMENTE los
                                campos que el usuario modifico.

El panel "Ultima peticion" muestra el cuerpo exacto que se envio.
"""
import json
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, Optional, Tuple

from libreria_app.api.http_client import ApiResult
from libreria_app.gui import theme
from libreria_app.gui.theme import COLOR
from libreria_app.gui.widgets import Mensaje

SUP = COLOR['superficie']
FORMATOS = ('Hardcover', 'Paperback', 'eBook', 'Audiobook')

CAMPOS = (
    ('isbn', 'ISBN'), ('titulo', 'Título'), ('autores', 'Autor(es) · separados por coma'),
    ('generos', 'Género(s) · separados por coma'), ('anio', 'Año de publicación'),
    ('precio', 'Precio'), ('stock', 'Existencia'), ('formato', 'Formato'), ('categoria', 'Categoría'),
)

EXPLICACION = {
    'POST': ('POST crea un recurso nuevo. Se envió el libro completo; el servidor responde '
             '201 Created y la URL del libro nuevo en la cabecera Location.'),
    'PUT': ('PUT REEMPLAZA el libro completo: se enviaron los nueve campos, cambiaran o no. '
            'Las listas enviadas sustituyen a las anteriores, y omitir cualquier campo se '
            'habría rechazado con HTTP 400.'),
    'PATCH': ('PATCH modifica PARCIALMENTE: solo se enviaron los campos que cambiaron. '
              'Todo lo demás quedó igual en el servidor.'),
    'DELETE': 'DELETE elimina el recurso identificado por la URL. No lleva cuerpo.',
}


class AdminView(ttk.Frame):

    def __init__(self, parent, app, panel):
        super().__init__(parent)
        self.app = app
        self.panel = panel
        self.modo = 'nuevo'
        self.original: Optional[Dict[str, Any]] = None
        self.categorias_cargadas = False
        self.es_admin = es_admin = bool(app.auth.sesion and app.auth.sesion.es_administrador)

        ttk.Label(self, text='Administración de libros', style='Titulo.TLabel').pack(anchor='w')
        ttk.Label(self, text='POST /books · PUT, PATCH y DELETE /books/{isbn} · requiere rol administrador',
                  style='Suave.TLabel').pack(anchor='w', pady=(0, 8))

        if not es_admin:
            aviso = tk.Label(self, bg='#fef3c7', fg='#78350f', anchor='w', justify='left', padx=12, pady=8,
                             text=('Tu cuenta tiene rol «cliente». Solo un administrador puede modificar el '
                                   'catálogo: el microservicio de libros lo verifica en cada petición '
                                   '(respondería HTTP 403), así que estas funciones están deshabilitadas.'))
            aviso.pack(fill='x', pady=(0, 8))

        # --- Barra de modo ---
        barra = ttk.Frame(self)
        barra.pack(fill='x', pady=(0, 8))
        ttk.Button(barra, text='+ Nuevo libro', command=self.nuevo).pack(side='left')
        ttk.Label(barra, text='   Cargar libro existente · ISBN:').pack(side='left')
        self.isbn_cargar = ttk.Entry(barra, width=18)
        self.isbn_cargar.pack(side='left', padx=6)
        self.isbn_cargar.bind('<Return>', lambda e: self.cargar(self.isbn_cargar.get()))
        ttk.Button(barra, text='Cargar', command=lambda: self.cargar(self.isbn_cargar.get())).pack(side='left')
        self.etiqueta_modo = ttk.Label(barra, text='', style='Subtitulo.TLabel')
        self.etiqueta_modo.pack(side='right')

        cuerpo = ttk.Frame(self)
        cuerpo.pack(fill='both', expand=True)

        # --- Formulario ---
        marco = ttk.LabelFrame(cuerpo, text='Datos del libro', padding=14)
        marco.pack(side='left', fill='both', expand=True)
        marco.columnconfigure(1, weight=1)
        self.entradas: Dict[str, Any] = {}
        for fila, (clave, etiqueta) in enumerate(CAMPOS):
            tk.Label(marco, text=etiqueta, bg=SUP, anchor='w').grid(row=fila, column=0, sticky='w', pady=3, padx=(0, 10))
            if clave == 'formato':
                entrada = ttk.Combobox(marco, values=FORMATOS)
            elif clave == 'categoria':
                entrada = ttk.Combobox(marco, state='readonly')
            else:
                entrada = ttk.Entry(marco)
            entrada.grid(row=fila, column=1, sticky='we', pady=3)
            self.entradas[clave] = entrada
        tk.Label(marco, text='Imágenes · una URL por línea (la primera es la principal)',
                 bg=SUP, anchor='w').grid(row=len(CAMPOS), column=0, columnspan=2, sticky='w', pady=(8, 2))
        self.imagenes = tk.Text(marco, height=4, font=(theme.FUENTE, 9), relief='solid', bd=1)
        self.imagenes.grid(row=len(CAMPOS) + 1, column=0, columnspan=2, sticky='we')

        botones = tk.Frame(marco, bg=SUP)
        botones.grid(row=len(CAMPOS) + 2, column=0, columnspan=2, sticky='we', pady=(12, 0))
        self.boton_post = ttk.Button(botones, text='Registrar libro (POST)', style='Primario.TButton',
                                     command=self._crear)
        self.boton_put = ttk.Button(botones, text='Guardar todo (PUT)', style='Primario.TButton',
                                    command=self._reemplazar)
        self.boton_patch = ttk.Button(botones, text='Guardar solo cambios (PATCH)', style='Primario.TButton',
                                      command=self._modificar)
        self.boton_delete = ttk.Button(botones, text='Eliminar (DELETE)', style='Peligro.TButton',
                                       command=self._eliminar)
        self.mensaje = Mensaje(marco, fondo=SUP, ancho=520)
        self.mensaje.grid(row=len(CAMPOS) + 3, column=0, columnspan=2, sticky='w', pady=(10, 0))

        # --- Ultima peticion ---
        panel_peticion = ttk.LabelFrame(cuerpo, text='Última petición enviada', padding=12)
        panel_peticion.pack(side='left', fill='both', padx=(12, 0))
        self.peticion = tk.Text(panel_peticion, width=46, wrap='word', relief='flat', bg='#0f172a',
                                fg='#e2e8f0', font=('Consolas', 9), padx=8, pady=8)
        self.peticion.pack(fill='both', expand=True)
        self.peticion.insert('1.0', 'Aquí se mostrará el método, la URL, el código HTTP y el cuerpo exacto '
                                    'de la próxima operación de escritura.')
        self.peticion.configure(state='disabled')

        if not es_admin:
            for widget in list(self.entradas.values()) + [self.imagenes, self.boton_post, self.boton_put,
                                                          self.boton_patch, self.boton_delete]:
                widget.configure(state='disabled')
        self.nuevo()

    # ------------------------------------------------------------------
    def al_mostrar(self) -> None:
        if not self.categorias_cargadas:
            self.app.runner.run(self.app.books.categorias, al_terminar=self._categorias)

    def _categorias(self, r) -> None:
        if isinstance(r, ApiResult) and r.ok:
            self.entradas['categoria'].configure(values=r.data['categorias'])
            self.categorias_cargadas = True
        else:
            # Sin la lista del servidor se permite escribirla; si no existe,
            # el microservicio responde 400 con las categorias validas.
            self.entradas['categoria'].configure(state='normal')

    # ------------------------------------------------------------------
    # Modos
    # ------------------------------------------------------------------
    def nuevo(self) -> None:
        self.modo = 'nuevo'
        self.original = None
        self._llenar({})
        self.entradas['isbn'].configure(state='normal' if self.es_admin else 'disabled')
        self.etiqueta_modo.configure(text='Registrando un libro nuevo' if self.es_admin else '')
        for boton in (self.boton_put, self.boton_patch, self.boton_delete):
            boton.pack_forget()
        self.boton_post.pack(side='left')
        self.mensaje.limpiar()

    def cargar(self, isbn: str) -> None:
        if not self.es_admin:
            self.mensaje.mostrar('La administración de libros requiere rol administrador.', 'aviso')
            return
        isbn = (isbn or '').strip()
        if not isbn:
            self.mensaje.mostrar('Escribe el ISBN del libro que quieres cargar.', 'aviso')
            return
        self.mensaje.mostrar(f"Consultando GET /books/{isbn}…")
        self.app.runner.run(self.app.books.detalle, isbn, al_terminar=self._cargado)

    def _cargado(self, r) -> None:
        if not isinstance(r, ApiResult):
            self.mensaje.mostrar(f"Error inesperado: {r}", 'error')
            return
        if not r.ok:
            texto = 'No existe un libro con ese ISBN (HTTP 404).' if r.status == 404 else r.mensaje
            self.mensaje.mostrar(texto, 'error')
            return
        self._modo_edicion(r.data)
        self.mensaje.mostrar(f"Libro cargado desde el servidor (HTTP {r.status}).", 'exito')

    def _modo_edicion(self, libro: Dict[str, Any]) -> None:
        self.modo = 'editar'
        self.original = self._desde_libro(libro)
        self._llenar(self.original)
        self.entradas['isbn'].configure(state='readonly')   # el ISBN es inmutable
        self.etiqueta_modo.configure(text=f"Editando {libro['isbn']}")
        self.boton_post.pack_forget()
        for boton in (self.boton_put, self.boton_patch, self.boton_delete):
            boton.pack(side='left', padx=(0, 6))

    # ------------------------------------------------------------------
    # Lectura y escritura del formulario
    # ------------------------------------------------------------------
    @staticmethod
    def _desde_libro(libro: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'isbn': libro['isbn'], 'titulo': libro['titulo'], 'autores': list(libro['autores']),
            'generos': list(libro['generos']), 'anio': libro['anio'], 'precio': round(libro['precio'], 2),
            'stock': libro['stock'], 'formato': libro['formato'], 'categoria': libro['categoria'],
            'imagenes': [i['url'] for i in libro.get('imagenes', [])],
        }

    def _llenar(self, datos: Dict[str, Any]) -> None:
        estado_isbn = str(self.entradas['isbn'].cget('state'))
        self.entradas['isbn'].configure(state='normal')
        for clave, entrada in self.entradas.items():
            valor = datos.get(clave, '')
            if isinstance(valor, list):
                valor = ', '.join(valor)
            elif clave == 'precio' and isinstance(valor, float):
                valor = f"{valor:.2f}"
            if clave == 'categoria':
                entrada.set(valor)
                continue
            entrada.delete(0, 'end')
            entrada.insert(0, '' if valor is None else str(valor))
        self.entradas['isbn'].configure(state=estado_isbn)
        self.imagenes.delete('1.0', 'end')
        self.imagenes.insert('1.0', '\n'.join(datos.get('imagenes', [])))

    def _leer(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Convierte el formulario en los tipos que espera la API.
        Devuelve (datos, None) o (None, mensaje_de_error)."""
        texto = {k: e.get().strip() for k, e in self.entradas.items()}

        def lista(valor: str):
            return [v.strip() for v in valor.split(',') if v.strip()]

        try:
            anio = int(texto['anio'])
        except ValueError:
            return None, 'El año debe ser un número entero.'
        try:
            precio = round(float(texto['precio'].replace('$', '').replace(',', '')), 2)
        except ValueError:
            return None, 'El precio debe ser un número (por ejemplo 499.50).'
        try:
            stock = int(texto['stock'])
        except ValueError:
            return None, 'La existencia debe ser un número entero.'

        return {
            'isbn': texto['isbn'], 'titulo': texto['titulo'], 'autores': lista(texto['autores']),
            'generos': lista(texto['generos']), 'anio': anio, 'precio': precio, 'stock': stock,
            'formato': texto['formato'], 'categoria': texto['categoria'],
            'imagenes': [u.strip() for u in self.imagenes.get('1.0', 'end').splitlines() if u.strip()],
        }, None

    def _diferencias(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        """Campos que el usuario cambio respecto de lo que envio el servidor.
        Los generos se comparan como conjunto (el servidor los devuelve
        ordenados); autores e imagenes, en orden (el orden importa: define
        el orden de autoria y cual imagen es la principal)."""
        cambios = {}
        for clave, valor in datos.items():
            if clave == 'isbn':
                continue
            anterior = self.original.get(clave)
            if clave == 'generos':
                iguales = sorted(v.lower() for v in valor) == sorted(v.lower() for v in anterior)
            else:
                iguales = valor == anterior
            if not iguales:
                cambios[clave] = valor
        return cambios

    # ------------------------------------------------------------------
    # Operaciones
    # ------------------------------------------------------------------
    def _crear(self) -> None:
        datos, error = self._leer()
        if error:
            self.mensaje.mostrar(error, 'aviso')
            return
        self._enviar('POST', datos, self.app.books.crear, datos)

    def _reemplazar(self) -> None:
        datos, error = self._leer()
        if error:
            self.mensaje.mostrar(error, 'aviso')
            return
        cuerpo = {k: v for k, v in datos.items() if k != 'isbn'}
        self._enviar('PUT', cuerpo, self.app.books.reemplazar, self.original['isbn'], cuerpo)

    def _modificar(self) -> None:
        datos, error = self._leer()
        if error:
            self.mensaje.mostrar(error, 'aviso')
            return
        cambios = self._diferencias(datos)
        if not cambios:
            self.mensaje.mostrar('No modificaste ningún campo: no hay nada que enviar con PATCH.', 'aviso')
            return
        self._enviar('PATCH', cambios, self.app.books.modificar, self.original['isbn'], cambios)

    def _eliminar(self) -> None:
        isbn, titulo = self.original['isbn'], self.original['titulo']
        confirmado = messagebox.askyesno(
            'Confirmar eliminación',
            f"¿Eliminar definitivamente este libro?\n\n{titulo}\nISBN {isbn}\n\n"
            'Se enviará DELETE /books/' + isbn + ' al microservicio. Esta acción no se puede deshacer.',
            icon='warning', parent=self.app,
        )
        if not confirmado:
            self.mensaje.mostrar('Eliminación cancelada: no se envió ninguna petición.', 'info')
            return
        self._enviar('DELETE', None, self.app.books.eliminar, isbn)

    def _enviar(self, metodo: str, cuerpo: Optional[Dict[str, Any]], funcion, *args) -> None:
        self.mensaje.mostrar(f"Enviando {metodo} al microservicio de libros…")
        for boton in (self.boton_post, self.boton_put, self.boton_patch, self.boton_delete):
            boton.state(['disabled'])

        def listo(r):
            for boton in (self.boton_post, self.boton_put, self.boton_patch, self.boton_delete):
                boton.state(['!disabled'])
            self._resultado(metodo, cuerpo, r)
        self.app.runner.run(funcion, *args, al_terminar=listo)

    def _resultado(self, metodo: str, cuerpo: Optional[Dict[str, Any]], r) -> None:
        if not isinstance(r, ApiResult):
            self.mensaje.mostrar(f"Error inesperado: {r}", 'error')
            return
        self._mostrar_peticion(metodo, cuerpo, r)
        if self.app.verificar_sesion(r):
            return

        if not r.ok:
            textos = {
                'ERR_ISBN_DUPLICADO': 'Ya existe un libro con ese ISBN (HTTP 409 Conflict).',
                'ERR_SIN_PERMISOS': 'Tu cuenta no tiene permisos para modificar el catálogo (HTTP 403).',
                'ERR_LIBRO_NO_ENCONTRADO': 'El libro ya no existe en el servidor (HTTP 404).',
            }
            self.mensaje.mostrar(textos.get(r.codigo, f"{r.mensaje}" + (f" (HTTP {r.status})" if r.status else '')),
                                 'error')
            return

        if metodo == 'DELETE':
            self.nuevo()
            self.mensaje.mostrar(f"{r.mensaje.rstrip('.')} (HTTP {r.status}). El catálogo se actualizó.", 'exito')
        else:
            self._modo_edicion(r.data['libro'])
            detalle = ''
            if metodo == 'PATCH':
                detalle = f" Campos modificados: {', '.join(r.data.get('campos_actualizados', []))}."
            self.mensaje.mostrar(f"{r.mensaje.rstrip('.')} (HTTP {r.status}).{detalle} El catálogo se actualizó.", 'exito')
        self.panel.catalogo_modificado()

    def _mostrar_peticion(self, metodo: str, cuerpo: Optional[Dict[str, Any]], r: ApiResult) -> None:
        ruta = r.url.split('?')[0]
        lineas = [f"{metodo} {ruta}", f"Respuesta: HTTP {r.status or '— (sin respuesta)'} · {r.duracion_ms} ms", '']
        if cuerpo is not None:
            lineas.append(f"Cuerpo enviado ({len(cuerpo)} campo(s)):")
            lineas.append(json.dumps(cuerpo, ensure_ascii=False, indent=2))
        else:
            lineas.append('Sin cuerpo.')
        lineas += ['', EXPLICACION[metodo]]
        if not r.ok:
            lineas += ['', f"Resultado: {r.codigo or 'error'} — {r.mensaje}"]

        self.peticion.configure(state='normal')
        self.peticion.delete('1.0', 'end')
        self.peticion.insert('1.0', '\n'.join(lineas))
        self.peticion.configure(state='disabled')
