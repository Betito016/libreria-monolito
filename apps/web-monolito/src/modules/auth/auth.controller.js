// src/modules/auth/auth.controller.js
// Autenticación basada en sesión de servidor. El registro público
// siempre crea usuarios con rol 'cliente'; el rol 'administrador' está
// limitado a uno solo por el índice único parcial de la base de datos.
const bcrypt = require('bcrypt');
const usuariosModel = require('../usuarios/usuarios.model');

module.exports = {
  loginForm: (req, res) => res.render('auth/views/login'),

  login: async (req, res, next) => {
    try {
      const { email, password } = req.body;
      const usuario = await usuariosModel.obtenerPorEmail(email);
      if (!usuario || !usuario.activo) {
        req.session.flash = { type: 'error', message: 'Credenciales inválidas o usuario inactivo.' };
        return res.redirect('/login');
      }
      const ok = await bcrypt.compare(password, usuario.password_hash);
      if (!ok) {
        req.session.flash = { type: 'error', message: 'Credenciales inválidas.' };
        return res.redirect('/login');
      }
      req.session.user = { id: usuario.id, nombre: usuario.nombre, rol: usuario.rol };
      req.session.flash = { type: 'success', message: `Bienvenido, ${usuario.nombre}.` };
      res.redirect('/');
    } catch (err) { next(err); }
  },

  registroForm: (req, res) => res.render('auth/views/registro'),

  registro: async (req, res, next) => {
    try {
      const { nombre, email, password, password2 } = req.body;
      if (!nombre || !email || !password || password !== password2) {
        req.session.flash = { type: 'error', message: 'Revisa los datos: las contraseñas deben coincidir.' };
        return res.redirect('/registro');
      }
      if (password.length < 8) {
        req.session.flash = { type: 'error', message: 'La contraseña debe tener al menos 8 caracteres.' };
        return res.redirect('/registro');
      }
      const existente = await usuariosModel.obtenerPorEmail(email);
      if (existente) {
        req.session.flash = { type: 'error', message: 'Ese correo ya está registrado.' };
        return res.redirect('/registro');
      }
      const passwordHash = await bcrypt.hash(password, 10);
      await usuariosModel.crear({ nombre, email, passwordHash, rol: 'cliente' });
      req.session.flash = { type: 'success', message: 'Cuenta creada. Ya puedes iniciar sesión.' };
      res.redirect('/login');
    } catch (err) { next(err); }
  },

  logout: (req, res) => {
    req.session.destroy(() => res.redirect('/'));
  },
};
