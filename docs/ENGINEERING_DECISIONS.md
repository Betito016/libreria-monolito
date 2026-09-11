# Registro de Decisiones de Ingeniería

Ejercicio 02 · Integración de Aplicaciones Computacionales · UDEM

Cada entrada sigue el esquema pedido en el enunciado:

> Necesidad o problema → alternativas consideradas → decisión tomada → justificación técnica → riesgo o limitación → evidencia de validación

Este archivo se actualiza conforme avanza el ejercicio (incluye ya las decisiones tomadas al construir
`apps/web-monolito/`, y se irán añadiendo las de infraestructura GCP, despliegue y pruebas conforme se completen).

---

## D-01. Arquitectura monolítica server-side

- **Necesidad/problema:** Elegir cómo se comunican la interfaz, la lógica de negocio y el acceso a datos para
  gestionar el catálogo de una librería con CRUD completo, autenticación y roles.
- **Alternativas consideradas:**
  1. Monolito server-side (Express + EJS, sin API intermedia).
  2. Backend API REST/JSON + frontend SPA (React/Vue) consumiendo esa API.
  3. Arquitectura de microservicios (un servicio por entidad: libros, usuarios, imágenes...).
- **Decisión tomada:** Monolito server-side con Express y EJS, un único proceso desplegable.
- **Justificación técnica:** El enunciado del ejercicio lo exige explícitamente (restricción arquitectónica: sin
  API REST/GraphQL/SOAP, sin JSON/XML entre frontend y backend). Independientemente de esa restricción, para el
  tamaño del problema (7 entidades, un equipo de una persona, sin necesidad de escalar componentes por separado)
  un monolito minimiza la complejidad operativa: un solo despliegue, un solo runtime que monitorear, sin necesidad
  de versionar un contrato de API entre capas.
- **Riesgo o limitación:** Escalar horizontalmente el sistema completo cuando solo una parte (p. ej. subida de
  imágenes) tuviera alta carga es más costoso que en una arquitectura desacoplada; el acoplamiento entre vistas y
  lógica de negocio dificulta reemplazar la interfaz sin tocar el backend. Se documenta el análisis completo de
  este trade-off en `docs/TEST_PLAN.md`/reporte técnico (Tarea 2c del ejercicio, ~600 palabras comparando monolito
  vs. desacoplado vs. microservicios).
- **Evidencia de validación:** `apps/web-monolito/src/app.js` monta todos los módulos (`auth`, `libros`,
  `usuarios`, `autores`, `generos`, `formatos`, `conceptos`) en un único `express()` y un único proceso
  (`src/server.js`); no existe ningún endpoint que devuelva `application/json`.

---

## D-02. Acceso directo a PostgreSQL con `pg` parametrizado (sin ORM, sin API intermedia)

- **Necesidad/problema:** Decidir cómo la aplicación lee y escribe en PostgreSQL.
- **Alternativas consideradas:**
  1. Driver `pg` nativo con consultas SQL parametrizadas escritas a mano.
  2. Un ORM (Sequelize, Prisma, TypeORM).
  3. Una capa de API/servicio de datos intermedia.
- **Decisión tomada:** Driver `pg` con `Pool` centralizado (`src/config/db.js`) y SQL parametrizado en cada
  `*.model.js`.
- **Justificación técnica:** El enunciado exige acceso directo a PostgreSQL vía `pg`, sin capas intermedias. Más
  allá de esa restricción, el modelo de datos (tablas puente `libro_autor`, `libro_genero`, `libro_concepto` con
  atributo propio, imágenes 1:N) requiere control fino sobre `JOIN`s y transacciones que un ORM generalista suele
  ocultar o complicar; con 7 entidades el costo de escribir SQL a mano es bajo y da control total sobre los
  índices/constraints ya definidos en `db/01_schema.sql`.
- **Riesgo o limitación:** Sin ORM, la responsabilidad de parametrizar cada consulta recae 100% en el
  desarrollador — un solo `model.js` que concatene un valor de usuario en el SQL reintroduce el riesgo de SQL
  Injection que se buscaba evitar. Se mitiga con revisión de código (ninguna consulta actual concatena valores de
  `req.body`/`req.params`; todas usan `$1, $2...`).
