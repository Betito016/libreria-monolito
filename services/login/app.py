"""
Microservicio de autenticacion de la Libreria.

Stack: Python + Flask + Psycopg 3 + PostgreSQL (library_db) + Redis.
Responde en XML por defecto y en JSON con ?format=json.

Endpoints:
    POST  /register        Registrar un nuevo usuario                       (publico)
    GET   /verify          Canjear el token de verificacion de correo       (publico)
    POST  /login           Validar credenciales, crear sesion y emitir JWT  (publico)
    POST  /token/refresh   Renovar el JWT con el refresh token (rotacion)    (refresh token)
    POST  /session/extend  Renovar el JWT con la cookie de sesion           (cookie)
    GET   /session         Estado de la sesion y del usuario                (cookie)
    POST  /logout          Revocar el JWT y borrar sesion y refresh token   (publico)
    PATCH /profile         Modificar el propio perfil                       (Bearer JWT)
    GET   /health          Estado del servicio, PostgreSQL y Redis          (publico)
    GET   /metrics         Metricas del servicio                            (publico)

Redis (capa compartida):
    session:<sid>, refresh:<sha256>, user:sessions:<user_id>   sesiones y refresh tokens
    jwt:revoked:<jti>, jwt:revoked_before:<user_id>            lista de revocacion
Si Redis no responde, login/refresh/logout/session responden 503 (falla segura).
"""
from datetime import datetime, timezone

import jwt
from flask import g, jsonify, request

from config.config import Config
from api.responses import api_response, error_response, parse_request_body
from api.openapi import build_openapi_spec, SWAGGER_UI_HTML
from auth.email_validator import validate_email
from auth.jwt_tokens import descripcion_segura, emitir_access_token
from auth.mailer import enviar_verificacion, generar_token, hash_token
from auth.passwords import hash_password, verify_password, validate_password_strength
from auth.sesiones import AlmacenSesiones
from db.database import UserRepository, EmailAlreadyRegisteredError, DatabaseUnavailableError
from libreria_common.flask_base import ServicioBase
from libreria_common.seguridad import revocar_jti, revocar_usuario

servicio = ServicioBase.crear('login', __name__)
app, logger, config = servicio.app, servicio.logger, servicio.config
sesiones = AlmacenSesiones(servicio.redis, Config.SESSION_TTL_MINUTES)

CAMPOS_REGISTRO = ('nombre', 'apellido_paterno', 'apellido_materno', 'email', 'password')
CAMPOS_PERFIL = ('nombre', 'apellido_paterno', 'apellido_materno', 'email', 'password')


def _usuario_publico(row: dict) -> dict:
    """Proyeccion segura de un usuario: nunca incluye password_hash."""
    return {
        'id': str(row['id']),
        'user_id': str(row['id']),
        'nombre': row['nombre'],
        'apellido_paterno': row.get('apellido_paterno'),
        'apellido_materno': row.get('apellido_materno'),
        'email': row['email'],
        'rol': row['rol'],
        'role_id': row.get('role_id'),
        'activo': row.get('activo', True),
        'email_verificado': row.get('email_verificado', False),
    }


@app.errorhandler(DatabaseUnavailableError)
def _error_bd(_exc=None):
    return error_response('ERR_BASE_DATOS', 'El servicio de base de datos no está disponible.', status=503)


def _enviar_token(usuario: dict) -> dict:
    """Genera un token de verificacion, lo registra y lo envia por correo."""
    token, token_hash = generar_token()
    registro = UserRepository.create_verification_token(
        usuario_id=usuario['id'], token_hash=token_hash, email_destino=usuario['email'],
        ttl_hours=Config.TOKEN_TTL_HOURS,
    )
    enviado, detalle = enviar_verificacion(destinatario=usuario['email'], nombre=usuario['nombre'], token=token)
    if enviado:
        UserRepository.mark_token_sent(registro['id'])
    return {'enviado': enviado, 'detalle': detalle, 'destinatario': usuario['email'],
            'expira_en': str(registro['expira_en'])}


# ----------------------------------------------------------------------
# Sesion: cookie con el sid + datos en Redis
# ----------------------------------------------------------------------
def _sid_de_cookie():
    return request.cookies.get(Config.SESSION_COOKIE_NAME)


