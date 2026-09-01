# Revisión de Seguridad — Librería en Línea

Ejercicio 02 · Integración de Aplicaciones Computacionales · UDEM
Parte 6, punto 17 del enunciado.

Cada control se documenta como: **amenaza que mitiga → control aplicado → evidencia/cómo se prueba → estado**.
Los riesgos referenciados vienen de `docs/REQUIREMENTS.md` §5. Esta revisión se hizo leyendo el código real de
`apps/web-monolito/src/`, no de memoria — cada fila cita el archivo donde vive el control (o la ausencia de él).

Estados: ✓ Control presente y suficiente para el alcance del ejercicio · ~ Control presente pero con brecha
conocida · ✗ Control ausente.

---

## 1. Hash de contraseñas y política básica de contraseñas

- **Amenaza:** que una fuga de la base de datos exponga contraseñas en texto plano, o que cuentas se creen con
  contraseñas triviales/vacías.
- **Control aplicado:** las contraseñas se hashean con `bcrypt` (`bcrypt.hash(password, 10)`) antes de guardarse;
  nunca se persiste ni se compara texto plano (`bcrypt.compare` en login).
- **Evidencia:** `auth.controller.js:44` (hash al registrar), `auth.controller.js:19` (compare al hacer login).
  Columna `password_hash VARCHAR(255)` en `db/01_schema.sql:56` — no existe columna `password` en texto plano.
- **Estado:** ✓ Corregido el 2026-08-31 y **verificado en vivo**: `auth.controller.js:registro` exige mínimo 8
  caracteres antes de hashear. Probado contra la app real: `POST /registro` con password de 6 caracteres no crea
  la cuenta (confirmado con `SELECT COUNT(*) ... = 0` en la base). No se agregó requisito de complejidad
  (mayúsculas/símbolos) para no penalizar usabilidad más allá de lo que pide el ejercicio ("política básica").

## 2. Variables de entorno para secretos y credenciales

- **Amenaza:** publicar credenciales de base de datos o la clave de sesión en el repositorio o en el sitio de
  entrega.
- **Control aplicado:** todas las credenciales (`PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD`, `SESSION_SECRET`,
  `PORT`) se leen de `.env` vía `dotenv`; `.env` está excluido de git.
- **Evidencia:** `apps/web-monolito/.gitignore:2` excluye `.env`; `apps/web-monolito/.env.example` solo trae
  nombres de variables, con `library666`/`localhost` como placeholders de desarrollo, no un secreto real de
  producción; `config/db.js:4` y `app.js:9` leen todo vía `process.env`.
- **Estado:** ✓ para el repositorio de código. **Pendiente de re-verificar en el momento de armar el `.tar.gz`**
  de entrega (Parte 10, punto 24 del ejercicio): confirmar que `.env` real (con la contraseña de producción) no
  quede incluido en el paquete ni se suba a `ubiquitous.udem.edu`.

## 3. Consultas SQL parametrizadas (mitigación de SQL Injection)

- **Amenaza:** que un valor de usuario (ISBN, título, término de búsqueda, credenciales) se interprete como código
  SQL y permita leer/alterar datos fuera de lo previsto.
- **Control aplicado:** el 100% de las consultas en todos los `*.model.js` y en `catalogo.factory.js` usan
  parámetros posicionales (`$1, $2, ...`) del driver `pg`; no hay ninguna concatenación de un valor de
  `req.body`/`req.params`/`req.query` directamente en un string SQL.
- **Evidencia:** revisar `libros.model.js` (incluida la búsqueda `ILIKE $1` en `listar()`, línea 12, que interpola
  el `%...%` como parámetro, no como texto SQL) y `catalogo.factory.js:18-42`. Los únicos valores interpolados
  directamente en el string SQL son `tabla`/`columna` en `catalogo.factory.js`, que **no** vienen de request del
  usuario sino que están fijos en el código (`autores.routes.js` etc. los pasan como constantes al invocar la
  fábrica), por lo que no son una superficie de inyección.
