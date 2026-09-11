# Evidencia — Microservicio Bilingüe (XML/JSON)

Integración de Aplicaciones Computacionales · UDEM · Ejercicio 3 (extensión bilingüe)

Este documento captura la evidencia de funcionamiento de los endpoints REST agregados a
`app.py` para que el microservicio conteste en XML (por defecto) o en JSON (`?format=json`),
además de dos endpoints nuevos: conceptos de Cloud Computing con sus libros, y datos mínimos
de libros con imagen. Corrida local, catálogo completo (30 libros, 4 conceptos), verificado
también con Swagger UI (`/docs`).

## 1. `/books` — catálogo completo

**XML (sin `format`, comportamiento por defecto exigido en el punto 4):**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<books><total>30</total><libro><isbn>9780451524935</isbn><titulo>1984</titulo><anio>1949</anio><precio>430.0</precio><stock>25</stock><formato>Paperback</formato><categoria>Fiction</categoria></libro>...</books>
```

**JSON (`?format=json`):**

```json
{"libros":[{"anio":1949,"categoria":"Fiction","formato":"Paperback","isbn":"9780451524935","precio":430.0,"stock":25,"titulo":"1984"}, ...], "total":30}
```

## 2. `/books/{isbn}` — un libro por ISBN

**Ejemplo pedido explícitamente:** `GET /books/9780451524935?format=json`

XML (default):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<book><isbn>9780451524935</isbn><titulo>1984</titulo><anio>1949</anio><precio>430.0</precio><stock>25</stock><formato>Paperback</formato><categoria>Fiction</categoria></book>
```

JSON:
```json
{"anio":1949,"categoria":"Fiction","formato":"Paperback","isbn":"9780451524935","precio":430.0,"stock":25,"titulo":"1984"}
```

**Caso de error (ISBN inexistente), también bilingüe — `GET /books/0000000000000`:**
```
HTTP 404
<?xml version="1.0" encoding="UTF-8"?>
<error><codigo_error>ERR_BOOK_NOT_FOUND</codigo_error><mensaje>No existe un libro registrado con el ISBN '0000000000000'.</mensaje></error>
```

## 3. `/concepts` — Conceptos de Cloud Computing (IaaS, PaaS, SaaS, FaaS) + libros (punto 5)

```json
{"conceptos":[
  {"concepto_id":1,"nombre":"IaaS","definicion":"...","libros":[{"isbn":"9780134092669","titulo":"Cloud Computing: Concepts, Technology & Architecture","anio":2017}]},
  {"concepto_id":2,"nombre":"PaaS","...":"..."},
  {"concepto_id":3,"nombre":"SaaS","...":"..."},
  {"concepto_id":4,"nombre":"FaaS","...":"..."}
], "total":4}
```

## 4. `/books/covers` — datos mínimos + imagen (punto 6)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<books><total>30</total><libro><isbn>9780451524935</isbn><titulo>1984</titulo><imagen>https://covers.openlibrary.org/b/isbn/9780451524935-L.jpg</imagen></libro>...</books>
```

Las URLs de imagen coinciden exactamente con las declaradas en `library.xml` (una imagen de
portada por ISBN, servida por Open Library), que es la fuente de datos original de este
catálogo — no se inventó un origen de imágenes nuevo.

## 5. Swagger UI (`/docs`)

Se agregó un endpoint `/openapi.json` (especificación OpenAPI 3.0 generada en `openapi.py`)
y una página `/docs` que monta Swagger UI apuntando a esa especificación. Se probó "Try it
out" contra `/books`, `/books/{isbn}`, `/books/covers` y `/concepts`, alternando el parámetro
`format` entre `xml` y `json` — en los cuatro casos Swagger UI mostró código `200` y el cuerpo
esperado en el formato solicitado. Capturas de pantalla tomadas durante la sesión de trabajo
(Swagger UI listando los 4 endpoints, y cada endpoint respondiendo tanto en XML como en JSON).

## 6. Reflexión — ¿por qué implementarlo así?

**Negociación por parámetro de consulta, no por cabecera `Accept`.** El enunciado pide
literalmente `?format=json`, así que se implementó como un parámetro de query explícito
(`_wants_json()` lee `request.args.get('format', 'xml')`) en vez de inspeccionar la cabecera
HTTP `Accept`. Es más simple de probar desde un navegador (basta pegar la URL) y más explícito
para quien consume la API por primera vez, a costa de no ser "puramente RESTful" en el sentido
estricto de content negotiation — un trade-off razonable para un ejercicio académico donde la
usabilidad de la demostración importa tanto como el resultado.

**XML como formato por defecto, no JSON.** El microservicio nació como un servicio SOAP, cuyo
contrato es inherentemente XML. Mantener XML como default cuando no se envía `format` preserva
compatibilidad con cualquier cliente o prueba que ya asumía XML de sesiones anteriores, y hace
que el cambio sea estrictamente aditivo: nada de lo que ya funcionaba en XML se rompe; JSON es
un modo opcional, no un reemplazo.

**Un solo conversor recursivo (`_append_fields`) en vez de builders XML manuales por endpoint.**
El resto del código SOAP (`soap/service.py`) construye cada elemento XML a mano con
`ET.SubElement`, porque ahí el contrato WSDL exige nombres y estructura exactos. Los endpoints
REST nuevos no tienen ese contrato rígido — son datos propios del ejercicio — así que un único
diccionario Python describe la respuesta, y una función recursiva lo vuelca a JSON (`jsonify`)
o a XML (`ElementTree`) según se pida. Esto evita duplicar la lógica de armado de respuesta
cuatro veces (una por endpoint) y garantiza que ambos formatos siempre representen exactamente
los mismos datos, sin que puedan divergir con el tiempo.

**El endpoint `/soap` no se tocó.** SOAP 1.1 exige un Envelope XML por especificación — no
tendría sentido, y rompería el contrato WSDL ya publicado, hacerlo "bilingüe". Por eso el
parámetro `format` sólo aplica a los endpoints REST nuevos (`/books`, `/books/{isbn}`,
`/books/covers`, `/concepts`); `/soap` sigue siendo XML puro, tal como se entregó en la sesión
anterior.

**Imágenes como URL derivada del ISBN, no un campo nuevo en la base de datos.** El esquema
original (`books`) no tiene columna de imagen. En vez de alterar el esquema para un solo
endpoint, se reutilizó el mismo patrón que ya usa `library.xml` (fuente de los datos
sembrados): una URL de portada pública de Open Library, construida a partir del ISBN. Es
determinista, no requiere almacenamiento adicional, y es consistente con el dato de origen del
ejercicio.
