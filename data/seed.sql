-- =====================================================================
-- data/seed.sql
-- Datos de prueba para la Librería en Línea (~15 registros por tabla).
-- Idempotente: se puede correr varias veces sin duplicar (usa
-- ON CONFLICT DO NOTHING sobre las columnas UNIQUE del esquema).
--
-- Uso:
--   psql -U library_user -h localhost -d library_db -f data/seed.sql
--
-- Requiere que data/db_scheme.sql ya haya sido aplicado.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- USUARIOS (15): 1 administrador (solo si no existe ya uno) + 14 clientes
-- Contraseña de TODOS los usuarios de prueba: Password123
-- Se hashea con pgcrypto (crypt/gen_salt('bf')), compatible con bcrypt
-- de Node (mismo formato $2a$/$2b$), así que puedes iniciar sesión con
-- estos usuarios desde la app tal cual.
-- ---------------------------------------------------------------------
INSERT INTO usuarios (nombre, email, password_hash, rol, activo)
SELECT 'Admin Biblioteca', 'admin@libreria.test',
       crypt('Password123', gen_salt('bf', 10)), 'administrador', true
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE rol = 'administrador')
ON CONFLICT (email) DO NOTHING;

INSERT INTO usuarios (nombre, email, password_hash, rol, activo) VALUES
('Ana Torres',       'ana.torres@correo.test',       crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Luis Hernández',   'luis.hernandez@correo.test',   crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('María López',      'maria.lopez@correo.test',      crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Carlos Ramírez',   'carlos.ramirez@correo.test',   crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Sofía Martínez',   'sofia.martinez@correo.test',   crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Diego Sánchez',    'diego.sanchez@correo.test',    crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Valeria Gómez',    'valeria.gomez@correo.test',    crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Javier Flores',    'javier.flores@correo.test',    crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Paola Reyes',      'paola.reyes@correo.test',      crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Ricardo Morales',  'ricardo.morales@correo.test',  crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Fernanda Cruz',    'fernanda.cruz@correo.test',    crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Andrés Ortiz',     'andres.ortiz@correo.test',     crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Camila Vargas',    'camila.vargas@correo.test',    crypt('Password123', gen_salt('bf', 10)), 'cliente', false),
('Jorge Castillo',   'jorge.castillo@correo.test',   crypt('Password123', gen_salt('bf', 10)), 'cliente', true)
ON CONFLICT (email) DO NOTHING;

-- ---------------------------------------------------------------------
-- FORMATOS (15) — catálogo independiente
-- ---------------------------------------------------------------------
INSERT INTO formatos (nombre) VALUES
('Tapa dura'), ('Tapa blanda'), ('Bolsillo'), ('Digital (PDF)'),
('Digital (EPUB)'), ('Audiolibro'), ('Edición ilustrada'),
('Edición de coleccionista'), ('Edición especial'), ('Cómic'),
('Fascículo'), ('Edición de lujo'), ('Rústica'), ('Pasta dura'),
('Digital (MOBI)')
ON CONFLICT (nombre) DO NOTHING;

-- ---------------------------------------------------------------------
-- GENEROS (15) — catálogo independiente
-- ---------------------------------------------------------------------
INSERT INTO generos (nombre) VALUES
('Ficción'), ('No ficción'), ('Ciencia ficción'), ('Fantasía'),
('Terror'), ('Misterio'), ('Romance'), ('Historia'), ('Biografía'),
('Poesía'), ('Autoayuda'), ('Ciencia'), ('Tecnología'), ('Filosofía'),
('Infantil')
ON CONFLICT (nombre) DO NOTHING;

-- ---------------------------------------------------------------------
-- AUTORES (15)
-- ---------------------------------------------------------------------
INSERT INTO autores (nombre) VALUES
('Gabriel García Márquez'), ('Isabel Allende'), ('Jorge Luis Borges'),
('Mario Vargas Llosa'), ('Julio Cortázar'), ('Pablo Neruda'),
('Octavio Paz'), ('Laura Esquivel'), ('Carlos Fuentes'),
('Elena Poniatowska'), ('Juan Rulfo'), ('Rosario Castellanos'),
('Sor Juana Inés de la Cruz'), ('Amado Nervo'), ('Ángeles Mastretta')
ON CONFLICT (nombre) DO NOTHING;

-- ---------------------------------------------------------------------
-- CONCEPTOS (15) — catálogo de términos
-- ---------------------------------------------------------------------
INSERT INTO conceptos (termino) VALUES
('Recursión'), ('Herencia'), ('Polimorfismo'), ('Normalización'),
('Índice'), ('Transacción ACID'), ('Patrón MVC'),
('Inyección de dependencias'), ('Complejidad algorítmica'),
('Árbol binario'), ('Tabla hash'), ('Programación funcional'),
('Concurrencia'), ('Encapsulamiento'), ('Clave foránea')
ON CONFLICT (termino) DO NOTHING;

-- ---------------------------------------------------------------------
-- LIBROS (15)
-- ---------------------------------------------------------------------
INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9780307474728', 'Cien años de soledad', 1967, 349.00, 12, id FROM formatos WHERE nombre = 'Tapa dura'
ON CONFLICT (isbn) DO NOTHING;

INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9780307387264', 'El amor en los tiempos del cólera', 1985, 329.00, 8, id FROM formatos WHERE nombre = 'Tapa blanda'
ON CONFLICT (isbn) DO NOTHING;

INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9788401337208', 'La casa de los espíritus', 1982, 299.00, 10, id FROM formatos WHERE nombre = 'Tapa blanda'
ON CONFLICT (isbn) DO NOTHING;

INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9789875666023', 'Ficciones', 1944, 259.00, 6, id FROM formatos WHERE nombre = 'Bolsillo'
ON CONFLICT (isbn) DO NOTHING;

INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9788432217684', 'La ciudad y los perros', 1963, 289.00, 9, id FROM formatos WHERE nombre = 'Tapa blanda'
ON CONFLICT (isbn) DO NOTHING;

INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9788437604572', 'Rayuela', 1963, 319.00, 5, id FROM formatos WHERE nombre = 'Edición especial'
ON CONFLICT (isbn) DO NOTHING;

INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9789561329935', 'Veinte poemas de amor y una canción desesperada', 1924, 199.00, 14, id FROM formatos WHERE nombre = 'Bolsillo'
ON CONFLICT (isbn) DO NOTHING;

INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9789681602654', 'El laberinto de la soledad', 1950, 279.00, 7, id FROM formatos WHERE nombre = 'Rústica'
ON CONFLICT (isbn) DO NOTHING;

INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9789685960874', 'Como agua para chocolate', 1989, 249.00, 11, id FROM formatos WHERE nombre = 'Tapa blanda'
ON CONFLICT (isbn) DO NOTHING;

INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9786073151594', 'La región más transparente', 1958, 309.00, 4, id FROM formatos WHERE nombre = 'Pasta dura'
ON CONFLICT (isbn) DO NOTHING;

INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9789681902259', 'La noche de Tlatelolco', 1971, 269.00, 6, id FROM formatos WHERE nombre = 'Tapa blanda'
ON CONFLICT (isbn) DO NOTHING;

INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9786071606973', 'Pedro Páramo', 1955, 229.00, 15, id FROM formatos WHERE nombre = 'Bolsillo'
ON CONFLICT (isbn) DO NOTHING;

INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9789684115234', 'Balún Canán', 1957, 259.00, 3, id FROM formatos WHERE nombre = 'Rústica'
ON CONFLICT (isbn) DO NOTHING;

INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9789700512345', 'Primero sueño', 1692, 189.00, 5, id FROM formatos WHERE nombre = 'Edición de coleccionista'
ON CONFLICT (isbn) DO NOTHING;

INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9789681909562', 'Arráncame la vida', 1985, 239.00, 8, id FROM formatos WHERE nombre = 'Tapa blanda'
ON CONFLICT (isbn) DO NOTHING;

INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9789684112233', 'Antología del cuento latinoamericano', 1998, 359.00, 2, id FROM formatos WHERE nombre = 'Edición de lujo'
ON CONFLICT (isbn) DO NOTHING;

-- ---------------------------------------------------------------------
-- LIBRO_AUTOR (M:N) — un autor por libro, salvo la antología (varios)
-- ---------------------------------------------------------------------
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Cien años de soledad' AND a.nombre = 'Gabriel García Márquez'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'El amor en los tiempos del cólera' AND a.nombre = 'Gabriel García Márquez'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'La casa de los espíritus' AND a.nombre = 'Isabel Allende'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Ficciones' AND a.nombre = 'Jorge Luis Borges'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'La ciudad y los perros' AND a.nombre = 'Mario Vargas Llosa'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Rayuela' AND a.nombre = 'Julio Cortázar'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Veinte poemas de amor y una canción desesperada' AND a.nombre = 'Pablo Neruda'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'El laberinto de la soledad' AND a.nombre = 'Octavio Paz'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Como agua para chocolate' AND a.nombre = 'Laura Esquivel'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'La región más transparente' AND a.nombre = 'Carlos Fuentes'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'La noche de Tlatelolco' AND a.nombre = 'Elena Poniatowska'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Pedro Páramo' AND a.nombre = 'Juan Rulfo'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Balún Canán' AND a.nombre = 'Rosario Castellanos'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Primero sueño' AND a.nombre = 'Sor Juana Inés de la Cruz'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Arráncame la vida' AND a.nombre = 'Ángeles Mastretta'
ON CONFLICT DO NOTHING;
-- La antología demuestra el lado "varios autores por libro" de la relación M:N
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Antología del cuento latinoamericano' AND a.nombre = 'Jorge Luis Borges'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Antología del cuento latinoamericano' AND a.nombre = 'Julio Cortázar'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Antología del cuento latinoamericano' AND a.nombre = 'Juan Rulfo'
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------
-- LIBRO_GENERO (M:N) — uno o dos géneros por libro
-- ---------------------------------------------------------------------
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Cien años de soledad' AND g.nombre = 'Ficción' ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Cien años de soledad' AND g.nombre = 'Fantasía' ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'El amor en los tiempos del cólera' AND g.nombre = 'Romance' ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'La casa de los espíritus' AND g.nombre = 'Fantasía' ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Ficciones' AND g.nombre = 'Ciencia ficción' ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'La ciudad y los perros' AND g.nombre = 'Ficción' ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Rayuela' AND g.nombre = 'Ficción' ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Veinte poemas de amor y una canción desesperada' AND g.nombre = 'Poesía' ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'El laberinto de la soledad' AND g.nombre = 'Filosofía' ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Como agua para chocolate' AND g.nombre = 'Romance' ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'La región más transparente' AND g.nombre = 'Ficción' ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'La noche de Tlatelolco' AND g.nombre = 'No ficción' ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'La noche de Tlatelolco' AND g.nombre = 'Historia' ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Pedro Páramo' AND g.nombre = 'Ficción' ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Balún Canán' AND g.nombre = 'Ficción' ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Primero sueño' AND g.nombre = 'Poesía' ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Arráncame la vida' AND g.nombre = 'Ficción' ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Antología del cuento latinoamericano' AND g.nombre = 'Ficción' ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------
-- LIBRO_CONCEPTO (M:N con atributo "definicion")
-- Datos de práctica: cada libro "define" 1-2 conceptos técnicos
-- (definición ligada al PAR libro-concepto, como pide el modelo).
-- ---------------------------------------------------------------------
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'Cien años de soledad' AND c.termino = 'Recursión'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'Ficciones' AND c.termino = 'Árbol binario'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'Rayuela' AND c.termino = 'Programación funcional'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'El laberinto de la soledad' AND c.termino = 'Encapsulamiento'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'La ciudad y los perros' AND c.termino = 'Herencia'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'Pedro Páramo' AND c.termino = 'Polimorfismo'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'La región más transparente' AND c.termino = 'Normalización'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'La noche de Tlatelolco' AND c.termino = 'Transacción ACID'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'Balún Canán' AND c.termino = 'Índice'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'Antología del cuento latinoamericano' AND c.termino = 'Patrón MVC'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Otra definición de ejemplo, distinta a la de otro libro para el mismo concepto.'
FROM libros l, conceptos c WHERE l.titulo = 'Como agua para chocolate' AND c.termino = 'Recursión'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'Veinte poemas de amor y una canción desesperada' AND c.termino = 'Clave foránea'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'Primero sueño' AND c.termino = 'Concurrencia'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'Arráncame la vida' AND c.termino = 'Inyección de dependencias'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'El amor en los tiempos del cólera' AND c.termino = 'Complejidad algorítmica'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'La casa de los espíritus' AND c.termino = 'Tabla hash'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;

-- ---------------------------------------------------------------------
-- IMAGENES (1:N) — se usan imágenes placeholder hospedadas externamente
-- (placehold.co) para que se vean correctamente en el navegador sin
-- necesidad de subir archivos reales a /uploads primero.
-- ---------------------------------------------------------------------
INSERT INTO imagenes (libro_id, url_imagen, texto_alt, es_principal)
SELECT l.id, 'https://placehold.co/300x450/1c3d5a/ffffff?text=' || replace(l.titulo, ' ', '+'), l.titulo, true
FROM libros l
WHERE NOT EXISTS (SELECT 1 FROM imagenes im WHERE im.libro_id = l.id);

COMMIT;
