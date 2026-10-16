# Microservicio de Autenticación

Microservicio **independiente** de autenticación y gestión básica de usuarios para la plataforma de librería en línea.

**Stack:** Python · Flask · Psycopg 3 · PostgreSQL · Redis
**Puerto:** 5000
**Base de datos:** `library_db` (la misma del monolito Node.js — no se crea una base paralela)

Arquitectura de los 6 servicios y de la capa Redis: [docs/REDIS_MICROSERVICIOS.md](../../docs/REDIS_MICROSERVICIOS.md).

---

## Endpoints

| Método   | Endpoint    | Función                                          | Acceso |
|----------|-------------|--------------------------------------------------|---|
| POST     | `/register` | Registrar un nuevo usuario y enviar correo de verificación | público |
| GET/POST | `/verify`   | Canjear el token del correo y marcar el correo como verificado | público |
| POST     | `/login`    | Validar credenciales, crear la sesión en Redis y emitir JWT + refresh token | público |
| POST     | `/token/refresh` | Renovar el JWT con el refresh token (rotación, un solo uso) | refresh token |
| POST     | `/session/extend` | Renovar el JWT con la cookie de sesión       | cookie |
| GET      | `/session`  | Consultar la sesión, el perfil y cuánto le queda  | cookie |
| POST     | `/logout`   | Revocar el JWT y borrar sesión y refresh token     | Bearer |
| PATCH    | `/profile`  | Modificar nombre, apellidos, correo o contraseña  | Bearer |
| GET      | `/health`, `/metrics` | Estado (PostgreSQL y Redis) y métricas  | público |

**Cuentas que no pueden autenticarse:** `/login` responde **403** `ERR_CORREO_NO_VERIFICADO` si el correo no se ha verificado, y `ERR_CUENTA_INACTIVA` si la cuenta está desactivada. Ambos se informan solo después de validar la contraseña, para no revelar el estado de cuentas ajenas.

**Perfil:** `PATCH /profile` modifica solo los campos enviados. Cambiar correo o contraseña exige `password_actual`; un correo nuevo queda sin verificar y se envía otro token. `rol`, `activo` e `id` se rechazan con 400 `ERR_CAMPOS_NO_PERMITIDOS`: un usuario no puede ascenderse a administrador editando su perfil. Un cambio de correo o contraseña **cierra todas las sesiones** del usuario y revoca sus JWT (`sesiones_cerradas: true`).

### Sesión, JWT y refresh token (Redis)

`POST /login` crea la sesión **en el servidor** y devuelve:

```json
"token": {"access_token": "eyJhbGciOi...", "refresh_token": "…", "token_type": "Bearer", "algoritmo": "HS256", "expires_in": 1200}
```

| Pieza | Dónde vive | Vida |
|---|---|---|
| JWT de acceso (HS256, `JWT_SECRET_KEY`) | en el cliente | 20 min (`ACCESS_TOKEN_MINUTES`) |
| Sesión `session:<sid>` | Redis | 60 min, se renueva con cada refresh (`SESSION_TTL_MINUTES`) |
| Refresh token | cliente; en Redis solo su huella `refresh:<sha256>` | igual que la sesión, **un solo uso** |

- El JWT lleva `sub`, `user_id`, `email`, `role_id`, `rol`, `sid`, `jti`, `typ`, `iss`, `iat` y `exp`. Lo firma **solo** este servicio; los otros 5 lo validan con la misma clave.
- **Renovar:** `POST /token/refresh {"refresh_token": …}` consume el refresh con `GETDEL`, emite un JWT y un refresh nuevos y revoca el `jti` anterior. Reusar un refresh responde 401 `ERR_REFRESH_INVALIDO`.
- **Logout:** revoca el `jti` (`jwt:revoked:<jti>`, TTL = vida restante) y borra la sesión y el refresh. Ese JWT responde 401 `ERR_TOKEN_REVOCADO` en los 6 servicios.
- **Si Redis no responde**, login, refresh, sesión y logout responden **503**: nunca se emite ni se acepta un token sin poder registrarlo o comprobarlo.
- Sin `JWT_SECRET_KEY` (mínimo 32 bytes) o sin `REDIS_URL`, el servicio no arranca. En los logs el token aparece solo como `[JWT PRESENTE eyJhbGciOi…abcd (N caracteres)]`.

**Cookie de sesión:** se llama `libreria_login_session` y no `session` (el nombre por defecto de Flask). Las cookies no distinguen puerto: si otro servicio Flask en el mismo host usara el nombre por defecto, ambas cookies se sobrescribirían.

Extras: `GET /docs` (Swagger UI) y `GET /openapi.json` (especificación OpenAPI 3.0).

