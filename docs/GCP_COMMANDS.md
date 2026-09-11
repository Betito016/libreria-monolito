# Comandos de Infraestructura GCP

Ejercicio 02 · Integración de Aplicaciones Computacionales · UDEM
Parte 4, puntos 9-10 y Parte 8. Todos los comandos aquí se ejecutaron realmente el 2026-09-01 contra la
instancia del usuario (no son un plan hipotético) — ver evidencia en `docs/TEST_PLAN.md` y
`docs/SECURITY_REVIEW.md`.

## 1. Instancia

La instancia ya existía de una configuración previa a esta sesión de trabajo; se documenta aquí tal como está,
no se creó desde cero.

| Campo | Valor |
|---|---|
| Nombre | `integracion` |
| Proyecto | `integracion-505802` |
| Zona | `us-central1-c` |
| Tipo de máquina | `e2-standard-2` (2 vCPU, 8 GB RAM) |
| Imagen | `centos-stream-10` (proyecto `centos-cloud`) |
| Disco | 20 GB |
| Red | `default`, IP externa efímera (PREMIUM tier) |

Comandos usados para inspeccionarla y arrancarla (no crearla — ya existía):

```bash
gcloud config set project integracion-505802
gcloud compute instances list
gcloud compute instances describe integracion --zone=us-central1-c \
  --format="yaml(name,zone,machineType,status,disks[].diskSizeGb,disks[].licenses,networkInterfaces)"
gcloud compute instances start integracion --zone=us-central1-c
```

Justificación del tamaño (`e2-standard-2`): más grande de lo estrictamente necesario para este ejercicio (un
`e2-small` o `e2-medium` habría bastado para Node + PostgreSQL + NGINX con esta carga), pero ya estaba
aprovisionado así desde antes de esta sesión — no se cambió para no perder el disco/configuración existente sin
necesidad.

## 2. Firewall — estado inicial, hallazgos y limpieza

**Estado encontrado al revisar** (antes de tocar nada):

| Regla | Rango | Puerto | Problema |
|---|---|---|---|
| `default-allow-ssh` | `0.0.0.0/0` | 22 | Correcta, necesaria |
| `default-allow-http` | `0.0.0.0/0` | 80 | Correcta, necesaria |
| `default-allow-icmp` | `0.0.0.0/0` | icmp | Correcta |
| `default-allow-internal` | `10.128.0.0/9` | todos | Correcta (red interna) |
| `default-allow-rdp` | `0.0.0.0/0` | 3389 | **Innecesaria** — nada escucha RDP en un Linux/CentOS |
| `allow-node-3000` | `0.0.0.0/0` | 3000 | **Contradice la Parte 8, punto 19**: Node no debe exponerse directo a Internet |
| `permitir-tcp-3000` | `0.0.0.0/0` | 3000 | Duplicada de la anterior |

Ver `docs/SECURITY_REVIEW.md`, controles 10-11, para el análisis completo de por qué esto era una brecha real (no
solo una regla de más) y cómo se combinó con un bug de código (`HOST` por defecto `0.0.0.0` en `server.js`).

**Comandos de limpieza ejecutados** (una vez que el reverse proxy en el puerto 80 quedó verificado funcionando —
ver sección 5):

```bash
gcloud compute firewall-rules delete allow-node-3000 permitir-tcp-3000 default-allow-rdp --quiet
gcloud compute firewall-rules list
```

**Estado final:** solo `default-allow-ssh` (22), `default-allow-http` (80), `default-allow-icmp` e
`default-allow-internal`. El puerto 3000 nunca queda expuesto a Internet — ni por firewall ni porque `server.js`
ahora escucha en `127.0.0.1` por defecto (defensa en profundidad: dos capas independientes, no solo una).

## 3. PostgreSQL — reconstrucción con privilegio mínimo

**Hallazgo antes de empezar:** `library_db` ya existía de una carga anterior, con `library_user` como `OWNER`
completo de la base (la misma brecha documentada en `docs/SECURITY_REVIEW.md`, control 9, antes de corregirla).
Contenía solo datos de seed antiguos (15 usuarios, 16 libros de prueba) — nada del usuario. Se decidió borrar y
recrear limpio en vez de intentar corregir privilegios sobre una base ya existente.

