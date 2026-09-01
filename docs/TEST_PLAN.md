# Plan y Matriz de Pruebas — Librería en Línea

Ejercicio 02 · Integración de Aplicaciones Computacionales · UDEM
Parte 7, punto 18 · Tarea 2b (mínimo 15 casos, positivos y negativos).

Cada caso referencia un requisito de `docs/REQUIREMENTS.md` (RF-xx / RNF-xx) y, cuando aplica, una brecha de
`docs/SECURITY_REVIEW.md`. **Estado** usa tres valores para no fingir evidencia que no existe:

- ✓ **Aprobada** — ejecutada realmente contra el sistema, con evidencia.
- ~ **Verificada por code review** — la lógica que la prueba ejercita ya existe y se revisó en el código, pero
  todavía no se ha ejecutado end-to-end.
- ✗ **Pendiente** — no ejecutable todavía porque depende de infraestructura, seed de datos o despliegue que faltan
  (o, en un caso, documenta deliberadamente un riesgo aún no resuelto).

**Actualización 2026-08-31 (D-18 en `docs/ENGINEERING_DECISIONS.md`):** el usuario instaló PostgreSQL 18
localmente a mitad de esta sesión. Se cargó `db/00`…`06` contra esa instancia y se levantó la aplicación completa
apuntando a ella, lo que permitió pasar de "revisado por código" a "ejecutado y verificado" en la mayoría de los
casos de esta matriz. Lo que sigue pendiente depende específicamente de la instancia GCP real (Parte 4) y del
reverse proxy (Parte 8), no de la lógica de la aplicación.

---

## 1. Pruebas funcionales: login, logout, búsqueda

| ID | Requisito | Caso (precondición → entrada → pasos) | Resultado esperado | Resultado observado / Evidencia | Estado |
|----|-----------|----------------------------------------|----------------------|-----------------------------------|--------|
| TC-01 | RF-02 | Usuario ya registrado y activo. `POST /login` con email y password correctos. | Redirección a `/`, flash "Bienvenido, &lt;nombre&gt;.", `req.session.user` con id/nombre/rol. | ✓ Ejecutada: login del administrador sembrado (`admin@libreria.test` / `Password123`) contra la app real → `302` a `/`, sesión con cookie válida usada en el resto de las pruebas de esta sesión. | ✓ |
| TC-02 | RF-02 | Usuario existente. `POST /login` con password incorrecto. | Redirección a `/login`, flash "Credenciales inválidas.", sin sesión creada. | ~ `auth.controller.js:20-23` (`bcrypt.compare` falla → redirect). No se ejecutó explícitamente esta variante. | ~ |
| TC-03 | RF-03 | Sesión iniciada. `GET /logout`. | `req.session.destroy()`, redirección a `/`, siguiente request sin `usuarioActual`. | ~ `auth.controller.js:51-53`. No ejecutada explícitamente. | ~ |
| TC-04 | RF-05 | Al menos un libro con "Cloud" en el título sembrado. `GET /libros?q=cloud`. | Solo libros cuyo título o ISBN coincide (`ILIKE %cloud%`) aparecen listados. | ~ `libros.model.js:listar` verificado contra `vista_catalogo_libros` (TC-32/33). El parámetro `?q=` específico no se ejecutó vía HTTP esta sesión. | ~ |

## 2. Pruebas de cada CRUD

