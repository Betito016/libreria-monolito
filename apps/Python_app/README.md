# Librería en Línea — Cliente de escritorio en Python

Aplicación de escritorio que funciona como **cliente de los microservicios** de autenticación (`services/login`) y de gestión de libros (`services/books`). Toda la información se obtiene y se modifica **a través de sus endpoints HTTP**; la aplicación nunca se conecta a las bases de datos.

| | |
|---|---|
| **Python** | 3.10 o superior (desarrollada y probada con **3.14.5**) |
| **Biblioteca gráfica** | **Tkinter** (incluida en Python) con widgets `ttk` |
| **Dependencias** | `requests` (HTTP) y `Pillow` (portadas JPEG) — ver `requirements.txt` |
| **Sistema** | Windows 11 |

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

Se usa `127.0.0.1` y no `localhost` a propósito: en Windows, `localhost` se resuelve primero a `::1` (IPv6), pero el servidor de Flask escucha solo en IPv4. Cada conexión esperaba unos 2 segundos el reintento antes de caer a IPv4 (medido: 2069 ms contra 0 ms). `localhost` sigue funcionando, solo que más lento.

Para trabajar contra la **instancia remota** no hay que tocar el código: en la pantalla inicial, **⚙ Configurar servidor** (o, ya dentro, la sección **Configuración**):

1. Escribe las direcciones, por ejemplo `http://34.135.84.31:5000` y `http://34.135.84.31:5001`.
2. **Probar conexión** consulta `GET /health` en ambas direcciones sin guardar nada.
3. **Guardar** aplica el cambio de inmediato y lo conserva para los siguientes arranques.
4. **Restaurar predeterminados** vuelve a `localhost`.

Se puede escribir `localhost:5000` o `http://localhost:5000/`: la aplicación normaliza la dirección (agrega `http://` y quita la `/` final). Si se escribe una ruta (`…:5001/books`), la rechaza con un mensaje, porque la aplicación construye ella misma las rutas de cada endpoint.

### Dónde se conserva la información local

| Archivo | Contenido |
|---|---|
| `%APPDATA%\LibreriaPythonApp\config.json` | Direcciones de los servicios y tiempos. Sin credenciales. |
| `%APPDATA%\LibreriaPythonApp\sesion.json` | La **cookie de sesión** emitida por el login, por servidor. **Nunca la contraseña.** |
| `%APPDATA%\LibreriaPythonApp\errores.log` | Detalle técnico de errores inesperados. |

Ninguno está dentro del repositorio. Las rutas exactas aparecen también en la sección **Configuración**.

---

## 4. Estructura de la aplicación

```
apps/Python_app/
├── main.py                        Punto de entrada
├── requirements.txt
└── libreria_app/
    ├── config/
    │   └── settings.py            CONFIGURACIÓN: direcciones, validación, archivo config.json
    ├── api/
    │   └── http_client.py         COMUNICACIÓN HTTP: único módulo que usa la red
    ├── services/
    │   ├── auth_service.py        AUTENTICACIÓN / SESIÓN / PERFIL (microservicio de login)
    │   ├── session_store.py       Persistencia local de la cookie de sesión
    │   ├── books_service.py       LIBROS: catálogo, búsqueda y CRUD (microservicio de libros)
    │   └── health_service.py      COMPROBACIÓN DE SERVICIOS: semáforo verde/amarillo/rojo
    └── gui/                       GUI
        ├── app.py                 Ventana principal, reloj de sesión, monitoreo de salud
        ├── tasks.py               Ejecución en segundo plano (la ventana nunca se congela)
        ├── login_view.py          Iniciar sesión · crear cuenta · verificar correo
        ├── dashboard_view.py      Panel principal y menú de secciones
        ├── catalog_view.py        Catálogo, búsqueda y paginación
        ├── dialogs.py             Detalle del libro (varias imágenes) y aviso de expiración
        ├── admin_view.py          POST · PUT · PATCH · DELETE
        ├── profile_view.py        Sesión y perfil
        ├── status_view.py         Estado de los microservicios
        ├── config_view.py         Configuración del servidor
        ├── http_log_view.py       Registro de peticiones HTTP
        ├── widgets.py             Semáforo, área con scroll, caché de imágenes
        └── theme.py               Colores y estilos
```

Las capas solo se comunican hacia abajo: la **GUI** llama a los **servicios**, los servicios llaman al **cliente HTTP**, y solo el cliente HTTP toca la red. Ninguna pantalla importa `requests`.

### Recorrido de una petición

Ejemplo: el usuario presiona **Guardar solo cambios (PATCH)** en Administración.

