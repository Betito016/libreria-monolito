"""
Microservicio users: administra usuarios, roles, correos y contrasenas.

Stack: Flask + Psycopg 3 + PostgreSQL (library_db) + Redis. Puerto 5004.
XML por defecto, JSON con ?format=json.

    GET    /roles          Catalogo de roles                        (publico)
    GET    /users          Listado con filtros q, role_id, activo   (JWT administrador: lectura administrativa)
    GET    /users/{id}     Detalle                                  (JWT: administrador o el propio usuario)
    POST   /users          Crear usuario con rol                    (JWT administrador)
    PATCH  /users/{id}     Modificar datos, rol, contrasena, estado (JWT administrador)
    DELETE /users/{id}     Eliminar                                 (JWT administrador)
    GET    /health, /metrics

Cambiar la contrasena, el correo, el rol o desactivar/eliminar a un usuario
revoca TODOS sus tokens (jwt:revoked_before:<user_id> en Redis): los demas
servicios los rechazaran aunque no hayan expirado, y login no dejara renovar
sus sesiones.
"""
from datetime import datetime, timezone

import bcrypt
from flask import g, request

import config
from libreria_common.bd import BaseDatos, dsn
from libreria_common.flask_base import ServicioBase
from libreria_common.respuestas import api_response, leer_json
from libreria_common.seguridad import AuthError, ROL_ADMINISTRADOR, revocar_usuario
from libreria_common.validacion import (ValidacionError, correo, entero, requeridos, solo_campos, texto)
from repositorio import RepositorioUsuarios

servicio = ServicioBase.crear('users', __name__)
app, logger = servicio.app, servicio.logger
bd = BaseDatos(dsn(config.DB_HOST, config.DB_PORT, config.DB_NAME, config.DB_USER, config.DB_PASSWORD), config.DB_NAME)
repo = RepositorioUsuarios(bd)
solo_admin = servicio.auth.requiere_jwt(roles=[ROL_ADMINISTRADOR])
autenticado = servicio.auth.requiere_jwt()

CAMPOS = ('nombre', 'apellido_paterno', 'apellido_materno', 'email', 'password', 'role_id', 'activo',
          'email_verificado')
# Cambios que invalidan los tokens vigentes del usuario.
SENSIBLES = ('password', 'email', 'role_id', 'activo')


def _hash(password: str) -> str:
    if not isinstance(password, str) or len(password) < config.PASSWORD_MIN:
        raise ValidacionError('ERR_PASSWORD_DEBIL', f'La contraseña debe tener al menos {config.PASSWORD_MIN} caracteres.',
                              campo_invalido='password')
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def _booleano(datos, campo):
    valor = datos.get(campo)
    if valor is not None and not isinstance(valor, bool):
        raise ValidacionError('ERR_TIPO_INVALIDO', f"El campo '{campo}' debe ser true o false.", campo_invalido=campo)
    return valor


def _paginacion():
    try:
        page = max(1, int(request.args.get('page', 1)))
        size = min(config.PAGE_SIZE_MAX, max(1, int(request.args.get('page_size', config.PAGE_SIZE_DEFAULT))))
    except ValueError:
        raise ValidacionError('ERR_FILTRO_INVALIDO', 'page y page_size deben ser enteros.')
    return page, size


# ----------------------------------------------------------------------
@app.route('/health', methods=['GET'])
def health():
    postgres, redis_estado = bd.ping(), servicio.redis.estado()
    return api_response('health', {
        'estado': 'ok' if postgres['conectado'] and redis_estado['disponible'] else 'degradado',
        'microservicio': 'users', 'postgresql': postgres, 'redis': redis_estado,
        'capacidades': {'lectura': postgres['conectado'] and redis_estado['disponible'],
                        'escritura': postgres['conectado'] and redis_estado['disponible']},
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }, status=200 if postgres['conectado'] else 503)


@app.route('/roles', methods=['GET'])
def roles():
    filas = repo.roles()
    return api_response('roles', {'total': len(filas), 'roles': filas})


