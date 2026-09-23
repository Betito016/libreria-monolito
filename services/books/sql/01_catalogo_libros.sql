-- =====================================================================
-- services/books/sql/01_catalogo_libros.sql
-- Migracion del catalogo para el microservicio de libros (services/books)
-- Motor: PostgreSQL  |  Base: libreria_db
-- GENERADO por generar_01_catalogo.py a partir de library.xml.
-- No editar a mano: modificar el script y regenerar.
-- =====================================================================
--
-- POR QUE ESTA MIGRACION
-- ---------------------------------------------------------------------
-- El catalogo solo guardaba en la base los atributos escalares del libro
-- (isbn, titulo, anio, precio, stock, formato, categoria). Los autores
-- vivian en un diccionario de Python y la imagen se calculaba a partir
-- del ISBN. Para consultar eso bastaba; para un CRUD no: un libro nuevo
-- no tendria donde guardar sus autores ni sus imagenes.
--
-- Siguiendo las dependencias multivaluadas de library.xml:
--   isbn ->> autor    (un libro, varios autores)  -> authors + book_authors
--   isbn ->> genero   (un libro, varios generos)  -> genres  + book_genres
--   isbn ->> imagen   (un libro, varias imagenes) -> book_images
--
-- GENERO vs CATEGORIA
-- ---------------------------------------------------------------------
-- La tabla `categories` del seed contenia en realidad el PRIMER genero de
-- cada libro (Cloud, Fiction, Security...). Se separan los conceptos:
--   * genero    : de que trata el libro. Varios por libro (tabla genres).
--   * categoria : para que sirve el libro. Uno por libro
--                 (Educacion, Negocios, Divulgacion, Literatura).
--
-- BORRADO DE LIBROS
-- ---------------------------------------------------------------------
-- Autores, generos e imagenes de un libro se eliminan en cascada: no
-- tienen sentido sin el libro. Las restricciones existentes sobre
-- book_concepts y clasificaciones_cloud NO se tocan: impiden borrar un
-- libro con conceptos o clasificaciones, y el microservicio lo informa
-- con un 409 en lugar de perder esos datos en silencio.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1. TABLAS NUEVAS
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS authors (
    id    SERIAL PRIMARY KEY,
    name  VARCHAR(150) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS book_authors (
    book_isbn  VARCHAR(20) NOT NULL REFERENCES books(isbn) ON DELETE CASCADE,
    author_id  INTEGER     NOT NULL REFERENCES authors(id) ON DELETE RESTRICT,
    position   SMALLINT    NOT NULL DEFAULT 1,
    PRIMARY KEY (book_isbn, author_id)
);

CREATE TABLE IF NOT EXISTS genres (
    id    SERIAL PRIMARY KEY,
    name  VARCHAR(80) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS book_genres (
    book_isbn  VARCHAR(20) NOT NULL REFERENCES books(isbn) ON DELETE CASCADE,
    genre_id   INTEGER     NOT NULL REFERENCES genres(id) ON DELETE RESTRICT,
    PRIMARY KEY (book_isbn, genre_id)
);

CREATE TABLE IF NOT EXISTS book_images (
    id          SERIAL PRIMARY KEY,
    book_isbn   VARCHAR(20)  NOT NULL REFERENCES books(isbn) ON DELETE CASCADE,
    url         TEXT         NOT NULL,
    alt_text    VARCHAR(255),
    is_primary  BOOLEAN      NOT NULL DEFAULT FALSE,
    position    SMALLINT     NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (book_isbn, url)
);

-- A lo mas una imagen principal por libro.
CREATE UNIQUE INDEX IF NOT EXISTS ux_book_images_primary
    ON book_images (book_isbn) WHERE is_primary;

CREATE INDEX IF NOT EXISTS ix_book_authors_author ON book_authors (author_id);
CREATE INDEX IF NOT EXISTS ix_book_genres_genre   ON book_genres (genre_id);
CREATE INDEX IF NOT EXISTS ix_book_images_book    ON book_images (book_isbn);

-- ---------------------------------------------------------------------
-- 2. RESTRICCIONES DE DOMINIO EN `books`
-- ---------------------------------------------------------------------
-- El microservicio valida estos rangos, pero la base tambien los impone:
-- ningun otro cliente de libreria_db podra guardar precios o existencias
-- negativas.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_books_price') THEN
        ALTER TABLE books ADD CONSTRAINT ck_books_price CHECK (price >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_books_stock') THEN
        ALTER TABLE books ADD CONSTRAINT ck_books_stock CHECK (stock >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_books_year') THEN
        ALTER TABLE books ADD CONSTRAINT ck_books_year CHECK (year BETWEEN 1400 AND 2100);
    END IF;
END $$;

-- ---------------------------------------------------------------------
-- 3. DATA MIGRATION: generos (9) desde library.xml
-- ---------------------------------------------------------------------
INSERT INTO genres (name) VALUES
    ('Cloud'),
    ('Architecture'),
    ('Programming'),
    ('DevOps'),
    ('Business'),
    ('Data Science'),
    ('AI'),
    ('Fiction'),
    ('Security')
ON CONFLICT (name) DO NOTHING;

-- ---------------------------------------------------------------------
-- 4. DATA MIGRATION: autores (15) desde library.xml
-- ---------------------------------------------------------------------
INSERT INTO authors (name) VALUES
    ('Thomas Erl'),
    ('Zaigham Mahmood'),
    ('Kelsey Hightower'),
    ('Brendan Burns'),
    ('David Chen'),
    ('Robert C. Martin'),
    ('Mary Rose Cook'),
    ('María Sol'),
    ('Alicia Díaz'),
    ('Ricardo Montalvo'),
    ('Javier Salinas'),
    ('Elena Torres'),
    ('Patricia Gómez'),
    ('Matías Ortega'),
    ('Carlos Vega')
ON CONFLICT (name) DO NOTHING;

-- ---------------------------------------------------------------------
-- 5. DATA MIGRATION: relaciones libro-autor, libro-genero e imagenes
-- ---------------------------------------------------------------------
-- Solo para libros que existen en `books` (el seed del monolito cargo
-- los mismos 30 ISBN de library.xml).
-- 9780134092669 | Cloud Computing: Concepts, Technology & Architecture
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9780134092669', id, 1 FROM authors WHERE name = 'Thomas Erl' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780134092669') ON CONFLICT DO NOTHING;
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9780134092669', id, 2 FROM authors WHERE name = 'Zaigham Mahmood' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780134092669') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9780134092669', id FROM genres WHERE name = 'Cloud' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780134092669') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9780134092669', id FROM genres WHERE name = 'Architecture' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780134092669') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9780134092669', 'https://covers.openlibrary.org/b/isbn/9780134092669-L.jpg', 'Cloud Computing cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9780134092669') ON CONFLICT DO NOTHING;
-- 9781118795555 | Architecting the Cloud
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9781118795555', id, 1 FROM authors WHERE name = 'Thomas Erl' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781118795555') ON CONFLICT DO NOTHING;
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9781118795555', id, 2 FROM authors WHERE name = 'Zaigham Mahmood' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781118795555') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781118795555', id FROM genres WHERE name = 'Cloud' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781118795555') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781118795555', id FROM genres WHERE name = 'Architecture' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781118795555') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9781118795555', 'https://covers.openlibrary.org/b/isbn/9781118795555-L.jpg', 'Architecting the Cloud cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9781118795555') ON CONFLICT DO NOTHING;
-- 9781449311756 | Cloud Native Go
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9781449311756', id, 1 FROM authors WHERE name = 'Kelsey Hightower' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781449311756') ON CONFLICT DO NOTHING;
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9781449311756', id, 2 FROM authors WHERE name = 'Brendan Burns' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781449311756') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781449311756', id FROM genres WHERE name = 'Cloud' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781449311756') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781449311756', id FROM genres WHERE name = 'Programming' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781449311756') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9781449311756', 'https://covers.openlibrary.org/b/isbn/9781449311756-L.jpg', 'Cloud Native Go cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9781449311756') ON CONFLICT DO NOTHING;
-- 9781492034485 | Kubernetes Up and Running
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9781492034485', id, 1 FROM authors WHERE name = 'Kelsey Hightower' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781492034485') ON CONFLICT DO NOTHING;
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9781492034485', id, 2 FROM authors WHERE name = 'Brendan Burns' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781492034485') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781492034485', id FROM genres WHERE name = 'Cloud' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781492034485') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781492034485', id FROM genres WHERE name = 'DevOps' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781492034485') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9781492034485', 'https://covers.openlibrary.org/b/isbn/9781492034485-L.jpg', 'Kubernetes Up and Running cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9781492034485') ON CONFLICT DO NOTHING;
-- 9780596006378 | Cloud Computing For Dummies
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9780596006378', id, 1 FROM authors WHERE name = 'David Chen' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780596006378') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9780596006378', id FROM genres WHERE name = 'Cloud' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780596006378') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9780596006378', id FROM genres WHERE name = 'Business' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780596006378') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9780596006378', 'https://covers.openlibrary.org/b/isbn/9780596006378-L.jpg', 'Cloud Computing For Dummies cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9780596006378') ON CONFLICT DO NOTHING;
-- 9780132350884 | Clean Code
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9780132350884', id, 1 FROM authors WHERE name = 'Robert C. Martin' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780132350884') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9780132350884', id FROM genres WHERE name = 'Programming' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780132350884') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9780132350884', 'https://covers.openlibrary.org/b/isbn/9780132350884-L.jpg', 'Clean Code cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9780132350884') ON CONFLICT DO NOTHING;
-- 9780201616224 | The Pragmatic Programmer
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9780201616224', id, 1 FROM authors WHERE name = 'Mary Rose Cook' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780201616224') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9780201616224', id FROM genres WHERE name = 'Programming' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780201616224') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9780201616224', 'https://covers.openlibrary.org/b/isbn/9780201616224-L.jpg', 'The Pragmatic Programmer cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9780201616224') ON CONFLICT DO NOTHING;
-- 9780201485677 | Refactoring
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9780201485677', id, 1 FROM authors WHERE name = 'Robert C. Martin' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780201485677') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9780201485677', id FROM genres WHERE name = 'Programming' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780201485677') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9780201485677', 'https://covers.openlibrary.org/b/isbn/9780201485677-L.jpg', 'Refactoring cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9780201485677') ON CONFLICT DO NOTHING;
-- 9781942788294 | Practical Go
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9781942788294', id, 1 FROM authors WHERE name = 'Mary Rose Cook' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781942788294') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781942788294', id FROM genres WHERE name = 'Programming' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781942788294') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9781942788294', 'https://covers.openlibrary.org/b/isbn/9781942788294-L.jpg', 'Practical Go cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9781942788294') ON CONFLICT DO NOTHING;
-- 9781492044550 | Designing Data-Intensive Applications
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9781492044550', id, 1 FROM authors WHERE name = 'María Sol' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781492044550') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781492044550', id FROM genres WHERE name = 'Data Science' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781492044550') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9781492044550', 'https://covers.openlibrary.org/b/isbn/9781492044550-L.jpg', 'Designing Data-Intensive Applications cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9781492044550') ON CONFLICT DO NOTHING;
-- 9781617294945 | Microservices Patterns
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9781617294945', id, 1 FROM authors WHERE name = 'David Chen' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781617294945') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781617294945', id FROM genres WHERE name = 'Programming' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781617294945') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781617294945', id FROM genres WHERE name = 'Architecture' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781617294945') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9781617294945', 'https://covers.openlibrary.org/b/isbn/9781617294945-L.jpg', 'Microservices Patterns cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9781617294945') ON CONFLICT DO NOTHING;
-- 9781119366894 | The Lean Startup
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9781119366894', id, 1 FROM authors WHERE name = 'Alicia Díaz' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781119366894') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781119366894', id FROM genres WHERE name = 'Business' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781119366894') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9781119366894', 'https://covers.openlibrary.org/b/isbn/9781119366894-L.jpg', 'The Lean Startup cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9781119366894') ON CONFLICT DO NOTHING;
-- 9781118761964 | Business Model Generation
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9781118761964', id, 1 FROM authors WHERE name = 'Ricardo Montalvo' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781118761964') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781118761964', id FROM genres WHERE name = 'Business' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781118761964') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9781118761964', 'https://covers.openlibrary.org/b/isbn/9781118761964-L.jpg', 'Business Model Generation cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9781118761964') ON CONFLICT DO NOTHING;
-- 9781451648539 | The Innovators
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9781451648539', id, 1 FROM authors WHERE name = 'Javier Salinas' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781451648539') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781451648539', id FROM genres WHERE name = 'Business' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781451648539') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9781451648539', 'https://covers.openlibrary.org/b/isbn/9781451648539-L.jpg', 'The Innovators cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9781451648539') ON CONFLICT DO NOTHING;
-- 9780306347412 | The Signal and the Noise
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9780306347412', id, 1 FROM authors WHERE name = 'Elena Torres' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780306347412') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9780306347412', id FROM genres WHERE name = 'Data Science' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780306347412') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9780306347412', 'https://covers.openlibrary.org/b/isbn/9780306347412-L.jpg', 'The Signal and the Noise cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9780306347412') ON CONFLICT DO NOTHING;
-- 9780262035613 | Deep Learning
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9780262035613', id, 1 FROM authors WHERE name = 'Patricia Gómez' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780262035613') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9780262035613', id FROM genres WHERE name = 'AI' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780262035613') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9780262035613', 'https://covers.openlibrary.org/b/isbn/9780262035613-L.jpg', 'Deep Learning cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9780262035613') ON CONFLICT DO NOTHING;
-- 9781250231577 | The Age of AI
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9781250231577', id, 1 FROM authors WHERE name = 'Patricia Gómez' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781250231577') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781250231577', id FROM genres WHERE name = 'AI' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781250231577') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9781250231577', 'https://covers.openlibrary.org/b/isbn/9781250231577-L.jpg', 'The Age of AI cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9781250231577') ON CONFLICT DO NOTHING;
-- 9780451524935 | 1984
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9780451524935', id, 1 FROM authors WHERE name = 'Matías Ortega' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780451524935') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9780451524935', id FROM genres WHERE name = 'Fiction' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780451524935') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9780451524935', 'https://covers.openlibrary.org/b/isbn/9780451524935-L.jpg', '1984 cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9780451524935') ON CONFLICT DO NOTHING;
-- 9780062315007 | The Martian
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9780062315007', id, 1 FROM authors WHERE name = 'Carlos Vega' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780062315007') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9780062315007', id FROM genres WHERE name = 'Fiction' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780062315007') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9780062315007', 'https://covers.openlibrary.org/b/isbn/9780062315007-L.jpg', 'The Martian cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9780062315007') ON CONFLICT DO NOTHING;
-- 9781451673319 | The Road
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9781451673319', id, 1 FROM authors WHERE name = 'Matías Ortega' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781451673319') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781451673319', id FROM genres WHERE name = 'Fiction' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781451673319') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9781451673319', 'https://covers.openlibrary.org/b/isbn/9781451673319-L.jpg', 'The Road cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9781451673319') ON CONFLICT DO NOTHING;
-- 9780307887443 | The Circle
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9780307887443', id, 1 FROM authors WHERE name = 'Carlos Vega' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780307887443') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9780307887443', id FROM genres WHERE name = 'Fiction' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780307887443') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9780307887443', 'https://covers.openlibrary.org/b/isbn/9780307887443-L.jpg', 'The Circle cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9780307887443') ON CONFLICT DO NOTHING;
-- 9781593279288 | The Linux Command Line
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9781593279288', id, 1 FROM authors WHERE name = 'Kelsey Hightower' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781593279288') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781593279288', id FROM genres WHERE name = 'Programming' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781593279288') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9781593279288', 'https://covers.openlibrary.org/b/isbn/9781593279288-L.jpg', 'The Linux Command Line cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9781593279288') ON CONFLICT DO NOTHING;
-- 9780071592559 | Network Security Essentials
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9780071592559', id, 1 FROM authors WHERE name = 'David Chen' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780071592559') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9780071592559', id FROM genres WHERE name = 'Security' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780071592559') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9780071592559', 'https://covers.openlibrary.org/b/isbn/9780071592559-L.jpg', 'Network Security Essentials cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9780071592559') ON CONFLICT DO NOTHING;
-- 9780764577671 | Fundamentals of Network Security
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9780764577671', id, 1 FROM authors WHERE name = 'David Chen' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780764577671') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9780764577671', id FROM genres WHERE name = 'Security' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780764577671') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9780764577671', 'https://covers.openlibrary.org/b/isbn/9780764577671-L.jpg', 'Fundamentals of Network Security cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9780764577671') ON CONFLICT DO NOTHING;
-- 9781720049584 | Hands-On Machine Learning
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9781720049584', id, 1 FROM authors WHERE name = 'Elena Torres' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781720049584') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781720049584', id FROM genres WHERE name = 'Data Science' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781720049584') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781720049584', id FROM genres WHERE name = 'AI' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781720049584') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9781720049584', 'https://covers.openlibrary.org/b/isbn/9781720049584-L.jpg', 'Hands-On Machine Learning cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9781720049584') ON CONFLICT DO NOTHING;
-- 9781119543033 | Big Data Analytics
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9781119543033', id, 1 FROM authors WHERE name = 'María Sol' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781119543033') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781119543033', id FROM genres WHERE name = 'Data Science' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781119543033') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9781119543033', 'https://covers.openlibrary.org/b/isbn/9781119543033-L.jpg', 'Big Data Analytics cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9781119543033') ON CONFLICT DO NOTHING;
-- 9781501127625 | The Power of Habit
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9781501127625', id, 1 FROM authors WHERE name = 'Javier Salinas' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781501127625') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781501127625', id FROM genres WHERE name = 'Business' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781501127625') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9781501127625', 'https://covers.openlibrary.org/b/isbn/9781501127625-L.jpg', 'The Power of Habit cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9781501127625') ON CONFLICT DO NOTHING;
-- 9780134484205 | Cybersecurity Essentials
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9780134484205', id, 1 FROM authors WHERE name = 'David Chen' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780134484205') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9780134484205', id FROM genres WHERE name = 'Security' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9780134484205') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9780134484205', 'https://covers.openlibrary.org/b/isbn/9780134484205-L.jpg', 'Cybersecurity Essentials cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9780134484205') ON CONFLICT DO NOTHING;
-- 9781514732915 | The Book of the Ancestor
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9781514732915', id, 1 FROM authors WHERE name = 'Matías Ortega' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781514732915') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781514732915', id FROM genres WHERE name = 'Fiction' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781514732915') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9781514732915', 'https://covers.openlibrary.org/b/isbn/9781514732915-L.jpg', 'The Book of the Ancestor cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9781514732915') ON CONFLICT DO NOTHING;
-- 9781942788078 | Mastering PostgreSQL
INSERT INTO book_authors (book_isbn, author_id, position) SELECT '9781942788078', id, 1 FROM authors WHERE name = 'María Sol' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781942788078') ON CONFLICT DO NOTHING;
INSERT INTO book_genres (book_isbn, genre_id) SELECT '9781942788078', id FROM genres WHERE name = 'Programming' AND EXISTS (SELECT 1 FROM books WHERE isbn = '9781942788078') ON CONFLICT DO NOTHING;
INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) SELECT '9781942788078', 'https://covers.openlibrary.org/b/isbn/9781942788078-L.jpg', 'Mastering PostgreSQL cover', TRUE, 0 WHERE EXISTS (SELECT 1 FROM books WHERE isbn = '9781942788078') ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------
-- 6. DATA MIGRATION: categorias amplias
-- ---------------------------------------------------------------------
-- El seed inserto las categorias con id explicito (1..9), lo cual NO
-- avanza la secuencia de SERIAL. Sin este setval, el siguiente INSERT
-- intentaria reutilizar el id 1 y fallaria por llave duplicada.
SELECT setval(
    pg_get_serial_sequence('categories', 'id'),
    GREATEST((SELECT COALESCE(MAX(id), 0) FROM categories), 1)
);

