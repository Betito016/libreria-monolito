"""
Microservicio de gestion de libros.

Stack: Python + Flask + Psycopg 3 + PostgreSQL (libreria_db) + Redis.
Responde en XML por defecto y en JSON con ?format=json.

    GET    /health              Estado del servicio, PostgreSQL, Redis y login
    GET    /metrics             Metricas (cache, peticiones, JWT)
    GET    /categories          Categorias validas            (publico, cache)
    GET    /api/books           Catalogo paginado con filtros (publico, cache)
    GET    /api/books/{isbn}    Detalle con conceptos         (publico, cache)
    POST   /api/books           Crear                         (JWT de administrador)
    PUT    /api/books/{isbn}    Reemplazar completo           (JWT de administrador)
    PATCH  /api/books/{isbn}    Modificar parcial             (JWT de administrador)
    DELETE /api/books/{isbn}    Eliminar                      (JWT de administrador)

Las mismas rutas responden tambien sin el prefijo /api (/books, /books/{isbn}).

Redis:
    books:list:<filtros>, books:<isbn>, books:categories   cache (TTL corto, opcional)
    jwt:revoked:<jti>                                       revocacion (critica)
Toda escritura invalida books:* despues de confirmarse en PostgreSQL.
Las respuestas del catalogo llevan la cabecera X-Cache: HIT | MISS.
"""
from datetime import datetime, timezone

import requests
from flask import g, jsonify, request

from config.config import Config
from api.openapi import build_openapi_spec, SWAGGER_UI_HTML
from api.responses import api_response, error_response, parse_request_body
from api.validacion import ValidacionError, normalizar_isbn, validar_libro
from db.database import (BookInUseError, BookNotFoundError, BookRepository, CategoryNotFoundError,
                         DatabaseUnavailableError, DuplicateIsbnError)
from libreria_common.cache import clave_filtros
from libreria_common.flask_base import ServicioBase
from libreria_common.seguridad import ROL_ADMINISTRADOR

servicio = ServicioBase.crear('books', __name__)
app, logger, cache = servicio.app, servicio.logger, servicio.cache
solo_admin = servicio.auth.requiere_jwt(roles=[ROL_ADMINISTRADOR])


# ----------------------------------------------------------------------
# Errores propios del dominio
# ----------------------------------------------------------------------
@app.errorhandler(ValidacionError)
def _err_validacion(exc: ValidacionError):
    return error_response(exc.codigo, exc.mensaje, status=400, **exc.extra)


@app.errorhandler(BookNotFoundError)
def _err_no_encontrado(exc: BookNotFoundError):
    return error_response('ERR_LIBRO_NO_ENCONTRADO', str(exc), status=404)


@app.errorhandler(DuplicateIsbnError)
def _err_duplicado(exc: DuplicateIsbnError):
    return error_response('ERR_ISBN_DUPLICADO', str(exc), status=409, campo_invalido='isbn')


@app.errorhandler(CategoryNotFoundError)
def _err_categoria(exc: CategoryNotFoundError):
    return error_response('ERR_CATEGORIA_INVALIDA', str(exc), status=400,
                          campo_invalido='categoria', categorias_validas=exc.validas)


@app.errorhandler(BookInUseError)
def _err_en_uso(exc: BookInUseError):
    return error_response('ERR_LIBRO_EN_USO', str(exc), status=409)


@app.errorhandler(DatabaseUnavailableError)
def _err_bd(exc: DatabaseUnavailableError):
    logger.error(f"PostgreSQL no disponible: {exc}")
    return error_response('ERR_BASE_DATOS', 'El servicio de base de datos no está disponible.', status=503)


def _leer_cuerpo():
    datos = parse_request_body()
    if datos is None:
        raise ValidacionError('ERR_CUERPO_INVALIDO', 'El cuerpo de la petición no es JSON, XML ni formulario válido.')
    return datos


def _con_cache(raiz: str, clave: str, consultar):
    """Cache-aside: Redis primero; si no esta (o Redis falla), PostgreSQL."""
    datos = cache.obtener(clave)
    estado = 'HIT'
    if datos is None:
        estado = 'MISS'
        datos = consultar()
        cache.guardar(clave, datos)
    return api_response(raiz, datos, headers={'X-Cache': estado})


