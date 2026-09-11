-- =====================================================================
-- db/03_all_quieries_before_stored_procedures.sql
-- (nombre de archivo tal como lo pide el enunciado del ejercicio)
--
-- Consultas de referencia/verificación usadas ANTES de introducir los
-- stored procedures (04_stored_procedures.sql) y las vistas
-- (06_views.sql). Sirven para dos cosas:
--
--   1. Verificar que db/02_seed_30_per_table.sql cargó correctamente
--      (conteos por tabla, relaciones esperadas).
--   2. Dejar registrada la consulta "manual" que la aplicación Node.js
--      ejecuta hoy en apps/web-monolito/src/modules/libros/libros.model.js
--      (función listar()), como punto de comparación explícito contra
--      la vista equivalente que se crea después en 06_views.sql
--      (vista_catalogo_libros) — así se puede defender por qué la
--      vista es preferible (reutilización, un solo lugar para cambiar
--      la lógica de listado) sin perder de vista cómo se resolvía antes.
--
-- Todas las consultas son de solo lectura (SELECT): no modifican datos.
-- Ejecutar con: psql -U library_user -h localhost -d library_db -f db/03_all_quieries_before_stored_procedures.sql
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Conteo de filas por tabla (verificación del seed: ~30 por tabla
--    en los catálogos principales, según docs/TEST_PLAN.md).
-- ---------------------------------------------------------------------
SELECT 'usuarios' AS tabla, COUNT(*) FROM usuarios
UNION ALL SELECT 'formatos', COUNT(*) FROM formatos
UNION ALL SELECT 'generos', COUNT(*) FROM generos
UNION ALL SELECT 'autores', COUNT(*) FROM autores
UNION ALL SELECT 'conceptos', COUNT(*) FROM conceptos
UNION ALL SELECT 'libros', COUNT(*) FROM libros
UNION ALL SELECT 'libro_autor', COUNT(*) FROM libro_autor
UNION ALL SELECT 'libro_genero', COUNT(*) FROM libro_genero
UNION ALL SELECT 'libro_concepto', COUNT(*) FROM libro_concepto
UNION ALL SELECT 'imagenes', COUNT(*) FROM imagenes
ORDER BY tabla;

-- ---------------------------------------------------------------------
-- 2. Confirmar que existe exactamente un Administrador (RF-13).
-- ---------------------------------------------------------------------
SELECT id, nombre, email FROM usuarios WHERE rol = 'administrador';
SELECT COUNT(*) AS total_administradores FROM usuarios WHERE rol = 'administrador';
-- Se espera total_administradores = 1. Ver también la prueba negativa
-- TC-20 en docs/TEST_PLAN.md (intentar crear un segundo administrador).

-- ---------------------------------------------------------------------
-- 3. Consulta "manual" equivalente a libros.model.js:listar() — la
--    misma que ejecuta hoy la aplicación para /libros, ANTES de
--    reemplazarse por SELECT * FROM vista_catalogo_libros.
-- ---------------------------------------------------------------------
SELECT l.id, l.isbn, l.titulo, l.anio_publicacion, l.precio, l.stock,
       f.nombre AS formato,
       COALESCE(string_agg(DISTINCT a.nombre, ', '), '—') AS autores,
       (SELECT im.url_imagen FROM imagenes im WHERE im.libro_id = l.id
          ORDER BY im.es_principal DESC, im.orden ASC LIMIT 1) AS portada
  FROM libros l
  JOIN formatos f ON f.id = l.formato_id
  LEFT JOIN libro_autor la ON la.libro_id = l.id
  LEFT JOIN autores a ON a.id = la.autor_id
 GROUP BY l.id, f.nombre
 ORDER BY l.titulo ASC
 LIMIT 10;

-- ---------------------------------------------------------------------
-- 4. Verificar la relación libro-concepto del libro obligatorio de
--    Cloud Computing (RF-09a): debe traer los 10 conceptos definidos
--    en db/02_seed_30_per_table.sql.
-- ---------------------------------------------------------------------
SELECT c.termino, lc.definicion
  FROM libro_concepto lc
  JOIN conceptos c ON c.id = lc.concepto_id
  JOIN libros l ON l.id = lc.libro_id
 WHERE l.titulo = 'Cloud Computing: Fundamentos y Arquitecturas'
 ORDER BY c.termino;
-- Se esperan 10 filas: Bucket, FaaS, Hybrid Cloud, IaaS, Multicloud,
-- PaaS, Private Cloud, Public Cloud, SaaS, Serverless.

-- ---------------------------------------------------------------------
-- 5. Verificar que el mismo concepto puede tener definiciones distintas
--    en libros distintos (evidencia de la 4FN — ver docs/ENGINEERING_DECISIONS.md).
-- ---------------------------------------------------------------------
SELECT c.termino, l.titulo, lc.definicion
  FROM libro_concepto lc
  JOIN conceptos c ON c.id = lc.concepto_id
  JOIN libros l ON l.id = lc.libro_id
 WHERE c.termino = 'Recursión'
 ORDER BY l.titulo;
-- Se esperan al menos 2 filas ('Cien años de soledad' y 'Como agua
-- para chocolate' en el seed actual), cada una con una "definicion"
-- distinta para el mismo concepto.

-- ---------------------------------------------------------------------
-- 6. Verificar que ningún libro tiene más de una imagen "principal"
--    (confirma en vivo lo que exige ux_una_imagen_principal_por_libro).
-- ---------------------------------------------------------------------
SELECT libro_id, COUNT(*) AS imagenes_principales
  FROM imagenes
 WHERE es_principal = TRUE
 GROUP BY libro_id
HAVING COUNT(*) > 1;
-- Se espera 0 filas.

-- ---------------------------------------------------------------------
-- 7. Libros con más de un autor (evidencia de la relación M:N
--    libro-autor, no solo 1:N) — RF-08.
-- ---------------------------------------------------------------------
SELECT l.titulo, COUNT(*) AS num_autores
  FROM libro_autor la
  JOIN libros l ON l.id = la.libro_id
 GROUP BY l.titulo
HAVING COUNT(*) > 1
 ORDER BY l.titulo;
