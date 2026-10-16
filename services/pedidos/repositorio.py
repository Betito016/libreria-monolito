"""
Acceso a libreria_db para el microservicio pedidos (orders, order_items y el
stock de books).

Crear un pedido: en UNA transaccion se bloquean (FOR UPDATE) las filas de los
libros pedidos, se comprueba el stock, se descuenta y se insertan el pedido y
sus lineas. Dos pedidos simultaneos del mismo libro se ordenan por el bloqueo:
nunca se vende mas de lo que hay.
"""
from typing import Any, Dict, List, Optional

import psycopg

from libreria_common.bd import BaseDatos
from libreria_common.validacion import Conflicto, NoEncontrado, ValidacionError

ESTADOS = ('pendiente', 'pagado', 'enviado', 'entregado', 'cancelado')
# Transiciones que se pueden pedir con PATCH. 'pagado' NO esta: solo lo pone
# el microservicio pagos al registrar un pago aprobado.
TRANSICIONES = {
    'pendiente': {'cancelado'},
    'pagado': {'enviado', 'cancelado'},
    'enviado': {'entregado'},
    'entregado': set(),
    'cancelado': set(),
}


def _serializar(pedido: Dict[str, Any], lineas: List[Dict[str, Any]]) -> Dict[str, Any]:
    pedido = dict(pedido)
    pedido['user_id'] = str(pedido['user_id'])
    pedido['total'] = float(pedido['total'])
    for campo in ('creado_en', 'actualizado_en'):
        pedido[campo] = pedido[campo].isoformat()
    pedido['lineas'] = [{**l, 'precio_unitario': float(l['precio_unitario']),
                         'subtotal': round(float(l['precio_unitario']) * l['cantidad'], 2)} for l in lineas]
    return pedido


