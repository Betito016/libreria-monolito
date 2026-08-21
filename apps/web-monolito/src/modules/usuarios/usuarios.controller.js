// src/modules/usuarios/usuarios.controller.js
// Gestión administrativa de usuarios ya registrados (alta pública de
// cuentas ocurre en el módulo "auth"; aquí solo se administra rol y
// estado, y se elimina). La restricción "máximo un administrador" la
// hace cumplir la base de datos (índice único parcial).
const usuariosModel = require('./usuarios.model');

module.exports = {
  index: async (req, res, next) => {
    try {
      const usuarios = await usuariosModel.listar();
      res.render('usuarios/views/list', { usuarios });
    } catch (err) { next(err); }
  },

  editarForm: async (req, res, next) => {
    try {
      const usuario = await usuariosModel.obtenerPorId(req.params.id);
      if (!usuario) return res.status(404).render('404');
      res.render('usuarios/views/form', { usuario });
    } catch (err) { next(err); }
  },

  actualizar: async (req, res, next) => {
    try {
      const { rol, activo } = req.body;
      await usuariosModel.actualizarRolYEstado(req.params.id, {
        rol,
        activo: activo === 'on',
      });
      req.session.flash = { type: 'success', message: 'Usuario actualizado.' };
      res.redirect('/admin/usuarios');
    } catch (err) {
      req.session.flash = {
        type: 'error',
        message: 'No se pudo actualizar: ya existe un administrador registrado (solo puede haber uno).',
      };
      res.redirect('/admin/usuarios');
    }
  },

  eliminar: async (req, res, next) => {
    try {
      await usuariosModel.eliminar(req.params.id);
      req.session.flash = { type: 'success', message: 'Usuario eliminado.' };
      res.redirect('/admin/usuarios');
    } catch (err) { next(err); }
  },
};
