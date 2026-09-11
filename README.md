# web-monolito — Librería en Línea

Aplicación web **monolítica** en Node.js + Express + EJS (renderizado 100%
del lado del servidor) con acceso directo a PostgreSQL (sin ORM). Sigue el
patrón **MVC** y una **organización de código por módulos** (uno por
entidad de negocio: `libros`, `autores`, `generos`, `formatos`,
`conceptos`, `usuarios`, `auth`).

**Restricción arquitectónica respetada:** no existen rutas de API REST,
GraphQL ni SOAP. No se produce ni consume JSON/XML como formato de
intercambio — todas las interacciones son formularios HTML clásicos
(`application/x-www-form-urlencoded` o `multipart/form-data` para
imágenes) con redirecciones POST→GET (patrón *Post/Redirect/Get*). El
archivo `package.json` existe únicamente porque `npm` lo requiere para
administrar las dependencias del proyecto.

## Estructura del repositorio esperada

```
proyecto/
├── db/
│   ├── 00_create_database.sql              <- rol + base de datos (mínimo privilegio)
│   ├── 01_schema.sql                       <- tablas, PK/FK/CHECK, privilegios de library_user
│   ├── 02_seed_30_per_table.sql            <- datos sintéticos (~30 filas por tabla)
│   ├── 03_all_quieries_before_stored_procedures.sql  <- consultas de verificación
│   ├── 04_stored_procedures.sql            <- sp_asignar_autores_libro / sp_asignar_generos_libro
│   ├── 05_triggers.sql                     <- triggers de actualizado_en
│   └── 06_views.sql                        <- vista_catalogo_libros
├── docs/                                   <- documentación de ingeniería del ejercicio
└── apps/
    └── web-monolito/        <- esta aplicación
        ├── package.json
        ├── .env.example
        └── src/...
```

Ajusta las rutas de este documento si tu estructura real difiere. (La carpeta `data/` que existía antes con
`db_scheme.sql`/`seed.sql` se consolidó dentro de `db/` para evitar tener dos copias del esquema divergiendo con el
tiempo — ver `docs/ENGINEERING_DECISIONS.md`.)

---

## 1. Requisitos previos

Se asume que en el servidor **CentOS Stream 10** ya está instalado y
corriendo PostgreSQL (servidor y cliente `psql`).

El rol de aplicación (`library_user`) y la base de datos se crean con
`db/00_create_database.sql`, **no a mano** — a propósito, para que
`library_user` quede con privilegios mínimos (no es dueño de la base,
no puede hacer DDL) en vez de tener `OWNER` completo. Ver
`docs/SECURITY_REVIEW.md`, control 9, y `docs/ENGINEERING_DECISIONS.md`,
decisión D-13.

```bash
# Ejecutar como el usuario del sistema "postgres" (superusuario de PostgreSQL):
sudo -i -u postgres psql -f db/00_create_database.sql
```

Antes de correrlo, edita `db/00_create_database.sql` y reemplaza el
placeholder `CAMBIA_ESTA_CONTRASEÑA_ANTES_DE_USAR` por una contraseña
real — **no la dejes en el archivo versionado en git** una vez definida
(o pásala por variable de entorno al ejecutar `psql`).

## 2. Instalar Node.js

CentOS Stream 10 no trae Node.js por defecto. Se instala desde el módulo
de `dnf` o desde NodeSource (recomendado, versión LTS más reciente):

```bash
sudo dnf module list nodejs        # ver versiones disponibles vía AppStream
sudo dnf module install -y nodejs:20

# --- o, alternativamente, vía NodeSource ---
curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
sudo dnf install -y nodejs

node -v
npm -v
```

## 3. Copiar el proyecto al servidor

```bash
sudo mkdir -p /opt/libreria
sudo chown $USER:$USER /opt/libreria
# copia el repositorio completo (apps/, db/, docs/) a /opt/libreria
# por ejemplo con scp, rsync o git clone
```

A partir de aquí se asume que el proyecto quedó en `/opt/libreria`, con
`/opt/libreria/db/` y `/opt/libreria/apps/web-monolito`.

## 4. Cargar el esquema en PostgreSQL

Los scripts de `db/` se cargan **en este orden exacto** (cada uno depende del
anterior), y no todos con el mismo rol: `00`, `01`, `04`, `05` y `06` son
DDL (crean la base, tablas, procedimientos, triggers y vistas) y deben
ejecutarse como el superusuario `postgres`; `library_user` a propósito
**no** tiene privilegio para crear objetos (ver `docs/SECURITY_REVIEW.md`,
control 9) — solo `02` y `03`, que son lectura/escritura de filas, se
ejecutan como `library_user`. (Verificado en una instancia local: intentar
correr `04_stored_procedures.sql` como `library_user` falla con
`ERROR: permiso denegado al esquema public`, como se espera.)

```bash
cd /opt/libreria

sudo -i -u postgres psql -f db/00_create_database.sql
sudo -i -u postgres psql -d library_db -f db/01_schema.sql

psql -h localhost -U library_user -d library_db -f db/02_seed_30_per_table.sql
psql -h localhost -U library_user -d library_db -f db/03_all_quieries_before_stored_procedures.sql

sudo -i -u postgres psql -d library_db -f db/04_stored_procedures.sql
sudo -i -u postgres psql -d library_db -f db/05_triggers.sql
sudo -i -u postgres psql -d library_db -f db/06_views.sql
```