class RepositorioPedidos:

    def __init__(self, bd: BaseDatos):
        self.bd = bd

    def _cargar(self, cur, order_id: int) -> Dict[str, Any]:
        cur.execute('SELECT * FROM orders WHERE id = %s', (order_id,))
        pedido = cur.fetchone()
        if not pedido:
            raise NoEncontrado(f'No existe el pedido {order_id}.')
        cur.execute("""SELECT book_isbn AS isbn, titulo, cantidad, precio_unitario FROM order_items
                       WHERE order_id = %s ORDER BY id""", (order_id,))
        return _serializar(pedido, cur.fetchall())

    def obtener(self, order_id: int) -> Dict[str, Any]:
        with self.bd.cursor() as cur:
            return self._cargar(cur, order_id)

    def listar(self, user_id: Optional[str], estado: Optional[str], page: int, page_size: int) -> Dict[str, Any]:
        condiciones, params = [], []
        if user_id:
            condiciones.append('user_id = %s'); params.append(user_id)
        if estado:
            condiciones.append('estado = %s'); params.append(estado)
        donde = ('WHERE ' + ' AND '.join(condiciones)) if condiciones else ''
        with self.bd.cursor() as cur:
            cur.execute(f'SELECT count(*) AS n FROM orders {donde}', params)
            total = cur.fetchone()['n']
            cur.execute(f"""SELECT o.*, (SELECT count(*) FROM order_items i WHERE i.order_id = o.id)::int AS total_lineas
                            FROM orders o {donde} ORDER BY o.creado_en DESC LIMIT %s OFFSET %s""",
                        params + [page_size, (page - 1) * page_size])
            pedidos = []
            for fila in cur.fetchall():
                lineas = fila.pop('total_lineas')
                pedido = _serializar(fila, [])
                pedido['total_lineas'] = lineas
                pedido.pop('lineas')
                pedidos.append(pedido)
            return {'total': total, 'pedidos': pedidos}

    def crear(self, user_id: str, email: str, items: List[Dict[str, Any]], direccion: Optional[str]) -> Dict[str, Any]:
        isbns = sorted(i['isbn'] for i in items)          # orden fijo de bloqueo: evita interbloqueos
        with self.bd.cursor() as cur:
            cur.execute('SELECT isbn, title, price, stock FROM books WHERE isbn = ANY(%s) ORDER BY isbn FOR UPDATE',
                        (isbns,))
            libros = {f['isbn']: f for f in cur.fetchall()}
            faltan = [i for i in isbns if i not in libros]
            if faltan:
                raise ValidacionError('ERR_LIBRO_INEXISTENTE', f"No existen los libros: {', '.join(faltan)}.",
                                      campo_invalido='items')
            sin_stock = [f"{libros[i['isbn']]['title']} (pedido {i['cantidad']}, hay {libros[i['isbn']]['stock']})"
                         for i in items if libros[i['isbn']]['stock'] < i['cantidad']]
            if sin_stock:
                raise Conflicto('ERR_STOCK_INSUFICIENTE', 'Stock insuficiente: ' + '; '.join(sin_stock) + '.')
            total = round(sum(float(libros[i['isbn']]['price']) * i['cantidad'] for i in items), 2)
            cur.execute("""INSERT INTO orders (user_id, user_email, total, direccion_envio)
                           VALUES (%s, %s, %s, %s) RETURNING id""", (user_id, email, total, direccion))
            order_id = cur.fetchone()['id']
            for i in items:
                libro = libros[i['isbn']]
                cur.execute("""INSERT INTO order_items (order_id, book_isbn, titulo, cantidad, precio_unitario)
                               VALUES (%s, %s, %s, %s, %s)""", (order_id, i['isbn'], libro['title'], i['cantidad'], libro['price']))
                cur.execute('UPDATE books SET stock = stock - %s WHERE isbn = %s', (i['cantidad'], i['isbn']))
            return self._cargar(cur, order_id)

    def _devolver_stock(self, cur, order_id: int) -> None:
        cur.execute("""UPDATE books b SET stock = b.stock + i.cantidad
                       FROM order_items i WHERE i.order_id = %s AND i.book_isbn = b.isbn""", (order_id,))

    def modificar(self, order_id: int, cambios: Dict[str, Any]) -> Dict[str, Any]:
        with self.bd.cursor() as cur:
            cur.execute('SELECT estado FROM orders WHERE id = %s FOR UPDATE', (order_id,))
            fila = cur.fetchone()
            if not fila:
                raise NoEncontrado(f'No existe el pedido {order_id}.')
            actual = fila['estado']
            nuevo = cambios.get('estado')
            if nuevo and nuevo != actual:
                if nuevo == 'pagado':
                    raise Conflicto('ERR_TRANSICION_INVALIDA',
                                    "Un pedido solo pasa a 'pagado' al registrar su pago en el microservicio pagos.")
                if nuevo not in TRANSICIONES[actual]:
                    raise Conflicto('ERR_TRANSICION_INVALIDA', f"No se puede pasar de '{actual}' a '{nuevo}'. "
                                    f"Permitido: {', '.join(sorted(TRANSICIONES[actual])) or 'ninguno'}.")
                if nuevo == 'cancelado' and actual == 'pagado':
                    raise Conflicto('ERR_TRANSICION_INVALIDA',
                                    'El pedido ya está pagado: se cancela reembolsando su pago en el microservicio pagos.')
                if nuevo == 'cancelado':
                    self._devolver_stock(cur, order_id)
            if 'direccion_envio' in cambios and actual not in ('pendiente', 'pagado'):
                raise Conflicto('ERR_PEDIDO_EN_CAMINO', 'La dirección solo se puede cambiar antes del envío.')
            asignaciones, valores = [], []
            for campo in ('estado', 'direccion_envio'):
                if campo in cambios:
                    asignaciones.append(f'{campo} = %s'); valores.append(cambios[campo])
            cur.execute(f"UPDATE orders SET {', '.join(asignaciones)}, actualizado_en = now() WHERE id = %s",
                        valores + [order_id])
            return self._cargar(cur, order_id)

    def eliminar(self, order_id: int) -> Dict[str, Any]:
        try:
            with self.bd.cursor() as cur:
                pedido = self._cargar(cur, order_id)
                if pedido['estado'] not in ('pendiente', 'cancelado'):
                    raise Conflicto('ERR_PEDIDO_NO_ELIMINABLE',
                                    f"Un pedido '{pedido['estado']}' no se puede eliminar (tiene un pago o ya se envió).")
                if pedido['estado'] == 'pendiente':
                    self._devolver_stock(cur, order_id)
                cur.execute('DELETE FROM orders WHERE id = %s', (order_id,))
                return pedido
        except psycopg.errors.ForeignKeyViolation:
            # Un pedido cancelado por reembolso conserva su pago como historial.
            raise Conflicto('ERR_PEDIDO_CON_PAGOS', 'El pedido tiene pagos registrados (historial) y no se puede eliminar.')

    def cancelar_vencidos(self, minutos: int) -> List[int]:
        """Cancela los pedidos pendientes mas viejos que `minutos` y devuelve su stock."""
        with self.bd.cursor() as cur:
            cur.execute("""SELECT id FROM orders WHERE estado = 'pendiente'
                           AND creado_en < now() - make_interval(mins => %s) FOR UPDATE SKIP LOCKED""", (minutos,))
            ids = [f['id'] for f in cur.fetchall()]
            for order_id in ids:
                self._devolver_stock(cur, order_id)
                cur.execute("UPDATE orders SET estado = 'cancelado', actualizado_en = now() WHERE id = %s", (order_id,))
            return ids
