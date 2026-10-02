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

    # Duracion de la sesion autenticada. Es un vencimiento ABSOLUTO: solo se
    # prorroga explicitamente con POST /session/extend, no con cada peticion.
    SESSION_LIFETIME_MINUTES = int(os.getenv('SESSION_LIFETIME_MINUTES', '30'))

    # Nombre propio para la cookie de sesion. Las cookies no distinguen
    # puerto: si otro servicio Flask en el mismo host usara el nombre por
    # defecto ('session'), ambas cookies se sobrescribirian entre si.
    SESSION_COOKIE_NAME = os.getenv('SESSION_COOKIE_NAME', 'libreria_login_session')

    # JWT de acceso. Login lo FIRMA; el servicio de libros lo VALIDA con la
    # misma clave y el mismo algoritmo (JWT_SECRET y JWT_ALGORITHM deben ser
    # identicos en ambos .env). Sin valor por defecto: sin clave el servicio
    # no arranca, para no firmar nunca con una clave conocida.
    JWT_SECRET = os.getenv('JWT_SECRET', '')
    JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
    JWT_ISSUER = os.getenv('JWT_ISSUER', 'libreria-login')

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