- **Estado:** ✓. Falta la prueba negativa documentada (Parte 3, punto 8 / Parte 7, punto 18): intentar una
  búsqueda o un campo con `'; DROP TABLE libros; --` y verificar que se trata como texto literal. Se agregará como
  caso de prueba en `docs/TEST_PLAN.md`.

## 4. Validación server-side de todos los campos

- **Amenaza:** que el sistema confíe en la validación HTML/JS del navegador (fácilmente evadible) y persista datos
  inconsistentes (precio negativo, ISBN vacío, año de publicación fuera de rango, etc.).
- **Control aplicado:** existe una segunda línea de defensa a nivel de base de datos (`CHECK (precio >= 0)`,
  `CHECK (stock >= 0)`, `CHECK (anio_publicacion > 0)`, `NOT NULL`, `UNIQUE` en `db/01_schema.sql`), y los
  controladores de catálogos simples sí validan explícitamente (`catalogo.factory.js:59`, rechaza valor vacío
  antes de tocar la base de datos).
- **Evidencia:** `db/01_schema.sql:104-105` (CHECKs de `libros`); `catalogo.factory.js:56-62`.
- **Estado:** ✓ Corregido el 2026-08-31 y **verificado en vivo**: `libros.controller.js` agrega `validarLibro()`
  y la ejecuta antes de `crear`/`actualizar` — rechaza ISBN/título/formato vacíos, precio o stock no numéricos o
  negativos, y año de publicación no entero/positivo, con mensajes específicos por campo. Probado contra la app
  real corriendo con PostgreSQL local: `POST /libros/:id` con `precio=-5` redirige a `/editar` sin tocar la fila
  (el precio en la base quedó sin cambios). Los `CHECK` de PostgreSQL se conservan como segunda línea de defensa
  (p. ej. ante una condición de carrera). No se agregó validación de *formato* de ISBN (longitud exacta ISBN-10/13
  con dígito verificador) por ser una regla más propia de negocio que de seguridad; queda como posible mejora
  futura, no como brecha de seguridad.

## 5. Autorización por rol en cada ruta administrativa

- **Amenaza:** que un usuario `cliente` (o sin sesión) ejecute operaciones de administración (crear/editar/borrar
  libros, catálogos, usuarios) accediendo directamente a la URL.
- **Control aplicado:** middleware `requireAdmin` (`middlewares/auth.js:12-18`) montado en **todas** las rutas de
  escritura de `libros.routes.js` y como `router.use(requireAdmin)` global en `usuarios.routes.js` y en el router
  que genera `catalogo.factory.js` (línea 103) — por lo tanto se aplica automáticamente a `autores`, `generos`,
  `formatos` y `conceptos` sin tener que repetirlo en cada ruta.
- **Evidencia:** `libros.routes.js:11-25`, `usuarios.routes.js:7`, `catalogo.factory.js:103`.
- **Estado:** ✓ para todas las rutas de **administración**, **verificado en vivo**: con sesión de `cliente` real,
  `GET /libros/nuevo` y `GET /admin/usuarios` redirigen a `/`, y el HTML que recibe ese `cliente` en `/libros` y
  `/libros/:id` no contiene ningún botón de administración (0 coincidencias al buscar "Nuevo libro", "Editar",
  etc.). La brecha relacionada de autenticación mínima (`GET /libros` y `GET /libros/:id` sin `requireLogin`,
  RF-04) se corrigió el 2026-08-31 — ver `docs/ENGINEERING_DECISIONS.md`, historial de correcciones.

## 6. Manejo seguro de sesiones y cierre de sesión

- **Amenaza:** secuestro de sesión, sesiones que no expiran, o que `logout` no invalide realmente la sesión en el
  servidor.
- **Control aplicado:** `express-session` con `resave: false`, `saveUninitialized: false`, expiración de 4 horas
  (`cookie.maxAge`); `logout` llama a `req.session.destroy()` (invalida la sesión en el servidor, no solo borra la
  cookie del cliente).
