// src/middlewares/auth.js
// Autorización basada en sesión de servidor (no tokens, no JSON).

function requireLogin(req, res, next) {
  if (!req.session.user) {
    req.session.flash = { type: 'error', message: 'Debes iniciar sesión para continuar.' };
    return res.redirect('/login');
  }
  next();
}

function requireAdmin(req, res, next) {
  if (!req.session.user || req.session.user.rol !== 'administrador') {
    req.session.flash = { type: 'error', message: 'No tienes permisos de administrador para esta acción.' };
    return res.redirect('/');
  }
  next();
}

module.exports = { requireLogin, requireAdmin };
