-- ============================================================================
-- PROYECTO: Módulo SOAP de Clasificación de Catálogo de Librería
-- ARCHIVO: web_report/sql/soap_module.sql
-- ============================================================================

CREATE TABLE IF NOT EXISTS clasificadores (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clasificaciones_cloud (
    id SERIAL PRIMARY KEY,
    concepto_id INTEGER NOT NULL REFERENCES concepts(id) ON DELETE RESTRICT,
    libro_isbn VARCHAR(20) NOT NULL REFERENCES books(isbn) ON DELETE RESTRICT,
    clasificador_id INTEGER NOT NULL REFERENCES clasificadores(id) ON DELETE RESTRICT,
    modelo_cloud VARCHAR(10) NOT NULL,
    fecha_clasificacion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ip_origen VARCHAR(45) DEFAULT '127.0.0.1',
    cliente_tipo VARCHAR(50) DEFAULT 'Desktop-GUI-Client',
    cliente_id VARCHAR(100) DEFAULT 'CLI-DEFAULT',
    CONSTRAINT chk_modelo_cloud CHECK (modelo_cloud IN ('IaaS', 'PaaS', 'SaaS', 'FaaS')),
    CONSTRAINT uq_clasificador_concepto UNIQUE (clasificador_id, concepto_id)
);

CREATE TABLE IF NOT EXISTS clientes_servidos (
    id SERIAL PRIMARY KEY,
    tipo_cliente VARCHAR(50) NOT NULL,
    identificador_cliente VARCHAR(100) NOT NULL UNIQUE,
    peticiones_atendidas INTEGER NOT NULL DEFAULT 1,
    primera_peticion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ultima_peticion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clasif_concepto ON clasificaciones_cloud(concepto_id);
CREATE INDEX IF NOT EXISTS idx_clasif_clasificador ON clasificaciones_cloud(clasificador_id);
CREATE INDEX IF NOT EXISTS idx_clasif_modelo ON clasificaciones_cloud(modelo_cloud);

CREATE OR REPLACE VIEW vista_conceptos_pendientes AS
SELECT 
    c.id AS concepto_id,
    c.name AS concepto_nombre,
    c.definition AS definicion,
    b.isbn AS libro_isbn,
    b.title AS libro_titulo,
    b.year AS libro_anio,
    COALESCE(cat.name, 'Sin Categoría') AS categoria_nombre
FROM concepts c
JOIN book_concepts bc ON c.id = bc.concept_id
JOIN books b ON bc.book_isbn = b.isbn
LEFT JOIN categories cat ON b.category_id = cat.id
ORDER BY c.id ASC;

CREATE OR REPLACE VIEW vista_estadisticas_modelos AS
SELECT 
    COUNT(*) FILTER (WHERE modelo_cloud = 'IaaS') AS total_iaas,
    COUNT(*) FILTER (WHERE modelo_cloud = 'PaaS') AS total_paas,
    COUNT(*) FILTER (WHERE modelo_cloud = 'SaaS') AS total_saas,
    COUNT(*) FILTER (WHERE modelo_cloud = 'FaaS') AS total_faas,
    COUNT(*) AS total_general
FROM clasificaciones_cloud;
