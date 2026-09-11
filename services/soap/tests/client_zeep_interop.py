"""
==============================================================================
TAREA 4: Demostración de Interoperabilidad con Cliente SOAP Generado (Zeep)
==============================================================================
Este cliente utiliza la biblioteca Zeep para interpretar directamente el
contrato WSDL (library-classifier.wsdl) y generar las estructuras de cliente
de forma automática sin conocer los detalles de implementación interna.
==============================================================================
"""

import os
import sys
from pathlib import Path

# Configurar salida segura para Windows UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import zeep
from zeep import Client

BASE_DIR = Path(__file__).resolve().parent.parent
WSDL_FILE = str(BASE_DIR / 'wsdl' / 'library-classifier.wsdl')

def test_interoperability():
    print("=" * 70)
    print("DEMOSTRACION DE INTEROPERABILIDAD SOAP (TAREA 4)")
    print(f"Cargando contrato WSDL desde: {WSDL_FILE}")
    print("=" * 70)

    try:
        client = Client(wsdl=WSDL_FILE)
        print("[OK] Cliente WSDL inicializado e inspeccionado con exito por Zeep.")
        
        # Mostrar operaciones disponibles descubiertas desde el WSDL
        print("\nOperaciones descubiertas dinamicamente desde el WSDL:")
        for service in client.wsdl.services.values():
            for port in service.ports.values():
                for operation in port.binding._operations.values():
                    print(f" * Operacion: {operation.name}")

        print("\n" + "-" * 70)
        print("1. Validando estructura generada desde el contrato XSD...")
        print("-" * 70)
        
        concept_type = client.get_type('ns0:ConceptoPendienteType')
        print(f" * Tipo XSD detectado e instanciado: {concept_type}")

        print("\n[EXITO] Interoperabilidad demostrada: El WSDL define el contrato de forma estricta")
        print("        permitiendo a cualquier cliente (.NET, Java, Zeep) interactuar sin acoplamiento.")

    except Exception as e:
        print(f"[ERROR] Error durante prueba de interoperabilidad: {e}")

if __name__ == '__main__':
    test_interoperability()
