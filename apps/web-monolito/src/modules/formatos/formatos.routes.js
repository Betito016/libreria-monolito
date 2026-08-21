// src/modules/formatos/formatos.routes.js
const crearCatalogo = require('../catalogo/catalogo.factory');

const { router } = crearCatalogo({
  tabla: 'formatos',
  columna: 'nombre',
  etiqueta: 'Formato',
  etiquetaPlural: 'Formatos',
  base: '/admin/formatos',
});

module.exports = router;