```bash
# Conectado por SSH a la instancia:
sudo -u postgres psql -c 'DROP DATABASE IF EXISTS library_db;'
sudo -u postgres psql -c 'DROP ROLE IF EXISTS library_user;'
```

**Nota sobre autenticación local:** `pg_hba.conf` tenía `local all all md5`, y la contraseña del rol `postgres`
para ese método no se conocía (no documentada de la configuración previa). Se resolvió de la forma estándar:
cambiar temporalmente esa línea a `peer` (el usuario del sistema `postgres` entra sin contraseña), resetear la
contraseña del rol `postgres` a una nueva (`ALTER ROLE postgres WITH PASSWORD ...`, valor no repetido aquí — se
compartió una sola vez con el usuario en el chat de esta sesión, nunca escrito a un archivo del repositorio), y
revertir `pg_hba.conf` a `md5` al terminar. Backup guardado automáticamente como
`/var/lib/pgsql/data/pg_hba.conf.bak-<timestamp>`.

**Carga del esquema, en el orden y con los roles correctos** (ver también `README.md`):

```bash
# Como root/superusuario del SO, conectando a psql con el rol "postgres" (DDL):
sudo -u postgres psql -f db/00_create_database.sql
sudo -u postgres psql -d library_db -f db/01_schema.sql

# Como library_user (solo DML, ya tiene los privilegios otorgados por 01_schema.sql):
PGPASSWORD='<password-de-library_user>' psql -U library_user -h localhost -d library_db -f db/02_seed_30_per_table.sql
PGPASSWORD='<password-de-library_user>' psql -U library_user -h localhost -d library_db -f db/03_all_quieries_before_stored_procedures.sql

# De nuevo como "postgres" (DDL: procedimientos, triggers, vista):
sudo -u postgres psql -d library_db -f db/04_stored_procedures.sql
sudo -u postgres psql -d library_db -f db/05_triggers.sql
sudo -u postgres psql -d library_db -f db/06_views.sql
```

**Verificación de privilegio mínimo, en la instancia real:**

```
$ PGPASSWORD=*** psql -U library_user -h localhost -d library_db -c "CREATE TABLE prueba_ddl (id INT);"
ERROR:  permission denied for schema public
```

Confirma que `library_user` puede leer/escribir filas (probado con `SELECT` sobre `vista_catalogo_libros`, que
funcionó) pero no puede crear objetos — el mismo resultado que se había verificado antes en local (ver D-18 en
`docs/ENGINEERING_DECISIONS.md`).

**Conteo final de filas** (coincide exactamente con lo verificado en local):

```
usuarios: 30 | formatos: 30 | libros: 32 | libro_concepto: 45
```

## 4. Aplicación Node.js

**Sincronización del código:** el repositorio en el servidor (`/opt/udem/integracion02/libreria-monolito`) no
tenía configurada una llave SSH ni credenciales para `git pull` desde GitHub (el repo es privado). En vez de
bloquear el trabajo configurando esto primero, se copiaron los archivos actualizados directamente por
`gcloud compute scp`. **Pendiente para una próxima sesión:** generar una llave de despliegue (`ssh-keygen`) como
el usuario `alejandro_vs0506` y agregarla como *Deploy Key* (solo lectura) en la configuración del repositorio en
GitHub, para que `git pull` funcione ahí directamente.

**Bug real encontrado al desplegar** (no visible solo revisando el código en local): `src/server.js` tenía
`HOST = process.env.HOST || '0.0.0.0'` — sin la variable de entorno `HOST` definida explícitamente, Node
escuchaba en todas las interfaces de red, exponiéndose directo a Internet en combinación con el firewall abierto
de la sección 2. Corregido a `'127.0.0.1'` por defecto (commit `adf4456`) — ver control 10 en
`docs/SECURITY_REVIEW.md`.

