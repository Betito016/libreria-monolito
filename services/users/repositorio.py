"""
Acceso a library_db para el microservicio users (tablas usuarios y roles).

usuarios.rol sigue siendo el enum que usa el monolito; el role_id sale del
catalogo roles. Escribir un role_id actualiza usuarios.rol con el nombre
correspondiente.
"""
import uuid
from typing import Any, Dict, List, Optional

import psycopg
from psycopg import sql

from libreria_common.bd import BaseDatos
from libreria_common.validacion import Conflicto, NoEncontrado, ValidacionError

COLUMNAS = """u.id, u.nombre, u.apellido_paterno, u.apellido_materno, u.email, u.rol,
              r.id AS role_id, u.activo, u.email_verificado, u.fecha_registro, u.actualizado_en"""
DESDE = "FROM usuarios u JOIN roles r ON r.nombre = u.rol::text"
EDITABLES = ('nombre', 'apellido_paterno', 'apellido_materno', 'email', 'password_hash', 'activo', 'email_verificado')


def _publico(fila: Dict[str, Any]) -> Dict[str, Any]:
    fila = dict(fila)
    fila['id'] = fila['user_id'] = str(fila['id'])
    for campo in ('fecha_registro', 'actualizado_en'):
        if fila.get(campo) is not None:
            fila[campo] = fila[campo].isoformat()
    return fila


def _conflicto(exc: psycopg.errors.UniqueViolation, email: Optional[str]) -> Conflicto:
    if 'administrador' in str(exc) or 'ux_un_solo_administrador' in str(exc):
        return Conflicto('ERR_UN_SOLO_ADMINISTRADOR',
                         'Ya existe un administrador: el sistema solo admite uno (regla del esquema).')
    return Conflicto('ERR_EMAIL_DUPLICADO', f"El correo '{email}' ya está registrado.")


class RepositorioUsuarios:

    def __init__(self, bd: BaseDatos):
        self.bd = bd

    def roles(self) -> List[Dict[str, Any]]:
        with self.bd.cursor() as cur:
            cur.execute('SELECT id AS role_id, nombre, descripcion FROM roles ORDER BY id')
            return cur.fetchall()

    def _nombre_rol(self, cur, role_id: int) -> str:
        cur.execute('SELECT nombre FROM roles WHERE id = %s', (role_id,))
        fila = cur.fetchone()
        if not fila:
            raise ValidacionError('ERR_ROL_INVALIDO', f'No existe el role_id {role_id}.', campo_invalido='role_id')
        return fila['nombre']

    def listar(self, texto: Optional[str], role_id: Optional[int], activo: Optional[bool],
               page: int, page_size: int) -> Dict[str, Any]:
        condiciones, parametros = [], []
        if texto:
            condiciones.append("(u.nombre ILIKE %s OR u.apellido_paterno ILIKE %s OR u.email ILIKE %s)")
            parametros += [f'%{texto}%'] * 3
        if role_id is not None:
            condiciones.append('r.id = %s'); parametros.append(role_id)
        if activo is not None:
            condiciones.append('u.activo = %s'); parametros.append(activo)
        donde = ('WHERE ' + ' AND '.join(condiciones)) if condiciones else ''
        with self.bd.cursor() as cur:
            cur.execute(f'SELECT count(*) AS n {DESDE} {donde}', parametros)
            total = cur.fetchone()['n']
            cur.execute(f'SELECT {COLUMNAS} {DESDE} {donde} ORDER BY u.fecha_registro, u.email LIMIT %s OFFSET %s',
                        parametros + [page_size, (page - 1) * page_size])
            return {'total': total, 'usuarios': [_publico(f) for f in cur.fetchall()]}

    def obtener(self, user_id: str) -> Dict[str, Any]:
        try:
            uuid.UUID(str(user_id))
        except ValueError:
            raise NoEncontrado(f'No existe el usuario {user_id}.')
        with self.bd.cursor() as cur:
            cur.execute(f'SELECT {COLUMNAS} {DESDE} WHERE u.id = %s', (user_id,))
            fila = cur.fetchone()
        if not fila:
            raise NoEncontrado(f'No existe el usuario {user_id}.')
        return _publico(fila)

    def crear(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with self.bd.cursor() as cur:
                rol = self._nombre_rol(cur, datos['role_id'])
                cur.execute(
                    """INSERT INTO usuarios (nombre, apellido_paterno, apellido_materno, email, password_hash,
                                             rol, activo, email_verificado)
                       VALUES (%s, %s, %s, %s, %s, %s::rol_usuario, %s, %s) RETURNING id""",
                    (datos['nombre'], datos['apellido_paterno'], datos.get('apellido_materno'), datos['email'],
                     datos['password_hash'], rol, datos['activo'], datos['email_verificado']))
                nuevo = cur.fetchone()['id']
        except psycopg.errors.UniqueViolation as exc:
            raise _conflicto(exc, datos.get('email'))
        return self.obtener(str(nuevo))

    def modificar(self, user_id: str, cambios: Dict[str, Any]) -> Dict[str, Any]:
        self.obtener(user_id)                                    # 404 si no existe
        try:
            with self.bd.cursor() as cur:
                asignaciones, valores = [], []
                for campo in EDITABLES:
                    if campo in cambios:
                        asignaciones.append(sql.SQL('{} = %s').format(sql.Identifier(campo)))
                        valores.append(cambios[campo])
                if 'role_id' in cambios:
                    asignaciones.append(sql.SQL('rol = %s::rol_usuario'))
                    valores.append(self._nombre_rol(cur, cambios['role_id']))
                consulta = sql.SQL('UPDATE usuarios SET {}, actualizado_en = now() WHERE id = %s').format(
                    sql.SQL(', ').join(asignaciones))
                cur.execute(consulta, valores + [user_id])
        except psycopg.errors.UniqueViolation as exc:
            raise _conflicto(exc, cambios.get('email'))
        return self.obtener(user_id)

    def eliminar(self, user_id: str) -> Dict[str, Any]:
        usuario = self.obtener(user_id)
        try:
            with self.bd.cursor() as cur:
                cur.execute('DELETE FROM verificaciones_email WHERE usuario_id = %s', (user_id,))
                cur.execute('DELETE FROM usuarios WHERE id = %s', (user_id,))
        except psycopg.errors.ForeignKeyViolation:
            raise Conflicto('ERR_USUARIO_EN_USO', 'El usuario tiene información asociada y no puede eliminarse; '
                                                  'desactívalo con PATCH {"activo": false}.')
        return usuario
