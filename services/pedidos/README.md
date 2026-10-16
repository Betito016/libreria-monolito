# Microservicio pedidos (:5003)

Pedidos, líneas de pedido y stock, sobre `libreria_db` (tablas `orders`, `order_items` y la columna `books.stock`). **Todo requiere JWT**: un pedido es información privada.

| Método | Endpoint | Acceso |
|---|---|---|
| GET | `/orders?estado=&user_id=` | cliente: solo los suyos · administrador: todos |
| GET | `/orders/{id}` | dueño o administrador |
| POST | `/orders` `{items: [{isbn, cantidad}], direccion_envio}` | cliente o administrador |
| PATCH | `/orders/{id}` `{estado}` / `{direccion_envio}` | dueño (solo cancelar) o administrador |
| DELETE | `/orders/{id}` (pendiente o cancelado) | administrador |
| GET | `/health`, `/metrics` | público |

**Estados:** `pendiente → pagado → enviado → entregado`, y `pendiente → cancelado`. `pagado` solo lo pone el microservicio pagos.

**Stock:** al crear, las filas de `books` se bloquean con `SELECT … FOR UPDATE` en orden de ISBN (sin interbloqueos) y se descuenta en la misma transacción; cancelar lo devuelve. Después se invalida `books:*`.

**Redis:**
- `order:idem:<user_id>:<clave>` (24 h): un `POST` repetido con la misma cabecera `Idempotency-Key` devuelve el mismo pedido (`repetido: true`) sin descontar stock otra vez.
- `lock:pedidos:barrido`: un hilo cancela cada minuto los pedidos pendientes de más de 30 minutos (`ORDER_PENDING_MINUTES`) y devuelve su stock; con varias instancias, solo la que tiene el candado lo hace.

## Instalación

```bash
CREATE ROLE orders_app_user WITH LOGIN PASSWORD '<password-generada>';
psql -d libreria_db -f sql/01_pedidos.sql
cp .env.example .env
python -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/python app.py
venv/bin/python -m pytest -q        # 13 pruebas
```

Ver [docs/REDIS_MICROSERVICIOS.md](../../docs/REDIS_MICROSERVICIOS.md).
