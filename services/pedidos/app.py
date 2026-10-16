"""
Microservicio pedidos: pedidos, lineas de pedido, stock y estados.

Stack: Flask + Psycopg 3 + PostgreSQL (libreria_db) + Redis. Puerto 5003.
XML por defecto, JSON con ?format=json. Todo requiere JWT: un pedido es
informacion privada (lectura administrativa o del propio cliente).

    GET    /orders          Listado: el administrador ve todos (filtros estado, user_id);
                            un cliente solo los suyos                         (JWT)
    GET    /orders/{id}     Detalle con lineas (administrador o dueno)        (JWT)
    POST   /orders          Crear: items [{isbn, cantidad}], direccion_envio  (JWT)
                            Descuenta stock; cabecera opcional Idempotency-Key
    PATCH  /orders/{id}     Estado (pendiente->cancelado, pagado->enviado->entregado)
                            y direccion. El cliente solo puede cancelar el suyo  (JWT)
    DELETE /orders/{id}     Eliminar un pedido pendiente o cancelado          (JWT administrador)
    GET    /health, /metrics

Redis:
    order:idem:<user_id>:<clave>   POST idempotente (24 h)
    lock:pedidos:barrido           solo un proceso cancela los pedidos vencidos
    books:*                        el stock cambia: se invalida la cache del catalogo
"""
import threading
import time
from datetime import datetime, timezone

from flask import g, request

import config
from libreria_common.bd import BaseDatos, BaseDatosNoDisponible, dsn
from libreria_common.candado import Candado
from libreria_common.flask_base import ServicioBase
from libreria_common.redis_capa import RedisNoDisponible
from libreria_common.respuestas import api_response, leer_json
from libreria_common.seguridad import AuthError, ROL_ADMINISTRADOR
from libreria_common.validacion import ValidacionError, solo_campos, texto
from repositorio import ESTADOS, RepositorioPedidos

servicio = ServicioBase.crear('pedidos', __name__)
app, logger, cache = servicio.app, servicio.logger, servicio.cache
bd = BaseDatos(dsn(config.DB_HOST, config.DB_PORT, config.DB_NAME, config.DB_USER, config.DB_PASSWORD), config.DB_NAME)
repo = RepositorioPedidos(bd)
autenticado = servicio.auth.requiere_jwt()
solo_admin = servicio.auth.requiere_jwt(roles=[ROL_ADMINISTRADOR])


def _es_admin() -> bool:
    return g.usuario['role_id'] == ROL_ADMINISTRADOR


def _order_id(valor: str) -> int:
    if not valor.isdigit():
        raise ValidacionError('ERR_ID_INVALIDO', 'El id del pedido debe ser un número entero.')
    return int(valor)


def _del_usuario_o_admin(pedido: dict) -> dict:
    if not _es_admin() and pedido['user_id'] != g.usuario['user_id']:
        # Token valido, pero el recurso es de otro usuario: 403 (permiso), no 401.
        raise AuthError('ERR_SIN_PERMISOS', 'Solo puedes consultar o modificar tus propios pedidos.', 403)
    return pedido


def _invalidar_catalogo() -> None:
    cache.invalidar(['books:*'])                 # el stock se muestra en el catalogo


def _items(datos) -> list:
    items = datos.get('items')
    if not isinstance(items, list) or not items:
        raise ValidacionError('ERR_CAMPOS_OBLIGATORIOS', "Envía 'items': [{\"isbn\": ..., \"cantidad\": ...}].",
                              campos_faltantes=['items'])
    if len(items) > config.MAX_LINEAS:
        raise ValidacionError('ERR_DEMASIADAS_LINEAS', f'Un pedido admite máximo {config.MAX_LINEAS} libros distintos.')
    agrupados = {}
    for item in items:
        if not isinstance(item, dict) or set(item) - {'isbn', 'cantidad'}:
            raise ValidacionError('ERR_ITEM_INVALIDO', 'Cada item debe ser {"isbn": "...", "cantidad": n}.')
        isbn = str(item.get('isbn') or '').replace('-', '').strip().upper()
        cantidad = item.get('cantidad', 1)
        if not isbn:
            raise ValidacionError('ERR_ITEM_INVALIDO', 'Cada item necesita un isbn.')
        if isinstance(cantidad, bool) or not isinstance(cantidad, int) or not 1 <= cantidad <= config.MAX_CANTIDAD:
            raise ValidacionError('ERR_ITEM_INVALIDO', f'La cantidad debe ser un entero entre 1 y {config.MAX_CANTIDAD}.')
        agrupados[isbn] = agrupados.get(isbn, 0) + cantidad
    return [{'isbn': i, 'cantidad': c} for i, c in agrupados.items()]


