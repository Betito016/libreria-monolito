# Historial de Prompts de IA

Ejercicio 02 · Integración de Aplicaciones Computacionales · UDEM
Tarea 2e (Trabajo en Casa) — evidencia de trazabilidad del uso de IA (Claude Code) en este proyecto.

Registro cronológico de las interacciones relevantes con el asistente de IA durante el desarrollo del ejercicio.
Cada entrada resume (no transcribe completo) el pedido, la respuesta, los archivos afectados, el riesgo y cómo se
verificó — siguiendo la disciplina de `docs/PROMPT_MAESTRO_IA.md`. El detalle línea por línea de cada cambio de
código vive en `docs/ENGINEERING_DECISIONS.md` (decisiones D-01 a D-18); este archivo es el resumen orientado a
"qué se le pidió a la IA y qué hizo", no el razonamiento de ingeniería en sí.

---

## Sesión 2026-08-31

### 1. Análisis de brechas contra el enunciado

**Pedido:** comparar el PDF de instrucciones del ejercicio contra el estado del repositorio (`README.md`,
`apps/web-monolito/`, `data/`, `db/`) y listar qué faltaba por completar.

**Respuesta:** un diagnóstico por Parte del ejercicio (1 a 10 más Trabajo en Casa), marcando qué ya existía en el
código vs. qué faltaba, priorizando qué atacar primero.

**Archivos modificados:** ninguno (solo análisis).

**Riesgo:** ninguno (sin cambios).

**Resultado:** aceptado; se usó como plan de trabajo para el resto de la sesión.

---

### 2. Documentos fundacionales: requisitos y decisiones de arquitectura

**Pedido:** "vamos por partes... empezamos con [los .md]" — crear `docs/REQUIREMENTS.md` y
`docs/ENGINEERING_DECISIONS.md` primero, para que el resto del trabajo tuviera de dónde alimentarse.

**Respuesta:** `REQUIREMENTS.md` con RF-01 a RF-15 y RNF-01 a RNF-08 numerados, cada uno con su estado real
verificado contra el código (no copiado del enunciado); `ENGINEERING_DECISIONS.md` con el esquema pedido
(necesidad → alternativas → decisión → justificación → riesgo → evidencia) para 8 decisiones ya tomadas en el
código (D-01 a D-08), incluyendo dos brechas detectadas al escribir los documentos: RF-04 (catálogo visible sin
sesión) y un posible filtrado de mensajes internos de error.

**Archivos modificados:** `docs/REQUIREMENTS.md`, `docs/ENGINEERING_DECISIONS.md` (creados).

**Riesgo:** ninguno — solo documentación, sin tocar código todavía.

**Resultado:** aceptado; el usuario pidió seguir con seguridad y corregir las brechas encontradas.

---

### 3. Revisión de seguridad y corrección de brechas de código

**Pedido:** seguir con `docs/SECURITY_REVIEW.md` y, de una vez, revisar si era necesario corregir alguna brecha de
código detectada y corregirla si aplicaba.

**Respuesta:** `SECURITY_REVIEW.md` con los 10 controles del punto 17 (amenaza → control → evidencia → estado),
que destapó 8 brechas concretas. Se corrigieron las 4 de menor riesgo/mayor relevancia de inmediato:

1. `requireLogin` agregado a `GET /libros` y `GET /libros/:id` (RF-04).
2. El middleware de error de `app.js` dejó de reenviar `err.message` crudo al usuario.
3. Validación server-side (`validarLibro()`) agregada en `libros.controller.js`.
4. Longitud mínima de contraseña (8 caracteres) en `auth.controller.js`.

**Archivos modificados:** `docs/SECURITY_REVIEW.md` (creado); `app.js`, `libros.routes.js`, `libros.controller.js`,
`auth.controller.js` (código).

**Riesgo:** bajo — cambios pequeños y localizados, cada uno en una sola ruta/función.

**Pruebas ejecutadas:** `node -c` en los 4 archivos modificados; smoke test manual levantando el servidor y
confirmando con `curl` que `GET /libros` sin sesión responde `302 → /login`.

**Resultado:** aprobado. Las 4 brechas restantes (fallback de `SESSION_SECRET`, validación de MIME en imágenes,
privilegio de `library_user`, checklist de secretos antes de publicar) se dejaron pendientes deliberadamente por
depender de infraestructura o de decisiones fuera del alcance de "código" de ese momento.

---

### 4. Vocabulario de estado sin emojis

