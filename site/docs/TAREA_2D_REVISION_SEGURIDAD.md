# Tarea 2d — Revisión Final de Seguridad

Ejercicio 02 · Integración de Aplicaciones Computacionales · UDEM
Trabajo en Casa. Tabla resumida para publicar en la página web (sección "Seguridad y roles" del `index.html`).

Esta es la versión condensada, pensada para el sitio público, de la revisión completa en
`docs/SECURITY_REVIEW.md` (10 controles con evidencia detallada). Aquí se listan **10 amenazas** (mínimo pedido:
8), cada una con su mitigación real y el riesgo residual honesto — no se marca nada como "resuelto" si no lo está.

| # | Amenaza / error posible | Mitigación aplicada | Riesgo residual |
|---|--------------------------|----------------------|-------------------|
| 1 | Fuga de contraseñas si se compromete la base de datos | Hash `bcrypt` (10 rounds) sobre toda contraseña; nunca se guarda texto plano | Sin política de complejidad (solo longitud mínima de 8 caracteres) — aceptado como suficiente para el alcance del ejercicio |
| 2 | SQL Injection vía formularios o parámetros de búsqueda | 100% de las consultas parametrizadas con `pg` (`$1, $2...`); verificado en vivo con `'; DROP TABLE libros; --` como texto de búsqueda, sin efecto | Ninguno detectado — el propio driver hace imposible la inyección clásica mientras se use el patrón parametrizado |
| 3 | Acceso no autorizado a funciones administrativas | Middleware `requireAdmin` en toda ruta de escritura y en `/admin/*`; verificado en vivo que un `cliente` real no ve ni un botón de administración en el HTML | Ninguno detectado |
| 4 | Consulta del catálogo por usuarios no autenticados | Middleware `requireLogin` en las rutas de catálogo (`GET /libros`, `GET /libros/:id`) | Ninguno — corregido durante esta misma revisión (era una brecha real detectada al escribir `docs/REQUIREMENTS.md`) |
| 5 | Subida de archivos maliciosos disfrazados de imagen | Whitelist de extensión, límite de 5 MB, nombre de archivo generado por el servidor (nunca el original del usuario) | **Sí existe:** el filtro valida solo la extensión del nombre, no el tipo MIME real ni los *magic bytes* — un ejecutable renombrado a `.png` pasaría el filtro. Mitigación futura: validar la firma binaria del archivo |
| 6 | Secuestro de sesión / sesión que nunca expira | `express-session` con expiración de 4 horas; `logout` destruye la sesión en el servidor, no solo la cookie | La cookie no fuerza `secure: true` explícitamente (depende de que el reverse proxy final use TLS); `SESSION_SECRET` tiene un valor de respaldo en el código si falta la variable de entorno |
| 7 | Mensajes de error que exponen detalle interno de PostgreSQL | Middleware de error centralizado que nunca reenvía `err.message` al usuario; el detalle real solo queda en el log del servidor | Ninguno detectado tras la corrección — antes de esta revisión sí existía la brecha |
| 8 | El proceso de la aplicación con privilegios excesivos en la base de datos | `library_user` (el rol que usa la app) tiene solo `SELECT/INSERT/UPDATE/DELETE` sobre las tablas, sin poder crear/eliminar tablas, roles o bases — verificado que un intento de DDL con ese rol falla | **Sí existe, pero solo en la instancia GCP real todavía no actualizada:** la instancia que ya estaba corriendo antes de esta revisión tiene a `library_user` como dueño completo de la base; falta re-cargar el esquema corregido ahí |
| 9 | Creación de un segundo Administrador (elevación de privilegios) | Índice único parcial en PostgreSQL (`rol = 'administrador'` a lo más una fila); probado con un intento real que falló tanto por `psql` directo como desde la interfaz web, con mensaje traducido | Ninguno detectado |
| 10 | Publicación accidental de secretos (contraseñas, `.env`, claves) | `.env` excluido por `.gitignore`; `.env.example` solo con nombres de variable; ninguna contraseña real quedó escrita en el repositorio durante todo el desarrollo | Pendiente el checklist final antes de comprimir el proyecto para publicarlo (Parte 10 del ejercicio) — todavía no se ha hecho ese empaquetado |

## Cómo se validó cada fila

Las filas 2, 3, 7 y 9 se probaron **en vivo** contra una instancia PostgreSQL local (con la aplicación corriendo
de verdad, no solo revisando código) — el detalle completo, con los mensajes de error reales obtenidos, está en
`docs/TEST_PLAN.md`. Las filas 1, 4, 6 y 10 se verificaron por revisión de código y, en el caso de la fila 4,
también con un smoke test HTTP. Las filas 5 y 8 documentan riesgos residuales genuinos, no resueltos todavía —
mantenerlos visibles aquí es intencional: el ejercicio pide honestidad sobre lo que falta, no una lista de
controles perfectos.
