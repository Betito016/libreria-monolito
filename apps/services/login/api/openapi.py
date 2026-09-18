"""
Especificacion OpenAPI 3.0 del microservicio de login.

Cada endpoint declara los dos content types (application/xml y
application/json) para reflejar que el mismo recurso se representa en ambos
formatos, y el parametro `format` que elige cual.
"""

FORMAT_PARAM = {
    "name": "format",
    "in": "query",
    "required": False,
    "description": "Formato de la respuesta. Si se omite, el microservicio responde en XML.",
    "schema": {"type": "string", "enum": ["xml", "json"], "default": "xml"},
}

USUARIO_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "format": "uuid"},
        "nombre": {"type": "string", "example": "Ana"},
        "apellido_paterno": {"type": "string", "example": "Torres"},
        "apellido_materno": {"type": "string", "example": "Ruiz", "nullable": True},
        "email": {"type": "string", "format": "email", "example": "ana.torres@gmail.com"},
        "rol": {"type": "string", "example": "cliente"},
        "email_verificado": {"type": "boolean", "example": True},
    },
}

ERROR_SCHEMA = {
    "type": "object",
    "properties": {
        "estado": {"type": "string", "example": "error"},
        "codigo_error": {"type": "string", "example": "ERR_CREDENCIALES_INVALIDAS"},
        "mensaje": {"type": "string"},
    },
}

REGISTER_BODY_SCHEMA = {
    "type": "object",
    "required": ["nombre", "apellido_paterno", "email", "password"],
    "properties": {
        "nombre": {"type": "string", "example": "Ana"},
        "apellido_paterno": {"type": "string", "example": "Torres"},
        "apellido_materno": {"type": "string", "example": "Ruiz"},
        "email": {"type": "string", "format": "email", "example": "ana.torres@gmail.com"},
        "password": {"type": "string", "format": "password", "minLength": 8,
                     "example": "Password123"},
    },
}

LOGIN_BODY_SCHEMA = {
    "type": "object",
    "required": ["email", "password"],
    "properties": {
        "email": {"type": "string", "format": "email", "example": "ana.torres@correo.test"},
        "password": {"type": "string", "format": "password", "example": "Password123"},
    },
}


def _dual_content(schema: dict) -> dict:
    """Un mismo recurso, dos representaciones."""
    return {
        "application/xml": {"schema": schema},
        "application/json": {"schema": schema},
    }


