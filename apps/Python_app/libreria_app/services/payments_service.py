"""
Pagos: microservicio pagos (:5002). Todo requiere JWT.

    Listar              GET    /payments?order_id=&estado=
    Detalle             GET    /payments/{id}
    Pagar un pedido     POST   /payments         {order_id, metodo, monto}  -> pedido 'pagado'
                                                 cabecera Idempotency-Key: no se cobra dos veces
    Reembolsar          PATCH  /payments/{id}    {"estado": "reembolsado"}   (administrador)
    Eliminar            DELETE /payments/{id}    (administrador; solo rechazados o reembolsados)
"""
import uuid
from typing import Optional

from libreria_app.api.http_client import ApiClient, ApiResult

METODOS = ('tarjeta', 'transferencia', 'efectivo')


class PaymentsService:

    def __init__(self, api: ApiClient):
        self.api = api

    def listar(self, order_id: Optional[int] = None, page: int = 1, page_size: int = 50) -> ApiResult:
        return self.api.request('pagos', 'GET', '/payments', params={'order_id': order_id, 'page': page,
                                                                     'page_size': page_size})

    def detalle(self, pago_id: int) -> ApiResult:
        return self.api.request('pagos', 'GET', f'/payments/{pago_id}')

    def pagar(self, order_id: int, metodo: str, monto: float) -> ApiResult:
        return self.api.request('pagos', 'POST', '/payments',
                                json_body={'order_id': order_id, 'metodo': metodo, 'monto': monto},
                                extra_headers={'Idempotency-Key': uuid.uuid4().hex})

    def reembolsar(self, pago_id: int) -> ApiResult:
        return self.api.request('pagos', 'PATCH', f'/payments/{pago_id}', json_body={'estado': 'reembolsado'})

    def eliminar(self, pago_id: int) -> ApiResult:
        return self.api.request('pagos', 'DELETE', f'/payments/{pago_id}')