- **Evidencia de validación:** Cualquier `*.model.js` en `apps/web-monolito/src/modules/*`, por ejemplo
  `libros.model.js` y `catalogo.factory.js`, usa `pool.query(sql, [valores])` en el 100% de los casos.

---

## D-03. Renderizado server-side con EJS (sin frontend framework, sin JSON)

- **Necesidad/problema:** Elegir cómo se genera la interfaz que ve el usuario.
- **Alternativas consideradas:**
  1. EJS con `res.render()` desde el servidor (HTML final generado en cada request).
  2. Otro motor de plantillas server-side (Pug, Handlebars).
  3. SPA (React/Vue) que consuma datos vía `fetch` y renderice en el navegador.
- **Decisión tomada:** EJS, con formularios HTML clásicos (`POST` + redirección, patrón Post/Redirect/Get).
- **Justificación técnica:** Cumple la restricción de "cero JSON/XML entre frontend y backend" sin esfuerzo extra
  (una SPA necesitaría inventar un formato de intercambio que el ejercicio prohíbe). EJS permite mezclar JS/HTML de
  forma directa y sencilla de depurar sin build step (a diferencia de JSX/Vue SFC), adecuado para un equipo de una
  persona y un alcance de 7 entidades.
- **Riesgo o limitación:** Sin separación cliente/servidor, cada acción de escritura implica una recarga completa
  de página (peor UX que una SPA); mezclar demasiada lógica en las vistas EJS es un riesgo de mantenibilidad si no
  se disciplina — se mitiga manteniendo las vistas solo con iteración/condicionales de presentación y delegando
  toda regla de negocio a los controladores/modelos (ver D-04).
- **Evidencia de validación:** No existe ninguna ruta que responda `res.json(...)` en todo `apps/web-monolito/src`;
  todas las vistas están en `views/*.ejs` dentro de cada módulo.

---

## D-04. Organización por módulos (MVC) + fábrica de catálogos

- **Necesidad/problema:** Evitar concentrar toda la lógica en `app.js` o en las vistas, y evitar duplicar el mismo
  CRUD cuatro veces para `autores`, `generos`, `formatos` y `conceptos` (tablas estructuralmente idénticas: `id` +
  una columna de texto única).
- **Alternativas consideradas:**
  1. Un módulo completo (`model`/`controller`/`routes`/`views`) por entidad, duplicando código para los 4
     catálogos simples.
  2. Una fábrica (`catalogo.factory.js`) que genera el módulo MVC completo para cualquier catálogo simple,
     parametrizada por tabla/columna/etiqueta.
  3. Meter toda la lógica de rutas directamente en `app.js`.
- **Decisión tomada:** Organización por módulos tipo MVC (`routes/controller/model/views` por entidad de negocio),
  con una fábrica compartida (opción 2) solo para los 4 catálogos idénticos; `libros`, `usuarios` y `auth`
  mantienen su propio módulo completo porque tienen lógica propia (imágenes, conceptos, roles, sesión).
- **Justificación técnica:** La fábrica elimina ~4x duplicación de código estructuralmente idéntico sin romper la
  separación de responsabilidades que pide el ejercicio (routes/controller/model siguen existiendo, solo que se
  generan dinámicamente). `libros` y `usuarios` no entran en la fábrica porque su lógica no es genérica (relaciones
  M:N, imágenes, reglas de un-solo-administrador).
- **Riesgo o limitación:** La fábrica añade una capa de indirección: alguien que busque "el controlador de
  autores" no encontrará un `autores.controller.js` explícito, sino que debe entender `catalogo.factory.js` y cómo
  se invoca desde `autores.routes.js`. Se documenta explícitamente en comentarios del propio archivo para mitigar
  esta pérdida de "grep-abilidad".
- **Evidencia de validación:** `apps/web-monolito/src/modules/catalogo/catalogo.factory.js` genera model +
  controller + router; `modules/autores/autores.routes.js` (y generos/formatos/conceptos) solo instancian la
  fábrica con sus parámetros.

---

## D-05. Autenticación por sesión de servidor (no JWT/tokens)

