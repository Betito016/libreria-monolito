import unittest
import sys
from pathlib import Path

# Agregar directorio raíz al path de Python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from soap.service import SOAPDispatcher

class TestLibrarySOAPService(unittest.TestCase):

    def setUp(self):
        self.dispatcher = SOAPDispatcher()
        self.test_email = "test.ingeniero@udem.edu"
        self.test_nombre = "Raúl"
        self.test_apellidos = "González"

    def test_P01_obtener_conceptos_pendientes(self):
        """P01: Obtener conceptos pendientes -> Lista válida de conceptos en SOAP response."""
        xml_req = f"""<?xml version="1.0" encoding="UTF-8"?>
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://udem.edu/iac/library/soap">
            <soapenv:Header/>
            <soapenv:Body>
                <tns:ObtenerConceptosPendientesRequest>
                    <tns:clasificador_email>{self.test_email}</tns:clasificador_email>
                </tns:ObtenerConceptosPendientesRequest>
            </soapenv:Body>
        </soapenv:Envelope>
        """
        response_xml, status_code = self.dispatcher.dispatch(xml_req)
        self.assertEqual(status_code, 200)
        self.assertIn("ObtenerConceptosPendientesResponse", response_xml)
        self.assertIn("concepto_id", response_xml)
        self.assertIn("total_pendientes", response_xml)
        print("\n[PASSED] P01: Obtener conceptos pendientes retornó lista válida.")

    def test_P02_registrar_clasificacion_valida(self):
        """P02: Registrar IaaS/PaaS/SaaS/FaaS -> Registro exitoso."""
        unique_email = f"user_{id(self)}@udem.edu"
        xml_req = f"""<?xml version="1.0" encoding="UTF-8"?>
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://udem.edu/iac/library/soap">
            <soapenv:Header/>
            <soapenv:Body>
                <tns:RegistrarClasificacionRequest>
                    <tns:nombre>Ana</tns:nombre>
                    <tns:apellidos>Martínez</tns:apellidos>
                    <tns:email>{unique_email}</tns:email>
                    <tns:concepto_id>1</tns:concepto_id>
                    <tns:libro_isbn>9780134092669</tns:libro_isbn>
                    <tns:modelo_cloud>IaaS</tns:modelo_cloud>
                    <tns:cliente_tipo>Desktop-PyQt-GUI</tns:cliente_tipo>
                    <tns:cliente_id>CLI-TEST-001</tns:cliente_id>
                </tns:RegistrarClasificacionRequest>
            </soapenv:Body>
        </soapenv:Envelope>
        """
        response_xml, status_code = self.dispatcher.dispatch(xml_req)
        self.assertEqual(status_code, 200)
        self.assertIn("RegistrarClasificacionResponse", response_xml)
        self.assertIn("<tns:status>SUCCESS</tns:status>", response_xml)
        self.assertIn("clasificacion_id", response_xml)
        print("[PASSED] P02: Registro de clasificación completado con éxito.")

    def test_N01_repetir_clasificacion_duplicada(self):
        """N01: Repetir clasificación -> SOAP Fault 409 (Conflicto)."""
        dup_email = f"dup_{id(self)}@udem.edu"
        xml_req = f"""<?xml version="1.0" encoding="UTF-8"?>
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://udem.edu/iac/library/soap">
            <soapenv:Header/>
            <soapenv:Body>
                <tns:RegistrarClasificacionRequest>
                    <tns:nombre>Carlos</tns:nombre>
                    <tns:apellidos>López</tns:apellidos>
                    <tns:email>{dup_email}</tns:email>
                    <tns:concepto_id>2</tns:concepto_id>
                    <tns:libro_isbn>9780134092669</tns:libro_isbn>
                    <tns:modelo_cloud>PaaS</tns:modelo_cloud>
                </tns:RegistrarClasificacionRequest>
            </soapenv:Body>
        </soapenv:Envelope>
        """
        # Primera inserción exitosa
        resp1, code1 = self.dispatcher.dispatch(xml_req)
        self.assertEqual(code1, 200)

        # Segunda inserción idéntica -> debe generar SOAP Fault 409
        resp2, code2 = self.dispatcher.dispatch(xml_req)
        self.assertEqual(code2, 409)
        self.assertIn("Fault", resp2)
        self.assertIn("ERR_DUPLICATE_CLASSIFICATION_409", resp2)
        print("[PASSED] N01: Detección de clasificación duplicada generó SOAP Fault 409.")

    def test_N02_concepto_inexistente(self):
        """N02: Concepto inexistente -> SOAP Fault de cliente."""
        xml_req = f"""<?xml version="1.0" encoding="UTF-8"?>
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://udem.edu/iac/library/soap">
            <soapenv:Header/>
            <soapenv:Body>
                <tns:RegistrarClasificacionRequest>
                    <tns:nombre>Elena</tns:nombre>
                    <tns:apellidos>Torres</tns:apellidos>
                    <tns:email>elena@udem.edu</tns:email>
                    <tns:concepto_id>999999</tns:concepto_id>
                    <tns:libro_isbn>9780134092669</tns:libro_isbn>
                    <tns:modelo_cloud>SaaS</tns:modelo_cloud>
                </tns:RegistrarClasificacionRequest>
            </soapenv:Body>
        </soapenv:Envelope>
        """
        resp, code = self.dispatcher.dispatch(xml_req)
        self.assertEqual(code, 400)
        self.assertIn("Fault", resp)
        self.assertIn("ERR_CONCEPT_NOT_FOUND", resp)
        print("[PASSED] N02: Concepto inexistente capturado y manejado como SOAP Fault.")

    def test_N03_modelo_invalido(self):
        """N03: Modelo inválido -> SOAP Fault de validación."""
        xml_req = f"""<?xml version="1.0" encoding="UTF-8"?>
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://udem.edu/iac/library/soap">
            <soapenv:Header/>
            <soapenv:Body>
                <tns:RegistrarClasificacionRequest>
                    <tns:nombre>Laura</tns:nombre>
                    <tns:apellidos>Gómez</tns:apellidos>
                    <tns:email>laura@udem.edu</tns:email>
                    <tns:concepto_id>1</tns:concepto_id>
                    <tns:libro_isbn>9780134092669</tns:libro_isbn>
                    <tns:modelo_cloud>ModeloInvalidoNoCloud</tns:modelo_cloud>
                </tns:RegistrarClasificacionRequest>
            </soapenv:Body>
        </soapenv:Envelope>
        """
        resp, code = self.dispatcher.dispatch(xml_req)
        self.assertEqual(code, 400)
        self.assertIn("Fault", resp)
        self.assertIn("ERR_VALIDATION_INVALID_CLOUD_MODEL", resp)
        print("[PASSED] N03: Modelo inválido rechazado con SOAP Fault.")

    def test_N04_xml_mal_formado(self):
        """N04: XML sintácticamente inválido -> SOAP Fault sin ejecución SQL."""
        broken_xml = "<soapenv:Envelope><soapenv:Body><no_cerre_tag></soapenv:Body>"
        resp, code = self.dispatcher.dispatch(broken_xml)
        self.assertEqual(code, 400)
        self.assertIn("Fault", resp)
        self.assertIn("ERR_SOAP_ENVELOPE_INVALID", resp)
        print("[PASSED] N04: XML mal formado interceptado por parser manual.")

    def test_T01_ws_security_autorizado(self):
        """Tarea 1: Estadísticas protegidas con WS-Security válido -> Conteo devuelto."""
        xml_req = """<?xml version="1.0" encoding="UTF-8"?>
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                          xmlns:tns="http://udem.edu/iac/library/soap"
                          xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
            <soapenv:Header>
                <wsse:Security>
                    <wsse:UsernameToken>
                        <wsse:Username>admin_clasificador</wsse:Username>
                        <wsse:Password>CloudSecure2026!</wsse:Password>
                    </wsse:UsernameToken>
                </wsse:Security>
            </soapenv:Header>
            <soapenv:Body>
                <tns:ObtenerEstadisticasPorModeloRequest/>
            </soapenv:Body>
        </soapenv:Envelope>
        """
        resp, code = self.dispatcher.dispatch(xml_req)
        self.assertEqual(code, 200)
        self.assertIn("ObtenerEstadisticasPorModeloResponse", resp)
        self.assertIn("total_general", resp)
        print("[PASSED] Tarea 1: Consulta de estadísticas autenticada con WS-Security exitosa.")

    def test_T01_ws_security_credenciales_invalidas(self):
        """Tarea 1: Estadísticas con credenciales erróneas -> SOAP Fault 401."""
        xml_req = """<?xml version="1.0" encoding="UTF-8"?>
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                          xmlns:tns="http://udem.edu/iac/library/soap"
                          xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
            <soapenv:Header>
                <wsse:Security>
                    <wsse:UsernameToken>
                        <wsse:Username>hacker_anon</wsse:Username>
                        <wsse:Password>PasswordFalso123</wsse:Password>
                    </wsse:UsernameToken>
                </wsse:Security>
            </soapenv:Header>
            <soapenv:Body>
                <tns:ObtenerEstadisticasPorModeloRequest/>
            </soapenv:Body>
        </soapenv:Envelope>
        """
        resp, code = self.dispatcher.dispatch(xml_req)
        self.assertEqual(code, 401)
        self.assertIn("Fault", resp)
        self.assertIn("ERR_WS_SECURITY_UNAUTHORIZED", resp)
        print("[PASSED] Tarea 1: Intento no autorizado bloqueado por WS-Security (HTTP 401).")

if __name__ == '__main__':
    unittest.main()
