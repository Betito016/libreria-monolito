"""
Codigo compartido por los microservicios de la Libreria (login, books, users,
authors, pedidos y pagos).

Un solo lugar para lo que debe ser IDENTICO en todos los servicios:

    config        Variables de entorno comunes (JWT_SECRET_KEY, REDIS_URL, CORS...)
    redis_capa    Conexion a Redis con timeouts, autenticacion y corte rapido
    seguridad     Validacion de JWT, lista de revocacion y control de roles
    cache         Cache JSON opcional (si Redis falla, se lee de PostgreSQL)
    metricas      Contadores por servicio para GET /metrics
    flask_base    CORS, logs, manejo de 401/403/503 y GET /metrics
    respuestas    Respuestas XML (por defecto) y JSON (?format=json)

Cada servicio lo instala en su venv:  pip install -e ../common
"""
__version__ = '1.0.0'
