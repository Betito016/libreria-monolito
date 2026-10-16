"""
Pedidos: microservicio pedidos (:5003). Todo requiere JWT: un cliente ve y
cancela sus pedidos; un administrador ve todos y gestiona los envios.

    Listar              GET    /orders?estado=
    Detalle con lineas  GET    /orders/{id}
    Crear               POST   /orders           {items: [{isbn, cantidad}], direccion_envio}
                                                 cabecera Idempotency-Key: un reintento no duplica
    Cambiar estado      PATCH  /orders/{id}      {estado} | {direccion_envio}
    Eliminar            DELETE /orders/{id}      (administrador)
"""
import uuid
from typing import Any, Dict, List, Optional

from libreria_app.api.http_client import ApiClient, ApiResult


class OrdersService:

    def __init__(self, api: ApiClient):
        self.api = api

    def listar(self, estado: Optional[str] = None, page: int = 1, page_size: int = 50) -> ApiResult:
        return self.api.request('pedidos', 'GET', '/orders', params={'estado': estado, 'page': page, 'page_size': page_size})

    def detalle(self, order_id: int) -> ApiResult:
        return self.api.request('pedidos', 'GET', f'/orders/{order_id}')

    def crear(self, items: List[Dict[str, Any]], direccion: Optional[str] = None) -> ApiResult:
        cuerpo = {'items': items}
        if direccion:
            cuerpo['direccion_envio'] = direccion
        # Clave unica por intento de compra: si la red falla y se reintenta,
        # el servidor devuelve el mismo pedido en lugar de crear otro.
        return self.api.request('pedidos', 'POST', '/orders', json_body=cuerpo,
                                extra_headers={'Idempotency-Key': uuid.uuid4().hex})

    def modificar(self, order_id: int, cambios: Dict[str, Any]) -> ApiResult:
        return self.api.request('pedidos', 'PATCH', f'/orders/{order_id}', json_body=cambios)

    def eliminar(self, order_id: int) -> ApiResult:
        return self.api.request('pedidos', 'DELETE', f'/orders/{order_id}')
