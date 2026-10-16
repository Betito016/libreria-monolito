"""
Acceso a libreria_db para el microservicio authors (authors y book_authors).
"""
import re
from typing import Any, Dict, List, Optional

import psycopg

from libreria_common.bd import BaseDatos
from libreria_common.validacion import Conflicto, NoEncontrado, ValidacionError


def _isbns(valor: Any) -> List[str]:
    if not isinstance(valor, list):
        raise ValidacionError('ERR_TIPO_INVALIDO', "El campo 'libros' debe ser una lista de ISBN.", campo_invalido='libros')
    isbns = []
    for v in valor:
        isbn = re.sub(r'[\s-]', '', str(v)).upper()
        if not re.match(r'^(\d{9}[\dX]|\d{13})$', isbn):
            raise ValidacionError('ERR_ISBN_INVALIDO', f"ISBN inválido en 'libros': {v}", campo_invalido='libros')
        if isbn not in isbns:
            isbns.append(isbn)
    return isbns


class RepositorioAutores:

    def __init__(self, bd: BaseDatos):
        self.bd = bd

    def listar(self, nombre: Optional[str], page: int, page_size: int) -> Dict[str, Any]:
        donde, params = ('WHERE a.name ILIKE %s', [f'%{nombre}%']) if nombre else ('', [])
        with self.bd.cursor() as cur:
            cur.execute(f'SELECT count(*) AS n FROM authors a {donde}', params)
            total = cur.fetchone()['n']
            cur.execute(f"""SELECT a.id, a.name AS nombre, a.nacionalidad, count(ba.book_isbn)::int AS total_libros
                            FROM authors a LEFT JOIN book_authors ba ON ba.author_id = a.id {donde}
                            GROUP BY a.id ORDER BY a.name LIMIT %s OFFSET %s""",
                        params + [page_size, (page - 1) * page_size])
            return {'total': total, 'autores': cur.fetchall()}

    def obtener(self, autor_id: int) -> Dict[str, Any]:
        with self.bd.cursor() as cur:
            cur.execute('SELECT id, name AS nombre, nacionalidad, biografia, creado_en FROM authors WHERE id = %s',
                        (autor_id,))
            autor = cur.fetchone()
            if not autor:
                raise NoEncontrado(f'No existe el autor {autor_id}.')
            cur.execute("""SELECT b.isbn, b.title AS titulo, b.year AS anio, ba.position AS posicion
                           FROM book_authors ba JOIN books b ON b.isbn = ba.book_isbn
                           WHERE ba.author_id = %s ORDER BY b.title""", (autor_id,))
            autor['libros'] = cur.fetchall()
        autor['creado_en'] = autor['creado_en'].isoformat() if autor.get('creado_en') else None
        autor['total_libros'] = len(autor['libros'])
        return autor

    def _relacionar(self, cur, autor_id: int, isbns: List[str]) -> None:
        if isbns:
            cur.execute('SELECT isbn FROM books WHERE isbn = ANY(%s)', (isbns,))
            existentes = {f['isbn'] for f in cur.fetchall()}
            faltan = [i for i in isbns if i not in existentes]
            if faltan:
                raise ValidacionError('ERR_LIBRO_INEXISTENTE', f"No existen los libros: {', '.join(faltan)}.",
                                      campo_invalido='libros')
        cur.execute('DELETE FROM book_authors WHERE author_id = %s', (autor_id,))
        for isbn in isbns:
            # posicion: despues de los autores que el libro ya tiene
            cur.execute("""INSERT INTO book_authors (book_isbn, author_id, position)
                           VALUES (%s, %s, (SELECT coalesce(max(position), 0) + 1 FROM book_authors WHERE book_isbn = %s))""",
                        (isbn, autor_id, isbn))

    def crear(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with self.bd.cursor() as cur:
                cur.execute('INSERT INTO authors (name, nacionalidad, biografia) VALUES (%s, %s, %s) RETURNING id',
                            (datos['nombre'], datos.get('nacionalidad'), datos.get('biografia')))
                autor_id = cur.fetchone()['id']
                if 'libros' in datos:
                    self._relacionar(cur, autor_id, _isbns(datos['libros']))
        except psycopg.errors.UniqueViolation:
            raise Conflicto('ERR_AUTOR_DUPLICADO', f"Ya existe un autor llamado '{datos['nombre']}'.")
        return self.obtener(autor_id)

    def modificar(self, autor_id: int, cambios: Dict[str, Any]) -> Dict[str, Any]:
        self.obtener(autor_id)
        columnas = {'nombre': 'name', 'nacionalidad': 'nacionalidad', 'biografia': 'biografia'}
        try:
            with self.bd.cursor() as cur:
                presentes = [c for c in columnas if c in cambios]
                if presentes:
                    asignaciones = ', '.join(f'{columnas[c]} = %s' for c in presentes)
                    cur.execute(f'UPDATE authors SET {asignaciones} WHERE id = %s',
                                [cambios[c] for c in presentes] + [autor_id])
                if 'libros' in cambios:
                    self._relacionar(cur, autor_id, _isbns(cambios['libros']))
        except psycopg.errors.UniqueViolation:
            raise Conflicto('ERR_AUTOR_DUPLICADO', f"Ya existe un autor llamado '{cambios.get('nombre')}'.")
        return self.obtener(autor_id)

    def eliminar(self, autor_id: int) -> Dict[str, Any]:
        autor = self.obtener(autor_id)
        if autor['libros']:
            raise Conflicto('ERR_AUTOR_CON_LIBROS',
                            f"El autor tiene {len(autor['libros'])} libro(s) asociado(s). Quita la relación "
                            f"(PATCH {{\"libros\": []}}) antes de eliminarlo.")
        with self.bd.cursor() as cur:
            cur.execute('DELETE FROM authors WHERE id = %s', (autor_id,))
        return autor
