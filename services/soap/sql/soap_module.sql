-- ============================================================================
-- PROYECTO: Módulo SOAP de Clasificación de Catálogo de Librería
-- ARCHIVO: sql/soap_module.sql
-- DESCRIPCIÓN: Esquema de persistencia del módulo SOAP, restricciones, índices
--              y políticas de mínimo privilegio sobre PostgreSQL.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. TABLAS PROPIAS DEL MÓDULO SOAP
-- ----------------------------------------------------------------------------

-- Tabla: clasificadores
-- Registra los usuarios del cliente SOAP que realizan clasificaciones.
-- Nota: Es independiente de la tabla 'users' del monolito.
CREATE TABLE IF NOT EXISTS clasificadores (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Comentarios de documentación
COMMENT ON TABLE clasificadores IS 'Usuarios operadores del módulo SOAP que clasifican conceptos.';
COMMENT ON COLUMN clasificadores.email IS 'Identificador único del clasificador (evita duplicar perfiles).';

-- Tabla: clasificaciones_cloud
-- Registra la asignación de modelos Cloud (IaaS, PaaS, SaaS, FaaS) a conceptos de libros.
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
    
    -- Restricción de modelos Cloud permitidos
    CONSTRAINT chk_modelo_cloud CHECK (modelo_cloud IN ('IaaS', 'PaaS', 'SaaS', 'FaaS')),
    
    -- Restricción técnica fundamental: Un clasificador no puede clasificar dos veces el mismo concepto
    CONSTRAINT uq_clasificador_concepto UNIQUE (clasificador_id, concepto_id)
);

COMMENT ON TABLE clasificaciones_cloud IS 'Registro transaccional de clasificaciones cloud con auditoría.';
COMMENT ON CONSTRAINT uq_clasificador_concepto ON clasificaciones_cloud IS 'Impide clasificaciones duplicadas por el mismo usuario.';

-- Tabla: clientes_servidos
-- Registra y contabiliza las peticiones atendidas por tipo de cliente de escritorio.
CREATE TABLE IF NOT EXISTS clientes_servidos (
    id SERIAL PRIMARY KEY,
    tipo_cliente VARCHAR(50) NOT NULL,
    identificador_cliente VARCHAR(100) NOT NULL UNIQUE,
    peticiones_atendidas INTEGER NOT NULL DEFAULT 1,
    primera_peticion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ultima_peticion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE clientes_servidos IS 'Métricas de consumo y auditoría de clientes SOAP conectados.';

-- ----------------------------------------------------------------------------
-- 2. ÍNDICES PARA RENDIMIENTO Y CONSULTAS
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_clasif_concepto ON clasificaciones_cloud(concepto_id);
CREATE INDEX IF NOT EXISTS idx_clasif_clasificador ON clasificaciones_cloud(clasificador_id);
CREATE INDEX IF NOT EXISTS idx_clasif_modelo ON clasificaciones_cloud(modelo_cloud);
CREATE INDEX IF NOT EXISTS idx_clasif_fecha ON clasificaciones_cloud(fecha_clasificacion);

-- ----------------------------------------------------------------------------
-- 3. VISTAS PARA ACCESO CONTROLADO Y DESACOPLADO
-- ----------------------------------------------------------------------------

-- Vista para consultar conceptos pendientes con metadatos de libro y categoría
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

-- Vista para estadísticas globales por modelo de servicio
CREATE OR REPLACE VIEW vista_estadisticas_modelos AS
SELECT 
    COUNT(*) FILTER (WHERE modelo_cloud = 'IaaS') AS total_iaas,
    COUNT(*) FILTER (WHERE modelo_cloud = 'PaaS') AS total_paas,
    COUNT(*) FILTER (WHERE modelo_cloud = 'SaaS') AS total_saas,
    COUNT(*) FILTER (WHERE modelo_cloud = 'FaaS') AS total_faas,
    COUNT(*) AS total_general
FROM clasificaciones_cloud;

-- ----------------------------------------------------------------------------
-- 4. POLÍTICAS DE MÍNIMO PRIVILEGIO (SEGURIDAD POSTGRESQL)
-- ----------------------------------------------------------------------------
-- Crear rol/usuario exclusivo para el módulo SOAP si no existe:
-- DO $$
-- BEGIN
--   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'soap_app_user') THEN
--     CREATE ROLE soap_app_user WITH LOGIN PASSWORD 'soap_secure_pass_2026';
--   END IF;
-- END
-- $$;

-- Permisos de SOLO LECTURA sobre las tablas del monolito:
-- GRANT SELECT ON books, concepts, book_concepts, categories TO soap_app_user;

-- Permisos de LECTURA y ESCRITURA sobre las tablas del módulo SOAP:
-- GRANT SELECT, INSERT, UPDATE ON clasificadores, clasificaciones_cloud, clientes_servidos TO soap_app_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO soap_app_user;

-- NUNCA otorgar permisos de SUPERUSER, DROP TABLE o ALTER TABLE a soap_app_user.
