# Changelog de Cambios Asistidos por IA

Ejercicio 02 · Integración de Aplicaciones Computacionales · UDEM
Tarea 2e (Trabajo en Casa).

Lista cronológica, estilo changelog, de los cambios concretos hechos con asistencia de IA (Claude Code) sobre este
repositorio. Para el contexto de *por qué* de cada cambio, ver `docs/AI_PROMPT_HISTORY.md` (el pedido y la
respuesta) y `docs/ENGINEERING_DECISIONS.md` (el razonamiento de ingeniería). Este archivo responde solo *qué*
cambió y *cuándo*.

## 2026-08-31

### Documentación fundacional
- Creado `docs/REQUIREMENTS.md` — RF-01 a RF-15, RNF-01 a RNF-08, actores, riesgos.
- Creado `docs/ENGINEERING_DECISIONS.md` — decisiones D-01 a D-08 (arquitectura monolítica, acceso directo a
  PostgreSQL, EJS, organización por módulos, autenticación por sesión, regla de un solo administrador, carga de
  imágenes, manejo centralizado de errores).
- Creado `docs/SECURITY_REVIEW.md` — 10 controles de seguridad con estado real.

### Corrección de brechas de código (primera ronda)
- `apps/web-monolito/src/modules/libros/libros.routes.js` — agregado `requireLogin` a `GET /` y `GET /:id`
  (RF-04: el catálogo dejó de ser visible sin sesión).
- `apps/web-monolito/src/app.js` — el middleware de error final dejó de reenviar `err.message` al usuario.
- `apps/web-monolito/src/modules/libros/libros.controller.js` — agregada `validarLibro()` (ISBN/título/formato
  obligatorios; precio y stock numéricos ≥ 0; año entero positivo) antes de `crear`/`actualizar`.
- `apps/web-monolito/src/modules/auth/auth.controller.js` — longitud mínima de contraseña (8 caracteres) en
  registro.

### Limpieza de formato
- `docs/REQUIREMENTS.md`, `docs/SECURITY_REVIEW.md`, `docs/TEST_PLAN.md` — reemplazados 6 tipos de emoji por el
  vocabulario `✓`/`~`/`✗`.

### Reorganización de la capa de base de datos
- Creados `db/00_create_database.sql`, `db/01_schema.sql` (consolida `data/db_scheme.sql` + `db/esquema.sql`),
  `db/02_seed_30_per_table.sql` (incluye el libro "Cloud Computing: Fundamentos y Arquitecturas" con sus 10
  conceptos obligatorios), `db/03_all_quieries_before_stored_procedures.sql`, `db/04_stored_procedures.sql`
  (`sp_asignar_autores_libro`, `sp_asignar_generos_libro`), `db/05_triggers.sql`, `db/06_views.sql`
  (`vista_catalogo_libros`).
- Eliminados `data/db_scheme.sql`, `data/seed.sql`, `db/esquema.sql` (duplicados consolidados).
- `README.md` — estructura y pasos de instalación actualizados a la nueva nomenclatura `db/00`…`06`.
- `apps/web-monolito/README.md` — simplificado a notas de diseño + enlace al README raíz (evita mantener dos
  copias de las instrucciones de despliegue).
- `apps/web-monolito/src/modules/libros/libros.model.js` — `listar()` usa `vista_catalogo_libros` en vez del
  `JOIN`/`GROUP BY` inline.

### Verificación en vivo contra PostgreSQL 18 local (tras instalar `psql`)
- Corregido `db/02_seed_30_per_table.sql` — sintaxis inválida en 4 `INSERT` de una sola columna (faltaban
  paréntesis por fila).
- Corregido `db/00_create_database.sql` — placeholder de contraseña sin caracteres no-ASCII (evita un error de
  codificación UTF-8 al autenticarse).
- Corregido `db/04_stored_procedures.sql` — el comentario de verificación manual usaba subconsultas directamente
  en `CALL` (inválido en PostgreSQL); corregido con la técnica `\gset` de `psql`.
- Corregido `README.md` — `04_stored_procedures.sql`, `05_triggers.sql`, `06_views.sql` deben cargarse como
  `postgres` (DDL), no como `library_user` (confirmado con el error real `permiso denegado al esquema public`).
- `apps/web-monolito/src/modules/libros/libros.model.js` — `asignarAutores`/`asignarGeneros` reemplazados por
  `CALL sp_asignar_autores_libro(...)`/`sp_asignar_generos_libro(...)`, eliminando la transacción manual
  `BEGIN/DELETE/INSERT×N/COMMIT` en JavaScript.
- `docs/REQUIREMENTS.md`, `docs/ENGINEERING_DECISIONS.md` (nueva decisión D-18), `docs/SECURITY_REVIEW.md`,
  `docs/TEST_PLAN.md` — actualizados con evidencia real de ejecución (24 de 36 casos de prueba pasaron de
  "revisado por código" a "ejecutado y verificado").

### Documentación adicional
- Creado `docs/EVIDENCE_GUIDE.md` — checklist de capturas de pantalla por carpeta/sección para cuando se despliegue
  en la instancia GCP real.
- Creados `docs/PROMPT_MAESTRO_IA.md`, `docs/AI_PROMPT_HISTORY.md`, este archivo (`docs/AI_CHANGELOG.md`) — Tarea
  2e.

### Diagramas, normalización y Trabajo en Casa (misma sesión, continuación)
- Creados `docs/ARCHITECTURE_MONOLITHIC.svg` y `docs/DB_DESIGN_ER_4FN.svg` — diagramas hechos a mano en SVG (sin
  herramienta de rasterizado a `.png` disponible; queda anotado en el propio chat que es un paso pendiente de un
  clic si se necesita literalmente `.png`). Revisados renderizados en el navegador antes de darlos por buenos.
- Creado `docs/NORMALIZATION_4FN.xlsx` (8 hojas: Portada, 0-No Normalizado, 1FN, 2FN, 3FN-BCNF, 4FN, Dependencias
  FD-MVD, Esquema Final) con `openpyxl` — sin fórmulas (documento de análisis, no un modelo financiero).
- Creado `docs/TAREA_2C_EVALUACION_ARQUITECTONICA.md` (~650 palabras, monolito vs. desacoplado vs. microservicios).
- Creado `docs/TAREA_2D_REVISION_SEGURIDAD.md` (tabla resumida de 10 amenazas para publicación web).
- Creado `docs/REPORTE_TECNICO.md` (Parte 9, punto 21) — sintetiza y enlaza los 12 puntos exigidos, sin duplicar
  el contenido detallado de los demás documentos.

---

## Pendiente de registrar en próximas sesiones

- Repetir la carga de `db/00`…`06` en la instancia GCP real (hoy solo verificada en local).
- `docs/GCP_COMMANDS.md` — comandos reales de creación de la instancia (Parte 4).
- Configuración del reverse proxy Apache/NGINX (Parte 8).
- Diagramas (`docs/ARCHITECTURE_MONOLITHIC.png`, `docs/DB_DESIGN_ER_4FN.png`) y `docs/NORMALIZATION_4FN.xlsx`.
- Reporte técnico y sitio web final (`index.html`) para publicar en `ubiquitous.udem.edu` (Parte 9 y 10).
- Tareas de Trabajo en Casa 2a (normalización), 2c (evaluación arquitectónica), 2d (tabla resumida de seguridad).
