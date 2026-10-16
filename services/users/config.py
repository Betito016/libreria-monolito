"""Configuracion del microservicio users (la comun se lee en libreria_common)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / '.env')

HOST = os.getenv('USERS_HOST', '0.0.0.0')
PORT = int(os.getenv('USERS_PORT', '5004'))
DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '5432'))
DB_NAME = os.getenv('DB_NAME', 'library_db')
DB_USER = os.getenv('DB_USER', 'users_app_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

PASSWORD_MIN = 8
PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX = 20, 100
