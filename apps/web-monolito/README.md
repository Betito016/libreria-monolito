# web-monolito — Librería en Línea

Aplicación web **monolítica** en Node.js + Express + EJS (renderizado 100%
del lado del servidor) con acceso directo a PostgreSQL (sin ORM). Sigue el
patrón **MVC** y una **organización de código por módulos** (uno por
entidad de negocio: `libros`, `autores`, `generos`, `formatos`,
`conceptos`, `usuarios`, `auth`).

**Restricción arquitectónica respetada:** no existen rutas de API REST,
GraphQL ni SOAP. No se produce ni consume JSON/XML como formato de
intercambio — todas las interacciones son formularios HTML clásicos
(`application/x-www-form-urlencoded` o `multipart/form-data` para
imágenes) con redirecciones POST→GET (patrón *Post/Redirect/Get*). El
archivo `package.json` existe únicamente porque `npm` lo requiere para
administrar las dependencias del proyecto.

Las instrucciones de instalación/despliegue completas (base de datos,
Node.js, systemd, firewall/SELinux, reverse proxy) viven en el
[`README.md`](../../README.md) de la raíz del repositorio — se mantienen
en un solo lugar para no repetir (y desincronizar) los mismos pasos en
dos archivos. Este archivo solo documenta las decisiones de diseño
específicas de esta aplicación.

## Notas de diseño relevantes para la evaluación

- **Macroarquitectura:** monolito — un único proceso Node.js, un único
  despliegue, acceso directo a la base de datos (sin microservicios ni
  API intermedia).
- **MVC:** cada módulo separa `*.model.js` (SQL parametrizado con
  `pg`), `*.controller.js` (orquesta petición/respuesta) y
  `*.routes.js` (mapeo URL→controlador); las vistas EJS viven en
  `views/` dentro de cada módulo.
- **Organización por módulos:** `src/modules/{auth, usuarios, libros,
  autores, generos, formatos, conceptos}`. Los cuatro catálogos simples
  (`autores`, `generos`, `formatos`, `conceptos`) comparten una
  *fábrica* de módulo CRUD (`modules/catalogo/catalogo.factory.js`)
  para no duplicar código estructuralmente idéntico, sin dejar de
  seguir MVC.
- **CRUD en todas las tablas normalizadas:** `usuarios`, `libros`,
  `autores`, `generos`, `formatos`, `conceptos` e `imagenes` tienen
  CRUD directo; `libro_autor` y `libro_genero` (tablas puente sin
  atributos propios) se gestionan como parte del formulario del libro;
  `libro_concepto` (tabla puente **con** atributo `definicion`) tiene
  su propia interfaz de alta/baja dentro de la ficha del libro.
- **Sin JSON/XML:** todas las mutaciones usan formularios HTML con
  método `POST` y redirección posterior (patrón PRG); la subida de
  imágenes usa `multipart/form-data` vía `multer`, no un endpoint de
  API.
- **Vista y stored procedures (`db/06_views.sql`, `db/04_stored_procedures.sql`):**
  `libros.model.js:listar()` usa `vista_catalogo_libros` en vez de repetir
  el `JOIN`/`GROUP BY` en la aplicación. Los procedimientos
  `sp_asignar_autores_libro`/`sp_asignar_generos_libro` existen y están
  documentados, pero deliberadamente **no** están conectados todavía a
  `libros.model.js` — ver `docs/ENGINEERING_DECISIONS.md`, decisión D-17.

Para el detalle completo de requisitos, decisiones de arquitectura,
revisión de seguridad y plan de pruebas, ver la carpeta
[`docs/`](../../docs) en la raíz del repositorio.
