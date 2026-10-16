import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
env_file = BASE_DIR / '.env'
if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv()


class Config:
    # Servidor
    HOST = os.getenv('LOGIN_HOST', '0.0.0.0')
    PORT = int(os.getenv('LOGIN_PORT', '5000'))
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')

    # JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_MINUTES (20), REDIS_URL y
    # CORS_ORIGINS se leen en libreria_common.config.ConfigComun: son los
    # mismos para los seis microservicios.

    # Sesion en Redis (session:<sid>) y su refresh token. El TTL es
    # deslizante: cada renovacion lo reinicia. El JWT de acceso dura
    # ACCESS_TOKEN_MINUTES y se renueva con POST /token/refresh.
    SESSION_TTL_MINUTES = int(os.getenv('SESSION_TTL_MINUTES', '60'))

    # La cookie solo lleva el id de la sesion (aleatorio, 256 bits); los datos
    # viven en Redis. Nombre propio: las cookies no distinguen puerto.
    SESSION_COOKIE_NAME = os.getenv('SESSION_COOKIE_NAME', 'libreria_login_session')
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() in ('true', '1', 't')

    # PostgreSQL (misma base que el monolito: library_db)
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', '5432'))
    DB_NAME = os.getenv('DB_NAME', 'library_db')
    DB_USER = os.getenv('DB_USER', 'login_app_user')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')

    # Validacion de correo: verificar que el dominio tenga registros MX
    VERIFY_EMAIL_MX = os.getenv('VERIFY_EMAIL_MX', 'True').lower() in ('true', '1', 't')

    # --- Correo de verificacion (SMTP / Postfix) ---
    MAIL_ENABLED = os.getenv('MAIL_ENABLED', 'True').lower() in ('true', '1', 't')
    SMTP_HOST = os.getenv('SMTP_HOST', 'localhost')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '25'))
    SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'False').lower() in ('true', '1', 't')
    SMTP_USER = os.getenv('SMTP_USER', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    MAIL_FROM = os.getenv('MAIL_FROM', 'no-reply@libreria.local')

    # URL publica del microservicio, usada para armar el enlace de verificacion
    PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', 'http://localhost:5000')

    # Vigencia del token de verificacion
    TOKEN_TTL_HOURS = int(os.getenv('TOKEN_TTL_HOURS', '24'))

    # SOLO DESARROLLO LOCAL: escribe el token de verificacion en el log del
    # servidor. Windows no tiene Postfix, asi que en el escenario local el
    # correo no puede enviarse y sin esto no habria forma de verificar una
    # cuenta nueva. Nunca debe activarse en la instancia remota. El token
    # jamas viaja en la respuesta HTTP: solo lo ve quien opera el servidor.
    MAIL_DEV_LOG_TOKEN = os.getenv('MAIL_DEV_LOG_TOKEN', 'False').lower() in ('true', '1', 't')

    @classmethod
    def dsn(cls) -> str:
        return (
            f"host={cls.DB_HOST} port={cls.DB_PORT} dbname={cls.DB_NAME} "
            f"user={cls.DB_USER} password={cls.DB_PASSWORD}"
        )
