"""
Sesion y perfil del usuario autenticado.

    Ver datos de la sesion    GET  /session         (sesion guardada en Redis)
    Renovar el JWT            POST /token/refresh   (refresh token de un solo uso)
    Modificar el perfil       PATCH /profile        (solo los campos cambiados)
"""
import tkinter as tk
from tkinter import ttk

from libreria_app.api.http_client import ApiResult
from libreria_app.gui import theme
from libreria_app.gui.dialogs import mmss
from libreria_app.gui.theme import COLOR
from libreria_app.gui.widgets import Mensaje, formulario

SUP = COLOR['superficie']
CAMPOS_NOMBRE = ('nombre', 'apellido_paterno', 'apellido_materno', 'email')


class ProfileView(ttk.Frame):

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        ttk.Label(self, text='Sesión y perfil', style='Titulo.TLabel').pack(anchor='w')
        ttk.Label(self, text='GET /session · POST /token/refresh · PATCH /profile  (microservicio de login :5000)',
                  style='Suave.TLabel').pack(anchor='w', pady=(0, 10))

        cuerpo = ttk.Frame(self)
        cuerpo.pack(fill='both', expand=True)

        # --- Sesion actual ---
        sesion = ttk.LabelFrame(cuerpo, text='Sesión actual', padding=16)
        sesion.pack(side='left', fill='both', padx=(0, 12))
        self.datos = {}
        for fila, (clave, etiqueta) in enumerate((
                ('nombre_completo', 'Nombre'), ('email', 'Correo'), ('rol', 'Rol'),
                ('email_verificado', 'Correo verificado'), ('expira', 'El JWT expira en'),
                ('duracion', 'Duración del JWT'))):
            tk.Label(sesion, text=etiqueta, bg=SUP, fg=COLOR['texto_suave'], anchor='w').grid(
                row=fila, column=0, sticky='w', pady=3, padx=(0, 14))
            valor = tk.Label(sesion, text='', bg=SUP, anchor='w', font=(theme.FUENTE, 10, 'bold'))
            valor.grid(row=fila, column=1, sticky='w', pady=3)
            self.datos[clave] = valor

        botones = tk.Frame(sesion, bg=SUP)
        botones.grid(row=6, column=0, columnspan=2, sticky='w', pady=(14, 0))
        ttk.Button(botones, text='Consultar al servidor', command=self._consultar).pack(side='left')
        ttk.Button(botones, text='Renovar JWT', style='Primario.TButton',
                   command=self._extender).pack(side='left', padx=8)
        self.msg_sesion = Mensaje(sesion, fondo=SUP, ancho=340)
        self.msg_sesion.grid(row=7, column=0, columnspan=2, sticky='w', pady=(10, 0))

        # --- Modificar perfil ---
        perfil = ttk.LabelFrame(cuerpo, text='Modificar perfil (PATCH /profile)', padding=16)
        perfil.pack(side='left', fill='both', expand=True)
        tk.Label(perfil, bg=SUP, fg=COLOR['texto_suave'], justify='left', anchor='w', wraplength=460,
                 text=('Solo se envían los campos que modifiques. Cambiar el correo o la contraseña '
                       'exige tu contraseña actual; un correo nuevo debe verificarse de nuevo.')
                 ).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 10))
        self.perfil = formulario(perfil, [
            ('nombre', 'Nombre'), ('apellido_paterno', 'Apellido paterno'),
            ('apellido_materno', 'Apellido materno'), ('email', 'Correo electrónico'),
            ('password', 'Nueva contraseña'), ('password_confirmacion', 'Confirmar nueva contraseña'),
            ('password_actual', 'Contraseña actual'),
        ], fila_inicial=1)
        self.boton_guardar = ttk.Button(perfil, text='Guardar cambios', style='Primario.TButton',
                                        command=self._guardar)
        self.boton_guardar.grid(row=8, column=1, sticky='e', pady=(12, 0))
        self.msg_perfil = Mensaje(perfil, fondo=SUP, ancho=460)
        self.msg_perfil.grid(row=9, column=0, columnspan=2, sticky='w', pady=(10, 0))

        self._mostrar_usuario()

    # ------------------------------------------------------------------
    def al_mostrar(self) -> None:
        self._mostrar_usuario()

    def _mostrar_usuario(self) -> None:
        sesion = self.app.auth.sesion
        if sesion is None:
            return
        u = sesion.usuario
        self.datos['nombre_completo'].configure(text=sesion.nombre_completo)
        self.datos['email'].configure(text=u.get('email', ''))
        self.datos['rol'].configure(text=u.get('rol', ''))
        verificado = u.get('email_verificado')
        self.datos['email_verificado'].configure(text='Sí' if verificado else 'No',
                                                 fg=COLOR['exito'] if verificado else COLOR['aviso'])
        self.datos['duracion'].configure(text=f"{sesion.duracion_minutos} minutos")
        self.actualizar_reloj(sesion.segundos_restantes())
        for clave in CAMPOS_NOMBRE:
            self.perfil[clave].delete(0, 'end')
            self.perfil[clave].insert(0, u.get(clave) or '')

    def actualizar_reloj(self, restantes: int) -> None:
        self.datos['expira'].configure(text=mmss(restantes))

    # ------------------------------------------------------------------
    def _consultar(self) -> None:
        self.msg_sesion.mostrar('Consultando GET /session…')

        def listo(r):
            if not isinstance(r, ApiResult):
                self.msg_sesion.mostrar(f"Error inesperado: {r}", 'error')
            elif not r.ok:
                self.msg_sesion.mostrar(r.mensaje, 'error')
            elif not r.data.get('autenticado'):
                self.app.sesion_terminada('El servidor indica que la sesión ya no es válida.')
            else:
                self._mostrar_usuario()
                self.msg_sesion.mostrar(f"Sesión vigente según el servidor (HTTP {r.status}).", 'exito')
        self.app.runner.run(self.app.auth.consultar_sesion, al_terminar=listo)

    def _extender(self) -> None:
        self.msg_sesion.mostrar('Solicitando POST /token/refresh…')

        def listo(r):
            if isinstance(r, ApiResult) and r.ok:
                self._mostrar_usuario()
                self.msg_sesion.mostrar(f"JWT renovado con el refresh token (HTTP {r.status}); "
                                        'el anterior quedó revocado en Redis.', 'exito')
            elif isinstance(r, ApiResult):
                self.msg_sesion.mostrar(r.mensaje, 'error')
        self.app.renovar_token(al_terminar=listo)

    def _guardar(self) -> None:
        actual = self.app.auth.sesion.usuario
        valores = {k: e.get().strip() for k, e in self.perfil.items()}

        cambios = {}
        for clave in CAMPOS_NOMBRE:
            if valores[clave] != (actual.get(clave) or ''):
                cambios[clave] = valores[clave]
        if valores['password']:
            if valores['password'] != valores['password_confirmacion']:
                self.msg_perfil.mostrar('La nueva contraseña y su confirmación no coinciden.', 'aviso')
                return
            cambios['password'] = valores['password']

        if not cambios:
            self.msg_perfil.mostrar('No modificaste ningún campo: no hay nada que enviar.', 'aviso')
            return
        if ('email' in cambios or 'password' in cambios):
            if not valores['password_actual']:
                self.msg_perfil.mostrar('Para cambiar correo o contraseña escribe tu contraseña actual.', 'aviso')
                return
            cambios['password_actual'] = valores['password_actual']

        self.boton_guardar.state(['disabled'])
        enviados = sorted(k for k in cambios if k != 'password_actual')
        self.msg_perfil.mostrar(f"Enviando PATCH /profile con: {', '.join(enviados)}…")
        self.app.runner.run(self.app.auth.actualizar_perfil, cambios, al_terminar=self._guardado)

    def _guardado(self, r) -> None:
        self.boton_guardar.state(['!disabled'])
        if not isinstance(r, ApiResult):
            self.msg_perfil.mostrar(f"Error inesperado: {r}", 'error')
            return
        if self.app.verificar_sesion(r):
            return
        if not r.ok:
            self.msg_perfil.mostrar(f"{r.mensaje}" + (f" (HTTP {r.status})" if r.status else ''), 'error')
            return
        for clave in ('password', 'password_confirmacion', 'password_actual'):
            self.perfil[clave].delete(0, 'end')
        if r.data.get('sesiones_cerradas'):
            # Cambio de correo o contrasena: el servidor revoco todos los JWT
            # del usuario y cerro sus sesiones en Redis.
            self.app.mostrar_login('Perfil actualizado. Por seguridad se cerraron todas tus sesiones '
                                   '(tokens revocados en Redis): inicia sesión con tus nuevos datos.', 'exito')
            return
        self._mostrar_usuario()
        texto = f"Perfil actualizado (HTTP {r.status}). Campos: {', '.join(r.data['campos_actualizados'])}."
        if r.data.get('correo_verificacion'):
            texto += (' Tu nuevo correo quedó sin verificar: si cierras sesión, no podrás volver a entrar '
                      'hasta ingresar el código que enviamos.')
            self.msg_perfil.mostrar(texto, 'aviso')
        else:
            self.msg_perfil.mostrar(texto, 'exito')
