import datetime
import xml.etree.ElementTree as ET
from typing import Optional, Tuple

SOAP_ENV_NS = "http://schemas.xmlsoap.org/soap/envelope/"
TNS_NS = "http://udem.edu/iac/library/soap"

def create_soap_fault(
    fault_code: str,
    fault_string: str,
    codigo_error: str,
    mensaje_detalle: str,
    campo_invalido: Optional[str] = None,
    http_status: int = 500
) -> Tuple[str, int]:
    """
    Construye un sobre SOAP 1.1 con elemento Fault estructurado de forma manual y segura.
    
    :param fault_code: 'soapenv:Client' o 'soapenv:Server'
    :param fault_string: Mensaje general del error SOAP
    :param codigo_error: Código específico de negocio (ej. 'ERR_DUPLICATE_409', 'ERR_INVALID_MODEL')
    :param mensaje_detalle: Explicación amigable sin exponer internals
    :param campo_invalido: Nombre del campo que causó el error (si aplica)
    :param http_status: Código de respuesta HTTP asociado (200/400/401/409/500)
    :return: Tupla (XML en string, código de estado HTTP)
    """
    ET.register_namespace('soapenv', SOAP_ENV_NS)
    ET.register_namespace('tns', TNS_NS)

    envelope = ET.Element(f"{{{SOAP_ENV_NS}}}Envelope")
    body = ET.SubElement(envelope, f"{{{SOAP_ENV_NS}}}Body")
    fault = ET.SubElement(body, f"{{{SOAP_ENV_NS}}}Fault")

    fc_elem = ET.SubElement(fault, "faultcode")
    fc_elem.text = fault_code

    fs_elem = ET.SubElement(fault, "faultstring")
    fs_elem.text = fault_string

    detail = ET.SubElement(fault, "detail")
    fault_detail = ET.SubElement(detail, f"{{{TNS_NS}}}SoapFaultDetail")

    c_err = ET.SubElement(fault_detail, f"{{{TNS_NS}}}codigo_error")
    c_err.text = codigo_error

    m_det = ET.SubElement(fault_detail, f"{{{TNS_NS}}}mensaje")
    m_det.text = mensaje_detalle

    if campo_invalido:
        c_inv = ET.SubElement(fault_detail, f"{{{TNS_NS}}}campo_invalido")
        c_inv.text = campo_invalido

    ts = ET.SubElement(fault_detail, f"{{{TNS_NS}}}timestamp")
    ts.text = datetime.datetime.now().isoformat()

    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(envelope, encoding='unicode')
    return xml_str, http_status
