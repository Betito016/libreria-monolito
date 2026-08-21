-- =====================================================================
-- library/db/esquema.sql
-- Sistema de administración de libros - Diseño de Base de Datos
-- Motor: PostgreSQL
-- =====================================================================
--
-- PARTE 1 - ANÁLISIS Y NORMALIZACIÓN
-- ---------------------------------------------------------------------
-- Dependencias funcionales (FD):
--   isbn -> titulo, anio_publicacion, precio, stock, formato_id
--
-- Dependencias multivaluadas (MVD) -> requieren tablas puente (4FN):
--   isbn ->> autor           (un libro, varios autores)
--   isbn ->> genero          (un libro, varios géneros)
--   isbn ->> imagen          (un libro, varias imágenes)
--   isbn ->> (concepto, definicion)
--       -> la definición depende del PAR (libro, concepto), no solo
--          del concepto, porque el mismo concepto puede tener
--          definiciones distintas según el libro. Por eso "concepto"
--          es catálogo aparte y "definicion" vive en la tabla puente.
--
-- Catálogos independientes: formato y genero (no dependen de nada más
-- que de su propio identificador).
--
-- Regla de negocio: a lo más UN usuario con rol 'administrador'.
-- Se resuelve con un índice único parcial (no es normalización, es
-- integridad de negocio).
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- Extensiones útiles (UUID como alternativa a serial si se requiere)
-- ---------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------
-- Tipos enumerados
-- ---------------------------------------------------------------------
CREATE TYPE rol_usuario AS ENUM ('administrador', 'cliente');

-- =====================================================================
-- TABLA: usuarios
-- Administra los usuarios registrados del sistema.
-- =====================================================================
CREATE TABLE usuarios (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre          VARCHAR(120)  NOT NULL,
    email           VARCHAR(150)  NOT NULL UNIQUE,
    password_hash   VARCHAR(255)  NOT NULL,
    rol             rol_usuario   NOT NULL DEFAULT 'cliente',
    activo          BOOLEAN       NOT NULL DEFAULT TRUE,
    fecha_registro  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    actualizado_en  TIMESTAMPTZ   NOT NULL DEFAULT now()
);

-- Regla de negocio: máximo un administrador en todo el sistema.
-- Un índice único parcial garantiza que a lo más UNA fila cumpla
-- rol = 'administrador'.
CREATE UNIQUE INDEX ux_un_solo_administrador
    ON usuarios ((rol))
    WHERE rol = 'administrador';

-- =====================================================================
-- CATÁLOGOS INDEPENDIENTES
-- =====================================================================

CREATE TABLE formatos (
    id      SERIAL PRIMARY KEY,
    nombre  VARCHAR(50) NOT NULL UNIQUE   -- ej: 'Tapa dura', 'Digital', 'Audiolibro'
);

CREATE TABLE generos (
    id      SERIAL PRIMARY KEY,
    nombre  VARCHAR(80) NOT NULL UNIQUE   -- ej: 'Ficción', 'Historia', 'Ciencia'
);

CREATE TABLE autores (
    id      SERIAL PRIMARY KEY,
    nombre  VARCHAR(150) NOT NULL,
    UNIQUE (nombre)
);

CREATE TABLE conceptos (
    id       SERIAL PRIMARY KEY,
    termino  VARCHAR(150) NOT NULL UNIQUE  -- el nombre del concepto, ej. 'Recursión'
);

-- =====================================================================
-- TABLA: libros
-- Contiene únicamente los atributos que dependen exclusivamente del ISBN.
-- =====================================================================
CREATE TABLE libros (
    id                SERIAL PRIMARY KEY,
    isbn              VARCHAR(20)     NOT NULL UNIQUE,
    titulo            VARCHAR(255)    NOT NULL,
    anio_publicacion  SMALLINT        CHECK (anio_publicacion > 0),
    precio            NUMERIC(10,2)   NOT NULL CHECK (precio >= 0),
    stock             INTEGER         NOT NULL DEFAULT 0 CHECK (stock >= 0),
    formato_id        INTEGER         NOT NULL REFERENCES formatos(id),
    creado_en         TIMESTAMPTZ     NOT NULL DEFAULT now(),
    actualizado_en    TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX ix_libros_titulo ON libros (titulo);

-- =====================================================================
-- RELACIONES M:N (resuelven las dependencias multivaluadas)
-- =====================================================================

-- Un libro puede tener varios autores; un autor puede escribir varios libros.
CREATE TABLE libro_autor (
    libro_id   INTEGER NOT NULL REFERENCES libros(id)  ON DELETE CASCADE,
    autor_id   INTEGER NOT NULL REFERENCES autores(id) ON DELETE RESTRICT,
    PRIMARY KEY (libro_id, autor_id)
);

-- Un libro puede pertenecer a varios géneros.
CREATE TABLE libro_genero (
    libro_id   INTEGER NOT NULL REFERENCES libros(id)   ON DELETE CASCADE,
    genero_id  INTEGER NOT NULL REFERENCES generos(id)  ON DELETE RESTRICT,
    PRIMARY KEY (libro_id, genero_id)
);

-- Un libro define varios conceptos, y la definición depende del PAR
-- (libro, concepto) -- por eso el atributo "definicion" vive aquí y no
-- en la tabla "conceptos".
CREATE TABLE libro_concepto (
    libro_id     INTEGER NOT NULL REFERENCES libros(id)     ON DELETE CASCADE,
    concepto_id  INTEGER NOT NULL REFERENCES conceptos(id)  ON DELETE RESTRICT,
    definicion   TEXT    NOT NULL,
    PRIMARY KEY (libro_id, concepto_id)
);

-- =====================================================================
-- IMÁGENES
-- Un libro puede tener varias imágenes (portada, contraportada, etc.)
-- =====================================================================
CREATE TABLE imagenes (
    id            SERIAL PRIMARY KEY,
    libro_id      INTEGER      NOT NULL REFERENCES libros(id) ON DELETE CASCADE,
    url_imagen    TEXT         NOT NULL,
    texto_alt     VARCHAR(255),
    es_principal  BOOLEAN      NOT NULL DEFAULT FALSE,
    orden         SMALLINT     NOT NULL DEFAULT 0,
    creado_en     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX ix_imagenes_libro_id ON imagenes (libro_id);

-- A lo más una imagen "principal" por libro.
CREATE UNIQUE INDEX ux_una_imagen_principal_por_libro
    ON imagenes (libro_id)
    WHERE es_principal = TRUE;

-- =====================================================================
-- TRIGGERS: mantener actualizado_en automáticamente
-- =====================================================================
CREATE OR REPLACE FUNCTION fn_actualizar_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.actualizado_en = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_usuarios_actualizado
    BEFORE UPDATE ON usuarios
    FOR EACH ROW EXECUTE FUNCTION fn_actualizar_timestamp();

CREATE TRIGGER trg_libros_actualizado
    BEFORE UPDATE ON libros
    FOR EACH ROW EXECUTE FUNCTION fn_actualizar_timestamp();

COMMIT;

-- =====================================================================
-- FIN esquema.sql
-- =====================================================================
