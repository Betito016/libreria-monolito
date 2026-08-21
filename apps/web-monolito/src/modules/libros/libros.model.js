// src/modules/libros/libros.model.js
// Acceso a datos del agregado "libro": tabla principal + relaciones
// M:N (autores, generos), 1:N (imagenes) y M:N con atributo
// (libro_concepto, que lleva la definición particular del libro).
const pool = require('../../config/db');

async function listar(busqueda) {
  const params = [];
  let where = '';
  if (busqueda) {
    params.push(`%${busqueda}%`);
    where = 'WHERE l.titulo ILIKE $1 OR l.isbn ILIKE $1';
  }
  const { rows } = await pool.query(
    `SELECT l.id, l.isbn, l.titulo, l.anio_publicacion, l.precio, l.stock,
            f.nombre AS formato,
            COALESCE(string_agg(DISTINCT a.nombre, ', '), '—') AS autores,
            (SELECT im.url_imagen FROM imagenes im WHERE im.libro_id = l.id
               ORDER BY im.es_principal DESC, im.orden ASC LIMIT 1) AS portada
       FROM libros l
       JOIN formatos f ON f.id = l.formato_id
       LEFT JOIN libro_autor la ON la.libro_id = l.id
       LEFT JOIN autores a ON a.id = la.autor_id
       ${where}
       GROUP BY l.id, f.nombre
       ORDER BY l.titulo ASC`,
    params
  );
  return rows;
}

async function obtenerBasico(id) {
  const { rows } = await pool.query(
    `SELECT l.*, f.nombre AS formato_nombre
       FROM libros l
       JOIN formatos f ON f.id = l.formato_id
      WHERE l.id = $1`,
    [id]
  );
  return rows[0];
}

async function obtenerDetalle(id) {
  const libro = await obtenerBasico(id);
  if (!libro) return null;

  const [autores, generos, imagenes, conceptos] = await Promise.all([
    pool.query(
      `SELECT a.id, a.nombre FROM autores a
         JOIN libro_autor la ON la.autor_id = a.id
        WHERE la.libro_id = $1 ORDER BY a.nombre`,
      [id]
    ),
    pool.query(
      `SELECT g.id, g.nombre FROM generos g
         JOIN libro_genero lg ON lg.genero_id = g.id
        WHERE lg.libro_id = $1 ORDER BY g.nombre`,
      [id]
    ),
    pool.query(
      `SELECT id, url_imagen, texto_alt, es_principal, orden
         FROM imagenes WHERE libro_id = $1
        ORDER BY es_principal DESC, orden ASC`,
      [id]
    ),
    pool.query(
      `SELECT c.id AS concepto_id, c.termino, lc.definicion
         FROM libro_concepto lc
         JOIN conceptos c ON c.id = lc.concepto_id
        WHERE lc.libro_id = $1 ORDER BY c.termino`,
      [id]
    ),
  ]);

  return {
    ...libro,
    autores: autores.rows,
    generos: generos.rows,
    imagenes: imagenes.rows,
    conceptos: conceptos.rows,
  };
}

async function crear(datos) {
  const { isbn, titulo, anio_publicacion, precio, stock, formato_id } = datos;
  const { rows } = await pool.query(
    `INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, formato_id)
     VALUES ($1,$2,$3,$4,$5,$6) RETURNING id`,
    [isbn, titulo, anio_publicacion || null, precio, stock, formato_id]
  );
  return rows[0].id;
}

async function actualizar(id, datos) {
  const { isbn, titulo, anio_publicacion, precio, stock, formato_id } = datos;
  await pool.query(
    `UPDATE libros SET isbn=$1, titulo=$2, anio_publicacion=$3, precio=$4,
            stock=$5, formato_id=$6 WHERE id=$7`,
    [isbn, titulo, anio_publicacion || null, precio, stock, formato_id, id]
  );
}

async function eliminar(id) {
  await pool.query(`DELETE FROM libros WHERE id = $1`, [id]);
}

