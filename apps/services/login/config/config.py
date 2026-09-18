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

    # Clave de firma de la sesion de Flask.
    # Debe ser fija y persistente: si cambia entre reinicios, todas las
    # sesiones activas quedan invalidadas.
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-only-change-me')

    # Duracion de la sesion autenticada
    SESSION_LIFETIME_MINUTES = int(os.getenv('SESSION_LIFETIME_MINUTES', '60'))

    # PostgreSQL (misma base que el monolito: library_db)
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', '5432'))
    DB_NAME = os.getenv('DB_NAME', 'library_db')
    DB_USER = os.getenv('DB_USER', 'login_app_user')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')

    # Origenes permitidos para CORS con credenciales.
    # Con cookies de sesion NO puede usarse '*': el navegador exige un
    # origen explicito cuando la peticion viaja con credenciales.
    CORS_ORIGINS = [
        o.strip() for o in os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',') if o.strip()
    ]

    # Validacion de correo: verificar que el dominio tenga registros MX
    VERIFY_EMAIL_MX = os.getenv('VERIFY_EMAIL_MX', 'True').lower() in ('true', '1', 't')

    @classmethod
    def dsn(cls) -> str:
        return (
            f"host={cls.DB_HOST} port={cls.DB_PORT} dbname={cls.DB_NAME} "
            f"user={cls.DB_USER} password={cls.DB_PASSWORD}"
        )