| ID | Requisito | Caso | Resultado esperado | Resultado observado / Evidencia | Estado |
|----|-----------|------|----------------------|-----------------------------------|--------|
| TC-05 | RF-06 | Admin autenticado. `POST /libros` con ISBN nuevo, título, precio ≥0, stock ≥0, formato válido. | Libro creado, redirección a `/libros/:id`, flash de éxito. | ✓ Ejecutada dos veces (ISBN `TEST-9999-CURL` y `TEST-SP-0001`): ambas devolvieron `302` a `/libros/<id>` y las filas aparecieron en `libros` con los valores enviados. Filas de prueba eliminadas después. | ✓ |
| TC-06 | RF-06 | Admin autenticado. `POST /libros` con precio `-10`. | **Rechazado antes del INSERT**: flash con mensaje de validación, redirección de vuelta al formulario, sin fila creada/modificada. | ✓ Ejecutada: `POST /libros/69` con `precio=-5` → `302` a `/libros/69/editar`; `SELECT precio` confirmó que el valor en la base **no cambió** (siguió en 99.90). | ✓ |
| TC-07 | RF-06 | Admin autenticado. `POST /libros` con ISBN repetido. | Flash "Verifica que el ISBN no esté repetido.", redirección a `/libros/nuevo`, sin duplicado en `libros`. | ~ Restricción `UNIQUE(isbn)` verificada directamente por `psql` (ver TC-15, mismo constraint). La ruta HTTP específica de creación con ISBN duplicado no se ejecutó. | ~ |
| TC-08 | RF-06 | Libro existente. `POST /libros/:id/eliminar` como admin. | Libro y sus imágenes eliminadas (`ON DELETE CASCADE`), redirección a `/libros`. | ~ `libros.model.js:eliminar` + FK `ON DELETE CASCADE` verificado por diseño; la limpieza de los libros de prueba de esta sesión se hizo con `DELETE` directo por `psql`, no por la ruta HTTP. | ~ |
| TC-09 | RF-07 | Admin autenticado. CRUD de `autores`/`generos`/`formatos`/`conceptos` vía `catalogo.factory.js` (crear, editar, listar, eliminar). | Cada operación persiste/lee/actualiza/borra en la tabla correspondiente; valor vacío se rechaza antes del INSERT. | ~ `catalogo.factory.js` revisado; no ejecutado vía HTTP esta sesión (los autores/géneros usados en las pruebas ya venían del seed). | ~ |
| TC-10 | RF-14 | Admin autenticado. `POST /admin/usuarios/:id` cambiando `rol`/`activo` de un usuario `cliente`. | Usuario actualizado, redirección a `/admin/usuarios`. | ~ La ruta se ejercitó en TC-20 (intento de promover a un segundo administrador, que debía fallar); el caso positivo de cambiar solo `activo` no se probó. | ~ |

## 3. Pruebas de autorización (visitante / usuario registrado / administrador)

| ID | Requisito | Caso | Resultado esperado | Resultado observado / Evidencia | Estado |
|----|-----------|------|----------------------|-----------------------------------|--------|
| TC-11 | RF-04 | Sin sesión iniciada. `GET /libros`. | Redirección `302` a `/login` (no debe mostrarse el catálogo). | ✓ Ejecutada: `curl -D-` sobre `GET /libros` sin cookie → `HTTP/1.1 302 Found`, `Location: /login`. | ✓ |
| TC-12 | RF-15 | Sesión de `cliente` (no admin). `GET /admin/usuarios` o `GET /libros/nuevo`. | `requireAdmin` redirige a `/` con flash de acceso denegado. No se ejecuta la operación. | ✓ Ejecutada con sesión real de `ana.torres@correo.test` (rol `cliente`): `GET /libros/nuevo` → `302` a `/`; `GET /admin/usuarios` → `302` a `/`. | ✓ |
| TC-13 | RF-14 | Sesión de administrador. `GET /admin/usuarios`. | Acceso permitido, lista de usuarios renderizada. | ✓ Ejecutada: con sesión de admin, `GET /admin/usuarios` devolvió `200` y la página renderizó el flash de la prueba TC-20. | ✓ |
| TC-14 | RF-04 | Sesión de `cliente`. `GET /libros`, `GET /libros/:id`. | Acceso permitido (catálogo visible, pero sin botones de administración en la vista). | ✓ Ejecutada: con sesión real de `cliente`, el HTML devuelto por `GET /libros` y `GET /libros/17` tuvo **0 coincidencias** al buscar "Nuevo libro", "Editar", "btn-peligro", "Subir imagen" y "Agregar concepto". | ✓ |

## 4. Pruebas negativas de base de datos y restricciones

Todas ejecutadas directamente por `psql` como `library_user` contra la instancia PostgreSQL 18 local.