// --- Relación M:N libro-autor ---
async function asignarAutores(libroId, autorIds) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query('DELETE FROM libro_autor WHERE libro_id = $1', [libroId]);
    for (const autorId of autorIds) {
      await client.query(
        'INSERT INTO libro_autor (libro_id, autor_id) VALUES ($1,$2)',
        [libroId, autorId]
      );
    }
    await client.query('COMMIT');
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

// --- Relación M:N libro-genero ---
async function asignarGeneros(libroId, generoIds) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query('DELETE FROM libro_genero WHERE libro_id = $1', [libroId]);
    for (const generoId of generoIds) {
      await client.query(
        'INSERT INTO libro_genero (libro_id, genero_id) VALUES ($1,$2)',
        [libroId, generoId]
      );
    }
    await client.query('COMMIT');
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

// --- Imágenes (1:N) ---
async function agregarImagen(libroId, { url_imagen, texto_alt, esPrincipal }) {
  if (esPrincipal) {
    await pool.query('UPDATE imagenes SET es_principal = FALSE WHERE libro_id = $1', [libroId]);
  }
  await pool.query(
    `INSERT INTO imagenes (libro_id, url_imagen, texto_alt, es_principal)
     VALUES ($1,$2,$3,$4)`,
    [libroId, url_imagen, texto_alt || null, !!esPrincipal]
  );
}

async function obtenerImagen(id) {
  const { rows } = await pool.query('SELECT * FROM imagenes WHERE id = $1', [id]);
  return rows[0];
}

async function eliminarImagen(id) {
  await pool.query('DELETE FROM imagenes WHERE id = $1', [id]);
}

async function marcarImagenPrincipal(id, libroId) {
  await pool.query('UPDATE imagenes SET es_principal = FALSE WHERE libro_id = $1', [libroId]);
  await pool.query('UPDATE imagenes SET es_principal = TRUE WHERE id = $1', [id]);
}

// --- Conceptos y definiciones por libro (M:N con atributo) ---
async function upsertConcepto(libroId, conceptoId, definicion) {
  await pool.query(
    `INSERT INTO libro_concepto (libro_id, concepto_id, definicion)
     VALUES ($1,$2,$3)
     ON CONFLICT (libro_id, concepto_id) DO UPDATE SET definicion = EXCLUDED.definicion`,
    [libroId, conceptoId, definicion]
  );
}

async function eliminarConcepto(libroId, conceptoId) {
  await pool.query(
    'DELETE FROM libro_concepto WHERE libro_id = $1 AND concepto_id = $2',
    [libroId, conceptoId]
  );
}

async function crearConceptoSiNoExiste(termino) {
  const { rows } = await pool.query(
    `INSERT INTO conceptos (termino) VALUES ($1)
     ON CONFLICT (termino) DO UPDATE SET termino = EXCLUDED.termino
     RETURNING id`,
    [termino]
  );
  return rows[0].id;
}

// --- Listas auxiliares para formularios ---
async function listarAutores() {
  const { rows } = await pool.query('SELECT id, nombre FROM autores ORDER BY nombre');
  return rows;
}
async function listarGeneros() {
  const { rows } = await pool.query('SELECT id, nombre FROM generos ORDER BY nombre');
  return rows;
}
async function listarFormatos() {
  const { rows } = await pool.query('SELECT id, nombre FROM formatos ORDER BY nombre');
  return rows;
}
async function listarConceptos() {
  const { rows } = await pool.query('SELECT id, termino FROM conceptos ORDER BY termino');
  return rows;
}

module.exports = {
  listar,
  obtenerBasico,
  obtenerDetalle,
  crear,
  actualizar,
  eliminar,
  asignarAutores,
  asignarGeneros,
  agregarImagen,
  obtenerImagen,
  eliminarImagen,
  marcarImagenPrincipal,
  upsertConcepto,
  eliminarConcepto,
  crearConceptoSiNoExiste,
  listarAutores,
  listarGeneros,
  listarFormatos,
  listarConceptos,
};
