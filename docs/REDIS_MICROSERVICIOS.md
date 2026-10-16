# Redis + microservicios de la Librería

Seis microservicios Flask comparten una capa Redis para **sesiones, revocación de JWT, caché, candados e idempotencia**. Todos validan el mismo JWT (HS256) y responden XML por defecto o JSON con `?format=json`.

```
                       ┌────────────── App de escritorio (Tkinter) ──────────────┐
                       │ semáforos de los 6 servicios · CRUD · JWT renovado solo  │
                       └────┬──────┬──────┬───────┬────────┬───────┬─────────────┘
                            │      │      │       │        │       │   HTTP (HTTPS vía nginx en la instancia)
                         login  books   users  authors  pedidos  pagos
                         :5000  :5001   :5004   :5005    :5003   :5002
                            │      │      │       │        │       │
                            └──────┴──────┴───┬───┴────────┴───────┘
                                              │  REDIS_URL=redis://:password@host:6379/0
                                     ┌────────┴────────┐
                                     │  Redis 8 (GCP)  │  requirepass · timeouts
                                     └─────────────────┘
                     PostgreSQL: library_db (usuarios, roles) · libreria_db (catálogo, pedidos, pagos)
```

El código común vive en un solo paquete, [`services/common`](../services/common/README.md) (`libreria_common`), instalado en cada venv con `pip install -e ../common`.

## 1. Por qué Redis

| Necesidad | Por qué no basta con PostgreSQL o con el JWT solo | Qué hace Redis |
|---|---|---|
| **Cerrar sesión de verdad** | Un JWT firmado es válido hasta su `exp`; borrarlo en el cliente no invalida copias | `jwt:revoked:<jti>` con TTL = vida restante del token. Los 6 servicios lo consultan en cada petición protegida |
| **Sesión y refresh token** | Guardarlos en PostgreSQL agrega escrituras a cada renovación y requiere limpieza de vencidos | `session:<sid>` y `refresh:<sha256>` con TTL: caducan solos |
| **Revocar a un usuario completo** (cambio de contraseña, rol, desactivación) | Habría que rastrear todos sus `jti` | `jwt:revoked_before:<user_id>` = instante; todo token emitido antes se rechaza |
| **Lecturas públicas frecuentes** (catálogo, autores) | Cada GET arma varios JOIN | Caché `books:*` y `authors:*` con TTL de 60 s, invalidada en cada escritura |
| **Dos pagos simultáneos del mismo pedido** | Con varios procesos, un candado en memoria no sirve | `lock:order:<id>` con `SET NX EX` |
| **Reintentos de red** (doble clic, timeout del cliente) | Crearían pedidos o cobros duplicados | `order:idem:*` y `payment:idem:*` (Idempotency-Key, 24 h) |
| **Tareas programadas con varias réplicas** | Cada réplica cancelaría los mismos pedidos | `lock:pedidos:barrido` |

Redis es memoria compartida entre servicios, con expiración automática y operaciones atómicas (`SET NX`, `GETDEL`, `MULTI`). Esas tres propiedades son justo las que necesitan la revocación, los refresh tokens de un solo uso y los candados.

## 2. Claves en Redis

| Clave | Quién escribe | Quién lee | TTL | Si Redis no responde |
|---|---|---|---|---|
| `session:<sid>` | login | login | 60 min, deslizante | 503 (falla segura) |
| `refresh:<sha256(refresh)>` | login | login (`GETDEL`: un solo uso) | igual que la sesión | 503 |
| `user:sessions:<user_id>` | login | login, users | igual que la sesión | 503 |
| `jwt:revoked:<jti>` | login (logout, refresh) | **los 6** | vida restante del JWT | **401/503: nunca se acepta un token sin comprobarlo** |
| `jwt:revoked_before:<user_id>` | login (`/profile`), users | **los 6** | 21 min (vida máxima de un JWT + 1) | 503 |
| `books:list:<filtros>`, `books:<isbn>`, `books:categories` | books | books | 60 s | se lee de PostgreSQL (opcional) |
| `authors:list:<filtros>`, `authors:<id>` | authors | authors | 60 s | se lee de PostgreSQL (opcional) |
| `order:idem:<user_id>:<clave>` | pedidos | pedidos | 24 h | 503 |
| `payment:idem:<user_id>:<clave>` | pagos | pagos | 24 h | 503 |
| `lock:order:<order_id>` | pagos | pagos | 30 s | 503 |
| `lock:pedidos:barrido` | pedidos | pedidos | 55 s | se omite ese barrido |

