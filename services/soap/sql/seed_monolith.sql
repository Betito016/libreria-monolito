-- ============================================================================
-- PROYECTO: Monolito de Librería (Esquema Existente y Datos Base)
-- ARCHIVO: sql/seed_monolith.sql
-- DESCRIPCIÓN: Crea las tablas existentes del monolito y precarga datos
--              extraídos de library.xml.
-- ============================================================================

-- Categorías
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

-- Libros del Monolito
CREATE TABLE IF NOT EXISTS books (
    isbn VARCHAR(20) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    year INTEGER NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    stock INTEGER NOT NULL,
    format VARCHAR(50),
    category_id INTEGER REFERENCES categories(id)
);

-- Conceptos del Monolito
CREATE TABLE IF NOT EXISTS concepts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    definition TEXT NOT NULL
);

-- Relación Libros - Conceptos
CREATE TABLE IF NOT EXISTS book_concepts (
    id SERIAL PRIMARY KEY,
    book_isbn VARCHAR(20) NOT NULL REFERENCES books(isbn),
    concept_id INTEGER NOT NULL REFERENCES concepts(id),
    CONSTRAINT uq_book_concept UNIQUE (book_isbn, concept_id)
);

-- Usuarios del Monolito (El módulo SOAP NUNCA debe reutilizar esta tabla)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'customer'
);

-- ----------------------------------------------------------------------------
-- INSERCIÓN DE DATOS BASE DEL MONOLITO
-- ----------------------------------------------------------------------------

-- Categorías
INSERT INTO categories (id, name) VALUES 
(1, 'Cloud'),
(2, 'Architecture'),
(3, 'Programming'),
(4, 'DevOps'),
(5, 'Business'),
(6, 'Data Science'),
(7, 'AI'),
(8, 'Fiction'),
(9, 'Security')
ON CONFLICT (id) DO NOTHING;

-- Libros
INSERT INTO books (isbn, title, year, price, stock, format, category_id) VALUES
('9780134092669', 'Cloud Computing: Concepts, Technology & Architecture', 2017, 1099.00, 12, 'Hardcover', 1),
('9781118795555', 'Architecting the Cloud', 2014, 950.00, 8, 'Hardcover', 1),
('9781449311756', 'Cloud Native Go', 2015, 890.00, 10, 'Paperback', 1),
('9781492034485', 'Kubernetes Up and Running', 2019, 1280.00, 9, 'Hardcover', 4),
('9780596006378', 'Cloud Computing For Dummies', 2021, 780.00, 15, 'Paperback', 1),
('9780132350884', 'Clean Code', 2008, 845.00, 20, 'Hardcover', 3),
('9780201616224', 'The Pragmatic Programmer', 1999, 760.00, 18, 'Paperback', 3),
('9780201485677', 'Refactoring', 1999, 910.00, 11, 'Hardcover', 3),
('9781942788294', 'Practical Go', 2021, 660.00, 16, 'Paperback', 3),
('9781492044550', 'Designing Data-Intensive Applications', 2017, 1345.00, 7, 'Hardcover', 6),
('9781617294945', 'Microservices Patterns', 2018, 1150.00, 6, 'Hardcover', 2),
('9781119366894', 'The Lean Startup', 2017, 610.00, 22, 'Paperback', 5),
('9781118761964', 'Business Model Generation', 2014, 720.00, 12, 'Paperback', 5),
('9781451648539', 'The Innovators', 2014, 820.00, 14, 'Hardcover', 5),
('9780306347412', 'The Signal and the Noise', 2012, 690.00, 10, 'Paperback', 6),
('9780262035613', 'Deep Learning', 2016, 1450.00, 5, 'Hardcover', 7),
('9781250231577', 'The Age of AI', 2018, 740.00, 17, 'Paperback', 7),
('9780451524935', '1984', 1949, 430.00, 25, 'Paperback', 8),
('9780062315007', 'The Martian', 2011, 500.00, 18, 'Paperback', 8),
('9781451673319', 'The Road', 2006, 520.00, 9, 'Paperback', 8),
('9780307887443', 'The Circle', 2013, 560.00, 13, 'Paperback', 8),
('9781593279288', 'The Linux Command Line', 2015, 700.00, 16, 'Paperback', 3),
('9780071592559', 'Network Security Essentials', 2011, 980.00, 8, 'Hardcover', 9),
('9780764577671', 'Fundamentals of Network Security', 2010, 870.00, 11, 'Paperback', 9),
('9781720049584', 'Hands-On Machine Learning', 2020, 1299.00, 4, 'Hardcover', 7),
('9781119543033', 'Big Data Analytics', 2018, 1040.00, 9, 'Paperback', 6),
('9781501127625', 'The Power of Habit', 2012, 610.00, 19, 'Paperback', 5),
('9780134484205', 'Cybersecurity Essentials', 2017, 1060.00, 10, 'Hardcover', 9),
('9781514732915', 'The Book of the Ancestor', 2020, 590.00, 6, 'Paperback', 8),
('9781942788078', 'Mastering PostgreSQL', 2022, 920.00, 7, 'Paperback', 3)
ON CONFLICT (isbn) DO NOTHING;

-- Conceptos extraídos del catálogo
INSERT INTO concepts (id, name, definition) VALUES
(1, 'IaaS', 'En el contexto de «Cloud Computing: Concepts, Technology & Architecture», IaaS describe el uso de infraestructura virtualizada bajo demanda, como máquinas virtuales, redes y almacenamiento, donde el proveedor administra el hardware y el usuario controla buena parte del sistema operativo y las aplicaciones.'),
(2, 'PaaS', 'En el contexto de «Cloud Computing: Concepts, Technology & Architecture», PaaS proporciona una plataforma administrada para desarrollar y desplegar aplicaciones sin gestionar directamente los servidores, incorporando runtimes, servicios, herramientas y mecanismos de escalamiento.'),
(3, 'SaaS', 'Software como Servicio: Aplicaciones completas entregadas a través de Internet bajo modelo de suscripción, administradas totalmente por el proveedor.'),
(4, 'FaaS', 'Función como Servicio (Serverless): Modelo de ejecución donde el código se ejecuta en respuesta a eventos sin requerir aprovisionamiento de infraestructura.')
ON CONFLICT (id) DO NOTHING;

-- Relación Libro-Concepto
INSERT INTO book_concepts (book_isbn, concept_id) VALUES
('9780134092669', 1),
('9780134092669', 2),
('9781118795555', 3),
('9781449311756', 4)
ON CONFLICT (book_isbn, concept_id) DO NOTHING;
