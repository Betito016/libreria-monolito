/**
 * Model: obtiene el catálogo de libros EXCLUSIVAMENTE en XML desde el
 * microservicio configurado, y lo traduce a objetos JS planos para las Views.
 * No conoce nada del DOM de la aplicación (separación de responsabilidades MVC).
 */
class BookModel {
  constructor(config) {
    this.config = config;
  }

  buildUrl(page, pageSize) {
    const base = this.config.baseUrl.replace(/\/+$/, '');
    const endpoint = this.config.endpoint.startsWith('/')
      ? this.config.endpoint
      : `/${this.config.endpoint}`;

    const url = new URL(base + endpoint);
    url.searchParams.set('format', 'xml');
    url.searchParams.set('page', String(page));
    url.searchParams.set('page_size', String(pageSize));
    return url.toString();
  }

  async fetchPage(page, pageSize) {
    const url = this.buildUrl(page, pageSize);

    let response;
    try {
      response = await fetch(url, { headers: { Accept: 'application/xml' } });
    } catch (err) {
      throw new Error(`No se pudo contactar al microservicio en ${url} (${err.message}).`);
    }

    if (!response.ok) {
      throw new Error(`El microservicio respondió con estado ${response.status}.`);
    }

    const xmlText = await response.text();
    return this._parseXml(xmlText);
  }

  _parseXml(xmlText) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(xmlText, 'application/xml');

    if (doc.querySelector('parsererror')) {
      throw new Error('El microservicio no devolvió un XML válido.');
    }

    const root = doc.documentElement;
    const textOf = (parent, tag) => parent.querySelector(`:scope > ${tag}`)?.textContent ?? '';

    const total = Number(textOf(root, 'total') || 0);
    const page = Number(textOf(root, 'page') || 1);
    const pageSize = Number(textOf(root, 'page_size') || 0);
    const totalPages = Number(textOf(root, 'total_pages') || 1);

    const books = Array.from(root.querySelectorAll(':scope > libro')).map((libroEl) => {
      const autores = Array.from(libroEl.querySelectorAll(':scope > autor')).map((a) => a.textContent);
      return {
        isbn: textOf(libroEl, 'isbn'),
        titulo: textOf(libroEl, 'titulo'),
        anio: textOf(libroEl, 'anio'),
        precio: textOf(libroEl, 'precio'),
        stock: textOf(libroEl, 'stock'),
        formato: textOf(libroEl, 'formato'),
        categoria: textOf(libroEl, 'categoria'),
        imagen: textOf(libroEl, 'imagen'),
        autores
      };
    });

    return { total, page, pageSize, totalPages, books };
  }
}
