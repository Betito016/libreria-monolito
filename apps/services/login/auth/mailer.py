"""
Envio de correos de verificacion via SMTP (Postfix local).

Flujo completo de verificacion de correo:

  1. /register genera un token aleatorio (secrets.token_urlsafe) y guarda
     SOLO su SHA-256 en `verificaciones_email`.
  2. Este modulo entrega el mensaje con el token en claro al MTA local
     (Postfix en localhost:25), que se encarga de la entrega.
  3. El usuario devuelve el token a /verify, que lo re-hashea, lo compara
     y recien entonces pone `usuarios.email_verificado = TRUE`.

El token en claro nunca se guarda: existe solo en el correo enviado. Si
alguien leyera la base, no podria canjear los tokens pendientes.

Nota sobre la entrega externa: Google Cloud bloquea el puerto 25 saliente
en las VMs de Compute Engine, asi que Postfix acepta y encola el mensaje
pero no puede entregarlo a dominios externos (gmail, outlook, etc.). El
envio del microservicio SI ocurre y es verificable en la cola del MTA
(`mailq`, `postcat -q <id>`) y en /var/log/maillog. Para entrega externa
real haria falta un relay autenticado por el puerto 587.
"""
import hashlib
import logging
import secrets
import smtplib
from email.message import EmailMessage
from typing import Tuple

from config.config import Config

logger = logging.getLogger(__name__)

TOKEN_BYTES = 32


def generar_token() -> Tuple[str, str]:
    """Devuelve (token_en_claro, sha256_del_token)."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _construir_mensaje(destinatario: str, nombre: str, token: str) -> EmailMessage:
    enlace = f"{Config.PUBLIC_BASE_URL}/verify?token={token}"

    msg = EmailMessage()
    msg['Subject'] = 'Verifica tu correo - Libreria en Linea'
    msg['From'] = Config.MAIL_FROM
    msg['To'] = destinatario
    msg.set_content(
        f"""Hola {nombre},

Para completar tu registro necesitamos confirmar que este correo te pertenece.

Tu codigo de verificacion es:

    {token}

Tambien puedes verificarlo directamente en:

    {enlace}

El codigo vence en {Config.TOKEN_TTL_HOURS} horas. Si tu no te registraste,
puedes ignorar este mensaje.

--
Libreria en Linea
Integracion de Aplicaciones Computacionales - UDEM
"""
    )
    return msg


def enviar_verificacion(destinatario: str, nombre: str, token: str) -> Tuple[bool, str]:
    """Entrega el correo de verificacion al MTA. Devuelve (enviado, detalle).

    No lanza excepcion: un fallo de correo no debe impedir que el usuario
    quede registrado. El registro se completa y el detalle queda en la
    respuesta y en los logs para poder reintentar.
    """
    if not Config.MAIL_ENABLED:
        logger.info("Envio de correo deshabilitado (MAIL_ENABLED=False).")
        return False, "envio deshabilitado por configuracion"

    mensaje = _construir_mensaje(destinatario, nombre, token)

    try:
        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=10) as smtp:
            if Config.SMTP_USE_TLS:
                smtp.starttls()
            if Config.SMTP_USER:
                smtp.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
            smtp.send_message(mensaje)

        logger.info(f"Correo de verificacion entregado al MTA para {destinatario}")
        return True, f"mensaje aceptado por el MTA en {Config.SMTP_HOST}:{Config.SMTP_PORT}"

    except smtplib.SMTPException as exc:
        logger.error(f"SMTP rechazo el mensaje para {destinatario}: {exc}")
        return False, f"el MTA rechazo el mensaje: {exc}"
    except OSError as exc:
        logger.error(f"No se pudo contactar al MTA: {exc}")
        return False, f"no se pudo contactar al MTA: {exc}"
