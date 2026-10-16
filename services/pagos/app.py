"""
Microservicio pagos: registra pagos y actualiza el estado de los pedidos.

Stack: Flask + Psycopg 3 + PostgreSQL (libreria_db) + Redis. Puerto 5002.
XML por defecto, JSON con ?format=json. Todo requiere JWT.

    GET    /payments        Listado: administrador todos (filtros order_id, estado, user_id);
                            un cliente solo los suyos                                  (JWT)
    GET    /payments/{id}   Detalle (administrador o dueno)                            (JWT)
    POST   /payments        Pagar un pedido pendiente: {order_id, metodo, monto?}      (JWT, dueno o admin)
                            -> pedido 'pagado' en la misma transaccion. Cabecera opcional Idempotency-Key
    PATCH  /payments/{id}   {"estado": "reembolsado"}: reembolso -> pedido cancelado
                            y stock devuelto                                           (JWT administrador)
    DELETE /payments/{id}   Eliminar un pago rechazado o reembolsado                   (JWT administrador)
    GET    /health, /metrics

Redis:
    lock:order:<order_id>            candado: dos pagos simultaneos del mismo pedido no se procesan a la vez
    payment:idem:<user_id>:<clave>   un reintento con la misma Idempotency-Key no cobra dos veces (24 h)
    books:*                          un reembolso devuelve stock: se invalida la cache del catalogo
"""
from datetime import datetime, timezone

from flask import g, request

import config
from libreria_common.bd import BaseDatos, dsn
from libreria_common.candado import Candado
from libreria_common.flask_base import ServicioBase
from libreria_common.respuestas import api_response, leer_json
from libreria_common.seguridad import AuthError, ROL_ADMINISTRADOR
from libreria_common.validacion import ValidacionError, entero, numero, requeridos, solo_campos
from repositorio import RepositorioPagos

servicio = ServicioBase.crear('pagos', __name__)
app, logger, cache = servicio.app, servicio.logger, servicio.cache
bd = BaseDatos(dsn(config.DB_HOST, config.DB_PORT, config.DB_NAME, config.DB_USER, config.DB_PASSWORD), config.DB_NAME)
repo = RepositorioPagos(bd)
autenticado = servicio.auth.requiere_jwt()
solo_admin = servicio.auth.requiere_jwt(roles=[ROL_ADMINISTRADOR])


def _es_admin() -> bool:
    return g.usuario['role_id'] == ROL_ADMINISTRADOR


def _id(valor: str, nombre: str) -> int:
    if not valor.isdigit():
        raise ValidacionError('ERR_ID_INVALIDO', f'El id del {nombre} debe ser un número entero.')
    return int(valor)


@app.route('/health', methods=['GET'])
def health():
    postgres, redis_estado = bd.ping(), servicio.redis.estado()
    return api_response('health', {
        'estado': 'ok' if postgres['conectado'] and redis_estado['disponible'] else 'degradado',
        'microservicio': 'pagos', 'postgresql': postgres, 'redis': redis_estado,
        'capacidades': {'lectura': postgres['conectado'] and redis_estado['disponible'],
                        'escritura': postgres['conectado'] and redis_estado['disponible']},
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }, status=200 if postgres['conectado'] else 503)


