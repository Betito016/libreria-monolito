-- =====================================================================
-- db/04_stored_procedures.sql
--
-- Dos stored procedures que formalizan en la base de datos una
-- operación que hoy la aplicación resuelve con una transacción manual
-- en JavaScript (apps/web-monolito/src/modules/libros/libros.model.js,
-- funciones asignarAutores/asignarGeneros: BEGIN; DELETE; INSERT×N;
-- COMMIT). Moverla a un procedimiento almacenado tiene una ventaja
-- concreta: la atomicidad la garantiza el motor en una sola llamada
-- (CALL), sin depender de que el cliente Node abra/cierre la
-- transacción correctamente.
--
-- Nota deliberada (ver docs/ENGINEERING_DECISIONS.md, historial de
-- correcciones): estos procedimientos se dejan aquí, documentados y
-- listos para usarse, pero la aplicación Node.js TODAVÍA no los llama
-- — no hay una instancia PostgreSQL disponible en esta sesión para
-- probarlos en vivo, y cambiar una ruta que hoy funciona sin poder
-- verificarla es justo el tipo de riesgo en cascada que se quiere
-- evitar. El siguiente paso, una vez verificados con CALL directo vía
-- psql en la instancia real (ver docs/TEST_PLAN.md), es reemplazar el
-- cuerpo de asignarAutores/asignarGeneros en libros.model.js por un
-- solo client.query('CALL sp_asignar_autores_libro($1, $2)', [...]).
--
-- Ejecutar con: psql -U library_user -h localhost -d library_db -f db/04_stored_procedures.sql
-- =====================================================================

CREATE OR REPLACE PROCEDURE sp_asignar_autores_libro(
    p_libro_id  INTEGER,
    p_autor_ids INTEGER[]
)
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM libro_autor WHERE libro_id = p_libro_id;

    IF p_autor_ids IS NOT NULL AND array_length(p_autor_ids, 1) > 0 THEN
        INSERT INTO libro_autor (libro_id, autor_id)
        SELECT p_libro_id, autor_id
          FROM unnest(p_autor_ids) AS autor_id;
    END IF;
END;
$$;

COMMENT ON PROCEDURE sp_asignar_autores_libro(INTEGER, INTEGER[]) IS
    'Reemplaza por completo el conjunto de autores de un libro: borra las '
    'filas actuales de libro_autor para ese libro_id y vuelve a insertar '
    'las recibidas en p_autor_ids. Atómico (procedimiento completo o nada).';

CREATE OR REPLACE PROCEDURE sp_asignar_generos_libro(
    p_libro_id   INTEGER,
    p_genero_ids INTEGER[]
)
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM libro_genero WHERE libro_id = p_libro_id;

    IF p_genero_ids IS NOT NULL AND array_length(p_genero_ids, 1) > 0 THEN
        INSERT INTO libro_genero (libro_id, genero_id)
        SELECT p_libro_id, genero_id
          FROM unnest(p_genero_ids) AS genero_id;
    END IF;
END;
$$;

COMMENT ON PROCEDURE sp_asignar_generos_libro(INTEGER, INTEGER[]) IS
    'Reemplaza por completo el conjunto de géneros de un libro: borra las '
    'filas actuales de libro_genero para ese libro_id y vuelve a insertar '
    'las recibidas en p_genero_ids. Atómico (procedimiento completo o nada).';

-- ---------------------------------------------------------------------
-- Ejemplo de uso manual para verificar por psql (Parte 4, punto 10).
--
-- IMPORTANTE: CALL no acepta subconsultas directamente como argumento
-- ("no se puede usar una subconsulta en un argumento a CALL" — error
-- real visto al probar esto contra una instancia local). Resuelve los
-- IDs primero con \gset:
--
--   SELECT id AS libro_id FROM libros WHERE titulo = 'Rayuela' \gset
--   SELECT id AS autor_id FROM autores WHERE nombre = 'Julio Cortázar' \gset
--   CALL sp_asignar_autores_libro(:libro_id, ARRAY[:autor_id]);
--   SELECT * FROM libro_autor WHERE libro_id = :libro_id;
--
-- Se espera exactamente una fila con el autor_id de Julio Cortázar.
-- (Esta restricción de CALL no afecta a la aplicación Node: ahí los
-- valores ya llegan resueltos como parámetros de pg, no como subconsultas.)
-- ---------------------------------------------------------------------