def _poner_cookie(respuesta, sid: str):
    respuesta.set_cookie(Config.SESSION_COOKIE_NAME, sid, max_age=Config.SESSION_TTL_MINUTES * 60,
                         httponly=True, samesite='Lax', secure=Config.SESSION_COOKIE_SECURE)
    return respuesta


def _info_sesion(sesion: dict) -> dict:
    restante_sesion, restante_token = sesiones.tiempos(sesion)
    return {
        'expira_en': datetime.fromtimestamp(int(sesion['exp_access']), tz=timezone.utc).isoformat(),
        'segundos_restantes': restante_token,          # vida del JWT de acceso (20 min)
        'duracion_minutos': config.access_token_minutos,
        'sesion_segundos_restantes': restante_sesion,  # vida de la sesion/refresh en Redis
        'sesion_duracion_minutos': Config.SESSION_TTL_MINUTES,
        'almacen': 'redis',
    }


def _bloque_tokens(access: dict, refresh: str) -> dict:
    return {**{k: access[k] for k in ('access_token', 'token_type', 'algoritmo', 'expira_en_epoch', 'expires_in')},
            'refresh_token': refresh, 'refresh_expires_in': Config.SESSION_TTL_MINUTES * 60}


def _renovar(sesion: dict, usuario: dict, origen: str):
    """Emite un JWT nuevo, rota el refresh token y revoca el JWT anterior."""
    access = emitir_access_token(config, usuario, sesion['sid'])
    refresh = sesiones.rotar(sesion, access)
    revocar_jti(servicio.redis, sesion['jti'], sesion['exp_access'])
    logger.info(f"    {origen}: JWT renovado {descripcion_segura(access['access_token'])}; "
                f"refresh rotado; JWT anterior (jti {sesion['jti'][:8]}…) revocado")
    sesion = sesiones.obtener(sesion['sid'])
    return api_response('sesion', {
        'estado': 'exito', 'mensaje': 'Sesión renovada.', 'usuario': _usuario_publico(usuario),
        'sesion': _info_sesion(sesion), 'token': _bloque_tokens(access, refresh),
    })


def _usuario_valido(user_id: str):
    usuario = UserRepository.find_by_id(user_id)
    if not usuario or not usuario['activo']:
        return None
    return usuario


def _sesion_revocada(sesion: dict) -> bool:
    """El servicio users (o un cambio de contrasena) puede revocar todo lo del
    usuario con jwt:revoked_before:<user_id>; una sesion creada antes de ese
    instante tampoco puede renovarse con su refresh token."""
    limite = servicio.redis.ejecutar(lambda r: r.get(f"jwt:revoked_before:{sesion['user_id']}"), critico=True)
    return bool(limite) and int(sesion['creada']) <= int(limite)


# ----------------------------------------------------------------------
# POST /register
# ----------------------------------------------------------------------
@app.route('/register', methods=['POST', 'OPTIONS'])
def register():
    if request.method == 'OPTIONS':
        return api_response('preflight', {'estado': 'ok'})

    datos = parse_request_body()
    valores = {campo: (datos.get(campo) or '').strip() for campo in CAMPOS_REGISTRO}

    faltantes = [c for c in ('nombre', 'apellido_paterno', 'email', 'password') if not valores[c]]
    if faltantes:
        return error_response('ERR_CAMPOS_OBLIGATORIOS', f"Faltan campos obligatorios: {', '.join(faltantes)}.",
                              status=400, campos_faltantes=faltantes)

    error_password = validate_password_strength(valores['password'])
    if error_password:
        return error_response('ERR_PASSWORD_DEBIL', error_password, status=400)

    email_valido, detalle = validate_email(valores['email'], check_mx=Config.VERIFY_EMAIL_MX)
    if not email_valido:
        return error_response('ERR_EMAIL_INVALIDO', detalle, status=400, campo_invalido='email')

    try:
        # El correo NO se marca como verificado: sintaxis y MX prueban que el
        # dominio recibe correo, no que el buzon sea de quien se registra.
        usuario = UserRepository.create_user(
            nombre=valores['nombre'], apellido_paterno=valores['apellido_paterno'],
            apellido_materno=valores['apellido_materno'] or None, email=valores['email'],
            password_hash=hash_password(valores['password']), email_verificado=False,
        )
        correo = _enviar_token(usuario)
    except EmailAlreadyRegisteredError as exc:
        return error_response('ERR_EMAIL_DUPLICADO', str(exc), status=409, campo_invalido='email')
    except DatabaseUnavailableError as exc:
        logger.error(f"PostgreSQL no disponible durante el registro: {exc}")
        return _error_bd()

    logger.info(f"Usuario registrado: {valores['email']} (correo enviado: {correo['enviado']})")
    return api_response('registro', {
        'estado': 'exito', 'mensaje': 'Usuario registrado. Revisa tu correo para verificar la cuenta.',
        'validacion_dominio': detalle, 'correo_verificacion': correo, 'usuario': _usuario_publico(usuario),
    }, status=201)


