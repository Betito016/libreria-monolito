-- =====================================================================
-- db/02_seed_30_per_table.sql
-- Datos sintéticos (~30 registros por tabla) para probar la solución.
-- Idempotente: usa ON CONFLICT DO NOTHING sobre las columnas UNIQUE del
-- esquema, por lo que se puede volver a ejecutar sin duplicar filas.
--
-- Requiere que db/01_schema.sql ya haya sido aplicado.
-- Uso: psql -U library_user -h localhost -d library_db -f db/02_seed_30_per_table.sql
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- USUARIOS (30): 1 administrador (solo si no existe ya uno) + 29 clientes
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
('Ana Torres', 'ana.torres@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Luis Hernández', 'luis.hernandez@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('María López', 'maria.lopez@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Carlos Ramírez', 'carlos.ramirez@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Sofía Martínez', 'sofia.martinez@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Diego Sánchez', 'diego.sanchez@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Valeria Gómez', 'valeria.gomez@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Javier Flores', 'javier.flores@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Paola Reyes', 'paola.reyes@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Ricardo Morales', 'ricardo.morales@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Fernanda Cruz', 'fernanda.cruz@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Andrés Ortiz', 'andres.ortiz@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Camila Vargas', 'camila.vargas@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', false),
('Jorge Castillo', 'jorge.castillo@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Renata Salas', 'renata.salas@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Emilio Peña', 'emilio.pena@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Daniela Ríos', 'daniela.rios@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Iván Cabrera', 'ivan.cabrera@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Ximena Duarte', 'ximena.duarte@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Héctor Nava', 'hector.nava@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Lucía Beltrán', 'lucia.beltran@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Rodrigo Espino', 'rodrigo.espino@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Natalia Vega', 'natalia.vega@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Tomás Aguilar', 'tomas.aguilar@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', false),
('Mariana Solís', 'mariana.solis@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Gustavo Lara', 'gustavo.lara@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Regina Prado', 'regina.prado@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Álvaro Medina', 'alvaro.medina@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true),
('Isabela Cortés', 'isabela.cortes@correo.test', crypt('Password123', gen_salt('bf', 10)), 'cliente', true)
ON CONFLICT (email) DO NOTHING;

-- ---------------------------------------------------------------------
-- FORMATOS (30) — catálogo independiente
-- ---------------------------------------------------------------------
INSERT INTO formatos (nombre) VALUES
('Tapa dura'), ('Tapa blanda'), ('Bolsillo'), ('Digital (PDF)'), ('Digital (EPUB)'), ('Digital (MOBI)'), ('Audiolibro'), ('Edición ilustrada'), ('Edición de coleccionista'), ('Edición especial'), ('Cómic'), ('Fascículo'), ('Edición de lujo'), ('Rústica'), ('Pasta dura'), ('Edición de bolsillo grande'), ('Letra grande'), ('Edición bilingüe'), ('Edición conmemorativa'), ('Edición universitaria'), ('Edición escolar'), ('Caja coleccionable'), ('Edición firmada'), ('Edición limitada'), ('Edición revisada'), ('Edición anotada'), ('Edición facsimilar'), ('Cuadernillo'), ('Edición digital interactiva'), ('Audiolibro dramatizado')
ON CONFLICT (nombre) DO NOTHING;

-- ---------------------------------------------------------------------
-- GENEROS (30) — catálogo independiente
-- ---------------------------------------------------------------------
INSERT INTO generos (nombre) VALUES
('Ficción'), ('No ficción'), ('Ciencia ficción'), ('Fantasía'), ('Terror'), ('Misterio'), ('Romance'), ('Historia'), ('Biografía'), ('Poesía'), ('Autoayuda'), ('Ciencia'), ('Tecnología'), ('Filosofía'), ('Infantil'), ('Juvenil'), ('Aventura'), ('Drama'), ('Comedia'), ('Policíaco'), ('Distopía'), ('Realismo mágico'), ('Ensayo'), ('Política'), ('Economía'), ('Psicología'), ('Arte'), ('Viajes'), ('Gastronomía'), ('Religión')
ON CONFLICT (nombre) DO NOTHING;

-- ---------------------------------------------------------------------
-- AUTORES (30)
-- ---------------------------------------------------------------------
INSERT INTO autores (nombre) VALUES
('Gabriel García Márquez'), ('Isabel Allende'), ('Jorge Luis Borges'), ('Mario Vargas Llosa'), ('Julio Cortázar'), ('Pablo Neruda'), ('Octavio Paz'), ('Laura Esquivel'), ('Carlos Fuentes'), ('Elena Poniatowska'), ('Juan Rulfo'), ('Rosario Castellanos'), ('Sor Juana Inés de la Cruz'), ('Amado Nervo'), ('Ángeles Mastretta'), ('Alejo Carpentier'), ('Miguel Ángel Asturias'), ('Ernesto Sabato'), ('Roberto Bolaño'), ('Gabriela Mistral'), ('José Martí'), ('Rubén Darío'), ('Horacio Quiroga'), ('Juan José Arreola'), ('Elena Garro'), ('Rosario Ferré'), ('Guillermo Cabrera Infante'), ('Alfonsina Storni'), ('César Vallejo'), ('Equipo de Cómputo en la Nube')
ON CONFLICT (nombre) DO NOTHING;

-- ---------------------------------------------------------------------
-- CONCEPTOS (30) — catálogo de términos. Incluye los 10
-- conceptos de Cloud Computing exigidos por el ejercicio (RF-09a).
-- ---------------------------------------------------------------------
INSERT INTO conceptos (termino) VALUES
('Recursión'), ('Herencia'), ('Polimorfismo'), ('Normalización'), ('Índice'), ('Transacción ACID'), ('Patrón MVC'), ('Inyección de dependencias'), ('Complejidad algorítmica'), ('Árbol binario'), ('Tabla hash'), ('Programación funcional'), ('Concurrencia'), ('Encapsulamiento'), ('Clave foránea'), ('IaaS'), ('PaaS'), ('SaaS'), ('FaaS'), ('Bucket'), ('Public Cloud'), ('Private Cloud'), ('Hybrid Cloud'), ('Multicloud'), ('Serverless'), ('Contenedor (Docker)'), ('Balanceo de carga'), ('Caché'), ('API REST'), ('Escalabilidad horizontal')
ON CONFLICT (termino) DO NOTHING;

-- ---------------------------------------------------------------------
-- LIBROS (32)
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
INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9780134685991', 'Cloud Computing: Fundamentos y Arquitecturas', 2021, 459.00, 20, id FROM formatos WHERE nombre = 'Digital (PDF)'
ON CONFLICT (isbn) DO NOTHING;
INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9781492078005', 'Estructuras de Datos y Algoritmos', 2019, 389.00, 18, id FROM formatos WHERE nombre = 'Tapa blanda'
ON CONFLICT (isbn) DO NOTHING;
INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9781492045711', 'Bases de Datos Avanzadas', 2020, 419.00, 16, id FROM formatos WHERE nombre = 'Digital (EPUB)'
ON CONFLICT (isbn) DO NOTHING;
INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9781098106916', 'Ingeniería de Software Moderna', 2022, 439.00, 14, id FROM formatos WHERE nombre = 'Tapa dura'
ON CONFLICT (isbn) DO NOTHING;
INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9781449319354', 'Introducción a las Redes', 2018, 349.00, 10, id FROM formatos WHERE nombre = 'Rústica'
ON CONFLICT (isbn) DO NOTHING;
INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9781491950357', 'Sistemas Operativos Concurrentes', 2017, 369.00, 9, id FROM formatos WHERE nombre = 'Pasta dura'
ON CONFLICT (isbn) DO NOTHING;
INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9781492032649', 'Inteligencia Artificial Aplicada', 2021, 479.00, 12, id FROM formatos WHERE nombre = 'Edición ilustrada'
ON CONFLICT (isbn) DO NOTHING;
INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9781098127249', 'Ciberseguridad Práctica', 2022, 399.00, 13, id FROM formatos WHERE nombre = 'Digital (PDF)'
ON CONFLICT (isbn) DO NOTHING;
INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9781492077893', 'Arquitectura de Microservicios', 2020, 449.00, 11, id FROM formatos WHERE nombre = 'Tapa blanda'
ON CONFLICT (isbn) DO NOTHING;
INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9781492076520', 'DevOps en la Práctica', 2021, 409.00, 15, id FROM formatos WHERE nombre = 'Digital (MOBI)'
ON CONFLICT (isbn) DO NOTHING;
INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9781492032663', 'Machine Learning desde Cero', 2023, 459.00, 17, id FROM formatos WHERE nombre = 'Edición especial'
ON CONFLICT (isbn) DO NOTHING;
INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9788437601885', 'El reino de este mundo', 1949, 269.00, 6, id FROM formatos WHERE nombre = 'Bolsillo'
ON CONFLICT (isbn) DO NOTHING;
INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9788437601557', 'Hombres de maíz', 1949, 279.00, 5, id FROM formatos WHERE nombre = 'Tapa blanda'
ON CONFLICT (isbn) DO NOTHING;
INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9788432217455', 'El túnel', 1948, 229.00, 10, id FROM formatos WHERE nombre = 'Bolsillo'
ON CONFLICT (isbn) DO NOTHING;
INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9788433978117', 'Los detectives salvajes', 1998, 349.00, 7, id FROM formatos WHERE nombre = 'Tapa blanda'
ON CONFLICT (isbn) DO NOTHING;
INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
SELECT '9789561316638', 'Desolación', 1922, 209.00, 8, id FROM formatos WHERE nombre = 'Rústica'
ON CONFLICT (isbn) DO NOTHING;

-- ---------------------------------------------------------------------
-- LIBRO_AUTOR (M:N)
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
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Antología del cuento latinoamericano' AND a.nombre = 'Jorge Luis Borges'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Antología del cuento latinoamericano' AND a.nombre = 'Julio Cortázar'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Antología del cuento latinoamericano' AND a.nombre = 'Juan Rulfo'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Cloud Computing: Fundamentos y Arquitecturas' AND a.nombre = 'Equipo de Cómputo en la Nube'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Estructuras de Datos y Algoritmos' AND a.nombre = 'Equipo de Cómputo en la Nube'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Bases de Datos Avanzadas' AND a.nombre = 'Equipo de Cómputo en la Nube'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Ingeniería de Software Moderna' AND a.nombre = 'Equipo de Cómputo en la Nube'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Introducción a las Redes' AND a.nombre = 'Equipo de Cómputo en la Nube'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Sistemas Operativos Concurrentes' AND a.nombre = 'Equipo de Cómputo en la Nube'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Inteligencia Artificial Aplicada' AND a.nombre = 'Equipo de Cómputo en la Nube'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Ciberseguridad Práctica' AND a.nombre = 'Equipo de Cómputo en la Nube'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Arquitectura de Microservicios' AND a.nombre = 'Equipo de Cómputo en la Nube'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'DevOps en la Práctica' AND a.nombre = 'Equipo de Cómputo en la Nube'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Machine Learning desde Cero' AND a.nombre = 'Equipo de Cómputo en la Nube'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'El reino de este mundo' AND a.nombre = 'Alejo Carpentier'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Hombres de maíz' AND a.nombre = 'Miguel Ángel Asturias'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'El túnel' AND a.nombre = 'Ernesto Sabato'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Los detectives salvajes' AND a.nombre = 'Roberto Bolaño'
ON CONFLICT DO NOTHING;
INSERT INTO libro_autor (libro_id, autor_id)
SELECT l.id, a.id FROM libros l, autores a WHERE l.titulo = 'Desolación' AND a.nombre = 'Gabriela Mistral'
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------
-- LIBRO_GENERO (M:N)
-- ---------------------------------------------------------------------
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Cien años de soledad' AND g.nombre = 'Ficción'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Cien años de soledad' AND g.nombre = 'Fantasía'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'El amor en los tiempos del cólera' AND g.nombre = 'Romance'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'La casa de los espíritus' AND g.nombre = 'Fantasía'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Ficciones' AND g.nombre = 'Ciencia ficción'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'La ciudad y los perros' AND g.nombre = 'Ficción'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Rayuela' AND g.nombre = 'Ficción'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Veinte poemas de amor y una canción desesperada' AND g.nombre = 'Poesía'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'El laberinto de la soledad' AND g.nombre = 'Filosofía'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Como agua para chocolate' AND g.nombre = 'Romance'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'La región más transparente' AND g.nombre = 'Ficción'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'La noche de Tlatelolco' AND g.nombre = 'No ficción'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'La noche de Tlatelolco' AND g.nombre = 'Historia'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Pedro Páramo' AND g.nombre = 'Ficción'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Balún Canán' AND g.nombre = 'Ficción'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Primero sueño' AND g.nombre = 'Poesía'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Arráncame la vida' AND g.nombre = 'Ficción'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Antología del cuento latinoamericano' AND g.nombre = 'Ficción'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Cloud Computing: Fundamentos y Arquitecturas' AND g.nombre = 'Tecnología'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Cloud Computing: Fundamentos y Arquitecturas' AND g.nombre = 'Ciencia'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Estructuras de Datos y Algoritmos' AND g.nombre = 'Tecnología'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Estructuras de Datos y Algoritmos' AND g.nombre = 'Ciencia'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Bases de Datos Avanzadas' AND g.nombre = 'Tecnología'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Bases de Datos Avanzadas' AND g.nombre = 'Ciencia'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Ingeniería de Software Moderna' AND g.nombre = 'Tecnología'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Introducción a las Redes' AND g.nombre = 'Tecnología'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Introducción a las Redes' AND g.nombre = 'Ciencia'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Sistemas Operativos Concurrentes' AND g.nombre = 'Tecnología'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Sistemas Operativos Concurrentes' AND g.nombre = 'Ciencia'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Inteligencia Artificial Aplicada' AND g.nombre = 'Tecnología'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Inteligencia Artificial Aplicada' AND g.nombre = 'Ciencia'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Ciberseguridad Práctica' AND g.nombre = 'Tecnología'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Arquitectura de Microservicios' AND g.nombre = 'Tecnología'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'DevOps en la Práctica' AND g.nombre = 'Tecnología'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Machine Learning desde Cero' AND g.nombre = 'Tecnología'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Machine Learning desde Cero' AND g.nombre = 'Ciencia'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'El reino de este mundo' AND g.nombre = 'Ficción'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'El reino de este mundo' AND g.nombre = 'Historia'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Hombres de maíz' AND g.nombre = 'Realismo mágico'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'El túnel' AND g.nombre = 'Ficción'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'El túnel' AND g.nombre = 'Drama'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Los detectives salvajes' AND g.nombre = 'Ficción'
ON CONFLICT DO NOTHING;
INSERT INTO libro_genero (libro_id, genero_id)
SELECT l.id, g.id FROM libros l, generos g WHERE l.titulo = 'Desolación' AND g.nombre = 'Poesía'
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------
-- LIBRO_CONCEPTO (M:N con atributo "definicion"). El libro de Cloud
-- Computing trae los 10 conceptos obligatorios del ejercicio (RF-09a).
-- ---------------------------------------------------------------------
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'Cien años de soledad' AND c.termino = 'Recursión'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'El amor en los tiempos del cólera' AND c.termino = 'Complejidad algorítmica'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'La casa de los espíritus' AND c.termino = 'Tabla hash'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'Ficciones' AND c.termino = 'Árbol binario'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'La ciudad y los perros' AND c.termino = 'Herencia'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'Rayuela' AND c.termino = 'Programación funcional'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'Veinte poemas de amor y una canción desesperada' AND c.termino = 'Clave foránea'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'El laberinto de la soledad' AND c.termino = 'Encapsulamiento'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Otra definición de ejemplo, distinta a la de otro libro para el mismo concepto.'
FROM libros l, conceptos c WHERE l.titulo = 'Como agua para chocolate' AND c.termino = 'Recursión'
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
FROM libros l, conceptos c WHERE l.titulo = 'Pedro Páramo' AND c.termino = 'Polimorfismo'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Ejemplo de definición asociada a este libro para fines de práctica del CRUD.'
FROM libros l, conceptos c WHERE l.titulo = 'Balún Canán' AND c.termino = 'Índice'
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
FROM libros l, conceptos c WHERE l.titulo = 'Antología del cuento latinoamericano' AND c.termino = 'Patrón MVC'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Modelo de servicio en la nube donde el proveedor entrega infraestructura virtualizada (cómputo, almacenamiento, red) y el cliente administra sistema operativo y aplicaciones.'
FROM libros l, conceptos c WHERE l.titulo = 'Cloud Computing: Fundamentos y Arquitecturas' AND c.termino = 'IaaS'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Modelo en el que el proveedor entrega una plataforma completa (runtime, herramientas, middleware) para que el desarrollador despliegue aplicaciones sin gestionar la infraestructura subyacente.'
FROM libros l, conceptos c WHERE l.titulo = 'Cloud Computing: Fundamentos y Arquitecturas' AND c.termino = 'PaaS'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Modelo en el que el proveedor entrega una aplicación completa lista para usar a través de internet, sin que el cliente administre infraestructura ni plataforma.'
FROM libros l, conceptos c WHERE l.titulo = 'Cloud Computing: Fundamentos y Arquitecturas' AND c.termino = 'SaaS'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Modelo serverless donde el desarrollador despliega funciones individuales que se ejecutan bajo demanda, facturadas por invocación/tiempo de ejecución.'
FROM libros l, conceptos c WHERE l.titulo = 'Cloud Computing: Fundamentos y Arquitecturas' AND c.termino = 'FaaS'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Contenedor lógico de almacenamiento de objetos (archivos) en la nube, identificado por un nombre único dentro del proveedor.'
FROM libros l, conceptos c WHERE l.titulo = 'Cloud Computing: Fundamentos y Arquitecturas' AND c.termino = 'Bucket'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Infraestructura de nube operada por un proveedor externo y compartida entre múltiples clientes (multi-tenant) a través de internet.'
FROM libros l, conceptos c WHERE l.titulo = 'Cloud Computing: Fundamentos y Arquitecturas' AND c.termino = 'Public Cloud'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Infraestructura de nube dedicada a una sola organización, alojada en su propio centro de datos o por un proveedor de forma exclusiva.'
FROM libros l, conceptos c WHERE l.titulo = 'Cloud Computing: Fundamentos y Arquitecturas' AND c.termino = 'Private Cloud'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Combinación de nube pública y privada que permite mover cargas de trabajo entre ambas según necesidad.'
FROM libros l, conceptos c WHERE l.titulo = 'Cloud Computing: Fundamentos y Arquitecturas' AND c.termino = 'Hybrid Cloud'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Estrategia de usar servicios de más de un proveedor de nube pública simultáneamente, para evitar dependencia de un solo proveedor.'
FROM libros l, conceptos c WHERE l.titulo = 'Cloud Computing: Fundamentos y Arquitecturas' AND c.termino = 'Multicloud'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Modelo de ejecución en el que el proveedor administra dinámicamente la asignación de servidores; el desarrollador no aprovisiona ni administra infraestructura directamente.'
FROM libros l, conceptos c WHERE l.titulo = 'Cloud Computing: Fundamentos y Arquitecturas' AND c.termino = 'Serverless'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Estructura jerárquica donde cada nodo tiene a lo más dos hijos; base de árboles de búsqueda balanceados.'
FROM libros l, conceptos c WHERE l.titulo = 'Estructuras de Datos y Algoritmos' AND c.termino = 'Árbol binario'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Medida del crecimiento del tiempo o memoria que requiere un algoritmo en función del tamaño de la entrada.'
FROM libros l, conceptos c WHERE l.titulo = 'Estructuras de Datos y Algoritmos' AND c.termino = 'Complejidad algorítmica'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Proceso de organizar columnas y tablas de una base de datos relacional para minimizar la redundancia.'
FROM libros l, conceptos c WHERE l.titulo = 'Bases de Datos Avanzadas' AND c.termino = 'Normalización'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Conjunto de propiedades (Atomicidad, Consistencia, Aislamiento, Durabilidad) que garantizan operaciones de base de datos confiables.'
FROM libros l, conceptos c WHERE l.titulo = 'Bases de Datos Avanzadas' AND c.termino = 'Transacción ACID'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Estructura auxiliar que acelera la búsqueda de filas en una tabla a costa de espacio y overhead de escritura.'
FROM libros l, conceptos c WHERE l.titulo = 'Bases de Datos Avanzadas' AND c.termino = 'Índice'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Patrón de diseño que separa un sistema en Modelo (datos), Vista (presentación) y Controlador (flujo de control).'
FROM libros l, conceptos c WHERE l.titulo = 'Ingeniería de Software Moderna' AND c.termino = 'Patrón MVC'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Técnica que distribuye tráfico entrante entre varios servidores para mejorar disponibilidad y rendimiento.'
FROM libros l, conceptos c WHERE l.titulo = 'Introducción a las Redes' AND c.termino = 'Balanceo de carga'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Capacidad de un sistema de ejecutar múltiples tareas que progresan en un mismo período de tiempo.'
FROM libros l, conceptos c WHERE l.titulo = 'Sistemas Operativos Concurrentes' AND c.termino = 'Concurrencia'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Paradigma de programación que trata la computación como evaluación de funciones matemáticas, evitando estado mutable.'
FROM libros l, conceptos c WHERE l.titulo = 'Inteligencia Artificial Aplicada' AND c.termino = 'Programación funcional'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Patrón de diseño donde un objeto recibe sus dependencias en vez de crearlas internamente, facilitando pruebas y bajo acoplamiento.'
FROM libros l, conceptos c WHERE l.titulo = 'Ciberseguridad Práctica' AND c.termino = 'Inyección de dependencias'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Estrategia de aumentar la capacidad de un sistema agregando más instancias en vez de más recursos a una sola máquina.'
FROM libros l, conceptos c WHERE l.titulo = 'Arquitectura de Microservicios' AND c.termino = 'Escalabilidad horizontal'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Unidad estándar de software que empaqueta código y sus dependencias para que la aplicación corra de forma consistente en cualquier entorno.'
FROM libros l, conceptos c WHERE l.titulo = 'Arquitectura de Microservicios' AND c.termino = 'Contenedor (Docker)'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Estilo de arquitectura para servicios web que usa los verbos HTTP y recursos identificados por URL para exponer funcionalidad.'
FROM libros l, conceptos c WHERE l.titulo = 'DevOps en la Práctica' AND c.termino = 'API REST'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Almacenamiento temporal de datos de acceso frecuente para reducir la latencia de futuras solicitudes.'
FROM libros l, conceptos c WHERE l.titulo = 'Machine Learning desde Cero' AND c.termino = 'Caché'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Otra definición de ejemplo, distinta a la de otro libro para el mismo concepto.'
FROM libros l, conceptos c WHERE l.titulo = 'El reino de este mundo' AND c.termino = 'Herencia'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Otra definición de ejemplo, distinta a la de otro libro para el mismo concepto.'
FROM libros l, conceptos c WHERE l.titulo = 'Hombres de maíz' AND c.termino = 'Polimorfismo'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Otra definición de ejemplo, distinta a la de otro libro para el mismo concepto.'
FROM libros l, conceptos c WHERE l.titulo = 'El túnel' AND c.termino = 'Concurrencia'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Otra definición de ejemplo, distinta a la de otro libro para el mismo concepto.'
FROM libros l, conceptos c WHERE l.titulo = 'Los detectives salvajes' AND c.termino = 'Tabla hash'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;
INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
SELECT l.id, c.id, 'Otra definición de ejemplo, distinta a la de otro libro para el mismo concepto.'
FROM libros l, conceptos c WHERE l.titulo = 'Desolación' AND c.termino = 'Clave foránea'
ON CONFLICT (libro_id, concepto_id) DO NOTHING;

-- ---------------------------------------------------------------------
-- IMAGENES (1:N) — placeholders hospedados externamente (placehold.co)
-- para que se vean correctamente en el navegador sin subir archivos
-- reales a /uploads primero.
-- ---------------------------------------------------------------------
INSERT INTO imagenes (libro_id, url_imagen, texto_alt, es_principal)
SELECT l.id, 'https://placehold.co/300x450/1c3d5a/ffffff?text=' || replace(l.titulo, ' ', '+'), l.titulo, true
FROM libros l
WHERE NOT EXISTS (SELECT 1 FROM imagenes im WHERE im.libro_id = l.id);

COMMIT;
