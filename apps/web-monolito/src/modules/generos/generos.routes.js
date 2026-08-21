// src/modules/generos/generos.routes.js
const crearCatalogo = require('../catalogo/catalogo.factory');

const { router } = crearCatalogo({
  tabla: 'generos',
  columna: 'nombre',
  etiqueta: 'Género',
  etiquetaPlural: 'Géneros',
  base: '/admin/generos',
});

module.exports = router;
