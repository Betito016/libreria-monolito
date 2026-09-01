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

## 2026-09-01

### Despliegue real en la instancia GCP (`integracion`, proyecto `integracion-505802`)
- Revisado el estado real de la instancia (`gcloud compute instances describe`, firewall) antes de tocar nada;
  confirmado con el usuario antes de arrancarla (genera costo) y antes de borrar la base de datos vieja.
- Encontradas y corregidas 2 reglas de firewall duplicadas abriendo el puerto 3000 a Internet, más una regla RDP
  sin uso — eliminadas después de verificar el reverse proxy funcionando.
- `library_db`/`library_user` (con `OWNER` incorrecto, de una carga anterior) eliminados y recreados desde cero
  con `db/00`…`06`, en el mismo orden y con los mismos roles ya verificados en local. Confirmado en la instancia
  real que `library_user` no puede hacer DDL.
- Corregido `apps/web-monolito/src/server.js` — `HOST` por defecto era `'0.0.0.0'` (exponía Node a toda la red);
  cambiado a `'127.0.0.1'`. Brecha real encontrada solo al desplegar, no visible en local (commit `adf4456`).
- Actualizado `bcrypt` a `6.0.0` para resolver 3 vulnerabilidades de `npm audit` (2 altas, 1 crítica) en la cadena
  `bcrypt → @mapbox/node-pre-gyp → tar`; verificado que `hash()`/`compare()` no cambiaron de comportamiento
  (commit `24199b9`).
- Configurado `web-monolito.service` (systemd) y `/etc/nginx/conf.d/libreria.conf` (NGINX) publicando `/library`
  con `proxy_redirect` + `sub_filter` — sin modificar ningún controlador ni vista EJS. Verificado end-to-end desde
  un cliente externo real (login, sesión, catálogo).
- Creados `docs/GCP_COMMANDS.md`, `docs/nginx-libreria.conf`, `docs/web-monolito.service`; actualizados
  `docs/SECURITY_REVIEW.md` (controles 9-11), `docs/TEST_PLAN.md` (TC-29, TC-32), `docs/REQUIREMENTS.md` (RNF-08)
  y `docs/REPORTE_TECNICO.md` (secciones 10-11) con la evidencia real obtenida.

---

## Pendiente de registrar en próximas sesiones

- Configurar una *deploy key* de GitHub en la instancia para que `git pull` funcione ahí directamente (hoy se
  sincronizó el código por `scp`).
- Repetir en la instancia GCP las 6 pruebas negativas de integridad y la verificación del libro de Cloud
  Computing (hoy con evidencia solo de la instancia local).
- Capturar las evidencias visuales siguiendo `docs/EVIDENCE_GUIDE.md`.
- Sitio web final (`index.html`) para publicar en `ubiquitous.udem.edu` (Parte 10).
- Tarea de Trabajo en Casa 2b ya cubierta por `docs/TEST_PLAN.md`; 2a, 2c y 2d ya completas.