- **Necesidad/problema:** Decidir cómo se identifica a un usuario autenticado entre requests.
- **Alternativas consideradas:**
  1. Sesión de servidor con cookie de sesión (`express-session`), estado guardado en el proceso Node.
  2. Tokens JWT almacenados en el cliente (localStorage o cookie), sin estado en el servidor.
- **Decisión tomada:** Sesión de servidor con `express-session`, cookie `httpOnly` por defecto, expiración de 4
  horas (`cookie.maxAge`).
- **Justificación técnica:** Coherente con un monolito que renderiza HTML: no hay un cliente JS que necesite
  adjuntar un token en cada `fetch` (de hecho no hay `fetch` de datos, todo es navegación de página completa). JWT
  añadiría complejidad (firma, expiración, revocación) sin resolver ningún problema que la sesión de servidor no
  resuelva ya para este alcance.
- **Riesgo o limitación:** La sesión vive en memoria del proceso (`MemoryStore` por defecto de `express-session`,
  no configurado explícitamente en `app.js`); si el proceso se reinicia, todas las sesiones activas se pierden, y
  la solución no escalaría a múltiples instancias sin un store compartido (Redis, Postgres). Aceptable para el
  alcance del ejercicio (un solo proceso), pero es una limitación a declarar en el reporte técnico si se pregunta
  por escalabilidad futura.
- **Evidencia de validación:** `apps/web-monolito/src/app.js:35-40` configura `express-session`;
  `middlewares/auth.js` verifica `req.session.user` en cada ruta protegida.

---

## D-06. Regla "máximo un Administrador" reforzada en la base de datos, no solo en la aplicación

- **Necesidad/problema:** El ejercicio exige que solo pueda existir un usuario Administrador, y que esa regla se
  proteja también a nivel de base de datos (Parte 3, punto 6).
- **Alternativas consideradas:**
  1. Validar solo en el controlador (`SELECT COUNT(*) WHERE rol='administrador'` antes de cada `INSERT`/`UPDATE`).
  2. Índice único parcial en PostgreSQL (`CREATE UNIQUE INDEX ... WHERE rol = 'administrador'`).
  3. Trigger `BEFORE INSERT/UPDATE` que lance una excepción si ya existe un administrador.
- **Decisión tomada:** Índice único parcial (opción 2) como mecanismo principal.
- **Justificación técnica:** Un índice único parcial es la forma idiomática en PostgreSQL de expresar "a lo más
  una fila cumple esta condición"; se aplica atómicamente en cualquier `INSERT`/`UPDATE` concurrente sin necesidad
  de un `SELECT` previo (que sería vulnerable a condiciones de carrera bajo concurrencia), y es más simple de
  auditar que un trigger con lógica PL/pgSQL propia.
- **Riesgo o limitación:** El error que PostgreSQL devuelve ante una violación (`duplicate key value violates
  unique constraint "ux_un_solo_administrador"`) es un mensaje técnico de bajo nivel; si se propagara tal cual al
  usuario final violaría RNF-07 (no exponer detalles internos). Mitigado en `usuarios.controller.js:actualizar`,
  que captura el error y muestra un mensaje de negocio ("ya existe un administrador registrado").
- **Evidencia de validación:** `db/01_schema.sql:60-66` (`ux_un_solo_administrador`);
  `usuarios.controller.js:33-39` captura el error y traduce el mensaje.

---

## D-07. Carga de imágenes con `multer`, nombre generado por el sistema

- **Necesidad/problema:** Permitir subir imágenes de portada/galería por libro sin exponer riesgos de path
  traversal, sobrescritura de archivos o ejecución de archivos maliciosos disfrazados de imagen.
- **Alternativas consideradas:**
  1. Guardar el archivo en disco con el nombre original enviado por el usuario.
  2. Guardar el archivo en disco con un nombre generado por el sistema (`libro-<id>-<timestamp>.<ext>`), validando
     extensión y tamaño antes de aceptarlo.
  3. Guardar el binario directamente en PostgreSQL (`bytea`).
- **Decisión tomada:** Opción 2 — `multer.diskStorage` con nombre generado por el sistema; la base de datos solo
  guarda la ruta relativa (`/uploads/<nombre>`) y metadatos (`texto_alt`, `es_principal`, `orden`).
