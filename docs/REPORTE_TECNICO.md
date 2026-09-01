# Reporte Técnico — Librería en Línea

Ejercicio 02 · Integración de Aplicaciones Computacionales · UDEM
Parte 9, punto 21. Este reporte sintetiza y conecta el trabajo hecho a lo largo del ejercicio; no repite el
detalle completo de cada documento, sino que lo referencia — la evidencia exhaustiva vive en los archivos
citados en cada sección.

---

## 1. Descripción del problema y alcance

Se construyó una aplicación web monolítica para administrar el catálogo de una librería en línea: gestión de
libros con múltiples autores y géneros, conceptos técnicos definidos por libro (con definición propia por par
libro-concepto), imágenes con portada, control de stock/precio, y un único usuario Administrador. El sistema
completo — interfaz, lógica de negocio y acceso a datos — vive en un solo proceso Node.js/Express, renderizando
HTML del lado del servidor con EJS y accediendo a PostgreSQL directamente vía `pg` (sin ORM, sin API intermedia).
Fuera de alcance: pagos, envíos, facturación, roles adicionales a `cliente`/`administrador`, multi-idioma.

## 2. Requisitos funcionales y no funcionales

Documentados de forma exhaustiva en [`docs/REQUIREMENTS.md`](REQUIREMENTS.md): 15 requisitos funcionales
(RF-01 a RF-15, más RF-09a para el caso obligatorio de Cloud Computing) y 8 no funcionales (RNF-01 a RNF-08),
cada uno con su estado real verificado contra el código — no una lista aspiracional copiada del enunciado. Al
cierre de esta sesión, 6 de los 15 RF y todos los RNF salvo el de despliegue tienen evidencia de ejecución real
(no solo revisión de código), documentada en [`docs/TEST_PLAN.md`](TEST_PLAN.md).

## 3. Macro-arquitectura y patrón de presentación seleccionado

**Macro-arquitectura:** monolito server-side. El diagrama completo (navegador → Apache/NGINX → Express →
7 capas internas → PostgreSQL / almacenamiento de imágenes) está en
[`docs/ARCHITECTURE_MONOLITHIC.svg`](ARCHITECTURE_MONOLITHIC.svg). La justificación completa de esta decisión,
con alternativas consideradas y riesgos aceptados, está en la decisión **D-01** de
[`docs/ENGINEERING_DECISIONS.md`](ENGINEERING_DECISIONS.md); el análisis comparativo pedido por la Tarea 2c
(monolito vs. desacoplado vs. microservicios, considerando complejidad operativa, despliegue, escalabilidad,
mantenimiento, seguridad y tamaño de equipo) está completo en
[`docs/TAREA_2C_EVALUACION_ARQUITECTONICA.md`](TAREA_2C_EVALUACION_ARQUITECTONICA.md).

**Patrón de presentación:** MVC con organización por módulos (`routes/controller/model/views` por entidad de
negocio), más una fábrica compartida (`catalogo.factory.js`) para los cuatro catálogos estructuralmente idénticos
(autores, géneros, formatos, conceptos) — decisiones **D-03** y **D-04**. Renderizado 100% server-side con EJS,
sin JSON/XML entre frontend y backend — formularios HTML clásicos con el patrón Post/Redirect/Get.

## 4. Organización del código y responsabilidades de los módulos

```
apps/web-monolito/src/
  app.js            inicialización de Express, middleware, montaje de rutas
  config/db.js      pool de conexión a PostgreSQL (config centralizada)
  middlewares/      auth.js (requireLogin/requireAdmin), upload.js (multer)
  modules/          un directorio por entidad: auth, usuarios, libros, autores,
                    generos, formatos, conceptos (los últimos 4 vía catalogo.factory.js)
  views/            partials compartidos (header, footer, alerts)
  public/           CSS y estáticos servidos por Express
```

