"""
Microservicio independiente de autenticacion y gestion basica de usuarios.

Stack: Python + Flask + Psycopg 3 + PostgreSQL (library_db).
Responde en XML por defecto y en JSON con ?format=json.

Endpoints:
    POST  /register        Registrar un nuevo usuario
    GET   /verify          Canjear el token de verificacion de correo
    POST  /login           Autenticar e iniciar sesion
    POST  /logout          Cerrar la sesion
    GET   /session         Consultar la sesion y el perfil del usuario
    POST  /session/extend  Prorrogar la sesion vigente
    PATCH /profile         Modificar datos del perfil
    GET   /health          Estado del microservicio y de PostgreSQL
"""
import logging
import sys
import time
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request, session

from config.config import Config
from api.responses import api_response, error_response, parse_request_body
from api.openapi import build_openapi_spec, SWAGGER_UI_HTML
from auth.email_validator import validate_email
from auth.jwt_tokens import descripcion_segura, emitir_token
from auth.mailer import enviar_verificacion, generar_token, hash_token
from auth.passwords import hash_password, verify_password, validate_password_strength
from db.database import (
    UserRepository,
    EmailAlreadyRegisteredError,
    DatabaseUnavailableError,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] (%(name)s) %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("LoginMicroservice")

# HS256 exige una clave de al menos 32 bytes (RFC 7518, 3.2).
if len(Config.JWT_SECRET.encode()) < 32:
    logger.critical("JWT_SECRET no esta definida o tiene menos de 32 bytes: el servicio no puede emitir tokens.")
    raise SystemExit(1)

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
app.permanent_session_lifetime = timedelta(minutes=Config.SESSION_LIFETIME_MINUTES)
app.config.update(
    SESSION_COOKIE_NAME=Config.SESSION_COOKIE_NAME,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    # HTTP plano (sin TLS): con Secure=True el cliente descartaria la cookie.
    SESSION_COOKIE_SECURE=False,
    # Por defecto Flask renueva la cookie en CADA peticion. Eso haria que la
    # sesion no expirara nunca mientras el cliente consulte /session, y
    # POST /session/extend no tendria sentido. La sesion vence en un momento
    # fijo y solo se prorroga de forma explicita.
    SESSION_REFRESH_EACH_REQUEST=False,
)

CAMPOS_REGISTRO = ('nombre', 'apellido_paterno', 'apellido_materno', 'email', 'password')
CAMPOS_PERFIL = ('nombre', 'apellido_paterno', 'apellido_materno', 'email', 'password')


@app.after_request
def _add_cors_headers(response):
    """CORS con credenciales: con cookies de sesion no se permite '*'."""
    origin = request.headers.get('Origin')
    if origin and origin in Config.CORS_ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Vary'] = 'Origin'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PATCH, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Accept, Authorization'
    return response


# ----------------------------------------------------------------------
# Logs de cada peticion (para seguir el flujo en la consola)
# ----------------------------------------------------------------------
@app.before_request
def _log_peticion():
    if request.method == 'OPTIONS' or request.path in ('/health', '/docs', '/openapi.json'):
        return
    logger.info(f"--> {request.method} {request.path} | endpoint publico (login no exige JWT)")


@app.after_request
def _log_respuesta(response):
    if request.method != 'OPTIONS' and request.path not in ('/health', '/docs', '/openapi.json'):
        logger.info(f"<-- {response.status_code} {request.method} {request.path}")
    return response


def _usuario_publico(row: dict) -> dict:
    """Proyeccion segura de un usuario: nunca incluye password_hash."""
    return {
        'id': str(row['id']),
        'nombre': row['nombre'],
        'apellido_paterno': row.get('apellido_paterno'),
        'apellido_materno': row.get('apellido_materno'),
        'email': row['email'],
        'rol': row['rol'],
        'activo': row.get('activo', True),
        'email_verificado': row.get('email_verificado', False),
    }


def _error_bd():
    return error_response(
        'ERR_BASE_DATOS', 'El servicio de base de datos no está disponible.', status=503
    )