**Invalidación cruzada:** authors, pedidos y pagos borran `books:*` (el catálogo muestra autores y stock); books borra `authors:*`. Se invalida **después** del `COMMIT`, con `SCAN` + `UNLINK` (no `KEYS`, que bloquea Redis).

Las respuestas cacheables llevan la cabecera `X-Cache: HIT | MISS`.

## 3. JWT

- Lo emite **solo login**: HS256 con `JWT_SECRET_KEY` (≥ 32 bytes, la misma en los 6 `.env`), 20 minutos.
- Claims: `sub`, `user_id`, `email`, `role_id` (1 administrador, 2 cliente), `rol`, `sid`, `jti`, `typ=access`, `iss`, `iat`, `exp`.
- Cada servicio lo valida **localmente** (firma, algoritmo, emisor, claims obligatorios, vencimiento) y después consulta la revocación en Redis.
- **Renovación:** `POST /token/refresh` con el refresh token devuelve un JWT y un refresh nuevos; el refresh anterior se consume (`GETDEL`) y el `jti` anterior se revoca. La app de escritorio renueva sola cuando faltan 2 minutos.
- **Logout:** revoca el `jti`, borra `session:<sid>` y el refresh. El mismo JWT responde 401 `ERR_TOKEN_REVOCADO` en todos los servicios.

| Respuesta | Caso |
|---|---|
| 401 `ERR_TOKEN_AUSENTE` | Sin `Authorization: Bearer` |
| 401 `ERR_TOKEN_INVALIDO` | Firma, algoritmo, emisor o claims incorrectos |
| 401 `ERR_TOKEN_EXPIRADO` | Pasó `exp` |
| 401 `ERR_TOKEN_REVOCADO` | Logout, renovación o revocación del usuario |
| 403 `ERR_SIN_PERMISOS` | Token válido, rol insuficiente |
| 503 | Redis no disponible: no se puede comprobar la revocación |

Las 401 incluyen `WWW-Authenticate: Bearer error="invalid_token", error_description="<código>"` (RFC 6750).

## 4. Endpoints: quién usa JWT y quién usa Redis

| Servicio | Endpoint | JWT | Redis |
|---|---|---|---|
| **login :5000** | `POST /login` | emite | crea sesión + refresh |
| | `POST /token/refresh` | emite (refresh token) | `GETDEL` refresh, revoca jti anterior |
| | `POST /session/extend` | emite (cookie) | renueva sesión |
| | `GET /session` | — (cookie) | lee sesión |
| | `POST /logout` | Bearer | revoca jti, borra sesión |
| | `PATCH /profile` | Bearer | correo/contraseña → `revoked_before` |
| | `POST /register`, `GET /verify` | público | — |
| **books :5001** | `GET /api/books`, `/api/books/{isbn}`, `/categories` | público | caché |
| | `POST`, `PUT`, `PATCH`, `DELETE /api/books…` | admin | revocación + invalida `books:*`, `authors:*` |
| **users :5004** | `GET /roles` | público | — |
| | `GET /users` | admin | revocación |
| | `GET /users/{id}` | admin o el propio usuario | revocación |
| | `POST`, `PATCH`, `DELETE /users…` | admin | revocación; cambios sensibles → `revoked_before` |
| **authors :5005** | `GET /authors`, `/authors/{id}` | público | caché |
| | `POST`, `PATCH`, `DELETE /authors…` | admin | revocación + invalida `authors:*`, `books:*` |
| **pedidos :5003** | `GET /orders`, `/orders/{id}` | cliente (los suyos) o admin | revocación |
| | `POST /orders` | cliente o admin | idempotencia + invalida `books:*` |
| | `PATCH /orders/{id}` | dueño (cancelar) o admin | revocación + invalida `books:*` |
| | `DELETE /orders/{id}` | admin | revocación |
| **pagos :5002** | `GET /payments`, `/payments/{id}` | cliente (los suyos) o admin | revocación |
| | `POST /payments` | dueño del pedido o admin | candado `lock:order` + idempotencia |
| | `PATCH /payments/{id}` (reembolso) | admin | revocación + invalida `books:*` |
| | `DELETE /payments/{id}` | admin | revocación |
| **todos** | `GET /health`, `GET /metrics` | público | `PING` con latencia / contadores |

