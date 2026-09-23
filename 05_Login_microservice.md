# 05 - Microservicio de Autenticación

Microservicio independiente de autenticación y gestión básica de usuarios: **Python + Flask + Psycopg 3 + PostgreSQL**, sobre la base existente del proyecto (`library_db`), con respuestas en **XML y JSON**.

Código: [`services/login/`](services/login/)
Migraciones: [`db/07_auth_microservice.sql`](db/07_auth_microservice.sql) · [`db/08_email_verification.sql`](db/08_email_verification.sql)

---

## Endpoints

| Método | Endpoint | Función |
|---|---|---|
| POST | `/register` | Registrar un nuevo usuario y enviar correo de verificación |
| POST | `/login` | Autenticar al usuario e iniciar sesión |
| POST | `/logout` | Cerrar la sesión |
| GET | `/session` | Consultar si existe una sesión autenticada |
| GET | `/health` | Verificar el estado del microservicio y PostgreSQL |
| GET/POST | `/verify` | Canjear el token del correo y marcar el correo como verificado |

XML por defecto; JSON con `?format=json`.

---

## Evidencia

Todas las pruebas se ejecutaron con `curl` contra el microservicio desplegado en la instancia GCP (puerto 5000).

### 1. `/health` — comprueba PostgreSQL de verdad

```bash
curl -s "http://HOST:5000/health?format=json"
```
```json
{"estado": "ok", "microservicio": "login",
 "postgresql": {"base_datos": "library_db", "conectado": true,
                "version": "PostgreSQL 16.14 on x86_64-redhat-linux-gnu"}}
```

El mismo endpoint sin `?format` devuelve XML:

```xml
<health>
  <estado>ok</estado>
  <microservicio>login</microservicio>
  <postgresql>
    <conectado>true</conectado>
    <base_datos>library_db</base_datos>
    <version>PostgreSQL 16.14 on x86_64-redhat-linux-gnu</version>
  </postgresql>
</health>
```

Con PostgreSQL detenido responde `503` y `"estado": "degradado"`, no un `200` fijo.

### 2. `/register` — valida el dominio y envía el correo

```bash
curl -s -X POST "http://HOST:5000/register?format=json" \
  -H 'Content-Type: application/json' \
  -d '{"nombre":"Demo","apellido_paterno":"Flag",
       "email":"demo.flag@gmail.com","password":"Password123"}'
```
```json
{
  "estado": "exito",
  "mensaje": "Usuario registrado. Revisa tu correo para verificar la cuenta.",
  "validacion_dominio": "MX encontrado: alt1.gmail-smtp-in.l.google.com",
  "correo_verificacion": {
    "enviado": true,
    "detalle": "mensaje aceptado por el MTA en localhost:25",
    "destinatario": "demo.flag@gmail.com",
    "expira_en": "2026-09-19 21:44:32.775237+00:00"
  },
  "usuario": {
    "id": "7e2081cb-23c7-4834-916f-40bf3b53176d",
    "nombre": "Demo", "apellido_paterno": "Flag", "apellido_materno": null,
    "email": "demo.flag@gmail.com", "rol": "cliente",
    "email_verificado": false
  }
}
```

**`email_verificado` es `false`**, aunque el dominio sea válido y el correo se haya enviado. Ese es el punto: el registro no puede afirmar que el buzón fue confirmado.

### 3. El correo existe de verdad — cola de Postfix

```bash
sudo mailq
```
```
-Queue ID-  --Size-- ----Arrival Time---- -Sender/Recipient-------
E15B730B3143*    1058 Fri Sep 18 21:44:32  no-reply@libreria.local
                                         demo.flag@gmail.com
```

Contenido real del mensaje entregado al MTA (`sudo postcat -q E15B730B3143`):