# ----------------------------------------------------------------------
# Manejo de la sesion
# ----------------------------------------------------------------------
# La sesion guarda su propio instante de vencimiento (`expira_en`, epoch
# UTC). Asi el servidor puede decir con precision cuanto le queda, y el
# cliente puede advertir al usuario antes de que expire.

def _ahora() -> int:
    return int(time.time())


def _iniciar_sesion(usuario: dict) -> None:
    session.clear()
    session.permanent = True
    session['usuario_id'] = str(usuario['id'])
    session['email'] = usuario['email']
    session['expira_en'] = _ahora() + Config.SESSION_LIFETIME_MINUTES * 60


def _estado_sesion():
    """Devuelve (usuario_id, motivo) con motivo en
    'vigente' | 'sin_sesion' | 'expirada'."""
    usuario_id = session.get('usuario_id')
    if not usuario_id:
        return None, 'sin_sesion'
    if _ahora() >= session.get('expira_en', 0):
        session.clear()
        return None, 'expirada'
    return usuario_id, 'vigente'


def _info_sesion() -> dict:
    expira = session.get('expira_en', 0)
    return {
        'expira_en': datetime.fromtimestamp(expira, tz=timezone.utc).isoformat(),
        'segundos_restantes': max(0, expira - _ahora()),
        'duracion_minutos': Config.SESSION_LIFETIME_MINUTES,
    }


def _requerir_sesion():
    """Para endpoints protegidos. Devuelve (usuario, None) si hay una
    sesion valida, o (None, respuesta_401) si no la hay."""
    usuario_id, motivo = _estado_sesion()
    if not usuario_id:
        if motivo == 'expirada':
            return None, error_response(
                'ERR_SESION_EXPIRADA',
                'La sesión expiró. Inicia sesión de nuevo.',
                status=401, motivo=motivo,
            )
        return None, error_response(
            'ERR_SESION_INVALIDA', 'No hay una sesión activa.', status=401, motivo=motivo
        )

    try:
        usuario = UserRepository.find_by_id(usuario_id)
    except DatabaseUnavailableError:
        return None, _error_bd()

    if not usuario or not usuario['activo']:
        session.clear()
        return None, error_response(
            'ERR_SESION_INVALIDA', 'La sesión ya no es válida.',
            status=401, motivo='usuario_invalido',
        )
    return usuario, None


def _enviar_token(usuario: dict) -> dict:
    """Genera un token de verificacion, lo registra y lo envia por correo."""
    token, token_hash = generar_token()
    registro = UserRepository.create_verification_token(
        usuario_id=usuario['id'],
        token_hash=token_hash,
        email_destino=usuario['email'],
        ttl_hours=Config.TOKEN_TTL_HOURS,
    )
    enviado, detalle = enviar_verificacion(
        destinatario=usuario['email'], nombre=usuario['nombre'], token=token
    )
    if enviado:
        UserRepository.mark_token_sent(registro['id'])
    return {
        'enviado': enviado,
        'detalle': detalle,
        'destinatario': usuario['email'],
        'expira_en': str(registro['expira_en']),
    }


