// src/server.js
const app = require('./app');

const PORT = process.env.PORT || 3000;
// Seguro por defecto: si HOST no está definido, escuchar solo en localhost.
// Node NO debe exponerse directo a Internet (Parte 8, punto 19) — el
// reverse proxy (Apache/NGINX) es el único punto de entrada público.
const HOST = process.env.HOST || '127.0.0.1';

app.listen(PORT, HOST, () => {
  console.log(`Servidor escuchando en http://${HOST}:${PORT}`);
});
