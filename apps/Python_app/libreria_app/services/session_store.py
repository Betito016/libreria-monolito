"""
Persistencia local de la sesion, para no pedir credenciales en cada arranque.

QUE SE GUARDA
    La cookie de sesion que emitio el microservicio de login, el JWT de
    acceso (20 min), el refresh token (para renovarlo al reabrir la app) y
    el nombre y rol del usuario (solo para mostrarlos mientras se valida).

QUE NO SE GUARDA
    La contrasena. Nunca. Recordar al usuario es recordar la cookie, no sus
    credenciales.

POR QUE ESTO NO BASTA POR SI SOLO
    Que la cookie exista en disco no significa que la sesion siga viva en el
    servidor: puede haber expirado, o el usuario pudo cerrarla en otro lado.
    Al arrancar, la aplicacion SIEMPRE la valida con GET /session antes de
    mostrar el panel principal.

DONDE
    %APPDATA%\\LibreriaPythonApp\\sesion.json  (perfil del usuario, fuera
    del repositorio). Las sesiones se guardan por servidor de login: una
    cookie de localhost no tiene sentido contra la instancia remota.

La cookie y el JWT son credenciales mientras esten vigentes: quien copie
este archivo podria actuar como el usuario hasta que expiren.
"""
import json
from datetime import datetime
from typing import Any, Dict, Optional

from requests.cookies import RequestsCookieJar

from libreria_app.config.settings import directorio_datos

RUTA_SESION = directorio_datos() / 'sesion.json'


class SessionStore:

    def _leer(self) -> Dict[str, Any]:
        try:
            return json.loads(RUTA_SESION.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def _escribir(self, datos: Dict[str, Any]) -> None:
        RUTA_SESION.parent.mkdir(parents=True, exist_ok=True)
        RUTA_SESION.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding='utf-8')

    def guardar(self, login_url: str, cookies: RequestsCookieJar, usuario: Dict[str, Any],
                tokens: Optional[Dict[str, Optional[str]]] = None) -> None:
        datos = self._leer()
        datos[login_url] = {
            'tokens': tokens or {},
            'cookies': [
                {
                    'name': c.name, 'value': c.value, 'domain': c.domain,
                    'path': c.path, 'expires': c.expires, 'secure': c.secure,
                }
                for c in cookies
            ],
            'usuario': {k: usuario.get(k) for k in ('nombre', 'apellido_paterno', 'email', 'rol', 'role_id')},
            'guardado_en': datetime.now().isoformat(timespec='seconds'),
        }
        self._escribir(datos)

    def restaurar(self, login_url: str, cookies: RequestsCookieJar) -> Optional[Dict[str, Any]]:
        """Carga en el cookie jar la sesion guardada para ese servidor.
        Devuelve los datos basicos del usuario, o None si no habia sesion."""
        entrada = self._leer().get(login_url)
        if not entrada:
            return None
        for c in entrada.get('cookies', []):
            cookies.set(
                c['name'], c['value'], domain=c['domain'], path=c['path'],
                expires=c['expires'], secure=c['secure'],
            )
        return entrada.get('usuario')

    def tokens(self, login_url: str) -> Dict[str, Optional[str]]:
        """{'access': JWT, 'refresh': refresh token} guardados para ese servidor."""
        return dict((self._leer().get(login_url) or {}).get('tokens') or {})

    def token(self, login_url: str) -> Optional[str]:
        """JWT de acceso guardado para ese servidor, o None."""
        return self.tokens(login_url).get('access')

    def borrar(self, login_url: str) -> None:
        datos = self._leer()
        if datos.pop(login_url, None) is not None:
            self._escribir(datos)

    @staticmethod
    def ruta() -> str:
        return str(RUTA_SESION)
