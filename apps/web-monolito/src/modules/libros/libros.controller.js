// src/modules/libros/libros.controller.js
const fs = require('fs');
const path = require('path');
const librosModel = require('./libros.model');

function normalizarIds(valor) {
  if (!valor) return [];
  return Array.isArray(valor) ? valor.map(Number) : [Number(valor)];
}

module.exports = {
  index: async (req, res, next) => {
    try {
      const busqueda = req.query.q || '';
      const libros = await librosModel.listar(busqueda);
      res.render('libros/views/list', { libros, busqueda });
    } catch (err) { next(err); }
  },

  detalle: async (req, res, next) => {
    try {
      const libro = await librosModel.obtenerDetalle(req.params.id);
      if (!libro) return res.status(404).render('404');
      const conceptosCatalogo = await librosModel.listarConceptos();
      res.render('libros/views/detail', { libro, conceptosCatalogo });
    } catch (err) { next(err); }
  },

  nuevoForm: async (req, res, next) => {
    try {
      const [autores, generos, formatos] = await Promise.all([
        librosModel.listarAutores(),
        librosModel.listarGeneros(),
        librosModel.listarFormatos(),
      ]);
      res.render('libros/views/form', {
        libro: null, autores, generos, formatos,
        seleccionAutores: [], seleccionGeneros: [],
      });
    } catch (err) { next(err); }
  },

  crear: async (req, res, next) => {
    try {
      const { isbn, titulo, anio_publicacion, precio, stock, formato_id } = req.body;
      const id = await librosModel.crear({ isbn, titulo, anio_publicacion, precio, stock, formato_id });
      await librosModel.asignarAutores(id, normalizarIds(req.body.autores));
      await librosModel.asignarGeneros(id, normalizarIds(req.body.generos));
      req.session.flash = { type: 'success', message: 'Libro creado correctamente.' };
      res.redirect(`/libros/${id}`);
    } catch (err) {
      req.session.flash = { type: 'error', message: 'No se pudo crear el libro. Verifica que el ISBN no esté repetido.' };
      res.redirect('/libros/nuevo');
    }
  },

  editarForm: async (req, res, next) => {
    try {
      const libro = await librosModel.obtenerDetalle(req.params.id);
      if (!libro) return res.status(404).render('404');
      const [autores, generos, formatos] = await Promise.all([
        librosModel.listarAutores(),
        librosModel.listarGeneros(),
        librosModel.listarFormatos(),
      ]);
      res.render('libros/views/form', {
        libro, autores, generos, formatos,
        seleccionAutores: libro.autores.map((a) => a.id),
        seleccionGeneros: libro.generos.map((g) => g.id),
      });
    } catch (err) { next(err); }
  },

  actualizar: async (req, res, next) => {
    try {
      const { isbn, titulo, anio_publicacion, precio, stock, formato_id } = req.body;
      await librosModel.actualizar(req.params.id, { isbn, titulo, anio_publicacion, precio, stock, formato_id });
      await librosModel.asignarAutores(req.params.id, normalizarIds(req.body.autores));
      await librosModel.asignarGeneros(req.params.id, normalizarIds(req.body.generos));
      req.session.flash = { type: 'success', message: 'Libro actualizado.' };
      res.redirect(`/libros/${req.params.id}`);
    } catch (err) {
      req.session.flash = { type: 'error', message: 'No se pudo actualizar el libro.' };
      res.redirect(`/libros/${req.params.id}/editar`);
    }
  },

  eliminar: async (req, res, next) => {
    try {
      await librosModel.eliminar(req.params.id);
      req.session.flash = { type: 'success', message: 'Libro eliminado.' };
      res.redirect('/libros');
    } catch (err) { next(err); }
  },

  // ---- Imágenes ----
  subirImagen: async (req, res, next) => {
    try {
      if (!req.file) {
        req.session.flash = { type: 'error', message: 'Selecciona un archivo de imagen.' };
        return res.redirect(`/libros/${req.params.id}`);
      }
      await librosModel.agregarImagen(req.params.id, {
        url_imagen: `/uploads/${req.file.filename}`,
        texto_alt: req.body.texto_alt,
        esPrincipal: req.body.es_principal === 'on',
      });
      req.session.flash = { type: 'success', message: 'Imagen agregada.' };
      res.redirect(`/libros/${req.params.id}`);
    } catch (err) { next(err); }
  },

  eliminarImagen: async (req, res, next) => {
    try {
      const imagen = await librosModel.obtenerImagen(req.params.imgId);
      if (imagen) {
        const rutaArchivo = path.join(__dirname, '..', '..', 'public', imagen.url_imagen);
        fs.unlink(rutaArchivo, () => {});
        await librosModel.eliminarImagen(req.params.imgId);
      }
      req.session.flash = { type: 'success', message: 'Imagen eliminada.' };
      res.redirect(`/libros/${req.params.id}`);
    } catch (err) { next(err); }
  },

  marcarImagenPrincipal: async (req, res, next) => {
    try {
      await librosModel.marcarImagenPrincipal(req.params.imgId, req.params.id);
      res.redirect(`/libros/${req.params.id}`);
    } catch (err) { next(err); }
  },

  // ---- Conceptos definidos por el libro ----
  agregarConcepto: async (req, res, next) => {
    try {
      let conceptoId = req.body.concepto_id;
      const nuevoTermino = (req.body.nuevo_termino || '').trim();
      const definicion = (req.body.definicion || '').trim();

      if (!definicion) {
        req.session.flash = { type: 'error', message: 'La definición no puede estar vacía.' };
        return res.redirect(`/libros/${req.params.id}`);
      }
      if (!conceptoId && nuevoTermino) {
        conceptoId = await librosModel.crearConceptoSiNoExiste(nuevoTermino);
      }
      if (!conceptoId) {
        req.session.flash = { type: 'error', message: 'Selecciona un concepto existente o escribe uno nuevo.' };
        return res.redirect(`/libros/${req.params.id}`);
      }
      await librosModel.upsertConcepto(req.params.id, conceptoId, definicion);
      req.session.flash = { type: 'success', message: 'Concepto asociado al libro.' };
      res.redirect(`/libros/${req.params.id}`);
    } catch (err) { next(err); }
  },

  eliminarConcepto: async (req, res, next) => {
    try {
      await librosModel.eliminarConcepto(req.params.id, req.params.conceptoId);
      req.session.flash = { type: 'success', message: 'Definición eliminada del libro.' };
      res.redirect(`/libros/${req.params.id}`);
    } catch (err) { next(err); }
  },
};
