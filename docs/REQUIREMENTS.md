# Requisitos del Sistema — Librería en Línea

Ejercicio 02 · Integración de Aplicaciones Computacionales · UDEM
Aplicación web monolítica (Node.js + Express + EJS + PostgreSQL) para la gestión de una librería en línea.

Este documento se escribe **antes/en paralelo a validar el código existente** en `apps/web-monolito/`, tal como pide
la Parte 1 del ejercicio. Donde el sistema ya tiene una implementación, se indica su estado actual (columna
**Estado**) para que este archivo sirva también como checklist de verificación, no solo como enunciado de
intenciones.

Estados usados: ✓ Implementado · ~ Implementado parcialmente / con brecha conocida · ✗ Pendiente.

---

## 1. Alcance

El sistema permite a un único Administrador gestionar el catálogo de una librería (libros, autores, géneros,
formatos, conceptos e imágenes) y a los usuarios registrados consultar dicho catálogo. Toda la interfaz se renderiza
en el servidor con EJS; no existen API REST/GraphQL/SOAP ni intercambio de JSON/XML entre frontend y backend
(ver restricciones arquitectónicas en `docs/ENGINEERING_DECISIONS.md`).

Fuera de alcance: pagos, envíos, facturación, multi-idioma, roles adicionales a `cliente`/`administrador`.

## 2. Requisitos funcionales

| ID | Requisito | Criterio de aceptación | Estado |
|----|-----------|-------------------------|--------|
| RF-01 | Registro de usuario | Un visitante puede crear una cuenta desde `/registro` con nombre, correo único y contraseña (con confirmación). La cuenta se crea siempre con rol `cliente`. | ✓ `auth.controller.js:registro` |
| RF-02 | Inicio de sesión | Un usuario registrado puede autenticarse en `/login` con correo y contraseña; la contraseña se valida contra un hash `bcrypt`, nunca en texto plano. | ✓ `auth.controller.js:login` |
| RF-03 | Cierre de sesión | Un usuario autenticado puede cerrar sesión desde cualquier vista; la sesión de servidor se destruye. | ✓ `auth.controller.js:logout` |
| RF-04 | Consulta del catálogo por usuarios autenticados | Solo un usuario con sesión iniciada puede listar y ver el detalle de libros. | ✓ Corregido el 2026-08-31: `libros.routes.js` aplica `requireLogin` a `GET /` y `GET /:id`. Verificado con smoke test manual: `GET /libros` sin sesión responde `302 Location: /login`. |
| RF-05 | Búsqueda por ISBN y título | El listado de libros admite un parámetro de búsqueda `q` que filtra por ISBN o título. | ✓ `libros.controller.js:index` + `librosModel.listar(busqueda)` |
| RF-06 | CRUD de libros | El Administrador puede crear, leer, actualizar y eliminar libros (ISBN, título, año, precio, stock, formato). | ✓ `libros.routes.js` protegidas con `requireAdmin` |
| RF-07 | CRUD de autores, géneros, formatos y conceptos | El Administrador puede crear, leer, actualizar y eliminar registros de estos cuatro catálogos. | ✓ `catalogo.factory.js` (módulo compartido, montado en `/admin/autores`, `/admin/generos`, `/admin/formatos`, `/admin/conceptos`) |
| RF-08 | Asociar múltiples autores y géneros a un libro | El formulario de libro permite seleccionar 0..N autores y 0..N géneros; se persisten en `libro_autor` y `libro_genero`. | ✓ `librosModel.asignarAutores`/`asignarGeneros` (ahora vía `CALL sp_asignar_autores_libro`/`sp_asignar_generos_libro`, ver D-17/D-18). Verificado en vivo: libro creado con 2 autores + 1 género, luego editado para reemplazar por 1 autor distinto y quitar todos los géneros — la base reflejó exactamente ambos cambios. |
| RF-09 | Registrar conceptos y definiciones por libro | Desde la ficha de un libro se puede asociar un concepto del catálogo (o crear uno nuevo) junto con una definición específica de ese libro, y eliminarla. | ✓ `libros.controller.js:agregarConcepto/eliminarConcepto` → tabla `libro_concepto` |
| RF-09a | Ejemplo obligatorio: conceptos de Cloud Computing | Debe existir al menos un libro de Computación con los conceptos IaaS, PaaS, SaaS, FaaS, Bucket, Public/Private/Hybrid Cloud, Multicloud y Serverless cargados como evidencia. | ✓ Verificado en vivo el 2026-08-31: `db/02_seed_30_per_table.sql` cargado contra PostgreSQL 18 local, `GET /libros/17` con sesión real muestra los 10 conceptos exigidos con sus definiciones (ver TC-27 en `docs/TEST_PLAN.md`). |
| RF-10 | Carga, edición y eliminación de imágenes | El Administrador puede subir imágenes (JPG/PNG/WebP) a un libro, marcar una como portada y eliminarlas. | ✓ Verificado en vivo el 2026-09-01 contra la instancia GCP real: subida, marcado como portada y eliminación probados con `curl` sobre `http://34.67.65.195/library/...`, confirmados en base de datos (ver TC-37, `docs/TEST_PLAN.md`) |
| RF-11 | Marcar imagen como portada | Solo una imagen por libro puede ser portada (`es_principal`). | ✓ Reforzado en BD con `ux_una_imagen_principal_por_libro` (índice único parcial), verificado en vivo. Mejora futura menor detectada: al eliminar la portada no se reasigna otra automáticamente (ver D-07 en `ENGINEERING_DECISIONS.md`) |
| RF-12 | Control de stock y precio | `stock` y `precio` no pueden ser negativos; se valida en formulario y en BD. | ✓ `CHECK (precio >= 0)`, `CHECK (stock >= 0)` en `libros` |
| RF-13 | Administración restringida a un único Administrador | Solo puede existir un usuario con rol `administrador` en todo el sistema; el registro público nunca crea administradores. | ✓ Índice único parcial `ux_un_solo_administrador`; `auth.controller.js:registro` fuerza `rol: 'cliente'` |
| RF-14 | Gestión de usuarios | El Administrador puede listar usuarios, cambiar su rol/estado activo y eliminarlos. | ✓ `usuarios.controller.js` bajo `/admin/usuarios`, protegido con `requireAdmin` |
| RF-15 | Acceso denegado a funciones administrativas | Un usuario `cliente` que intente acceder a una ruta `/admin/*` o de gestión recibe una respuesta controlada (no un error crudo). | ✓ `middlewares/auth.js:requireAdmin` redirige a `/` con mensaje flash |