- **Evidencia:** `app.js:35-40`; `auth.controller.js:51-53`.
- **Estado:** ~ Dos brechas a resolver antes de la entrega:
  1. La cookie de sesión no fija explícitamente `cookie.httpOnly: true` ni `cookie.secure: true` — `httpOnly` es
     `true` por defecto en `express-session` (mitigación XSS ya activa sin configurarlo), pero `secure` no está
     activado, así que la cookie viajaría sin cifrado si en algún punto se accediera por HTTP puro en vez de
     detrás de un proxy con TLS. Para el alcance del ejercicio (HTTP interno + proxy) es aceptable, pero debe
     quedar como limitación documentada, no como omisión accidental.
  2. `SESSION_SECRET` tiene un valor por defecto hardcodeado en el código (`app.js:36`,
     `'clave-de-desarrollo-cambiar-en-produccion'`) que se usa si la variable de entorno no está definida. Es un
     *fallback* razonable para no crashear en desarrollo, pero representa un riesgo si `.env` faltara en producción
     y nadie lo notara. Pendiente: hacer que el arranque falle explícitamente si `SESSION_SECRET` no está definido
     fuera de desarrollo.

## 7. Validación de archivos subidos (extensión, MIME, tamaño, nombre)

- **Amenaza:** subir un archivo ejecutable/script disfrazado de imagen, agotar espacio en disco con archivos
  gigantes, o sobrescribir/acceder a archivos del sistema vía el nombre del archivo.
- **Control aplicado:** `multer` con `fileFilter` que solo acepta extensiones `.jpg/.jpeg/.png/.webp/.gif`, límite
  de tamaño de 5 MB (`limits.fileSize`), y nombre de archivo generado por el servidor
  (`libro-<id>-<timestamp>.<ext>`), nunca el nombre original enviado por el usuario.
- **Evidencia:** `middlewares/upload.js` completo.
- **Estado:** ~ Ya cubre nombre, tamaño y extensión. **Falta validar el tipo MIME real / firma binaria del
  archivo** (`fileFilter` solo mira la extensión del nombre original, que el atacante controla — un `.exe`
  renombrado a `foto.png` pasaría el filtro). Riesgo residual documentado en D-07 de
  `docs/ENGINEERING_DECISIONS.md`; mitigación futura: validar los *magic bytes* con una librería como `file-type`
  antes de aceptar el archivo.

## 8. Mensajes de error controlados (sin stack traces ni SQL al usuario)

- **Amenaza:** que un error de PostgreSQL o una excepción de Node exponga nombres de tabla/constraint, rutas del
  servidor o un stack trace al usuario final, información útil para un atacante.
- **Control aplicado:** middleware de error final en `app.js:65-70` evita que Express muestre su página de error
  por defecto (que sí incluye stack trace); en su lugar, todo error termina en un mensaje flash + redirección.
  Varios controladores además capturan el error específico y devuelven un mensaje de negocio propio (ISBN
  duplicado, catálogo en uso, segundo administrador).
- **Evidencia:** `app.js:65-70`; `libros.controller.js:51-54` (crear/actualizar); `catalogo.factory.js:66-69,84-87,94-97`;
  `usuarios.controller.js:33-39`.
- **Estado:** ✓ Corregido el 2026-08-31 (ver D-08 en `docs/ENGINEERING_DECISIONS.md`): el middleware final ya no
  interpola `err.message` en el mensaje mostrado al usuario, solo lo registra vía `console.error`. Esto cubre como
  red de seguridad rutas como `libros.controller.js:eliminar`, que no tiene manejo específico de errores de FK y
  antes habría dejado pasar el mensaje crudo de Postgres.

## 9. Principio de mínimo privilegio para el usuario de PostgreSQL

- **Amenaza:** que si la aplicación se ve comprometida (p. ej. vía una inyección no prevista), el usuario de base
  de datos que usa la app tenga privilegios para borrar la base completa, crear roles nuevos, o leer/escribir
  fuera de las tablas que la aplicación necesita.
