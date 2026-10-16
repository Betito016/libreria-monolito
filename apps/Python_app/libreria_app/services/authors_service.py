"""
Autores y su relacion con libros: microservicio authors (:5005).
Lecturas publicas (con cache en Redis); escrituras con JWT de administrador.

    Listar / buscar     GET    /authors?nombre=
    Detalle con libros  GET    /authors/{id}
    Crear               POST   /authors          {nombre, nacionalidad, biografia, libros: [isbn]}
    Modificar           PATCH  /authors/{id}     (libros reemplaza las relaciones)
    Eliminar            DELETE /authors/{id}     (409 si aun tiene libros)
"""
from typing import Any, Dict, Optional

from libreria_app.api.http_client import ApiClient, ApiResult


class AuthorsService:

    def __init__(self, api: ApiClient):
        self.api = api

    def listar(self, nombre: Optional[str] = None, page: int = 1, page_size: int = 50) -> ApiResult:
        return self.api.request('authors', 'GET', '/authors', params={'nombre': nombre, 'page': page, 'page_size': page_size})

    def detalle(self, autor_id: int) -> ApiResult:
        return self.api.request('authors', 'GET', f'/authors/{autor_id}')

    def crear(self, datos: Dict[str, Any]) -> ApiResult:
        return self.api.request('authors', 'POST', '/authors', json_body=datos)

    def modificar(self, autor_id: int, cambios: Dict[str, Any]) -> ApiResult:
        return self.api.request('authors', 'PATCH', f'/authors/{autor_id}', json_body=cambios)

    def eliminar(self, autor_id: int) -> ApiResult:
        return self.api.request('authors', 'DELETE', f'/authors/{autor_id}')
