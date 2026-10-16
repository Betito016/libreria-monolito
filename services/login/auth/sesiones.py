"""
Sesiones y refresh tokens en Redis (operaciones CRITICAS: si Redis no
responde, se lanza RedisNoDisponible y el servicio responde 503).

    session:<sid>              JSON {user_id, email, role_id, refresh, jti, exp_access, creada}
                               TTL = SESSION_TTL_MINUTES (deslizante: se renueva en cada refresh)
    refresh:<sha256(token)>    sid de la sesion; mismo TTL que la sesion
    user:sessions:<user_id>    SET de sids del usuario (para cerrarlas todas)

El refresh token es de UN SOLO USO: al renovar se consume con GETDEL (atomico)
y se emite otro. Si alguien reutiliza uno ya consumido, no existe y se rechaza.
"""
import json
import secrets
import time
from typing import Any, Dict, Optional, Tuple

from libreria_common.redis_capa import CapaRedis
from auth.jwt_tokens import huella, nuevo_refresh_token


class AlmacenSesiones:

    def __init__(self, capa: CapaRedis, ttl_minutos: int):
        self.capa = capa
        self.ttl = ttl_minutos * 60

    def _guardar(self, tubo, sid: str, datos: Dict[str, Any], refresh_hash: str) -> None:
        tubo.set(f'session:{sid}', json.dumps(datos), ex=self.ttl)
        tubo.set(f'refresh:{refresh_hash}', sid, ex=self.ttl)
        tubo.sadd(f"user:sessions:{datos['user_id']}", sid)
        tubo.expire(f"user:sessions:{datos['user_id']}", self.ttl)

    def crear(self, usuario: Dict[str, Any], sid: str, access: Dict[str, Any]) -> str:
        """Crea la sesion y devuelve el refresh token (en claro, solo esta vez)."""
        refresh = nuevo_refresh_token()
        datos = {'user_id': str(usuario['id']), 'email': usuario['email'], 'role_id': int(usuario['role_id']),
                 'refresh': huella(refresh), 'jti': access['jti'], 'exp_access': access['expira_en_epoch'],
                 'creada': int(time.time())}

        def operar(r):
            tubo = r.pipeline(transaction=True)
            self._guardar(tubo, sid, datos, datos['refresh'])
            tubo.execute()
        self.capa.ejecutar(operar, critico=True)
        return refresh

    @staticmethod
    def nuevo_sid() -> str:
        return secrets.token_urlsafe(32)

    def obtener(self, sid: Optional[str]) -> Optional[Dict[str, Any]]:
        if not sid:
            return None
        def operar(r):
            tubo = r.pipeline(transaction=False)
            tubo.get(f'session:{sid}')
            tubo.ttl(f'session:{sid}')
            return tubo.execute()
        crudo, ttl = self.capa.ejecutar(operar, critico=True)
        if not crudo:
            return None
        datos = json.loads(crudo)
        datos['sid'] = sid
        datos['segundos_restantes'] = max(0, int(ttl))
        return datos

    def consumir_refresh(self, refresh_token: str) -> Optional[str]:
        """Consume el refresh token (un solo uso). Devuelve el sid o None."""
        return self.capa.ejecutar(lambda r: r.getdel(f'refresh:{huella(refresh_token)}'), critico=True)

    def rotar(self, sesion: Dict[str, Any], access: Dict[str, Any]) -> str:
        """Tras consumir el refresh anterior: guarda el refresh y el jti nuevos
        y reinicia el TTL de la sesion. Devuelve el refresh nuevo."""
        refresh = nuevo_refresh_token()
        datos = {k: sesion[k] for k in ('user_id', 'email', 'role_id', 'creada')}
        datos.update(refresh=huella(refresh), jti=access['jti'], exp_access=access['expira_en_epoch'])

        def operar(r):
            tubo = r.pipeline(transaction=True)
            tubo.delete(f"refresh:{sesion['refresh']}")      # por si se renovo por cookie
            self._guardar(tubo, sesion['sid'], datos, datos['refresh'])
            tubo.execute()
        self.capa.ejecutar(operar, critico=True)
        return refresh

    def cerrar(self, sid: str) -> Optional[Dict[str, Any]]:
        """Borra la sesion y su refresh token. Devuelve lo que habia (o None)."""
        sesion = self.obtener(sid)
        if not sesion:
            return None

        def operar(r):
            tubo = r.pipeline(transaction=True)
            tubo.delete(f'session:{sid}', f"refresh:{sesion['refresh']}")
            tubo.srem(f"user:sessions:{sesion['user_id']}", sid)
            tubo.execute()
        self.capa.ejecutar(operar, critico=True)
        return sesion

    def cerrar_todas(self, user_id: str) -> int:
        """Cierra todas las sesiones del usuario (cambio de contrasena o de rol)."""
        sids = self.capa.ejecutar(lambda r: r.smembers(f'user:sessions:{user_id}'), critico=True) or set()
        cerradas = sum(1 for sid in sids if self.cerrar(sid))
        self.capa.ejecutar(lambda r: r.delete(f'user:sessions:{user_id}'), critico=True)
        return cerradas

    def tiempos(self, sesion: Dict[str, Any]) -> Tuple[int, int]:
        return sesion['segundos_restantes'], max(0, int(sesion['exp_access']) - int(time.time()))
