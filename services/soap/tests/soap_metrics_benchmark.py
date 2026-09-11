"""
==============================================================================
TAREA 5: Medición Técnica y Benchmark SOAP (Overhead XML vs Payload)
==============================================================================
Este script calcula y registra:
1. Tamaño en bytes de solicitud y respuesta de RegistrarClasificacion (SOAP vs JSON/Negocio).
2. Porcentaje de overhead XML frente a datos de negocio reales.
3. Conteo de líneas de código (LOC) de los componentes del servicio y clientes.
==============================================================================
"""

import os
import sys
import json
from pathlib import Path

# Configurar salida segura para Windows UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent

def calculate_metrics():
    print("=" * 75)
    print("MEDICION TECNICA Y BENCHMARK SOAP (TAREA 5)")
    print("=" * 75)

    # 1. Payload de Negocio Puro (Equivalente JSON)
    business_request_data = {
        "nombre": "Alex",
        "apellidos": "Morales",
        "email": "alex.morales@udem.edu",
        "concepto_id": 1,
        "libro_isbn": "9780134092669",
        "modelo_cloud": "IaaS",
        "cliente_tipo": "Desktop-Tkinter-GUI",
        "cliente_id": "GUI-USER-01"
    }
    json_req_bytes = len(json.dumps(business_request_data).encode('utf-8'))

    # Solicitud SOAP Envelope Real
    soap_req_xml = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://udem.edu/iac/library/soap">
    <soapenv:Header/>
    <soapenv:Body>
        <tns:RegistrarClasificacionRequest>
            <tns:nombre>Alex</tns:nombre>
            <tns:apellidos>Morales</tns:apellidos>
            <tns:email>alex.morales@udem.edu</tns:email>
            <tns:concepto_id>1</tns:concepto_id>
            <tns:libro_isbn>9780134092669</tns:libro_isbn>
            <tns:modelo_cloud>IaaS</tns:modelo_cloud>
            <tns:cliente_tipo>Desktop-Tkinter-GUI</tns:cliente_tipo>
            <tns:cliente_id>GUI-USER-01</tns:cliente_id>
        </tns:RegistrarClasificacionRequest>
    </soapenv:Body>
</soapenv:Envelope>"""
    soap_req_bytes = len(soap_req_xml.encode('utf-8'))

    # 2. Respuesta de Negocio Pura (Equivalente JSON)
    business_response_data = {
        "status": "SUCCESS",
        "mensaje": "Concepto 1 clasificado exitosamente como 'IaaS' por alex.morales@udem.edu.",
        "clasificacion_id": 1,
        "fecha_registro": "2026-09-01T16:30:00.000000"
    }
    json_resp_bytes = len(json.dumps(business_response_data).encode('utf-8'))

    # Respuesta SOAP Envelope Real
    soap_resp_xml = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://udem.edu/iac/library/soap">
    <soapenv:Body>
        <tns:RegistrarClasificacionResponse>
            <tns:status>SUCCESS</tns:status>
            <tns:mensaje>Concepto 1 clasificado exitosamente como 'IaaS' por alex.morales@udem.edu.</tns:mensaje>
            <tns:clasificacion_id>1</tns:clasificacion_id>
            <tns:fecha_registro>2026-09-01T16:30:00.000000</tns:fecha_registro>
        </tns:RegistrarClasificacionResponse>
    </soapenv:Body>
</soapenv:Envelope>"""
    soap_resp_bytes = len(soap_resp_xml.encode('utf-8'))

    # Cálculos de overhead
    req_overhead_pct = ((soap_req_bytes - json_req_bytes) / soap_req_bytes) * 100.0
    resp_overhead_pct = ((soap_resp_bytes - json_resp_bytes) / soap_resp_bytes) * 100.0

    print("\n--- 1. COMPARATIVA DE TAMANIO EN BYTES (RegistrarClasificacion) ---")
    print(f" * Solicitud JSON (Datos puros):     {json_req_bytes} bytes")
    print(f" * Solicitud SOAP XML (Envelope):    {soap_req_bytes} bytes")
    print(f" * Overhead XML en Solicitud:        {req_overhead_pct:.2f}%")
    print()
    print(f" * Respuesta JSON (Datos puros):     {json_resp_bytes} bytes")
    print(f" * Respuesta SOAP XML (Envelope):    {soap_resp_bytes} bytes")
    print(f" * Overhead XML en Respuesta:        {resp_overhead_pct:.2f}%")

    # 3. Conteo de Líneas de Código (LOC)
    print("\n--- 2. CONTEO DE LINEAS DE CODIGO (LOC) ---")
    files_to_count = [
        ("Servidor Flask (app.py)", BASE_DIR / 'app.py'),
        ("Despachador de Servicio (soap/service.py)", BASE_DIR / 'soap' / 'service.py'),
        ("Parser/Constructor XML (soap/envelope.py)", BASE_DIR / 'soap' / 'envelope.py'),
        ("Manejador de Faults (soap/faults.py)", BASE_DIR / 'soap' / 'faults.py'),
        ("Seguridad WS-Security (soap/security.py)", BASE_DIR / 'soap' / 'security.py'),
        ("Persistencia SQL (db/database.py)", BASE_DIR / 'db' / 'database.py'),
        ("Contrato WSDL (wsdl/library-classifier.wsdl)", BASE_DIR / 'wsdl' / 'library-classifier.wsdl'),
        ("Script de Base de Datos (sql/soap_module.sql)", BASE_DIR / 'sql' / 'soap_module.sql'),
        ("Cliente de Escritorio GUI (client/desktop_classifier.py)", BASE_DIR / 'client' / 'desktop_classifier.py'),
        ("Suite de Pruebas (tests/test_soap_suite.py)", BASE_DIR / 'tests' / 'test_soap_suite.py')
    ]

    total_loc = 0
    for name, path in files_to_count:
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                lines = [l for l in f.readlines() if l.strip() and not l.strip().startswith("#") and not l.strip().startswith("--")]
                loc = len(lines)
                total_loc += loc
                print(f" * {name:<55}: {loc:>4} lineas efectivas")

    print(f" {'-'*65}")
    print(f" * TOTAL LINEAS DE CODIGO EFECTIVAS PROYECTO:       {total_loc:>4} LOC")
    print("=" * 75)

if __name__ == '__main__':
    calculate_metrics()
