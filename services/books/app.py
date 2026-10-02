"""
Microservicio de gestion de libros.

Stack: Python + Flask + Psycopg 3 + PostgreSQL (libreria_db).
Responde en XML por defecto y en JSON con ?format=json.

    GET    /health              Estado del servicio, de PostgreSQL y del login
    GET    /categories          Categorias validas (publico)
    GET    /api/books           Catalogo paginado con filtros (publico)
    GET    /api/books/{isbn}    Detalle con conceptos (publico)
    POST   /api/books           Crear               (JWT de administrador)
    PUT    /api/books/{isbn}    Reemplazar completo (JWT de administrador)
    PATCH  /api/books/{isbn}    Modificar parcial   (JWT de administrador)
    DELETE /api/books/{isbn}    Eliminar            (JWT de administrador)

Las mismas rutas responden tambien sin el prefijo /api (/books, /books/{isbn})
para no romper a los clientes anteriores.

El catalogo es publico: leerlo no requiere token. Escribir requiere
"Authorization: Bearer <token>" con un JWT emitido por el microservicio de
login a un administrador (ver auth/jwt_auth.py). La proteccion se aplica
ruta por ruta, no con un middleware global.
"""
import logging
import sys
from datetime import datetime, timezone

from flask import Flask, g, jsonify, request

from config.config import Config
from api.openapi import build_openapi_spec, SWAGGER_UI_HTML
from api.responses import api_response, error_response, parse_request_body
from api.validacion import ValidacionError, normalizar_isbn, validar_libro
from auth.jwt_auth import AuthError, describir_authorization, estado_login, requiere_jwt_administrador
from db.database import (
    BookInUseError,
    BookNotFoundError,
    BookRepository,
    CategoryNotFoundError,
    DatabaseUnavailableError,
    DuplicateIsbnError,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] (%(name)s) %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("BooksMicroservice")

# HS256 exige una clave de al menos 32 bytes (RFC 7518, 3.2).
if len(Config.JWT_SECRET.encode()) < 32:
    logger.critical("JWT_SECRET no esta definida o tiene menos de 32 bytes: no se pueden validar tokens.")
    raise SystemExit(1)

app = Flask(__name__)


@app.after_request
def _add_cors_headers(response):
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Accept, Authorization'
    return response


# ----------------------------------------------------------------------
# Logs de cada peticion: metodo, ruta, si es publica o protegida y si trae
# un Bearer token (sin mostrarlo completo).
# ----------------------------------------------------------------------
_SIN_LOG = ('/health', '/docs', '/openapi.json')


@app.before_request
def _log_peticion():
    if request.method == 'OPTIONS' or request.path in _SIN_LOG:
        return
    vista = app.view_functions.get(request.endpoint)
    protegida = getattr(vista, 'requiere_jwt', False)
    logger.info(f"--> {request.method} {request.path} | "
                f"{'PROTEGIDO (requiere JWT)' if protegida else 'publico (sin JWT)'} | "
                f"{describir_authorization(request.headers.get('Authorization'))}")
    if protegida and request.content_length:
        cuerpo = request.get_json(silent=True)
        if isinstance(cuerpo, dict):
            logger.info(f"    campos recibidos: {', '.join(sorted(cuerpo))}")


@app.after_request
def _log_respuesta(response):
    if request.method != 'OPTIONS' and request.path not in _SIN_LOG:
        logger.info(f"<-- {response.status_code} {request.method} {request.path}")
    return response


# ----------------------------------------------------------------------
# Traduccion de errores a respuestas HTTP (un solo lugar para todo el
# servicio: cada ruta solo lanza la excepcion que corresponde).
# ----------------------------------------------------------------------
@app.errorhandler(ValidacionError)
def _err_validacion(exc: ValidacionError):
    return error_response(exc.codigo, exc.mensaje, status=400, **exc.extra)


@app.errorhandler(AuthError)
def _err_auth(exc: AuthError):
    respuesta = error_response(exc.codigo, exc.mensaje, status=exc.status)
    if exc.status == 401:
        # RFC 6750: el 401 indica que esquema de autenticacion se espera.
        respuesta.headers['WWW-Authenticate'] = f'Bearer error="invalid_token", error_description="{exc.codigo}"'
    return respuesta


@app.errorhandler(BookNotFoundError)
def _err_no_encontrado(exc: BookNotFoundError):
    return error_response('ERR_LIBRO_NO_ENCONTRADO', str(exc), status=404)


@app.errorhandler(DuplicateIsbnError)
def _err_duplicado(exc: DuplicateIsbnError):
    return error_response('ERR_ISBN_DUPLICADO', str(exc), status=409, campo_invalido='isbn')


@app.errorhandler(CategoryNotFoundError)
def _err_categoria(exc: CategoryNotFoundError):
    return error_response(
        'ERR_CATEGORIA_INVALIDA', str(exc), status=400,
        campo_invalido='categoria', categorias_validas=exc.validas,
    )


