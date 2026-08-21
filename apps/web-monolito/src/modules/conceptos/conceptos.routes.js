// src/modules/conceptos/conceptos.routes.js
// CRUD del catálogo de "términos" de conceptos. La DEFINICIÓN de cada
// concepto por libro (que puede variar de un libro a otro) se gestiona
// dentro del módulo "libros", sobre la tabla puente libro_concepto.
const crearCatalogo = require('../catalogo/catalogo.factory');

const { router } = crearCatalogo({
  tabla: 'conceptos',
  columna: 'termino',
  etiqueta: 'Concepto',
  etiquetaPlural: 'Conceptos',
  base: '/admin/conceptos',
});

module.exports = router;
