# Actividad Redis + microservicios — estado y pendientes

Nota para retomar el trabajo desde otra computadora (el chat original no es accesible desde ahí).

## Hecho (en este commit)

- Paquete compartido `services/common` (`libreria_common`) y los 6 servicios con Redis: login (sesión, refresh, revocación), books (caché + invalidación), users, authors, pedidos y pagos. Arquitectura y claves: [REDIS_MICROSERVICIOS.md](REDIS_MICROSERVICIOS.md).
- App Tkinter con los 6 servicios: semáforos, CRUD, renovación automática del JWT, logout que revoca, soporte de certificado HTTPS (CA).
- Pruebas: common 26 · login 13 · books 30 · users 11 · authors 6 · pedidos 13 · pagos 12 · app 27 (todas con `fakeredis`, sin Redis ni PostgreSQL reales).
- Entrega preparada **fuera del repo** en la laptop: `C:\integracion\entrega\604775_Entrega_Redis.zip` (PDF de evidencias, reflexión, capturas, evidencia API). Las evidencias se tomaron en **local** con el Redis de la instancia por túnel.
- La animación para ubiquitous se hace en otro chat (no tocar aquí).

## Pendiente

### Paso 8 — Despliegue en la instancia GCP (`integracion`, zona `us-central1-c`)

El repo es privado: la instancia se actualiza con un *git bundle* (no puede hacer `git pull` de GitHub).

1. **Código:** actualizar el clon de la instancia con un bundle y copiar/actualizar los servicios en su carpeta de despliegue (login y books ya existen como `library-login` / `library-books`).
2. **Variables:** en el `.env` de login y books renombrar `JWT_SECRET` → `JWT_SECRET_KEY` (mismo valor) y agregar `REDIS_URL=redis://:<requirepass>@127.0.0.1:6379/0`, `ACCESS_TOKEN_MINUTES=20`, `CORS_ORIGINS`. Quitar `SECRET_KEY` y `SESSION_LIFETIME_MINUTES` de login. Los 6 `.env` con la **misma** `JWT_SECRET_KEY`. Los secretos se generan en el servidor y no se imprimen.
3. **Base de datos:** crear los roles `users_app_user`, `authors_app_user`, `orders_app_user`, `payments_app_user` con contraseña aleatoria y aplicar:
   - `library_db`: `db/10_roles.sql`, `db/11_users_service.sql`
   - `libreria_db`: `services/authors/sql/01_autores.sql`, `services/pedidos/sql/01_pedidos.sql`, `services/pagos/sql/01_pagos.sql`
   (El procedimiento con superusuario/`pg_hba` en la instancia requiere autorización explícita cada vez.)
4. **venvs:** en cada servicio `pip install -r requirements.txt` (instala `-e ../common`).
5. **systemd:** unidades nuevas `library-users` (5004), `library-authors` (5005), `library-pedidos` (5003), `library-pagos` (5002), con su usuario de sistema, igual que `library-login` / `library-books`. Reiniciar login y books.
6. **SOAP 5002 → 5006:** mover el servicio SOAP al 5006 (su unidad y su `.env`) y actualizar la app Electron (`apps/electron-catalog/src/models/ConfigModel.js`) y sus docs.
7. **Firewall:** abrir los puertos nuevos en el firewall de GCP y en `firewalld` (o solo 443 si todo va por nginx).
8. **HTTPS:** nginx con certificado autofirmado delante de los 6 servicios; copiar el certificado de la CA a la laptop y ponerlo en la app (*Configuración → Certificado HTTPS (CA)*). Con HTTPS, `SESSION_COOKIE_SECURE=true` en login.
9. Probar con la app contra la instancia (Configuración → Probar conexión de las 6 URLs).

### Otros

- Revisar si en la instancia quedó el libro de prueba ISBN `9786047750057` de la actividad JWT y borrarlo.
- En la base **local** de la laptop se borró por error el autor id 16 (no era de la semilla: probablemente el autor huérfano de un libro de prueba de la actividad JWT). Los 15 autores semilla están completos.

## Trabajar en local desde otra PC

Requisitos: Python 3.14, PostgreSQL 18 local con `library_db` y `libreria_db`, `gcloud` autenticado con acceso a la instancia.

Usar `127.0.0.1`, no `localhost` (en Windows `localhost` tarda 2 s por IPv6).

```powershell
# 1) Túnel a Redis de la instancia (ventana aparte; se reconecta solo)
powershell -ExecutionPolicy Bypass -File tools\dev_local\tunel_redis.ps1

# 2) Contraseña de Redis: crear %USERPROFILE%\.libreria_secretos\redis.env con
#      REDIS_URL=redis://:<requirepass>@127.0.0.1:6379/0
#    (el requirepass está en la configuración de Redis de la instancia; no versionarlo)

# 3) venv de cada servicio (y de la app)
cd services\<servicio>; python -m venv venv; venv\Scripts\pip install -r requirements.txt

# 4) Roles, migraciones y .env de los servicios nuevos (pide la contraseña de postgres en esta terminal)
$env:PGPASSWORD = '...'
python tools\dev_local\preparar_servicio_local.py users authors pedidos pagos
# login y books: copiar su .env.example a .env y poner DB_PASSWORD de su rol; luego las variables comunes
python tools\dev_local\actualizar_env_local.py login books

# 5) Levantar los 6 servicios (ventanas, o --logs <carpeta> para segundo plano)
python tools\dev_local\levantar_servicios.py
```

Los `.env` y `redis.env` **no** están en el repo: hay que crearlos en cada computadora.