## 3. Requisitos no funcionales

| ID | Requisito | Estado / mecanismo actual |
|----|-----------|-----------------------------|
| RNF-01 | **Seguridad** — contraseñas con hash, SQL parametrizado, sesiones seguras, validación server-side, subida de archivos controlada. | ✓ `bcrypt`, `pg` parametrizado en todos los modelos, `express-session`, `multer` con whitelist de extensión y límite de tamaño (5 MB). Ver `docs/SECURITY_REVIEW.md` (pendiente de crear) para el detalle amenaza → control. |
| RNF-02 | **Mantenibilidad** — separación de responsabilidades, sin lógica de negocio en las vistas. | ✓ Organización por módulos (`routes/controller/model/views` por entidad); fábrica de catálogos evita duplicar 4 módulos casi idénticos. |
| RNF-03 | **Integridad de datos** — normalización hasta 4FN, restricciones de unicidad/CHECK/FK a nivel de motor. | ✓ Esquema, stored procedures, triggers y vista **cargados y verificados en vivo** contra PostgreSQL 18 local (`db/00`…`06`); las 6 pruebas negativas de integridad (ISBN duplicado, stock/precio negativo, FK inexistente, `DELETE` restringido, segundo administrador) fallaron exactamente como se esperaba. Sigue faltando la documentación formal de la evolución 1FN→4FN (`docs/NORMALIZATION_4FN.xlsx`, `docs/DB_DESIGN_ER_4FN.png`) y repetir esta carga en la instancia GCP real. |
| RNF-04 | **Rendimiento básico** — consultas de listado e índices para búsquedas frecuentes. | ✓ Índices `ix_libros_titulo`, `ix_imagenes_libro_id`; pool de conexiones (`pg.Pool`) reutilizado, no una conexión por request. |
| RNF-05 | **Usabilidad** — mensajes de confirmación/error comprensibles, navegación consistente. | ✓ Patrón flash (`req.session.flash`) + partials comunes (`header`, `footer`, `alerts`). |
| RNF-06 | **Disponibilidad** — el proceso Node debe poder reiniciarse solo ante fallos. | ~ Documentado en `README.md` vía `systemd` (`Restart=on-failure`), pero no hay evidencia de que ya esté desplegado así en una instancia real. |
| RNF-07 | **Trazabilidad de errores** — registrar errores en servidor sin exponer detalle interno al usuario. | ✓ Corregido el 2026-08-31: el middleware final de `app.js` sigue haciendo `console.error(err)` para el log del servidor, pero ya **no** reenvía `err.message` al usuario — siempre muestra un mensaje genérico. Sirve como red de seguridad por defecto para cualquier controlador que no capture su propio error explícitamente. |
| RNF-08 | **Facilidad de despliegue** — Node escuchando solo en localhost, publicado detrás de un reverse proxy. | ✓ Verificado en vivo el 2026-09-01 en la instancia GCP real (`integracion`): Node escucha solo en `127.0.0.1:3000` (confirmado — el puerto no responde desde fuera del servidor), NGINX publica `/library` con `proxy_redirect` + `sub_filter` reescribiendo enlaces/redirecciones, corre como servicio `systemd` (`web-monolito.service`, `Restart=on-failure`). Ver `docs/GCP_COMMANDS.md`. |