```
Subject: Verifica tu correo - Libreria en Linea
From: no-reply@libreria.local
To: demo.flag@gmail.com
Message-Id: <20260918214432.E15B730B3143@integracion.localdomain>
Date: Fri, 18 Sep 2026 21:44:32 +0000 (UTC)

Hola Demo,

Para completar tu registro necesitamos confirmar que este correo te pertenece.

Tu codigo de verificacion es:

    _9v45jHFd7HbgKPU7f0bfW0lVOdDRP7lMDeWKJFXnpI

Tambien puedes verificarlo directamente en:

    http://136.119.31.253:5000/verify?token=_9v45jHFd7HbgKPU7f0bfW0lVOdDRP7lMDeWKJFXnpI

El codigo vence en 24 horas.
```

### 4. Estado en la base **antes** de verificar

```sql
SELECT u.email, u.email_verificado, v.enviado, (v.usado_en IS NOT NULL) AS token_usado
FROM usuarios u JOIN verificaciones_email v ON v.usuario_id = u.id
WHERE u.email = 'demo.flag@gmail.com';
```
```
        email        | email_verificado | enviado | token_usado
---------------------+------------------+---------+-------------
 demo.flag@gmail.com | f                | t       | f
```

Correo enviado (`enviado = t`), pero **no verificado** y token **sin usar**.

### 5. `/verify` — el canje del token

```bash
curl -s "http://HOST:5000/verify?token=_9v45jHFd7HbgKPU7f0bfW0lVOdDRP7lMDeWKJFXnpI&format=json"
```
```json
{"estado": "exito", "mensaje": "Correo verificado correctamente.",
 "usuario": {"email": "demo.flag@gmail.com", "email_verificado": true,
             "nombre": "Demo", "apellido_paterno": "Flag", "rol": "cliente"}}
```

### 6. Estado en la base **después** — el flag cambió

```
        email        | email_verificado | enviado | token_usado |           usado_en
---------------------+------------------+---------+-------------+-------------------------------
 demo.flag@gmail.com | t                | t       | t           | 2026-09-18 21:45:31.877519+00
```

### 7. Casos de error del token

```bash
# Reusar el mismo token
curl -s "http://HOST:5000/verify?token=<usado>&format=json"     # HTTP 409
{"estado":"error","codigo_error":"ERR_TOKEN_YA_USADO",
 "mensaje":"Este token ya fue utilizado. El correo ya estaba verificado."}

# Token inventado
curl -s "http://HOST:5000/verify?token=token-falso-123&format=json"  # HTTP 400
{"estado":"error","codigo_error":"ERR_TOKEN_INVALIDO",
 "mensaje":"El token de verificacion no es valido."}
```

### 8. Ciclo de sesión

```bash
# Login (guarda la cookie de sesión)
curl -s -c cookies.txt -X POST "http://HOST:5000/login?format=json" \
  -H 'Content-Type: application/json' \
  -d '{"email":"ana.torres@correo.test","password":"Password123"}'
```
```json
{"estado":"exito","mensaje":"Bienvenido, Ana.",
 "usuario":{"nombre":"Ana","apellido_paterno":"Torres","rol":"cliente"}}
```
```bash
curl -s -b cookies.txt "http://HOST:5000/session?format=json"
# {"autenticado": true, "usuario": {...}}

curl -s -b cookies.txt -c cookies.txt -X POST "http://HOST:5000/logout?format=json"
# {"estado":"exito","mensaje":"Sesion cerrada.","sesion_previa":true}

curl -s -b cookies.txt "http://HOST:5000/session?format=json"
# {"autenticado": false, "mensaje": "No hay una sesion activa."}
```

### 9. Errores de autenticación

| Caso | HTTP | `codigo_error` |
|---|---|---|
| Correo duplicado | 409 | `ERR_EMAIL_DUPLICADO` |
| Dominio sin registro MX | 400 | `ERR_EMAIL_INVALIDO` |
| Contraseña incorrecta | 401 | `ERR_CREDENCIALES_INVALIDAS` |
| Correo no registrado | 401 | `ERR_CREDENCIALES_INVALIDAS` *(mismo mensaje)* |
| Campos faltantes | 400 | `ERR_CAMPOS_OBLIGATORIOS` |
| Contraseña < 8 caracteres | 400 | `ERR_PASSWORD_DEBIL` |

### 10. El cuerpo de la petición acepta tres formatos

