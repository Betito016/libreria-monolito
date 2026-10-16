"""Errores y validadores basicos comunes a los servicios nuevos."""
import re
from typing import Any, Dict, Iterable, Optional

CORREO_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


class ValidacionError(Exception):
    def __init__(self, codigo: str, mensaje: str, **extra):
        super().__init__(mensaje)
        self.codigo, self.mensaje, self.extra = codigo, mensaje, extra


class NoEncontrado(Exception):
    """El recurso no existe: 404."""


class Conflicto(Exception):
    """Choca con el estado actual (duplicado, en uso, transicion invalida): 409."""

    def __init__(self, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.codigo, self.mensaje = codigo, mensaje


def solo_campos(datos: Dict[str, Any], permitidos: Iterable[str]) -> None:
    sobran = sorted(set(datos) - set(permitidos))
    if sobran:
        raise ValidacionError('ERR_CAMPOS_NO_PERMITIDOS', f"Campos no permitidos: {', '.join(sobran)}.",
                              campos_rechazados=sobran)


def requeridos(datos: Dict[str, Any], campos: Iterable[str]) -> None:
    faltan = [c for c in campos if datos.get(c) in (None, '', [])]
    if faltan:
        raise ValidacionError('ERR_CAMPOS_OBLIGATORIOS', f"Faltan campos obligatorios: {', '.join(faltan)}.",
                              campos_faltantes=faltan)


def texto(datos: Dict[str, Any], campo: str, maximo: int, requerido: bool = False) -> Optional[str]:
    valor = datos.get(campo)
    if valor is None:
        if requerido:
            requeridos(datos, [campo])
        return None
    if not isinstance(valor, str) or not valor.strip():
        raise ValidacionError('ERR_TIPO_INVALIDO', f"El campo '{campo}' debe ser un texto no vacío.", campo_invalido=campo)
    if len(valor.strip()) > maximo:
        raise ValidacionError('ERR_CAMPO_DEMASIADO_LARGO', f"El campo '{campo}' admite máximo {maximo} caracteres.",
                              campo_invalido=campo)
    return valor.strip()


def entero(datos: Dict[str, Any], campo: str, minimo: int = 0, maximo: int = 10**9) -> Optional[int]:
    valor = datos.get(campo)
    if valor is None:
        return None
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ValidacionError('ERR_TIPO_INVALIDO', f"El campo '{campo}' debe ser un número entero.", campo_invalido=campo)
    if not minimo <= valor <= maximo:
        raise ValidacionError('ERR_FUERA_DE_RANGO', f"El campo '{campo}' debe estar entre {minimo} y {maximo}.",
                              campo_invalido=campo)
    return valor


def numero(datos: Dict[str, Any], campo: str, minimo: float = 0, maximo: float = 99_999_999.99) -> Optional[float]:
    valor = datos.get(campo)
    if valor is None:
        return None
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValidacionError('ERR_TIPO_INVALIDO', f"El campo '{campo}' debe ser un número.", campo_invalido=campo)
    if not minimo <= float(valor) <= maximo:
        raise ValidacionError('ERR_FUERA_DE_RANGO', f"El campo '{campo}' debe estar entre {minimo} y {maximo}.",
                              campo_invalido=campo)
    return round(float(valor), 2)


def correo(datos: Dict[str, Any], campo: str = 'email', requerido: bool = False) -> Optional[str]:
    valor = texto(datos, campo, 254, requerido)
    if valor is not None and not CORREO_RE.match(valor):
        raise ValidacionError('ERR_EMAIL_INVALIDO', 'El correo no tiene un formato válido.', campo_invalido=campo)
    return valor.lower() if valor else valor
