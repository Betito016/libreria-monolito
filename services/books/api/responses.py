"""
Representacion bilingue de un mismo recurso: XML por defecto, JSON bajo
peticion explicita (?format=json).

Mismo criterio que services/login, pero cada microservicio lleva su propia
copia: son desplegables de forma independiente y no comparten codigo.
"""
import xml.etree.ElementTree as ET
from typing import Any, Dict

from flask import Response, jsonify, request

# Plurales cuyo singular no se obtiene quitando la 's' final.
_PLURAL_TO_SINGULAR = {
    'autores': 'autor',
    'imagenes': 'imagen',
    'campos_actualizados': 'campo',
    'campos_faltantes': 'campo',
    'campos_rechazados': 'campo',
    'campos_permitidos': 'campo',
    'categorias_validas': 'categoria',
}


def wants_json() -> bool:
    """XML es el formato por defecto: solo se responde JSON si se pide."""
    return request.args.get('format', 'xml').strip().lower() == 'json'


def _to_xml_text(value: Any) -> str:
    """Booleanos en minusculas, como exige xs:boolean."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


def _append_fields(parent: ET.Element, data: Dict[str, Any]) -> None:
    for key, value in data.items():
        if isinstance(value, list):
            item_tag = _PLURAL_TO_SINGULAR.get(key) or (
                key[:-1] if key.endswith('s') and len(key) > 1 else 'item'
            )
            # A diferencia del login, las listas van envueltas en su propio
            # nodo (<autores><autor/>...</autores>): un libro tiene varias
            # listas y aplanarlas mezclaria sus elementos entre si.
            contenedor = ET.SubElement(parent, key)
            for item in value:
                item_elem = ET.SubElement(contenedor, item_tag)
                if isinstance(item, dict):
                    _append_fields(item_elem, item)
                else:
                    item_elem.text = _to_xml_text(item)
        elif isinstance(value, dict):
            _append_fields(ET.SubElement(parent, key), value)
        else:
            ET.SubElement(parent, key).text = _to_xml_text(value)


def api_response(root_tag: str, data: Dict[str, Any], status: int = 200, headers=None) -> Response:
    if wants_json():
        response = jsonify(data)
        response.status_code = status
    else:
        root_elem = ET.Element(root_tag)
        _append_fields(root_elem, data)
        xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root_elem, encoding='unicode')
        response = Response(xml_str, status=status, mimetype='application/xml; charset=utf-8')

    for nombre, valor in (headers or {}).items():
        response.headers[nombre] = valor
    return response


def error_response(codigo: str, mensaje: str, status: int = 400, **extra) -> Response:
    payload = {'estado': 'error', 'codigo_error': codigo, 'mensaje': mensaje}
    payload.update(extra)
    return api_response('error', payload, status=status)


def _xml_a_dict(elemento: ET.Element) -> Any:
    """Un nodo con hijos se interpreta como lista de sus textos
    (<autores><autor>A</autor><autor>B</autor></autores> -> ['A', 'B'])."""
    hijos = list(elemento)
    if not hijos:
        return (elemento.text or '').strip()
    return [(h.text or '').strip() for h in hijos]


def parse_request_body() -> Any:
    """JSON, formulario o XML. Devuelve None si el cuerpo no se pudo leer."""
    if request.is_json:
        return request.get_json(silent=True)

    if request.form:
        return request.form.to_dict()

    raw = (request.get_data(as_text=True) or '').strip()
    if raw.startswith('<'):
        try:
            root = ET.fromstring(raw)
            return {hijo.tag: _xml_a_dict(hijo) for hijo in root}
        except ET.ParseError:
            return None

    return {} if not raw else None