### Formato de respuesta

Todos los endpoints responden **XML por defecto**. Para recibir JSON hay que pedirlo explícitamente:

```bash
curl -X POST http://HOST:5000/login                 # -> XML
curl -X POST "http://HOST:5000/login?format=xml"    # -> XML
curl -X POST "http://HOST:5000/login?format=json"   # -> JSON
```

### Formato del cuerpo de la petición

El enunciado define el formato de *respuesta*, no el de *petición*. Se aceptan los tres que podría usar un evaluador, para que funcione con curl, Swagger UI, Postman o un formulario HTML sin configuración extra:

```bash
# JSON
curl -X POST http://HOST:5000/login -H 'Content-Type: application/json' \
     -d '{"email":"ana.torres@correo.test","password":"Password123"}'

# Formulario
curl -X POST http://HOST:5000/login -d 'email=ana.torres@correo.test&password=Password123'

# XML
curl -X POST http://HOST:5000/login -H 'Content-Type: application/xml' \
     -d '<login><email>ana.torres@correo.test</email><password>Password123</password></login>'
```

---

## Arquitectura

```
services/login/
├── app.py                      # Flask: rutas y orquestación de los 5 endpoints
├── requirements.txt
├── .env.example
├── config/
│   └── config.py               # Configuración desde variables de entorno
├── db/
│   └── database.py             # Persistencia con Psycopg 3 + pool de conexiones
├── auth/
│   ├── jwt_tokens.py           # Emisión del JWT de acceso y del refresh token
│   ├── sesiones.py             # Sesiones y refresh tokens en Redis
│   ├── passwords.py            # Hash y verificación bcrypt
│   └── email_validator.py      # Validación de correo (sintaxis + MX)
└── api/
    ├── responses.py            # Serialización bilingüe XML/JSON
    └── openapi.py              # Especificación OpenAPI + Swagger UI
```

Cada capa tiene una sola responsabilidad: `db/` no sabe de HTTP, `api/` no sabe de SQL, y `app.py` solo coordina.

---

## Decisiones de diseño

### La contraseña se guarda una sola vez, en `usuarios`

No existe tabla de contraseñas ni columna duplicada: `password_hash` pertenece a la cuenta de usuario y vive en `usuarios`, junto al resto de sus atributos. Una tabla aparte solo para contraseñas no aportaría normalización (la relación sería 1:1 obligatoria) y añadiría un JOIN a cada login.

### bcrypt, por interoperabilidad y no por costumbre

La tabla `usuarios` ya contenía 31 usuarios con hashes generados por dos fuentes distintas: el monolito Node.js (`bcrypt`, costo 10, prefijo `$2b$`) y el seed de PostgreSQL (`pgcrypto`, prefijo `$2a$`). La librería `bcrypt` de Python verifica ambos formatos.

El resultado es interoperabilidad real en las dos direcciones: los usuarios que ya existían pueden autenticarse en este microservicio, y los que se registran aquí pueden entrar al monolito. Haber elegido otro algoritmo (pbkdf2, argon2) habría partido el sistema en dos islas de usuarios incompatibles.

### Sesión del lado del servidor, en Redis

La cookie solo lleva un identificador aleatorio (`sid`); los datos de la sesión viven en `session:<sid>` en Redis. Así `/logout` invalida la sesión de verdad (antes, con la cookie firmada de Flask, no había estado en el servidor que borrar) y la sesión caduca sola por TTL, sin tareas de limpieza en PostgreSQL.

### CORS con credenciales: por qué no se usa `*`

Cuando una petición viaja con cookies, el navegador **rechaza** `Access-Control-Allow-Origin: *`. Hay que responder el origen exacto y añadir `Access-Control-Allow-Credentials: true`. Por eso el microservicio mantiene una lista blanca (`CORS_ORIGINS`) en vez de abrir a todo el mundo.

### Validación de correo en tres niveles

"Validar el correo" son en realidad tres preguntas distintas, con métodos y niveles de certeza diferentes:

| Pregunta | Método | Certeza |
|---|---|---|
| ¿Está bien escrito? | Expresión regular (RFC 5322 simplificado) | Solo descarta errores de tecleo |
| ¿El dominio puede recibir correo? | Consulta DNS del registro **MX** | Alta: sin MX, ninguna dirección del dominio existe |
| ¿El buzón existe y es de quien se registra? | **Token enviado por correo y devuelto a `/verify`** | La única prueba real |

Los dos primeros ocurren en `/register` y solo sirven para **rechazar** direcciones imposibles. `noexiste@gmail.com` los pasa ambos sin problema, por eso **`/register` deja `email_verificado = false`**.

