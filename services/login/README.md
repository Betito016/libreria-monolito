# Microservicio de Autenticación

Microservicio **independiente** de autenticación y gestión básica de usuarios para la plataforma de librería en línea.

**Stack:** Python · Flask · Psycopg 3 · PostgreSQL
**Puerto:** 5000
**Base de datos:** `library_db` (la misma del monolito Node.js — no se crea una base paralela)

---

## Endpoints

| Método   | Endpoint    | Función                                          |
|----------|-------------|--------------------------------------------------|
| POST     | `/register` | Registrar un nuevo usuario y enviar correo de verificación |
| POST     | `/login`    | Autenticar al usuario e iniciar sesión            |
| POST     | `/logout`   | Cerrar la sesión                                  |
| GET      | `/session`  | Consultar la sesión, el perfil y cuánto le queda  |
| POST     | `/session/extend` | Prorrogar la sesión vigente                 |
| PATCH    | `/profile`  | Modificar nombre, apellidos, correo o contraseña  |
| GET      | `/health`   | Verificar el estado del microservicio y PostgreSQL |
| GET/POST | `/verify`   | Canjear el token del correo y marcar el correo como verificado |

**Cuentas que no pueden autenticarse:** `/login` responde **403** `ERR_CORREO_NO_VERIFICADO` si el correo no se ha verificado, y `ERR_CUENTA_INACTIVA` si la cuenta está desactivada. Ambos se informan solo después de validar la contraseña, para no revelar el estado de cuentas ajenas.

**Vencimiento de la sesión:** es absoluto (30 minutos por defecto, `SESSION_LIFETIME_MINUTES`). Flask renueva la cookie en cada petición por defecto, lo que haría que la sesión no expirara nunca mientras el cliente consulte `/session`; por eso se desactiva `SESSION_REFRESH_EACH_REQUEST` y la sesión solo se prorroga con `POST /session/extend`. `/login`, `/session` y `/session/extend` devuelven `sesion.segundos_restantes` para que el cliente pueda advertir antes de que expire.

**Perfil:** `PATCH /profile` modifica solo los campos enviados. Cambiar correo o contraseña exige `password_actual`; un correo nuevo queda sin verificar y se envía otro token. `rol`, `activo` e `id` se rechazan con 400 `ERR_CAMPOS_NO_PERMITIDOS`: un usuario no puede ascenderse a administrador editando su perfil.

**JWT:** además de la cookie, `POST /login` y `POST /session/extend` devuelven un bloque `token`:

```json
"token": {"access_token": "eyJhbGciOi...", "token_type": "Bearer", "algoritmo": "HS256", "expires_in": 1800}
```

El microservicio de libros exige ese token en sus escrituras como `Authorization: Bearer <access_token>`. Lo firma **solo** este servicio (`auth/jwt_tokens.py`), con `JWT_SECRET` y `JWT_ALGORITHM` (HS256). Libros lo valida con la misma clave, así que ambos `.env` deben tener el mismo valor. El token lleva `sub`, `email`, `rol`, `iss`, `iat` y `exp`, y vence al mismo tiempo que la sesión. Sin `JWT_SECRET` (mínimo 32 bytes) el servicio no arranca. En los logs el token aparece solo como `[JWT PRESENTE eyJhbGciOi…abcd (N caracteres)]`.

**Qué es público:** `/login`, `/register`, `/verify`, `/health` y `/logout` no exigen autenticación: sirven justamente para obtenerla, recuperarla o cerrarla. `/session` es una consulta que siempre responde 200. `/session/extend` y `/profile` siguen protegidos con la cookie de sesión.

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
│   ├── jwt_tokens.py           # Emisión del JWT de acceso
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

### Sesión del lado de Flask

`/login` crea una sesión mediante la cookie firmada nativa de Flask. El `SECRET_KEY` debe ser **fijo y persistente**: si cambia entre reinicios, todas las sesiones activas quedan invalidadas.

`/logout` limpia la sesión del lado del cliente. Con cookies firmadas no hay estado en el servidor que invalidar; una invalidación real del lado del servidor requeriría `Flask-Session` con backend (Redis/PostgreSQL), que es trabajo futuro documentado.

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

- **Sin HTTPS.** El despliegue actual es HTTP plano, por lo que la cookie de sesión no puede llevar la bandera `Secure` (el navegador la descartaría). En un entorno real esto es obligatorio antes de exponer un endpoint de login.
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
cp .env.example .env     # y rellenar SECRET_KEY, JWT_SECRET y DB_PASSWORD
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python app.py
```

Generar un `SECRET_KEY`:

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