- **Justificación técnica:** Usar el nombre original del usuario permite path traversal (`../../etc/passwd`) o
  colisiones/sobrescritura entre usuarios; generarlo del lado del servidor elimina ambos riesgos por construcción.
  Guardar el archivo en disco (no en BD) evita inflar la base de datos con binarios y es más simple de servir vía
  `express.static`/reverse proxy.
- **Riesgo o limitación:** El filtro actual (`middlewares/upload.js`) valida solo la **extensión** del archivo
  (`.jpg/.jpeg/.png/.webp/.gif`), no el tipo MIME real ni la firma binaria (*magic bytes*) del archivo — un
  atacante podría renombrar un archivo ejecutable a `.png`. Riesgo residual a documentar en
  `docs/SECURITY_REVIEW.md` y, si el tiempo lo permite, mitigar con una librería de sniffing de tipo (`file-type`).
- **Evidencia de validación:** `apps/web-monolito/src/middlewares/upload.js` (filtro de extensión, límite 5 MB,
  `filename` con `Date.now()`); tabla `imagenes` en `db/01_schema.sql:145-153` solo con `url_imagen` (texto), sin
  columna binaria. **Verificado en vivo el 2026-09-01** contra la instancia GCP real: subida de un PNG real vía
  `curl` (`multipart/form-data`), archivo guardado como `/uploads/libro-17-<timestamp>.png` (nunca el nombre
  original), servido correctamente a través de NGINX bajo `/library/uploads/...` (ver TC-37 en
  `docs/TEST_PLAN.md`).
- **Mejora futura menor detectada en esa misma prueba (no crítica, no es un riesgo de seguridad):** al eliminar
  la imagen marcada como `es_principal`, ninguna otra imagen del libro se promueve automáticamente — el libro
  queda sin portada hasta que un administrador marque otra manualmente. El índice único parcial sigue siendo
  correcto (permite 0 o 1 fila con `es_principal = TRUE`, nunca más de 1), así que no hay inconsistencia de
  datos; es solo una mejora de UX pendiente (reasignar la imagen más antigua restante como principal dentro de
  `eliminarImagen()` si no queda ninguna marcada).

---

## D-08. Manejo centralizado de errores sin exponer detalle interno

- **Necesidad/problema:** Evitar que un error de PostgreSQL o una excepción de Node lleguen al usuario final como
  stack trace o mensaje técnico crudo (requisito de seguridad explícito del ejercicio).
- **Alternativas consideradas:**
  1. Middleware de error único al final de `app.js` que capture cualquier excepción no manejada.
  2. Dejar que cada controlador maneje sus propios errores sin un mecanismo de respaldo común.
- **Decisión tomada:** Ambas cosas: middleware de error final en `app.js` **como red de seguridad**, más manejo
  específico en los controladores que ya conocen mensajes de negocio útiles (ISBN duplicado, catálogo en uso,
  segundo administrador).
- **Justificación técnica:** El middleware final asegura que ninguna excepción no capturada tumbe el proceso o
  muestre un stack trace de Express; el manejo específico en cada controlador permite dar mensajes accionables
  ("el ISBN ya existe") en vez de un genérico "ocurrió un error".
- **Riesgo o limitación:** *(Resuelto el 2026-08-31)* el middleware final reenviaba `err.message` tal cual al
  flash de usuario. Se corrigió para que siempre muestre un mensaje genérico ("Ocurrió un error inesperado...")
  y deje el detalle real únicamente en `console.error`. Limitación restante, aceptada: si un controlador captura
  su propio error y arma un mensaje a partir de datos del propio error (no es el caso actual), debe seguir la
  misma disciplina de no citar texto crudo de Postgres.
- **Evidencia de validación:** `apps/web-monolito/src/app.js:65-71` (mensaje genérico fijo, no interpola
  `err.message`); contraejemplos ya mitigados en `libros.controller.js:crear/actualizar` y
  `catalogo.factory.js:crear/actualizar/eliminar`.

---

## D-14. Consolidar el esquema duplicado (`data/db_scheme.sql` vs. `db/esquema.sql`) en `db/01_schema.sql`

