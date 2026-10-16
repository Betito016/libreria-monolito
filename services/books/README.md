# Microservicio de Libros

Catálogo de libros de la librería en línea: consulta pública y administración (CRUD) restringida a administradores.

**Stack:** Python · Flask · Psycopg 3 · PostgreSQL (`libreria_db`, el catálogo de `library.xml`)
**Puerto:** 5001 · **Formato:** XML por defecto, JSON con `?format=json`

## Endpoints

| Método | Endpoint | Acceso | Función |
|---|---|---|---|
| GET | `/health` | público | Estado del servicio, de PostgreSQL y del login |
| GET | `/categories` | público | Categorías válidas |
| GET | `/api/books` | público | Catálogo paginado; filtros `isbn`, `titulo`, `anio`, `precio_min`, `precio_max` |
| GET | `/api/books/{isbn}` | público | Detalle con autores, géneros, imágenes y conceptos |
| POST | `/api/books` | **JWT** de administrador | Crear |
| PUT | `/api/books/{isbn}` | **JWT** de administrador | Reemplazo completo (exige todos los campos) |
| PATCH | `/api/books/{isbn}` | **JWT** de administrador | Modificación parcial (solo los campos enviados) |
| DELETE | `/api/books/{isbn}` | **JWT** de administrador | Eliminar |

Las mismas rutas responden sin el prefijo (`/books`, `/books/{isbn}`), con la misma protección, para no romper a los clientes anteriores.

Documentación interactiva: `GET /docs` (Swagger UI, con el botón **Authorize** para pegar el token).

## Autenticación con JWT

Las escrituras exigen el header:

```
Authorization: Bearer <access_token>
```

El token lo emite el microservicio de **login** (`POST /login` → `token.access_token`). Este servicio lo valida **localmente** con la misma clave y el mismo algoritmo (`JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ISSUER` idénticos en los 6 `.env`) y después consulta en Redis si fue revocado (`jwt:revoked:<jti>`, `jwt:revoked_before:<user_id>`).

La protección es **selectiva**: solo las cuatro rutas de escritura llevan `servicio.auth.requiere_jwt(roles=[ROL_ADMINISTRADOR])` (validador compartido de [`libreria_common`](../common/README.md)). Los GET, `/categories` y `/health` siguen públicos.

| Situación | Respuesta |
|---|---|
| Falta el header `Authorization`, o `Bearer` sin token | 401 `ERR_TOKEN_AUSENTE` |
| Esquema distinto de `Bearer` (p. ej. `Basic`) | 401 `ERR_TOKEN_INVALIDO` |
| Firma inválida, token alterado o malformado | 401 `ERR_TOKEN_INVALIDO` |
| Algoritmo distinto de `JWT_ALGORITHM` (incluido `none`) | 401 `ERR_TOKEN_INVALIDO` |
| Emisor distinto o faltan claims (`exp`, `iat`, `sub`, `iss`) | 401 `ERR_TOKEN_INVALIDO` |
| Token expirado | 401 `ERR_TOKEN_EXPIRADO` |
| Token revocado (logout, renovación, cambio de contraseña o rol) | 401 `ERR_TOKEN_REVOCADO` |
| Token válido, pero rol `cliente` | 403 `ERR_SIN_PERMISOS` |
| Redis no responde: no se puede comprobar la revocación | 503 |

Las respuestas 401 incluyen `WWW-Authenticate: Bearer …` (RFC 6750).

**Si el login cae:** las lecturas y las escrituras con tokens ya emitidos siguen funcionando, pero nadie puede iniciar sesión para obtener uno nuevo. `/health` responde `degradado` con `autenticacion.emision_de_tokens = false`.

## Caché en Redis

| Clave | Endpoint |
|---|---|
| `books:list:<filtros>` | `GET /api/books` (una entrada por combinación de filtros y página) |
| `books:<isbn>` | `GET /api/books/{isbn}` |
| `books:categories` | `GET /categories` |

- TTL corto: `CACHE_TTL_SECONDS` (60 s). Las respuestas llevan `X-Cache: HIT | MISS`.
- **Invalidación:** cada `POST`, `PUT`, `PATCH` o `DELETE`, después del `COMMIT`, borra `books:list:*`, `books:<isbn>` y `authors:*` (con `SCAN` + `UNLINK`). authors, pedidos y pagos también borran `books:*` cuando cambian autores o stock.
- **Opcional:** si Redis no responde, la lectura va a PostgreSQL y responde igual. La autorización, en cambio, sí falla segura (503).

### Logs

Cada petición deja en la consola del servicio si la ruta es pública o protegida y si trae token, **sin mostrarlo completo**:

```
--> PATCH /api/books/978... | PROTEGIDO (requiere JWT) | Authorization: Bearer [JWT PRESENTE eyJhbGciOi…vMa4 (288 caracteres)]
    campos recibidos: precio
    JWT valido: firma OK, alg HS256, sub=... email=admin@libreria.test rol=administrador
    Operacion realizada: PATCH 978... (precio) por admin@libreria.test
<-- 200 PATCH /api/books/978...
```

### Pruebas

```bash
venv\Scripts\python -m pytest -q
```

`tests/test_jwt_auth.py` (30 pruebas, con `fakeredis`) cubre GET públicos, escrituras sin token, con token válido, token malformado, firma alterada, otro algoritmo, `alg=none`, otro emisor, token expirado, token revocado, rol cliente (403), caché HIT/MISS e invalidación, Redis caído y que los logs no revelan el token. No necesita PostgreSQL, Redis ni el login.

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
| 401 / 403 | Sin JWT válido / JWT válido sin rol administrador |
| 404 | Libro inexistente |
| 409 | ISBN duplicado, o libro con conceptos/clasificaciones que impiden borrarlo |
| 503 | PostgreSQL no disponible |

## Instalación

```bash
# 1. Rol de base de datos (la contraseña no se versiona)
CREATE ROLE books_app_user WITH LOGIN PASSWORD '<password-generada>';

# 2. Migración del catálogo (generada desde library.xml)
psql -d libreria_db -f sql/01_catalogo_libros.sql

# 3. Entorno y ejecución
cp .env.example .env         # completar DB_PASSWORD, JWT_SECRET_KEY (la misma de login), REDIS_URL y LOGIN_SERVICE_URL
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python app.py
```

La migración se regenera desde `library.xml` con `python sql/generar_01_catalogo.py <ruta/a/library.xml>`; es idempotente.

En la instancia GCP corre como `library-books.service` bajo el usuario de sistema `booksapp`.