Cada módulo separa `*.model.js` (SQL parametrizado), `*.controller.js` (orquesta petición/respuesta) y
`*.routes.js` (mapeo URL→controlador); las vistas EJS no contienen SQL ni lógica de negocio compleja — decisión
**D-04**.

## 5. Modelo de datos y normalización hasta 4FN

10 tablas: `usuarios`, `formatos`, `generos`, `autores`, `conceptos`, `libros`, y las tablas puente `libro_autor`,
`libro_genero`, `libro_concepto` (esta última con el atributo propio `definicion`, evidencia central de la 4FN
del modelo) más `imagenes` (1:N directa). El proceso completo de normalización —desde una relación no
normalizada hasta 4FN, con cada dependencia funcional y multivaluada identificada— está en
[`docs/NORMALIZATION_4FN.xlsx`](NORMALIZATION_4FN.xlsx) (8 hojas: Portada, 0-No Normalizado, 1FN, 2FN, 3FN-BCNF,
4FN, Dependencias FD-MVD, Esquema Final). El diagrama ER final está en
[`docs/DB_DESIGN_ER_4FN.svg`](DB_DESIGN_ER_4FN.svg). El esquema ejecutable vive en
[`db/01_schema.sql`](../db/01_schema.sql).

## 6. Decisiones sobre integridad y restricciones de PostgreSQL

Cada tabla tiene sus `PK`/`FK`/`UNIQUE`/`CHECK` justificados en `db/01_schema.sql` (comentarios inline) y en la
decisión **D-06** de `ENGINEERING_DECISIONS.md` para la regla más particular del sistema: **a lo más un
Administrador**, resuelta con un índice único parcial (`ux_un_solo_administrador`) en vez de validarlo solo en la
aplicación — evita condiciones de carrera. Las 6 pruebas negativas de integridad exigidas por el ejercicio (ISBN
duplicado, stock negativo, precio inválido, FK inexistente, `DELETE` restringido por relación en uso, segundo
administrador) se ejecutaron contra una instancia PostgreSQL 18 real, con el error exacto de cada una documentado
en `docs/TEST_PLAN.md`, sección 4. El esquema incluye además 2 stored procedures (`sp_asignar_autores_libro`,
`sp_asignar_generos_libro` — `db/04_stored_procedures.sql`), 2 triggers de auditoría (`actualizado_en` —
`db/05_triggers.sql`) y una vista (`vista_catalogo_libros` — `db/06_views.sql`), todos verificados en vivo
(decisión **D-18**).

## 7. Funcionalidades implementadas y flujo navegador → aplicación → base de datos

CRUD completo sobre las 6 tablas administrables (usuarios, libros, autores, géneros, formatos, conceptos); las
relaciones M:N (`libro_autor`, `libro_genero`) se gestionan desde el formulario del libro, y la relación con
atributo (`libro_concepto`) tiene su propia interfaz de alta/baja en la ficha del libro. El flujo es siempre:
`Navegador → formulario HTML (POST) → ruta Express → middleware (auth) → controlador → validación server-side →
modelo (SQL parametrizado o CALL a stored procedure) → PostgreSQL → redirección (PRG) → vista EJS renderizada`.
El caso obligatorio del libro de Cloud Computing con sus 10 conceptos (IaaS, PaaS, SaaS, FaaS, Bucket, Public/
Private/Hybrid Cloud, Multicloud, Serverless) está sembrado en `db/02_seed_30_per_table.sql` y se verificó
renderizado en la ficha real del libro (`docs/TEST_PLAN.md`, TC-27).

## 8. Seguridad: autenticación, autorización, sesiones, validación, secretos, SQL parametrizado y uploads