- **Necesidad/problema:** el repositorio tenía dos copias casi idénticas del esquema (`data/db_scheme.sql` y
  `db/esquema.sql`, con comentarios ligeramente distintos) más `data/seed.sql`, sin la nomenclatura `00`…`06` que
  pide la Parte 3/4 del ejercicio para cargar `db/` en orden.
- **Alternativas consideradas:**
  1. Dejar ambas copias y solo agregar los archivos `00`, `02`–`06` nuevos alrededor.
  2. Consolidar en una sola fuente de verdad bajo `db/`, con la nomenclatura exacta que pide el ejercicio, y borrar
     las copias antiguas.
- **Decisión tomada:** opción 2. `db/01_schema.sql` es ahora la única definición del esquema; se eliminaron
  `data/db_scheme.sql`, `db/esquema.sql`, `data/seed.sql` y la carpeta `data/` completa.
- **Justificación técnica:** dos copias del mismo esquema es un riesgo de "código limpio" concreto: cualquier
  cambio futuro (una columna nueva, un CHECK adicional) tenía que aplicarse dos veces o los archivos divergían sin
  que nada lo advirtiera — de hecho ya habían divergido en los comentarios antes de esta consolidación. Además, la
  nomenclatura `00`…`06` es la que el propio ejercicio pide para documentar el orden de carga (Parte 4, punto 10).
- **Riesgo o limitación:** el `README.md` y cualquier instancia GCP que ya se haya cargado con
  `data/db_scheme.sql` (ver nota del usuario: ya existe una instancia funcionando desde antes de esta sesión)
  seguirá teniendo el esquema viejo hasta que se vuelva a cargar `db/01_schema.sql` — no es un cambio retroactivo
  automático. `README.md` se actualizó para reflejar solo la ruta nueva.
- **Evidencia de validación:** `git status` tras el cambio confirma que `data/` ya no existe y que `db/` contiene
  únicamente `00_create_database.sql` … `06_views.sql`.

  El mismo problema existía con la documentación de despliegue: `apps/web-monolito/README.md` era casi un
  duplicado exacto de `README.md` (raíz), con las mismas instrucciones de instalación repetidas palabra por
  palabra. Se aplicó el mismo principio: `apps/web-monolito/README.md` ahora solo documenta las notas de diseño
  específicas de la app y enlaza al `README.md` raíz como única fuente de verdad para instalación/despliegue.

## D-15. Privilegios mínimos de `library_user` resueltos en `db/00_create_database.sql` + `db/01_schema.sql`

- **Necesidad/problema:** `library_user` era `OWNER` de `library_db` (ver brecha #7 en `docs/SECURITY_REVIEW.md`,
  control 9), muy por encima de lo que la aplicación necesita en tiempo de ejecución.
- **Alternativas consideradas:**
  1. Mantener a `library_user` como `OWNER` (como estaba).
  2. Crear la base con un superusuario/rol distinto, y otorgarle a `library_user` solo
     `SELECT, INSERT, UPDATE, DELETE` sobre las tablas ya creadas.
- **Decisión tomada:** opción 2. `db/00_create_database.sql` crea el rol y la base (esta última sin asignársela a
  `library_user`); `db/01_schema.sql` crea las tablas como superusuario y, al final, le otorga a `library_user`
  exactamente `GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES` + `GRANT USAGE, SELECT ON ALL SEQUENCES`.
- **Justificación técnica:** si el proceso Node se ve comprometido, el atacante hereda los privilegios de
  `library_user` — con esta decisión, como máximo puede leer/escribir filas, nunca `DROP TABLE`, `DROP DATABASE`,
  ni crear roles nuevos.
- **Riesgo o limitación:** ahora hay una dependencia de orden más estricta: `01_schema.sql` debe ejecutarse como
  superusuario (no como `library_user`, que no puede otorgarse privilegios a sí mismo), y cualquier objeto nuevo
  creado después (como la vista de D-16) necesita su propio `GRANT` explícito — Postgres no hereda privilegios
  hacia objetos creados con posterioridad. Documentado en `db/06_views.sql`.