def _invalidar_catalogo(isbn: str) -> None:
    # Un libro puede crear autores o cambiar sus listas de libros: la cache
    # del servicio authors tambien queda obsoleta (Redis es compartido).
    cache.invalidar(['books:list:*', f'books:{isbn}', 'authors:*'])


# ----------------------------------------------------------------------
# GET /health
# ----------------------------------------------------------------------
def _estado_login() -> dict:
    """El login es necesario para que alguien obtenga un token, no para
    validarlo: los JWT se validan aqui con la clave compartida."""
    try:
        estado = requests.get(f"{Config.LOGIN_SERVICE_URL}/health", params={'format': 'json'}, timeout=2).json().get('estado')
        return {'disponible': estado in ('ok', 'degradado'), 'estado': estado, 'url': Config.LOGIN_SERVICE_URL}
    except (requests.RequestException, ValueError) as exc:
        return {'disponible': False, 'estado': 'inaccesible', 'url': Config.LOGIN_SERVICE_URL,
                'error': exc.__class__.__name__}


@app.route('/health', methods=['GET'])
def health():
    """ok: PostgreSQL y Redis disponibles. degradado (200): Redis o login
    caidos: el catalogo se lee de PostgreSQL, pero sin Redis no se puede
    comprobar la revocacion y las escrituras responden 503. 503: PostgreSQL caido."""
    postgres = BookRepository.ping()
    redis_estado = servicio.redis.estado()
    login = _estado_login()
    lectura = postgres['conectado']
    escritura = lectura and redis_estado['disponible']
    return api_response('health', {
        'estado': 'ok' if escritura and login['disponible'] else 'degradado',
        'microservicio': 'books',
        'postgresql': postgres,
        'redis': redis_estado,
        'dependencias': {'login': login},
        'autenticacion': {'tipo': 'JWT Bearer', 'algoritmo': servicio.config.jwt_algorithm,
                          'revocacion': 'redis', 'emision_de_tokens': login['disponible']},
        'capacidades': {'lectura': lectura, 'escritura': escritura, 'cache': redis_estado['disponible']},
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }, status=200 if lectura else 503)


