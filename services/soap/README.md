# Módulo SOAP de Clasificación de Librería (2026)

Servicio SOAP 1.1 independiente desarrollado en Python (Flask + psycopg2) que se integra con la base de datos PostgreSQL de la librería sin modificar el código ni el esquema existente del monolito Node.js.

## 🚀 Arquitectura y Características

- **Servidor SOAP Manual:** Construcción y análisis manual de sobres XML con `xml.etree.ElementTree` (sin frameworks que oculten el Envelope).
- **Contrato Estricto:** Publicación de WSDL con tipos XSD en `/soap?wsdl`.
- **Seguridad WS-Security:** Autenticación `UsernameToken` en operaciones sensibles (`ObtenerEstadisticasPorModelo`).
- **Control Robusto de SOAP Fault:** Detección de clasificaciones duplicadas (HTTP 409), modelos inválidos, conceptos inexistentes y XMLs mal formados.
- **Cliente de Escritorio GUI:** Interfaz interactiva construida en Tkinter para clasificar en tiempo real.
- **Interoperabilidad:** Verificada con cliente WSDL generado (`zeep`).

---

## 📂 Estructura del Proyecto

```
library_soap_service/
├── app.py                     # Servidor Flask y endpoints /soap y /soap?wsdl
├── requirements.txt           # Dependencias de Python
├── .env.example               # Parámetros y credenciales de entorno
├── config/
│   └── config.py              # Carga de configuración
├── db/
│   └── database.py            # Capa de persistencia con psycopg2 y fallback SQLite
├── soap/
│   ├── envelope.py            # Parser y constructor manual de XML SOAP 1.1
│   ├── faults.py              # Generador de SOAP Fault estructurados
│   ├── security.py            # Validador de encabezados WS-Security
│   └── service.py             # Lógica de despacho de operaciones
├── wsdl/
│   └── library-classifier.wsdl # Contrato WSDL oficial
├── sql/
│   ├── soap_module.sql        # Esquema propio, vistas y permisos de mínimo privilegio
│   └── seed_monolith.sql      # Datos base del monolito extraídos de library.xml
├── client/
│   └── desktop_classifier.py  # Aplicación de escritorio GUI para el clasificador
├── tests/
│   ├── test_soap_suite.py     # Pruebas automatizadas positivas y negativas
│   ├── client_zeep_interop.py # Cliente de interoperabilidad WSDL
│   └── soap_metrics_benchmark.py # Benchmark de overhead y métricas LOC
└── web_report/                # Reporte técnico completo navegable para entrega
    ├── index.html
    ├── css/style.css
    ├── js/app.js
    ├── wsdl/
    ├── sql/
    └── descargas/
```

---

## 🛠️ Instalación y Ejecución

### 1. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 2. Iniciar el Servidor SOAP
```bash
python app.py
```
- Endpoint SOAP: `POST http://localhost:5000/soap`
- Contrato WSDL: `GET http://localhost:5000/soap?wsdl`

### 3. Ejecutar Pruebas Automatizadas
```bash
python -m unittest tests/test_soap_suite.py
```

### 4. Ejecutar Cliente de Escritorio
```bash
python client/desktop_classifier.py
```

### 5. Ejecutar Prueba de Interoperabilidad
```bash
python tests/client_zeep_interop.py
```

### 6. Ejecutar Benchmark de Métricas
```bash
python tests/soap_metrics_benchmark.py
```
