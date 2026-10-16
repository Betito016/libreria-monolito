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

# Los seis microservicios: (clave, nombre visible, puerto por defecto).
# Toda la interfaz (configuracion, semaforos, estado) se arma con esta lista.
SERVICIOS = (
    ('login', 'Login', 5000),
    ('books', 'Libros', 5001),
    ('users', 'Usuarios', 5004),
    ('authors', 'Autores', 5005),
    ('pedidos', 'Pedidos', 5003),
    ('pagos', 'Pagos', 5002),
)
NOMBRE_SERVICIO = {clave: nombre for clave, nombre, _ in SERVICIOS}


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
        errores.append(f"{nombre}: falta el servidor (por ejemplo, 127.0.0.1 o una IP)")
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
    users_url: str = 'http://127.0.0.1:5004'
    authors_url: str = 'http://127.0.0.1:5005'
    pedidos_url: str = 'http://127.0.0.1:5003'
    pagos_url: str = 'http://127.0.0.1:5002'
    timeout_segundos: float = 5.0
    intervalo_salud_segundos: int = 15
    # El JWT dura 20 minutos: la app lo renueva sola cuando le quedan estos segundos.
    renovar_antes_segundos: int = 120
    # Ruta a un certificado (CA) para confiar en el HTTPS autofirmado de la instancia.
    certificado_ca: str = ''

    # ------------------------------------------------------------------
    @classmethod
    def predeterminada(cls) -> 'AppConfig':
        return cls()

    @classmethod
    def cargar(cls) -> 'AppConfig':
        """Lee la configuracion guardada. Si no existe o esta danada, usa los
        valores predeterminados en lugar de impedir que la app arranque. Las
        claves nuevas que no esten en un archivo viejo toman su valor por defecto."""
        try:
            datos = json.loads(RUTA_CONFIG.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return cls.predeterminada()
        conocidos = {f.name for f in fields(cls)}
        try:
            config = cls(**{k: v for k, v in datos.items() if k in conocidos})
        except TypeError:
            return cls.predeterminada()
        return config if not config.validar() else cls.predeterminada()

    def guardar(self) -> None:
        RUTA_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        RUTA_CONFIG.write_text(json.dumps(asdict(self), indent=2), encoding='utf-8')

    def url(self, servicio: str) -> str:
        return getattr(self, f'{servicio}_url')

    def normalizada(self) -> 'AppConfig':
        return AppConfig(
            **{f'{s}_url': normalizar_url(self.url(s)) for s, _, _ in SERVICIOS},
            timeout_segundos=float(self.timeout_segundos),
            intervalo_salud_segundos=int(self.intervalo_salud_segundos),
            renovar_antes_segundos=int(self.renovar_antes_segundos),
            certificado_ca=(self.certificado_ca or '').strip(),
        )

    def validar(self) -> List[str]:
        errores = []
        for clave, nombre, _ in SERVICIOS:
            errores += validar_url(self.url(clave), f'Servicio de {nombre.lower()}')
        if not 1 <= float(self.timeout_segundos) <= 60:
            errores.append('El tiempo de espera debe estar entre 1 y 60 segundos.')
        if not 5 <= int(self.intervalo_salud_segundos) <= 3600:
            errores.append('El intervalo de comprobación debe estar entre 5 y 3600 segundos.')
        if not 30 <= int(self.renovar_antes_segundos) <= 600:
            errores.append('La renovación del token debe hacerse entre 30 y 600 segundos antes de que expire.')
        if self.certificado_ca and not Path(self.certificado_ca).exists():
            errores.append(f'No existe el certificado {self.certificado_ca}.')
        return errores