Cubierto en detalle en [`docs/SECURITY_REVIEW.md`](SECURITY_REVIEW.md) (10 controles, amenaza → control →
evidencia → estado) y su versión resumida para publicación en
[`docs/TAREA_2D_REVISION_SEGURIDAD.md`](TAREA_2D_REVISION_SEGURIDAD.md) (10 amenazas). Resumen: contraseñas con
`bcrypt` y longitud mínima; sesiones de servidor con expiración; autorización por rol (`requireLogin`/
`requireAdmin`) verificada en vivo, incluyendo que el HTML que recibe un `cliente` no contiene ningún control de
administración; 100% de las consultas parametrizadas (probado con inyección SQL real, sin efecto); validación
server-side de todos los campos de `libros`; manejo de errores que nunca expone detalle interno de PostgreSQL al
usuario; y el rol de base de datos de la aplicación (`library_user`) restringido a privilegios mínimos (sin DDL).
Dos riesgos residuales quedan documentados sin resolver, explícitamente: validación de imágenes solo por
extensión (no por tipo MIME real), y la instancia GCP real todavía no actualizada con el modelo de privilegio
mínimo.

## 9. Estrategia de pruebas y resultados

Matriz completa en [`docs/TEST_PLAN.md`](TEST_PLAN.md): 36 casos en 10 categorías (mínimo pedido: 15), de los
cuales 24 tienen evidencia de ejecución real contra PostgreSQL 18 local y la aplicación corriendo — no solo
revisión de código. Incluye pruebas funcionales, de autorización por los tres roles, negativas de integridad (con
el mensaje de error real de PostgreSQL en cada una), de validación de campos, de las relaciones M:N y M:N con
atributo, de inyección SQL, y de los artefactos de base de datos nuevos (vista, stored procedures, trigger).

## 10. Despliegue mediante Apache/NGINX

**Pendiente de ejecución** — documentado como plan en `README.md` (sección de reverse proxy con NGINX) pero no
verificado contra un reverse proxy real todavía. La aplicación ya está preparada para ello: escucha en un puerto
configurable vía `.env` (pensado para bindear solo a `127.0.0.1`), y el `README.md` incluye la configuración de
NGINX de referencia. Falta: montar el proxy en la instancia GCP real, verificar rutas estáticas/formularios/
sesiones/uploads bajo el prefijo `/library`, y capturar la evidencia correspondiente (ver
`docs/EVIDENCE_GUIDE.md`, carpeta `11-despliegue/`).

## 11. Limitaciones actuales, riesgos técnicos y posibles mejoras

- La instancia GCP real del usuario predata esta sesión de trabajo y todavía no tiene el esquema/privilegios
  corregidos — es el bloqueante principal para dar por cerradas las Partes 4, 7 (evidencia en el entorno real) y 8.
- Validación de imágenes solo por extensión, no por firma binaria (riesgo de seguridad residual documentado).
- `SESSION_SECRET` tiene un valor de respaldo hardcodeado si falta la variable de entorno — aceptable en
  desarrollo, a revisar antes de producción.
- La sesión vive en memoria del proceso (`express-session` sin store externo) — no escala a múltiples instancias
  sin un store compartido (Redis/Postgres); aceptado por ser un solo proceso en el alcance del ejercicio.
- Mejoras futuras razonables: paginación del catálogo si crece más allá de unas pocas decenas de libros, búsqueda
  con índice `GIN`/`trigram` si el volumen lo justifica, y conectar los stored procedures de `libro_autor`/
  `libro_genero` a más operaciones si se identifican otras transacciones multi-paso.

## 12. Análisis de qué tendría que cambiar si el sistema evolucionara hacia componentes desacoplados

Ver el análisis completo en `docs/TAREA_2C_EVALUACION_ARQUITECTONICA.md`. En resumen: habría que introducir un
formato de intercambio (JSON) y una API versionada, duplicar la validación entre cliente y servidor, resolver
autenticación stateless (tokens) en vez de sesión de servidor, y decidir dónde vive cada responsabilidad que hoy
comparte un solo proceso — middleware de autorización, lógica de negocio y acceso a datos tendrían que exponerse
de forma consistente a un frontend separado. El modelo de datos (10 tablas ya en 4FN) no cambiaría; lo que
cambiaría es exclusivamente la capa de presentación y el contrato entre capas.
