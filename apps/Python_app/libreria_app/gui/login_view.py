"""
Pantalla inicial: iniciar sesion, crear cuenta y verificar el correo.

Tambien permite abrir la configuracion ANTES de iniciar sesion, porque es
aqui donde se elige contra que servidor (local o remoto) se va a trabajar.
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional

from libreria_app.api.http_client import ApiResult
from libreria_app.gui import theme
from libreria_app.gui.theme import COLOR
from libreria_app.gui.widgets import Mensaje, Semaforo, formulario

SUP = COLOR['superficie']


class LoginView(ttk.Frame):

    def __init__(self, app, mensaje: Optional[str] = None, tipo: str = 'info'):
        super().__init__(app)
        self.app = app

        tarjeta = tk.Frame(self, bg=SUP, padx=36, pady=28, highlightbackground=COLOR['borde'],
                           highlightthickness=1)
        tarjeta.place(relx=0.5, rely=0.5, anchor='center')

        tk.Label(tarjeta, text='📚  Librería en Línea', bg=SUP,
                 font=(theme.FUENTE, 20, 'bold')).pack(anchor='w')
        tk.Label(tarjeta, text='Cliente de escritorio de los microservicios de login y libros',
                 bg=SUP, fg=COLOR['texto_suave']).pack(anchor='w', pady=(2, 12))

        # --- Servidores y su estado ---
        servidores = tk.Frame(tarjeta, bg=SUP)
        servidores.pack(fill='x', pady=(0, 10))
        self.luces = {}
        self.etiquetas = {}
        for fila, (servicio, nombre) in enumerate((('login', 'Login'), ('books', 'Libros'))):
            luz = Semaforo(servidores, 12, fondo=SUP)
            luz.grid(row=fila, column=0, padx=(0, 6), pady=2)
            etiqueta = tk.Label(servidores, bg=SUP, fg=COLOR['texto_suave'], anchor='w')
            etiqueta.grid(row=fila, column=1, sticky='w')
            self.luces[servicio] = luz
            self.etiquetas[servicio] = (nombre, etiqueta)
        ttk.Button(servidores, text='⚙ Configurar servidor', command=self._abrir_configuracion).grid(
            row=0, column=2, rowspan=2, padx=(24, 0))
        self._actualizar_servidores()
        app.al_cambiar_salud(self._salud)

        self.aviso = Mensaje(tarjeta, fondo=SUP, ancho=460)
        self.aviso.pack(anchor='w', pady=(0, 8))
        if mensaje:
            self.aviso.mostrar(mensaje, tipo)

        self.pestanas = ttk.Notebook(tarjeta)
        self.pestanas.pack(fill='both')
        self._pestana_login()
        self._pestana_registro()
        self._pestana_verificacion()

    def destroy(self):
        self.app.quitar_oyente_salud(self._salud)
        super().destroy()

    # ------------------------------------------------------------------
    def _actualizar_servidores(self) -> None:
        for servicio, (nombre, etiqueta) in self.etiquetas.items():
            etiqueta.configure(text=f"{nombre}: {self.app.api.url_base(servicio)}")

    def _salud(self, estados) -> None:
        for servicio, estado in estados.items():
            self.luces[servicio].fijar(estado.nivel)
        self._actualizar_servidores()

    def _abrir_configuracion(self) -> None:
        from libreria_app.gui.config_view import ConfigView
        ventana = tk.Toplevel(self)
        ventana.title('Configuración del servidor')
        ventana.transient(self.app)
        ventana.configure(bg=COLOR['fondo'], padx=16, pady=16)
        ConfigView(ventana, self.app, al_guardar=lambda: (self._actualizar_servidores(), ventana.destroy())
                   ).pack(fill='both', expand=True)

    def _pagina(self, titulo: str) -> tk.Frame:
        marco = tk.Frame(self.pestanas, bg=SUP, padx=16, pady=14)
        self.pestanas.add(marco, text=titulo)
        return marco

    # ------------------------------------------------------------------
    # Iniciar sesion: POST /login
    # ------------------------------------------------------------------
    def _pestana_login(self) -> None:
        pagina = self._pagina('Iniciar sesión')
        self.login = formulario(pagina, [('email', 'Correo electrónico'), ('password', 'Contraseña')])
        self.boton_login = ttk.Button(pagina, text='Iniciar sesión', style='Primario.TButton',
                                      command=self._iniciar_sesion)
        self.boton_login.grid(row=2, column=1, sticky='e', pady=(10, 0))
        self.msg_login = Mensaje(pagina, fondo=SUP, ancho=440)
        self.msg_login.grid(row=3, column=0, columnspan=2, sticky='w', pady=(10, 0))
        self.boton_ir_verificar = ttk.Button(pagina, text='Ir a verificar mi correo',
                                             command=lambda: self._ir_a_verificar(self.login['email'].get()))
        for entrada in self.login.values():
            entrada.bind('<Return>', lambda e: self._iniciar_sesion())
        self.login['email'].focus_set()

    def _iniciar_sesion(self) -> None:
        email = self.login['email'].get().strip()
        password = self.login['password'].get()
        self.boton_ir_verificar.grid_remove()
        if not email or not password:
            self.msg_login.mostrar('Escribe tu correo y tu contraseña.', 'aviso')
            return
        self.boton_login.state(['disabled'])
        self.msg_login.mostrar('Conectando con el servicio de login…')
        self.app.runner.run(self.app.auth.iniciar_sesion, email, password, al_terminar=self._login_listo)

    def _login_listo(self, r) -> None:
        if not self.winfo_exists():
            return
        self.boton_login.state(['!disabled'])
        if isinstance(r, Exception):
            self.msg_login.mostrar(f"Error inesperado: {r}", 'error')
            return
        if r.ok:
            self.app.mostrar_panel()
            return
        if r.codigo == 'ERR_CREDENCIALES_INVALIDAS':
            self.msg_login.mostrar('Correo o contraseña incorrectos (HTTP 401).', 'error')
        elif r.codigo == 'ERR_CORREO_NO_VERIFICADO':
            self.msg_login.mostrar(
                'Tu cuenta existe, pero todavía no puede iniciar sesión: falta verificar tu correo '
                '(HTTP 403). Ingresa el código que te enviamos.', 'aviso')
            self.boton_ir_verificar.grid(row=4, column=0, columnspan=2, sticky='w', pady=(6, 0))
        elif r.codigo == 'ERR_CUENTA_INACTIVA':
            self.msg_login.mostrar('Esta cuenta está desactivada (HTTP 403).', 'error')
        else:
            self.msg_login.mostrar(r.mensaje, 'error')

    # ------------------------------------------------------------------
    # Crear cuenta: POST /register
    # ------------------------------------------------------------------
    def _pestana_registro(self) -> None:
        pagina = self._pagina('Crear cuenta')
        self.registro = formulario(pagina, [
            ('nombre', 'Nombre *'), ('apellido_paterno', 'Apellido paterno *'),
            ('apellido_materno', 'Apellido materno'), ('email', 'Correo electrónico *'),
            ('password', 'Contraseña * (mín. 8)'), ('password_confirmacion', 'Confirmar contraseña *'),
        ])
        self.boton_registro = ttk.Button(pagina, text='Crear cuenta', style='Primario.TButton',
                                         command=self._registrar)
        self.boton_registro.grid(row=6, column=1, sticky='e', pady=(10, 0))
        self.msg_registro = Mensaje(pagina, fondo=SUP, ancho=440)
        self.msg_registro.grid(row=7, column=0, columnspan=2, sticky='w', pady=(10, 0))

    def _registrar(self) -> None:
        datos = {k: e.get().strip() for k, e in self.registro.items() if k != 'password_confirmacion'}
        datos['password'] = self.registro['password'].get()

        # Verificaciones previas solo para ahorrar un viaje al servidor; las
        # reglas reales las aplica el microservicio.
        faltan = [k for k in ('nombre', 'apellido_paterno', 'email', 'password') if not datos[k]]
        if faltan:
            self.msg_registro.mostrar('Completa los campos marcados con *.', 'aviso')
            return
        if datos['password'] != self.registro['password_confirmacion'].get():
            self.msg_registro.mostrar('Las contraseñas no coinciden.', 'aviso')
            return

        self.boton_registro.state(['disabled'])
        self.msg_registro.mostrar('Registrando en el servicio de login…')
        self.app.runner.run(self.app.auth.registrar, datos, al_terminar=self._registro_listo)

    def _registro_listo(self, r) -> None:
        if not self.winfo_exists():
            return
        self.boton_registro.state(['!disabled'])
        if isinstance(r, Exception):
            self.msg_registro.mostrar(f"Error inesperado: {r}", 'error')
            return
        if not r.ok:
            self.msg_registro.mostrar(f"{r.mensaje} (HTTP {r.status})" if r.status else r.mensaje, 'error')
            return

        correo = r.data.get('correo_verificacion', {})
        email = r.data['usuario']['email']
        if correo.get('enviado'):
            texto = f"Cuenta creada (HTTP 201). Enviamos un código de verificación a {email}."
        else:
            texto = (f"Cuenta creada (HTTP 201), pero el correo no se pudo enviar: "
                     f"{correo.get('detalle')}.")
        for entrada in self.registro.values():
            entrada.delete(0, 'end')
        self._ir_a_verificar(email, texto)

    # ------------------------------------------------------------------
    # Verificar correo: GET /verify?token=...
    # ------------------------------------------------------------------
    def _pestana_verificacion(self) -> None:
        pagina = self._pagina('Verificar correo')
        tk.Label(pagina, text='Pega el código que recibiste por correo al registrarte.',
                 bg=SUP, fg=COLOR['texto_suave']).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 8))
        self.verificacion = formulario(pagina, [('token', 'Código de verificación')], ancho=48, fila_inicial=1)
        self.boton_verificar = ttk.Button(pagina, text='Verificar correo', style='Primario.TButton',
                                          command=self._verificar)
        self.boton_verificar.grid(row=2, column=1, sticky='e', pady=(10, 0))
        self.msg_verificacion = Mensaje(pagina, fondo=SUP, ancho=440)
        self.msg_verificacion.grid(row=3, column=0, columnspan=2, sticky='w', pady=(10, 0))
        self.email_pendiente = ''

    def _ir_a_verificar(self, email: str, texto: Optional[str] = None) -> None:
        self.email_pendiente = email
        self.pestanas.select(2)
        self.msg_verificacion.mostrar(texto or f"Ingresa el código enviado a {email}.",
                                      'exito' if texto else 'info')
        self.verificacion['token'].focus_set()

    def _verificar(self) -> None:
        token = self.verificacion['token'].get().strip()
        if not token:
            self.msg_verificacion.mostrar('Pega el código de verificación.', 'aviso')
            return
        self.boton_verificar.state(['disabled'])
        self.msg_verificacion.mostrar('Verificando…')
        self.app.runner.run(self.app.auth.verificar_correo, token, al_terminar=self._verificacion_lista)

    def _verificacion_lista(self, r) -> None:
        if not self.winfo_exists():
            return
        self.boton_verificar.state(['!disabled'])
        if isinstance(r, Exception):
            self.msg_verificacion.mostrar(f"Error inesperado: {r}", 'error')
            return
        if not r.ok:
            self.msg_verificacion.mostrar(f"{r.mensaje} (HTTP {r.status})" if r.status else r.mensaje, 'error')
            return
        email = r.data['usuario']['email']
        self.verificacion['token'].delete(0, 'end')
        self.pestanas.select(0)
        self.login['email'].delete(0, 'end')
        self.login['email'].insert(0, email)
        self.login['password'].focus_set()
        self.msg_login.mostrar(f"Correo {email} verificado. Ya puedes iniciar sesión.", 'exito')
