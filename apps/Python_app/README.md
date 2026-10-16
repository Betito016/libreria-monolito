# Librería en Línea — Cliente de escritorio en Python

Aplicación de escritorio que funciona como **cliente de los 6 microservicios** de la librería: login, books, users, authors, pedidos y pagos. Toda la información se obtiene y se modifica **a través de sus endpoints HTTP**; la aplicación nunca se conecta a las bases de datos ni a Redis.

| | |
|---|---|
| **Python** | 3.10 o superior (desarrollada y probada con **3.14.5**) |
| **Biblioteca gráfica** | **Tkinter** (incluida en Python) con widgets `ttk` |
| **Dependencias** | `requests` (HTTP) y `Pillow` (portadas JPEG) — ver `requirements.txt` |
| **Sistema** | Windows 11 |

Arquitectura de los servicios y de la capa Redis: [docs/REDIS_MICROSERVICIOS.md](../../docs/REDIS_MICROSERVICIOS.md).

---

## 1. Instalación

```powershell
cd library\apps\Python_app
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Tkinter viene con el instalador oficial de Python para Windows. Para comprobarlo: `python -m tkinter` debe abrir una ventana pequeña.

## 2. Ejecución

```powershell
.\venv\Scripts\activate
python main.py
```

## 3. Configuración

La primera vez, la aplicación usa los valores predeterminados (servicios locales):

| Servicio | Dirección predeterminada |
|---|---|
| Login | `http://127.0.0.1:5000` |
| Libros | `http://127.0.0.1:5001` |
| Pagos | `http://127.0.0.1:5002` |
| Pedidos | `http://127.0.0.1:5003` |
| Usuarios | `http://127.0.0.1:5004` |
| Autores | `http://127.0.0.1:5005` |

Se usa `127.0.0.1` y no `localhost` a propósito: en Windows, `localhost` se resuelve primero a `::1` (IPv6), pero el servidor de Flask escucha solo en IPv4. Cada conexión esperaba unos 2 segundos el reintento antes de caer a IPv4 (medido: 2069 ms contra 0 ms).

Para trabajar contra la **instancia remota** no hay que tocar el código: en la pantalla inicial, **⚙ Configurar servidor** (o, ya dentro, la sección **Configuración**):

1. Escribe las seis direcciones.
2. **Probar conexión** consulta `GET /health` en las seis sin guardar nada.
3. **Guardar** aplica el cambio de inmediato y lo conserva para los siguientes arranques.
4. **Restaurar predeterminados** vuelve a `127.0.0.1`.

Otros valores de esa pantalla:

| Campo | Para qué |
|---|---|
| Tiempo máximo de espera | Timeout de cada petición |
| Comprobar estado cada | Intervalo del semáforo |
| Renovar el JWT cuando falten | Segundos antes del vencimiento en que la app pide un JWT nuevo (120 por defecto) |
| Certificado HTTPS (CA) | Ruta al certificado autofirmado de nginx en la instancia. Con él, las direcciones `https://` se verifican; un certificado que no coincide se reporta como `TLS_INVALIDO` |

### Dónde se conserva la información local

| Archivo | Contenido |
|---|---|
| `%APPDATA%\LibreriaPythonApp\config.json` | Direcciones de los servicios y tiempos. Sin credenciales. |
| `%APPDATA%\LibreriaPythonApp\sesion.json` | Cookie de sesión, JWT y refresh token, por servidor. **Nunca la contraseña.** |
| `%APPDATA%\LibreriaPythonApp\errores.log` | Detalle técnico de errores inesperados. |

Ninguno está dentro del repositorio. Las rutas exactas aparecen también en la sección **Configuración**.

---

## 4. Secciones