```
admin_view._modificar()              compara el formulario con el libro tal como llegó
        │                            del servidor y arma {"precio": 199.5}
        ▼
tasks.BackgroundRunner.run()         manda el trabajo a un hilo aparte
        │
        ▼  (hilo de trabajo)
books_service.modificar(isbn, cambios)
        │
        ▼
http_client.ApiClient.request()      arma  PATCH http://host:5001/api/books/{isbn}?format=json
        │                            con  Authorization: Bearer <JWT>  y timeout,
        │                            y lo registra en la consola (token enmascarado)
        ▼
────────── red ──────────►  microservicio de libros
                                 ├─ @requiere_jwt_administrador: firma, algoritmo,
                                 │  vencimiento y rol administrador del JWT
                                 ├─ valida los datos, UPDATE en PostgreSQL
                                 └─ responde HTTP 200 + JSON del libro
        ◄──────────────────
http_client  → ApiResult(ok, status=200, data, mensaje)   (nunca lanza excepciones a la GUI)
        │
        ▼  (cola → hilo de Tkinter)
admin_view._resultado()              muestra el mensaje, el cuerpo enviado,
                                     y pide al catálogo que se recargue del servidor
```

Si en cualquier punto la respuesta es **401**, `app.verificar_sesion()` descarta la sesión local y regresa a la pantalla de inicio de sesión.

---

## 5. Microservicios consumidos

| Operación | Método | Endpoint | Servicio |
|---|---|---|---|
| Registrarse | POST | `/register` | login |
| Verificar correo | GET | `/verify?token=…` | login |
| Iniciar sesión | POST | `/login` | login |
| Cerrar sesión | POST | `/logout` | login |
| Validar sesión · ver perfil | GET | `/session` | login |
| Extender sesión | POST | `/session/extend` | login |
| Modificar perfil | PATCH | `/profile` | login |
| Estado | GET | `/health` | ambos |
| Catálogo y búsqueda | GET | `/api/books?isbn=&titulo=&anio=&precio_min=&precio_max=` | libros · público |
| Detalle con conceptos | GET | `/api/books/{isbn}` | libros · público |
| Categorías | GET | `/categories` | libros · público |
| Registrar | POST | `/api/books` | libros · **Bearer JWT** |
| Actualización completa | PUT | `/api/books/{isbn}` | libros · **Bearer JWT** |
| Actualización parcial | PATCH | `/api/books/{isbn}` | libros · **Bearer JWT** |
| Eliminar | DELETE | `/api/books/{isbn}` | libros · **Bearer JWT** |

Todas las peticiones llevan `?format=json` (los servicios responden XML por defecto).

### Flujo JWT

```
Login (POST /login, público) ──► el servicio de login valida credenciales y emite un JWT
        │
        ▼
AuthService._recibir_token()  ──► guarda el token en ApiClient.token (y en sesion.json)
        │
        ▼
GET /api/books (público)      ──► viaja SIN Authorization
        │
        ▼
POST/PUT/PATCH/DELETE         ──► ApiClient.request() agrega  Authorization: Bearer <token>
        │
        ▼
Servicio de libros            ──► valida firma, algoritmo y vencimiento; exige rol administrador
        │
        ▼
401 (token ausente, inválido o expirado) ──► la app regresa al inicio de sesión con el motivo
```

El header se agrega **en un solo lugar**: `ApiClient.request()` (`api/http_client.py`), solo cuando el servicio es libros y el método es POST, PUT, PATCH o DELETE. Ninguna pantalla ni servicio arma headers.

### Quién conserva la sesión

- **El servidor** (microservicio de login) es la autoridad. Emite dos credenciales que vencen juntas (30 minutos, prorrogables con `POST /session/extend`):
  - la **cookie** `libreria_login_session`, que usan `/session`, `/session/extend` y `/profile`;
  - el **JWT**, que el servicio de libros exige en sus escrituras.
- **En memoria**, `ApiClient.session` (una `requests.Session`) guarda la cookie y `ApiClient.token` guarda el JWT.
- **En disco**, `SessionStore` guarda la cookie y el JWT para no pedir credenciales al reabrir la app. Al arrancar, **siempre** se valida con `GET /session`: tenerlos guardados no garantiza que la sesión siga viva.
- **Al cerrar sesión**, la app olvida ambos. Un JWT no se puede revocar en el servidor: una copia seguiría siendo válida hasta que venza.

### Logs en consola

Al ejecutar `python main.py`, la consola muestra cada petición:

```
--> PATCH http://127.0.0.1:5001/api/books/978...?format=json   [servicio de libros]
    Headers: Accept: application/json | Content-Type: application/json | Authorization: Bearer [JWT PRESENTE eyJhbGciOi…sZ1g (288 caracteres)]
    Autenticacion: REQUERIDA (JWT) -> se envia el Bearer token recibido en el login
    Datos enviados: {"precio": 150.0}
<-- HTTP 200 en 10 ms | EXITO | Libro modificado parcialmente.
    Respuesta: {...}
```

