// src/modules/usuarios/usuarios.model.js
const pool = require('../../config/db');

module.exports = {
  async listar() {
    const { rows } = await pool.query(
      `SELECT id, nombre, email, rol, activo, fecha_registro
         FROM usuarios ORDER BY fecha_registro DESC`
    );
    return rows;
  },

  async obtenerPorId(id) {
    const { rows } = await pool.query(`SELECT * FROM usuarios WHERE id = $1`, [id]);
    return rows[0];
  },

  async obtenerPorEmail(email) {
    const { rows } = await pool.query(`SELECT * FROM usuarios WHERE email = $1`, [email]);
    return rows[0];
  },

  async crear({ nombre, email, passwordHash, rol }) {
    const { rows } = await pool.query(
      `INSERT INTO usuarios (nombre, email, password_hash, rol)
       VALUES ($1,$2,$3,$4) RETURNING id`,
      [nombre, email, passwordHash, rol]
    );
    return rows[0].id;
  },

  async actualizarRolYEstado(id, { rol, activo }) {
    await pool.query(
      `UPDATE usuarios SET rol = $1, activo = $2 WHERE id = $3`,
      [rol, activo, id]
    );
  },

  async eliminar(id) {
    await pool.query(`DELETE FROM usuarios WHERE id = $1`, [id]);
  },
};