```bash
# JSON
curl -X POST "http://HOST:5000/login?format=json" -H 'Content-Type: application/json' \
     -d '{"email":"ana.torres@correo.test","password":"Password123"}'

# Formulario
curl -X POST "http://HOST:5000/login?format=json" \
     -d 'email=luis.hernandez@correo.test&password=Password123'

# XML
curl -X POST "http://HOST:5000/login?format=json" -H 'Content-Type: application/xml' \
     -d '<login><email>maria.lopez@correo.test</email><password>Password123</password></login>'
```

Los tres devuelven `{"estado": "exito", ...}`.

---

## Reflexión

### Qué significa realmente "validar que el correo existe"

Esta fue la parte del ejercicio donde la primera solución estaba mal, y vale la pena explicar por qué. "Validar el correo" suena a una sola cosa, pero en realidad son tres preguntas distintas, cada una con un método y un nivel de certeza diferente:

**1. ¿Está bien escrito?** Se responde con una expresión regular. Es instantáneo y gratis, pero solo descarta errores de tecleo. `noexiste@gmail.com` pasa esta prueba sin problema.

**2. ¿El dominio puede recibir correo?** Se responde consultando los registros **MX** del dominio por DNS. Si `gmail.com` declara `alt1.gmail-smtp-in.l.google.com`, sabemos que hay servidores de correo detrás. Si un dominio no tiene MX, o no existe, ninguna dirección de ese dominio puede recibir nada — y ahí sí se puede rechazar con certeza. Eso es lo que hace el microservicio al registrar, y es lo que aparece como `"validacion_dominio": "MX encontrado: ..."` en la respuesta JSON.

**3. ¿El buzón existe y le pertenece a quien se registra?** Ninguna de las dos anteriores lo responde. `noexiste@gmail.com` tiene sintaxis válida y un dominio con MX impecable, y aun así no existe. Y aunque existiera, nada impide que yo me registre con el correo de otra persona.

La primera versión de este microservicio ponía `email_verificado = TRUE` al terminar el paso 2. Era un error de diseño: la base afirmaba algo que nunca se comprobó. Un flag que dice "verificado" cuando lo único que se validó fue el DNS del dominio es peor que no tener el flag, porque da una falsa sensación de garantía a cualquier otro sistema que lo consulte.

**La única prueba real de propiedad es el ida y vuelta:** generar un token aleatorio, enviarlo por correo a esa dirección, y esperar a que alguien con acceso a ese buzón lo devuelva. Si el token regresa, el buzón existe *y* la persona que se registró tiene acceso a él. Por eso `email_verificado` solo cambia a `true` desde `/verify`, nunca desde `/register`. La migración `08` incluso revierte el flag de los usuarios que habían quedado marcados con la lógica anterior: es preferible decir "no sé" a afirmar algo falso.

### Por qué el token se guarda hasheado

El token viaja en claro por correo, pero en la base se guarda solo su **SHA-256**. La razón es la misma que con las contraseñas: si alguien consiguiera leer la tabla `verificaciones_email`, con los tokens en claro podría verificar cuentas ajenas antes que sus dueños. Con solo el hash, las solicitudes pendientes son inútiles para un atacante. El token en claro existe únicamente dentro del correo enviado.

Cada token además se marca con `usado_en` al canjearse, lo que lo vuelve de un solo uso — por eso reintentar con el mismo token devuelve `409` y no vuelve a "verificar" nada.

### Por qué una tabla aparte para los tokens, pero no para las contraseñas

Parece contradictorio con la instrucción de no crear tablas de más, pero la diferencia es real. `password_hash` es un **atributo** de la cuenta: hay exactamente uno, siempre, y no tiene sentido fuera del usuario. Sacarlo a otra tabla sería una relación 1:1 obligatoria — normalización de adorno que solo agrega un JOIN a cada login.

Un token de verificación es un **evento** con ciclo de vida propio: se emite, vence, se usa una sola vez, y un mismo usuario puede pedir varios a lo largo del tiempo. Eso es una relación 1:N genuina. Guardarlo como columna en `usuarios` obligaría a sobrescribir el token anterior y perdería el rastro de cuándo se emitió y cuándo se canjeó.