**`npm audit` reportó 3 vulnerabilidades (2 altas, 1 crítica)** en la cadena `bcrypt → @mapbox/node-pre-gyp → tar`
(usada solo durante la instalación del binario nativo, no en tiempo de ejecución). Se actualizó `bcrypt` a la
versión 6.0.0 (commit `24199b9`), verificado que `hash()`/`compare()` siguen produciendo/aceptando el mismo
formato `$2b$` — compatible con los hashes ya sembrados. `npm audit` ahora reporta 0 vulnerabilidades, tanto en
local como en la instancia GCP.

```bash
cd apps/web-monolito
npm install
npm audit          # 0 vulnerabilidades tras actualizar bcrypt

# .env real de la instancia (PGPASSWORD y SESSION_SECRET no se repiten aquí):
cat .env
# PORT=3000
# HOST=127.0.0.1
# SESSION_SECRET=<generado con `openssl rand -hex 32`>
# PGHOST=localhost
# PGPORT=5432
# PGDATABASE=library_db
# PGUSER=library_user
# PGPASSWORD=<el mismo definido en db/00_create_database.sql>
```

**Servicio systemd** (`/etc/systemd/system/web-monolito.service`, mismo contenido documentado en `README.md`):

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now web-monolito
sudo systemctl status web-monolito
```

Verificado: `Active: active (running)`, reinicia solo si el proceso falla (`Restart=on-failure`).

## 5. Reverse proxy NGINX bajo `/library`

**Instalación:**

```bash
sudo dnf install -y nginx
```

**Problema de diseño a resolver:** la aplicación genera todos sus enlaces, formularios y redirecciones como rutas
absolutas desde la raíz (`href="/libros"`, `action="/logout"`, `res.redirect('/')`), sin conocer ningún prefijo.
Montarla bajo `/library` con un `proxy_pass` simple habría dejado esos enlaces rotos (apuntando a `/libros` en vez
de `/library/libros`). En vez de modificar cada controlador y cada vista EJS (~30-40 lugares, alto riesgo de
regresión sin poder probar cada uno), se resolvió enteramente en NGINX con dos directivas estándar para este
problema:

- `proxy_redirect / /library/;` — reescribe la cabecera `Location` de las redirecciones (patrón Post/Redirect/Get).
- `sub_filter 'href="/' 'href="/library/'; sub_filter 'action="/' 'action="/library/'; sub_filter 'src="/' 'src="/library/';`
  — reescribe el cuerpo HTML de la respuesta al vuelo.

Configuración completa: `/etc/nginx/conf.d/libreria.conf` en el servidor, copia idéntica versionada en
[`docs/nginx-libreria.conf`](nginx-libreria.conf). El `server {}` por defecto de `/etc/nginx/nginx.conf` (servía
`/usr/share/nginx/html` en el puerto 80) se comentó para que no compitiera con la configuración nueva.

```bash
sudo setsebool -P httpd_can_network_connect 1   # SELinux: permitir que nginx haga proxy a la red
sudo systemctl enable --now nginx
sudo nginx -t   # valida la sintaxis antes de recargar
```

**Verificación completa, desde un cliente externo real** (no desde dentro del servidor):

```
$ curl http://34.67.65.195/                    -> 302 a /library/
$ curl http://34.67.65.195/library/            -> 200, HTML con enlaces ya prefijados
$ curl http://34.67.65.195/library/login       -> 200, <form action="/library/login">
$ POST http://34.67.65.195/library/login (login real) -> 302 a /library/, cookie de sesión válida
$ GET  http://34.67.65.195/library/libros (con sesión) -> 200, 32 libros, enlaces correctos
$ curl http://34.67.65.195:3000/               -> sin respuesta (puerto ya no expuesto)
```

Todo funcionó en el primer intento tras la configuración — sin necesidad de tocar el código de la aplicación.

## 6. Pendiente para la próxima sesión

- Configurar la *deploy key* de GitHub para que `git pull` funcione directamente en el servidor (ver sección 4).
- Capturar las evidencias/screenshots de todo lo anterior siguiendo `docs/EVIDENCE_GUIDE.md` (los comandos ya
  están verificados y funcionando; falta la evidencia visual para el sitio final).
- Evaluar si agregar HTTPS (certificado, puerto 443) — no lo exige el ejercicio explícitamente, pero mejoraría el
  control 6 de `docs/SECURITY_REVIEW.md` (cookie `secure`).
