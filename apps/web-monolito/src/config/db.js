// src/config/db.js
// Pool de conexiones a PostgreSQL usado por todos los modelos.
// Acceso directo a la base de datos (sin ORM, sin API intermedia).
require('dotenv').config();
const { Pool } = require('pg');

const pool = new Pool({
  host: process.env.PGHOST || 'localhost',
  port: Number(process.env.PGPORT) || 5432,
  database: process.env.PGDATABASE || 'library_db',
  user: process.env.PGUSER || 'library_user',
  password: process.env.PGPASSWORD || 'library666',
});

pool.on('error', (err) => {
  console.error('Error inesperado en el pool de PostgreSQL:', err);
});

module.exports = pool;
