"""
Configuracion de la aplicacion: a que servidores conectarse y con que tiempos.

Se guarda en un archivo JSON en el perfil del usuario, FUERA del proyecto:

    Windows : %APPDATA%\\LibreriaPythonApp\\config.json
    Otros   : ~/.libreria_python_app/config.json

Asi se puede cambiar entre servicios locales y remotos sin tocar el codigo
fuente, y el cambio sobrevive a cerrar la aplicacion. La configuracion no
contiene credenciales: solo direcciones y tiempos.
"""
import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import List
from urllib.parse import urlparse


def directorio_datos() -> Path:
    """Carpeta de datos de la aplicacion en el perfil del usuario."""
    appdata = os.environ.get('APPDATA')
    if appdata:
        return Path(appdata) / 'LibreriaPythonApp'
    return Path.home() / '.libreria_python_app'


RUTA_CONFIG = directorio_datos() / 'config.json'


def normalizar_url(url: str) -> str:
    """Construye una URL base utilizable a partir de lo que escriba el usuario.

    'localhost:5000'          -> 'http://localhost:5000'
    'http://1.2.3.4:5001/'    -> 'http://1.2.3.4:5001'
    '  http://host:5000/  '   -> 'http://host:5000'
    """
    url = (url or '').strip()
    if url and '://' not in url:
        url = 'http://' + url
    return url.rstrip('/')


def validar_url(url: str, nombre: str) -> List[str]:
    """Errores de formato de una URL base (lista vacia si es valida)."""
    partes = urlparse(url)
    errores = []
    if partes.scheme not in ('http', 'https'):
        errores.append(f"{nombre}: debe empezar con http:// o https://")
    if not partes.hostname:
        errores.append(f"{nombre}: falta el servidor (por ejemplo, localhost o una IP)")
    try:
        partes.port  # lanza ValueError si el puerto no es numerico o esta fuera de rango
    except ValueError:
        errores.append(f"{nombre}: el puerto no es válido")
    if partes.path not in ('', '/'):
        errores.append(f"{nombre}: escribe solo la dirección base, sin rutas como /books")
    return errores


@dataclass
class AppConfig:
    # 127.0.0.1 y no 'localhost': en Windows 'localhost' resuelve primero a ::1
    # (IPv6); Flask escucha solo en IPv4 y cada conexion espera ~2 s el reintento.
    login_url: str = 'http://127.0.0.1:5000'
    books_url: str = 'http://127.0.0.1:5001'
    timeout_segundos: float = 5.0
    intervalo_salud_segundos: int = 15
    aviso_expiracion_segundos: int = 300

    # ------------------------------------------------------------------
    @classmethod
    def predeterminada(cls) -> 'AppConfig':
        return cls()

    @classmethod
    def cargar(cls) -> 'AppConfig':
        """Lee la configuracion guardada. Si no existe o esta danada, usa los
        valores predeterminados en lugar de impedir que la app arranque."""
        try:
            datos = json.loads(RUTA_CONFIG.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return cls.predeterminada()

        conocidos = {f.name for f in fields(cls)}
        config = cls(**{k: v for k, v in datos.items() if k in conocidos})
        return config if not config.validar() else cls.predeterminada()

    def guardar(self) -> None:
        RUTA_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        RUTA_CONFIG.write_text(json.dumps(asdict(self), indent=2), encoding='utf-8')

    def normalizada(self) -> 'AppConfig':
        return AppConfig(
            login_url=normalizar_url(self.login_url),
            books_url=normalizar_url(self.books_url),
            timeout_segundos=float(self.timeout_segundos),
            intervalo_salud_segundos=int(self.intervalo_salud_segundos),
            aviso_expiracion_segundos=int(self.aviso_expiracion_segundos),
        )

    def validar(self) -> List[str]:
        errores = validar_url(self.login_url, 'Servicio de login')
        errores += validar_url(self.books_url, 'Servicio de libros')
        if not 1 <= float(self.timeout_segundos) <= 60:
            errores.append('El tiempo de espera debe estar entre 1 y 60 segundos.')
        if not 5 <= int(self.intervalo_salud_segundos) <= 3600:
            errores.append('El intervalo de comprobación debe estar entre 5 y 3600 segundos.')
        if not 10 <= int(self.aviso_expiracion_segundos) <= 3600:
            errores.append('El aviso de expiración debe estar entre 10 y 3600 segundos.')
        return errores
