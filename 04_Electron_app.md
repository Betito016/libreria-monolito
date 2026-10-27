# 04 - Electron App

Prompt utilizado para generar la aplicación de escritorio (Electron) que consume el microservicio SOAP/REST bilingüe (XML/JSON) desarrollado en `services/soap`.

## Prompt

```
escribe una aplicacion de escritorio para windows 11 con electron que muestre el catalofgo de libros con sus imagenes usando cards, cada card debe mostrar la imagen del libro , autor(es), isbn, stock, titulo, año de publicacion, genero y precio. Implementa paginacion y carga por peticion , la aplicacion de escritorio para windows 11 con electron debe consumir EXCLUSIVAMENTE XML provisto por el microservicio disponible en : http://34.51.99.221:5001/books la que habiamos hecho, pero la URL y el EndPoint debe ser configurables en la applicacion. Esta configuracion debe de persistir mediante el uso de LocalStorage., tambien incluye los pasos para ejecutar la apliacion en windows 11 mediante la creacion de un archivo llamadado README.md
```

## Nota

La IP `34.51.99.221` del prompt es la de la instancia del profesor (a modo de ejemplo genérico en el enunciado). Nuestra instancia (`integracion`, GCP) usa una IP externa distinta.

**Endpoint real de nuestro microservicio:**

```
http://34.135.84.31:5006/books
```

Esta dirección está **reservada como IP estática** en GCP (`integracion-ip`, región `us-central1`), así que ya no cambia al reiniciar la instancia. Antes era efímera y rotó tres veces, dejando enlaces muertos en la app y en la documentación.

La aplicación Electron debe apuntar por defecto a esta URL/puerto (configurables y persistidos en LocalStorage, tal como pide el prompt), no a la IP de ejemplo del enunciado.

## Resultados (evidencia)

**Microservicio respondiendo en vivo** (`GET /books?format=json&page=1`, código 200, IP pública real):

![Microservicio funcionando](evidencia/microservicio.png)

**Aplicación de escritorio Electron consumiendo el XML del microservicio:**

![App Electron funcionando](evidencia/electron-app.png)

## Reflexión

El microservicio original (`services/soap`) nació como un servicio SOAP 1.1: su contrato natural es XML, no JSON. Cuando se le agregó la capa REST bilingüe, JSON quedó como una comodidad opcional (`?format=json`), pero **el XML sigue siendo el formato por defecto y el que representa el contrato real del servicio**. Por eso la aplicación Electron se construyó para consumir *exclusivamente* XML: no es una limitación arbitraria, es la forma correcta de probar que un cliente de escritorio puede integrarse con un servicio de este tipo sin depender de la comodidad de JSON. Esto obligó a resolver cosas que con JSON se hubieran pasado por alto, como parsear el XML con `DOMParser` y navegar el árbol de nodos (`<libro>`, `<autor>`, `<imagen>`, etc.) en vez de simplemente hacer `response.json()`.

Que la URL y el endpoint sean configurables y persistan en `LocalStorage` tampoco es un capricho del enunciado: en un despliegue real, la IP de un servidor cambia (en nuestro caso, la IP externa de la instancia de GCP es *efímera* y cambió más de una vez durante el proyecto). Si la URL estuviera fija en el código, cada cambio de IP obligaría a recompilar y redistribuir la aplicación. Con la configuración persistida del lado del cliente, el mismo instalador sirve para apuntar a cualquier instancia del microservicio (local, de prueba, de producción) sin tocar una sola línea de código.

Durante la integración también apareció un problema que no es obvio hasta que se topa uno con él: **CORS**. El renderer de Electron es, en el fondo, un navegador Chromium, y como tal aplica la misma política de mismo origen que cualquier página web. Como el microservicio Flask no enviaba la cabecera `Access-Control-Allow-Origin`, el navegador bloqueaba la respuesta aunque el servidor sí contestara correctamente — el error se veía como "Failed to fetch" y parecía un problema de red, pero era el navegador protegiendo al usuario de una respuesta sin autorización explícita de origen cruzado. Esto refuerza que un microservicio pensado para ser consumido por un cliente de escritorio (o cualquier cliente basado en navegador) *tiene* que declarar explícitamente qué orígenes puede aceptar, no es opcional.

Finalmente, la paginación con "carga por petición" (cada cambio de página dispara una nueva llamada HTTP al microservicio, en vez de traer los 30 libros de una sola vez y paginar solo en memoria) refleja cómo se comportaría un cliente real contra un catálogo mucho más grande: no tiene sentido cargar miles de registros de golpe cuando el usuario solo va a ver 12 a la vez.

