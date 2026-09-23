# Microservicio de Libros

Catálogo de libros de la librería en línea: consulta pública y administración (CRUD) restringida a administradores.

**Stack:** Python · Flask · Psycopg 3 · PostgreSQL (`libreria_db`, el catálogo de `library.xml`)
**Puerto:** 5001 · **Formato:** XML por defecto, JSON con `?format=json`

## Endpoints

| Método | Endpoint | Acceso | Función |
|---|---|---|---|
| GET | `/health` | público | Estado del servicio, de PostgreSQL y del login |
| GET | `/categories` | público | Categorías válidas |
| GET | `/books` | público | Catálogo paginado; filtros `isbn`, `titulo`, `anio`, `precio_min`, `precio_max` |
| GET | `/books/{isbn}` | público | Detalle con autores, géneros, imágenes y conceptos |
| POST | `/books` | administrador | Crear |
| PUT | `/books/{isbn}` | administrador | Reemplazo completo (exige todos los campos) |
| PATCH | `/books/{isbn}` | administrador | Modificación parcial (solo los campos enviados) |
| DELETE | `/books/{isbn}` | administrador | Eliminar |

Documentación interactiva: `GET /docs` (Swagger UI).

## Autorización delegada al login

Este servicio **no tiene sesiones propias** ni conoce la clave con la que el login firma sus cookies. En cada escritura toma la cookie `libreria_login_session` que envió el cliente y le pregunta al microservicio de login (`GET /session`) a quién pertenece:

| Situación | Respuesta |
|---|---|
| Sin cookie, o sesión inválida | 401 `ERR_SESION_INVALIDA` |
| Sesión expirada | 401 `ERR_SESION_EXPIRADA` |
| Sesión válida pero rol `cliente` | 403 `ERR_SIN_PERMISOS` |
| El login no responde | 503 `ERR_LOGIN_NO_DISPONIBLE` |

Si el login cae, **las lecturas siguen funcionando** (el catálogo es público) y `/health` reporta `degradado` con `capacidades.escritura = false`.

## Modelo de datos

Un libro se reparte en varias tablas de `libreria_db`:

| Tabla | Contenido | Relación |
|---|---|---|
| `books` | ISBN, título, año, precio, existencia, formato | — |
| `categories` | Categoría amplia (Educación, Negocios, Divulgación, Literatura) | una por libro |
| `authors` + `book_authors` | Autores, con orden | varios por libro |
| `genres` + `book_genres` | Géneros (Cloud, Fiction, Security…) | varios por libro |
| `book_images` | Imágenes; una marcada como principal | varias por libro |
| `concepts` + `book_concepts` | Conceptos de Cloud Computing | varios por libro (solo lectura) |

**Género ≠ categoría:** el género describe de qué trata el libro (puede tener varios); la categoría describe para qué sirve (una sola). La migración `sql/01_catalogo_libros.sql` separa ambos conceptos: la tabla `categories` original contenía en realidad el primer género de cada libro.

## Códigos de respuesta

| Código | Caso |
|---|---|
| 200 / 201 | Correcto (201 en POST, con cabecera `Location`) |
| 400 | Datos inválidos, campos faltantes en PUT, ISBN inmutable, filtro inválido |
| 401 / 403 | Sin sesión / sin permisos |
| 404 | Libro inexistente |
| 409 | ISBN duplicado, o libro con conceptos/clasificaciones que impiden borrarlo |
| 503 | PostgreSQL o login no disponibles |

## Instalación

```bash
# 1. Rol de base de datos (la contraseña no se versiona)
CREATE ROLE books_app_user WITH LOGIN PASSWORD '<password-generada>';

# 2. Migración del catálogo (generada desde library.xml)
psql -d libreria_db -f sql/01_catalogo_libros.sql

# 3. Entorno y ejecución
cp .env.example .env         # completar DB_PASSWORD y LOGIN_SERVICE_URL
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python app.py
```

La migración se regenera desde `library.xml` con `python sql/generar_01_catalogo.py <ruta/a/library.xml>`; es idempotente.

En la instancia GCP corre como `library-books.service` bajo el usuario de sistema `booksapp`.