| Sección | Servicio | Acceso |
|---|---|---|
| Catálogo (búsqueda, detalle con imágenes y conceptos) | books | público; muestra `X-Cache` (Redis) |
| Autores (CRUD; libros como lista de ISBN) | authors | lectura pública, escritura administrador |
| Pedidos (crear con selector de libros, cancelar, enviado, entregado, **Pagar →**) | pedidos | cliente: los suyos · administrador: todos |
| Pagos (pagar un pedido pendiente, **Reembolsar**) | pagos | cliente: los suyos · administrador: todos |
| Libros (admin): POST · PUT · PATCH · DELETE | books | administrador |
| Usuarios (CRUD, rol, activo) | users | administrador (un cliente ve el 403 del servidor) |
| Sesión y perfil (renovar JWT, PATCH /profile) | login | sesión iniciada |
| Estado de servicios (semáforo de los 6) | todos, `GET /health` | público |
| Configuración, Registro HTTP | — | — |

Las vistas de Usuarios, Autores, Pedidos y Pagos comparten `gui/crud_view.py`: tabla, formulario de detalle, **+ Nuevo**, **Guardar** (POST, o PATCH solo con los campos cambiados), **Eliminar** con confirmación y el panel *Última petición* (método, URL, si llevó Bearer, código HTTP y cuerpo). La interfaz deshabilita lo que el rol no permite, pero quien decide es el microservicio (401/403).

## 5. Estructura de la aplicación

```
apps/Python_app/
├── main.py                        Punto de entrada
├── requirements.txt
└── libreria_app/
    ├── config/settings.py         SERVICIOS (nombre, puerto), AppConfig, config.json
    ├── api/http_client.py         ÚNICO módulo que usa la red: Bearer, TLS, logs enmascarados
    ├── services/
    │   ├── auth_service.py        Login, renovación (refresh), logout, perfil
    │   ├── session_store.py       Cookie + JWT + refresh guardados por servidor
    │   ├── health_service.py      Semáforo verde/amarillo/rojo de los 6 servicios
    │   ├── books_service.py       Catálogo y CRUD de libros
    │   ├── users_service.py       Usuarios y roles
    │   ├── authors_service.py     Autores
    │   ├── orders_service.py      Pedidos (Idempotency-Key en cada POST)
    │   └── payments_service.py    Pagos y reembolsos
    └── gui/
        ├── app.py                 Ventana, reloj del JWT, renovación automática, salud
        ├── tasks.py               Hilos de trabajo (la ventana nunca se congela)
        ├── crud_view.py           Vista base de los recursos
        ├── users_view.py · authors_view.py · orders_view.py · payments_view.py
        ├── login_view.py · dashboard_view.py · catalog_view.py · admin_view.py
        ├── profile_view.py · status_view.py · config_view.py · http_log_view.py
        └── dialogs.py · widgets.py · theme.py
```

Las capas solo se comunican hacia abajo: la **GUI** llama a los **servicios**, los servicios llaman al **cliente HTTP**, y solo el cliente HTTP toca la red. Los filtros de búsqueda se leen en el hilo de Tkinter antes de lanzar la petición: los hilos de trabajo nunca tocan widgets.

## 6. JWT, renovación y Redis desde el punto de vista del cliente

```
POST /login (público) ─► JWT (20 min) + refresh token + cookie de sesión
        │                 la sesión vive en Redis del lado del servidor
        ▼
ApiClient.request() agrega  Authorization: Bearer <JWT>  solo donde hace falta
        │
        ├─ books / authors: solo escrituras          (las lecturas son públicas y cacheadas)
        ├─ users / pedidos / pagos: todo             (salvo /health, /metrics, /roles)
        └─ login: /profile y /logout
        ▼
cada servicio valida firma + vencimiento + revocación en Redis + rol
        │
        ├─ 401 → la app vuelve al login con el motivo (expirado, revocado, inválido)
        └─ 403 → el mensaje del servidor, sin cerrar la sesión
```

- **Renovación automática:** el reloj de la barra superior muestra `JWT: mm:ss`. Cuando faltan `renovar_antes_segundos` (120), la app llama a `POST /token/refresh`; el servidor rota el refresh y revoca el JWT anterior. Si el login no responde, reintenta cada 15 s mientras al token le quede vida. El botón **Renovar** lo hace a mano.
- **Al reabrir la app**, valida la sesión guardada con `GET /session` y, si el JWT guardado está por vencer o venció, lo renueva.
- **Cerrar sesión** envía `POST /logout` con el Bearer y el refresh token: el servidor revoca el `jti` en Redis, así que una copia del token ya no sirve en ningún servicio. La app además lo borra de memoria y de disco.
- **Cambiar correo o contraseña** en *Sesión y perfil* cierra todas las sesiones del usuario: la app regresa al login.

