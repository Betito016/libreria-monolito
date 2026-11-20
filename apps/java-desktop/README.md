# Librería en Línea — cliente de escritorio en Java (Swing)

Tercera app de escritorio de Library, junto a la de Python (Tkinter) y la de Electron. Habla **solo con el Library API Gateway**: no conoce los puertos de los microservicios, solo la dirección del gateway (por defecto `http://34.135.84.31`).

| Pantalla | Petición al gateway | Acceso |
|---|---|---|
| Semáforos (arriba) | `GET /health` cada 15 s | público — estado agregado por servicio e instancia |
| Iniciar / cerrar sesión | `POST /api/login/login` · `POST /api/login/logout` | el logout revoca el JWT en Redis |
| Catálogo (con búsqueda) | `GET /api/books/books?format=json&titulo=…` | público — nginx reparte entre books :5001 y :6001 |
| Autores | `GET /api/autores/authors?format=json` | público |
| Usuarios (admin) | `GET /api/users/users?format=json` + `Authorization: Bearer` | sin sesión → 401; rol cliente → 403 |
| Registro HTTP | — | cada petición: ruta, código, ms, **instancia que atendió** y **X-Request-ID** |

- **Sin dependencias externas:** `java.net.http.HttpClient` (JDK 11+), Swing y un lector JSON propio (`Json.java`).
- **La red se usa en segundo plano** (`SwingWorker`): la ventana no se congela.
- **Configuración fuera del código:** la dirección del gateway se escribe arriba, en *Guardar y probar*, y se guarda en `%APPDATA%\LibreriaJavaApp\config.properties`. No se guardan contraseñas ni tokens; el JWT vive solo en memoria y en el registro aparece como `Bearer [JWT PRESENTE]`.
- **Cada petición lleva un `X-Request-ID`** (`java-…`), que el gateway respeta, devuelve y escribe en su registro: con ese id se sigue una petición de punta a punta.

## Compilar y ejecutar (Windows 11)

Requiere un JDK 17 o superior (probado con Microsoft OpenJDK 21):

```powershell
winget install Microsoft.OpenJDK.21
cd library\apps\java-desktop
powershell -ExecutionPolicy Bypass -File compilar.ps1     # genera libreria-java.jar
java -jar libreria-java.jar
```

Pruebas sin red (lector JSON y validación de la configuración):

```powershell
java -cp build test\PruebaJson.java
```

## Estructura

```
src/library/java/
├── LibreriaJavaApp.java   ventana, pestañas, semáforos, acciones
├── GatewayClient.java     ÚNICO lugar con red: arma gateway + /api/<servicio> + ruta, Bearer, X-Request-ID, registro
├── Config.java            dirección del gateway (archivo en %APPDATA%), validación
└── Json.java              lector/escritor JSON mínimo
test/PruebaJson.java       pruebas sin red
compilar.ps1               javac + jar
```
