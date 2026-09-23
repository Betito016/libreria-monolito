"""
Capa de persistencia del microservicio de libros (Psycopg 3 + pool).

Opera sobre libreria_db. Un libro se reparte en varias tablas:

    books          atributos escalares (isbn, titulo, anio, precio, ...)
    categories     categoria amplia, una por libro (solo lectura aqui)
    book_authors   autores, varios por libro, con orden
    book_genres    generos, varios por libro
    book_images    imagenes, varias por libro, una marcada como principal
    book_concepts  conceptos asociados (solo lectura aqui)

Cada escritura (crear, reemplazar, modificar) ocurre en UNA transaccion:
o se guardan el libro y todas sus relaciones, o no se guarda nada.
"""
import logging
from typing import Any, Dict, List, Optional

import psycopg
from psycopg import sql as psql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from config.config import Config

logger = logging.getLogger(__name__)


class DatabaseUnavailableError(Exception):
    """No fue posible contactar a PostgreSQL."""


class BookNotFoundError(Exception):
    """No existe un libro con ese ISBN."""


class DuplicateIsbnError(Exception):
    """Ya existe un libro con ese ISBN."""


class CategoryNotFoundError(Exception):
    """La categoria indicada no existe."""

    def __init__(self, categoria: str, validas: List[str]):
        super().__init__(f"La categoría '{categoria}' no existe.")
        self.validas = validas


class BookInUseError(Exception):
    """El libro tiene datos que dependen de el y no puede borrarse."""


# Columnas escalares de `books` que PATCH puede modificar, con el nombre de
# campo que usa la API. Los nombres de columna salen de aqui, nunca del
# cliente, y se componen con psycopg.sql.
COLUMNAS_ESCALARES = {
    'titulo': 'title',
    'anio': 'year',
    'precio': 'price',
    'stock': 'stock',
    'formato': 'format',
}

SELECT_LIBRO = """
    SELECT b.isbn, b.title, b.year, b.price, b.stock, b.format, c.name AS category
    FROM books b
    LEFT JOIN categories c ON c.id = b.category_id
"""


def _escapar_like(texto: str) -> str:
    """Evita que '%' o '_' escritos por el usuario actuen como comodines."""
    return texto.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


