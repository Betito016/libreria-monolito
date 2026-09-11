# Guía de Evidencias (Capturas de Pantalla)

Ejercicio 02 · Integración de Aplicaciones Computacionales · UDEM

Esta guía dice **qué capturar, cuándo y cómo nombrar cada archivo**, para que cuando llegue el momento de tomar
evidencias (después de subir a git y actualizar la instancia GCP) sea un checklist a seguir, no una decisión
improvisada. No es necesario tomarlas ahora — este documento existe justo para no tener que decidir esto sobre la
marcha más adelante.

## Dónde van los archivos

Según la Parte 10 del ejercicio, el sitio final en `ubiquitous.udem.edu` se organiza así:

```
~/html/ejercicio02/
  index.html
  css/
  img/
  evidencias/       <- todas las capturas de esta guía van aquí
  docs/             <- copia de los .md de este repo (REQUIREMENTS, ENGINEERING_DECISIONS, etc.)
  sql/               <- copia de db/
  descargas/ejercicio02.tar.gz
```

Dentro de `evidencias/`, usa subcarpetas por sección para no terminar con 60 archivos sueltos. La numeración
coincide con las secciones del `index.html` que pide el punto 23 del ejercicio, así cada carpeta se enlaza directo
desde su sección:

```
evidencias/
  04-infraestructura-gcp/
  05-base-datos/
  07-implementacion/
  08-seguridad/
  10-pruebas/
  11-despliegue/
  12-galeria-app/
```

## Convención de nombres

`NN-descripcion-corta.png` dentro de cada carpeta, donde `NN` es un número de dos dígitos que da el orden en el
que quieres que se lean (no tiene que coincidir con el orden en que las tomas). Todo en minúsculas, sin espacios
ni acentos (usa guiones). Ejemplos: `01-gcloud-crear-instancia.png`, `02-firewall-reglas.png`.

Antes de subir cualquier captura, revisa que **no aparezca ninguna contraseña, token, IP interna sensible ni
cadena de conexión completa** — recorta o tapa esos valores. La contraseña de `postgres` que usamos en local, por
ejemplo, nunca debe aparecer en una captura.

---

## 04-infraestructura-gcp/ (Parte 4, puntos 9-10 → alimenta `docs/GCP_COMMANDS.md`)

| Archivo | Qué capturar |
|---|---|
| `01-gcloud-version.png` | Salida de `gcloud --version` confirmando el SDK CLI instalado |
| `02-gcloud-crear-instancia.png` | Terminal con el comando `gcloud compute instances create ...` y su salida completa (IP, zona, estado) |
| `03-firewall-reglas.png` | `gcloud compute firewall-rules list` o la consola web mostrando las reglas creadas |
| `04-instancia-consola.png` | Consola web de GCP mostrando la instancia corriendo (Compute Engine → VM instances) |
| `05-ssh-conexion.png` | Terminal conectado por SSH a la instancia, con `cat /etc/os-release` mostrando CentOS Stream 10 |
| `06-postgres-instalado.png` | `psql --version` y `systemctl status postgresql` corriendo en el servidor GCP |

## 05-base-datos/ (Parte 3 y 4, punto 10 → alimenta `docs/DB_DESIGN_ER_4FN.png` y verificación por `psql`)

Estas son las que ya probamos en local — repítelas en GCP con las mismas sentencias (ya sabemos que deben salir
así porque las corrimos en esta sesión):

| Archivo | Qué capturar |
|---|---|
| `01-carga-00-schema.png` | Salida de cargar `db/00_create_database.sql` y `db/01_schema.sql` (sin errores) |
| `02-carga-seed.png` | Salida de `db/02_seed_30_per_table.sql` (termina en `COMMIT`) |
| `03-conteo-tablas.png` | Resultado de la consulta de conteo por tabla (sección 1 de `db/03_all_quieries_before_stored_procedures.sql`) — deben salir los mismos ~30 por tabla que en local |
| `04-carga-sp-triggers-vistas.png` | Salida de cargar `04_stored_procedures.sql`, `05_triggers.sql`, `06_views.sql` como `postgres` |
| `05-prueba-isbn-duplicado.png` | El error real de PostgreSQL al repetir TC-15 (ISBN duplicado) |
| `06-prueba-stock-negativo.png` | El error real al repetir TC-16 (stock negativo) |
| `07-prueba-precio-negativo.png` | El error real al repetir TC-17 (precio negativo) |
| `08-prueba-fk-inexistente.png` | El error real al repetir TC-18 (FK inexistente) |
| `09-prueba-delete-restrict.png` | El error real al repetir TC-19 (eliminar autor en uso) |
| `10-prueba-segundo-admin.png` | El error real al repetir TC-20 (segundo administrador), tanto por `psql` como el mensaje traducido en la app |
| `11-vista-catalogo.png` | `SELECT * FROM vista_catalogo_libros LIMIT 5;` funcionando como `library_user` |
| `12-stored-procedure.png` | Un `CALL sp_asignar_autores_libro(...)` funcionando (usa `\gset`, no subconsultas — ver la nota en `db/04_stored_procedures.sql`) |
| `13-permiso-denegado-ddl.png` | (Opcional pero recomendada) el error `permiso denegado al esquema public` al intentar cargar `04_stored_procedures.sql` como `library_user` — es la evidencia más directa del control de mínimo privilegio |
| `14-diagrama-er.png` | El diagrama ER completo (puede ser exportado desde pgAdmin, dbdiagram.io, o dibujado a mano/herramienta de diagramas) — este es el que se referencia como `docs/DB_DESIGN_ER_4FN.png` |