@app.errorhandler(BookInUseError)
def _err_en_uso(exc: BookInUseError):
    return error_response('ERR_LIBRO_EN_USO', str(exc), status=409)


@app.errorhandler(DatabaseUnavailableError)
def _err_bd(exc: DatabaseUnavailableError):
    logger.error(f"PostgreSQL no disponible: {exc}")
    return error_response('ERR_BASE_DATOS', 'El servicio de base de datos no está disponible.', status=503)


@app.errorhandler(404)
def _err_ruta(_exc):
    return error_response('ERR_RUTA_NO_ENCONTRADA', f"No existe el recurso {request.path}.", status=404)


@app.errorhandler(405)
def _err_metodo(_exc):
    return error_response(
        'ERR_METODO_NO_PERMITIDO', f"El método {request.method} no está permitido en {request.path}.",
        status=405,
    )


def _leer_cuerpo():
    datos = parse_request_body()
    if datos is None:
        raise ValidacionError('ERR_CUERPO_INVALIDO', 'El cuerpo de la petición no es JSON, XML ni formulario válido.')
    return datos


def _isbn_de_ruta(isbn: str) -> str:
    """Acepta el ISBN con o sin guiones en la URL."""
    return normalizar_isbn(isbn)


# ----------------------------------------------------------------------
# GET /health
# ----------------------------------------------------------------------
@app.route('/health', methods=['GET'])
def health():
    """Tres niveles, pensados para el semaforo del cliente:

      ok         PostgreSQL y login disponibles.
      degradado  (503) PostgreSQL caido: el servicio no puede operar.
      degradado  (200) Solo login caido: los JWT ya emitidos se siguen
                 validando aqui (lectura y escritura funcionan), pero nadie
                 puede iniciar sesion para obtener un token nuevo.
    """
    postgres = BookRepository.ping()
    login = estado_login()

    lectura = postgres['conectado']

    return api_response(
        'health',
        {
            'estado': 'ok' if lectura and login['disponible'] else 'degradado',
            'microservicio': 'books',
            'postgresql': postgres,
            'dependencias': {'login': login},
            'autenticacion': {'tipo': 'JWT Bearer', 'algoritmo': Config.JWT_ALGORITHM,
                              'emision_de_tokens': login['disponible']},
            'capacidades': {'lectura': lectura, 'escritura': lectura},
            'timestamp': datetime.now(timezone.utc).isoformat(),
        },
        status=200 if lectura else 503,
    )


# ----------------------------------------------------------------------
# GET /categories
# ----------------------------------------------------------------------
@app.route('/categories', methods=['GET'])
def categorias():
    nombres = BookRepository.list_categories()
    return api_response('categorias', {'total': len(nombres), 'categorias': nombres})


# ----------------------------------------------------------------------
# GET /books
# ----------------------------------------------------------------------
def _filtro_numero(nombre: str, tipo):
    valor = request.args.get(nombre)
    if valor is None or not valor.strip():
        return None
    try:
        numero = tipo(valor.strip())
    except ValueError:
        raise ValidacionError(
            'ERR_FILTRO_INVALIDO', f"El filtro '{nombre}' debe ser numerico.", campo_invalido=nombre
        )
    if numero < 0:
        raise ValidacionError(
            'ERR_FILTRO_INVALIDO', f"El filtro '{nombre}' no puede ser negativo.", campo_invalido=nombre
        )
    return numero


@app.route('/api/books', methods=['GET'])
@app.route('/books', methods=['GET'])
def listar_libros():
    filtros = {
        'isbn': (request.args.get('isbn') or '').replace('-', '').strip() or None,
        'titulo': (request.args.get('titulo') or '').strip() or None,
        'anio': _filtro_numero('anio', int),
        'precio_min': _filtro_numero('precio_min', float),
        'precio_max': _filtro_numero('precio_max', float),
    }
    if (filtros['precio_min'] is not None and filtros['precio_max'] is not None
            and filtros['precio_min'] > filtros['precio_max']):
        raise ValidacionError(
            'ERR_FILTRO_INVALIDO', 'precio_min no puede ser mayor que precio_max.', campo_invalido='precio_min'
        )

    try:
        page = max(1, int(request.args.get('page', 1)))
        page_size = min(Config.PAGE_SIZE_MAX, max(1, int(request.args.get('page_size', Config.PAGE_SIZE_DEFAULT))))
    except ValueError:
        raise ValidacionError('ERR_FILTRO_INVALIDO', 'page y page_size deben ser enteros.')

    resultado = BookRepository.search(filtros, page, page_size)
    total = resultado['total']
    return api_response(
        'books',
        {
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': max(1, (total + page_size - 1) // page_size),
            'filtros': {k: v for k, v in filtros.items() if v is not None},
            'libros': resultado['libros'],
        },
    )