La pregunta útil para decidir no es "¿cuántas tablas quedan?", sino "¿esto es un atributo de la entidad o una cosa con vida propia?".

### Hasta dónde llega el envío y dónde se topa con la plataforma

El microservicio entrega el mensaje a **Postfix** en `localhost:25`, y Postfix lo acepta, le asigna un Queue ID y lo encola — eso es comprobable con `mailq` y `postcat`, y es la prueba de que el envío ocurre de verdad, no es una simulación.

La entrega hacia afuera es otra historia. Google Cloud **bloquea el puerto 25 saliente** en las VMs de Compute Engine como política anti-spam de la plataforma. En el log se ve exactamente eso:

```
postfix/smtp: connect to gmail-smtp-in.l.google.com[108.177.121.26]:25: Connection timed out
postfix/smtp: connect to gmail-smtp-in.l.google.com[2607:f8b0:4001:c19::1a]:25: Network is unreachable
```

Postfix resuelve el MX correctamente y hace todo bien; lo que falla es la salida de la red. Para entrega externa real habría que relevar el correo por un proveedor autenticado en el puerto 587 (SendGrid, Mailgun, Gmail SMTP), que es un cambio de configuración de Postfix, no del microservicio: el código ya envía por SMTP y no le importa quién esté del otro lado.

Vale la pena señalarlo porque es la clase de restricción que no aparece en ningún requerimiento y solo se descubre al desplegar. El diseño correcto fue no acoplar el microservicio a un método de entrega: habla SMTP con un MTA local, y cómo ese MTA entregue es un problema de infraestructura.

### Por qué el registro no falla si el correo no se envía

Si Postfix estuviera caído, el usuario igual queda registrado y la respuesta lo dice explícitamente (`"enviado": false` con el detalle del error). Hacer fallar todo el registro por un problema de correo convertiría al MTA en un punto único de falla para dar de alta usuarios. El token queda guardado y se puede reintentar el envío; lo que no se puede es perder el registro del usuario por algo que no depende de él.

### Sobre los formatos y la sesión

El parámetro `?format=` decide únicamente cómo se **serializa** la respuesta; el contenido es el mismo diccionario. Eso permitió notar un detalle que en JSON no existe: `str(True)` en Python produce `"True"`, pero `xs:boolean` exige `"true"` en minúsculas — un consumidor XML estricto habría fallado al parsear `email_verificado`. En JSON el booleano es un tipo nativo y el problema no aparece. Mismo dato, dos representaciones, dos conjuntos de reglas.

En cuanto a CORS: mientras el microservicio SOAP pudo abrirse con `Access-Control-Allow-Origin: *`, aquí eso es inválido. En cuanto la petición viaja con cookie de sesión, el navegador **rechaza** el comodín y exige un origen explícito más `Access-Control-Allow-Credentials: true`. Es deliberado del estándar: `*` significa "cualquier sitio puede leer esta respuesta", y combinarlo con credenciales permitiría que cualquier página hiciera peticiones autenticadas en nombre del usuario.

### Lo que queda pendiente

- **HTTPS.** Todo corre en HTTP plano: las contraseñas y los tokens viajan sin cifrar, y la cookie de sesión no puede llevar la bandera `Secure`. Para un ejercicio es aceptable; para producción es inadmisible en un endpoint de login.
- **Relay SMTP autenticado** por el puerto 587, para que los correos salgan de verdad a dominios externos.
- **Rate limiting** en `/login` y en `/register`, hoy ausente: nada impide intentar contraseñas por fuerza bruta ni generar correos de verificación en masa.
- **Reenvío de token** (`/resend-verification`) para el caso en que el correo se pierda o el token venza.

> **Nota sobre la dirección del servicio.** Los ejemplos de evidencia de arriba se capturaron cuando la instancia usaba una IP efímera, que rotó tres veces y dejó enlaces de verificación apuntando a direcciones muertas. La instancia ahora tiene una **IP estática reservada** (`integracion-ip`, `34.135.84.31`), así que `PUBLIC_BASE_URL` ya no se invalida al reiniciar. Las capturas se conservan tal como se obtuvieron, con la IP que estaba vigente en ese momento.