- **Evidencia de validación:** **Verificado en vivo (D-18)** contra una instancia local PostgreSQL 18: tras cargar
  `00` y `01` como `postgres`, se confirmó que `library_user` puede hacer `SELECT/INSERT/UPDATE/DELETE` sobre las
  tablas pero **no** puede crear objetos — intentar cargar `04_stored_procedures.sql` como `library_user` falla
  con `ERROR: permiso denegado al esquema public`, exactamente como se esperaba. Pendiente únicamente repetir esta
  carga en la instancia GCP real del usuario (que sigue con `library_user` como `OWNER` del intento anterior a
  esta sesión).

## D-16. Formalizar `vista_catalogo_libros` y conectarla a `libros.model.js:listar()`

- **Necesidad/problema:** la Parte 3, punto 14 del ejercicio pide que el CRUD se apoye en vistas, no solo en SQL
  suelto dentro de la aplicación; `libros.model.js:listar()` ya tenía un `JOIN + GROUP BY` no trivial (autores
  concatenados, subconsulta de portada) que era candidato natural.
- **Alternativas consideradas:**
  1. Dejar el JOIN inline en `libros.model.js` (como estaba).
  2. Convertirlo en una vista (`vista_catalogo_libros`) y que el modelo haga `SELECT ... FROM vista_catalogo_libros`.
- **Decisión tomada:** opción 2, pero **solo para esta consulta**. `obtenerDetalle()` (autores/géneros/imágenes/
  conceptos de un libro puntual) se dejó como JOINs simples parametrizados por `libro_id` — envolverlos en vistas
  no agrega valor real (YAGNI) y sí una capa extra de indirección.
- **Justificación técnica:** la vista centraliza en un solo lugar la lógica de "cómo se arma el listado de
  libros" (útil si mañana un reporte de inventario necesita lo mismo), y es exactamente el tipo de artefacto de
  base de datos que el ejercicio pide evidenciar con `psql`.
- **Riesgo o limitación:** el cambio en `libros.model.js` es de bajo riesgo (una sola consulta de lectura, mismas
  columnas/alias que antes, verificado contra `list.ejs` que las usa). *(Actualizado en D-18: ya verificado en
  vivo — sin riesgo pendiente.)*
- **Evidencia de validación:** `node -c` sobre `libros.model.js` (sin errores de sintaxis JS); comparación manual
  de columnas entre `db/06_views.sql` y `libros/views/list.ejs`. **Verificado en vivo (D-18):** `SELECT * FROM
  vista_catalogo_libros` como `library_user` funciona; `GET /libros` con sesión real devuelve las 32 tarjetas del
  catálogo, incluida la del libro de Cloud Computing.

## D-18. Verificación en vivo de `db/00`…`06` y conexión de los stored procedures a la app (D-17 cerrada)

- **Necesidad/problema:** todo el trabajo de D-14 a D-16 se había hecho "a ciegas" (sin `psql`/Docker disponibles
  en la sesión), documentado con el estado `~` ("revisado por código, no ejecutado"). El usuario instaló
  PostgreSQL 18 localmente a mitad de esta sesión, lo que permitió por primera vez ejecutar los scripts contra un
  motor real y cerrar esa brecha de verificación.
- **Qué se hizo:** se cargaron en orden `db/00_create_database.sql` → `06_views.sql` contra una instancia local
  (PostgreSQL 18), se corrieron las 6 pruebas negativas de integridad de `docs/TEST_PLAN.md` (TC-15 a TC-20), la
  prueba de inyección SQL (TC-28), el trigger de `actualizado_en`, y luego se levantó la aplicación completa
  (`apps/web-monolito`) apuntando a esa base y se ejercitaron los flujos reales por HTTP: login de administrador y
  de cliente, catálogo (32 libros vía `vista_catalogo_libros`), ficha del libro de Cloud Computing (10 conceptos
  renderizados), creación/edición de libros con múltiples autores y géneros, rechazo de precio negativo,
  restricciones de rol para `cliente` (incluyendo que el HTML que recibe un `cliente` real no contiene ningún
  botón de administración — cierra TC-14 con evidencia real, no solo lectura de código), registro con contraseña
  corta rechazado, e intento de crear un segundo administrador (rechazado tanto por `psql` directo como por la
  ruta de la app, con el mensaje traducido correcto). El log del servidor no mostró ningún error no manejado
  durante toda la sesión de pruebas.
