"""
Usuarios y roles (microservicio users :5004). Solo administradores: el
listado es una lectura administrativa y el servicio exige JWT con role_id 1.

Cambiar contrasena, correo, rol o estado de un usuario revoca TODOS sus
tokens (jwt:revoked_before:<user_id> en Redis) en los seis servicios.
"""
from tkinter import ttk
from typing import Any, Dict, List

from libreria_app.gui.crud_view import Campo, VistaRecurso

ROLES = ['1 - administrador', '2 - cliente']


def _rol_texto(role_id) -> str:
    return next((r for r in ROLES if r.startswith(f'{role_id} ')), '')


class UsersView(VistaRecurso):
    titulo = 'Usuarios'
    subtitulo = 'GET/POST /users · PATCH/DELETE /users/{id} · microservicio users :5004 · requiere JWT de administrador'
    columnas = (('email', 'Correo', 210), ('nombre_completo', 'Nombre', 170), ('rol', 'Rol', 100),
                ('activo', 'Activo', 60), ('verificado', 'Verificado', 75))
    clave_lista = 'usuarios'
    nombre_singular = 'usuario'

    def __init__(self, parent, app, panel):
        super().__init__(parent, app, panel)
        if not app.auth.sesion.es_administrador:
            self.mostrar_aviso('Tu cuenta tiene rol «cliente»: la administración de usuarios es solo para administradores '
                               '(el microservicio users respondería HTTP 403).')

    def definir_campos(self) -> List[Campo]:
        return [Campo('nombre', 'Nombre'), Campo('apellido_paterno', 'Apellido paterno'),
                Campo('apellido_materno', 'Apellido materno'), Campo('email', 'Correo'),
                Campo('password', 'Contraseña (vacía = no cambiar)', 'password'),
                Campo('role_id', 'Rol', 'combo', ROLES), Campo('activo', 'Activo', 'bool'),
                Campo('email_verificado', 'Correo verificado', 'bool')]

    def construir_barra(self, barra) -> None:
        ttk.Label(barra, text='Buscar (nombre o correo):').pack(side='left')
        self.busqueda = ttk.Entry(barra, width=24)
        self.busqueda.pack(side='left', padx=6)
        self.busqueda.bind('<Return>', lambda e: self.recargar())
        ttk.Button(barra, text='Buscar', command=self.recargar).pack(side='left')

    def leer_filtros(self):
        return {'q': self.busqueda.get().strip() or None}

    def llamar_listar(self):
        return self.app.users.listar(self.filtros)

    def llamar_detalle(self, ident):
        return self.app.users.detalle(ident)

    def llamar_crear(self, datos):
        return self.app.users.crear(datos)

    def llamar_modificar(self, ident, cambios):
        return self.app.users.modificar(ident, cambios)

    def llamar_eliminar(self, ident):
        return self.app.users.eliminar(ident)

    def convertir_id(self, ident: str):
        return ident                                      # UUID

    def valores_fila(self, r: Dict[str, Any]):
        nombre = ' '.join(p for p in (r.get('nombre'), r.get('apellido_paterno')) if p)
        return (r['email'], nombre, r.get('rol'), 'sí' if r.get('activo') else 'no',
                'sí' if r.get('email_verificado') else 'no')

    def desde_registro(self, r: Dict[str, Any]) -> Dict[str, Any]:
        return {**{c.clave: r.get(c.clave) for c in self.campos}, 'password': '', 'role_id': _rol_texto(r.get('role_id'))}

    def a_cuerpo(self, valores: Dict[str, Any], crear: bool) -> Dict[str, Any]:
        cuerpo = dict(valores)
        if 'role_id' in cuerpo:
            if not cuerpo['role_id']:
                cuerpo.pop('role_id')
            else:
                cuerpo['role_id'] = int(cuerpo['role_id'].split(' ')[0])
        if not cuerpo.get('password'):
            cuerpo.pop('password', None)
        if 'apellido_materno' in cuerpo and not cuerpo['apellido_materno']:
            cuerpo['apellido_materno'] = None
        if crear:
            cuerpo = {k: v for k, v in cuerpo.items() if v not in ('', None)}
        return cuerpo

    def registro_de_respuesta(self, datos):
        return datos.get('usuario')

    def descripcion(self, registro):
        return registro.get('email', '')

    def puede_eliminar(self, registro) -> bool:
        return (self.app.auth.sesion.es_administrador and registro is not None
                and str(registro.get('id')) != self.app.auth.sesion.user_id)
