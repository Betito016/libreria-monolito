import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
BASE_DIR = Path(__file__).resolve().parent.parent
env_file = BASE_DIR / '.env'
if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv()

class Config:
    # Servidor
    SOAP_HOST = os.getenv('SOAP_HOST', '0.0.0.0')
    SOAP_PORT = int(os.getenv('SOAP_PORT', '5000'))
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')

    # Base de Datos PostgreSQL
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', '5432'))
    DB_NAME = os.getenv('DB_NAME', 'libreria_db')
    DB_USER = os.getenv('DB_USER', 'soap_app_user')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')   # solo desde .env: sin contrasena en el codigo

    # Base de Datos de Respaldo Local (SQLite para testing sin servidor PG activo)
    SQLITE_DB_PATH = BASE_DIR / 'db' / 'local_library.db'

    # WS-Security
    WS_SECURITY_USER = os.getenv('WS_SECURITY_USER', 'admin_clasificador')
    WS_SECURITY_PASS = os.getenv('WS_SECURITY_PASS', 'CloudSecure2026!')

    # Rutas
    WSDL_PATH = BASE_DIR / 'wsdl' / 'library-classifier.wsdl'
    SQL_INIT_PATH = BASE_DIR / 'sql' / 'seed_monolith.sql'
    SQL_MODULE_PATH = BASE_DIR / 'sql' / 'soap_module.sql'
    XML_CATALOG_PATH = BASE_DIR.parent / 'library.xml'