### Logs en consola

```
--> PATCH http://127.0.0.1:5001/api/books/978...?format=json   [servicio de libros]
    Headers: Accept: application/json | Content-Type: application/json | Authorization: Bearer [JWT PRESENTE eyJhbGciOi…sZ1g (513 caracteres)]
    Autenticacion: REQUERIDA (JWT) -> se envia el Bearer token recibido en el login
    Datos enviados: {"precio": 150.0}
<-- HTTP 200 en 10 ms | EXITO | Libro modificado parcialmente.
```

- **El JWT y el refresh token nunca se imprimen completos.** Contraseñas, `access_token` y `refresh_token` aparecen como `••••••`.
- Las lecturas cacheadas muestran `X-Cache: HIT | MISS`.
- Las comprobaciones periódicas de `/health` no se muestran; para verlas: `set LIBRERIA_LOG=DEBUG`.

## 7. Estado de los servicios

| Color | Significado | Cómo se detecta |
|---|---|---|
| 🟢 Verde | Funciona: responde y tiene acceso a PostgreSQL y a Redis | `/health` responde `"estado": "ok"` |
| 🟡 Amarillo | Responde, pero Redis, su base de datos o el login no están disponibles (las operaciones con token se rechazan por seguridad) | `"estado": "degradado"` |
| 🔴 Rojo | No hay respuesta útil | Sin conexión, tiempo agotado, URL inválida, o en ese puerto contesta otro programa |

Cada tarjeta muestra PostgreSQL, Redis (con su latencia) y las capacidades del servicio.

## 8. Pruebas

```powershell
.\venv\Scripts\python -m pytest -q        # 27 pruebas
```

`tests/test_http_client_jwt.py` comprueba qué rutas de cada uno de los 6 servicios llevan `Authorization: Bearer` y cuáles no, que `/logout` envía el JWT y el refresh token, que después del logout ninguna petición lleva token, y que los logs no revelan el JWT ni el refresh token.

## 9. Problemas conocidos

- **Credenciales guardadas:** `sesion.json` contiene el JWT y el refresh token mientras la sesión esté viva; quien lo copie podría usarlos hasta que expiren o hasta el logout (que sí los revoca en el servidor).
- **Correo de verificación en la instancia GCP:** Google Cloud bloquea el puerto 25 saliente; el código de verificación se lee en el servidor con `sudo mailq` y `sudo postcat -q <id>`.
- **Portadas:** para varios ISBN, Open Library no tiene portada; la app muestra *Imagen no disponible*.

## 10. Solución de problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| Servicios en 🔴 al abrir | Direcciones equivocadas o servicios apagados | **Configuración → Probar conexión** para ver cuál falla |
| Todos en 🟡 "Redis no disponible" | Redis caído o el túnel SSH cerrado | Reabrir el túnel / `systemctl status redis` en la instancia |
| "El token fue revocado" (401) | Se cerró la sesión, se renovó el token o cambió la contraseña/rol | Iniciar sesión de nuevo |
| "El refresh token no es válido" (401) | Ya se usó, o la sesión (60 min) expiró | Iniciar sesión de nuevo |
| "Tu rol no tiene permiso" (403) | La cuenta es `cliente` | Usuarios, Libros (admin) y reembolsos requieren al administrador |
| Error de certificado (`TLS_INVALIDO`) | `https://` sin la CA configurada o CA equivocada | Configuración → Certificado HTTPS (CA) |
| `ModuleNotFoundError: PIL` o `requests` | No se activó el entorno virtual | `.\venv\Scripts\activate` y `pip install -r requirements.txt` |
| Aparece "Error inesperado" | Error no previsto | El detalle queda en `%APPDATA%\LibreriaPythonApp\errores.log` |
