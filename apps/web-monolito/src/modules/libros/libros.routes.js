// src/modules/libros/libros.routes.js
const express = require('express');
const controller = require('./libros.controller');
const upload = require('../../middlewares/upload');
const { requireAdmin, requireLogin } = require('../../middlewares/auth');

const router = express.Router();

// Catálogo: lectura reservada a usuarios autenticados (RF-04)
router.get('/', requireLogin, controller.index);
router.get('/nuevo', requireAdmin, controller.nuevoForm);
router.post('/', requireAdmin, controller.crear);
router.get('/:id', requireLogin, controller.detalle);
router.get('/:id/editar', requireAdmin, controller.editarForm);
router.post('/:id', requireAdmin, controller.actualizar);
router.post('/:id/eliminar', requireAdmin, controller.eliminar);

// Imágenes (1:N) — multipart/form-data, nunca JSON
router.post('/:id/imagenes', requireAdmin, upload.single('imagen'), controller.subirImagen);
router.post('/:id/imagenes/:imgId/eliminar', requireAdmin, controller.eliminarImagen);
router.post('/:id/imagenes/:imgId/principal', requireAdmin, controller.marcarImagenPrincipal);

// Conceptos y definiciones por libro (libro_concepto)
router.post('/:id/conceptos', requireAdmin, controller.agregarConcepto);
router.post('/:id/conceptos/:conceptoId/eliminar', requireAdmin, controller.eliminarConcepto);

module.exports = router;