El flag solo cambia a `true` desde `/verify`, cuando alguien devuelve el token que se envió a ese buzón. El token se guarda **hasheado (SHA-256)** — igual que las contraseñas — y es de un solo uso (`usado_en`), por lo que reintentarlo devuelve `409`.

**Por qué no se sondea el buzón por SMTP (`RCPT TO`):** GCP bloquea el puerto 25 saliente, los proveedores grandes responden *accept-all* o aplican greylisting (resultado no confiable), y sondear buzones ajenos de forma masiva es un patrón que las listas de reputación marcan como spam.

### Envío de correo: hasta dónde llega

El microservicio entrega el mensaje a **Postfix** en `localhost:25`. Postfix lo acepta, le asigna un Queue ID y lo encola — verificable con `mailq` y `postcat -q <id>`.

La entrega **externa** falla porque Google Cloud bloquea el puerto 25 saliente en las VMs de Compute Engine:

```
postfix/smtp: connect to gmail-smtp-in.l.google.com[108.177.121.26]:25: Connection timed out
```

Postfix resuelve el MX correctamente; lo que falla es la salida de red. Para entrega externa real hay que configurar un relay autenticado por el puerto 587 (SendGrid, Mailgun, Gmail SMTP) — es un cambio de configuración del MTA, no del microservicio: el código ya habla SMTP y no le importa quién esté del otro lado.

Si el envío falla, **el registro no se cancela**: el usuario queda creado y la respuesta lo indica (`"enviado": false` con el detalle). Hacer fallar el alta por un problema de correo convertiría al MTA en punto único de falla.

### Seguridad adicional

- **Sin enumeración de usuarios:** `/login` devuelve el mismo mensaje y el mismo código (401) tanto si el correo no existe como si la contraseña es incorrecta. Distinguirlos permitiría descubrir qué correos están registrados.
- **Mínimo privilegio:** el microservicio se conecta como `login_app_user`, con permisos `SELECT, INSERT, UPDATE` únicamente sobre `usuarios`. No es `postgres` ni reutiliza `library_user` (el rol del monolito), y no puede borrar usuarios ni tocar el catálogo.
- **Registro público sin escalada:** `/register` fuerza `rol = 'cliente'`. El esquema tiene un índice único parcial (`ux_un_solo_administrador`) que permite un único administrador en todo el sistema.
- **`password_hash` nunca sale del servicio:** las respuestas usan una proyección explícita que lo excluye.

---

## Limitaciones conocidas

- **HTTPS por nginx.** El servicio habla HTTP; en la instancia se publica detrás de nginx con certificado autofirmado. Con HTTPS activo, `SESSION_COOKIE_SECURE=true`.
- **Sin límite de intentos.** No hay *rate limiting* en `/login`, por lo que no está protegido contra fuerza bruta.
- **Servidor de desarrollo.** Se ejecuta con el servidor integrado de Flask, no con un WSGI de producción (gunicorn/uWSGI).

---

## Instalación y ejecución

### 1. Crear el rol de base de datos (una sola vez)

La contraseña se genera al momento y no se versiona:

```sql
CREATE ROLE login_app_user WITH LOGIN PASSWORD '<password-generada>';
```

### 2. Aplicar la migración

```bash
psql -d library_db -f db/07_auth_microservice.sql
```

Agrega `apellido_paterno`, `apellido_materno` y `email_verificado` a `usuarios`, separa el nombre completo de los registros históricos y otorga los permisos mínimos al rol. Es idempotente y no rompe al monolito.

### 3. Configurar y ejecutar

```bash
cp .env.example .env     # y rellenar JWT_SECRET_KEY, REDIS_URL y DB_PASSWORD
python3 -m venv venv
./venv/bin/pip install -r requirements.txt     # incluye -e ../common
./venv/bin/python app.py
./venv/bin/python -m pytest -q                 # 13 pruebas (fakeredis)
```

Generar un `JWT_SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Verificar

```bash
curl http://localhost:5000/health
```

---

## Despliegue en la instancia GCP

Corre como servicio systemd (`library-login.service`) bajo el usuario de sistema `loginapp`:

```bash
sudo systemctl status library-login
sudo journalctl -u library-login -f
```

El puerto 5000 debe estar abierto en **ambos** firewalls:

```bash
# Firewall de red de GCP
gcloud compute firewall-rules create allow-login-5000 \
  --network=default --direction=INGRESS --action=ALLOW \
  --rules=tcp:5000 --source-ranges=0.0.0.0/0

# firewalld de la instancia (CentOS Stream)
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --reload
```