INSERT INTO categories (name) VALUES
    ('Educación'),
    ('Negocios'),
    ('Divulgación'),
    ('Literatura')
ON CONFLICT (name) DO NOTHING;

-- Categoria por defecto: Educación
UPDATE books SET category_id = (SELECT id FROM categories WHERE name = 'Educación');
UPDATE books SET category_id = (SELECT id FROM categories WHERE name = 'Negocios')
    WHERE isbn IN ('9781119366894', '9781118761964');
UPDATE books SET category_id = (SELECT id FROM categories WHERE name = 'Divulgación')
    WHERE isbn IN ('9781451648539', '9780306347412', '9781250231577', '9781501127625');
UPDATE books SET category_id = (SELECT id FROM categories WHERE name = 'Literatura')
    WHERE isbn IN ('9780451524935', '9780062315007', '9781451673319', '9780307887443', '9781514732915');

-- Las categorias originales (que eran generos) quedan sin libros: se retiran.
DELETE FROM categories
WHERE name IN ('Cloud', 'Architecture', 'Programming', 'DevOps', 'Business', 'Data Science', 'AI', 'Fiction', 'Security')
  AND NOT EXISTS (SELECT 1 FROM books b WHERE b.category_id = categories.id);

-- ---------------------------------------------------------------------
-- 7. PERMISOS DEL ROL DEL MICROSERVICIO (MINIMO PRIVILEGIO)
-- ---------------------------------------------------------------------
-- El rol se crea ANTES de ejecutar esta migracion (su contrasena no se
-- versiona):  CREATE ROLE books_app_user WITH LOGIN PASSWORD '<...>';
-- Categorias y conceptos son de SOLO LECTURA para el microservicio.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'books_app_user') THEN
        EXECUTE 'GRANT CONNECT ON DATABASE libreria_db TO books_app_user';
        EXECUTE 'GRANT USAGE ON SCHEMA public TO books_app_user';
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON books TO books_app_user';
        EXECUTE 'GRANT SELECT, INSERT, UPDATE ON authors, genres TO books_app_user';
        EXECUTE 'GRANT SELECT, INSERT, DELETE ON book_authors, book_genres, book_images TO books_app_user';
        EXECUTE 'GRANT SELECT ON categories, concepts, book_concepts TO books_app_user';
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE authors_id_seq, genres_id_seq, book_images_id_seq TO books_app_user';
    ELSE
        RAISE NOTICE 'El rol books_app_user no existe: se omiten los GRANT.';
    END IF;
END $$;

COMMIT;

-- =====================================================================
-- VERIFICACION POSTERIOR
-- =====================================================================
-- SELECT c.name AS categoria, COUNT(*) FROM books b
-- JOIN categories c ON c.id = b.category_id GROUP BY c.name;
--
-- SELECT (SELECT COUNT(*) FROM authors) AS autores,
--        (SELECT COUNT(*) FROM genres) AS generos,
--        (SELECT COUNT(*) FROM book_images) AS imagenes;
-- =====================================================================
