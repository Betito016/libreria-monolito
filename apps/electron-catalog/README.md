# Catálogo de Libros — Aplicación de escritorio (Electron)

Aplicación de escritorio para Windows 11, construida con Electron, que muestra el catálogo de libros en *cards* (imagen, autor(es), ISBN, stock, título, año de publicación, género y precio). Consume **exclusivamente XML** del microservicio bilingüe SOAP/REST desarrollado en [`services/soap`](../../services/soap), con paginación real (cada página dispara una nueva petición HTTP al microservicio).

## Arquitectura (MVC)

```
src/
├── index.html                     # Shell de la vista principal
├── styles.css
├── app.js                         # Entry point: instancia Models/Views/Controllers
├── models/
│   ├── ConfigModel.js              # Persistencia de configuración en LocalStorage
│   └── BookModel.js                # Fetch XML al microservicio + parseo a objetos JS
├── views/
│   ├── CatalogView.js              # Renderiza cards y controles de paginación
│   └── SettingsView.js             # Renderiza el panel de configuración
└── controllers/
    ├── CatalogController.js        # Conecta BookModel <-> CatalogView, maneja paginación
    └── SettingsController.js       # Conecta ConfigModel <-> SettingsView
```

- **Model**: `ConfigModel` (LocalStorage) y `BookModel` (HTTP + parseo XML) — no tocan el DOM.
- **View**: `CatalogView` y `SettingsView` — solo leen/escriben el DOM, reciben datos ya procesados.
- **Controller**: `CatalogController` y `SettingsController` — orquestan Model y View, manejan eventos de usuario.

`main.js` es el proceso principal de Electron (crea la ventana); no contiene lógica de negocio.

## Requisitos

- Windows 11
- [Node.js](https://nodejs.org/) 18 LTS o superior (incluye `npm`)

## Instalación y ejecución en Windows 11

1. Abre una terminal (PowerShell o CMD) en esta carpeta:
   ```powershell
   cd library\apps\electron-catalog
   ```
2. Instala las dependencias (descarga Electron):
   ```powershell
   npm install
   ```
3. Ejecuta la aplicación:
   ```powershell
   npm start
   ```

Se abrirá una ventana de escritorio con el catálogo de libros.

## Configuración del microservicio

Por defecto la aplicación apunta a:

```
URL base:  http://34.135.84.31:5006
Endpoint:  /books
```

Para cambiarla, usa el botón **⚙ Configuración** dentro de la app: ahí puedes editar la URL base, el endpoint y la cantidad de libros por página. Al guardar, la configuración se persiste en `LocalStorage` (namespace `catalogo-libros-config`) y sobrevive a reinicios de la aplicación.

La aplicación arma la petición como:

```
GET {URL base}{endpoint}?format=xml&page={n}&page_size={m}
```

y **siempre** solicita `format=xml` — el parseo del microservicio se hace exclusivamente sobre XML, nunca JSON.

## Generar un instalador para Windows (opcional)

No es requerido para la entrega, pero si se quiere empaquetar como `.exe`:

```powershell
npm install --save-dev electron-builder
npx electron-builder --win
```
