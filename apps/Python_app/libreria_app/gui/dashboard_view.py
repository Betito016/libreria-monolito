"""
Panel principal. Separa claramente las funciones de la aplicacion:

    Catalogo            consulta, busqueda y detalle      (servicio de libros)
    Administracion      alta, PUT, PATCH y baja            (servicio de libros)
    Sesion y perfil     datos de la sesion y del usuario   (servicio de login)
    Estado de servicios semaforo de ambos microservicios   (/health)
    Configuracion       direcciones de los servidores      (archivo local)
    Registro HTTP       peticiones realizadas y respuestas
"""
import tkinter as tk
from tkinter import messagebox, ttk

from libreria_app.gui import theme
from libreria_app.gui.dialogs import mmss
from libreria_app.gui.theme import COLOR
from libreria_app.gui.widgets import Semaforo

BARRA = COLOR['barra_lateral']

SECCIONES = (
    ('catalogo', '📖  Catálogo'),
    ('admin', '🛠  Administración'),
    ('perfil', '👤  Sesión y perfil'),
    ('estado', '🚦  Estado de servicios'),
    ('config', '⚙  Configuración'),
    ('http', '🧾  Registro HTTP'),
)


class DashboardView(ttk.Frame):

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        sesion = app.auth.sesion

        # --- Barra superior -------------------------------------------
        superior = tk.Frame(self, bg=BARRA, padx=16, pady=10)
        superior.pack(fill='x')
        tk.Label(superior, text='📚 Librería en Línea', bg=BARRA, fg=COLOR['texto_claro'],
                 font=(theme.FUENTE, 14, 'bold')).pack(side='left')

        self.luces = {}
        for servicio, nombre in (('login', 'Login'), ('books', 'Libros')):
            luz = Semaforo(superior, 12, fondo=BARRA)
            luz.pack(side='left', padx=(22, 4))
            tk.Label(superior, text=nombre, bg=BARRA, fg=COLOR['texto_claro']).pack(side='left')
            self.luces[servicio] = luz
        app.al_cambiar_salud(self._salud)

        ttk.Button(superior, text='Cerrar sesión', command=app.cerrar_sesion).pack(side='right')
        ttk.Button(superior, text='Extender', command=self._extender).pack(side='right', padx=6)
        self.reloj = tk.Label(superior, text='', bg=BARRA, fg=COLOR['texto_claro'],
                              font=(theme.FUENTE, 10, 'bold'))
        self.reloj.pack(side='right', padx=10)
        rol = 'administrador' if sesion.es_administrador else sesion.usuario.get('rol', '')
        tk.Label(superior, text=f"{sesion.nombre_completo} · {rol}", bg=BARRA,
                 fg=COLOR['texto_claro']).pack(side='right', padx=10)

        # --- Menu lateral ---------------------------------------------
        cuerpo = ttk.Frame(self)
        cuerpo.pack(fill='both', expand=True)
        lateral = tk.Frame(cuerpo, bg=BARRA, width=210)
        lateral.pack(side='left', fill='y')
        lateral.pack_propagate(False)

        self.botones = {}
        for clave, texto in SECCIONES:
            boton = tk.Button(lateral, text=texto, anchor='w', relief='flat', bd=0, padx=18, pady=11,
                              bg=BARRA, fg=COLOR['texto_claro'], activebackground=COLOR['barra_lateral_activa'],
                              activeforeground='white', font=(theme.FUENTE, 10), cursor='hand2',
                              command=lambda c=clave: self.ir(c))
            boton.pack(fill='x')
            self.botones[clave] = boton

        # --- Secciones (todas en la misma celda; se muestra una) ------
        contenedor = ttk.Frame(cuerpo, padding=18)
        contenedor.pack(side='left', fill='both', expand=True)
        contenedor.rowconfigure(0, weight=1)
        contenedor.columnconfigure(0, weight=1)

        from libreria_app.gui.admin_view import AdminView
        from libreria_app.gui.catalog_view import CatalogView
        from libreria_app.gui.config_view import ConfigView
        from libreria_app.gui.http_log_view import HttpLogView
        from libreria_app.gui.profile_view import ProfileView
        from libreria_app.gui.status_view import StatusView

        self.secciones = {
            'catalogo': CatalogView(contenedor, app, self),
            'admin': AdminView(contenedor, app, self),
            'perfil': ProfileView(contenedor, app),
            'estado': StatusView(contenedor, app),
            'config': ConfigView(contenedor, app),
            'http': HttpLogView(contenedor, app),
        }
        for seccion in self.secciones.values():
            seccion.grid(row=0, column=0, sticky='nsew')
        self.ir('catalogo')

    def destroy(self):
        self.app.quitar_oyente_salud(self._salud)
        super().destroy()

    # ------------------------------------------------------------------
    def ir(self, clave: str) -> None:
        for nombre, boton in self.botones.items():
            boton.configure(bg=COLOR['barra_lateral_activa'] if nombre == clave else BARRA)
        seccion = self.secciones[clave]
        seccion.tkraise()
        if hasattr(seccion, 'al_mostrar'):
            seccion.al_mostrar()

    def _salud(self, estados) -> None:
        for servicio, estado in estados.items():
            self.luces[servicio].fijar(estado.nivel)

    def _extender(self) -> None:
        def listo(r):
            if not getattr(r, 'ok', False):
                messagebox.showwarning('No se pudo extender la sesión', getattr(r, 'mensaje', str(r)),
                                       parent=self.app)
        self.app.extender_sesion(al_terminar=listo)

    def actualizar_reloj(self, restantes: int, por_expirar: bool) -> None:
        self.reloj.configure(text=f"Sesión: {mmss(restantes)}",
                             fg='#fca5a5' if por_expirar else COLOR['texto_claro'])
        perfil = self.secciones.get('perfil')
        if perfil:
            perfil.actualizar_reloj(restantes)

    # --- Coordinacion entre secciones -----------------------------------
    def editar_libro(self, isbn: str) -> None:
        self.ir('admin')
        self.secciones['admin'].cargar(isbn)

    def catalogo_modificado(self) -> None:
        """Tras un POST/PUT/PATCH/DELETE el catalogo se vuelve a pedir al
        servidor: lo que se ve refleja el estado real, no una copia local."""
        self.secciones['catalogo'].recargar()