# ----------------------------------------------------------------------
# GET /categories
# ----------------------------------------------------------------------
@app.route('/categories', methods=['GET'])
def categorias():
    def consultar():
        nombres = BookRepository.list_categories()
        return {'total': len(nombres), 'categorias': nombres}
    return _con_cache('categorias', 'books:categories', consultar)


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
        raise ValidacionError('ERR_FILTRO_INVALIDO', f"El filtro '{nombre}' debe ser numérico.", campo_invalido=nombre)
    if numero < 0:
        raise ValidacionError('ERR_FILTRO_INVALIDO', f"El filtro '{nombre}' no puede ser negativo.", campo_invalido=nombre)
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
        raise ValidacionError('ERR_FILTRO_INVALIDO', 'precio_min no puede ser mayor que precio_max.',
                              campo_invalido='precio_min')
    try:
        page = max(1, int(request.args.get('page', 1)))
        page_size = min(Config.PAGE_SIZE_MAX, max(1, int(request.args.get('page_size', Config.PAGE_SIZE_DEFAULT))))
    except ValueError:
        raise ValidacionError('ERR_FILTRO_INVALIDO', 'page y page_size deben ser enteros.')

    def consultar():
        resultado = BookRepository.search(filtros, page, page_size)
        total = resultado['total']
        return {'total': total, 'page': page, 'page_size': page_size,
                'total_pages': max(1, (total + page_size - 1) // page_size),
                'filtros': {k: v for k, v in filtros.items() if v is not None}, 'libros': resultado['libros']}

    clave = clave_filtros('books:list', {**filtros, 'page': page, 'page_size': page_size})
    return _con_cache('books', clave, consultar)


# ----------------------------------------------------------------------
# GET /books/{isbn}
# ----------------------------------------------------------------------
@app.route('/api/books/<isbn>', methods=['GET'])
@app.route('/books/<isbn>', methods=['GET'])
def detalle_libro(isbn: str):
    isbn = normalizar_isbn(isbn)

    def consultar():
        libro = BookRepository.get(isbn)
        if not libro:
            raise BookNotFoundError(f"No existe un libro con el ISBN {isbn}.")
        return libro
    return _con_cache('book', f'books:{isbn}', consultar)


# ----------------------------------------------------------------------
# Escrituras: JWT de administrador + invalidacion de cache
# ----------------------------------------------------------------------
@app.route('/api/books', methods=['POST'])
@app.route('/books', methods=['POST'])
@solo_admin
def crear_libro():
    datos = validar_libro(_leer_cuerpo(), modo='crear')
    libro = BookRepository.create(datos)
    _invalidar_catalogo(libro['isbn'])
    logger.info(f"    Operacion realizada: POST {libro['isbn']} por {g.usuario['email']}")
    return api_response('resultado', {'estado': 'exito', 'mensaje': 'Libro creado.', 'metodo': 'POST',
                                      'realizado_por': g.usuario['email'], 'libro': libro},
                        status=201, headers={'Location': f"{request.path.rstrip('/')}/{libro['isbn']}"})


@app.route('/api/books/<isbn>', methods=['PUT'])
@app.route('/books/<isbn>', methods=['PUT'])
@solo_admin
def reemplazar_libro(isbn: str):
    isbn = normalizar_isbn(isbn)
    cuerpo = _leer_cuerpo()
    libro = BookRepository.replace(isbn, validar_libro(cuerpo, modo='reemplazar', isbn_ruta=isbn))
    _invalidar_catalogo(isbn)
    logger.info(f"    Operacion realizada: PUT {isbn} por {g.usuario['email']}")
    return api_response('resultado', {'estado': 'exito', 'mensaje': 'Libro reemplazado por completo.', 'metodo': 'PUT',
                                      'campos_enviados': sorted(k for k in cuerpo if k != 'isbn'),
                                      'realizado_por': g.usuario['email'], 'libro': libro})


@app.route('/api/books/<isbn>', methods=['PATCH'])
@app.route('/books/<isbn>', methods=['PATCH'])
@solo_admin
def modificar_libro(isbn: str):
    isbn = normalizar_isbn(isbn)
    cambios = validar_libro(_leer_cuerpo(), modo='modificar', isbn_ruta=isbn)
    libro = BookRepository.update(isbn, cambios)
    _invalidar_catalogo(isbn)
    logger.info(f"    Operacion realizada: PATCH {isbn} ({', '.join(sorted(cambios))}) por {g.usuario['email']}")
    return api_response('resultado', {'estado': 'exito', 'mensaje': 'Libro modificado parcialmente.', 'metodo': 'PATCH',
                                      'campos_actualizados': sorted(cambios), 'realizado_por': g.usuario['email'],
                                      'libro': libro})


@app.route('/api/books/<isbn>', methods=['DELETE'])
@app.route('/books/<isbn>', methods=['DELETE'])
@solo_admin
def eliminar_libro(isbn: str):
    isbn = normalizar_isbn(isbn)
    BookRepository.delete(isbn)
    _invalidar_catalogo(isbn)
    logger.info(f"    Operacion realizada: DELETE {isbn} por {g.usuario['email']}")
    return api_response('resultado', {'estado': 'exito', 'mensaje': f"Libro {isbn} eliminado.", 'metodo': 'DELETE',
                                      'isbn': isbn, 'realizado_por': g.usuario['email']})


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
        'nombre': 'Microservicio de Libros', 'version': '2.0.0', 'documentacion': '/docs', 'formato_por_defecto': 'xml',
        'autenticacion': 'Escrituras: Authorization: Bearer <JWT de administrador emitido por login>',
        'endpoints_publicos': ['GET /health', 'GET /metrics', 'GET /categories', 'GET /api/books', 'GET /api/books/{isbn}'],
        'endpoints_protegidos': ['POST /api/books', 'PUT /api/books/{isbn}', 'PATCH /api/books/{isbn}',
                                 'DELETE /api/books/{isbn}'],
    })


if __name__ == '__main__':
    logger.info(f"Microservicio de libros en http://{Config.HOST}:{Config.PORT} (Redis {servicio.redis.destino})")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
