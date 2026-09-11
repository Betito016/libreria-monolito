import os
import sys
import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict
from flask import Flask, request, Response, jsonify
from config.config import Config
from soap.service import SOAPDispatcher
from openapi import build_openapi_spec

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] (%(name)s) %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("LibrarySoapService")

app = Flask(__name__)
dispatcher = SOAPDispatcher()

# ----------------------------------------------------------------------------
# Utilidades de respuesta bilingüe (XML / JSON)
#
# Los endpoints REST del microservicio (/books, /concepts, etc.) contestan en
# XML por defecto y en JSON cuando se envía el parámetro de consulta
# ?format=json. El endpoint SOAP (/soap) no se ve afectado: SOAP 1.1 exige
# siempre un Envelope XML, por lo que mantiene su contrato tal cual.
# ----------------------------------------------------------------------------
def _wants_json() -> bool:
    return request.args.get('format', 'xml').strip().lower() == 'json'

_PLURAL_TO_SINGULAR = {
    'autores': 'autor',
}

def _append_fields(parent: ET.Element, data: Dict[str, Any]) -> None:
    """Vuelca recursivamente un dict en elementos hijos de un nodo XML.
    Las listas se aplanan usando el singular del nombre de la clave
    (p. ej. 'libros' -> <libro>...</libro> por cada elemento)."""
    for key, value in data.items():
        if isinstance(value, list):
            item_tag = _PLURAL_TO_SINGULAR.get(key) or (key[:-1] if key.endswith('s') and len(key) > 1 else 'item')
            for item in value:
                item_elem = ET.SubElement(parent, item_tag)
                if isinstance(item, dict):
                    _append_fields(item_elem, item)
                else:
                    item_elem.text = '' if item is None else str(item)
        elif isinstance(value, dict):
            child = ET.SubElement(parent, key)
            _append_fields(child, value)
        else:
            child = ET.SubElement(parent, key)
            child.text = '' if value is None else str(value)

def api_response(root_tag: str, data: Dict[str, Any], status: int = 200):
    """Construye la respuesta del endpoint en JSON o XML según ?format."""
    if _wants_json():
        return jsonify(data), status

    root_elem = ET.Element(root_tag)
    _append_fields(root_elem, data)
    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root_elem, encoding='unicode')
    return Response(xml_str, status=status, mimetype='application/xml; charset=utf-8')

@app.after_request
def _add_cors_headers(response):
    """Habilita CORS para que clientes basados en navegador (p. ej. el
    renderer de la app de escritorio Electron) puedan consumir el XML/JSON
    de estos endpoints REST vía fetch(), sin necesidad de un proxy."""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Accept'
    return response

@app.route('/', methods=['GET'])
def index():
    return """
    <html>
    <head><title>Módulo SOAP de Clasificación de Librería</title></head>
    <body style="font-family: Arial, sans-serif; padding: 2rem; background: #0f172a; color: #f8fafc;">
        <h1>📚 Módulo SOAP de Clasificación de Librería</h1>
        <p>Servicio SOAP 1.1 independiente integrado con PostgreSQL.</p>
        <p><strong>Contrato WSDL:</strong> <a href="/soap?wsdl" style="color: #38bdf8;">/soap?wsdl</a></p>
        <p><strong>Endpoint SOAP:</strong> <code>POST /soap</code></p>
        <hr style="border: 1px solid #334155;"/>
        <p style="color: #94a3b8; font-size: 0.9rem;">Integración de Aplicaciones Computacionales 2026 - Universidad de Monterrey</p>
    </body>
    </html>
    """

@app.route('/books/covers', methods=['GET'])
def list_book_covers():
    """Datos mínimos de cada libro (ISBN, título) junto con su imagen de portada."""
    books = dispatcher.db.get_books_minimal_with_images()
    return api_response('books', {'total': len(books), 'libros': books})

@app.route('/books/<isbn>', methods=['GET'])
def get_book(isbn):
    """Detalle de un único libro identificado por su ISBN."""
    book = dispatcher.db.get_book_by_isbn(isbn)
    if not book:
        error_data = {
            'codigo_error': 'ERR_BOOK_NOT_FOUND',
            'mensaje': f"No existe un libro registrado con el ISBN '{isbn}'."
        }
        return api_response('error', error_data, status=404)
    return api_response('book', book)

@app.route('/books', methods=['GET'])
def list_books():
    """Catálogo de libros almacenados en la base de datos, paginado mediante
    los parámetros de consulta ?page= y ?page_size= (por defecto 1 y 12)."""
    try:
        page = max(1, int(request.args.get('page', 1)))
    except ValueError:
        page = 1
    try:
        page_size = min(100, max(1, int(request.args.get('page_size', 12))))
    except ValueError:
        page_size = 12
    result = dispatcher.db.get_all_books(page=page, page_size=page_size)
    return api_response('books', result)

@app.route('/concepts', methods=['GET'])
def list_cloud_concepts():
    """Todos los conceptos de Cloud Computing (IaaS, PaaS, SaaS, FaaS)
    junto con los libros del catálogo asociados a cada uno."""
    concepts = dispatcher.db.get_all_concepts_with_books()
    return api_response('concepts', {'total': len(concepts), 'conceptos': concepts})

@app.route('/openapi.json', methods=['GET'])
def openapi_spec():
    """Especificación OpenAPI 3.0 de los endpoints REST bilingües (XML/JSON)."""
    server_url = request.host_url.rstrip('/')
    return jsonify(build_openapi_spec(server_url))

@app.route('/docs', methods=['GET'])
def swagger_docs():
    """Página con Swagger UI apuntando a /openapi.json para probar los endpoints en vivo."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>API Docs - Módulo SOAP de Clasificación de Librería</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" />
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
        <script>
            window.onload = function() {
                SwaggerUIBundle({
                    url: "/openapi.json",
                    dom_id: "#swagger-ui"
                });
            };
        </script>
    </body>
    </html>
    """

@app.route('/soap', methods=['GET', 'POST'])
@app.route('/soap/library-classifier', methods=['GET', 'POST'])
def soap_endpoint():
    # Petición GET: Servir contrato WSDL
    if request.method == 'GET':
        if 'wsdl' in request.args or request.path.endswith('.wsdl'):
            if Config.WSDL_PATH.exists():
                with open(Config.WSDL_PATH, 'r', encoding='utf-8') as f:
                    wsdl_content = f.read()
                return Response(wsdl_content, mimetype='text/xml; charset=utf-8')
            else:
                return Response("<error>Archivo WSDL no encontrado en el servidor</error>", status=404, mimetype='text/xml')
        return Response("<info>Para consultar el contrato agregue ?wsdl a la URL</info>", mimetype='text/xml')

    # Petición POST: Procesar sobre SOAP
    raw_xml = request.get_data(as_text=True)
    client_ip = request.remote_addr or "127.0.0.1"

    logger.info(f"Petición SOAP recibida desde IP: {client_ip} | Tamaño: {len(raw_xml)} bytes")
    
    # Procesar con el despachador manual
    response_xml, status_code = dispatcher.dispatch(raw_xml, client_ip=client_ip)

    return Response(
        response_xml,
        status=status_code,
        mimetype='text/xml; charset=utf-8'
    )

if __name__ == '__main__':
    logger.info(f"Iniciando Módulo SOAP en http://{Config.SOAP_HOST}:{Config.SOAP_PORT}/soap")
    logger.info(f"Contrato WSDL disponible en http://localhost:{Config.SOAP_PORT}/soap?wsdl")
    app.run(host=Config.SOAP_HOST, port=Config.SOAP_PORT, debug=Config.DEBUG)