- **Bugs reales encontrados y corregidos gracias a poder ejecutar esto** (ninguno se habría detectado solo
  revisando el código):
  1. `db/02_seed_30_per_table.sql` tenía una sintaxis SQL inválida en los `INSERT` de una sola columna
     (`formatos`, `generos`, `autores`, `conceptos`): escribía `VALUES 'a', 'b', 'c'` en vez de
     `VALUES ('a'), ('b'), ('c')`. Corregido.
  2. El placeholder de contraseña en `db/00_create_database.sql` incluía una "ñ"
     (`CAMBIA_ESTA_CONTRASEÑA_ANTES_DE_USAR`), lo que causaba un error de codificación UTF-8 al autenticarse
     después (la codificación con la que `CREATE ROLE` guardó el valor no coincidía con la que usaba el cliente
     al conectarse). Cambiado a un placeholder solo-ASCII, con una nota explicando por qué.
  3. El `README.md` decía que `db/04_stored_procedures.sql`, `05_triggers.sql` y `06_views.sql` debían cargarse
     como `library_user` — **falso**: son DDL y `library_user` no tiene privilegio `CREATE` sobre el esquema
     (confirmado con `ERROR: permiso denegado al esquema public`). Corregido: esos tres se cargan como
     `postgres`, igual que `00` y `01`.
  4. El comentario de "verificación manual" dentro de `db/04_stored_procedures.sql` usaba subconsultas
     directamente como argumento de `CALL` (`CALL sp_x((SELECT ...), ...)`), lo cual PostgreSQL rechaza
     explícitamente ("no se puede usar una subconsulta en un argumento a CALL"). Corregido usando la técnica de
     `psql` con `\gset`. Esta restricción **no afecta** a la aplicación Node, porque ahí los valores llegan ya
     resueltos como parámetros de `pg`, nunca como subconsultas literales.
- **Decisión resultante (cierra D-17):** con todo esto verificado, se reemplazó la transacción manual de
  `libros.model.js:asignarAutores/asignarGeneros` (BEGIN/DELETE/INSERT×N/COMMIT en JS) por una sola llamada
  `pool.query('CALL sp_asignar_autores_libro($1, $2)', [libroId, autorIds])` (e igual para géneros). Se probó en
  vivo: crear un libro con 2 autores + 1 género, editarlo para reemplazar por un autor distinto y quitar todos los
  géneros — en ambos casos el resultado en la base fue exactamente el esperado.
- **Riesgo o limitación:** la instancia GCP que el usuario ya tenía corriendo desde antes de esta sesión **no**
  tiene ninguno de estos cambios — sigue con el esquema viejo, `library_user` como `OWNER`, y sin los stored
  procedures. Hay que repetir ahí la carga completa `00`→`06` para que el entorno real quede al día con lo que ya
  se verificó en local.
- **Evidencia de validación:** sesión de pruebas completa en esta conversación (comandos `psql`/`curl` y sus
  salidas); `git status` confirma los archivos tocados: `db/00_create_database.sql`, `db/02_seed_30_per_table.sql`,
  `db/04_stored_procedures.sql`, `README.md`, `libros.model.js`.

## D-19. Publicar `/library` reescribiendo con NGINX (`sub_filter`/`proxy_redirect`), sin modificar la aplicación

- **Necesidad/problema:** la aplicación genera todos sus enlaces, formularios y redirecciones como rutas
  absolutas desde raíz (`href="/libros"`, `action="/logout"`, `res.redirect('/')`), sin conocer ningún prefijo.
  El ejercicio exige publicarla bajo `/library` (Parte 8), y un `proxy_pass` simple habría dejado esos enlaces
  rotos apuntando fuera del prefijo.
- **Alternativas consideradas:**
  1. Modificar cada controlador (`res.redirect`) y cada vista EJS (`href`/`action`/`src`) para que use un
     `BASE_PATH` configurable, o montar toda la app bajo un `express.Router()` con ese prefijo.
  2. Resolverlo enteramente en NGINX: `proxy_redirect` para la cabecera `Location` de las redirecciones, y
     `sub_filter` para reescribir `href="/`, `action="/` y `src="/` en el cuerpo HTML de la respuesta.
