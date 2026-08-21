// src/modules/usuarios/usuarios.routes.js
const express = require('express');
const { requireAdmin } = require('../../middlewares/auth');
const controller = require('./usuarios.controller');

const router = express.Router();
router.use(requireAdmin);

router.get('/', controller.index);
router.get('/:id/editar', controller.editarForm);
router.post('/:id', controller.actualizar);
router.post('/:id/eliminar', controller.eliminar);

module.exports = router;
