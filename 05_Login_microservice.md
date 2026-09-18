# 05 - Microservicio de Autenticación

Microservicio independiente de autenticación y gestión básica de usuarios, desarrollado con **Python + Flask + Psycopg 3 + PostgreSQL**, integrado a la base de datos existente del proyecto (`library_db`) y con respuestas en **XML y JSON**.

Código: [`apps/services/login/`](apps/services/login/) · Migración: [`db/07_auth_microservice.sql`](db/07_auth_microservice.sql)

---

## Endpoints implementados

| Método | Endpoint    | Función                                          | Verificado |
|--------|-------------|--------------------------------------------------|------------|
| POST   | `/register` | Registrar un nuevo usuario                        | ✔ |
| POST   | `/login`    | Autenticar al usuario e iniciar sesión            | ✔ |
| POST   | `/logout`   | Cerrar la sesión                                  | ✔ |
| GET    | `/session`  | Consultar si existe una sesión autenticada        | ✔ |
| GET    | `/health`   | Verificar el estado del microservicio y PostgreSQL | ✔ |

Todos responden **XML por defecto** y JSON con `?format=json`.

---

## Resultados (evidencia)

**Swagger UI documentando los cinco endpoints en XML y JSON:**

![Swagger del microservicio de login](evidencia/login-swagger.png)

**Pruebas de los endpoints (registro, login, sesión, logout):**

![Pruebas de endpoints](evidencia/login-endpoints.png)

**Migración aplicada y datos en PostgreSQL:**

![Base de datos migrada](evidencia/login-base-datos.png)

### Salidas verificadas

`POST /register` — XML por defecto, con validación de correo por registro MX:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<registro>
  <estado>exito</estado>
  <mensaje>Usuario registrado correctamente.</mensaje>
  <validacion_email>MX encontrado: alt1.gmail-smtp-in.l.google.com</validacion_email>
  <usuario>
    <id>8411ac4c-9ad3-4f89-b6fc-34cee4550d0f</id>
    <nombre>Humberto</nombre>
    <apellido_paterno>Vargas</apellido_paterno>
    <apellido_materno>Salinas</apellido_materno>
    <email>humberto.prueba@gmail.com</email>
    <rol>cliente</rol>
    <email_verificado>true</email_verificado>
  </usuario>
</registro>
```

`GET /session?format=json` con la cookie de sesión activa:

```json
{"autenticado": true, "usuario": {"nombre": "Humberto", "apellido_paterno": "Vargas",
 "apellido_materno": "Salinas", "email": "humberto.prueba@gmail.com", "rol": "cliente"}}