# ----------------------------------------------------------------------
# GET|POST /verify
# ----------------------------------------------------------------------
@app.route('/verify', methods=['GET', 'POST', 'OPTIONS'])
def verify():
    """Canjea el token enviado por correo. GET para que el enlace del correo
    funcione desde el navegador, POST para clientes programaticos."""
    if request.method == 'OPTIONS':
        return api_response('preflight', {'estado': 'ok'})

    token = (request.args.get('token') or parse_request_body().get('token') or '').strip()
    if not token:
        return error_response('ERR_TOKEN_FALTANTE', 'Se requiere el token de verificación.', status=400)

    try:
        resultado = UserRepository.redeem_token(hash_token(token))
    except DatabaseUnavailableError:
        return _error_bd()

    if resultado['resultado'] == 'no_existe':
        return error_response('ERR_TOKEN_INVALIDO', 'El token de verificación no es válido.', status=400)
    if resultado['resultado'] == 'ya_usado':
        return error_response('ERR_TOKEN_YA_USADO', 'Este token ya fue utilizado. El correo ya estaba verificado.',
                              status=409)
    if resultado['resultado'] == 'expirado':
        return error_response('ERR_TOKEN_EXPIRADO', 'El token de verificación venció. Solicita uno nuevo.', status=410)

    usuario = resultado['usuario']
    logger.info(f"Correo verificado: {usuario['email']}")
    return api_response('verificacion', {
        'estado': 'exito', 'mensaje': 'Correo verificado correctamente. Ya puedes iniciar sesión.',
        'usuario': _usuario_publico(usuario),
    })