`db/01_schema.sql` ya incluye `CREATE EXTENSION IF NOT EXISTS "pgcrypto"`
(necesaria para `gen_random_uuid()` en `usuarios`) y, al final, los
`GRANT SELECT, INSERT, UPDATE, DELETE` que le dan a `library_user`
exactamente los privilegios que la aplicación necesita — nada de DDL, ni
ser dueño de la base. Guarda la salida de cada paso (o una captura de
`psql`) como evidencia para `docs/GCP_COMMANDS.md`.

## 5. Configurar y probar la aplicación

```bash
cd /opt/libreria/apps/web-monolito
cp .env.example .env
nano .env     # confirma host/usuario/password/db (ya vienen con los valores del ejercicio)

npm install
npm start
```

Deberías ver `Servidor escuchando en http://localhost:3000`. Prueba desde
el mismo servidor:

```bash
curl -I http://localhost:3000/
```

Detén la prueba con `Ctrl+C` antes de continuar.

## 6. Crear el primer usuario administrador

El registro público (`/registro`) siempre crea cuentas con rol
`cliente`. La base de datos permite **como máximo un administrador**
(índice único parcial), así que ese primer administrador se promueve
manualmente una sola vez:

1. Regístrate normalmente desde `/registro` con el correo que usarás
   como administrador.
2. Promuévelo a administrador directamente en la base de datos:

```bash
psql -h localhost -U library_user -d library_db -c \
  "UPDATE usuarios SET rol = 'administrador' WHERE email = 'tu-correo@ejemplo.com';"
```

De ahí en adelante, la gestión de usuarios (incluyendo cambiar el rol)
se puede hacer desde `/admin/usuarios` estando logueado como
administrador.

## 7. Ejecutar como servicio (systemd)

Crea un usuario de sistema dedicado (opcional pero recomendado) y un
archivo de unidad:

```bash
sudo useradd -r -s /sbin/nologin nodeapp
sudo chown -R nodeapp:nodeapp /opt/libreria/apps/web-monolito
```

`/etc/systemd/system/web-monolito.service`:

```ini
[Unit]
Description=Libreria en Linea - monolito Node.js
After=network.target postgresql.service

[Service]
Type=simple
User=nodeapp
WorkingDirectory=/opt/libreria/apps/web-monolito
EnvironmentFile=/opt/libreria/apps/web-monolito/.env
ExecStart=/usr/bin/node src/server.js
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Activar:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now web-monolito
sudo systemctl status web-monolito
journalctl -u web-monolito -f     # logs en vivo
```

## 8. Firewall y SELinux

CentOS Stream trae `firewalld` y SELinux en modo `enforcing` por
defecto.

**Firewall** — abrir el puerto de la aplicación (3000, o el que hayas
puesto en `.env`):

```bash
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --reload
```

**SELinux** — un proceso Node.js corriendo en un puerto no privilegiado
(>1024) normalmente no requiere ajustes. Si más adelante pones un
proxy inverso (Nginx/Apache) delante de la app en el puerto 80/443,
habilita que el proxy pueda conectarse a la red:

```bash
sudo setsebool -P httpd_can_network_connect 1
```

Y si cambias `src/public/uploads` a una ruta fuera del árbol de la
aplicación, restaura su contexto SELinux:

```bash
sudo semanage fcontext -a -t httpd_sys_rw_content_t "/opt/libreria/apps/web-monolito/src/public/uploads(/.*)?"
sudo restorecon -Rv /opt/libreria/apps/web-monolito/src/public/uploads
```

## 9. (Opcional) Proxy inverso con Nginx en el puerto 80

```bash
sudo dnf install -y nginx
```

`/etc/nginx/conf.d/libreria.conf`:

```nginx
server {
    listen 80;
    server_name _;

    client_max_body_size 10M;   # permite subir imágenes

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo systemctl enable --now nginx
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --reload
```

---

## Notas de diseño relevantes para la evaluación

- **Macroarquitectura:** monolito — un único proceso Node.js, un único
  despliegue, acceso directo a la base de datos (sin microservicios ni
  API intermedia).
- **MVC:** cada módulo separa `*.model.js` (SQL parametrizado con
  `pg`), `*.controller.js` (orquesta petición/respuesta) y
  `*.routes.js` (mapeo URL→controlador); las vistas EJS viven en
  `views/` dentro de cada módulo.
- **Organización por módulos:** `src/modules/{auth, usuarios, libros,
  autores, generos, formatos, conceptos}`. Los cuatro catálogos simples
  (`autores`, `generos`, `formatos`, `conceptos`) comparten una
  *fábrica* de módulo CRUD (`modules/catalogo/catalogo.factory.js`)
  para no duplicar código estructuralmente idéntico, sin dejar de
  seguir MVC.
- **CRUD en todas las tablas normalizadas:** `usuarios`, `libros`,
  `autores`, `generos`, `formatos`, `conceptos` e `imagenes` tienen
  CRUD directo; `libro_autor` y `libro_genero` (tablas puente sin
  atributos propios) se gestionan como parte del formulario del libro;
  `libro_concepto` (tabla puente **con** atributo `definicion`) tiene
  su propia interfaz de alta/baja dentro de la ficha del libro.
- **Sin JSON/XML:** todas las mutaciones usan formularios HTML con
  método `POST` y redirección posterior (patrón PRG); la subida de
  imágenes usa `multipart/form-data` vía `multer`, no un endpoint de
  API.
