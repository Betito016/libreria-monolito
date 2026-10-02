"""Especificacion OpenAPI 3.0 del microservicio de libros."""

FORMAT_PARAM = {
    "name": "format", "in": "query", "required": False,
    "description": "Formato de la respuesta. Si se omite, el microservicio responde en XML.",
    "schema": {"type": "string", "enum": ["xml", "json"], "default": "xml"},
}

ISBN_PARAM = {
    "name": "isbn", "in": "path", "required": True,
    "description": "ISBN-10 o ISBN-13, con o sin guiones.",
    "schema": {"type": "string"}, "example": "9780451524935",
}

IMAGEN_SCHEMA = {
    "type": "object",
    "properties": {
        "url": {"type": "string", "format": "uri"},
        "texto_alt": {"type": "string"},
        "principal": {"type": "boolean"},
    },
}

LIBRO_SCHEMA = {
    "type": "object",
    "properties": {
        "isbn": {"type": "string", "example": "9780451524935"},
        "titulo": {"type": "string", "example": "1984"},
        "autores": {"type": "array", "items": {"type": "string"}, "example": ["Matías Ortega"]},
        "generos": {"type": "array", "items": {"type": "string"}, "example": ["Fiction"]},
        "anio": {"type": "integer", "example": 1949},
        "precio": {"type": "number", "example": 430.0},
        "stock": {"type": "integer", "example": 25},
        "formato": {"type": "string", "example": "Paperback"},
        "categoria": {"type": "string", "example": "Literatura"},
        "imagen_principal": {"type": "string", "format": "uri", "nullable": True},
        "imagenes": {"type": "array", "items": IMAGEN_SCHEMA},
    },
}

LIBRO_DETALLE_SCHEMA = {
    **LIBRO_SCHEMA,
    "properties": {
        **LIBRO_SCHEMA["properties"],
        "conceptos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"nombre": {"type": "string"}, "definicion": {"type": "string"}},
            },
        },
    },
}

CUERPO_LIBRO = {
    "type": "object",
    "properties": {
        "isbn": {"type": "string", "example": "9786047750001"},
        "titulo": {"type": "string", "example": "PRUEBA INTEGRACION - 604775"},
        "autores": {"type": "array", "items": {"type": "string"}, "example": ["Humberto Vargas"]},
        "generos": {"type": "array", "items": {"type": "string"}, "example": ["Programming"]},
        "anio": {"type": "integer", "example": 2026},
        "precio": {"type": "number", "example": 499.0},
        "stock": {"type": "integer", "example": 10},
        "formato": {"type": "string", "example": "Paperback"},
        "categoria": {"type": "string", "example": "Educación"},
        "imagenes": {"type": "array", "items": {"type": "string", "format": "uri"}},
    },
}

ERROR_SCHEMA = {
    "type": "object",
    "properties": {
        "estado": {"type": "string", "example": "error"},
        "codigo_error": {"type": "string", "example": "ERR_ISBN_DUPLICADO"},
        "mensaje": {"type": "string"},
    },
}


def _dual(schema: dict) -> dict:
    return {"application/xml": {"schema": schema}, "application/json": {"schema": schema}}


def _cuerpo(schema: dict, requeridos: list) -> dict:
    return {
        "required": True,
        "content": {"application/json": {"schema": {**schema, "required": requeridos}}},
    }


def _resultado(descripcion: str) -> dict:
    return {
        "description": descripcion,
        "content": _dual({
            "type": "object",
            "properties": {
                "estado": {"type": "string", "example": "exito"},
                "metodo": {"type": "string"},
                "libro": LIBRO_DETALLE_SCHEMA,
            },
        }),
    }


def _error(descripcion: str) -> dict:
    return {"description": descripcion, "content": _dual(ERROR_SCHEMA)}


ERRORES_ESCRITURA = {
    "401": _error("Sin token, esquema distinto de Bearer, firma invalida o token expirado "
                  "(ERR_TOKEN_AUSENTE, ERR_TOKEN_INVALIDO, ERR_TOKEN_EXPIRADO)"),
    "403": _error("Token valido, pero el usuario no es administrador (ERR_SIN_PERMISOS)"),
    "503": _error("PostgreSQL no disponible"),
}

# Solo las escrituras la declaran: la lectura del catalogo es publica.
SEGURIDAD_JWT = [{"bearerAuth": []}]


