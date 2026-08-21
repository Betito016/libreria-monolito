// src/modules/catalogo/catalogo.factory.js
//
// Los catálogos "autores", "generos", "formatos" y "conceptos" son
// estructuralmente idénticos: una tabla con id + una columna de texto
// única, y un CRUD idéntico sobre ella. En vez de duplicar modelo/
// controlador/rutas/vistas cuatro veces, esta fábrica genera un módulo
// MVC completo por catálogo, reutilizando las mismas vistas EJS.
// Sigue de todas formas el patrón MVC: separa modelo (acceso a datos),
// controlador (orquestación de la petición/respuesta) y rutas.
const express = require('express');
const pool = require('../../config/db');
const { requireAdmin } = require('../../middlewares/auth');

function crearCatalogo({ tabla, columna, etiqueta, etiquetaPlural, base }) {
  // ---------------- MODEL ----------------
  const model = {
    async listar() {
      const { rows } = await pool.query(
        `SELECT id, ${columna} FROM ${tabla} ORDER BY ${columna} ASC`
      );
      return rows;
    },
    async obtener(id) {
      const { rows } = await pool.query(
        `SELECT id, ${columna} FROM ${tabla} WHERE id = $1`,
        [id]
      );
      return rows[0];
    },
    async crear(valor) {
      const { rows } = await pool.query(
        `INSERT INTO ${tabla} (${columna}) VALUES ($1) RETURNING id`,
        [valor]
      );
      return rows[0].id;
    },
    async actualizar(id, valor) {
      await pool.query(`UPDATE ${tabla} SET ${columna} = $1 WHERE id = $2`, [valor, id]);
    },
    async eliminar(id) {
      await pool.query(`DELETE FROM ${tabla} WHERE id = $1`, [id]);
    },
  };

  // ---------------- CONTROLLER ----------------
  const controller = {
    index: async (req, res, next) => {
      try {
        const items = await model.listar();
        res.render('catalogo/views/list', { items, columna, etiqueta, etiquetaPlural, base });
      } catch (err) { next(err); }
    },
    nuevoForm: (req, res) => {
      res.render('catalogo/views/form', { item: null, columna, etiqueta, base });
    },
    crear: async (req, res, next) => {
      try {
        const valor = (req.body[columna] || '').trim();
        if (!valor) {
          req.session.flash = { type: 'error', message: `${etiqueta} no puede estar vacío.` };
          return res.redirect(`${base}/nuevo`);
        }
        await model.crear(valor);
        req.session.flash = { type: 'success', message: `${etiqueta} creado correctamente.` };
        res.redirect(base);
      } catch (err) {
        req.session.flash = { type: 'error', message: `Ya existe un registro con ese valor.` };
        res.redirect(`${base}/nuevo`);
      }
    },
    editarForm: async (req, res, next) => {
      try {
        const item = await model.obtener(req.params.id);
        if (!item) return res.status(404).render('404');
        res.render('catalogo/views/form', { item, columna, etiqueta, base });
      } catch (err) { next(err); }
    },
    actualizar: async (req, res, next) => {
      try {
        const valor = (req.body[columna] || '').trim();
        await model.actualizar(req.params.id, valor);
        req.session.flash = { type: 'success', message: `${etiqueta} actualizado correctamente.` };
        res.redirect(base);
      } catch (err) {
        req.session.flash = { type: 'error', message: `No se pudo actualizar (¿valor duplicado?).` };
        res.redirect(`${base}/${req.params.id}/editar`);
      }
    },
    eliminar: async (req, res, next) => {
      try {
        await model.eliminar(req.params.id);
        req.session.flash = { type: 'success', message: `${etiqueta} eliminado.` };
        res.redirect(base);
      } catch (err) {
        req.session.flash = { type: 'error', message: `No se puede eliminar: está en uso por uno o más libros.` };
        res.redirect(base);
      }
    },
  };

  // ---------------- ROUTES ----------------
  const router = express.Router();
  router.use(requireAdmin); // toda la gestión de catálogos es exclusiva del administrador
  router.get('/', controller.index);
  router.get('/nuevo', controller.nuevoForm);
  router.post('/', controller.crear);
  router.get('/:id/editar', controller.editarForm);
  router.post('/:id', controller.actualizar);
  router.post('/:id/eliminar', controller.eliminar);

  return { model, controller, router };
}

module.exports = crearCatalogo;
