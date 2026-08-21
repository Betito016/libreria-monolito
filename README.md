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
├── data/
│   └── db_scheme.sql        <- esquema PostgreSQL (Parte 1 del ejercicio)
└── apps/
    └── web-monolito/        <- esta aplicación
        ├── package.json
        ├── .env.example
        └── src/...
```

Ajusta las rutas de este documento si tu estructura real difiere.

---

## 1. Requisitos previos

Se asume que en el servidor **CentOS Stream 10** ya están instalados y
corriendo:

- PostgreSQL (servidor y cliente `psql`)
- Un rol `library_user` con contraseña `library666`
- Una base de datos `library_db` propiedad de (o con privilegios totales
  para) `library_user`

Si el rol/base de datos aún no existen, créalos como el usuario del
sistema `postgres`:

```bash
sudo -i -u postgres psql -c "CREATE ROLE library_user WITH LOGIN PASSWORD 'library666';"
sudo -i -u postgres psql -c "CREATE DATABASE library_db OWNER library_user;"
```

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
# copia el repositorio completo (apps/ y data/) a /opt/libreria
# por ejemplo con scp, rsync o git clone
```

A partir de aquí se asume que el proyecto quedó en `/opt/libreria`, con
`/opt/libreria/data/db_scheme.sql` y `/opt/libreria/apps/web-monolito`.

## 4. Cargar el esquema en PostgreSQL

```bash
cd /opt/libreria
psql -h localhost -U library_user -d library_db -f data/db_scheme.sql
```

Te pedirá la contraseña (`library666`).

> **Nota sobre `pgcrypto`:** el esquema usa `CREATE EXTENSION IF NOT
> EXISTS "pgcrypto"` (necesaria para `gen_random_uuid()` en la tabla
> `usuarios`). Si `library_user` no tiene privilegio `CREATEDB`/superusuario
> y la extensión falla, créala una vez como `postgres`:
> ```bash
> sudo -i -u postgres psql -d library_db -c 'CREATE EXTENSION IF NOT EXISTS "pgcrypto";'
> ```
> y vuelve a ejecutar `db_scheme.sql` (o solo la parte de `CREATE TABLE`
> en adelante).

Si ejecutaste el script como `postgres` en vez de `library_user`, otorga
privilegios explícitos:

```bash
sudo -i -u postgres psql -d library_db -c "
  GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO library_user;
  GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO library_user;
"
```

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
