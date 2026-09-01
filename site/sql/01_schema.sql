-- =====================================================================
-- db/01_schema.sql
-- Sistema de administración de libros — Diseño de Base de Datos
-- Motor: PostgreSQL
-- =====================================================================
--
-- ANÁLISIS Y NORMALIZACIÓN (ver también docs/NORMALIZATION_4FN.xlsx,
-- pendiente de crear, y docs/DB_DESIGN_ER_4FN.png)
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
-- integridad de negocio) — ver ux_un_solo_administrador más abajo.
--
-- Ejecutar como superusuario (mismo rol que corrió 00_create_database.sql),
-- NO como library_user, porque este script crea el esquema y al final le
-- otorga privilegios a library_user (no puede otorgárselos a sí mismo):
--   sudo -i -u postgres psql -d library_db -f db/01_schema.sql
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- Extensiones útiles (pgcrypto: gen_random_uuid() para usuarios.id)
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
-- PRIVILEGIOS MÍNIMOS PARA library_user (rol de aplicación)
-- =====================================================================
-- library_user NO es owner de estas tablas (las crea el superusuario
-- que ejecuta este script); solo puede leer y escribir filas, nunca
-- alterar el esquema (no DDL) ni crear/borrar roles o bases de datos.
-- Ver docs/SECURITY_REVIEW.md, control 9, y docs/ENGINEERING_DECISIONS.md
-- decisión D-13.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO library_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO library_user;

COMMIT;

-- Los triggers (05_triggers.sql), stored procedures (04_stored_procedures.sql)
-- y vistas (06_views.sql) se cargan por separado, en ese orden relativo,
-- después de db/02_seed_30_per_table.sql y db/03_all_quieries_before_stored_procedures.sql
-- (ver docs/GCP_COMMANDS.md, pendiente, para el orden de carga completo).

-- =====================================================================
-- FIN 01_schema.sql
-- =====================================================================
