"""
Microservicio authors: autores y sus relaciones con libros.

Stack: Flask + Psycopg 3 + PostgreSQL (libreria_db) + Redis. Puerto 5005.
XML por defecto, JSON con ?format=json.

    GET    /authors          Listado (filtro nombre, paginado)          (publico, cache)
    GET    /authors/{id}     Detalle con sus libros                     (publico, cache)
    POST   /authors          Crear (opcional: libros = [isbn, ...])     (JWT administrador)
    PATCH  /authors/{id}     Modificar datos y/o relaciones con libros  (JWT administrador)
    DELETE /authors/{id}     Eliminar (409 si aun tiene libros)         (JWT administrador)
    GET    /health, /metrics

Redis: authors:list:<filtros> y authors:<id> (cache, TTL corto). Como el
catalogo de libros muestra los autores, cada escritura invalida tambien
books:* : la cache es compartida entre servicios.
"""
from datetime import datetime, timezone

from flask import g, request

import config
from libreria_common.bd import BaseDatos, dsn
from libreria_common.cache import clave_filtros
from libreria_common.flask_base import ServicioBase
from libreria_common.respuestas import api_response, leer_json
from libreria_common.seguridad import ROL_ADMINISTRADOR
from libreria_common.validacion import ValidacionError, requeridos, solo_campos, texto
from repositorio import RepositorioAutores

servicio = ServicioBase.crear('authors', __name__)
app, logger, cache = servicio.app, servicio.logger, servicio.cache
bd = BaseDatos(dsn(config.DB_HOST, config.DB_PORT, config.DB_NAME, config.DB_USER, config.DB_PASSWORD), config.DB_NAME)
repo = RepositorioAutores(bd)
solo_admin = servicio.auth.requiere_jwt(roles=[ROL_ADMINISTRADOR])
CAMPOS = ('nombre', 'nacionalidad', 'biografia', 'libros')


def _autor_id(valor: str) -> int:
    if not valor.isdigit():
        raise ValidacionError('ERR_ID_INVALIDO', 'El id del autor debe ser un número entero.')
    return int(valor)


def _con_cache(raiz, clave, consultar):
    datos, estado = cache.obtener(clave), 'HIT'
    if datos is None:
        datos, estado = consultar(), 'MISS'
        cache.guardar(clave, datos)
    return api_response(raiz, datos, headers={'X-Cache': estado})


def _invalidar(autor_id: int) -> None:
    cache.invalidar(['authors:list:*', f'authors:{autor_id}', 'books:*'])


def _validar(datos, crear: bool):
    solo_campos(datos, CAMPOS)
    if crear:
        requeridos(datos, ('nombre',))
    elif not datos:
        raise ValidacionError('ERR_SIN_CAMBIOS', 'No se envió ningún campo para modificar.')
    limpio = {}
    if 'nombre' in datos:
        limpio['nombre'] = texto(datos, 'nombre', 150, True)
    if 'nacionalidad' in datos:
        limpio['nacionalidad'] = texto(datos, 'nacionalidad', 80) if datos['nacionalidad'] else None
    if 'biografia' in datos:
        limpio['biografia'] = texto(datos, 'biografia', 4000) if datos['biografia'] else None
    if 'libros' in datos:
        limpio['libros'] = datos['libros']
    return limpio


@app.route('/health', methods=['GET'])
def health():
    postgres, redis_estado = bd.ping(), servicio.redis.estado()
    return api_response('health', {
        'estado': 'ok' if postgres['conectado'] and redis_estado['disponible'] else 'degradado',
        'microservicio': 'authors', 'postgresql': postgres, 'redis': redis_estado,
        'capacidades': {'lectura': postgres['conectado'], 'escritura': postgres['conectado'] and redis_estado['disponible'],
                        'cache': redis_estado['disponible']},
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }, status=200 if postgres['conectado'] else 503)


@app.route('/authors', methods=['GET'])
def listar():
    try:
        page = max(1, int(request.args.get('page', 1)))
        size = min(config.PAGE_SIZE_MAX, max(1, int(request.args.get('page_size', config.PAGE_SIZE_DEFAULT))))
    except ValueError:
        raise ValidacionError('ERR_FILTRO_INVALIDO', 'page y page_size deben ser enteros.')
    nombre = (request.args.get('nombre') or '').strip() or None

    def consultar():
        r = repo.listar(nombre, page, size)
        return {**r, 'page': page, 'page_size': size, 'total_pages': max(1, (r['total'] + size - 1) // size),
                'filtros': {'nombre': nombre} if nombre else {}}
    return _con_cache('autores', clave_filtros('authors:list', {'nombre': nombre, 'page': page, 'page_size': size}),
                      consultar)


@app.route('/authors/<autor_id>', methods=['GET'])
def detalle(autor_id):
    autor_id = _autor_id(autor_id)
    return _con_cache('autor', f'authors:{autor_id}', lambda: repo.obtener(autor_id))


@app.route('/authors', methods=['POST'])
@solo_admin
def crear():
    autor = repo.crear(_validar(leer_json(), crear=True))
    _invalidar(autor['id'])
    logger.info(f"    Operacion realizada: POST /authors {autor['id']} ({autor['nombre']}) por {g.usuario['email']}")
    return api_response('resultado', {'estado': 'exito', 'mensaje': 'Autor creado.', 'metodo': 'POST',
                                      'realizado_por': g.usuario['email'], 'autor': autor},
                        status=201, headers={'Location': f"/authors/{autor['id']}"})


@app.route('/authors/<autor_id>', methods=['PATCH'])
@solo_admin
def modificar(autor_id):
    autor_id = _autor_id(autor_id)
    cambios = _validar(leer_json(), crear=False)
    autor = repo.modificar(autor_id, cambios)
    _invalidar(autor_id)
    logger.info(f"    Operacion realizada: PATCH /authors/{autor_id} ({', '.join(sorted(cambios))}) por {g.usuario['email']}")
    return api_response('resultado', {'estado': 'exito', 'mensaje': 'Autor modificado.', 'metodo': 'PATCH',
                                      'campos_actualizados': sorted(cambios), 'realizado_por': g.usuario['email'],
                                      'autor': autor})


@app.route('/authors/<autor_id>', methods=['DELETE'])
@solo_admin
def eliminar(autor_id):
    autor_id = _autor_id(autor_id)
    autor = repo.eliminar(autor_id)
    _invalidar(autor_id)
    logger.info(f"    Operacion realizada: DELETE /authors/{autor_id} por {g.usuario['email']}")
    return api_response('resultado', {'estado': 'exito', 'mensaje': f"Autor {autor['nombre']} eliminado.",
                                      'metodo': 'DELETE', 'id': autor_id, 'realizado_por': g.usuario['email']})


@app.route('/', methods=['GET'])
def index():
    return api_response('microservicio', {
        'nombre': 'Microservicio de Autores', 'version': '1.0.0', 'formato_por_defecto': 'xml',
        'endpoints_publicos': ['GET /health', 'GET /metrics', 'GET /authors', 'GET /authors/{id}'],
        'endpoints_protegidos': ['POST /authors', 'PATCH /authors/{id}', 'DELETE /authors/{id}'],
    })


if __name__ == '__main__':
    logger.info(f"Microservicio de autores en http://{config.HOST}:{config.PORT} (Redis {servicio.redis.destino})")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
