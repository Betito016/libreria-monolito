"""
Generador de la especificación OpenAPI 3.0 para los endpoints REST bilingües
(XML/JSON) del Módulo SOAP de Clasificación de Librería.

El endpoint /soap (SOAP 1.1) queda fuera de este documento porque su
contrato ya está descrito por su propio WSDL en /soap?wsdl.
"""

def build_openapi_spec(server_url: str) -> dict:
    format_param = {
        "name": "format",
        "in": "query",
        "required": False,
        "description": "Formato de la respuesta. Si se omite, el microservicio responde en XML.",
        "schema": {"type": "string", "enum": ["xml", "json"], "default": "xml"}
    }

    book_schema = {
        "type": "object",
        "properties": {
            "isbn": {"type": "string", "example": "9780451524935"},
            "titulo": {"type": "string", "example": "1984"},
            "anio": {"type": "integer", "example": 1949},
            "precio": {"type": "number", "format": "float", "example": 430.0},
            "stock": {"type": "integer", "example": 25},
            "formato": {"type": "string", "example": "Paperback"},
            "categoria": {"type": "string", "example": "Fiction"},
            "autores": {"type": "array", "items": {"type": "string"}, "example": ["Matías Ortega"]},
            "imagen": {"type": "string", "format": "uri",
                       "example": "https://covers.openlibrary.org/b/isbn/9780451524935-L.jpg"}
        }
    }

    book_cover_schema = {
        "type": "object",
        "properties": {
            "isbn": {"type": "string", "example": "9780451524935"},
            "titulo": {"type": "string", "example": "1984"},
            "imagen": {"type": "string", "format": "uri",
                       "example": "https://covers.openlibrary.org/b/isbn/9780451524935-L.jpg"}
        }
    }

    concept_schema = {
        "type": "object",
        "properties": {
            "concepto_id": {"type": "integer", "example": 1},
            "nombre": {"type": "string", "example": "IaaS"},
            "definicion": {"type": "string"},
            "libros": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "isbn": {"type": "string"},
                        "titulo": {"type": "string"},
                        "anio": {"type": "integer"}
                    }
                }
            }
        }
    }

    error_schema = {
        "type": "object",
        "properties": {
            "codigo_error": {"type": "string", "example": "ERR_BOOK_NOT_FOUND"},
            "mensaje": {"type": "string"}
        }
    }

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Módulo SOAP de Clasificación de Librería - API Bilingüe (XML/JSON)",
            "description": (
                "Endpoints REST del microservicio de librería que responden en XML por defecto "
                "y en JSON al enviar el parámetro `format=json`. El endpoint SOAP 1.1 "
                "independiente (`/soap`) se documenta en su propio contrato WSDL (`/soap?wsdl`) "
                "y no forma parte de este documento OpenAPI."
            ),
            "version": "1.0.0"
        },
        "servers": [{"url": server_url}],
        "paths": {
            "/books": {
                "get": {
                    "summary": "Listar el catálogo de libros, paginado",
                    "parameters": [
                        format_param,
                        {
                            "name": "page",
                            "in": "query",
                            "required": False,
                            "description": "Número de página (1-indexada). Por defecto 1.",
                            "schema": {"type": "integer", "default": 1, "minimum": 1}
                        },
                        {
                            "name": "page_size",
                            "in": "query",
                            "required": False,
                            "description": "Cantidad de libros por página (máx. 100). Por defecto 12.",
                            "schema": {"type": "integer", "default": 12, "minimum": 1, "maximum": 100}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Página del catálogo de libros",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "total": {"type": "integer", "description": "Total de libros en el catálogo"},
                                            "page": {"type": "integer"},
                                            "page_size": {"type": "integer"},
                                            "total_pages": {"type": "integer"},
                                            "libros": {"type": "array", "items": book_schema}
                                        }
                                    }
                                },
                                "application/xml": {"schema": {"type": "string"}}
                            }
                        }
                    }
                }
            },
            "/books/{isbn}": {
                "get": {
                    "summary": "Obtener un libro por ISBN",
                    "parameters": [
                        {
                            "name": "isbn",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                            "example": "9780451524935"
                        },
                        format_param
                    ],
                    "responses": {
                        "200": {
                            "description": "Detalle del libro",
                            "content": {
                                "application/json": {"schema": book_schema},
                                "application/xml": {"schema": {"type": "string"}}
                            }
                        },
                        "404": {
                            "description": "El ISBN no existe en el catálogo",
                            "content": {
                                "application/json": {"schema": error_schema},
                                "application/xml": {"schema": {"type": "string"}}
                            }
                        }
                    }
                }
            },
            "/books/covers": {
                "get": {
                    "summary": "Datos mínimos de los libros junto con su imagen de portada",
                    "parameters": [format_param],
                    "responses": {
                        "200": {
                            "description": "Lista de libros con ISBN, título e imagen",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "total": {"type": "integer"},
                                            "libros": {"type": "array", "items": book_cover_schema}
                                        }
                                    }
                                },
                                "application/xml": {"schema": {"type": "string"}}
                            }
                        }
                    }
                }
            },
            "/concepts": {
                "get": {
                    "summary": "Conceptos de Cloud Computing (IaaS, PaaS, SaaS, FaaS) con los libros asociados",
                    "parameters": [format_param],
                    "responses": {
                        "200": {
                            "description": "Catálogo de conceptos y sus libros relacionados",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "total": {"type": "integer"},
                                            "conceptos": {"type": "array", "items": concept_schema}
                                        }
                                    }
                                },
                                "application/xml": {"schema": {"type": "string"}}
                            }
                        }
                    }
                }
            }
        }
    }
