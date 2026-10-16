# Microservicio pagos (:5002)

Registra pagos y actualiza el estado de los pedidos, sobre `libreria_db` (tabla `payments`). **Todo requiere JWT.**

| Método | Endpoint | Acceso |
|---|---|---|
| GET | `/payments?order_id=&estado=&user_id=` | cliente: solo los suyos · administrador: todos |
| GET | `/payments/{id}` | dueño o administrador |
| POST | `/payments` `{order_id, metodo, monto?}` | dueño del pedido o administrador |
| PATCH | `/payments/{id}` `{"estado": "reembolsado"}` | administrador |
| DELETE | `/payments/{id}` (rechazado o reembolsado) | administrador |
| GET | `/health`, `/metrics` | público |

- **Una sola transacción:** el `INSERT` del pago y el cambio del pedido a `pagado` se confirman juntos. Un índice único parcial impide dos pagos aprobados del mismo pedido.
- **Reembolso:** el pago pasa a `reembolsado`, el pedido a `cancelado` y el stock regresa; se invalida `books:*`.
- **Métodos:** `tarjeta`, `transferencia`, `efectivo` (pago simulado; no se guardan datos de tarjeta).

**Redis:**
- `lock:order:<order_id>` (`SET NX EX 30`): dos pagos simultáneos del mismo pedido no se procesan a la vez; el segundo recibe 409.
- `payment:idem:<user_id>:<clave>` (24 h): reintentar con la misma `Idempotency-Key` devuelve el mismo pago (`repetido: true`) y no cobra dos veces.

## Instalación

```bash
CREATE ROLE payments_app_user WITH LOGIN PASSWORD '<password-generada>';
psql -d libreria_db -f sql/01_pagos.sql
cp .env.example .env
python -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/python app.py
venv/bin/python -m pytest -q        # 12 pruebas
```

El puerto 5002 era del servicio SOAP, que pasa al **5006**.

Ver [docs/REDIS_MICROSERVICIOS.md](../../docs/REDIS_MICROSERVICIOS.md).
