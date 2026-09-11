import sqlite3
import datetime
import logging
from typing import List, Dict, Any, Optional, Tuple
from config.config import Config
from db.authors_data import AUTHORS_BY_ISBN

logger = logging.getLogger(__name__)

# Intentar importar psycopg2 si está disponible
try:
    import psycopg2
    from psycopg2 import pool, extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    logger.warning("psycopg2 no disponible. Se utilizará SQLite como motor local de pruebas.")

class DuplicateClassificationError(Exception):
    """Excepción lanzada cuando un clasificador intenta registrar un concepto previamente clasificado."""
    pass

class ConceptNotFoundError(Exception):
    """Excepción lanzada cuando el concepto solicitado no existe en el catálogo."""
    pass

class DatabaseManager:
    _instance = None

    def __init__(self):
        self.use_pg = False
        self.pg_pool = None
        self._init_connection()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = DatabaseManager()
        return cls._instance

    def _init_connection(self):
        """Intenta conectarse a PostgreSQL; si falla o no está disponible, inicializa SQLite."""
        if PSYCOPG2_AVAILABLE:
            try:
                self.pg_pool = psycopg2.pool.SimpleConnectionPool(
                    1, 10,
                    host=Config.DB_HOST,
                    port=Config.DB_PORT,
                    database=Config.DB_NAME,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD,
                    connect_timeout=2
                )
                self.use_pg = True
                logger.info("Conexión exitosa al pool de PostgreSQL.")
                return
            except Exception as e:
                logger.warning(f"No fue posible conectar a PostgreSQL ({e}). Usando SQLite local.")
                self.use_pg = False
        else:
            self.use_pg = False

        self._init_sqlite_db()

    def _init_sqlite_db(self):
        """Inicializa la base de datos local SQLite con las tablas del monolito y del módulo SOAP."""
        Config.SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(Config.SQLITE_DB_PATH) as conn:
            cursor = conn.cursor()
            # 1. Tablas del Monolito
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS books (
                isbn TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                year INTEGER NOT NULL,
                price REAL NOT NULL,
                stock INTEGER NOT NULL,
                format TEXT,
                category_id INTEGER REFERENCES categories(id)
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS concepts (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                definition TEXT NOT NULL
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS book_concepts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_isbn TEXT NOT NULL REFERENCES books(isbn),
                concept_id INTEGER NOT NULL REFERENCES concepts(id),
                UNIQUE (book_isbn, concept_id)
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'customer'
            );
            """)

            # 2. Tablas del Módulo SOAP
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS clasificadores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                apellidos TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS clasificaciones_cloud (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                concepto_id INTEGER NOT NULL REFERENCES concepts(id),
                libro_isbn TEXT NOT NULL REFERENCES books(isbn),
                clasificador_id INTEGER NOT NULL REFERENCES clasificadores(id),
                modelo_cloud TEXT NOT NULL CHECK(modelo_cloud IN ('IaaS', 'PaaS', 'SaaS', 'FaaS')),
                fecha_clasificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_origen TEXT DEFAULT '127.0.0.1',
                cliente_tipo TEXT DEFAULT 'Desktop-GUI-Client',
                cliente_id TEXT DEFAULT 'CLI-DEFAULT',
                UNIQUE (clasificador_id, concepto_id)
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS clientes_servidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo_cliente TEXT NOT NULL,
                identificador_cliente TEXT NOT NULL UNIQUE,
                peticiones_atendidas INTEGER NOT NULL DEFAULT 1,
                primera_peticion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ultima_peticion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 3. Precarga de datos del monolito si está vacío
            cursor.execute("SELECT COUNT(*) FROM concepts")
            if cursor.fetchone()[0] == 0:
                self._seed_sqlite_data(cursor)
            conn.commit()

    def _seed_sqlite_data(self, cursor):
        """Inserta datos de catálogo extraídos de library.xml."""
        categories = [(1, 'Cloud'), (2, 'Architecture'), (3, 'Programming'), (4, 'DevOps'),
                      (5, 'Business'), (6, 'Data Science'), (7, 'AI'), (8, 'Fiction'), (9, 'Security')]
        cursor.executemany("INSERT OR IGNORE INTO categories (id, name) VALUES (?, ?)", categories)

        books = [
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
        ]
        cursor.executemany("INSERT OR IGNORE INTO books (isbn, title, year, price, stock, format, category_id) VALUES (?, ?, ?, ?, ?, ?, ?)", books)

        concepts = [
            (1, 'IaaS', 'En el contexto de «Cloud Computing: Concepts, Technology & Architecture», IaaS describe el uso de infraestructura virtualizada bajo demanda, como máquinas virtuales, redes y almacenamiento, donde el proveedor administra el hardware y el usuario controla buena parte del sistema operativo y las aplicaciones.'),
            (2, 'PaaS', 'En el contexto de «Cloud Computing: Concepts, Technology & Architecture», PaaS proporciona una plataforma administrada para desarrollar y desplegar aplicaciones sin gestionar directamente los servidores, incorporando runtimes, servicios, herramientas y mecanismos de escalamiento.'),
            (3, 'SaaS', 'Software como Servicio: Aplicaciones completas entregadas a través de Internet bajo modelo de suscripción, administradas totalmente por el proveedor.'),
            (4, 'FaaS', 'Función como Servicio (Serverless): Modelo de ejecución donde el código se ejecuta en respuesta a eventos sin requerir aprovisionamiento de infraestructura.')
        ]
        cursor.executemany("INSERT OR IGNORE INTO concepts (id, name, definition) VALUES (?, ?, ?)", concepts)

        book_concepts = [
            ('9780134092669', 1),
            ('9780134092669', 2),
            ('9781118795555', 3),
            ('9781449311756', 4)
        ]
        cursor.executemany("INSERT OR IGNORE INTO book_concepts (book_isbn, concept_id) VALUES (?, ?)", book_concepts)

    def get_connection(self):
        if self.use_pg and self.pg_pool:
            return self.pg_pool.getconn()
        return sqlite3.connect(Config.SQLITE_DB_PATH)

    def release_connection(self, conn):
        if self.use_pg and self.pg_pool and conn:
            self.pg_pool.putconn(conn)
        elif conn:
            conn.close()

    def record_client_request(self, tipo_cliente: str, identificador_cliente: str):
        """Registra o actualiza el contador de peticiones por cliente atendido."""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            if self.use_pg:
                cur.execute("""
                    INSERT INTO clientes_servidos (tipo_cliente, identificador_cliente, peticiones_atendidas, ultima_peticion)
                    VALUES (%s, %s, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT (identificador_cliente) 
                    DO UPDATE SET peticiones_atendidas = clientes_servidos.peticiones_atendidas + 1,
                                  ultima_peticion = CURRENT_TIMESTAMP;
                """, (tipo_cliente, identificador_cliente))
            else:
                cur.execute("""
                    INSERT INTO clientes_servidos (tipo_cliente, identificador_cliente, peticiones_atendidas, ultima_peticion)
                    VALUES (?, ?, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT(identificador_cliente)
                    DO UPDATE SET peticiones_atendidas = clientes_servidos.peticiones_atendidas + 1,
                                  ultima_peticion = CURRENT_TIMESTAMP;
                """, (tipo_cliente, identificador_cliente))
            conn.commit()
        except Exception as e:
            if conn: conn.rollback()
            logger.error(f"Error al registrar cliente servido: {e}")
        finally:
            self.release_connection(conn)

    def get_pending_concepts(self, clasificador_email: Optional[str] = None) -> List[Dict[str, Any]]:
        """Recupera los conceptos pendientes del catálogo, opcionalmente filtrando los no clasificados por un usuario."""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            if clasificador_email:
                query = """
                    SELECT c.id, c.name, c.definition, b.isbn, b.title, b.year, COALESCE(cat.name, 'Cloud')
                    FROM concepts c
                    JOIN book_concepts bc ON c.id = bc.concept_id
                    JOIN books b ON bc.book_isbn = b.isbn
                    LEFT JOIN categories cat ON b.category_id = cat.id
                    WHERE c.id NOT IN (
                        SELECT cc.concepto_id 
                        FROM clasificaciones_cloud cc
                        JOIN clasificadores cl ON cc.clasificador_id = cl.id
                        WHERE cl.email = %s
                    )
                    ORDER BY c.id ASC
                """ if self.use_pg else """
                    SELECT c.id, c.name, c.definition, b.isbn, b.title, b.year, COALESCE(cat.name, 'Cloud')
                    FROM concepts c
                    JOIN book_concepts bc ON c.id = bc.concept_id
                    JOIN books b ON bc.book_isbn = b.isbn
                    LEFT JOIN categories cat ON b.category_id = cat.id
                    WHERE c.id NOT IN (
                        SELECT cc.concepto_id 
                        FROM clasificaciones_cloud cc
                        JOIN clasificadores cl ON cc.clasificador_id = cl.id
                        WHERE cl.email = ?
                    )
                    ORDER BY c.id ASC
                """
                cur.execute(query, (clasificador_email,))
            else:
                query = """
                    SELECT c.id, c.name, c.definition, b.isbn, b.title, b.year, COALESCE(cat.name, 'Cloud')
                    FROM concepts c
                    JOIN book_concepts bc ON c.id = bc.concept_id
                    JOIN books b ON bc.book_isbn = b.isbn
                    LEFT JOIN categories cat ON b.category_id = cat.id
                    ORDER BY c.id ASC
                """
                cur.execute(query)
            
            rows = cur.fetchall()
            results = []
            for r in rows:
                results.append({
                    'concepto_id': r[0],
                    'concepto_nombre': r[1],
                    'definicion': r[2],
                    'libro_isbn': r[3],
                    'libro_titulo': r[4],
                    'libro_anio': r[5],
                    'categoria': r[6]
                })
            return results
        finally:
            self.release_connection(conn)

    def register_classification(self, nombre: str, apellidos: str, email: str,
                                concepto_id: int, libro_isbn: str, modelo_cloud: str,
                                cliente_tipo: str = "Desktop-GUI-Client",
                                cliente_id: str = "CLI-DEFAULT",
                                ip_origen: str = "127.0.0.1") -> int:
        """Registra una nueva clasificación asegurando atomicidad y detección de duplicados."""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            # 1. Verificar si el concepto existe
            cur.execute("SELECT id FROM concepts WHERE id = %s" if self.use_pg else "SELECT id FROM concepts WHERE id = ?", (concepto_id,))
            if not cur.fetchone():
                raise ConceptNotFoundError(f"El concepto con ID {concepto_id} no existe en el catálogo.")

            # 2. Obtener o crear clasificador
            if self.use_pg:
                cur.execute("""
                    INSERT INTO clasificadores (nombre, apellidos, email)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (email) DO UPDATE SET nombre = EXCLUDED.nombre, apellidos = EXCLUDED.apellidos
                    RETURNING id;
                """, (nombre, apellidos, email))
                clasificador_id = cur.fetchone()[0]
            else:
                cur.execute("INSERT OR IGNORE INTO clasificadores (nombre, apellidos, email) VALUES (?, ?, ?)", (nombre, apellidos, email))
                cur.execute("SELECT id FROM clasificadores WHERE email = ?", (email,))
                clasificador_id = cur.fetchone()[0]

            # 3. Insertar la clasificación en clasificaciones_cloud
            if self.use_pg:
                cur.execute("""
                    INSERT INTO clasificaciones_cloud (concepto_id, libro_isbn, clasificador_id, modelo_cloud, ip_origen, cliente_tipo, cliente_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                """, (concepto_id, libro_isbn, clasificador_id, modelo_cloud, ip_origen, cliente_tipo, cliente_id))
                clasificacion_id = cur.fetchone()[0]
            else:
                cur.execute("""
                    INSERT INTO clasificaciones_cloud (concepto_id, libro_isbn, clasificador_id, modelo_cloud, ip_origen, cliente_tipo, cliente_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (concepto_id, libro_isbn, clasificador_id, modelo_cloud, ip_origen, cliente_tipo, cliente_id))
                clasificacion_id = cur.lastrowid

            conn.commit()
            return clasificacion_id

        except Exception as e:
            if conn: conn.rollback()
            # Detectar violación de unicidad (clasificación duplicada)
            err_str = str(e).lower()
            if "unique" in err_str or "duplicate" in err_str or "uq_clasificador_concepto" in err_str:
                raise DuplicateClassificationError(f"El usuario con email '{email}' ya ha clasificado previamente el concepto {concepto_id}.")
            raise e
        finally:
            self.release_connection(conn)

    def get_user_progress(self, email: str) -> Dict[str, Any]:
        """Obtiene métricas de progreso de clasificación para un usuario específico."""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            # Total de conceptos globales
            cur.execute("SELECT COUNT(*) FROM concepts")
            total_conceptos = cur.fetchone()[0]

            # Datos del clasificador
            cur.execute("SELECT id, nombre, apellidos FROM clasificadores WHERE email = %s" if self.use_pg else "SELECT id, nombre, apellidos FROM clasificadores WHERE email = ?", (email,))
            user_row = cur.fetchone()

            if not user_row:
                return {
                    'email': email,
                    'nombre_completo': 'Usuario No Registrado',
                    'total_clasificados': 0,
                    'total_pendientes': total_conceptos,
                    'porcentaje_progreso': 0.0
                }

            user_id, nombre, apellidos = user_row
            cur.execute("SELECT COUNT(*) FROM clasificaciones_cloud WHERE clasificador_id = %s" if self.use_pg else "SELECT COUNT(*) FROM clasificaciones_cloud WHERE clasificador_id = ?", (user_id,))
            total_clasificados = cur.fetchone()[0]
            total_pendientes = max(0, total_conceptos - total_clasificados)
            porcentaje = round((total_clasificados / total_conceptos * 100.0), 2) if total_conceptos > 0 else 0.0

            return {
                'email': email,
                'nombre_completo': f"{nombre} {apellidos}",
                'total_clasificados': total_clasificados,
                'total_pendientes': total_pendientes,
                'porcentaje_progreso': porcentaje
            }
        finally:
            self.release_connection(conn)

    @staticmethod
    def _book_extras(isbn: str) -> Dict[str, Any]:
        """Campos de un libro que no viven en la base de datos relacional:
        autores (referencia estática extraída de library.xml) e imagen de
        portada (URL determinística derivada del ISBN vía Open Library Covers)."""
        return {
            'autores': AUTHORS_BY_ISBN.get(isbn, []),
            'imagen': f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
        }

    def get_all_books(self, page: int = 1, page_size: int = 12) -> Dict[str, Any]:
        """Recupera el catálogo de libros paginado. page/page_size controlan el
        recorte devuelto; total siempre refleja el conteo global del catálogo."""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM books")
            total = cur.fetchone()[0]

            offset = max(0, (page - 1) * page_size)
            query = """
                SELECT b.isbn, b.title, b.year, b.price, b.stock, b.format, COALESCE(cat.name, 'Sin categoría')
                FROM books b
                LEFT JOIN categories cat ON b.category_id = cat.id
                ORDER BY b.title ASC
                LIMIT %s OFFSET %s
            """ if self.use_pg else """
                SELECT b.isbn, b.title, b.year, b.price, b.stock, b.format, COALESCE(cat.name, 'Sin categoría')
                FROM books b
                LEFT JOIN categories cat ON b.category_id = cat.id
                ORDER BY b.title ASC
                LIMIT ? OFFSET ?
            """
            cur.execute(query, (page_size, offset))
            rows = cur.fetchall()
            books = [
                {
                    'isbn': r[0],
                    'titulo': r[1],
                    'anio': r[2],
                    'precio': float(r[3]),
                    'stock': r[4],
                    'formato': r[5],
                    'categoria': r[6],
                    **self._book_extras(r[0])
                } for r in rows
            ]
            total_pages = max(1, (total + page_size - 1) // page_size)
            return {
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages,
                'libros': books
            }
        finally:
            self.release_connection(conn)

    def get_book_by_isbn(self, isbn: str) -> Optional[Dict[str, Any]]:
        """Recupera un único libro por su ISBN, o None si no existe."""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            query = """
                SELECT b.isbn, b.title, b.year, b.price, b.stock, b.format, COALESCE(cat.name, 'Sin categoría')
                FROM books b
                LEFT JOIN categories cat ON b.category_id = cat.id
                WHERE b.isbn = %s
            """ if self.use_pg else """
                SELECT b.isbn, b.title, b.year, b.price, b.stock, b.format, COALESCE(cat.name, 'Sin categoría')
                FROM books b
                LEFT JOIN categories cat ON b.category_id = cat.id
                WHERE b.isbn = ?
            """
            cur.execute(query, (isbn,))
            row = cur.fetchone()
            if not row:
                return None
            return {
                'isbn': row[0],
                'titulo': row[1],
                'anio': row[2],
                'precio': float(row[3]),
                'stock': row[4],
                'formato': row[5],
                'categoria': row[6],
                **self._book_extras(row[0])
            }
        finally:
            self.release_connection(conn)

    def get_all_concepts_with_books(self) -> List[Dict[str, Any]]:
        """Recupera todos los conceptos de Cloud Computing (IaaS, PaaS, SaaS, FaaS)
        junto con los libros del catálogo asociados a cada uno."""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, name, definition FROM concepts ORDER BY id ASC")
            concept_rows = cur.fetchall()

            book_query = """
                SELECT b.isbn, b.title, b.year
                FROM books b
                JOIN book_concepts bc ON b.isbn = bc.book_isbn
                WHERE bc.concept_id = %s
                ORDER BY b.title ASC
            """ if self.use_pg else """
                SELECT b.isbn, b.title, b.year
                FROM books b
                JOIN book_concepts bc ON b.isbn = bc.book_isbn
                WHERE bc.concept_id = ?
                ORDER BY b.title ASC
            """

            results = []
            for concepto_id, nombre, definicion in concept_rows:
                cur.execute(book_query, (concepto_id,))
                book_rows = cur.fetchall()
                results.append({
                    'concepto_id': concepto_id,
                    'nombre': nombre,
                    'definicion': definicion,
                    'libros': [
                        {'isbn': br[0], 'titulo': br[1], 'anio': br[2]} for br in book_rows
                    ]
                })
            return results
        finally:
            self.release_connection(conn)

    def get_books_minimal_with_images(self) -> List[Dict[str, Any]]:
        """Recupera los datos mínimos de cada libro (ISBN y título) junto con la
        URL de su imagen de portada, derivada del ISBN mediante el servicio
        público Open Library Covers."""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT isbn, title FROM books ORDER BY title ASC")
            rows = cur.fetchall()
            return [
                {
                    'isbn': r[0],
                    'titulo': r[1],
                    'imagen': f"https://covers.openlibrary.org/b/isbn/{r[0]}-L.jpg"
                } for r in rows
            ]
        finally:
            self.release_connection(conn)

    def get_model_statistics(self) -> Dict[str, Any]:
        """Obtiene el conteo total agregado de clasificaciones por cada modelo Cloud."""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    COUNT(CASE WHEN modelo_cloud = 'IaaS' THEN 1 END) AS total_iaas,
                    COUNT(CASE WHEN modelo_cloud = 'PaaS' THEN 1 END) AS total_paas,
                    COUNT(CASE WHEN modelo_cloud = 'SaaS' THEN 1 END) AS total_saas,
                    COUNT(CASE WHEN modelo_cloud = 'FaaS' THEN 1 END) AS total_faas,
                    COUNT(*) AS total_general
                FROM clasificaciones_cloud
            """)
            row = cur.fetchone()
            return {
                'total_iaas': row[0] or 0,
                'total_paas': row[1] or 0,
                'total_saas': row[2] or 0,
                'total_faas': row[3] or 0,
                'total_general': row[4] or 0,
                'timestamp_consulta': datetime.datetime.now().isoformat()
            }
        finally:
            self.release_connection(conn)
