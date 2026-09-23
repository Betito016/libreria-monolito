"""
Genera `01_catalogo_libros.sql` a partir de `library.xml` (Ejercicio-3).

Uso:
    python generar_01_catalogo.py <ruta/a/library.xml>

La migracion resultante se versiona junto con este script: el SQL es lo que
se ejecuta, y este script documenta de donde salieron los datos. Volver a
correrlo produce exactamente el mismo archivo.
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Clasificacion amplia, distinta del genero. El genero describe el contenido
# (Cloud, Fiction, Security...) y un libro puede tener varios; la categoria
# describe el proposito del libro y es una sola.
CATEGORIAS = ('Educación', 'Negocios', 'Divulgación', 'Literatura')

CATEGORIA_POR_ISBN = {
    # Negocios: libros de gestion y emprendimiento
    '9781119366894': 'Negocios',      # The Lean Startup
    '9781118761964': 'Negocios',      # Business Model Generation
    # Divulgacion: no ficcion para publico general
    '9781451648539': 'Divulgación',   # The Innovators
    '9780306347412': 'Divulgación',   # The Signal and the Noise
    '9781250231577': 'Divulgación',   # The Age of AI
    '9781501127625': 'Divulgación',   # The Power of Habit
    # Literatura: ficcion
    '9780451524935': 'Literatura',    # 1984
    '9780062315007': 'Literatura',    # The Martian
    '9781451673319': 'Literatura',    # The Road
    '9780307887443': 'Literatura',    # The Circle
    '9781514732915': 'Literatura',    # The Book of the Ancestor
}
CATEGORIA_POR_DEFECTO = 'Educación'   # textos tecnicos y de formacion

# Categorias originales del seed: en realidad eran el PRIMER genero de cada
# libro de library.xml, guardado como si fuera categoria.
CATEGORIAS_ORIGINALES = (
    'Cloud', 'Architecture', 'Programming', 'DevOps', 'Business',
    'Data Science', 'AI', 'Fiction', 'Security',
)


def q(texto: str) -> str:
    """Literal SQL con comillas simples escapadas."""
    return "'" + texto.replace("'", "''") + "'"


def generar(ruta_xml: Path) -> str:
    libros = ET.parse(ruta_xml).getroot().findall('book')

    autores, generos = [], []
    for libro in libros:
        for a in libro.findall('./authors/author'):
            if a.text not in autores:
                autores.append(a.text)
        for g in libro.findall('./genres/genre'):
            if g.text not in generos:
                generos.append(g.text)

    lineas = []
    w = lineas.append

    w("-- =====================================================================")
    w("-- services/books/sql/01_catalogo_libros.sql")
    w("-- Migracion del catalogo para el microservicio de libros (services/books)")
    w("-- Motor: PostgreSQL  |  Base: libreria_db")
    w("-- GENERADO por generar_01_catalogo.py a partir de library.xml.")
    w("-- No editar a mano: modificar el script y regenerar.")
    w("-- =====================================================================")
    w("--")
    w("-- POR QUE ESTA MIGRACION")
    w("-- ---------------------------------------------------------------------")
    w("-- El catalogo solo guardaba en la base los atributos escalares del libro")
    w("-- (isbn, titulo, anio, precio, stock, formato, categoria). Los autores")
    w("-- vivian en un diccionario de Python y la imagen se calculaba a partir")
    w("-- del ISBN. Para consultar eso bastaba; para un CRUD no: un libro nuevo")
    w("-- no tendria donde guardar sus autores ni sus imagenes.")
    w("--")
    w("-- Siguiendo las dependencias multivaluadas de library.xml:")
    w("--   isbn ->> autor    (un libro, varios autores)  -> authors + book_authors")
    w("--   isbn ->> genero   (un libro, varios generos)  -> genres  + book_genres")
    w("--   isbn ->> imagen   (un libro, varias imagenes) -> book_images")
    w("--")
    w("-- GENERO vs CATEGORIA")
    w("-- ---------------------------------------------------------------------")
    w("-- La tabla `categories` del seed contenia en realidad el PRIMER genero de")
    w("-- cada libro (Cloud, Fiction, Security...). Se separan los conceptos:")
    w("--   * genero    : de que trata el libro. Varios por libro (tabla genres).")
    w("--   * categoria : para que sirve el libro. Uno por libro")
    w("--                 (Educacion, Negocios, Divulgacion, Literatura).")
    w("--")
    w("-- BORRADO DE LIBROS")
    w("-- ---------------------------------------------------------------------")
    w("-- Autores, generos e imagenes de un libro se eliminan en cascada: no")
    w("-- tienen sentido sin el libro. Las restricciones existentes sobre")
    w("-- book_concepts y clasificaciones_cloud NO se tocan: impiden borrar un")
    w("-- libro con conceptos o clasificaciones, y el microservicio lo informa")
    w("-- con un 409 en lugar de perder esos datos en silencio.")
    w("-- =====================================================================")
    w("")
    w("BEGIN;")
    w("")
    w("-- ---------------------------------------------------------------------")
    w("-- 1. TABLAS NUEVAS")
    w("-- ---------------------------------------------------------------------")
    w("CREATE TABLE IF NOT EXISTS authors (")
    w("    id    SERIAL PRIMARY KEY,")
    w("    name  VARCHAR(150) NOT NULL UNIQUE")
    w(");")
    w("")
    w("CREATE TABLE IF NOT EXISTS book_authors (")
    w("    book_isbn  VARCHAR(20) NOT NULL REFERENCES books(isbn) ON DELETE CASCADE,")
    w("    author_id  INTEGER     NOT NULL REFERENCES authors(id) ON DELETE RESTRICT,")
    w("    position   SMALLINT    NOT NULL DEFAULT 1,")
    w("    PRIMARY KEY (book_isbn, author_id)")
    w(");")
    w("")
    w("CREATE TABLE IF NOT EXISTS genres (")
    w("    id    SERIAL PRIMARY KEY,")
    w("    name  VARCHAR(80) NOT NULL UNIQUE")
    w(");")
    w("")
    w("CREATE TABLE IF NOT EXISTS book_genres (")
    w("    book_isbn  VARCHAR(20) NOT NULL REFERENCES books(isbn) ON DELETE CASCADE,")
    w("    genre_id   INTEGER     NOT NULL REFERENCES genres(id) ON DELETE RESTRICT,")
    w("    PRIMARY KEY (book_isbn, genre_id)")
    w(");")
    w("")
    w("CREATE TABLE IF NOT EXISTS book_images (")
    w("    id          SERIAL PRIMARY KEY,")
    w("    book_isbn   VARCHAR(20)  NOT NULL REFERENCES books(isbn) ON DELETE CASCADE,")
    w("    url         TEXT         NOT NULL,")
    w("    alt_text    VARCHAR(255),")
    w("    is_primary  BOOLEAN      NOT NULL DEFAULT FALSE,")
    w("    position    SMALLINT     NOT NULL DEFAULT 0,")
    w("    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),")
    w("    UNIQUE (book_isbn, url)")
    w(");")
    w("")
    w("-- A lo mas una imagen principal por libro.")
    w("CREATE UNIQUE INDEX IF NOT EXISTS ux_book_images_primary")
    w("    ON book_images (book_isbn) WHERE is_primary;")
    w("")
    w("CREATE INDEX IF NOT EXISTS ix_book_authors_author ON book_authors (author_id);")
    w("CREATE INDEX IF NOT EXISTS ix_book_genres_genre   ON book_genres (genre_id);")
    w("CREATE INDEX IF NOT EXISTS ix_book_images_book    ON book_images (book_isbn);")
    w("")
    w("-- ---------------------------------------------------------------------")
    w("-- 2. RESTRICCIONES DE DOMINIO EN `books`")
    w("-- ---------------------------------------------------------------------")
    w("-- El microservicio valida estos rangos, pero la base tambien los impone:")
    w("-- ningun otro cliente de libreria_db podra guardar precios o existencias")
    w("-- negativas.")
    w("DO $$")
    w("BEGIN")
    w("    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_books_price') THEN")
    w("        ALTER TABLE books ADD CONSTRAINT ck_books_price CHECK (price >= 0);")
    w("    END IF;")
    w("    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_books_stock') THEN")
    w("        ALTER TABLE books ADD CONSTRAINT ck_books_stock CHECK (stock >= 0);")
    w("    END IF;")
    w("    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_books_year') THEN")
    w("        ALTER TABLE books ADD CONSTRAINT ck_books_year CHECK (year BETWEEN 1400 AND 2100);")
    w("    END IF;")
    w("END $$;")
    w("")
    w("-- ---------------------------------------------------------------------")
    w(f"-- 3. DATA MIGRATION: generos ({len(generos)}) desde library.xml")
    w("-- ---------------------------------------------------------------------")
    w("INSERT INTO genres (name) VALUES")
    w(",\n".join(f"    ({q(g)})" for g in generos))
    w("ON CONFLICT (name) DO NOTHING;")
    w("")
    w("-- ---------------------------------------------------------------------")
    w(f"-- 4. DATA MIGRATION: autores ({len(autores)}) desde library.xml")
    w("-- ---------------------------------------------------------------------")
    w("INSERT INTO authors (name) VALUES")
    w(",\n".join(f"    ({q(a)})" for a in autores))
    w("ON CONFLICT (name) DO NOTHING;")
    w("")
    w("-- ---------------------------------------------------------------------")
    w("-- 5. DATA MIGRATION: relaciones libro-autor, libro-genero e imagenes")
    w("-- ---------------------------------------------------------------------")
    w("-- Solo para libros que existen en `books` (el seed del monolito cargo")
    w("-- los mismos 30 ISBN de library.xml).")
    for libro in libros:
        isbn = libro.get('isbn')
        titulo = libro.findtext('title')
        w(f"-- {isbn} | {titulo}")
        for pos, a in enumerate(libro.findall('./authors/author'), start=1):
            w(
                "INSERT INTO book_authors (book_isbn, author_id, position) "
                f"SELECT {q(isbn)}, id, {pos} FROM authors WHERE name = {q(a.text)} "
                f"AND EXISTS (SELECT 1 FROM books WHERE isbn = {q(isbn)}) "
                "ON CONFLICT DO NOTHING;"
            )
        for g in libro.findall('./genres/genre'):
            w(
                "INSERT INTO book_genres (book_isbn, genre_id) "
                f"SELECT {q(isbn)}, id FROM genres WHERE name = {q(g.text)} "
                f"AND EXISTS (SELECT 1 FROM books WHERE isbn = {q(isbn)}) "
                "ON CONFLICT DO NOTHING;"
            )
        for pos, img in enumerate(libro.findall('./images/image')):
            w(
                "INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position) "
                f"SELECT {q(isbn)}, {q(img.get('uri'))}, {q(img.text or titulo)}, "
                f"{'TRUE' if pos == 0 else 'FALSE'}, {pos} "
                f"WHERE EXISTS (SELECT 1 FROM books WHERE isbn = {q(isbn)}) "
                "ON CONFLICT DO NOTHING;"
            )
    w("")
    w("-- ---------------------------------------------------------------------")
    w("-- 6. DATA MIGRATION: categorias amplias")
    w("-- ---------------------------------------------------------------------")
    w("-- El seed inserto las categorias con id explicito (1..9), lo cual NO")
    w("-- avanza la secuencia de SERIAL. Sin este setval, el siguiente INSERT")
    w("-- intentaria reutilizar el id 1 y fallaria por llave duplicada.")
    w("SELECT setval(")
    w("    pg_get_serial_sequence('categories', 'id'),")
    w("    GREATEST((SELECT COALESCE(MAX(id), 0) FROM categories), 1)")
    w(");")
    w("")
    w("INSERT INTO categories (name) VALUES")
    w(",\n".join(f"    ({q(c)})" for c in CATEGORIAS))
    w("ON CONFLICT (name) DO NOTHING;")
    w("")
    w(f"-- Categoria por defecto: {CATEGORIA_POR_DEFECTO}")
    w("UPDATE books SET category_id = (SELECT id FROM categories WHERE name = "
      f"{q(CATEGORIA_POR_DEFECTO)});")
    for categoria in CATEGORIAS:
        if categoria == CATEGORIA_POR_DEFECTO:
            continue
        isbns = [i for i, c in CATEGORIA_POR_ISBN.items() if c == categoria]
        lista = ", ".join(q(i) for i in isbns)
        w(f"UPDATE books SET category_id = (SELECT id FROM categories WHERE name = {q(categoria)})")
        w(f"    WHERE isbn IN ({lista});")
    w("")
    w("-- Las categorias originales (que eran generos) quedan sin libros: se retiran.")
    w("DELETE FROM categories")
    w(f"WHERE name IN ({', '.join(q(c) for c in CATEGORIAS_ORIGINALES)})")
    w("  AND NOT EXISTS (SELECT 1 FROM books b WHERE b.category_id = categories.id);")
    w("")
    w("-- ---------------------------------------------------------------------")
    w("-- 7. PERMISOS DEL ROL DEL MICROSERVICIO (MINIMO PRIVILEGIO)")
    w("-- ---------------------------------------------------------------------")
    w("-- El rol se crea ANTES de ejecutar esta migracion (su contrasena no se")
    w("-- versiona):  CREATE ROLE books_app_user WITH LOGIN PASSWORD '<...>';")
    w("-- Categorias y conceptos son de SOLO LECTURA para el microservicio.")
    w("DO $$")
    w("BEGIN")
    w("    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'books_app_user') THEN")
    w("        EXECUTE 'GRANT CONNECT ON DATABASE libreria_db TO books_app_user';")
    w("        EXECUTE 'GRANT USAGE ON SCHEMA public TO books_app_user';")
    w("        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON books TO books_app_user';")
    w("        EXECUTE 'GRANT SELECT, INSERT, UPDATE ON authors, genres TO books_app_user';")
    w("        EXECUTE 'GRANT SELECT, INSERT, DELETE ON book_authors, book_genres, book_images TO books_app_user';")
    w("        EXECUTE 'GRANT SELECT ON categories, concepts, book_concepts TO books_app_user';")
    w("        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE authors_id_seq, genres_id_seq, book_images_id_seq TO books_app_user';")
    w("    ELSE")
    w("        RAISE NOTICE 'El rol books_app_user no existe: se omiten los GRANT.';")
    w("    END IF;")
    w("END $$;")
    w("")
    w("COMMIT;")
    w("")
    w("-- =====================================================================")
    w("-- VERIFICACION POSTERIOR")
    w("-- =====================================================================")
    w("-- SELECT c.name AS categoria, COUNT(*) FROM books b")
    w("-- JOIN categories c ON c.id = b.category_id GROUP BY c.name;")
    w("--")
    w("-- SELECT (SELECT COUNT(*) FROM authors) AS autores,")
    w("--        (SELECT COUNT(*) FROM genres) AS generos,")
    w("--        (SELECT COUNT(*) FROM book_images) AS imagenes;")
    w("-- =====================================================================")
    return "\n".join(lineas) + "\n"


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    salida = Path(__file__).with_name('01_catalogo_libros.sql')
    # newline='\n' explicito: en Windows, write_text convierte a CRLF por
    # defecto, y un "COMMIT;\r" ya no coincide con los scripts que buscan
    # "^COMMIT;$" (por ejemplo, para ensayar la migracion con ROLLBACK).
    salida.write_text(generar(Path(sys.argv[1])), encoding='utf-8', newline='\n')
    print(f"Generado: {salida}")