## 07-implementacion/ (Parte 5, puntos 11-16 → CRUD, conceptos, imágenes)

| Archivo | Qué capturar |
|---|---|
| `01-catalogo.png` | `/libros` con sesión iniciada, mostrando el grid de libros |
| `02-detalle-libro.png` | `/libros/:id` de cualquier libro, con autores/géneros/imágenes visibles |
| `03-detalle-cloud-computing.png` | `/libros/:id` del libro "Cloud Computing: Fundamentos y Arquitecturas" con los 10 conceptos y definiciones visibles (evidencia directa de RF-09a) |
| `04-formulario-nuevo-libro.png` | El formulario de creación de libro (`/libros/nuevo`) como administrador |
| `05-crud-catalogos.png` | Uno de los catálogos simples (p. ej. `/admin/autores`) mostrando listar/crear/editar |
| `06-subida-imagen.png` | El formulario de subida de imagen y el resultado (imagen ya en la galería del libro) |
| `07-crud-usuarios.png` | `/admin/usuarios` mostrando la lista y el cambio de rol/estado |

## 08-seguridad/ (Parte 6 → alimenta `docs/SECURITY_REVIEW.md`)

| Archivo | Qué capturar |
|---|---|
| `01-password-corta-rechazada.png` | El flash de error al registrarse con contraseña de menos de 8 caracteres |
| `02-acceso-denegado-cliente.png` | Un usuario `cliente` intentando entrar a `/admin/usuarios` y siendo redirigido |
| `03-error-generico.png` | Un mensaje de error genérico (sin stack trace ni SQL) tras forzar algún fallo |
| `04-env-gitignored.png` | `git status` o `.gitignore` mostrando que `.env` nunca se sube al repositorio |
| `05-hash-en-bd.png` | Una fila de `usuarios` en `psql` mostrando `password_hash` como hash `bcrypt`, nunca texto plano |

## 10-pruebas/ (Parte 7 → alimenta `docs/TEST_PLAN.md`)

No repitas una por una todas las de `05-base-datos/` aquí si ya las pusiste ahí — con que `docs/TEST_PLAN.md`
enlace a esas capturas basta. Agrega aquí las que falten de esa matriz y que no sean puramente de base de datos:

| Archivo | Qué capturar |
|---|---|
| `01-login-exitoso.png` | Login correcto, redirección a `/` con flash de bienvenida |
| `02-login-fallido.png` | Login con contraseña incorrecta, flash de error |
| `03-busqueda.png` | `/libros?q=cloud` (o similar) mostrando el filtro funcionando |
| `04-autorizacion-visitante.png` | Un visitante sin sesión intentando `/libros`, redirigido a `/login` |

## 11-despliegue/ (Parte 8 → reverse proxy)

| Archivo | Qué capturar |
|---|---|
| `01-node-localhost.png` | `curl -I http://127.0.0.1:3000/` desde dentro del servidor (Node solo en localhost, no expuesto) |
| `02-nginx-config.png` o `02-apache-config.png` | El archivo de configuración del reverse proxy (`cat` en terminal) |
| `03-acceso-externo.png` | **La más importante de esta carpeta**: un navegador en tu máquina local (no el servidor) abriendo `http://IP_DEL_SERVIDOR/library` y mostrando la app funcionando |
| `04-formulario-bajo-proxy.png` | Un formulario funcionando correctamente bajo el prefijo `/library` (confirma que las rutas relativas no se rompieron) |

## 12-galeria-app/ (Parte 9, punto 12 del `index.html` → "Galería de evidencias con explicación")

Esta carpeta puede reutilizar imágenes de las anteriores — no dupliques archivos, referencia con rutas relativas
desde `index.html` a `evidencias/07-implementacion/01-catalogo.png`, etc. Solo agrega aquí algo que no encaje en
ninguna otra categoría, si aparece.

---

## Cómo se conecta esto con lo que ya existe

- `docs/TEST_PLAN.md` ya tiene, para cada caso `TC-xx`, una columna "Resultado observado / Evidencia" con el
  resultado real que obtuvimos en local — cuando repitas la prueba en GCP y tomes la captura correspondiente,
  agrega ahí mismo el nombre del archivo (p. ej. "ver `evidencias/05-base-datos/05-prueba-isbn-duplicado.png`").
- `docs/SECURITY_REVIEW.md` funciona igual: cada control tiene una columna de evidencia lista para el nombre del
  archivo una vez que exista.
- `docs/GCP_COMMANDS.md` (pendiente de crear cuando trabajemos la Parte 4) va a pedir las capturas de
  `04-infraestructura-gcp/` como parte de su propio contenido.
- El `index.html` final (Parte 10) enlaza directamente a estas carpetas para la sección 12 ("Galería de
  evidencias/screenshots con explicación") — cada imagen debe ir acompañada de 1-2 líneas explicando qué muestra,
  no solo la imagen sola (el ejercicio es explícito: "una captura sin explicación no constituye por sí sola una
  prueba").

## Total estimado

~35-40 capturas repartidas en las 6 carpetas. No es necesario tomarlas todas de una sesión — puedes ir tachando la
lista conforme avances por cada Parte del ejercicio.
