import xml.etree.ElementTree as ET
from typing import Tuple, Optional

SOAP_ENV_NS = "http://schemas.xmlsoap.org/soap/envelope/"
TNS_NS = "http://udem.edu/iac/library/soap"
WSSE_NS = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"

class EnvelopeError(Exception):
    pass

def parse_soap_request(raw_xml: str) -> Tuple[Optional[ET.Element], ET.Element, str]:
    """
    Analiza manualmente el XML recibido, valida la estructura SOAP 1.1 Envelope y extrae Header y Body.
    
    :param raw_xml: Cadena de texto XML recibida en la petición HTTP POST
    :return: Tupla (header_elem, operation_elem, operation_name)
    :raises EnvelopeError: Si el XML está mal formado o no es un SOAP Envelope válido.
    """
    if not raw_xml or not raw_xml.strip():
        raise EnvelopeError("El cuerpo de la petición XML está vacío.")

    try:
        root = ET.fromstring(raw_xml.strip().encode('utf-8'))
    except ET.ParseError as e:
        raise EnvelopeError(f"Error de análisis sintáctico XML: {e}")

    # Validar raíz Envelope
    root_tag = root.tag.split('}')[-1] if '}' in root.tag else root.tag
    if root_tag != 'Envelope':
        raise EnvelopeError(f"Elemento raíz inválido: se esperaba 'Envelope' y se recibió '{root_tag}'.")

    header_elem = None
    body_elem = None

    for child in root:
        tag_clean = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if tag_clean == 'Header':
            header_elem = child
        elif tag_clean == 'Body':
            body_elem = child

    if body_elem is None:
        raise EnvelopeError("No se encontró el elemento <Body> dentro del SOAP Envelope.")

    if len(body_elem) == 0:
        raise EnvelopeError("El elemento <Body> de la petición SOAP no contiene ninguna operación.")

    operation_elem = body_elem[0]
    operation_name = operation_elem.tag.split('}')[-1] if '}' in operation_elem.tag else operation_elem.tag

    return header_elem, operation_elem, operation_name

def create_soap_response(operation_response_element: ET.Element) -> str:
    """
    Envuelve el elemento de respuesta dentro de un <soapenv:Envelope> y <soapenv:Body> estándar.
    """
    ET.register_namespace('soapenv', SOAP_ENV_NS)
    ET.register_namespace('tns', TNS_NS)

    envelope = ET.Element(f"{{{SOAP_ENV_NS}}}Envelope")
    body = ET.SubElement(envelope, f"{{{SOAP_ENV_NS}}}Body")
    body.append(operation_response_element)

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(envelope, encoding='unicode')

def get_child_text(element: ET.Element, tag_name: str, default: str = "") -> str:
    """Extrae el texto de un hijo directo ignorando namespaces."""
    for child in element:
        child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if child_tag == tag_name:
            return child.text.strip() if child.text else default
    return default