- **Decisión tomada:** opción 2.
- **Justificación técnica:** la opción 1 significa tocar ~30-40 lugares del código (todo controlador que hace
  `res.redirect`, toda vista EJS con un enlace o formulario) sin poder probar cada uno contra un entorno real
  antes de esta sesión — exactamente el tipo de cambio amplio y difícil de verificar que se ha evitado a lo largo
  de todo este trabajo. La opción 2 es una técnica estándar de reverse-proxy para aplicaciones que no conocen su
  propio prefijo de montaje, no requiere tocar una sola línea de `apps/web-monolito/src`, y es reversible con
  solo editar la configuración de NGINX.
- **Riesgo o limitación:** `sub_filter` reescribe *cualquier* `href="/`, `action="/` o `src="/` en el HTML de
  respuesta — si en el futuro se agregara un enlace externo escrito exactamente así (poco probable, ningún caso
  actual lo hace) se reescribiría también por error. Tampoco reescribe URLs generadas dinámicamente por
  JavaScript del lado del cliente (la app no tiene ninguna hoy). Documentado para que quien mantenga el proyecto
  sepa por qué el prefijo funciona sin verlo en el código Node.
- **Evidencia de validación:** verificado end-to-end desde un cliente externo real contra la instancia GCP:
  navegación, login, sesión y catálogo funcionando bajo `http://<IP>/library/` con todos los enlaces/formularios
  correctamente reescritos. Detalle completo en `docs/GCP_COMMANDS.md`, sección 5, y configuración versionada en
  `docs/nginx-libreria.conf`.

## Decisiones pendientes de registrar

- **D-11 (parcial)** — Apache/NGINX como reverse proxy bajo `/library`: la configuración base ya está hecha y
  verificada (ver D-19); queda pendiente evaluar si agregar HTTPS/TLS, que el ejercicio no exige explícitamente.

## Historial de correcciones aplicadas

Brechas detectadas durante la propia redacción de este registro y de `docs/SECURITY_REVIEW.md`, corregidas de
inmediato en el código porque eran de bajo riesgo de romper algo más y de alta relevancia para la rúbrica
(requisitos explícitos del ejercicio). Cada una se verificó con `node -c` (sintaxis) y, para RF-04, con un smoke
test manual del servidor.

| Fecha | Cambio | Archivo(s) | Motivo |
|-------|--------|------------|--------|
| 2026-08-31 | `requireLogin` en `GET /libros` y `GET /libros/:id` | `libros.routes.js` | RF-04 — el catálogo debía requerir sesión iniciada, no era público |
| 2026-08-31 | Middleware de error final ya no reenvía `err.message` al usuario | `app.js` | D-08 / RNF-07 — evitar filtrar mensajes internos de PostgreSQL |
| 2026-08-31 | Validación server-side de `libros` (ISBN/título/formato obligatorios; precio y stock numéricos ≥ 0; año entero positivo) antes del `INSERT`/`UPDATE` | `libros.controller.js` | Control 4 de `SECURITY_REVIEW.md` — no depender solo de los `CHECK` de la BD |
| 2026-08-31 | Longitud mínima de contraseña (8 caracteres) en registro | `auth.controller.js` | Control 1 de `SECURITY_REVIEW.md` — política básica de contraseñas |
| 2026-09-01 | `HOST` por defecto cambiado de `'0.0.0.0'` a `'127.0.0.1'` | `server.js` | Control 10 de `SECURITY_REVIEW.md` — detectado al desplegar en la instancia GCP real: sin `HOST` explícito en `.env`, Node quedaba expuesto a toda interfaz de red, violando la Parte 8, punto 19 |

Quedan abiertas (deliberadamente no tocadas todavía, por ser de infraestructura o de mayor alcance): fallback
hardcodeado de `SESSION_SECRET`, validación de MIME/magic-bytes en imágenes, y cerrar el puerto 3000 en el
firewall de GCP (pendiente hasta tener el reverse proxy verificado — control 11 de `docs/SECURITY_REVIEW.md`).