```

`GET /health` comprobando PostgreSQL de verdad (no un "OK" fijo):

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

### Casos de error validados

| Caso                                   | Código | Resultado |
|----------------------------------------|--------|-----------|
| Correo duplicado                        | 409    | `ERR_EMAIL_DUPLICADO` |
| Dominio de correo inexistente (sin MX)  | 400    | `ERR_EMAIL_INVALIDO` |
| Contraseña incorrecta                   | 401    | `ERR_CREDENCIALES_INVALIDAS` |
| Correo no registrado                    | 401    | Mismo mensaje que contraseña incorrecta |
| Campos obligatorios faltantes           | 400    | `ERR_CAMPOS_OBLIGATORIOS` |
| PostgreSQL caído (`/health`)            | 503    | `estado: degradado` |

---

## Reflexión

### Por qué el microservicio usa la base existente en vez de una propia

La tentación al construir un microservicio "independiente" es darle también su propia base de datos, que es lo que recomienda el patrón *database per service*. Aquí habría sido un error: la plataforma ya tenía 31 usuarios reales en `library_db.usuarios`, gestionados por el monolito Node.js. Crear un catálogo de usuarios paralelo habría producido dos verdades sobre la misma persona — alguien registrado en el monolito no existiría para el microservicio, y viceversa.

"Independiente" aquí significa *desplegable y ejecutable por separado* (su propio proceso, puerto, rol de base de datos y ciclo de vida), no *aislado de los datos del negocio*. El microservicio corre en el puerto 5000 con su propio `systemd` y su propio rol de PostgreSQL, pero lee y escribe la misma tabla que el monolito.

### La decisión que más impacto tuvo: el algoritmo de hash

Al revisar la base antes de escribir código, los 31 usuarios existentes tenían hashes de dos orígenes distintos: `$2b$` del `bcrypt` de Node y `$2a$` del `pgcrypto` de PostgreSQL. Si el microservicio hubiera hasheado con cualquier otra cosa (pbkdf2, argon2, lo que Flask trae por defecto), esos 31 usuarios simplemente no habrían podido iniciar sesión, y los nuevos tampoco habrían podido entrar al monolito.

Usar `bcrypt` de Python — que verifica ambos prefijos — hizo que la integración funcionara en las dos direcciones desde el primer intento. Se verificó explícitamente: usuarios preexistentes como `ana.torres@correo.test` autentican correctamente en el microservicio nuevo.

Esta es justo la diferencia entre *escribir un servicio* e *integrar aplicaciones*: el requisito real no estaba en el enunciado, estaba en los datos que ya existían.

### Por qué la migración tenía que ser aditiva

El enunciado pide `nombre`, `apellido paterno` y `apellido materno` por separado, pero la tabla guardaba el nombre completo en una sola columna. La migración agrega las columnas nuevas como **NULLABLE** a propósito: el monolito Node inserta únicamente `(nombre, email, password_hash, rol)`, así que declararlas `NOT NULL` habría roto su registro de usuarios de inmediato.

La obligatoriedad de esos campos se valida en el microservicio, no en el esquema. Es la regla general al modificar una base compartida: el esquema debe aceptar a todos los clientes existentes, y cada servicio impone sus propias reglas de negocio encima. El `UPDATE` que separó los 31 nombres históricos (`'Ana Torres'` → `'Ana'` + `'Torres'`) se dejó idempotente para poder re-ejecutarlo sin duplicar efectos, y el apellido materno quedó nulo en vez de inventarse: ese dato no existía.

Se verificó después de migrar que el `INSERT` exacto del monolito sigue funcionando.

### Por qué XML es el formato por defecto

Podría parecer arbitrario en 2026, pero es coherente con el resto de la plataforma: el microservicio anterior nació como SOAP, cuyo contrato natural es XML. Que JSON sea *opt-in* mediante `?format=json` mantiene un criterio uniforme en todo el monorepo y obliga a tratar el formato como una decisión de presentación, no de contenido: los handlers construyen un único diccionario y una sola capa decide cómo serializarlo. Agregar un tercer formato mañana no tocaría ni un endpoint.

Ese diseño también hizo evidente un detalle fácil de pasar por alto: `str(True)` en Python produce `"True"`, pero `xs:boolean` exige `"true"` en minúsculas. Un consumidor XML estricto habría fallado al parsear. En JSON el problema no existe porque el booleano es un tipo nativo — un mismo dato, dos representaciones, dos conjuntos de reglas.

### Por qué CORS no puede ser `*` cuando hay sesión

En el ejercicio anterior bastó con `Access-Control-Allow-Origin: *` para que la app Electron consumiera el microservicio. Aquí eso no funciona: en cuanto la petición viaja con cookies de sesión, el navegador **rechaza** el comodín y exige un origen explícito más `Access-Control-Allow-Credentials: true`. Por eso este servicio mantiene una lista blanca de orígenes en vez de abrir a todos.

Es una restricción deliberada del estándar: `*` significa "cualquier sitio puede leer esta respuesta", y combinarlo con credenciales permitiría que cualquier página web hiciera peticiones autenticadas en nombre del usuario.

### Lo que queda pendiente y por qué importa

El servicio corre sobre **HTTP plano**, lo que significa que las contraseñas viajan sin cifrar y la cookie de sesión no puede llevar la bandera `Secure`. Para un ejercicio de clase es aceptable, pero es exactamente el tipo de hallazgo que invalidaría este diseño en producción. Tampoco hay límite de intentos en `/login`, así que no está protegido contra fuerza bruta.

Ambas cosas están documentadas como limitaciones conocidas en vez de quedar calladas: reconocer el límite de lo construido es parte del diseño, no una omisión.