# ----------------------------------------------------------------------
# POST /register
# ----------------------------------------------------------------------
@app.route('/register', methods=['POST', 'OPTIONS'])
def register():
    if request.method == 'OPTIONS':
        return api_response('preflight', {'estado': 'ok'})

    datos = parse_request_body()
    valores = {campo: (datos.get(campo) or '').strip() for campo in CAMPOS_REGISTRO}

    faltantes = [
        c for c in ('nombre', 'apellido_paterno', 'email', 'password') if not valores[c]
    ]
    if faltantes:
        return error_response(
            'ERR_CAMPOS_OBLIGATORIOS',
            f"Faltan campos obligatorios: {', '.join(faltantes)}.",
            status=400, campos_faltantes=faltantes,
        )

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
            nombre=valores['nombre'],
            apellido_paterno=valores['apellido_paterno'],
            apellido_materno=valores['apellido_materno'] or None,
            email=valores['email'],
            password_hash=hash_password(valores['password']),
            email_verificado=False,
        )
        correo = _enviar_token(usuario)
    except EmailAlreadyRegisteredError as exc:
        return error_response('ERR_EMAIL_DUPLICADO', str(exc), status=409, campo_invalido='email')
    except DatabaseUnavailableError as exc:
        logger.error(f"PostgreSQL no disponible durante el registro: {exc}")
        return _error_bd()

    logger.info(f"Usuario registrado: {valores['email']} (correo enviado: {correo['enviado']})")
    return api_response(
        'registro',
        {
            'estado': 'exito',
            'mensaje': 'Usuario registrado. Revisa tu correo para verificar la cuenta.',
            'validacion_dominio': detalle,
            'correo_verificacion': correo,
            'usuario': _usuario_publico(usuario),
        },
        status=201,
    )


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
        return error_response(
            'ERR_TOKEN_YA_USADO',
            'Este token ya fue utilizado. El correo ya estaba verificado.', status=409,
        )
    if resultado['resultado'] == 'expirado':
        return error_response(
            'ERR_TOKEN_EXPIRADO', 'El token de verificación venció. Solicita uno nuevo.', status=410
        )

    usuario = resultado['usuario']
    logger.info(f"Correo verificado: {usuario['email']}")
    return api_response(
        'verificacion',
        {
            'estado': 'exito',
            'mensaje': 'Correo verificado correctamente. Ya puedes iniciar sesión.',
            'usuario': _usuario_publico(usuario),
        },
    )


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
        return error_response(
            'ERR_CREDENCIALES_INCOMPLETAS', 'Se requieren email y password.', status=400
        )

    try:
        usuario = UserRepository.find_by_email(email)
    except DatabaseUnavailableError as exc:
        logger.error(f"PostgreSQL no disponible durante el login: {exc}")
        return _error_bd()

    # Mismo mensaje para usuario inexistente y password incorrecta: revelar
    # cual de los dos fallo permitiria enumerar correos registrados.
    if not usuario or not verify_password(password, usuario['password_hash']):
        logger.warning(f"Intento de login fallido para '{email}'")
        return error_response(
            'ERR_CREDENCIALES_INVALIDAS', 'Correo o contraseña incorrectos.', status=401
        )

    # Estas dos comprobaciones van DESPUES de validar la contrasena: solo
    # quien conoce la contrasena correcta se entera del estado de la cuenta.
    if not usuario['activo']:
        return error_response('ERR_CUENTA_INACTIVA', 'La cuenta está desactivada.', status=403)

    if not usuario['email_verificado']:
        return error_response(
            'ERR_CORREO_NO_VERIFICADO',
            'Tu correo aún no está verificado. Ingresa el código que te enviamos por correo.',
            status=403,
        )

    _iniciar_sesion(usuario)
    token = emitir_token(usuario, session['expira_en'])
    logger.info(f"Login exitoso: {usuario['email']} (rol {usuario['rol']})")
    logger.info(
        f"    JWT emitido: {descripcion_segura(token['access_token'])} "
        f"alg={token['algoritmo']} vence en {token['expires_in']} s"
    )
    return api_response(
        'login',
        {
            'estado': 'exito',
            'mensaje': f"Bienvenido, {usuario['nombre']}.",
            'usuario': _usuario_publico(usuario),
            'sesion': _info_sesion(),
            'token': token,
        },
    )


# ----------------------------------------------------------------------
# POST /logout
# ----------------------------------------------------------------------
@app.route('/logout', methods=['POST', 'OPTIONS'])
def logout():
    if request.method == 'OPTIONS':
        return api_response('preflight', {'estado': 'ok'})

    estaba_autenticado = 'usuario_id' in session
    session.clear()
    return api_response(
        'logout',
        {
            'estado': 'exito',
            'mensaje': 'Sesión cerrada.' if estaba_autenticado else 'No había sesión activa.',
            'sesion_previa': estaba_autenticado,
        },
    )