- **Control aplicado (documentado hoy):** la aplicación se conecta con un usuario de aplicación dedicado
  (`library_user`), **no** con el superusuario `postgres` — ver `config/db.js:11` y `README.md:40`.
- **Evidencia:** `README.md:48-50` crea `library_user` como rol de login con contraseña, y `README.md:49`
  lo declara **`OWNER`** de `library_db`.
- **Estado:** ✓ Corregido y **verificado en la instancia GCP real** (`integracion`, proyecto `integracion-505802`)
  el 2026-09-01: se recargó `db/00_create_database.sql` + `db/01_schema.sql` ahí (antes tenía `library_user` como
  `OWNER`, igual que se predijo). Confirmado con el mismo experimento que en local: `library_user` puede leer
  `vista_catalogo_libros` normalmente, pero `CREATE TABLE prueba_ddl (...)` con ese mismo rol falla con
  `ERROR: permission denied for schema public`.

## 10. Node.js no debe exponerse directo a Internet (Parte 8, punto 19)

- **Amenaza:** que el proceso Node quede accesible desde cualquier IP de Internet sin pasar por el reverse proxy,
  saltándose cualquier control (TLS, límites de tasa, etc.) que se configure ahí más adelante — y que el
  enunciado prohíbe explícitamente ("La aplicación Node.js deberá escuchar en 127.0.0.1:3000 y no exponerse
  directamente a Internet").
- **Control aplicado:** `src/server.js` fija el host de escucha (`app.listen(PORT, HOST, ...)`) con
  `HOST = process.env.HOST || '127.0.0.1'`.
- **Estado:** ✓ Corregido el 2026-09-01. **Brecha real encontrada al desplegar en GCP** (no se habría visto solo
  revisando el código en local): el valor por defecto de `HOST` era `'0.0.0.0'`, es decir, si la variable de
  entorno `HOST` no se definía explícitamente, el proceso escuchaba en **todas** las interfaces de red — expuesto
  directo a Internet en cuanto arrancara, combinado con la regla de firewall de GCP que además tenía el puerto
  3000 abierto a `0.0.0.0/0` (ver control 11). Se cambió el valor por defecto a `'127.0.0.1'` (seguro por
  defecto) y además se fija `HOST=127.0.0.1` explícitamente en el `.env` de la instancia GCP.
- **Evidencia:** `src/server.js:5`; verificado en la instancia real que, tras el cambio, `curl` desde dentro del
  servidor a `127.0.0.1:3000` responde pero un intento desde fuera (una vez cerrado también el firewall, ver
  control 11) ya no llega al proceso.

## 11. Reglas de firewall innecesarias o contradictorias con la arquitectura

- **Amenaza:** superficie de ataque innecesaria por reglas de firewall más permisivas de lo que el ejercicio
  permite.
- **Hallazgos en la instancia GCP real** (`integracion`, proyecto `integracion-505802`), no visibles desde el
  código: el puerto 3000 estaba abierto a `0.0.0.0/0` con **dos reglas duplicadas** (`allow-node-3000` y
  `permitir-tcp-3000`) — contradice directamente el punto 19 de la Parte 8 (ver control 10); y el puerto 3389
  (RDP) estaba abierto a `0.0.0.0/0` sin ningún servicio Windows escuchando ahí (la instancia es CentOS Linux) —
  regla sin propósito.
- **Estado:** ~ Pendiente de limpiar — identificado el 2026-09-01, se cerrará una vez que el reverse proxy
  (Apache/NGINX bajo `/library`) esté configurado y verificado funcionando (para no cerrar el único acceso HTTP
  directo a la app antes de tener el proxy listo). Plan: eliminar las 2 reglas de puerto 3000 y la de RDP,
  dejando solo 22 (SSH), 80 (HTTP) y, si se agrega TLS más adelante, 443.

## 12. No publicar contraseñas, `.env`, claves SSH, tokens o cadenas de conexión en `ubiquitous.udem.edu`

- **Amenaza:** que al comprimir y publicar el proyecto en el sitio de evidencias, se filtren credenciales reales
  (de la base de datos de producción, de la instancia GCP, etc.) accesibles públicamente.
- **Control aplicado (a nivel de repositorio):** `.gitignore` ya excluye `.env` y `node_modules/`; existe
  `.env.example` sin valores reales.
- **Evidencia:** `apps/web-monolito/.gitignore`; `apps/web-monolito/.env.example`.
- **Estado:** ~ Pendiente (no aplicable todavía porque aún no se ha empaquetado/publicado nada — Parte 10 del
  ejercicio no se ha ejecutado). Cuando se llegue a esa parte, agregar aquí una checklist explícita ejecutada antes
  de generar `descargas/ejercicio02.tar.gz`: excluir `.env`, `node_modules/`, cualquier clave SSH usada para
  conectarse a GCP, y el `SESSION_SECRET`/contraseña real de `library_user` usados en producción (deben diferir de
  los valores de `.env.example`).

---

## Resumen de brechas

| # | Brecha | Dónde se corrige | Prioridad | Estado |
|---|--------|-------------------|-----------|--------|
| 1 | Sin política de longitud mínima de contraseña | `auth.controller.js:registro` | Baja | ✓ Corregido 2026-08-31 |
| 2 | Sin validación server-side de campos de `libros` (precio/stock/ISBN/año) antes del INSERT | `libros.controller.js` | Media | ✓ Corregido 2026-08-31 |
| 3 | `RF-04`: catálogo de libros visible sin sesión | `libros.routes.js` | Media | ✓ Corregido 2026-08-31 |
| 6 | Middleware de error final reenvía `err.message` crudo al usuario | `app.js` | **Alta** | ✓ Corregido 2026-08-31 |
| 4 | `SESSION_SECRET` con fallback hardcodeado | `app.js:36` | Baja | ✗ Pendiente (deliberado, ver nota abajo) |
| 5 | Filtro de imagen solo por extensión, no por MIME/magic bytes | `middlewares/upload.js` | Baja | ✗ Pendiente (deliberado) |
| 7 | `library_user` es `OWNER` de la base (no mínimo privilegio) | `db/00_create_database.sql` + `db/01_schema.sql` | **Alta** | ✓ Corregido y verificado en la instancia GCP real (`integracion`) el 2026-09-01 |
| 8 | Checklist de secretos antes de publicar `.tar.gz` | Al llegar a la Parte 10 | — | ✗ Pendiente hasta esa fase |
| 9 | `HOST` por defecto era `0.0.0.0` (Node expuesto directo a Internet) | `src/server.js` | **Alta** | ✓ Corregido y verificado en GCP el 2026-09-01 (control 10) |
| 10 | Puerto 3000 abierto a `0.0.0.0/0` en el firewall de GCP (2 reglas duplicadas) + regla RDP sin uso | Consola/`gcloud` de GCP | **Alta** | ~ Pendiente cerrar hasta que el reverse proxy esté verificado (control 11) |

Las 4 primeras brechas se corrigieron el mismo día que se detectaron por ser cambios pequeños y localizados (no
tocan el modelo de datos ni cambian ningún contrato entre módulos), verificados con `node -c` en los 4 archivos
modificados y un smoke test manual del servidor confirmando que `GET /libros` sin sesión ahora responde
`302 → /login`. Las brechas 4 y 5 se dejaron deliberadamente para no introducir una dependencia nueva
(`file-type`) ni cambiar el comportamiento de arranque sin antes decidir junto con el resto del equipo/documentación
cómo debe fallar la app si falta `SESSION_SECRET` en producción. La brecha 8 depende de la Parte 10 (publicación).
Las brechas 7 y 9 se detectaron y corrigieron al desplegar de verdad en la instancia GCP — ninguna de las dos era
visible solo revisando el código en local, lo que confirma el valor de probar contra infraestructura real antes de
dar una parte por cerrada. La 10 se deja pendiente a propósito un poco más: cerrar el puerto 3000 antes de tener
el reverse proxy funcionando dejaría la app completamente inaccesible desde fuera del servidor.
