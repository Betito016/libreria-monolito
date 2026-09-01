-- =====================================================================
-- db/05_triggers.sql
-- Triggers de mantenimiento automático (movidos aquí desde
-- db/01_schema.sql para seguir la organización de archivos que pide
-- el ejercicio).
--
-- No se agregó ningún trigger adicional "de relleno": la única regla
-- de negocio con defensa a nivel de base de datos que exige el
-- ejercicio (máximo un Administrador) ya está resuelta con el índice
-- único parcial ux_un_solo_administrador en db/01_schema.sql, que es
-- la herramienta correcta para esa restricción (ver
-- docs/ENGINEERING_DECISIONS.md, decisión D-06) — un trigger que
-- duplicara esa misma validación sería complejidad innecesaria sin
-- beneficio adicional.
--
-- Ejecutar con: psql -U library_user -h localhost -d library_db -f db/05_triggers.sql
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

-- ---------------------------------------------------------------------
-- Verificación manual por psql (Parte 4, punto 10):
--   UPDATE libros SET stock = stock WHERE titulo = 'Rayuela';
--   SELECT titulo, actualizado_en FROM libros WHERE titulo = 'Rayuela';
-- Se espera que actualizado_en cambie a la hora actual aunque el valor
-- de stock no haya cambiado (el trigger dispara en cualquier UPDATE).
-- ---------------------------------------------------------------------
