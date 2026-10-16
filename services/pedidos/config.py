"""Configuracion del microservicio pedidos (la comun se lee en libreria_common)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / '.env')

HOST = os.getenv('PEDIDOS_HOST', '0.0.0.0')
PORT = int(os.getenv('PEDIDOS_PORT', '5003'))
DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '5432'))
DB_NAME = os.getenv('DB_NAME', 'libreria_db')
DB_USER = os.getenv('DB_USER', 'orders_app_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

# Un pedido pendiente que no se paga en este tiempo se cancela solo y su
# stock regresa al catalogo (tarea periodica coordinada con Redis).
ORDER_PENDING_MINUTES = int(os.getenv('ORDER_PENDING_MINUTES', '30'))
BARRIDO_SEGUNDOS = int(os.getenv('ORDER_SWEEP_SECONDS', '60'))
# Una peticion POST /orders repetida con el mismo Idempotency-Key devuelve el
# mismo pedido en lugar de crear otro (reintentos del cliente).
IDEMPOTENCIA_HORAS = 24
MAX_LINEAS, MAX_CANTIDAD = 50, 100
PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX = 20, 100
