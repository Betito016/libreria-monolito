import xml.etree.ElementTree as ET
from typing import Optional, Tuple
from config.config import Config

WSSE_NS = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
WSU_NS = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"

class SecurityException(Exception):
    def __init__(self, message: str, code: str = "ERR_AUTH_FAILED"):
        super().__init__(message)
        self.code = code

def extract_and_validate_ws_security(header_element: Optional[ET.Element]) -> Tuple[bool, Optional[str]]:
    """
    Analiza el encabezado SOAP Header buscando el bloque de seguridad WS-Security (UsernameToken)
    y valida las credenciales configuradas en el servidor.
    
    :param header_element: Elemento XML correspondiente a <soapenv:Header>
    :return: Tupla (True, username) si la autenticación es válida
    :raises SecurityException: Si faltan credenciales o son incorrectas
    """
    if header_element is None:
        raise SecurityException("Operación protegida: Se requiere encabezado SOAP Header con autenticación WS-Security.", "ERR_WS_SECURITY_MISSING_HEADER")

    # Buscar nodo wsse:Security
    sec_node = None
    for child in header_element:
        tag_clean = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if tag_clean == 'Security':
            sec_node = child
            break

    if sec_node is None:
        raise SecurityException("Encabezado de seguridad wsse:Security no encontrado.", "ERR_WS_SECURITY_MISSING")

    # Buscar wsse:UsernameToken
    token_node = None
    for child in sec_node:
        tag_clean = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if tag_clean == 'UsernameToken':
            token_node = child
            break

    if token_node is None:
        raise SecurityException("Elemento wsse:UsernameToken ausente en el bloque de seguridad.", "ERR_WS_SECURITY_NO_TOKEN")

    username = None
    password = None

    for child in token_node:
        tag_clean = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if tag_clean == 'Username':
            username = child.text.strip() if child.text else ""
        elif tag_clean == 'Password':
            password = child.text.strip() if child.text else ""

    if not username or not password:
        raise SecurityException("Credenciales incompletas en UsernameToken (Username o Password vacíos).", "ERR_WS_SECURITY_EMPTY_CREDENTIALS")

    # Validación contra credenciales autorizadas
    if username != Config.WS_SECURITY_USER or password != Config.WS_SECURITY_PASS:
        raise SecurityException("Credenciales WS-Security inválidas o no autorizadas.", "ERR_WS_SECURITY_UNAUTHORIZED")

    return True, username
