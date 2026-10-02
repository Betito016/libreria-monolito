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
    HOST = os.getenv('BOOKS_HOST', '0.0.0.0')
    PORT = int(os.getenv('BOOKS_PORT', '5001'))
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')

    # PostgreSQL: catalogo de library.xml
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', '5432'))
    DB_NAME = os.getenv('DB_NAME', 'libreria_db')
    DB_USER = os.getenv('DB_USER', 'books_app_user')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')

    # JWT emitido por el microservicio de login. Este servicio solo lo VALIDA:
    # clave, algoritmo y emisor deben ser los mismos que en services/login.
    # Sin valor por defecto para la clave: sin ella el servicio no arranca.
    JWT_SECRET = os.getenv('JWT_SECRET', '')
    JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
    JWT_ISSUER = os.getenv('JWT_ISSUER', 'libreria-login')

    # Microservicio de login: solo para /health (si cae, no se pueden emitir
    # tokens nuevos). Las escrituras validan el JWT sin consultarlo.
    LOGIN_SERVICE_URL = os.getenv('LOGIN_SERVICE_URL', 'http://localhost:5000').rstrip('/')
    LOGIN_TIMEOUT_SECONDS = float(os.getenv('LOGIN_TIMEOUT_SECONDS', '5'))

    # Rol requerido para crear, modificar o eliminar libros
    ROL_ADMINISTRADOR = 'administrador'

    # Paginacion
    PAGE_SIZE_DEFAULT = 12
    PAGE_SIZE_MAX = 100

    @classmethod
    def dsn(cls) -> str:
        return (
            f"host={cls.DB_HOST} port={cls.DB_PORT} dbname={cls.DB_NAME} "
            f"user={cls.DB_USER} password={cls.DB_PASSWORD}"
        )
