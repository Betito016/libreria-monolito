"""
Comprobacion del estado de los microservicios (GET /health).

Se distinguen tres niveles:

  verde     El servicio responde y reporta estado "ok": funciona y tiene
            acceso a su base de datos (y, en libros, al login).
  amarillo  El servicio RESPONDE, pero reporta estado "degradado": alguna
            dependencia (su base de datos, o el login en el caso de libros)
            no esta disponible.
  rojo      No hubo respuesta util: no se pudo conectar, se agoto el tiempo,
            la URL es invalida, o en esa direccion contesta otra cosa que no
            es el microservicio.

Detalle importante: un /health degradado puede responder con HTTP 503 y aun
asi traer un cuerpo JSON valido. Ese caso es AMARILLO (el servicio contesto
y explico que le pasa), no rojo. El rojo es solo para "no hay nadie".
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from libreria_app.api.http_client import ApiClient

NOMBRES = {'login': 'Microservicio de Login', 'books': 'Microservicio de Libros'}


@dataclass
class EstadoServicio:
    servicio: str
    nombre: str
    nivel: str                  # 'verde' | 'amarillo' | 'rojo'
    resumen: str
    url: str
    status: Optional[int]
    duracion_ms: int
    comprobado_en: datetime
    detalles: List[str] = field(default_factory=list)


def comprobar(api: ApiClient, servicio: str, registrar: bool = False) -> EstadoServicio:
    r = api.request(servicio, 'GET', '/health', con_cookies=False, registrar=registrar)
    base = dict(
        servicio=servicio, nombre=NOMBRES[servicio], url=api.url_base(servicio),
        status=r.status, duracion_ms=r.duracion_ms, comprobado_en=datetime.now(),
    )

    if r.status is None or r.codigo == 'RESPUESTA_INVALIDA':
        return EstadoServicio(nivel='rojo', resumen=r.mensaje, **base)

    datos = r.data if isinstance(r.data, dict) else {}
    detalles = _detalles(datos)
    estado = datos.get('estado')

    if estado == 'ok':
        return EstadoServicio(nivel='verde', resumen='Funcionando correctamente.', detalles=detalles, **base)
    if estado == 'degradado':
        return EstadoServicio(nivel='amarillo', resumen=_motivo_degradado(datos), detalles=detalles, **base)
    return EstadoServicio(
        nivel='amarillo', resumen=f"Respuesta inesperada del servicio (HTTP {r.status}).",
        detalles=detalles, **base,
    )


def _motivo_degradado(datos: dict) -> str:
    pg = datos.get('postgresql') or {}
    if not pg.get('conectado', True):
        return 'El servicio responde, pero no tiene acceso a su base de datos.'
    login = (datos.get('dependencias') or {}).get('login') or {}
    if login and not login.get('disponible', True):
        return 'El catálogo se puede consultar, pero no modificar: el servicio de login no está disponible.'
    return 'El servicio responde con una dependencia degradada.'


def _detalles(datos: dict) -> List[str]:
    lineas = []
    pg = datos.get('postgresql') or {}
    if pg:
        if pg.get('conectado'):
            extra = f", {pg['libros']} libros" if 'libros' in pg else ''
            lineas.append(f"PostgreSQL: conectado a {pg.get('base_datos')}{extra}")
        else:
            lineas.append('PostgreSQL: SIN CONEXIÓN')
    login = (datos.get('dependencias') or {}).get('login')
    if login:
        lineas.append(f"Dependencia login: {'disponible' if login.get('disponible') else 'NO disponible'}")
    capacidades = datos.get('capacidades')
    if capacidades:
        lineas.append(
            f"Lectura: {'sí' if capacidades.get('lectura') else 'no'} · "
            f"Escritura: {'sí' if capacidades.get('escritura') else 'no'}"
        )
    return lineas