## 4. Actores y operaciones

| Actor | Puede hacer | No puede / debe rechazarse |
|-------|-------------|------------------------------|
| **Visitante** (sin sesión) | Ver `/`, `/login`, `/registro`. | Cualquier ruta de catálogo (`/libros*`) o administración (`/admin/*`) — redirige a `/login` (ver RF-04, corregido). |
| **Usuario Registrado** (`cliente`) | Iniciar/cerrar sesión, listar y buscar libros, ver detalle y conceptos de un libro. | Crear/editar/eliminar libros, catálogos, imágenes, conceptos o usuarios; acceder a `/admin/*` (redirigido con `requireAdmin`). |
| **Administrador** (máx. 1) | Todo lo del Usuario Registrado + CRUD completo de libros, autores, géneros, formatos, conceptos, imágenes y usuarios. | Crear un segundo administrador (bloqueado por índice único parcial en BD, ver RF-13). |

## 5. Riesgos identificados

| Riesgo | Mitigación actual | Estado |
|--------|--------------------|--------|
| Acceso no autorizado a rutas administrativas | Middleware `requireAdmin` en todas las rutas de escritura y en `/admin/*` | ✓ |
| Acceso no autorizado al catálogo por Visitantes | Middleware `requireLogin` en `GET /libros` y `GET /libros/:id` | ✓ ver RF-04 |
| SQL Injection | 100% de las consultas usan parámetros (`$1, $2...`) vía `pg`; no hay concatenación de strings de usuario en SQL | ✓ (falta prueba negativa documentada con caracteres especiales, ver Parte 7 del ejercicio) |
| Subida de archivos peligrosos | Filtro por extensión (`multer` `fileFilter`), límite de 5 MB, nombre de archivo generado por el sistema (no el original del usuario) | ✓ (falta validar también el MIME real del archivo, no solo la extensión — riesgo residual) |
| Exposición de credenciales | Contraseñas con `bcrypt` (10 rounds); `.env` fuera de git (`.gitignore`); `.env.example` sin valores reales | ✓ |
| Eliminación accidental de información | `ON DELETE RESTRICT` en `libro_autor`/`libro_genero`/`libro_concepto` hacia catálogos (no se puede borrar un autor/género/concepto en uso); `ON DELETE CASCADE` de libro hacia sus imágenes/relaciones | ✓ diseño coherente; falta prueba negativa documentada |
| Publicación de datos sensibles al desplegar | `.gitignore` excluye `.env`; pendiente checklist explícito antes de comprimir el `.tar.gz` de entrega (excluir `node_modules`, `.env`, claves) | ~ pendiente formalizar en `docs/SECURITY_REVIEW.md` |

## 6. Supuestos y restricciones

- Restricciones arquitectónicas del ejercicio (monolito server-side, sin API/JSON/XML, un solo Administrador) se
  respetan íntegramente — ver justificación en `docs/ENGINEERING_DECISIONS.md`.
- Se asume PostgreSQL accesible en la misma instancia o red privada que el proceso Node (no hay capa de caché ni
  colas intermedias).
- Se asume un solo servidor de aplicación (no hay balanceo de carga ni sesión distribuida); la sesión vive en
  memoria del proceso Express (`express-session` sin store externo) — limitación aceptada para el alcance del
  ejercicio, documentada como riesgo de escalabilidad en `docs/ENGINEERING_DECISIONS.md`.
- El usuario de PostgreSQL que usa la aplicación (`library_user`) no debe ser superusuario (Parte 4, punto 10) —
  pendiente de verificar en la instancia GCP real una vez creada.

## 7. Trazabilidad hacia el resto de la entrega

Este documento alimenta directamente:
- `docs/ENGINEERING_DECISIONS.md` (decisiones que resuelven estos requisitos).
- `docs/TEST_PLAN.md` (cada caso de prueba deberá referenciar un RF-xx o RNF-xx de aquí).
- `docs/SECURITY_REVIEW.md` (cada control referenciará un riesgo de la sección 5).
