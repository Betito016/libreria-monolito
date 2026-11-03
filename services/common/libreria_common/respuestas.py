"""
Respuestas bilingues: XML por defecto, JSON con ?format=json. Mismo criterio
que login y books, para los servicios nuevos (users, authors, pedidos, pagos).
"""
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict

from flask import Response, jsonify, request

# Plurales cuyo singular no se obtiene quitando la 's' final.
_PLURAL_A_SINGULAR = {
    'autores': 'autor', 'imagenes': 'imagen', 'roles': 'rol', 'pedidos': 'pedido',
    'lineas': 'linea', 'campos_actualizados': 'campo', 'campos_faltantes': 'campo',
    'campos_rechazados': 'campo', 'libros': 'libro', 'pagos': 'pago', 'usuarios': 'usuario',
    'estados_validos': 'estado',
}


def wants_json() -> bool:
    return request.args.get('format', 'xml').strip().lower() == 'json'


def _texto_xml(valor: Any) -> str:
    if valor is None:
        return ''
    if isinstance(valor, bool):
        return 'true' if valor else 'false'
    return str(valor)


_NOMBRE_XML = re.compile(r'^[A-Za-z_][A-Za-z0-9_.-]*$')


def _nodo(padre: ET.Element, clave: Any) -> ET.Element:
    """Las claves que no son nombres XML validos (p. ej. '200' o 'GET /api/books/<isbn>'
    en /metrics) van como <item clave="...">: si no, el XML quedaria mal formado."""
    clave = str(clave)
    if _NOMBRE_XML.match(clave) and not clave.lower().startswith('xml'):
        return ET.SubElement(padre, clave)
    return ET.SubElement(padre, 'item', {'clave': clave})


def _agregar(padre: ET.Element, datos: Dict[str, Any]) -> None:
    for clave, valor in datos.items():
        if isinstance(valor, list):
            etiqueta = _PLURAL_A_SINGULAR.get(clave) or (clave[:-1] if clave.endswith('s') and len(clave) > 1 else 'item')
            contenedor = _nodo(padre, clave)
            for item in valor:
                nodo = ET.SubElement(contenedor, etiqueta if _NOMBRE_XML.match(etiqueta) else 'item')
                if isinstance(item, dict):
                    _agregar(nodo, item)
                else:
                    nodo.text = _texto_xml(item)
        elif isinstance(valor, dict):
            _agregar(_nodo(padre, clave), valor)
        else:
            _nodo(padre, clave).text = _texto_xml(valor)


def api_response(raiz: str, datos: Dict[str, Any], status: int = 200, headers=None) -> Response:
    if wants_json():
        respuesta = jsonify(datos)
        respuesta.status_code = status
    else:
        elemento = ET.Element(raiz)
        _agregar(elemento, datos)
        texto = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(elemento, encoding='unicode')
        respuesta = Response(texto, status=status, mimetype='application/xml; charset=utf-8')
    for nombre, valor in (headers or {}).items():
        respuesta.headers[nombre] = valor
    return respuesta


def error_response(codigo: str, mensaje: str, status: int = 400, **extra) -> Response:
    return api_response('error', {'estado': 'error', 'codigo_error': codigo, 'mensaje': mensaje, **extra}, status=status)


def leer_json() -> Dict[str, Any]:
    """Cuerpo JSON de la peticion (los servicios nuevos solo aceptan JSON)."""
    if not request.data:
        return {}
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        from libreria_common.validacion import ValidacionError
        raise ValidacionError('ERR_CUERPO_INVALIDO', 'El cuerpo de la petición debe ser un objeto JSON.')
    return datos