@app.route('/users', methods=['GET'])
@solo_admin
def listar():
    page, size = _paginacion()
    role_id = request.args.get('role_id')
    activo = request.args.get('activo')
    resultado = repo.listar((request.args.get('q') or '').strip() or None,
                            int(role_id) if role_id and role_id.isdigit() else None,
                            None if activo in (None, '') else activo.lower() in ('true', '1'), page, size)
    return api_response('usuarios', {**resultado, 'page': page, 'page_size': size,
                                     'total_pages': max(1, (resultado['total'] + size - 1) // size)})


@app.route('/users/<user_id>', methods=['GET'])
@autenticado
def detalle(user_id):
    if g.usuario['role_id'] != ROL_ADMINISTRADOR and g.usuario['user_id'] != user_id:
        raise AuthError('ERR_SIN_PERMISOS', 'Solo puedes consultar tu propio usuario.', 403)
    return api_response('usuario', repo.obtener(user_id))


@app.route('/users', methods=['POST'])
@solo_admin
def crear():
    datos = leer_json()
    solo_campos(datos, CAMPOS)
    requeridos(datos, ('nombre', 'apellido_paterno', 'email', 'password'))
    nuevo = {
        'nombre': texto(datos, 'nombre', 120, True), 'apellido_paterno': texto(datos, 'apellido_paterno', 120, True),
        'apellido_materno': texto(datos, 'apellido_materno', 120), 'email': correo(datos, 'email', True),
        'password_hash': _hash(datos['password']),
        'role_id': entero(datos, 'role_id', 1, 32767) or 2,
        'activo': True if _booleano(datos, 'activo') is None else datos['activo'],
        # Lo crea un administrador: no hace falta verificar el correo, salvo que se indique.
        'email_verificado': True if _booleano(datos, 'email_verificado') is None else datos['email_verificado'],
    }
    usuario = repo.crear(nuevo)
    logger.info(f"    Operacion realizada: POST /users {usuario['email']} (role_id {usuario['role_id']}) "
                f"por {g.usuario['email']}")
    return api_response('resultado', {'estado': 'exito', 'mensaje': 'Usuario creado.', 'metodo': 'POST',
                                      'realizado_por': g.usuario['email'], 'usuario': usuario},
                        status=201, headers={'Location': f"/users/{usuario['id']}"})


@app.route('/users/<user_id>', methods=['PATCH'])
@solo_admin
def modificar(user_id):
    datos = leer_json()
    solo_campos(datos, CAMPOS)
    if not datos:
        raise ValidacionError('ERR_SIN_CAMBIOS', 'No se envió ningún campo para modificar.')
    if user_id == g.usuario['user_id'] and (datos.get('activo') is False or datos.get('role_id') not in (None, ROL_ADMINISTRADOR)):
        raise ValidacionError('ERR_AUTO_BLOQUEO', 'No puedes quitarte el rol de administrador ni desactivar tu propia cuenta.')
    cambios = {}
    for campo, maximo in (('nombre', 120), ('apellido_paterno', 120)):
        if campo in datos:
            cambios[campo] = texto(datos, campo, maximo, True)
    if 'apellido_materno' in datos:
        cambios['apellido_materno'] = texto(datos, 'apellido_materno', 120) if datos['apellido_materno'] else None
    if 'email' in datos:
        cambios['email'] = correo(datos, 'email', True)
    if 'password' in datos:
        cambios['password_hash'] = _hash(datos['password'])
    if 'role_id' in datos:
        cambios['role_id'] = entero(datos, 'role_id', 1, 32767)
    for campo in ('activo', 'email_verificado'):
        if campo in datos:
            cambios[campo] = _booleano(datos, campo)

    usuario = repo.modificar(user_id, cambios)
    revocados = any(c in datos for c in SENSIBLES)
    if revocados:
        revocar_usuario(servicio.redis, user_id, servicio.config.access_token_minutos)
    logger.info(f"    Operacion realizada: PATCH /users/{user_id} ({', '.join(sorted(datos))}) por {g.usuario['email']}"
                f"{' -> tokens del usuario revocados' if revocados else ''}")
    return api_response('resultado', {
        'estado': 'exito', 'mensaje': 'Usuario modificado.' + (' Sus sesiones y tokens anteriores quedaron revocados.'
                                                                if revocados else ''),
        'metodo': 'PATCH', 'campos_actualizados': sorted(datos), 'tokens_revocados': revocados,
        'realizado_por': g.usuario['email'], 'usuario': usuario})


@app.route('/users/<user_id>', methods=['DELETE'])
@solo_admin
def eliminar(user_id):
    if user_id == g.usuario['user_id']:
        raise ValidacionError('ERR_AUTO_BLOQUEO', 'No puedes eliminar tu propia cuenta.')
    usuario = repo.eliminar(user_id)
    revocar_usuario(servicio.redis, user_id, servicio.config.access_token_minutos)
    logger.info(f"    Operacion realizada: DELETE /users/{user_id} ({usuario['email']}) por {g.usuario['email']}")
    return api_response('resultado', {'estado': 'exito', 'mensaje': f"Usuario {usuario['email']} eliminado.",
                                      'metodo': 'DELETE', 'id': user_id, 'realizado_por': g.usuario['email']})


@app.route('/', methods=['GET'])
def index():
    return api_response('microservicio', {
        'nombre': 'Microservicio de Usuarios', 'version': '1.0.0', 'formato_por_defecto': 'xml',
        'endpoints_publicos': ['GET /health', 'GET /metrics', 'GET /roles'],
        'endpoints_protegidos': ['GET /users (admin)', 'GET /users/{id} (admin o propio)', 'POST /users (admin)',
                                 'PATCH /users/{id} (admin)', 'DELETE /users/{id} (admin)'],
    })


if __name__ == '__main__':
    logger.info(f"Microservicio de usuarios en http://{config.HOST}:{config.PORT} (Redis {servicio.redis.destino})")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
