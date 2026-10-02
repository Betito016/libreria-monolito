"""
Catalogo y administracion de libros: todo lo que se habla con el
microservicio de libros.

    Operacion en la app            Metodo  Endpoint                     JWT
    ----------------------------   ------  ---------------------------  ---------
    Ver catalogo / buscar          GET     /api/books?titulo=...        no
    Ver detalle (con conceptos)    GET     /api/books/{isbn}            no
    Categorias para el formulario  GET     /categories                  no
    Registrar libro                POST    /api/books                   Bearer
    Actualizacion completa         PUT     /api/books/{isbn}            Bearer
    Actualizacion parcial          PATCH   /api/books/{isbn}            Bearer
    Eliminar                       DELETE  /api/books/{isbn}            Bearer

Lectura: publica. Escritura: el servidor exige un JWT de administrador. El
header Authorization lo agrega ApiClient (api/http_client.py) segun el
metodo; este modulo no toca headers ni decide permisos, solo los reporta.
"""
from typing import Any, Dict, Optional
from urllib.parse import quote

from libreria_app.api.http_client import ApiClient, ApiResult


RUTA_LIBROS = '/api/books'


def _ruta_libro(isbn: str) -> str:
    return f"{RUTA_LIBROS}/{quote(isbn.strip(), safe='')}"


class BooksService:

    def __init__(self, api: ApiClient):
        self.api = api

    def buscar(self, filtros: Optional[Dict[str, Any]] = None, page: int = 1, page_size: int = 12) -> ApiResult:
        params = {**(filtros or {}), 'page': page, 'page_size': page_size}
        return self.api.request('books', 'GET', RUTA_LIBROS, params=params)

    def detalle(self, isbn: str) -> ApiResult:
        return self.api.request('books', 'GET', _ruta_libro(isbn))

    def categorias(self) -> ApiResult:
        return self.api.request('books', 'GET', '/categories')

    def crear(self, libro: Dict[str, Any]) -> ApiResult:
        return self.api.request('books', 'POST', RUTA_LIBROS, json_body=libro)

    def reemplazar(self, isbn: str, libro_completo: Dict[str, Any]) -> ApiResult:
        """PUT: se envia la representacion COMPLETA del libro."""
        return self.api.request('books', 'PUT', _ruta_libro(isbn), json_body=libro_completo)

    def modificar(self, isbn: str, cambios: Dict[str, Any]) -> ApiResult:
        """PATCH: se envian SOLO los campos que cambiaron."""
        return self.api.request('books', 'PATCH', _ruta_libro(isbn), json_body=cambios)

    def eliminar(self, isbn: str) -> ApiResult:
        return self.api.request('books', 'DELETE', _ruta_libro(isbn))
