"""
Acceso a libreria_db para el microservicio pagos.

Registrar un pago y cambiar el estado del pedido van en UNA transaccion:
    1. bloquear el pedido (FOR UPDATE)
    2. comprobar que esta 'pendiente' y que el monto coincide con su total
    3. insertar el pago aprobado y marcar el pedido 'pagado'
Un reembolso marca el pago 'reembolsado', cancela el pedido y devuelve el
stock, tambien en una sola transaccion.
"""
import secrets
from typing import Any, Dict, Optional

import psycopg

from libreria_common.bd import BaseDatos
from libreria_common.validacion import Conflicto, NoEncontrado, ValidacionError


def _serializar(p: Dict[str, Any]) -> Dict[str, Any]:
    p = dict(p)
    p['user_id'] = str(p['user_id'])
    p['monto'] = float(p['monto'])
    for campo in ('creado_en', 'actualizado_en'):
        if p.get(campo) is not None:
            p[campo] = p[campo].isoformat()
    return p


class RepositorioPagos:

    def __init__(self, bd: BaseDatos):
        self.bd = bd

    def obtener(self, pago_id: int) -> Dict[str, Any]:
        with self.bd.cursor() as cur:
            cur.execute("""SELECT p.*, o.estado AS estado_pedido FROM payments p JOIN orders o ON o.id = p.order_id
                           WHERE p.id = %s""", (pago_id,))
            fila = cur.fetchone()
        if not fila:
            raise NoEncontrado(f'No existe el pago {pago_id}.')
        return _serializar(fila)

    def listar(self, user_id: Optional[str], order_id: Optional[int], estado: Optional[str],
               page: int, page_size: int) -> Dict[str, Any]:
        condiciones, params = [], []
        for columna, valor in (('p.user_id', user_id), ('p.order_id', order_id), ('p.estado', estado)):
            if valor is not None:
                condiciones.append(f'{columna} = %s'); params.append(valor)
        donde = ('WHERE ' + ' AND '.join(condiciones)) if condiciones else ''
        with self.bd.cursor() as cur:
            cur.execute(f'SELECT count(*) AS n FROM payments p {donde}', params)
            total = cur.fetchone()['n']
            cur.execute(f"""SELECT p.*, o.estado AS estado_pedido FROM payments p JOIN orders o ON o.id = p.order_id
                            {donde} ORDER BY p.creado_en DESC LIMIT %s OFFSET %s""",
                        params + [page_size, (page - 1) * page_size])
            return {'total': total, 'pagos': [_serializar(f) for f in cur.fetchall()]}

    def pedido(self, order_id: int) -> Dict[str, Any]:
        with self.bd.cursor() as cur:
            cur.execute('SELECT id, user_id, estado, total FROM orders WHERE id = %s', (order_id,))
            fila = cur.fetchone()
        if not fila:
            raise NoEncontrado(f'No existe el pedido {order_id}.')
        return {**fila, 'user_id': str(fila['user_id']), 'total': float(fila['total'])}

    def registrar(self, order_id: int, user_id: str, metodo: str, monto: Optional[float]) -> Dict[str, Any]:
        try:
            with self.bd.cursor() as cur:
                cur.execute('SELECT id, estado, total FROM orders WHERE id = %s FOR UPDATE', (order_id,))
                pedido = cur.fetchone()
                if not pedido:
                    raise NoEncontrado(f'No existe el pedido {order_id}.')
                if pedido['estado'] != 'pendiente':
                    raise Conflicto('ERR_PEDIDO_NO_PAGABLE', f"El pedido está '{pedido['estado']}': solo se paga un pedido pendiente.")
                total = float(pedido['total'])
                if monto is not None and round(monto, 2) != round(total, 2):
                    raise ValidacionError('ERR_MONTO_INCORRECTO', f'El monto debe ser igual al total del pedido ({total:.2f}).',
                                          campo_invalido='monto')
                cur.execute("""INSERT INTO payments (order_id, user_id, monto, metodo, estado, referencia)
                               VALUES (%s, %s, %s, %s, 'aprobado', %s) RETURNING id""",
                            (order_id, user_id, total, metodo, f'PAG-{secrets.token_hex(6).upper()}'))
                pago_id = cur.fetchone()['id']
                cur.execute("UPDATE orders SET estado = 'pagado', actualizado_en = now() WHERE id = %s", (order_id,))
        except psycopg.errors.UniqueViolation:
            raise Conflicto('ERR_PEDIDO_YA_PAGADO', 'El pedido ya tiene un pago aprobado.')
        return self.obtener(pago_id)

    def reembolsar(self, pago_id: int) -> Dict[str, Any]:
        with self.bd.cursor() as cur:
            cur.execute('SELECT * FROM payments WHERE id = %s FOR UPDATE', (pago_id,))
            pago = cur.fetchone()
            if not pago:
                raise NoEncontrado(f'No existe el pago {pago_id}.')
            if pago['estado'] != 'aprobado':
                raise Conflicto('ERR_PAGO_NO_REEMBOLSABLE', f"El pago está '{pago['estado']}': solo se reembolsa uno aprobado.")
            cur.execute('SELECT estado FROM orders WHERE id = %s FOR UPDATE', (pago['order_id'],))
            if cur.fetchone()['estado'] not in ('pagado',):
                raise Conflicto('ERR_PEDIDO_YA_ENVIADO', 'El pedido ya se envió: no se puede reembolsar desde aquí.')
            cur.execute("UPDATE payments SET estado = 'reembolsado', actualizado_en = now() WHERE id = %s", (pago_id,))
            cur.execute("UPDATE orders SET estado = 'cancelado', actualizado_en = now() WHERE id = %s", (pago['order_id'],))
            cur.execute("""UPDATE books b SET stock = b.stock + i.cantidad
                           FROM order_items i WHERE i.order_id = %s AND i.book_isbn = b.isbn""", (pago['order_id'],))
        return self.obtener(pago_id)

    def eliminar(self, pago_id: int) -> Dict[str, Any]:
        pago = self.obtener(pago_id)
        if pago['estado'] == 'aprobado':
            raise Conflicto('ERR_PAGO_APROBADO', 'Un pago aprobado no se elimina: primero reembólsalo (PATCH {"estado": "reembolsado"}).')
        with self.bd.cursor() as cur:
            cur.execute('DELETE FROM payments WHERE id = %s', (pago_id,))
        return pago
