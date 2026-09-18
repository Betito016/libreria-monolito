"""
Validacion de correo electronico antes del registro.

El enunciado pide "validar que el correo sea real" y sugiere Postfix. Aqui la
validacion ocurre en dos niveles, sin enviar correo:

  1. Sintaxis (RFC 5322 simplificado).
  2. Registro MX del dominio via DNS: comprueba que el dominio realmente
     tenga servidores de correo declarados. Un dominio sin MX no puede
     recibir correo, asi que la direccion no puede existir.

Por que NO se sondea el buzon por SMTP (RCPT TO):
  - Google Cloud bloquea el puerto 25 saliente en las VMs de Compute Engine
    por politica de plataforma, asi que la conexion SMTP directa no sale.
  - Ademas, la mayoria de los proveedores grandes responden "accept-all" o
    aplican greylisting, de modo que el resultado no seria confiable.
  - Sondear buzones ajenos de forma masiva es un patron que las listas de
    reputacion marcan como spam.

La verificacion definitiva de propiedad del buzon requiere enviar un correo
con token de confirmacion. Eso implica un relay SMTP autenticado (puerto 587)
y un endpoint /verify que el enunciado no contempla; queda documentado como
trabajo futuro en el README.
"""
import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# RFC 5322 simplificado: suficiente para rechazar lo evidentemente invalido
# sin caer en la expresion regular completa del estandar, que es impractica.
EMAIL_REGEX = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*\.[A-Za-z]{2,}$"
)

EMAIL_MAX_LENGTH = 150  # coincide con usuarios.email VARCHAR(150)


def validate_syntax(email: str) -> Optional[str]:
    """Devuelve un mensaje de error, o None si la sintaxis es valida."""
    if not email:
        return "El correo es obligatorio."
    if len(email) > EMAIL_MAX_LENGTH:
        return f"El correo no puede exceder {EMAIL_MAX_LENGTH} caracteres."
    if not EMAIL_REGEX.match(email):
        return "El formato del correo no es valido."
    return None


def domain_has_mx(email: str) -> Tuple[bool, str]:
    """Consulta los registros MX del dominio.

    Devuelve (tiene_mx, detalle). Si dnspython no esta instalado o el DNS no
    responde, devuelve True con la nota correspondiente: un fallo de
    infraestructura de DNS no debe impedir que un usuario legitimo se
    registre (falla en modo permisivo, y queda registrado en el detalle).
    """
    domain = email.rsplit('@', 1)[-1]

    try:
        import dns.resolver
    except ImportError:
        logger.warning("dnspython no instalado: se omite la verificacion MX.")
        return True, "verificacion MX omitida (dnspython no disponible)"

    try:
        answers = dns.resolver.resolve(domain, 'MX', lifetime=5)
        hosts = sorted(str(r.exchange).rstrip('.') for r in answers)
        if hosts:
            return True, f"MX encontrado: {hosts[0]}"
        return False, f"El dominio '{domain}' no declara servidores de correo."
    except dns.resolver.NXDOMAIN:
        return False, f"El dominio '{domain}' no existe."
    except dns.resolver.NoAnswer:
        return False, f"El dominio '{domain}' no tiene registros MX."
    except Exception as exc:
        logger.warning(f"No se pudo consultar MX de '{domain}': {exc}")
        return True, f"verificacion MX no concluyente ({exc.__class__.__name__})"


def validate_email(email: str, check_mx: bool = True) -> Tuple[bool, str]:
    """Validacion completa. Devuelve (es_valido, detalle)."""
    syntax_error = validate_syntax(email)
    if syntax_error:
        return False, syntax_error

    if not check_mx:
        return True, "sintaxis valida (verificacion MX deshabilitada)"

    has_mx, detail = domain_has_mx(email)
    if not has_mx:
        return False, detail
    return True, detail