| ID | Requisito | Caso | Resultado esperado | Resultado observado / Evidencia | Estado |
|----|-----------|------|----------------------|-----------------------------------|--------|
| TC-15 | RNF-03 | `INSERT` de un libro con el mismo ISBN que "Rayuela". | Falla con `duplicate key value violates unique constraint`. | ✓ Error real obtenido: `ERROR: llave duplicada viola restricción de unicidad «libros_isbn_key» — DETALLE: Ya existe la llave (isbn)=(9788437604572).` | ✓ |
| TC-16 | RNF-03 | `INSERT` con `stock = -5`. | Falla por `CHECK (stock >= 0)`. | ✓ Error real: `ERROR: el nuevo registro para la relación «libros» viola la restricción «check» «libros_stock_check»`. | ✓ |
| TC-17 | RNF-03 | `INSERT` con `precio = -10`. | Falla por `CHECK (precio >= 0)`. | ✓ Error real: `ERROR: ... viola la restricción «check» «libros_precio_check»`. | ✓ |
| TC-18 | RF-06 | `INSERT` con `formato_id = 999999` (FK inexistente). | Falla con `violates foreign key constraint`. | ✓ Error real: `ERROR: inserción o actualización en la tabla «libros» viola la llave foránea «libros_formato_id_fkey» — DETALLE: La llave (formato_id)=(999999) no está presente en la tabla «formatos».` | ✓ |
| TC-19 | Riesgo "eliminación accidental" | `DELETE FROM autores` sobre un autor referenciado por `libro_autor` (Julio Cortázar). | Falla por `ON DELETE RESTRICT`. | ✓ Error real: `ERROR: update or delete on table "autores" violates RESTRICT setting of foreign key constraint "libro_autor_autor_id_fkey" — DETAIL: Key (id)=(5) is referenced from table "libro_autor".` | ✓ |
| TC-20 | RF-13 | Ya existe un administrador; `UPDATE usuarios SET rol='administrador'` sobre otro usuario. Probado en dos niveles. | Falla por `ux_un_solo_administrador`; a nivel app, mensaje traducido. | ✓ **Nivel BD:** `ERROR: llave duplicada viola restricción de unicidad «ux_un_solo_administrador» — DETALLE: Ya existe la llave (rol)=(administrador).` **Nivel app:** `POST /admin/usuarios/<id de Ana Torres>` con `rol=administrador` → `302`; la página `/admin/usuarios` mostró el flash "ya existe un administrador registrado (solo puede haber uno)."; conteo de administradores se mantuvo en 1 en ambos casos. | ✓ |

## 5. Pruebas de validación de campos y archivos

