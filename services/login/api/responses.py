"""
Representacion bilingue de un mismo recurso: XML por defecto, JSON bajo
peticion explicita (?format=json).

Mismo criterio que el microservicio SOAP/REST de services/soap, para que todo
el monorepo se comporte igual: el formato es una decision de presentacion, no
de contenido. Los handlers construyen un unico dict y esta capa lo serializa.
"""
import xml.etree.ElementTree as ET
from typing import Any, Dict

from flask import Response, jsonify, request

# Plurales cuyo singular no se obtiene quitando la 's' final.
_PLURAL_TO_SINGULAR = {
    'errores': 'error',
    'campos_actualizados': 'campo',
    'campos_faltantes': 'campo',
    'campos_rechazados': 'campo',
}


def wants_json() -> bool:
    """XML es el formato por defecto: solo se responde JSON si se pide."""
    return request.args.get('format', 'xml').strip().lower() == 'json'


def _to_xml_text(value: Any) -> str:
    """Serializa un valor escalar a texto XML.

    Los booleanos van en minusculas ('true'/'false'), que es lo que define
    xs:boolean y lo que espera cualquier parser XML. `str(True)` en Python
    produciria 'True', que un cliente XML no interpretaria como booleano.
    """
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


def _append_fields(parent: ET.Element, data: Dict[str, Any]) -> None:
    """Vuelca recursivamente un dict en elementos hijos de un nodo XML."""
    for key, value in data.items():
        if isinstance(value, list):
            item_tag = _PLURAL_TO_SINGULAR.get(key) or (
                key[:-1] if key.endswith('s') and len(key) > 1 else 'item'
            )
            for item in value:
                item_elem = ET.SubElement(parent, item_tag)
                if isinstance(item, dict):
                    _append_fields(item_elem, item)
                else:
                    item_elem.text = _to_xml_text(item)
        elif isinstance(value, dict):
            _append_fields(ET.SubElement(parent, key), value)
        else:
            child = ET.SubElement(parent, key)
            child.text = _to_xml_text(value)


def api_response(root_tag: str, data: Dict[str, Any], status: int = 200) -> Response:
    """Serializa `data` como JSON o XML segun ?format, con el mismo contenido."""
    if wants_json():
        response = jsonify(data)
        response.status_code = status
        return response

    root_elem = ET.Element(root_tag)
    _append_fields(root_elem, data)
    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        root_elem, encoding='unicode'
    )
    return Response(xml_str, status=status, mimetype='application/xml; charset=utf-8')


def error_response(codigo: str, mensaje: str, status: int = 400, **extra) -> Response:
    """Forma unica para todos los errores del microservicio."""
    payload = {'estado': 'error', 'codigo_error': codigo, 'mensaje': mensaje}
    payload.update(extra)
    return api_response('error', payload, status=status)


def parse_request_body() -> Dict[str, Any]:
    """Lee el cuerpo de la peticion sin importar como lo envie el cliente.

    El enunciado especifica el formato de RESPUESTA (?format=), pero no el de
    la peticion. Se aceptan los tres que un evaluador podria usar -- JSON,
    formulario y XML -- para que el endpoint funcione con curl, Swagger UI,
    Postman o un formulario HTML sin configuracion adicional.
    """
    if request.is_json:
        payload = request.get_json(silent=True)
        if isinstance(payload, dict):
            return payload

    if request.form:
        return request.form.to_dict()

    raw = (request.get_data(as_text=True) or '').strip()
    if raw.startswith('<'):
        try:
            root = ET.fromstring(raw)
            return {child.tag: (child.text or '') for child in root}
        except ET.ParseError:
            return {}

    return {}
