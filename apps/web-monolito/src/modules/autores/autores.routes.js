// src/modules/autores/autores.routes.js
const crearCatalogo = require('../catalogo/catalogo.factory');

const { router } = crearCatalogo({
  tabla: 'autores',
  columna: 'nombre',
  etiqueta: 'Autor',
  etiquetaPlural: 'Autores',
  base: '/admin/autores',
});

module.exports = router;