## 5. Seguridad operativa

- **Redis con contraseña** (`requirepass`) y sin puerto abierto al exterior; desde la laptop se llega por túnel SSH (`gcloud compute ssh … -L 6379:127.0.0.1:6379`). La URL nunca se escribe en logs (solo `host:puerto/db`).
- **Timeouts** de conexión y de comando (`REDIS_TIMEOUT_SECONDS`), y un corte rápido de 5 s tras una falla para no esperar el timeout en cada petición.
- **Sin reintento por timeout:** un `GETDEL`, `SET NX` o `MULTI` que tardó pudo ejecutarse; repetirlo daría un resultado falso (por ejemplo, "refresh ya usado"). Solo se reintenta si la conexión se cayó.
- **Falla segura:** sin Redis, sesión, revocación, autorización, candados e idempotencia responden **503**; solo la caché es opcional (se lee de PostgreSQL).
- **CORS** solo para `CORS_ORIGINS`; un origen ajeno no recibe `Access-Control-Allow-Origin`.
- **Logs** sin tokens ni contraseñas: `[JWT PRESENTE eyJhbGciOi…abcd (513 caracteres)]`, contraseñas como `••••••`.
- **Mínimo privilegio en PostgreSQL:** cada servicio tiene su propio rol (`login_app_user`, `books_app_user`, `users_app_user`, `authors_app_user`, `orders_app_user`, `payments_app_user`) con permisos solo sobre sus tablas.
- **HTTPS** en la instancia: nginx con certificado autofirmado delante de los 6 servicios. La app ya lo soporta (*Configuración → Certificado HTTPS (CA)*; un certificado que no coincide se reporta como `TLS_INVALIDO`). El despliegue en la instancia está pendiente; las evidencias de esta entrega se tomaron en local.

## 6. Variables de entorno comunes

Mismos valores en los 6 `.env` (ver cada `.env.example`):

| Variable | Valor |
|---|---|
| `JWT_SECRET_KEY` | clave aleatoria ≥ 32 bytes (no versionada) |
| `JWT_ALGORITHM` / `JWT_ISSUER` | `HS256` / `libreria-login` |
| `ACCESS_TOKEN_MINUTES` | `20` |
| `REDIS_URL` | `redis://:<password>@127.0.0.1:6379/0` |
| `REDIS_TIMEOUT_SECONDS` | `1.5` (en local, por el túnel, `3`) |
| `CACHE_TTL_SECONDS` | `60` |
| `CORS_ORIGINS` | lista separada por comas |

Sin `JWT_SECRET_KEY` o `REDIS_URL`, el servicio no arranca.

## 7. Pruebas

Cada servicio tiene pruebas con `fakeredis` (no necesitan Redis ni PostgreSQL reales):

```powershell
cd services\<servicio>
venv\Scripts\python -m pytest -q
```

| Paquete | Pruebas |
|---|---|
| common | 26 |
| login | 13 |
| books | 30 |
| users | 11 |
| authors | 6 |
| pedidos | 13 |
| pagos | 12 |
| app de escritorio | 27 |
