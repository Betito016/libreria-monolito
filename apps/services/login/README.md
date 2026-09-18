# Microservicio de Autenticación

Microservicio **independiente** de autenticación y gestión básica de usuarios para la plataforma de librería en línea.

**Stack:** Python · Flask · Psycopg 3 · PostgreSQL
**Puerto:** 5000
**Base de datos:** `library_db` (la misma del monolito Node.js — no se crea una base paralela)

---

## Endpoints

| Método | Endpoint    | Función                                          |
|--------|-------------|--------------------------------------------------|
| POST   | `/register` | Registrar un nuevo usuario                        |
| POST   | `/login`    | Autenticar al usuario e iniciar sesión            |
| POST   | `/logout`   | Cerrar la sesión                                  |
| GET    | `/session`  | Consultar si existe una sesión autenticada        |
| GET    | `/health`   | Verificar el estado del microservicio y PostgreSQL |

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
apps/services/login/
├── app.py                      # Flask: rutas y orquestación de los 5 endpoints
├── requirements.txt
├── .env.example
├── config/
│   └── config.py               # Configuración desde variables de entorno
├── db/
│   └── database.py             # Persistencia con Psycopg 3 + pool de conexiones
├── auth/
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

### Validación de correo: sintaxis + registro MX

El enunciado pide validar que el correo sea real y sugiere Postfix. La validación ocurre en dos niveles, sin enviar correo:

1. **Sintaxis** (RFC 5322 simplificado).
2. **Registro MX del dominio** vía DNS: comprueba que el dominio tenga servidores de correo declarados. Un dominio sin MX no puede recibir correo, así que la dirección no puede existir.

**Por qué no se sondea el buzón por SMTP:** Google Cloud bloquea el puerto 25 saliente en las VMs de Compute Engine por política de plataforma, así que una conexión SMTP directa no sale de la instancia. Además, los proveedores grandes responden *accept-all* o aplican greylisting, de modo que el resultado no sería confiable, y sondear buzones ajenos de forma masiva es un patrón que las listas de reputación marcan como spam.

La verificación definitiva de **propiedad** del buzón requiere enviar un correo con token de confirmación, lo que implica un relay SMTP autenticado (puerto 587) y un endpoint `/verify` que el enunciado no contempla. Queda como trabajo futuro.

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
cp .env.example .env     # y rellenar SECRET_KEY y DB_PASSWORD
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