@app.route('/payments', methods=['GET'])
@autenticado
def listar():
    try:
        page = max(1, int(request.args.get('page', 1)))
        size = min(config.PAGE_SIZE_MAX, max(1, int(request.args.get('page_size', config.PAGE_SIZE_DEFAULT))))
        order_id = int(request.args['order_id']) if request.args.get('order_id') else None
    except ValueError:
        raise ValidacionError('ERR_FILTRO_INVALIDO', 'page, page_size y order_id deben ser enteros.')
    estado = request.args.get('estado') or None
    user_id = (request.args.get('user_id') or None) if _es_admin() else g.usuario['user_id']
    r = repo.listar(user_id, order_id, estado, page, size)
    return api_response('pagos', {**r, 'page': page, 'page_size': size,
                                  'total_pages': max(1, (r['total'] + size - 1) // size)})


@app.route('/payments/<pago_id>', methods=['GET'])
@autenticado
def detalle(pago_id):
    pago = repo.obtener(_id(pago_id, 'pago'))
    if not _es_admin() and pago['user_id'] != g.usuario['user_id']:
        raise AuthError('ERR_SIN_PERMISOS', 'Solo puedes consultar tus propios pagos.', 403)
    return api_response('pago', pago)


@app.route('/payments', methods=['POST'])
@autenticado
def pagar():
    datos = leer_json()
    solo_campos(datos, ('order_id', 'metodo', 'monto'))
    requeridos(datos, ('order_id', 'metodo'))
    order_id = entero(datos, 'order_id', 1)
    if datos['metodo'] not in config.METODOS:
        raise ValidacionError('ERR_METODO_PAGO_INVALIDO', f"metodo debe ser uno de: {', '.join(config.METODOS)}.",
                              campo_invalido='metodo')
    monto = numero(datos, 'monto', 0.01)

    pedido = repo.pedido(order_id)
    if not _es_admin() and pedido['user_id'] != g.usuario['user_id']:
        raise AuthError('ERR_SIN_PERMISOS', 'Solo puedes pagar tus propios pedidos.', 403)

    clave_idem = (request.headers.get('Idempotency-Key') or '').strip()[:80]
    clave_redis = f"payment:idem:{g.usuario['user_id']}:{clave_idem}" if clave_idem else None
    if clave_redis:
        previo = servicio.redis.ejecutar(lambda r: r.get(clave_redis), critico=True)
        if previo:
            logger.info(f"    Idempotency-Key repetida: se devuelve el pago {previo} sin cobrar de nuevo")
            return api_response('resultado', {'estado': 'exito', 'mensaje': 'Pago ya registrado con esa Idempotency-Key.',
                                              'metodo': 'POST', 'repetido': True, 'pago': repo.obtener(int(previo))})

    # Candado distribuido: si llega otro pago del mismo pedido al mismo tiempo
    # (doble clic, dos dispositivos), el segundo recibe 409 en vez de esperar.
    with Candado(servicio.redis, f'lock:order:{order_id}', ttl=config.CANDADO_SEGUNDOS,
                 mensaje='Ya se está procesando un pago de este pedido.'):
        pago = repo.registrar(order_id, pedido['user_id'], datos['metodo'], monto)
    if clave_redis:
        servicio.redis.ejecutar(lambda r: r.set(clave_redis, pago['id'], ex=config.IDEMPOTENCIA_HORAS * 3600),
                                critico=False)
    logger.info(f"    Operacion realizada: POST /payments {pago['id']} ({pago['metodo']}, {pago['monto']:.2f}) "
                f"-> pedido {order_id} 'pagado', por {g.usuario['email']}")
    return api_response('resultado', {'estado': 'exito', 'mensaje': f'Pago aprobado; el pedido {order_id} quedó pagado.',
                                      'metodo': 'POST', 'realizado_por': g.usuario['email'], 'pago': pago},
                        status=201, headers={'Location': f"/payments/{pago['id']}"})


@app.route('/payments/<pago_id>', methods=['PATCH'])
@solo_admin
def modificar(pago_id):
    pago_id = _id(pago_id, 'pago')
    datos = leer_json()
    solo_campos(datos, ('estado',))
    if datos.get('estado') != 'reembolsado':
        raise ValidacionError('ERR_ESTADO_INVALIDO', 'El único cambio permitido es {"estado": "reembolsado"}.',
                              estados_validos=['reembolsado'])
    actual = repo.obtener(pago_id)
    with Candado(servicio.redis, f"lock:order:{actual['order_id']}", ttl=config.CANDADO_SEGUNDOS):
        pago = repo.reembolsar(pago_id)
    cache.invalidar(['books:*'])
    logger.info(f"    Operacion realizada: PATCH /payments/{pago_id} reembolso -> pedido {pago['order_id']} cancelado "
                f"y stock devuelto, por {g.usuario['email']}")
    return api_response('resultado', {'estado': 'exito', 'mensaje': 'Pago reembolsado; el pedido se canceló y el stock regresó.',
                                      'metodo': 'PATCH', 'campos_actualizados': ['estado'],
                                      'realizado_por': g.usuario['email'], 'pago': pago})


@app.route('/payments/<pago_id>', methods=['DELETE'])
@solo_admin
def eliminar(pago_id):
    pago_id = _id(pago_id, 'pago')
    pago = repo.eliminar(pago_id)
    logger.info(f"    Operacion realizada: DELETE /payments/{pago_id} por {g.usuario['email']}")
    return api_response('resultado', {'estado': 'exito', 'mensaje': f'Pago {pago_id} eliminado.', 'metodo': 'DELETE',
                                      'id': pago_id, 'estado_previo': pago['estado'], 'realizado_por': g.usuario['email']})


@app.route('/', methods=['GET'])
def index():
    return api_response('microservicio', {
        'nombre': 'Microservicio de Pagos', 'version': '1.0.0', 'formato_por_defecto': 'xml',
        'endpoints_publicos': ['GET /health', 'GET /metrics'],
        'endpoints_protegidos': ['GET /payments', 'GET /payments/{id}', 'POST /payments',
                                 'PATCH /payments/{id} (admin)', 'DELETE /payments/{id} (admin)'],
    })


if __name__ == '__main__':
    logger.info(f"Microservicio de pagos en http://{config.HOST}:{config.PORT} (Redis {servicio.redis.destino})")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