# ----------------------------------------------------------------------
# GET /session
# ----------------------------------------------------------------------
@app.route('/session', methods=['GET'])
def consultar_sesion():
    """Endpoint de introspeccion: siempre responde 200 e informa el estado.
    Los endpoints protegidos (perfil, extension, CRUD de libros) son los que
    responden 401 cuando no hay sesion valida."""
    usuario_id, motivo = _estado_sesion()
    if not usuario_id:
        mensajes = {
            'sin_sesion': 'No hay una sesión activa.',
            'expirada': 'La sesión expiró.',
        }
        return api_response(
            'sesion', {'autenticado': False, 'motivo': motivo, 'mensaje': mensajes[motivo]}
        )

    try:
        usuario = UserRepository.find_by_id(usuario_id)
    except DatabaseUnavailableError:
        return _error_bd()

    if not usuario or not usuario['activo']:
        session.clear()
        return api_response(
            'sesion',
            {'autenticado': False, 'motivo': 'usuario_invalido',
             'mensaje': 'La sesión ya no es válida.'},
        )

    return api_response(
        'sesion',
        {'autenticado': True, 'usuario': _usuario_publico(usuario), 'sesion': _info_sesion()},
    )


# ----------------------------------------------------------------------
# POST /session/extend
# ----------------------------------------------------------------------
@app.route('/session/extend', methods=['POST', 'OPTIONS'])
def extender_sesion():
    if request.method == 'OPTIONS':
        return api_response('preflight', {'estado': 'ok'})

    usuario, error = _requerir_sesion()
    if error:
        return error

    session['expira_en'] = _ahora() + Config.SESSION_LIFETIME_MINUTES * 60
    # El JWT anterior vence a la hora original: se emite uno nuevo con el
    # vencimiento prorrogado, para que token y sesion sigan alineados.
    token = emitir_token(usuario, session['expira_en'])
    logger.info(f"Sesion extendida: {usuario['email']}; nuevo JWT {descripcion_segura(token['access_token'])}")
    return api_response(
        'sesion',
        {'estado': 'exito', 'mensaje': 'Sesión extendida.', 'sesion': _info_sesion(), 'token': token},
    )


