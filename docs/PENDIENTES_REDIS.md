# Actividad Redis + microservicios — estado y pendientes

Nota para retomar el trabajo desde otra computadora (el chat original no es accesible desde ahí).

## Hecho (en este commit)

- Paquete compartido `services/common` (`libreria_common`) y los 6 servicios con Redis: login (sesión, refresh, revocación), books (caché + invalidación), users, authors, pedidos y pagos. Arquitectura y claves: [REDIS_MICROSERVICIOS.md](REDIS_MICROSERVICIOS.md).
- App Tkinter con los 6 servicios: semáforos, CRUD, renovación automática del JWT, logout que revoca, soporte de certificado HTTPS (CA).
- Pruebas: common 26 · login 13 · books 30 · users 11 · authors 6 · pedidos 13 · pagos 12 · app 27 (todas con `fakeredis`, sin Redis ni PostgreSQL reales).
- Entrega preparada **fuera del repo** en la laptop: `C:\integracion\entrega\604775_Entrega_Redis.zip` (PDF de evidencias, reflexión, capturas, evidencia API). Las evidencias se tomaron en **local** con el Redis de la instancia por túnel.
- La animación para ubiquitous se hace en otro chat (no tocar aquí).

### Desplegado en la instancia GCP (2026-10-27)

- Clon de la instancia actualizado con un *git bundle* (el repo es privado; la instancia no tiene credenciales de GitHub).
- Los 6 servicios + SOAP corriendo con systemd; puertos, usuarios, rutas y nginx en [REDIS_MICROSERVICIOS.md § 8](REDIS_MICROSERVICIOS.md#8-despliegue-en-la-instancia-gcp-3413584131).
- Roles de BD nuevos (`users_app_user`, `authors_app_user`, `orders_app_user`, `payments_app_user`) con contraseña aleatoria y migraciones aplicadas. `pg_hba.conf` quedó como estaba (md5).
- SOAP movido al 5006 (y la app Electron apunta ahí).
- HTTPS por nginx en 8440–8445 con CA propia; el certificado público de la CA se copió a la laptop en `%USERPROFILE%\.libreria_secretos\libreria-ca.crt`.
- Verificado por túnel SSH: evidencias API 26/26 por HTTPS y la app de escritorio completa contra la instancia.

## Pendiente

- **Firewall de GCP:** solo están abiertos desde fuera 5000, 5001, 5002 y 80. Para usar desde Internet los servicios nuevos y el HTTPS hay que crear la regla (el asistente no tiene permiso para hacerlo):
  ```bash
  gcloud compute firewall-rules create allow-libreria-microservicios --network=default --direction=INGRESS --action=ALLOW --rules=tcp:5003-5006,tcp:8440-8445 --source-ranges=0.0.0.0/0
  ```
  Mientras tanto se puede llegar a todo por túnel SSH (`-L 8440:127.0.0.1:8440` … `-L 8445:127.0.0.1:8445`).
- **Opcional, endurecer:** cuando todo se use por HTTPS, cerrar el HTTP directo (5000–5005) en firewalld/GCP y poner `SESSION_COOKIE_SECURE=true` en login.
- **App contra la instancia:** en *Configuración*, URLs `https://34.135.84.31:8440` … `:8445` y el certificado `libreria-ca.crt` (requiere la regla de firewall de arriba).

### Otros

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
