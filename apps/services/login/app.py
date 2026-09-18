"""
Microservicio independiente de autenticacion y gestion basica de usuarios.

Stack: Python + Flask + Psycopg 3 + PostgreSQL (library_db).
Responde en XML por defecto y en JSON con ?format=json.

Endpoints:
    POST /register   Registrar un nuevo usuario
    POST /login      Autenticar e iniciar sesion
    POST /logout     Cerrar la sesion
    GET  /session    Consultar si existe una sesion autenticada
    GET  /health     Estado del microservicio y de PostgreSQL
"""
import logging
import sys
from datetime import timedelta

from flask import Flask, request, session

from config.config import Config
from api.responses import api_response, error_response, parse_request_body
from api.openapi import build_openapi_spec, SWAGGER_UI_HTML
from auth.email_validator import validate_email
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

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
app.permanent_session_lifetime = timedelta(minutes=Config.SESSION_LIFETIME_MINUTES)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,   # la cookie no es accesible desde JavaScript
    SESSION_COOKIE_SAMESITE='Lax',
    # SESSION_COOKIE_SECURE se queda en False porque el despliegue actual es
    # HTTP plano (sin TLS). Activarlo haria que el navegador descartara la
    # cookie por completo. Documentado como limitacion conocida en el README.
    SESSION_COOKIE_SECURE=False,
)

CAMPOS_REGISTRO = ('nombre', 'apellido_paterno', 'apellido_materno', 'email', 'password')


@app.after_request
def _add_cors_headers(response):
    """CORS con credenciales.

    Con cookies de sesion NO puede usarse 'Access-Control-Allow-Origin: *':
    el navegador exige un origen explicito cuando la peticion viaja con
    credenciales. Por eso se refleja el Origin solo si esta en la lista
    blanca de CORS_ORIGINS.
    """
    origin = request.headers.get('Origin')
    if origin and origin in Config.CORS_ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Vary'] = 'Origin'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Accept'
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
        'email_verificado': row.get('email_verificado', False),
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

    # El apellido materno es el unico opcional: no todos los nombres lo tienen.
    faltantes = [
        c for c in ('nombre', 'apellido_paterno', 'email', 'password') if not valores[c]
    ]
    if faltantes:
        return error_response(
            'ERR_CAMPOS_OBLIGATORIOS',
            f"Faltan campos obligatorios: {', '.join(faltantes)}.",
            status=400,
            campos_faltantes=faltantes,
        )

    error_password = validate_password_strength(valores['password'])
    if error_password:
        return error_response('ERR_PASSWORD_DEBIL', error_password, status=400)

    email_valido, detalle = validate_email(valores['email'], check_mx=Config.VERIFY_EMAIL_MX)
    if not email_valido:
        return error_response(
            'ERR_EMAIL_INVALIDO', detalle, status=400, campo_invalido='email'
        )

    try:
        usuario = UserRepository.create_user(
            nombre=valores['nombre'],
            apellido_paterno=valores['apellido_paterno'],
            apellido_materno=valores['apellido_materno'] or None,
            email=valores['email'],
            password_hash=hash_password(valores['password']),
            email_verificado=True,
        )
    except EmailAlreadyRegisteredError as exc:
        return error_response(
            'ERR_EMAIL_DUPLICADO', str(exc), status=409, campo_invalido='email'
        )
    except DatabaseUnavailableError as exc:
        logger.error(f"PostgreSQL no disponible durante el registro: {exc}")
        return error_response(
            'ERR_BASE_DATOS', 'El servicio de base de datos no esta disponible.', status=503
        )

    logger.info(f"Usuario registrado: {valores['email']}")
    return api_response(
        'registro',
        {
            'estado': 'exito',
            'mensaje': 'Usuario registrado correctamente.',
            'validacion_email': detalle,
            'usuario': _usuario_publico(usuario),
        },
        status=201,
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
            'ERR_CREDENCIALES_INCOMPLETAS',
            'Se requieren email y password.',
            status=400,
        )

    try:
        usuario = UserRepository.find_by_email(email)
    except DatabaseUnavailableError as exc:
        logger.error(f"PostgreSQL no disponible durante el login: {exc}")
        return error_response(
            'ERR_BASE_DATOS', 'El servicio de base de datos no esta disponible.', status=503
        )

    # Mismo mensaje para usuario inexistente y password incorrecta: revelar
    # cual de los dos fallo permitiria enumerar correos registrados.
    if not usuario or not verify_password(password, usuario['password_hash']):
        logger.warning(f"Intento de login fallido para '{email}'")
        return error_response(
            'ERR_CREDENCIALES_INVALIDAS', 'Correo o contrasena incorrectos.', status=401
        )

    if not usuario['activo']:
        return error_response('ERR_CUENTA_INACTIVA', 'La cuenta esta desactivada.', status=403)

    # Sesion del lado de Flask: a partir de aqui el usuario queda
    # identificado en solicitudes posteriores mediante la cookie firmada.
    session.permanent = True
    session['usuario_id'] = str(usuario['id'])
    session['email'] = usuario['email']

    logger.info(f"Login exitoso: {usuario['email']}")
    return api_response(
        'login',
        {
            'estado': 'exito',
            'mensaje': f"Bienvenido, {usuario['nombre']}.",
            'usuario': _usuario_publico(usuario),
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
            'mensaje': 'Sesion cerrada.' if estaba_autenticado else 'No habia sesion activa.',
            'sesion_previa': estaba_autenticado,
        },
    )


# ----------------------------------------------------------------------
# GET /session
# ----------------------------------------------------------------------
@app.route('/session', methods=['GET'])
def consultar_sesion():
    usuario_id = session.get('usuario_id')
    if not usuario_id:
        return api_response(
            'sesion', {'autenticado': False, 'mensaje': 'No hay una sesion activa.'}
        )

    try:
        usuario = UserRepository.find_by_id(usuario_id)
    except DatabaseUnavailableError:
        return error_response(
            'ERR_BASE_DATOS', 'El servicio de base de datos no esta disponible.', status=503
        )

    # La sesion apunta a un usuario que ya no existe (o fue eliminado):
    # se descarta para no dejar una sesion huerfana viva.
    if not usuario:
        session.clear()
        return api_response(
            'sesion', {'autenticado': False, 'mensaje': 'La sesion ya no es valida.'}
        )

    return api_response(
        'sesion',
        {'autenticado': True, 'usuario': _usuario_publico(usuario)},
    )


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
        },
        status=200 if saludable else 503,
    )


# ----------------------------------------------------------------------
# Documentacion (Swagger UI)
# ----------------------------------------------------------------------
@app.route('/openapi.json', methods=['GET'])
def openapi_spec():
    from flask import jsonify
    return jsonify(build_openapi_spec(request.host_url.rstrip('/')))


@app.route('/docs', methods=['GET'])
def swagger_docs():
    return SWAGGER_UI_HTML


@app.route('/', methods=['GET'])
def index():
    return api_response(
        'microservicio',
        {
            'nombre': 'Microservicio de Autenticacion',
            'version': '1.0.0',
            'documentacion': '/docs',
            'formato_por_defecto': 'xml',
            'endpoints': [
                'POST /register', 'POST /login', 'POST /logout',
                'GET /session', 'GET /health',
            ],
        },
    )


if __name__ == '__main__':
    logger.info(f"Microservicio de login en http://{Config.HOST}:{Config.PORT}")
    logger.info(f"Swagger UI en http://localhost:{Config.PORT}/docs")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
