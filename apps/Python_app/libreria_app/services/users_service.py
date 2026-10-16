"""
Usuarios y roles: todo lo que se habla con el microservicio users (:5004).
Todo requiere JWT (lectura administrativa); /roles es publico.

    Listar / buscar     GET    /users?q=&role_id=&activo=
    Detalle             GET    /users/{id}
    Roles               GET    /roles
    Crear               POST   /users
    Modificar           PATCH  /users/{id}   (rol, contrasena o estado revocan sus tokens)
    Eliminar            DELETE /users/{id}
"""
from typing import Any, Dict, Optional

from libreria_app.api.http_client import ApiClient, ApiResult


class UsersService:

    def __init__(self, api: ApiClient):
        self.api = api

    def listar(self, filtros: Optional[Dict[str, Any]] = None, page: int = 1, page_size: int = 50) -> ApiResult:
        return self.api.request('users', 'GET', '/users', params={**(filtros or {}), 'page': page, 'page_size': page_size})

    def detalle(self, user_id: str) -> ApiResult:
        return self.api.request('users', 'GET', f'/users/{user_id}')

    def roles(self) -> ApiResult:
        return self.api.request('users', 'GET', '/roles')

    def crear(self, datos: Dict[str, Any]) -> ApiResult:
        return self.api.request('users', 'POST', '/users', json_body=datos)

    def modificar(self, user_id: str, cambios: Dict[str, Any]) -> ApiResult:
        return self.api.request('users', 'PATCH', f'/users/{user_id}', json_body=cambios)

    def eliminar(self, user_id: str) -> ApiResult:
        return self.api.request('users', 'DELETE', f'/users/{user_id}')