def build_openapi_spec(server_url: str) -> dict:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Microservicio de Libros - Libreria en Linea",
            "version": "1.1.0",
            "description": (
                "Catalogo de libros (Flask + Psycopg 3 + PostgreSQL).\n\n"
                "**Formato:** XML por defecto; JSON con `?format=json`.\n\n"
                "**Lectura publica.** Crear, reemplazar, modificar y eliminar requieren "
                "`Authorization: Bearer <token>` con un **JWT** emitido por el microservicio "
                "de **login** (`POST /login` → `token.access_token`) a un **administrador**.\n\n"
                "Las rutas tambien responden sin el prefijo `/api` (`/books`, `/books/{isbn}`).\n\n"
                "**PUT vs PATCH:** PUT reemplaza el libro completo y exige todos los campos; "
                "PATCH modifica solo los campos enviados."
            ),
        },
        "servers": [{"url": server_url}],
        "components": {"securitySchemes": {"bearerAuth": {
            "type": "http", "scheme": "bearer", "bearerFormat": "JWT",
            "description": "access_token devuelto por POST /login del microservicio de login.",
        }}},
        "paths": {
            "/health": {"get": {
                "summary": "Estado del servicio, de PostgreSQL y del login",
                "parameters": [FORMAT_PARAM],
                "responses": {
                    "200": {"description": "ok, o degradado si el login no responde (no se emiten tokens nuevos)",
                            "content": _dual({"type": "object"})},
                    "503": {"description": "degradado: PostgreSQL no disponible",
                            "content": _dual({"type": "object"})},
                },
            }},
            "/categories": {"get": {
                "summary": "Categorias validas",
                "parameters": [FORMAT_PARAM],
                "responses": {"200": {"description": "Lista de categorias", "content": _dual({"type": "object"})}},
            }},
            "/api/books": {
                "get": {
                    "summary": "Catalogo paginado con filtros",
                    "parameters": [
                        FORMAT_PARAM,
                        {"name": "isbn", "in": "query", "schema": {"type": "string"},
                         "description": "Coincidencia parcial"},
                        {"name": "titulo", "in": "query", "schema": {"type": "string"},
                         "description": "Coincidencia parcial, sin distinguir mayusculas"},
                        {"name": "anio", "in": "query", "schema": {"type": "integer"}},
                        {"name": "precio_min", "in": "query", "schema": {"type": "number"}},
                        {"name": "precio_max", "in": "query", "schema": {"type": "number"}},
                        {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                        {"name": "page_size", "in": "query", "schema": {"type": "integer", "default": 12}},
                    ],
                    "responses": {
                        "200": {"description": "Pagina del catalogo", "content": _dual({
                            "type": "object",
                            "properties": {
                                "total": {"type": "integer"},
                                "page": {"type": "integer"},
                                "total_pages": {"type": "integer"},
                                "libros": {"type": "array", "items": LIBRO_SCHEMA},
                            },
                        })},
                        "400": _error("Filtro invalido (ERR_FILTRO_INVALIDO)"),
                    },
                },
                "post": {
                    "summary": "Crear un libro (JWT de administrador)",
                    "security": SEGURIDAD_JWT,
                    "parameters": [FORMAT_PARAM],
                    "requestBody": _cuerpo(
                        CUERPO_LIBRO,
                        ["isbn", "titulo", "autores", "anio", "precio", "stock", "formato", "categoria"],
                    ),
                    "responses": {
                        "201": _resultado("Libro creado; cabecera Location con su URL"),
                        "400": _error("Datos invalidos o categoria inexistente"),
                        "409": _error("ISBN duplicado (ERR_ISBN_DUPLICADO)"),
                        **ERRORES_ESCRITURA,
                    },
                },
            },
            "/api/books/{isbn}": {
                "get": {
                    "summary": "Detalle del libro, con sus conceptos",
                    "parameters": [ISBN_PARAM, FORMAT_PARAM],
                    "responses": {
                        "200": {"description": "Detalle", "content": _dual(LIBRO_DETALLE_SCHEMA)},
                        "400": _error("ISBN con formato invalido"),
                        "404": _error("Libro inexistente (ERR_LIBRO_NO_ENCONTRADO)"),
                    },
                },
                "put": {
                    "summary": "Reemplazar el libro completo (JWT de administrador)",
                    "security": SEGURIDAD_JWT,
                    "description": (
                        "Exige TODOS los campos, incluidas las listas autores, generos e "
                        "imagenes. Lo que no se envia no se conserva. El ISBN no cambia."
                    ),
                    "parameters": [ISBN_PARAM, FORMAT_PARAM],
                    "requestBody": _cuerpo(
                        CUERPO_LIBRO,
                        ["titulo", "autores", "generos", "anio", "precio", "stock",
                         "formato", "categoria", "imagenes"],
                    ),
                    "responses": {
                        "200": _resultado("Libro reemplazado"),
                        "400": _error("Faltan campos (ERR_CAMPOS_OBLIGATORIOS) o datos invalidos"),
                        "404": _error("Libro inexistente"),
                        **ERRORES_ESCRITURA,
                    },
                },
                "patch": {
                    "summary": "Modificar solo algunos campos (JWT de administrador)",
                    "security": SEGURIDAD_JWT,
                    "description": "Cualquier subconjunto de campos; el resto queda igual.",
                    "parameters": [ISBN_PARAM, FORMAT_PARAM],
                    "requestBody": _cuerpo(CUERPO_LIBRO, []),
                    "responses": {
                        "200": _resultado("Libro modificado"),
                        "400": _error("Sin cambios o datos invalidos"),
                        "404": _error("Libro inexistente"),
                        **ERRORES_ESCRITURA,
                    },
                },
                "delete": {
                    "summary": "Eliminar un libro (JWT de administrador)",
                    "security": SEGURIDAD_JWT,
                    "parameters": [ISBN_PARAM, FORMAT_PARAM],
                    "responses": {
                        "200": {"description": "Libro eliminado", "content": _dual({"type": "object"})},
                        "404": _error("Libro inexistente"),
                        "409": _error("El libro tiene conceptos o clasificaciones (ERR_LIBRO_EN_USO)"),
                        **ERRORES_ESCRITURA,
                    },
                },
            },
        },
    }


SWAGGER_UI_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8" />
    <title>API Docs - Microservicio de Libros</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" />
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        window.onload = function () {
            SwaggerUIBundle({ url: "/openapi.json", dom_id: "#swagger-ui" });
        };
    </script>
</body>
</html>
"""
