# libreria_common — código compartido por los 6 microservicios

Todo lo que debe comportarse **igual** en login, books, users, authors, pedidos y pagos: validación del JWT, revocación, conexión a Redis, caché, CORS, métricas y formato de respuestas. Se instala en el venv de cada servicio (no se copia):

```bash
pip install -e ../common          # ya incluido en cada requirements.txt
```

| Módulo | Contenido |
|---|---|
| `config.py` | `ConfigComun.desde_entorno()`: `JWT_SECRET_KEY`, `REDIS_URL`, `ACCESS_TOKEN_MINUTES`, `CACHE_TTL_SECONDS`, `CORS_ORIGINS`… Sin secretos, el servicio no arranca |
| `redis_capa.py` | `CapaRedis.ejecutar(op, critico=)`: timeouts, corte rápido tras una falla, operación **crítica** (503 si Redis cae) u **opcional** (devuelve `None`). Nunca escribe la URL con la contraseña |
| `seguridad.py` | `ValidadorJWT.requiere_jwt(roles=[...])`: firma, algoritmo, emisor, claims, `jwt:revoked:<jti>` y `jwt:revoked_before:<user_id>`. `revocar_jti`, `revocar_usuario` |
| `cache.py` | `CacheJSON` cache-aside con `SCAN` + `UNLINK` para invalidar por patrón |
| `candado.py` | `Candado`: `SET NX EX` para tomarlo; se libera solo si sigue siendo propio (`WATCH`/`MULTI`) |
| `flask_base.py` | `ServicioBase.crear(...)`: CORS por lista, logs sin secretos, manejadores 401/403/404/409/503 y `GET /metrics` |
| `metricas.py` | Contadores por servicio (peticiones, códigos, caché HIT/MISS, JWT rechazados, fallas de Redis) |
| `bd.py` | Pool de Psycopg 3; transacción por bloque; `BaseDatosNoDisponible` → 503 |
| `respuestas.py`, `validacion.py` | XML por defecto / JSON con `?format=json`; validación de campos con errores 400 uniformes |

Arquitectura completa, claves de Redis y tabla de endpoints: [docs/REDIS_MICROSERVICIOS.md](../../docs/REDIS_MICROSERVICIOS.md).

## Pruebas

```powershell
python -m venv venv; venv\Scripts\pip install -e .[pruebas]
venv\Scripts\python -m pytest -q        # 26 pruebas con fakeredis
```
