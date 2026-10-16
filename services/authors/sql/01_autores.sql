-- =====================================================================
-- services/authors/sql/01_autores.sql   (libreria_db)
-- Datos adicionales de los autores y permisos minimos del microservicio.
-- authors y book_authors ya existen (services/books/sql/01_catalogo_libros.sql).
-- El rol se crea aparte con contrasena generada (no se versiona):
--     CREATE ROLE authors_app_user WITH LOGIN PASSWORD '<password-generada>';
-- Idempotente.
-- =====================================================================
BEGIN;

ALTER TABLE authors ADD COLUMN IF NOT EXISTS nacionalidad VARCHAR(80);
ALTER TABLE authors ADD COLUMN IF NOT EXISTS biografia    TEXT;
ALTER TABLE authors ADD COLUMN IF NOT EXISTS creado_en    TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS ix_book_authors_author ON book_authors (author_id);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authors_app_user') THEN
        EXECUTE 'GRANT CONNECT ON DATABASE libreria_db TO authors_app_user';
        EXECUTE 'GRANT USAGE ON SCHEMA public TO authors_app_user';
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON authors, book_authors TO authors_app_user';
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE authors_id_seq TO authors_app_user';
        -- Solo lectura del catalogo: validar ISBN y mostrar los titulos.
        EXECUTE 'GRANT SELECT ON books TO authors_app_user';
    ELSE
        RAISE NOTICE 'El rol authors_app_user no existe: se omiten los GRANT.';
    END IF;
END $$;

COMMIT;