def build_openapi_spec(server_url: str) -> dict:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Microservicio de Autenticacion - Libreria en Linea",
            "description": (
                "Microservicio independiente de autenticacion y gestion basica de "
                "usuarios (Flask + Psycopg 3 + PostgreSQL).\n\n"
                "**Formato de respuesta:** XML por defecto. Para recibir JSON hay que "
                "pedirlo explicitamente con `?format=json`.\n\n"
                "**Cuerpo de las peticiones:** se acepta JSON, formulario "
                "(`application/x-www-form-urlencoded`) o XML.\n\n"
                "**Sesiones:** `/login` crea una sesion del lado de Flask mediante una "
                "cookie firmada; `/session` y `/logout` requieren que el cliente envie "
                "esa cookie."
            ),
            "version": "1.0.0",
        },
        "servers": [{"url": server_url}],
        "paths": {
            "/register": {
                "post": {
                    "summary": "Registrar un nuevo usuario",
                    "description": (
                        "Valida el correo (sintaxis + registro MX del dominio), verifica "
                        "que sea unico y almacena unicamente el hash bcrypt de la "
                        "contrasena. La contrasena nunca se guarda en texto plano."
                    ),
                    "parameters": [FORMAT_PARAM],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {"schema": REGISTER_BODY_SCHEMA},
                            "application/x-www-form-urlencoded": {"schema": REGISTER_BODY_SCHEMA},
                            "application/xml": {"schema": REGISTER_BODY_SCHEMA},
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Usuario registrado",
                            "content": _dual_content({
                                "type": "object",
                                "properties": {
                                    "estado": {"type": "string", "example": "exito"},
                                    "mensaje": {"type": "string"},
                                    "validacion_email": {"type": "string"},
                                    "usuario": USUARIO_SCHEMA,
                                },
                            }),
                        },
                        "400": {"description": "Datos invalidos", "content": _dual_content(ERROR_SCHEMA)},
                        "409": {"description": "El correo ya esta registrado", "content": _dual_content(ERROR_SCHEMA)},
                    },
                }
            },
            "/login": {
                "post": {
                    "summary": "Autenticar al usuario e iniciar sesion",
                    "description": (
                        "Verifica las credenciales contra PostgreSQL y, si son correctas, "
                        "crea una sesion del lado de Flask."
                    ),
                    "parameters": [FORMAT_PARAM],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {"schema": LOGIN_BODY_SCHEMA},
                            "application/x-www-form-urlencoded": {"schema": LOGIN_BODY_SCHEMA},
                            "application/xml": {"schema": LOGIN_BODY_SCHEMA},
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Autenticacion exitosa; se establece la cookie de sesion",
                            "content": _dual_content({
                                "type": "object",
                                "properties": {
                                    "estado": {"type": "string", "example": "exito"},
                                    "mensaje": {"type": "string"},
                                    "usuario": USUARIO_SCHEMA,
                                },
                            }),
                        },
                        "401": {"description": "Credenciales invalidas", "content": _dual_content(ERROR_SCHEMA)},
                        "403": {"description": "Cuenta desactivada", "content": _dual_content(ERROR_SCHEMA)},
                    },
                }
            },
            "/logout": {
                "post": {
                    "summary": "Cerrar la sesion",
                    "parameters": [FORMAT_PARAM],
                    "responses": {
                        "200": {
                            "description": "Sesion cerrada",
                            "content": _dual_content({
                                "type": "object",
                                "properties": {
                                    "estado": {"type": "string", "example": "exito"},
                                    "mensaje": {"type": "string"},
                                    "sesion_previa": {"type": "boolean"},
                                },
                            }),
                        }
                    },
                }
            },
            "/session": {
                "get": {
                    "summary": "Consultar si existe una sesion autenticada",
                    "description": "Requiere que el cliente envie la cookie de sesion emitida por /login.",
                    "parameters": [FORMAT_PARAM],
                    "responses": {
                        "200": {
                            "description": "Estado de la sesion",
                            "content": _dual_content({
                                "type": "object",
                                "properties": {
                                    "autenticado": {"type": "boolean"},
                                    "usuario": USUARIO_SCHEMA,
                                },
                            }),
                        }
                    },
                }
            },
            "/verify": {
                "get": {
                    "summary": "Verificar el correo canjeando el token enviado por email",
                    "description": (
                        "Unico camino por el que `email_verificado` pasa a `true`. "
                        "El token viaja por correo (Postfix) y nunca se almacena en "
                        "claro: la base guarda solo su SHA-256. Acepta GET para que "
                        "el enlace del correo funcione desde el navegador, y POST "
                        "para clientes programaticos."
                    ),
                    "parameters": [
                        {
                            "name": "token",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "Token recibido por correo.",
                        },
                        FORMAT_PARAM,
                    ],
                    "responses": {
                        "200": {
                            "description": "Correo verificado; email_verificado pasa a true",
                            "content": _dual_content({
                                "type": "object",
                                "properties": {
                                    "estado": {"type": "string", "example": "exito"},
                                    "mensaje": {"type": "string"},
                                    "usuario": USUARIO_SCHEMA,
                                },
                            }),
                        },
                        "400": {"description": "Token invalido o faltante", "content": _dual_content(ERROR_SCHEMA)},
                        "409": {"description": "El token ya fue utilizado", "content": _dual_content(ERROR_SCHEMA)},
                        "410": {"description": "El token expiro", "content": _dual_content(ERROR_SCHEMA)},
                    },
                }
            },
            "/health": {
                "get": {
                    "summary": "Verificar el estado del microservicio y de PostgreSQL",
                    "parameters": [FORMAT_PARAM],
                    "responses": {
                        "200": {
                            "description": "Microservicio y base de datos operativos",
                            "content": _dual_content({
                                "type": "object",
                                "properties": {
                                    "estado": {"type": "string", "example": "ok"},
                                    "microservicio": {"type": "string", "example": "login"},
                                    "postgresql": {
                                        "type": "object",
                                        "properties": {
                                            "conectado": {"type": "boolean"},
                                            "base_datos": {"type": "string", "example": "library_db"},
                                            "version": {"type": "string"},
                                        },
                                    },
                                },
                            }),
                        },
                        "503": {"description": "PostgreSQL no disponible", "content": _dual_content(ERROR_SCHEMA)},
                    },
                }
            },
        },
    }


SWAGGER_UI_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8" />
    <title>API Docs - Microservicio de Autenticacion</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" />
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        window.onload = function () {
            SwaggerUIBundle({
                url: "/openapi.json",
                dom_id: "#swagger-ui",
                // Envia la cookie de sesion en las pruebas de "Try it out",
                // necesario para que /session y /logout reconozcan el login.
                // Se usa withCredentials (no un requestInterceptor) porque
                // el interceptor tambien afectaria la carga del propio spec.
                withCredentials: true
            });
        };
    </script>
</body>
</html>
"""
