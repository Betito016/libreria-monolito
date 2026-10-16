# Microservicio authors (:5005)

Autores y su relación con los libros, sobre `libreria_db` (tablas `authors` y `book_authors`).

| Método | Endpoint | Acceso | Redis |
|---|---|---|---|
| GET | `/authors?nombre=&page=&page_size=` | público | caché `authors:list:<filtros>` |
| GET | `/authors/{id}` (con sus libros) | público | caché `authors:<id>` |
| POST | `/authors` (`libros: [isbn, ...]` opcional) | JWT administrador | invalida `authors:*` y `books:*` |
| PATCH | `/authors/{id}` (datos y/o relaciones) | JWT administrador | invalida `authors:*` y `books:*` |
| DELETE | `/authors/{id}` | JWT administrador | invalida; **409** si aún tiene libros |
| GET | `/health`, `/metrics` | público | — |

La caché tiene TTL de `CACHE_TTL_SECONDS` (60 s) y es **opcional**: si Redis no responde, se lee de PostgreSQL. Las respuestas llevan `X-Cache: HIT | MISS`. Como el catálogo de books muestra los autores, cada escritura invalida también `books:*`.

## Instalación

```bash
CREATE ROLE authors_app_user WITH LOGIN PASSWORD '<password-generada>';
psql -d libreria_db -f sql/01_autores.sql      # agrega nacionalidad, biografia, creado_en y permisos
cp .env.example .env
python -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/python app.py
venv/bin/python -m pytest -q                   # 6 pruebas
```

Ver [docs/REDIS_MICROSERVICIOS.md](../../docs/REDIS_MICROSERVICIOS.md).
