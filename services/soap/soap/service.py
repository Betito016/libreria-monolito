import logging
import datetime
import xml.etree.ElementTree as ET
from typing import Tuple, Optional

from db.database import (
    DatabaseManager,
    DuplicateClassificationError,
    ConceptNotFoundError
)
from soap.envelope import (
    TNS_NS,
    get_child_text,
    create_soap_response,
    parse_soap_request,
    EnvelopeError
)
from soap.faults import create_soap_fault
from soap.security import extract_and_validate_ws_security, SecurityException

logger = logging.getLogger(__name__)

ALLOWED_CLOUD_MODELS = {'IaaS', 'PaaS', 'SaaS', 'FaaS'}

class SOAPDispatcher:
    def __init__(self):
        self.db = DatabaseManager.get_instance()

    def dispatch(self, raw_xml: str, client_ip: str = "127.0.0.1") -> Tuple[str, int]:
        """
        Punto de entrada principal para despachar una petición SOAP HTTP POST.
        
        :param raw_xml: XML crudo recibido en el cuerpo HTTP
        :param client_ip: Dirección IP del cliente para fines de auditoría
        :return: Tupla (XML de respuesta, código de estado HTTP)
        """
        try:
            # 1. Parseo manual del sobre SOAP
            header_elem, operation_elem, operation_name = parse_soap_request(raw_xml)
        except EnvelopeError as e:
            logger.warning(f"Error en estructura SOAP Envelope: {e}")
            return create_soap_fault(
                fault_code="soapenv:Client",
                fault_string="Error en la estructura del mensaje SOAP Envelope.",
                codigo_error="ERR_SOAP_ENVELOPE_INVALID",
                mensaje_detalle=str(e),
                http_status=400
            )
        except Exception as e:
            logger.error(f"Error inesperado al parsear XML: {e}", exc_info=True)
            return create_soap_fault(
                fault_code="soapenv:Client",
                fault_string="El XML enviado no pudo ser interpretado.",
                codigo_error="ERR_XML_PARSE_FAILED",
                mensaje_detalle="Sintaxis XML inválida o mal estructurada.",
                http_status=400
            )

        # 2. Despacho según el nombre de la operación
        try:
            if operation_name == "ObtenerConceptosPendientesRequest" or operation_name == "ObtenerConceptosPendientes":
                return self._handle_obtener_conceptos_pendientes(operation_elem)

            elif operation_name == "RegistrarClasificacionRequest" or operation_name == "RegistrarClasificacion":
                return self._handle_registrar_clasificacion(operation_elem, client_ip)

            elif operation_name == "ObtenerProgresoUsuarioRequest" or operation_name == "ObtenerProgresoUsuario":
                return self._handle_obtener_progreso_usuario(operation_elem)

            elif operation_name == "ObtenerEstadisticasPorModeloRequest" or operation_name == "ObtenerEstadisticasPorModelo":
                return self._handle_obtener_estadisticas_por_modelo(header_elem, operation_elem)

            else:
                return create_soap_fault(
                    fault_code="soapenv:Client",
                    fault_string=f"Operación '{operation_name}' no reconocida en el contrato WSDL.",
                    codigo_error="ERR_OPERATION_NOT_FOUND",
                    mensaje_detalle=f"Las operaciones soportadas son: ObtenerConceptosPendientes, RegistrarClasificacion, ObtenerProgresoUsuario, ObtenerEstadisticasPorModelo.",
                    http_status=400
                )

        except DuplicateClassificationError as e:
            logger.warning(f"Conflicto de clasificación duplicada: {e}")
            return create_soap_fault(
                fault_code="soapenv:Client",
                fault_string="Conflicto: Clasificación duplicada.",
                codigo_error="ERR_DUPLICATE_CLASSIFICATION_409",
                mensaje_detalle=str(e),
                http_status=409
            )

        except ConceptNotFoundError as e:
            logger.warning(f"Concepto no encontrado: {e}")
            return create_soap_fault(
                fault_code="soapenv:Client",
                fault_string="Concepto inexistente.",
                codigo_error="ERR_CONCEPT_NOT_FOUND",
                mensaje_detalle=str(e),
                campo_invalido="concepto_id",
                http_status=400
            )

        except SecurityException as e:
            logger.warning(f"Falla de seguridad WS-Security: {e}")
            return create_soap_fault(
                fault_code="soapenv:Client",
                fault_string="Error de autenticación WS-Security.",
                codigo_error=e.code,
                mensaje_detalle=str(e),
                http_status=401
            )

        except Exception as e:
            logger.error(f"Error interno no controlado en el servidor SOAP: {e}", exc_info=True)
            return create_soap_fault(
                fault_code="soapenv:Server",
                fault_string="Ocurrió un error interno en el servidor SOAP.",
                codigo_error="ERR_INTERNAL_SERVER_ERROR",
                mensaje_detalle="La petición no pudo ser procesada. El incidente ha sido registrado en los logs del servidor.",
                http_status=500
            )

    # ------------------------------------------------------------------------
    # Manejador: ObtenerConceptosPendientes
    # ------------------------------------------------------------------------
    def _handle_obtener_conceptos_pendientes(self, elem: ET.Element) -> Tuple[str, int]:
        email = get_child_text(elem, "clasificador_email", "") or None
        conceptos = self.db.get_pending_concepts(email)

        # Construir elemento de respuesta XML
        resp_elem = ET.Element(f"{{{TNS_NS}}}ObtenerConceptosPendientesResponse")

        for c in conceptos:
            c_elem = ET.SubElement(resp_elem, f"{{{TNS_NS}}}conceptos")
            
            cid = ET.SubElement(c_elem, f"{{{TNS_NS}}}concepto_id")
            cid.text = str(c['concepto_id'])
            
            cnom = ET.SubElement(c_elem, f"{{{TNS_NS}}}concepto_nombre")
            cnom.text = c['concepto_nombre']
            
            cdef = ET.SubElement(c_elem, f"{{{TNS_NS}}}definicion")
            cdef.text = c['definicion']
            
            lisbn = ET.SubElement(c_elem, f"{{{TNS_NS}}}libro_isbn")
            lisbn.text = c['libro_isbn']
            
            ltit = ET.SubElement(c_elem, f"{{{TNS_NS}}}libro_titulo")
            ltit.text = c['libro_titulo']
            
            lanio = ET.SubElement(c_elem, f"{{{TNS_NS}}}libro_anio")
            lanio.text = str(c['libro_anio'])
            
            lcat = ET.SubElement(c_elem, f"{{{TNS_NS}}}categoria")
            lcat.text = c['categoria']

        tot_elem = ET.SubElement(resp_elem, f"{{{TNS_NS}}}total_pendientes")
        tot_elem.text = str(len(conceptos))

        return create_soap_response(resp_elem), 200

    # ------------------------------------------------------------------------
    # Manejador: RegistrarClasificacion
    # ------------------------------------------------------------------------
    def _handle_registrar_clasificacion(self, elem: ET.Element, client_ip: str) -> Tuple[str, int]:
        nombre = get_child_text(elem, "nombre")
        apellidos = get_child_text(elem, "apellidos")
        email = get_child_text(elem, "email")
        concepto_id_str = get_child_text(elem, "concepto_id")
        libro_isbn = get_child_text(elem, "libro_isbn")
        modelo_cloud = get_child_text(elem, "modelo_cloud")
        cliente_tipo = get_child_text(elem, "cliente_tipo", "Desktop-GUI-Client")
        cliente_id = get_child_text(elem, "cliente_id", "CLI-DEFAULT")

        # Validaciones de presencia
        if not nombre or not apellidos or not email:
            return create_soap_fault(
                fault_code="soapenv:Client",
                fault_string="Datos del clasificador incompletos.",
                codigo_error="ERR_VALIDATION_MISSING_USER_DATA",
                mensaje_detalle="Los campos 'nombre', 'apellidos' y 'email' son estrictamente obligatorios.",
                campo_invalido="nombre/apellidos/email",
                http_status=400
            )

        if not concepto_id_str or not concepto_id_str.isdigit():
            return create_soap_fault(
                fault_code="soapenv:Client",
                fault_string="Identificador de concepto inválido.",
                codigo_error="ERR_VALIDATION_INVALID_CONCEPT_ID",
                mensaje_detalle="El campo 'concepto_id' debe ser un número entero positivo.",
                campo_invalido="concepto_id",
                http_status=400
            )

        concepto_id = int(concepto_id_str)

        if not libro_isbn:
            return create_soap_fault(
                fault_code="soapenv:Client",
                fault_string="ISBN del libro obligatorio.",
                codigo_error="ERR_VALIDATION_MISSING_ISBN",
                mensaje_detalle="El campo 'libro_isbn' es requerido para asociar la clasificación.",
                campo_invalido="libro_isbn",
                http_status=400
            )

        # Validación del modelo Cloud
        if modelo_cloud not in ALLOWED_CLOUD_MODELS:
            return create_soap_fault(
                fault_code="soapenv:Client",
                fault_string=f"Modelo Cloud '{modelo_cloud}' inválido.",
                codigo_error="ERR_VALIDATION_INVALID_CLOUD_MODEL",
                mensaje_detalle=f"El modelo debe ser uno de los permitidos por el contrato: {', '.join(sorted(ALLOWED_CLOUD_MODELS))}.",
                campo_invalido="modelo_cloud",
                http_status=400
            )

        # Registrar cliente servido
        self.db.record_client_request(cliente_tipo, cliente_id)

        # Registrar clasificación en la base de datos
        clasif_id = self.db.register_classification(
            nombre=nombre,
            apellidos=apellidos,
            email=email,
            concepto_id=concepto_id,
            libro_isbn=libro_isbn,
            modelo_cloud=modelo_cloud,
            cliente_tipo=cliente_tipo,
            cliente_id=cliente_id,
            ip_origen=client_ip
        )

        # Construir respuesta exitosa
        resp_elem = ET.Element(f"{{{TNS_NS}}}RegistrarClasificacionResponse")
        
        st = ET.SubElement(resp_elem, f"{{{TNS_NS}}}status")
        st.text = "SUCCESS"
        
        ms = ET.SubElement(resp_elem, f"{{{TNS_NS}}}mensaje")
        ms.text = f"Concepto {concepto_id} clasificado exitosamente como '{modelo_cloud}' por {email}."
        
        cid = ET.SubElement(resp_elem, f"{{{TNS_NS}}}clasificacion_id")
        cid.text = str(clasif_id)
        
        fr = ET.SubElement(resp_elem, f"{{{TNS_NS}}}fecha_registro")
        fr.text = datetime.datetime.now().isoformat()

        return create_soap_response(resp_elem), 200

    # ------------------------------------------------------------------------
    # Manejador: ObtenerProgresoUsuario
    # ------------------------------------------------------------------------
    def _handle_obtener_progreso_usuario(self, elem: ET.Element) -> Tuple[str, int]:
        email = get_child_text(elem, "email")
        if not email:
            return create_soap_fault(
                fault_code="soapenv:Client",
                fault_string="El campo 'email' es requerido.",
                codigo_error="ERR_VALIDATION_MISSING_EMAIL",
                mensaje_detalle="Debe proporcionar el correo electrónico del clasificador para calcular su progreso.",
                campo_invalido="email",
                http_status=400
            )

        prog = self.db.get_user_progress(email)

        resp_elem = ET.Element(f"{{{TNS_NS}}}ObtenerProgresoUsuarioResponse")
        
        em = ET.SubElement(resp_elem, f"{{{TNS_NS}}}email")
        em.text = prog['email']
        
        nc = ET.SubElement(resp_elem, f"{{{TNS_NS}}}nombre_completo")
        nc.text = prog['nombre_completo']
        
        tc = ET.SubElement(resp_elem, f"{{{TNS_NS}}}total_clasificados")
        tc.text = str(prog['total_clasificados'])
        
        tp = ET.SubElement(resp_elem, f"{{{TNS_NS}}}total_pendientes")
        tp.text = str(prog['total_pendientes'])
        
        pp = ET.SubElement(resp_elem, f"{{{TNS_NS}}}porcentaje_progreso")
        pp.text = f"{prog['porcentaje_progreso']:.2f}"

        return create_soap_response(resp_elem), 200

    # ------------------------------------------------------------------------
    # Manejador: ObtenerEstadisticasPorModelo (Protegida con WS-Security)
    # ------------------------------------------------------------------------
    def _handle_obtener_estadisticas_por_modelo(self, header_elem: Optional[ET.Element], elem: ET.Element) -> Tuple[str, int]:
        # 1. Validar autenticación WS-Security
        extract_and_validate_ws_security(header_elem)

        # 2. Consultar estadísticas
        stats = self.db.get_model_statistics()

        resp_elem = ET.Element(f"{{{TNS_NS}}}ObtenerEstadisticasPorModeloResponse")
        
        tiaas = ET.SubElement(resp_elem, f"{{{TNS_NS}}}total_iaas")
        tiaas.text = str(stats['total_iaas'])
        
        tpaas = ET.SubElement(resp_elem, f"{{{TNS_NS}}}total_paas")
        tpaas.text = str(stats['total_paas'])
        
        tsaas = ET.SubElement(resp_elem, f"{{{TNS_NS}}}total_saas")
        tsaas.text = str(stats['total_saas'])
        
        tfaas = ET.SubElement(resp_elem, f"{{{TNS_NS}}}total_faas")
        tfaas.text = str(stats['total_faas'])
        
        tgen = ET.SubElement(resp_elem, f"{{{TNS_NS}}}total_general")
        tgen.text = str(stats['total_general'])
        
        ts = ET.SubElement(resp_elem, f"{{{TNS_NS}}}timestamp_consulta")
        ts.text = stats['timestamp_consulta']

        return create_soap_response(resp_elem), 200
