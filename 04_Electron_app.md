# 04 - Electron App

Prompt utilizado para generar la aplicación de escritorio (Electron) que consume el microservicio SOAP/REST bilingüe (XML/JSON) desarrollado en `services/soap`.

## Prompt

```
escribe una aplicacion de escritorio para windows 11 con electron que muestre el catalofgo de libros con sus imagenes usando cards, cada card debe mostrar la imagen del libro , autor(es), isbn, stock, titulo, año de publicacion, genero y precio. Implementa paginacion y carga por peticion , la aplicacion de escritorio para windows 11 con electron debe consumir EXCLUSIVAMENTE XML provisto por el microservicio disponible en : http://34.51.99.221:5001/books la que habiamos hecho, pero la URL y el EndPoint debe ser configurables en la applicacion. Esta configuracion debe de persistir mediante el uso de LocalStorage., tambien incluye los pasos para ejecutar la apliacion en windows 11 mediante la creacion de un archivo llamadado README.md
```

## Nota

La IP `34.51.99.221` del prompt es la de la instancia del profesor (a modo de ejemplo genérico en el enunciado). Nuestra instancia (`integracion`, GCP) usa una IP externa distinta, ya que es efímera y depende del proyecto de cada quien.

**Endpoint real de nuestro microservicio:**

```
http://34.61.137.144:5001/books
```

La aplicación Electron debe apuntar por defecto a esta URL/puerto (configurables y persistidos en LocalStorage, tal como pide el prompt), no a la IP de ejemplo del enunciado.