Ver el ejemplo completo (con el prompt exacto) en `docs/PROMPT_MAESTRO_IA.md`. Resumen: se reemplazaron 6 tipos de
emoji por 3 símbolos de texto plano (`✓`/`~`/`✗`) en los 3 documentos que los usaban, verificado con un script que
confirmó 0 coincidencias restantes.

---

### 5. Reorganización de la base de datos (`db/00`…`06`)

**Pedido:** "lo que creas que es mejor hacer como siguiente paso para mantenerlo ordenado para mejor toma de
decisiones."

**Respuesta:** se decidió (sin pedir confirmación previa, por instrucción explícita de autonomía) reorganizar
`db/` con la nomenclatura exacta del ejercicio (`00_create_database.sql` … `06_views.sql`), consolidando dos
copias divergentes del esquema (`data/db_scheme.sql` y `db/esquema.sql`) en una sola, corrigiendo que
`library_user` fuera `OWNER` de la base (violaba mínimo privilegio), completando el seed a ~30 filas por tabla
con el libro de Cloud Computing y sus 10 conceptos obligatorios (RF-09a), y agregando stored
procedures/triggers/vista. Se conectó la vista a la aplicación (bajo riesgo, una sola consulta de lectura) pero
**no** los stored procedures (alto riesgo sin poder probar contra una base real en ese momento).

**Archivos modificados:** `db/00` a `06` (creados), `data/db_scheme.sql`/`data/seed.sql`/`db/esquema.sql`
(eliminados), `README.md`, `apps/web-monolito/README.md` (simplificado para apuntar al README raíz),
`libros.model.js` (la vista).

**Riesgo:** medio — sin `psql`/Docker disponibles en ese momento, el trabajo de SQL no se pudo ejecutar, solo
revisar por código (balance de comillas, balance de `$$`, revisión manual).

**Resultado:** aceptado, con la limitación explícita documentada de que faltaba verificación en vivo.

---

### 6. Verificación en vivo contra PostgreSQL local (cierra la brecha de la interacción 5)

**Pedido:** "se supone que justo instale psql puedes revisar si ahora si jala" — y, tras compartir la contraseña
local de `postgres` (solo para uso transitorio en esta sesión, nunca escrita a un archivo del repositorio), se
autorizó seguir probando.

**Respuesta:** se cargaron `db/00` a `06` contra la instancia real, lo que encontró y corrigió 3 bugs reales que
la revisión de código no había detectado (ver D-18 en `ENGINEERING_DECISIONS.md`): sintaxis inválida en el seed,
un placeholder de contraseña con un carácter no-ASCII que rompía la autenticación, y el `README.md` diciendo que
los scripts DDL debían cargarse con el rol equivocado. Con la base ya poblada y verificada, se conectaron
finalmente los stored procedures a `libros.model.js` (cerrando la decisión pendiente de la interacción 5) y se
levantó la aplicación completa para ejercitar en vivo: login, catálogo, CRUD con relaciones, las 6 pruebas
negativas de integridad, inyección SQL, autorización por rol, y el trigger de auditoría.

**Archivos modificados:** `db/00_create_database.sql`, `db/02_seed_30_per_table.sql`, `db/04_stored_procedures.sql`
(correcciones); `README.md` (orden de carga corregido); `libros.model.js` (SPs conectados).

**Riesgo:** el más alto de la sesión (se estaba cambiando una ruta que ya funcionaba, `asignarAutores`/
`asignarGeneros`), mitigado por tener por primera vez una base de datos real contra la cual probar antes de dar el
cambio por bueno.

**Pruebas ejecutadas:** ver el detalle completo en `docs/TEST_PLAN.md` — 24 de 36 casos quedaron con evidencia
real de ejecución ese mismo día (antes eran 2).

**Resultado:** aprobado. Pendiente explícito: repetir esta misma carga en la instancia GCP real del usuario (que
sigue con el estado anterior a esta sesión) — el usuario decidió posponer esa parte hasta después de subir el
código a git.

---

### 7. Guía de evidencias y documentación de uso de IA

**Pedido:** crear una guía de qué capturas de pantalla tomar y cómo nombrarlas (para usarla más adelante, no de
inmediato), y continuar con el resto de la documentación pendiente que no dependiera de GCP.

**Respuesta:** `docs/EVIDENCE_GUIDE.md` (checklist de ~35-40 capturas organizadas por carpeta/sección) y esta
misma Tarea 2e (`docs/PROMPT_MAESTRO_IA.md`, este archivo, y `docs/AI_CHANGELOG.md`).

**Archivos modificados:** los tres archivos mencionados (creados).

**Riesgo:** ninguno — documentación pura.

**Resultado:** en curso.