# ----------------------------------------------------------------------
# GET /books/{isbn}
# ----------------------------------------------------------------------
@app.route('/api/books/<isbn>', methods=['GET'])
@app.route('/books/<isbn>', methods=['GET'])
def detalle_libro(isbn: str):
    isbn = _isbn_de_ruta(isbn)
    libro = BookRepository.get(isbn)
    if not libro:
        raise BookNotFoundError(f"No existe un libro con el ISBN {isbn}.")
    return api_response('book', libro)


# ----------------------------------------------------------------------
# POST /books
# ----------------------------------------------------------------------
@app.route('/api/books', methods=['POST'])
@app.route('/books', methods=['POST'])
@requiere_jwt_administrador
def crear_libro():
    admin = g.usuario
    datos = validar_libro(_leer_cuerpo(), modo='crear')

    libro = BookRepository.create(datos)
    logger.info(f"    Operacion realizada: POST {libro['isbn']} por {admin['email']}")
    return api_response(
        'resultado',
        {
            'estado': 'exito',
            'mensaje': 'Libro creado.',
            'metodo': 'POST',
            'realizado_por': admin['email'],
            'libro': libro,
        },
        status=201,
        headers={'Location': f"{request.path.rstrip('/')}/{libro['isbn']}"},
    )


# ----------------------------------------------------------------------
# PUT /books/{isbn}
# ----------------------------------------------------------------------
@app.route('/api/books/<isbn>', methods=['PUT'])
@app.route('/books/<isbn>', methods=['PUT'])
@requiere_jwt_administrador
def reemplazar_libro(isbn: str):
    admin = g.usuario
    isbn = _isbn_de_ruta(isbn)
    cuerpo = _leer_cuerpo()
    datos = validar_libro(cuerpo, modo='reemplazar', isbn_ruta=isbn)

    libro = BookRepository.replace(isbn, datos)
    logger.info(f"    Operacion realizada: PUT {isbn} por {admin['email']}")
    return api_response(
        'resultado',
        {
            'estado': 'exito',
            'mensaje': 'Libro reemplazado por completo.',
            'metodo': 'PUT',
            'campos_enviados': sorted(k for k in cuerpo if k != 'isbn'),
            'realizado_por': admin['email'],
            'libro': libro,
        },
    )


# ----------------------------------------------------------------------
# PATCH /books/{isbn}
# ----------------------------------------------------------------------
@app.route('/api/books/<isbn>', methods=['PATCH'])
@app.route('/books/<isbn>', methods=['PATCH'])
@requiere_jwt_administrador
def modificar_libro(isbn: str):
    admin = g.usuario
    isbn = _isbn_de_ruta(isbn)
    cambios = validar_libro(_leer_cuerpo(), modo='modificar', isbn_ruta=isbn)

    libro = BookRepository.update(isbn, cambios)
    logger.info(f"    Operacion realizada: PATCH {isbn} ({', '.join(sorted(cambios))}) por {admin['email']}")
    return api_response(
        'resultado',
        {
            'estado': 'exito',
            'mensaje': 'Libro modificado parcialmente.',
            'metodo': 'PATCH',
            'campos_actualizados': sorted(cambios),
            'realizado_por': admin['email'],
            'libro': libro,
        },
    )


# ----------------------------------------------------------------------
# DELETE /books/{isbn}
# ----------------------------------------------------------------------
@app.route('/api/books/<isbn>', methods=['DELETE'])
@app.route('/books/<isbn>', methods=['DELETE'])
@requiere_jwt_administrador
def eliminar_libro(isbn: str):
    admin = g.usuario
    isbn = _isbn_de_ruta(isbn)

    BookRepository.delete(isbn)
    logger.info(f"    Operacion realizada: DELETE {isbn} por {admin['email']}")
    return api_response(
        'resultado',
        {
            'estado': 'exito',
            'mensaje': f"Libro {isbn} eliminado.",
            'metodo': 'DELETE',
            'isbn': isbn,
            'realizado_por': admin['email'],
        },
    )


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
    return api_response(
        'microservicio',
        {
            'nombre': 'Microservicio de Libros',
            'version': '1.1.0',
            'documentacion': '/docs',
            'formato_por_defecto': 'xml',
            'autenticacion': 'Escrituras: Authorization: Bearer <JWT emitido por login>',
            'endpoints_publicos': ['GET /health', 'GET /categories', 'GET /api/books', 'GET /api/books/{isbn}'],
            'endpoints_protegidos': ['POST /api/books', 'PUT /api/books/{isbn}',
                                     'PATCH /api/books/{isbn}', 'DELETE /api/books/{isbn}'],
        },
    )


if __name__ == '__main__':
    logger.info(f"Microservicio de libros en http://{Config.HOST}:{Config.PORT}")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
