// src/middlewares/upload.js
// Manejo de imágenes vía multipart/form-data (formulario HTML clásico,
// NO json/xml). Los archivos se guardan en disco; solo la ruta relativa
// se persiste en la tabla "imagenes".
const multer = require('multer');
const path = require('path');
const fs = require('fs');

const uploadDir = path.join(__dirname, '..', 'public', 'uploads');
fs.mkdirSync(uploadDir, { recursive: true });

const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, uploadDir),
  filename: (req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase();
    const libroId = req.params.id || 'sinlibro';
    const nombre = `libro-${libroId}-${Date.now()}${ext}`;
    cb(null, nombre);
  },
});

const tiposPermitidos = ['.jpg', '.jpeg', '.png', '.webp', '.gif'];

function filtroArchivo(req, file, cb) {
  const ext = path.extname(file.originalname).toLowerCase();
  if (tiposPermitidos.includes(ext)) return cb(null, true);
  cb(new Error('Formato de imagen no soportado. Usa jpg, png, webp o gif.'));
}

module.exports = multer({
  storage,
  fileFilter: filtroArchivo,
  limits: { fileSize: 5 * 1024 * 1024 }, // 5 MB
});