# ----------------------------------------------------------------------
# POST /login
# ----------------------------------------------------------------------
@app.route('/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return api_response('preflight', {'estado': 'ok'})

    datos = parse_request_body()
    email = (datos.get('email') or '').strip()
    password = datos.get('password') or ''
    if not email or not password:
        return error_response('ERR_CREDENCIALES_INCOMPLETAS', 'Se requieren email y password.', status=400)

    try:
        usuario = UserRepository.find_by_email(email)
    except DatabaseUnavailableError as exc:
        logger.error(f"PostgreSQL no disponible durante el login: {exc}")
        return _error_bd()

    # Mismo mensaje para usuario inexistente y password incorrecta: revelar
    # cual de los dos fallo permitiria enumerar correos registrados.
    if not usuario or not verify_password(password, usuario['password_hash']):
        logger.warning(f"    Credenciales invalidas para '{email}'")
        return error_response('ERR_CREDENCIALES_INVALIDAS', 'Correo o contraseña incorrectos.', status=401)

    # Estas dos comprobaciones van DESPUES de validar la contrasena.
    if not usuario['activo']:
        return error_response('ERR_CUENTA_INACTIVA', 'La cuenta está desactivada.', status=403)
    if not usuario['email_verificado']:
        return error_response('ERR_CORREO_NO_VERIFICADO',
                              'Tu correo aún no está verificado. Ingresa el código que te enviamos por correo.',
                              status=403)

    logger.info(f"    Credenciales validas (bcrypt): {usuario['email']} (role_id {usuario['role_id']})")
    sid = sesiones.nuevo_sid()
    access = emitir_access_token(config, usuario, sid)
    refresh = sesiones.crear(usuario, sid, access)          # Redis: critico -> 503 si no responde
    sesion = sesiones.obtener(sid)
    logger.info(f"    Sesion guardada en Redis: session:{sid[:8]}… (TTL {Config.SESSION_TTL_MINUTES} min) "
                f"+ refresh:{'<sha256>'} | JWT emitido {descripcion_segura(access['access_token'])} "
                f"HS256, {config.access_token_minutos} min, jti {access['jti'][:8]}…")
    respuesta = api_response('login', {
        'estado': 'exito', 'mensaje': f"Bienvenido, {usuario['nombre']}.",
        'usuario': _usuario_publico(usuario), 'sesion': _info_sesion(sesion),
        'token': _bloque_tokens(access, refresh),
    })
    return _poner_cookie(respuesta, sid)


# ----------------------------------------------------------------------
# POST /token/refresh
# ----------------------------------------------------------------------
@app.route('/token/refresh', methods=['POST', 'OPTIONS'])
def token_refresh():
    """Renueva el JWT antes de que caduque. El refresh token es de un solo
    uso: se consume y se entrega otro (rotacion)."""
    if request.method == 'OPTIONS':
        return api_response('preflight', {'estado': 'ok'})
    refresh = (parse_request_body().get('refresh_token') or '').strip()
    if not refresh:
        return error_response('ERR_REFRESH_AUSENTE', 'Falta el refresh_token.', status=401)

    sid = sesiones.consumir_refresh(refresh)
    sesion = sesiones.obtener(sid) if sid else None
    if not sesion:
        logger.warning("    Refresh token inexistente, ya usado o expirado")
        return error_response('ERR_REFRESH_INVALIDO',
                              'El refresh token no es válido, ya se usó o la sesión expiró. Inicia sesión de nuevo.',
                              status=401)
    usuario = _usuario_valido(sesion['user_id'])
    if not usuario or _sesion_revocada(sesion):
        sesiones.cerrar(sid)
        return error_response('ERR_SESION_INVALIDA', 'La sesión ya no es válida: inicia sesión de nuevo.', status=401)
    return _renovar(sesion, usuario, 'POST /token/refresh')


# ----------------------------------------------------------------------
# POST /session/extend   (misma renovacion, autenticada con la cookie)
# ----------------------------------------------------------------------
@app.route('/session/extend', methods=['POST', 'OPTIONS'])
def extender_sesion():
    if request.method == 'OPTIONS':
        return api_response('preflight', {'estado': 'ok'})
    sesion = sesiones.obtener(_sid_de_cookie())
    if not sesion:
        return error_response('ERR_SESION_INVALIDA', 'No hay una sesión activa.', status=401)
    usuario = _usuario_valido(sesion['user_id'])
    if not usuario or _sesion_revocada(sesion):
        sesiones.cerrar(sesion['sid'])
        return error_response('ERR_SESION_INVALIDA', 'La sesión ya no es válida.', status=401)
    return _renovar(sesion, usuario, 'POST /session/extend')


# ----------------------------------------------------------------------
# GET /session
# ----------------------------------------------------------------------
@app.route('/session', methods=['GET'])
def consultar_sesion():
    """Introspeccion: siempre 200 si Redis responde, con autenticado true/false."""
    sesion = sesiones.obtener(_sid_de_cookie())
    if not sesion:
        motivo = 'expirada' if _sid_de_cookie() else 'sin_sesion'
        mensaje = 'La sesión expiró.' if motivo == 'expirada' else 'No hay una sesión activa.'
        return api_response('sesion', {'autenticado': False, 'motivo': motivo, 'mensaje': mensaje})
    try:
        usuario = _usuario_valido(sesion['user_id'])
    except DatabaseUnavailableError:
        return _error_bd()
    if not usuario:
        sesiones.cerrar(sesion['sid'])
        return api_response('sesion', {'autenticado': False, 'motivo': 'usuario_invalido',
                                       'mensaje': 'La sesión ya no es válida.'})
    return api_response('sesion', {'autenticado': True, 'usuario': _usuario_publico(usuario),
                                   'sesion': _info_sesion(sesion)})


# ----------------------------------------------------------------------
# POST /logout
# ----------------------------------------------------------------------
@app.route('/logout', methods=['POST', 'OPTIONS'])
def logout():
    """Revoca el JWT presentado (jwt:revoked:<jti>) y borra la sesion y su
    refresh token. Acepta el Bearer, la cookie y/o el refresh_token."""
    if request.method == 'OPTIONS':
        return api_response('preflight', {'estado': 'ok'})

    revocado, sids = None, set()
    autorizacion = request.headers.get('Authorization', '')
    if autorizacion.lower().startswith('bearer '):
        try:
            # Se verifica la firma (nadie puede cerrar sesiones ajenas con un
            # token inventado), pero se acepta un token ya expirado.
            claims = jwt.decode(autorizacion[7:].strip(), config.jwt_secret_key, algorithms=[config.jwt_algorithm],
                                issuer=config.jwt_issuer, options={'verify_exp': False})
            revocar_jti(servicio.redis, claims['jti'], claims['exp'])
            revocado = claims['jti']
            if claims.get('sid'):
                sids.add(claims['sid'])
        except jwt.InvalidTokenError:
            logger.warning("    /logout con un Bearer invalido: se ignora el token")
    if _sid_de_cookie():
        sids.add(_sid_de_cookie())
    refresh = (parse_request_body().get('refresh_token') or '').strip()
    if refresh:
        sid = sesiones.consumir_refresh(refresh)
        if sid:
            sids.add(sid)

    cerradas = [sid for sid in sids if sesiones.cerrar(sid)]
    logger.info(f"    Logout: sesiones borradas de Redis: {len(cerradas)}; "
                f"JWT revocado: {'jti ' + revocado[:8] + '…' if revocado else 'ninguno'}")
    respuesta = api_response('logout', {
        'estado': 'exito',
        'mensaje': 'Sesión cerrada.' if cerradas or revocado else 'No había sesión activa.',
        'sesion_previa': bool(cerradas), 'jwt_revocado': bool(revocado), 'sesiones_cerradas': len(cerradas),
    })
    respuesta.delete_cookie(Config.SESSION_COOKIE_NAME)
    return respuesta


# ----------------------------------------------------------------------
# PATCH /profile   (Bearer JWT)
# ----------------------------------------------------------------------
@app.route('/profile', methods=['PATCH'])
@servicio.auth.requiere_jwt()
def actualizar_perfil():
    """Actualizacion PARCIAL del propio perfil. Cambiar correo o contrasena
    exige la contrasena actual y cierra TODAS las sesiones del usuario."""
    try:
        usuario = UserRepository.find_by_id(g.usuario['user_id'])
    except DatabaseUnavailableError:
        return _error_bd()
    if not usuario or not usuario['activo']:
        return error_response('ERR_SESION_INVALIDA', 'La cuenta ya no está activa.', status=401)

    datos = parse_request_body()
    no_permitidos = [k for k in datos if k not in CAMPOS_PERFIL + ('password_actual',)]
    if no_permitidos:
        # Si alguien envia "rol": "administrador", debe saber que no se acepta.
        return error_response('ERR_CAMPOS_NO_PERMITIDOS',
                              f"Campos no modificables desde el perfil: {', '.join(no_permitidos)}.",
                              status=400, campos_rechazados=no_permitidos)

    recibidos = {k: datos[k] for k in CAMPOS_PERFIL if k in datos}
    if not recibidos:
        return error_response('ERR_SIN_CAMBIOS', 'No se envió ningún campo para actualizar.', status=400)

    cambios = {}
    for campo in ('nombre', 'apellido_paterno'):
        if campo in recibidos:
            valor = str(recibidos[campo] or '').strip()
            if not valor:
                return error_response('ERR_CAMPO_VACIO', f"El campo '{campo}' no puede quedar vacío.", status=400)
            cambios[campo] = valor
    if 'apellido_materno' in recibidos:
        cambios['apellido_materno'] = str(recibidos['apellido_materno'] or '').strip() or None

    sensibles = [c for c in ('email', 'password') if c in recibidos]
    if sensibles:
        password_actual = datos.get('password_actual') or ''
        if not password_actual:
            return error_response('ERR_PASSWORD_ACTUAL_REQUERIDA',
                                  'Para cambiar el correo o la contraseña debes enviar tu contraseña actual.', status=400)
        hash_actual = UserRepository.get_password_hash(usuario['id'])
        if not hash_actual or not verify_password(password_actual, hash_actual):
            return error_response('ERR_PASSWORD_ACTUAL_INCORRECTA', 'La contraseña actual no es correcta.', status=403)

    email_cambiado = False
    if 'email' in recibidos:
        nuevo_email = str(recibidos['email'] or '').strip()
        if nuevo_email.lower() != usuario['email'].lower():
            valido, detalle = validate_email(nuevo_email, check_mx=Config.VERIFY_EMAIL_MX)
            if not valido:
                return error_response('ERR_EMAIL_INVALIDO', detalle, status=400, campo_invalido='email')
            cambios['email'] = nuevo_email
            cambios['email_verificado'] = False
            email_cambiado = True

    if 'password' in recibidos:
        error_password = validate_password_strength(str(recibidos['password'] or ''))
        if error_password:
            return error_response('ERR_PASSWORD_DEBIL', error_password, status=400)
        cambios['password_hash'] = hash_password(str(recibidos['password']))

    try:
        actualizado = UserRepository.update_profile(usuario['id'], cambios)
        correo = _enviar_token(actualizado) if email_cambiado else None
    except EmailAlreadyRegisteredError as exc:
        return error_response('ERR_EMAIL_DUPLICADO', str(exc), status=409, campo_invalido='email')
    except DatabaseUnavailableError:
        return _error_bd()

    respuesta = {'estado': 'exito', 'mensaje': 'Perfil actualizado.',
                 'campos_actualizados': sorted(recibidos.keys()), 'usuario': _usuario_publico(actualizado),
                 'sesiones_cerradas': False}
    if 'password_hash' in cambios or email_cambiado:
        # Credenciales nuevas: ningun token ni sesion anterior debe seguir sirviendo.
        revocar_usuario(servicio.redis, str(usuario['id']), config.access_token_minutos)
        sesiones.cerrar_todas(str(usuario['id']))
        respuesta.update(sesiones_cerradas=True,
                         mensaje='Perfil actualizado. Por seguridad se cerraron tus sesiones: inicia sesión de nuevo.')
    if correo:
        respuesta['correo_verificacion'] = correo
    logger.info(f"    Perfil actualizado ({', '.join(sorted(recibidos))}): {actualizado['email']}")
    return api_response('perfil', respuesta)


# ----------------------------------------------------------------------
# GET /health
# ----------------------------------------------------------------------
@app.route('/health', methods=['GET'])
def health():
    postgres = UserRepository.ping()
    redis_estado = servicio.redis.estado()
    estado = 'ok' if postgres['conectado'] and redis_estado['disponible'] else 'degradado'
    return api_response('health', {
        'estado': estado, 'microservicio': 'login', 'postgresql': postgres, 'redis': redis_estado,
        'capacidades': {'registro': postgres['conectado'],
                        'inicio_de_sesion': postgres['conectado'] and redis_estado['disponible']},
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }, status=200 if postgres['conectado'] else 503)


# ----------------------------------------------------------------------
# Documentacion
# ----------------------------------------------------------------------
@app.route('/openapi.json', methods=['GET'])
def openapi_spec():
    return jsonify(build_openapi_spec(request.host_url.rstrip('/')))


@app.route('/docs', methods=['GET'])
def swagger_docs():
    return SWAGGER_UI_HTML


@app.route('/', methods=['GET'])
def index():
    return api_response('microservicio', {
        'nombre': 'Microservicio de Autenticación', 'version': '3.0.0', 'documentacion': '/docs',
        'formato_por_defecto': 'xml',
        'endpoints': ['POST /register', 'GET|POST /verify', 'POST /login', 'POST /token/refresh',
                      'POST /session/extend', 'GET /session', 'POST /logout', 'PATCH /profile',
                      'GET /health', 'GET /metrics'],
    })


if __name__ == '__main__':
    logger.info(f"Microservicio de login en http://{Config.HOST}:{Config.PORT} "
                f"(Redis {servicio.redis.destino}, JWT {config.access_token_minutos} min)")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
