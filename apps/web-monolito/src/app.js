// src/app.js
// Composición del monolito: un único proceso Express que sirve HTML
// renderizado en el servidor. No se registran rutas de API (sin JSON,
// sin XML). Organización por módulos, cada uno con su modelo,
// controlador, rutas y vistas (patrón MVC).
const path = require('path');
const express = require('express');
const session = require('express-session');
require('dotenv').config();

const authRoutes = require('./modules/auth/auth.routes');
const librosRoutes = require('./modules/libros/libros.routes');
const usuariosRoutes = require('./modules/usuarios/usuarios.routes');
const autoresRoutes = require('./modules/autores/autores.routes');
const generosRoutes = require('./modules/generos/generos.routes');
const formatosRoutes = require('./modules/formatos/formatos.routes');
const conceptosRoutes = require('./modules/conceptos/conceptos.routes');

const app = express();

// ---- Vistas (EJS) ----
app.set('view engine', 'ejs');
app.set('views', [
  path.join(__dirname, 'views'),   // vistas globales (home, 404, partials)
  path.join(__dirname, 'modules'), // cada módulo resuelve sus propias vistas/*
]);
// Ruta absoluta a los partials compartidos, disponible en TODAS las
// vistas sin importar la profundidad del módulo que las renderiza.
app.locals.partialsDir = path.join(__dirname, 'views', 'partials');

// ---- Middlewares base ----
app.use(express.urlencoded({ extended: true })); // formularios HTML clásicos
app.use(express.static(path.join(__dirname, 'public')));

app.use(session({
  secret: process.env.SESSION_SECRET || 'clave-de-desarrollo-cambiar-en-produccion',
  resave: false,
  saveUninitialized: false,
  cookie: { maxAge: 1000 * 60 * 60 * 4 }, // 4 horas
}));

// Exponer usuario de sesión y mensaje flash a todas las vistas
app.use((req, res, next) => {
  res.locals.usuarioActual = req.session.user || null;
  res.locals.flash = req.session.flash || null;
  delete req.session.flash;
  next();
});

// ---- Página de inicio ----
app.get('/', (req, res) => res.render('home'));

// ---- Módulos (macroarquitectura de monolito, un solo proceso/deploy) ----
app.use('/', authRoutes);
app.use('/libros', librosRoutes);
app.use('/admin/usuarios', usuariosRoutes);
app.use('/admin/autores', autoresRoutes);
app.use('/admin/generos', generosRoutes);
app.use('/admin/formatos', formatosRoutes);
app.use('/admin/conceptos', conceptosRoutes);

// ---- 404 ----
app.use((req, res) => res.status(404).render('404'));

// ---- Manejador de errores centralizado ----
app.use((err, req, res, next) => {
  console.error(err);
  req.session.flash = { type: 'error', message: err.message || 'Ocurrió un error inesperado.' };
  res.redirect(req.get('Referer') || '/');
});

module.exports = app;