- **El token nunca se imprime completo**, solo sus primeros y últimos caracteres. Contraseñas y `access_token` aparecen como `••••••`.
- **Comprobaciones de `/health`:** las periódicas no se muestran para no llenar la consola cada 15 s. Para verlas: `set LIBRERIA_LOG=DEBUG`.
- **Registro HTTP:** la sección del mismo nombre, dentro de la app, tiene la columna **Auth** (`Bearer` o `—`).

### PUT vs PATCH

| | PUT | PATCH |
|---|---|---|
| Semántica | Reemplaza el libro completo | Modifica solo lo enviado |
| Cuerpo | Los 9 campos, siempre | Solo los campos que cambiaron |
| Omitir un campo | El servidor responde 400 | Ese campo queda igual |
| Botón | Guardar todo (PUT) | Guardar solo cambios (PATCH) |

El panel **Última petición enviada** muestra el cuerpo exacto de cada operación.

---

## 6. Estado de los servicios

| Color | Significado | Cómo se detecta |
|---|---|---|
| 🟢 Verde | Funciona y tiene acceso a su base de datos | `/health` responde `"estado": "ok"` |
| 🟡 Amarillo | Responde, pero una dependencia está caída | `/health` responde `"estado": "degradado"` (aunque sea con HTTP 503) |
| 🔴 Rojo | No hay respuesta útil | Sin conexión, tiempo agotado, URL inválida, o en ese puerto contesta otro programa |

Se comprueba automáticamente cada 15 s (configurable), y con el botón **Comprobar ahora**.

---

### Pruebas

```powershell
.\venv\Scripts\python -m pytest -q
```

`tests/test_http_client_jwt.py` comprueba que las escrituras a libros llevan `Authorization: Bearer`, que los GET y el login no lo llevan, y que los logs marcan el token sin revelarlo.

## 7. Problemas conocidos

- **Sin HTTPS.** Los servicios del curso usan HTTP plano: credenciales y cookie viajan sin cifrar.
- **La cookie y el JWT guardados son credenciales** mientras estén vigentes: quien copie `sesion.json` podría actuar como el usuario hasta que expiren.
- **Cerrar sesión no invalida copias de la cookie ni del JWT.** Ninguno tiene estado en el servidor: `POST /logout` hace que *este* cliente los olvide, pero una copia tomada antes seguiría siendo válida hasta su vencimiento (30 minutos).
- **Correo de verificación en la instancia GCP:** Google Cloud bloquea el puerto 25 saliente, así que el correo se genera y queda en la cola de Postfix, pero no llega a buzones externos. El código de verificación se puede leer en el servidor con `sudo mailq` y `sudo postcat -q <id>`.
- **Portadas:** para varios ISBN de `library.xml`, Open Library no tiene portada (devuelve una imagen de 1×1). La aplicación lo muestra como *Imagen no disponible*.
- **Local y remoto con distinto host:** si login y libros se configuran en servidores diferentes, la cookie del login no viaja al servicio de libros y las escrituras responderán 401.

## 8. Solución de problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| Ambos servicios en 🔴 al abrir | Direcciones equivocadas o servicios apagados | **Configuración → Probar conexión** para ver cuál falla |
| 🔴 "respondió, pero no como el servicio de libros" | El puerto apunta a otro programa (p. ej. Nginx en el 80) | Corregir el puerto |
| 🔴 "no respondió en N segundos" | Firewall o servicio caído | Revisar firewall de GCP / `firewalld` y `systemctl status library-books` |
| Libros en 🟡 "no se pueden iniciar sesiones nuevas" | El servicio de login está caído | Levantar `library-login`. Mientras tanto, el catálogo y las sesiones ya iniciadas (su JWT) siguen funcionando |
| Login: "todavía no puede iniciar sesión" (403) | Correo sin verificar | Pestaña **Verificar correo** con el código recibido |
| "Tu cuenta no tiene permisos" (403) al guardar | La cuenta tiene rol `cliente` | El CRUD requiere un administrador |
| "Tu token de acceso (JWT) expiró" o "rechazó tu token" (401) | El JWT venció o `JWT_SECRET` no es igual en login y libros | Iniciar sesión de nuevo; revisar que ambos `.env` tengan la misma `JWT_SECRET` |
| Al abrir pide iniciar sesión otra vez | La sesión guardada expiró (30 min) o se cambió de servidor | Iniciar sesión de nuevo |
| `ModuleNotFoundError: PIL` o `requests` | No se activó el entorno virtual | `.\venv\Scripts\activate` y `pip install -r requirements.txt` |
| Aparece un diálogo "Error inesperado" | Error no previsto | El detalle queda en `%APPDATA%\LibreriaPythonApp\errores.log` |