# ----------------------------------------------------------------------
@app.route('/health', methods=['GET'])
def health():
    postgres, redis_estado = bd.ping(), servicio.redis.estado()
    return api_response('health', {
        'estado': 'ok' if postgres['conectado'] and redis_estado['disponible'] else 'degradado',
        'microservicio': 'pedidos', 'postgresql': postgres, 'redis': redis_estado,
        'tareas': {'cancelar_pendientes_tras_minutos': config.ORDER_PENDING_MINUTES},
        'capacidades': {'lectura': postgres['conectado'] and redis_estado['disponible'],
                        'escritura': postgres['conectado'] and redis_estado['disponible']},
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }, status=200 if postgres['conectado'] else 503)


@app.route('/orders', methods=['GET'])
@autenticado
def listar():
    try:
        page = max(1, int(request.args.get('page', 1)))
        size = min(config.PAGE_SIZE_MAX, max(1, int(request.args.get('page_size', config.PAGE_SIZE_DEFAULT))))
    except ValueError:
        raise ValidacionError('ERR_FILTRO_INVALIDO', 'page y page_size deben ser enteros.')
    estado = request.args.get('estado') or None
    if estado and estado not in ESTADOS:
        raise ValidacionError('ERR_FILTRO_INVALIDO', f"estado debe ser uno de: {', '.join(ESTADOS)}.")
    # Un cliente solo ve sus pedidos aunque pida otro user_id.
    user_id = request.args.get('user_id') or None if _es_admin() else g.usuario['user_id']
    r = repo.listar(user_id, estado, page, size)
    return api_response('pedidos', {**r, 'page': page, 'page_size': size,
                                    'total_pages': max(1, (r['total'] + size - 1) // size),
                                    'alcance': 'todos' if _es_admin() and not user_id else 'propios'})


@app.route('/orders/<order_id>', methods=['GET'])
@autenticado
def detalle(order_id):
    return api_response('pedido', _del_usuario_o_admin(repo.obtener(_order_id(order_id))))


@app.route('/orders', methods=['POST'])
@autenticado
def crear():
    datos = leer_json()
    solo_campos(datos, ('items', 'direccion_envio'))
    items = _items(datos)
    direccion = texto(datos, 'direccion_envio', 300) if datos.get('direccion_envio') else None
    clave_idem = (request.headers.get('Idempotency-Key') or '').strip()[:80]
    clave_redis = f"order:idem:{g.usuario['user_id']}:{clave_idem}" if clave_idem else None

    if clave_redis:
        previo = servicio.redis.ejecutar(lambda r: r.get(clave_redis), critico=True)
        if previo:
            logger.info(f"    Idempotency-Key repetida: se devuelve el pedido {previo} sin crear otro")
            return api_response('resultado', {'estado': 'exito', 'mensaje': 'Pedido ya creado con esa Idempotency-Key.',
                                              'metodo': 'POST', 'repetido': True, 'pedido': repo.obtener(int(previo))})

    pedido = repo.crear(g.usuario['user_id'], g.usuario['email'], items, direccion)
    if clave_redis:
        servicio.redis.ejecutar(lambda r: r.set(clave_redis, pedido['id'], ex=config.IDEMPOTENCIA_HORAS * 3600),
                                critico=False)
    _invalidar_catalogo()
    logger.info(f"    Operacion realizada: POST /orders {pedido['id']} ({len(items)} libro(s), total {pedido['total']}) "
                f"por {g.usuario['email']}; stock descontado")
    return api_response('resultado', {'estado': 'exito', 'mensaje': 'Pedido creado; el stock quedó apartado.',
                                      'metodo': 'POST', 'realizado_por': g.usuario['email'], 'pedido': pedido},
                        status=201, headers={'Location': f"/orders/{pedido['id']}"})


@app.route('/orders/<order_id>', methods=['PATCH'])
@autenticado
def modificar(order_id):
    order_id = _order_id(order_id)
    datos = leer_json()
    solo_campos(datos, ('estado', 'direccion_envio'))
    if not datos:
        raise ValidacionError('ERR_SIN_CAMBIOS', 'No se envió ningún campo para modificar.')
    if 'estado' in datos and datos['estado'] not in ESTADOS:
        raise ValidacionError('ERR_ESTADO_INVALIDO', f"estado debe ser uno de: {', '.join(ESTADOS)}.",
                              estados_validos=list(ESTADOS))
    _del_usuario_o_admin(repo.obtener(order_id))
    if not _es_admin() and datos.get('estado') not in (None, 'cancelado'):
        raise AuthError('ERR_SIN_PERMISOS', 'Un cliente solo puede cancelar su pedido; los envíos los gestiona un administrador.', 403)
    cambios = {}
    if 'estado' in datos:
        cambios['estado'] = datos['estado']
    if 'direccion_envio' in datos:
        cambios['direccion_envio'] = texto(datos, 'direccion_envio', 300) if datos['direccion_envio'] else None
    pedido = repo.modificar(order_id, cambios)
    if cambios.get('estado') == 'cancelado':
        _invalidar_catalogo()
    logger.info(f"    Operacion realizada: PATCH /orders/{order_id} ({', '.join(f'{k}={v}' for k, v in cambios.items())}) "
                f"por {g.usuario['email']}")
    return api_response('resultado', {'estado': 'exito', 'mensaje': 'Pedido modificado.', 'metodo': 'PATCH',
                                      'campos_actualizados': sorted(cambios), 'realizado_por': g.usuario['email'],
                                      'pedido': pedido})


@app.route('/orders/<order_id>', methods=['DELETE'])
@solo_admin
def eliminar(order_id):
    order_id = _order_id(order_id)
    pedido = repo.eliminar(order_id)
    _invalidar_catalogo()
    logger.info(f"    Operacion realizada: DELETE /orders/{order_id} por {g.usuario['email']}")
    return api_response('resultado', {'estado': 'exito', 'mensaje': f'Pedido {order_id} eliminado.', 'metodo': 'DELETE',
                                      'id': order_id, 'estado_previo': pedido['estado'],
                                      'realizado_por': g.usuario['email']})


@app.route('/', methods=['GET'])
def index():
    return api_response('microservicio', {
        'nombre': 'Microservicio de Pedidos', 'version': '1.0.0', 'formato_por_defecto': 'xml',
        'endpoints_publicos': ['GET /health', 'GET /metrics'],
        'endpoints_protegidos': ['GET /orders', 'GET /orders/{id}', 'POST /orders', 'PATCH /orders/{id}',
                                 'DELETE /orders/{id} (admin)'],
    })


# ----------------------------------------------------------------------
# Tarea periodica: cancelar pedidos pendientes vencidos (coordinada en Redis)
# ----------------------------------------------------------------------
def barrer_vencidos() -> list:
    """Si varias instancias de pedidos corren a la vez, el candado hace que
    solo una cancele: las demas ven el candado tomado y no hacen nada."""
    candado = Candado(servicio.redis, 'lock:pedidos:barrido', ttl=max(10, config.BARRIDO_SEGUNDOS - 5))
    try:
        if not candado.intentar():
            return []
        ids = repo.cancelar_vencidos(config.ORDER_PENDING_MINUTES)
        if ids:
            _invalidar_catalogo()
            logger.info(f"    Tarea: {len(ids)} pedido(s) pendiente(s) vencido(s) cancelado(s) y stock devuelto: {ids}")
        return ids
    except (RedisNoDisponible, BaseDatosNoDisponible) as exc:
        logger.warning(f"    Tarea de pedidos vencidos omitida: {exc}")
        return []
    finally:
        candado.liberar()


def _bucle_barrido():
    while True:
        time.sleep(config.BARRIDO_SEGUNDOS)
        barrer_vencidos()


if __name__ == '__main__':
    threading.Thread(target=_bucle_barrido, name='barrido-pedidos', daemon=True).start()
    logger.info(f"Microservicio de pedidos en http://{config.HOST}:{config.PORT} (Redis {servicio.redis.destino}); "
                f"pendientes se cancelan tras {config.ORDER_PENDING_MINUTES} min")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
