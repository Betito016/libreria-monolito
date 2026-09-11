-- =====================================================================
-- db/06_views.sql
--
-- vista_catalogo_libros formaliza en la base de datos la consulta que
-- apps/web-monolito/src/modules/libros/libros.model.js (función
-- listar()) ya ejecutaba "a mano" con un JOIN + GROUP BY (ver la
-- versión de referencia en db/03_all_quieries_before_stored_procedures.sql,
-- sección 3). Convertirla en vista evita mantener la misma lógica de
-- agregación duplicada si en el futuro otra pantalla necesita el mismo
-- listado (p. ej. un reporte de inventario).
--
-- Solo se creó UNA vista, no varias: las demás consultas del sistema
-- (obtenerDetalle en libros.model.js) ya son JOINs simples y
-- parametrizados por un solo libro_id — envolverlas en vistas no
-- aportaría nada y sería complejidad sin beneficio (YAGNI).
--
-- Ejecutar con: psql -U library_user -h localhost -d library_db -f db/06_views.sql
-- =====================================================================

CREATE OR REPLACE VIEW vista_catalogo_libros AS
SELECT l.id, l.isbn, l.titulo, l.anio_publicacion, l.precio, l.stock,
       f.nombre AS formato,
       COALESCE(string_agg(DISTINCT a.nombre, ', '), '—') AS autores,
       (SELECT im.url_imagen FROM imagenes im WHERE im.libro_id = l.id
          ORDER BY im.es_principal DESC, im.orden ASC LIMIT 1) AS portada
  FROM libros l
  JOIN formatos f ON f.id = l.formato_id
  LEFT JOIN libro_autor la ON la.libro_id = l.id
  LEFT JOIN autores a ON a.id = la.autor_id
 GROUP BY l.id, f.nombre;

COMMENT ON VIEW vista_catalogo_libros IS
    'Listado de libros con formato, autores concatenados y portada. Usada '
    'por libros.model.js:listar() en vez de repetir el JOIN + GROUP UP '
    'en la aplicación.';

-- library_user ya tiene SELECT sobre esta vista de forma automática
-- porque Postgres hereda los privilegios GRANT SELECT ON ALL TABLES
-- otorgados en db/01_schema.sql solo a las tablas existentes en ese
-- momento, NO a objetos creados después — hay que otorgarlo explícito:
GRANT SELECT ON vista_catalogo_libros TO library_user;

-- ---------------------------------------------------------------------
-- Verificación manual por psql (Parte 4, punto 10):
--   SELECT titulo, autores, formato FROM vista_catalogo_libros
--    ORDER BY titulo LIMIT 5;
-- Debe devolver el mismo resultado que la consulta manual de
-- db/03_all_quieries_before_stored_procedures.sql, sección 3.
-- ---------------------------------------------------------------------