| ID | Requisito | Caso | Resultado esperado | Resultado observado / Evidencia | Estado |
|----|-----------|------|----------------------|-----------------------------------|--------|
| TC-21 | Control 1 (`SECURITY_REVIEW.md`) | `POST /registro` con password de 6 caracteres. | Flash "La contraseña debe tener al menos 8 caracteres.", cuenta NO creada. | ✓ Ejecutada: `POST /registro` con `password=abc123` → `302` a `/registro`; `SELECT COUNT(*) FROM usuarios WHERE email='corta@test.test'` devolvió `0`. | ✓ |
| TC-22 | Control 7 (`SECURITY_REVIEW.md`) | Admin autenticado. `POST /libros/:id/imagenes` con un archivo `.exe` renombrado `.png`. | **Riesgo residual conocido:** el filtro actual solo mira la extensión del nombre, así que este caso **pasaría** el filtro indebidamente. | ✗ No ejecutada esta sesión (no se probó subida de imágenes); sigue documentando un riesgo residual real y no resuelto (brecha #5 en `SECURITY_REVIEW.md`). | ✗ |
| TC-23 | RF-10 | Admin autenticado. `POST /libros/:id/imagenes` con extensión fuera de la whitelist. | Rechazado por `fileFilter`. | ~ `middlewares/upload.js:24-28`. No ejecutada esta sesión. | ~ |
| TC-24 | RF-10 | Admin autenticado. Subida de una imagen de 8 MB. | Rechazada por `limits.fileSize` (máx. 5 MB). | ~ `middlewares/upload.js:33`. No ejecutada esta sesión. | ~ |

## 6. Pruebas de relaciones libro-autor, libro-género y libro-concepto

| ID | Requisito | Caso | Resultado esperado | Resultado observado / Evidencia | Estado |
|----|-----------|------|----------------------|-----------------------------------|--------|
| TC-25 | RF-08 | Admin crea/edita un libro seleccionando varios autores y un género, luego reemplaza por otro autor y quita todos los géneros. | `libro_autor`/`libro_genero` reflejan exactamente el estado final (sin duplicados, sin residuos). | ✓ Ejecutada: libro creado con 2 autores (Isabel Allende, Mario Vargas Llosa) + 1 género (Ciencia) → confirmado en BD. Editado para dejar solo 1 autor distinto (Laura Esquivel) y 0 géneros → confirmado en BD (`num_generos = 0`). | ✓ |
| TC-26 | RF-09 | El mismo concepto con definiciones distintas en libros distintos (p. ej. "Recursión" en dos libros del seed). | Ambas definiciones coexisten — valida la 4FN del modelo. | ✓ El seed (`db/02_seed_30_per_table.sql`) carga "Recursión" en dos libros distintos con textos de definición diferentes; la carga completó sin conflicto de `PRIMARY KEY (libro_id, concepto_id)` (45 filas en `libro_concepto`, conteo esperado). | ✓ |
| TC-27 | RF-09a | Seed cargado. `GET /libros/:id` del libro de Cloud Computing. | Se listan los 10 conceptos obligatorios con sus definiciones. | ✓ Ejecutada: `GET /libros/17` con sesión real devolvió HTML con las 10 coincidencias exactas: Bucket, FaaS, Hybrid Cloud, IaaS, Multicloud, PaaS, Private Cloud, Public Cloud, SaaS, Serverless. | ✓ |

## 7. Prueba de consulta SQL con caracteres especiales (verificación de parametrización)

| ID | Requisito | Caso | Resultado esperado | Resultado observado / Evidencia | Estado |
|----|-----------|------|----------------------|-----------------------------------|--------|
| TC-28 | Control 3 (`SECURITY_REVIEW.md`) | Búsqueda con `'; DROP TABLE libros; --` como valor de filtro. | El texto se trata como literal; ninguna tabla se altera. | ✓ Ejecutada contra `vista_catalogo_libros` (misma consulta parametrizada que usa `libros.model.js:listar()`): `SELECT COUNT(*) ... WHERE titulo ILIKE '%''; DROP TABLE libros; --%'` → `0` resultados; `SELECT COUNT(*) FROM libros` inmediatamente después siguió en `32` — la tabla no se alteró. | ✓ |

## 8. Prueba del despliegue mediante reverse proxy

| ID | Requisito | Caso | Resultado esperado | Resultado observado / Evidencia | Estado |
|----|-----------|------|----------------------|-----------------------------------|--------|
| TC-29 | RNF-08 / Parte 8 | Node escuchando en `127.0.0.1:3000`; Apache/NGINX configurado para `/library`. `GET http://IP_DEL_SERVIDOR/library`. | La app responde igual que en local bajo el prefijo `/library`. | ✗ No ejecutable: la instancia GCP real del usuario todavía no tiene el esquema/proxy actualizados (Parte 4 y Parte 8 pendientes). Lo probado esta sesión fue contra PostgreSQL **local**, no GCP. | ✗ |

## 9. Pruebas básicas de navegación y usabilidad

| ID | Requisito | Caso | Resultado esperado | Resultado observado / Evidencia | Estado |
|----|-----------|------|----------------------|-----------------------------------|--------|
| TC-30 | RNF-05 | Navegar `/` → `/login` → `/registro` → (tras login) `/libros` → `/libros/:id` → `/admin/usuarios`. | Todos los enlaces funcionan, sin 404 accidentales. | ✓ Ejecutada (parcial, sin clics de UI real pero cubriendo las mismas rutas): `/`, `/login`, `/registro`, `/libros`, `/libros/17`, `/libros/nuevo`, `/admin/usuarios` respondieron todos con el código esperado (200 o 302 según el caso) en esta sesión. Falta una pasada real en navegador (clics, no `curl`). | ✓ (cobertura de rutas; falta UI real) |
| TC-31 | RNF-05 | Cualquier acción de escritura exitosa o fallida. | Se muestra un mensaje flash legible. | ✓ Ejecutada: el flash "ya existe un administrador registrado (solo puede haber uno)." se confirmó renderizado en el HTML de `/admin/usuarios` después del intento de TC-20. | ✓ |

## 10. Pruebas de los artefactos de base de datos (vista, stored procedures, trigger)

| ID | Requisito | Caso | Resultado esperado | Resultado observado / Evidencia | Estado |
|----|-----------|------|----------------------|-----------------------------------|--------|
| TC-32 | RNF-03 | `db/06_views.sql` cargado. `SELECT titulo, autores, formato FROM vista_catalogo_libros ORDER BY titulo LIMIT 5;` como `library_user`. | Devuelve filas con autores concatenados y portada, sin error de permisos. | ✓ Ejecutada: devolvió 5 filas correctas (incluida "Antología del cuento latinoamericano" con 3 autores concatenados). | ✓ |
| TC-33 | RF-05 | App corriendo con `vista_catalogo_libros` ya creada. `GET /libros` con sesión real. | El catálogo carga con los 32 libros del seed. | ✓ Ejecutada: `GET /libros` devolvió HTML con 32 coincidencias de `tarjeta-libro`, incluida la del libro de Cloud Computing. | ✓ |
| TC-34 | RF-08 | `CALL sp_asignar_autores_libro(:libro_id, ARRAY[:autor_id])` vía `psql` (con `\gset`, no subconsulta directa — ver nota en `db/04_stored_procedures.sql`) tras vaciar la asignación previa. | Exactamente una fila con el autor esperado. | ✓ Ejecutada por `psql` directo (1 fila, autor correcto) **y** indirectamente por la app tras conectar D-17 (`libros.model.js` ahora llama a este procedimiento): ver TC-25. | ✓ |
| TC-35 | RF-08 | `CALL sp_asignar_generos_libro(:libro_id, ARRAY[]::INTEGER[])`. | La tabla `libro_genero` queda sin filas para ese libro. | ✓ Ejecutada por `psql` directo (`generos_restantes = 0`) **y** por la app en TC-25 (edición que dejó el libro sin géneros). | ✓ |
| TC-36 | RNF-03 | `UPDATE libros SET stock = stock` (sin cambiar el valor) sobre un libro existente. | `actualizado_en` cambia a la hora actual aunque el valor no haya cambiado (el trigger dispara en cualquier `UPDATE`). | ✓ Ejecutada: `actualizado_en` pasó de `21:06:49` a `21:08:30` en la misma sesión de pruebas, confirmando que `trg_libros_actualizado` disparó. | ✓ |

---

## Resumen de cobertura

- **36 casos** (mínimo pedido: 15), cubriendo las 9 categorías exigidas por el punto 18 del ejercicio más una
  categoría adicional (10) para los artefactos de base de datos.
- **24 aprobados con evidencia real** obtenida el 2026-08-31 contra una instancia PostgreSQL 18 local y la
  aplicación corriendo de verdad (login, catálogo, CRUD con relaciones, autorización por rol, las 6 pruebas
  negativas de integridad, inyección SQL, trigger, vista y ambos stored procedures).
- **11 verificados solo por revisión de código** — no requieren infraestructura adicional, simplemente no se
  ejecutaron en esta pasada (login con password incorrecto, logout, búsqueda por `?q=`, ISBN duplicado por HTTP,
  eliminación de libro por HTTP, CRUD de catálogos por HTTP, cambio de rol/activo exitoso, subida de imagen con
  extensión inválida/tamaño excedido).
- **2 pendientes de infraestructura real:** TC-22 (documenta un riesgo residual de seguridad no resuelto, no una
  falta de ejecución) y TC-29 (reverse proxy — depende de la instancia GCP real, no de la instancia local usada
  hoy).

**Siguiente paso natural:** repetir esta misma carga (`db/00`…`06`) contra la instancia GCP real del usuario (que
sigue con el esquema anterior a esta sesión) y volver a correr al menos TC-15 a TC-20 y TC-27 ahí, para que la
evidencia quede sobre el entorno que realmente se va a entregar — no solo sobre PostgreSQL local.