class BookRepository:
    _pool: Optional[ConnectionPool] = None

    @classmethod
    def pool(cls) -> ConnectionPool:
        if cls._pool is None:
            cls._pool = ConnectionPool(
                conninfo=Config.dsn(), min_size=1, max_size=10, timeout=5, open=False
            )
            cls._pool.open()
            logger.info("Pool de conexiones a PostgreSQL inicializado (Psycopg 3).")
        return cls._pool

    # ------------------------------------------------------------------
    # /health
    # ------------------------------------------------------------------
    @classmethod
    def ping(cls) -> Dict[str, Any]:
        try:
            with cls.pool().connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version(), current_database(), (SELECT COUNT(*) FROM books)")
                    version, database, total = cur.fetchone()
            return {
                'conectado': True,
                'base_datos': database,
                'version': version.split(',')[0],
                'libros': total,
            }
        except Exception as exc:
            logger.error(f"Fallo el health check de PostgreSQL: {exc}")
            return {'conectado': False, 'error': str(exc)}

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    @classmethod
    def list_categories(cls) -> List[str]:
        try:
            with cls.pool().connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT name FROM categories ORDER BY name")
                    return [fila[0] for fila in cur.fetchall()]
        except psycopg.OperationalError as exc:
            raise DatabaseUnavailableError(str(exc)) from exc

    @classmethod
    def search(cls, filtros: Dict[str, Any], page: int, page_size: int) -> Dict[str, Any]:
        """Catalogo paginado. Todos los filtros son opcionales y se combinan
        con AND. El total refleja los libros que cumplen los filtros."""
        condiciones, parametros = [], []

        if filtros.get('isbn'):
            condiciones.append("b.isbn ILIKE %s")
            parametros.append(f"%{_escapar_like(filtros['isbn'])}%")
        if filtros.get('titulo'):
            condiciones.append("b.title ILIKE %s")
            parametros.append(f"%{_escapar_like(filtros['titulo'])}%")
        if filtros.get('anio') is not None:
            condiciones.append("b.year = %s")
            parametros.append(filtros['anio'])
        if filtros.get('precio_min') is not None:
            condiciones.append("b.price >= %s")
            parametros.append(filtros['precio_min'])
        if filtros.get('precio_max') is not None:
            condiciones.append("b.price <= %s")
            parametros.append(filtros['precio_max'])

        where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

        try:
            with cls.pool().connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(f"SELECT COUNT(*) AS total FROM books b {where}", parametros)
                    total = cur.fetchone()['total']

                    cur.execute(
                        f"{SELECT_LIBRO} {where} ORDER BY b.title LIMIT %s OFFSET %s",
                        parametros + [page_size, (page - 1) * page_size],
                    )
                    filas = cur.fetchall()
                    libros = cls._armar_libros(cur, filas)

            return {'total': total, 'libros': libros}
        except psycopg.OperationalError as exc:
            raise DatabaseUnavailableError(str(exc)) from exc

    @classmethod
    def get(cls, isbn: str) -> Optional[Dict[str, Any]]:
        """Detalle de un libro, incluidos sus conceptos."""
        try:
            with cls.pool().connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    return cls._cargar_libro(cur, isbn, con_conceptos=True)
        except psycopg.OperationalError as exc:
            raise DatabaseUnavailableError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------
    @classmethod
    def create(cls, datos: Dict[str, Any]) -> Dict[str, Any]:
        isbn = datos['isbn']
        try:
            with cls.pool().connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    categoria_id = cls._categoria_id(cur, datos['categoria'])
                    cur.execute(
                        """
                        INSERT INTO books (isbn, title, year, price, stock, format, category_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (isbn, datos['titulo'], datos['anio'], datos['precio'],
                         datos['stock'], datos['formato'], categoria_id),
                    )
                    cls._reemplazar_autores(cur, isbn, datos['autores'])
                    cls._reemplazar_generos(cur, isbn, datos.get('generos', []))
                    cls._reemplazar_imagenes(cur, isbn, datos.get('imagenes', []), datos['titulo'])
                    return cls._cargar_libro(cur, isbn, con_conceptos=True)
        except psycopg.errors.UniqueViolation as exc:
            if exc.diag.table_name == 'books':
                raise DuplicateIsbnError(f"Ya existe un libro con el ISBN {isbn}.") from exc
            raise
        except psycopg.OperationalError as exc:
            raise DatabaseUnavailableError(str(exc)) from exc

    @classmethod
    def replace(cls, isbn: str, datos: Dict[str, Any]) -> Dict[str, Any]:
        """PUT: reemplaza TODA la representacion del libro. Lo que no venga
        en `datos` no se conserva: las listas vacias vacian las relaciones."""
        try:
            with cls.pool().connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cls._bloquear_existente(cur, isbn)
                    categoria_id = cls._categoria_id(cur, datos['categoria'])
                    cur.execute(
                        """
                        UPDATE books
                        SET title = %s, year = %s, price = %s, stock = %s,
                            format = %s, category_id = %s
                        WHERE isbn = %s
                        """,
                        (datos['titulo'], datos['anio'], datos['precio'], datos['stock'],
                         datos['formato'], categoria_id, isbn),
                    )
                    cls._reemplazar_autores(cur, isbn, datos['autores'])
                    cls._reemplazar_generos(cur, isbn, datos['generos'])
                    cls._reemplazar_imagenes(cur, isbn, datos['imagenes'], datos['titulo'])
                    return cls._cargar_libro(cur, isbn, con_conceptos=True)
        except psycopg.OperationalError as exc:
            raise DatabaseUnavailableError(str(exc)) from exc

    @classmethod
    def update(cls, isbn: str, cambios: Dict[str, Any]) -> Dict[str, Any]:
        """PATCH: solo modifica los campos presentes en `cambios`; el resto
        del libro queda exactamente como estaba."""
        try:
            with cls.pool().connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    actual = cls._bloquear_existente(cur, isbn)

                    asignaciones, valores = [], []
                    for campo, columna in COLUMNAS_ESCALARES.items():
                        if campo in cambios:
                            asignaciones.append(
                                psql.SQL("{} = %s").format(psql.Identifier(columna))
                            )
                            valores.append(cambios[campo])
                    if 'categoria' in cambios:
                        asignaciones.append(psql.SQL("category_id = %s"))
                        valores.append(cls._categoria_id(cur, cambios['categoria']))

                    if asignaciones:
                        cur.execute(
                            psql.SQL("UPDATE books SET {} WHERE isbn = %s").format(
                                psql.SQL(', ').join(asignaciones)
                            ),
                            valores + [isbn],
                        )

                    if 'autores' in cambios:
                        cls._reemplazar_autores(cur, isbn, cambios['autores'])
                    if 'generos' in cambios:
                        cls._reemplazar_generos(cur, isbn, cambios['generos'])
                    if 'imagenes' in cambios:
                        titulo = cambios.get('titulo', actual['title'])
                        cls._reemplazar_imagenes(cur, isbn, cambios['imagenes'], titulo)

                    return cls._cargar_libro(cur, isbn, con_conceptos=True)
        except psycopg.OperationalError as exc:
            raise DatabaseUnavailableError(str(exc)) from exc

    @classmethod
    def delete(cls, isbn: str) -> None:
        try:
            with cls.pool().connection() as conn:
                with conn.cursor() as cur:
                    # Autores, generos e imagenes se borran en cascada.
                    cur.execute("DELETE FROM books WHERE isbn = %s", (isbn,))
                    if cur.rowcount == 0:
                        raise BookNotFoundError(f"No existe un libro con el ISBN {isbn}.")
        except psycopg.errors.ForeignKeyViolation as exc:
            dependencias = {
                'book_concepts': 'tiene conceptos de Cloud Computing asociados',
                'clasificaciones_cloud': 'tiene clasificaciones registradas por usuarios',
            }
            motivo = dependencias.get(exc.diag.table_name, 'tiene información que depende de él')
            raise BookInUseError(
                f"No se puede eliminar el libro {isbn}: {motivo}."
            ) from exc
        except psycopg.OperationalError as exc:
            raise DatabaseUnavailableError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Auxiliares (todas reciben el cursor de la transaccion en curso)
    # ------------------------------------------------------------------
    @classmethod
    def _bloquear_existente(cls, cur, isbn: str) -> Dict[str, Any]:
        """Verifica que el libro exista y bloquea su fila hasta el fin de la
        transaccion, para que dos modificaciones simultaneas no se pisen."""
        cur.execute("SELECT isbn, title FROM books WHERE isbn = %s FOR UPDATE", (isbn,))
        fila = cur.fetchone()
        if not fila:
            raise BookNotFoundError(f"No existe un libro con el ISBN {isbn}.")
        return fila

    @classmethod
    def _categoria_id(cls, cur, nombre: str) -> int:
        cur.execute("SELECT id FROM categories WHERE lower(name) = lower(%s)", (nombre,))
        fila = cur.fetchone()
        if not fila:
            cur.execute("SELECT name FROM categories ORDER BY name")
            raise CategoryNotFoundError(nombre, [f['name'] for f in cur.fetchall()])
        return fila['id']

    @classmethod
    def _reemplazar_autores(cls, cur, isbn: str, autores: List[str]) -> None:
        cur.execute("DELETE FROM book_authors WHERE book_isbn = %s", (isbn,))
        for posicion, nombre in enumerate(autores, start=1):
            # ON CONFLICT ... DO UPDATE devuelve el id tanto si el autor es
            # nuevo como si ya existia (DO NOTHING no devolveria nada).
            cur.execute(
                """
                INSERT INTO authors (name) VALUES (%s)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
                """,
                (nombre,),
            )
            autor_id = cur.fetchone()['id']
            cur.execute(
                "INSERT INTO book_authors (book_isbn, author_id, position) VALUES (%s, %s, %s)",
                (isbn, autor_id, posicion),
            )

    @classmethod
    def _reemplazar_generos(cls, cur, isbn: str, generos: List[str]) -> None:
        cur.execute("DELETE FROM book_genres WHERE book_isbn = %s", (isbn,))
        for nombre in generos:
            cur.execute(
                """
                INSERT INTO genres (name) VALUES (%s)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
                """,
                (nombre,),
            )
            genero_id = cur.fetchone()['id']
            cur.execute(
                "INSERT INTO book_genres (book_isbn, genre_id) VALUES (%s, %s)",
                (isbn, genero_id),
            )

    @classmethod
    def _reemplazar_imagenes(cls, cur, isbn: str, imagenes: List[Dict[str, str]], titulo: str) -> None:
        """La primera imagen de la lista es la principal."""
        cur.execute("DELETE FROM book_images WHERE book_isbn = %s", (isbn,))
        for posicion, imagen in enumerate(imagenes):
            cur.execute(
                """
                INSERT INTO book_images (book_isbn, url, alt_text, is_primary, position)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (isbn, imagen['url'], imagen.get('texto_alt') or titulo, posicion == 0, posicion),
            )

    @classmethod
    def _cargar_libro(cls, cur, isbn: str, con_conceptos: bool = False) -> Optional[Dict[str, Any]]:
        cur.execute(f"{SELECT_LIBRO} WHERE b.isbn = %s", (isbn,))
        fila = cur.fetchone()
        if not fila:
            return None
        libro = cls._armar_libros(cur, [fila])[0]

        if con_conceptos:
            cur.execute(
                """
                SELECT c.name, c.definition
                FROM book_concepts bc
                JOIN concepts c ON c.id = bc.concept_id
                WHERE bc.book_isbn = %s
                ORDER BY c.id
                """,
                (isbn,),
            )
            libro['conceptos'] = [
                {'nombre': c['name'], 'definicion': c['definition']} for c in cur.fetchall()
            ]
        return libro

    @classmethod
    def _armar_libros(cls, cur, filas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Completa una lista de libros con sus autores, generos e imagenes.

        Hace TRES consultas para toda la pagina, no tres por libro: con 12
        libros por pagina, el enfoque ingenuo (una consulta por relacion y
        por libro) serian 36 viajes a la base.
        """
        if not filas:
            return []
        isbns = [f['isbn'] for f in filas]

        cur.execute(
            """
            SELECT ba.book_isbn, a.name
            FROM book_authors ba JOIN authors a ON a.id = ba.author_id
            WHERE ba.book_isbn = ANY(%s)
            ORDER BY ba.book_isbn, ba.position
            """,
            (isbns,),
        )
        autores: Dict[str, List[str]] = {}
        for f in cur.fetchall():
            autores.setdefault(f['book_isbn'], []).append(f['name'])

        cur.execute(
            """
            SELECT bg.book_isbn, g.name
            FROM book_genres bg JOIN genres g ON g.id = bg.genre_id
            WHERE bg.book_isbn = ANY(%s)
            ORDER BY bg.book_isbn, g.name
            """,
            (isbns,),
        )
        generos: Dict[str, List[str]] = {}
        for f in cur.fetchall():
            generos.setdefault(f['book_isbn'], []).append(f['name'])

        cur.execute(
            """
            SELECT book_isbn, url, alt_text, is_primary
            FROM book_images
            WHERE book_isbn = ANY(%s)
            ORDER BY book_isbn, position, id
            """,
            (isbns,),
        )
        imagenes: Dict[str, List[Dict[str, Any]]] = {}
        for f in cur.fetchall():
            imagenes.setdefault(f['book_isbn'], []).append({
                'url': f['url'],
                'texto_alt': f['alt_text'],
                'principal': f['is_primary'],
            })

        libros = []
        for f in filas:
            lista_imagenes = imagenes.get(f['isbn'], [])
            principal = next((i['url'] for i in lista_imagenes if i['principal']), None)
            libros.append({
                'isbn': f['isbn'],
                'titulo': f['title'],
                'autores': autores.get(f['isbn'], []),
                'generos': generos.get(f['isbn'], []),
                'anio': f['year'],
                'precio': float(f['price']),
                'stock': f['stock'],
                'formato': f['format'],
                'categoria': f['category'],
                'imagen_principal': principal,
                'imagenes': lista_imagenes,
            })
        return libros