# ----------------------------------------------------------------------
# PATCH /profile
# ----------------------------------------------------------------------
@app.route('/profile', methods=['PATCH', 'OPTIONS'])
def actualizar_perfil():
    """Actualizacion PARCIAL del perfil: solo se modifican los campos
    enviados. Cambiar correo o contrasena exige la contrasena actual, para
    que una sesion robada no baste para apoderarse de la cuenta."""
    if request.method == 'OPTIONS':
        return api_response('preflight', {'estado': 'ok'})

    usuario, error = _requerir_sesion()
    if error:
        return error

    datos = parse_request_body()
    no_permitidos = [k for k in datos if k not in CAMPOS_PERFIL + ('password_actual',)]
    if no_permitidos:
        # Rechazo explicito en lugar de ignorar en silencio: si alguien envia
        # "rol": "administrador", debe saber que ese campo no se acepta.
        return error_response(
            'ERR_CAMPOS_NO_PERMITIDOS',
            f"Campos no modificables desde el perfil: {', '.join(no_permitidos)}.",
            status=400, campos_rechazados=no_permitidos,
        )

    recibidos = {k: datos[k] for k in CAMPOS_PERFIL if k in datos}
    if not recibidos:
        return error_response('ERR_SIN_CAMBIOS', 'No se envió ningún campo para actualizar.', status=400)

    cambios = {}

    for campo in ('nombre', 'apellido_paterno'):
        if campo in recibidos:
            valor = str(recibidos[campo] or '').strip()
            if not valor:
                return error_response(
                    'ERR_CAMPO_VACIO', f"El campo '{campo}' no puede quedar vacio.", status=400
                )
            cambios[campo] = valor

    if 'apellido_materno' in recibidos:
        cambios['apellido_materno'] = str(recibidos['apellido_materno'] or '').strip() or None

    sensibles = [c for c in ('email', 'password') if c in recibidos]
    if sensibles:
        password_actual = datos.get('password_actual') or ''
        if not password_actual:
            return error_response(
                'ERR_PASSWORD_ACTUAL_REQUERIDA',
                'Para cambiar el correo o la contraseña debes enviar tu contraseña actual.',
                status=400,
            )
        try:
            hash_actual = UserRepository.get_password_hash(usuario['id'])
        except DatabaseUnavailableError:
            return _error_bd()
        if not hash_actual or not verify_password(password_actual, hash_actual):
            # 403 y no 401: la sesion es valida, lo que falla es la
            # autorizacion de ESTA operacion. Un 401 haria que el cliente
            # creyera que la sesion expiro.
            return error_response(
                'ERR_PASSWORD_ACTUAL_INCORRECTA', 'La contraseña actual no es correcta.', status=403
            )

    email_cambiado = False
    if 'email' in recibidos:
        nuevo_email = str(recibidos['email'] or '').strip()
        if nuevo_email.lower() != usuario['email'].lower():
            valido, detalle = validate_email(nuevo_email, check_mx=Config.VERIFY_EMAIL_MX)
            if not valido:
                return error_response('ERR_EMAIL_INVALIDO', detalle, status=400, campo_invalido='email')
            cambios['email'] = nuevo_email
            # El correo nuevo no esta comprobado: se vuelve a exigir verificacion.
            cambios['email_verificado'] = False
            email_cambiado = True

    if 'password' in recibidos:
        error_password = validate_password_strength(str(recibidos['password'] or ''))
        if error_password:
            return error_response('ERR_PASSWORD_DEBIL', error_password, status=400)
        cambios['password_hash'] = hash_password(str(recibidos['password']))

    try:
        actualizado = UserRepository.update_profile(usuario['id'], cambios)
        correo = None
        if email_cambiado:
            session['email'] = actualizado['email']
            correo = _enviar_token(actualizado)
    except EmailAlreadyRegisteredError as exc:
        return error_response('ERR_EMAIL_DUPLICADO', str(exc), status=409, campo_invalido='email')
    except DatabaseUnavailableError:
        return _error_bd()

    respuesta = {
        'estado': 'exito',
        'mensaje': 'Perfil actualizado.',
        # Nombres de los campos modificados, nunca sus valores (la contrasena
        # no debe regresar en ninguna forma).
        'campos_actualizados': sorted(recibidos.keys()),
        'usuario': _usuario_publico(actualizado),
    }
    if correo:
        respuesta['mensaje'] = 'Perfil actualizado. Debes verificar tu nuevo correo.'
        respuesta['correo_verificacion'] = correo

    logger.info(f"Perfil actualizado ({', '.join(sorted(recibidos))}): {actualizado['email']}")
    return api_response('perfil', respuesta)


# ----------------------------------------------------------------------
# GET /health
# ----------------------------------------------------------------------
@app.route('/health', methods=['GET'])
def health():
    postgres = UserRepository.ping()
    saludable = postgres['conectado']
    return api_response(
        'health',
        {
            'estado': 'ok' if saludable else 'degradado',
            'microservicio': 'login',
            'postgresql': postgres,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        },
        status=200 if saludable else 503,
    )


# ----------------------------------------------------------------------
# Documentacion (Swagger UI)
# ----------------------------------------------------------------------
@app.route('/openapi.json', methods=['GET'])
def openapi_spec():
    return jsonify(build_openapi_spec(request.host_url.rstrip('/')))


@app.route('/docs', methods=['GET'])
def swagger_docs():
    return SWAGGER_UI_HTML


@app.route('/', methods=['GET'])
def index():
    return api_response(
        'microservicio',
        {
            'nombre': 'Microservicio de Autenticación',
            'version': '2.0.0',
            'documentacion': '/docs',
            'formato_por_defecto': 'xml',
            'endpoints': [
                'POST /register', 'GET|POST /verify', 'POST /login', 'POST /logout',
                'GET /session', 'POST /session/extend', 'PATCH /profile', 'GET /health',
            ],
        },
    )


if __name__ == '__main__':
    logger.info(f"Microservicio de login en http://{Config.HOST}:{Config.PORT}")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
