/**
 * View: renderiza el estado del catálogo (cards + paginación) en el DOM.
 * No hace fetch ni conoce la URL del microservicio (eso es del Model);
 * solo recibe datos ya procesados y notifica interacciones vía callbacks.
 */
class CatalogView {
  constructor({ gridEl, statusEl, paginationEl }) {
    this.gridEl = gridEl;
    this.statusEl = statusEl;
    this.paginationEl = paginationEl;
  }

  showLoading() {
    this.statusEl.textContent = 'Cargando catálogo desde el microservicio…';
    this.statusEl.className = 'status status--loading';
  }

  showError(message) {
    this.statusEl.textContent = `⚠ ${message}`;
    this.statusEl.className = 'status status--error';
    this.gridEl.innerHTML = '';
    this.paginationEl.innerHTML = '';
  }

  render(pageData, onPageChange) {
    this.statusEl.textContent = '';
    this.statusEl.className = 'status';
    this._renderCards(pageData.books);
    this._renderPagination(pageData, onPageChange);
  }

  _renderCards(books) {
    this.gridEl.innerHTML = '';

    if (books.length === 0) {
      this.gridEl.innerHTML = '<p class="empty">No hay libros para mostrar.</p>';
      return;
    }

    for (const book of books) {
      const card = document.createElement('article');
      card.className = 'book-card';

      const authors = book.autores.length ? book.autores.join(', ') : 'Autor desconocido';
      const price = Number(book.precio || 0).toFixed(2);

      card.innerHTML = `
        <div class="book-cover">
          <img src="${book.imagen}" alt="Portada de ${book.titulo}" loading="lazy" />
        </div>
        <div class="book-info">
          <h3 class="book-title" title="${book.titulo}">${book.titulo}</h3>
          <p class="book-authors">${authors}</p>
          <dl class="book-meta">
            <div><dt>ISBN</dt><dd>${book.isbn}</dd></div>
            <div><dt>Año</dt><dd>${book.anio}</dd></div>
            <div><dt>Género</dt><dd>${book.categoria}</dd></div>
            <div><dt>Stock</dt><dd>${book.stock}</dd></div>
          </dl>
          <p class="book-price">$${price}</p>
        </div>
      `;

      const img = card.querySelector('img');
      img.addEventListener('error', () => {
        img.onerror = null;
        img.src = 'assets/placeholder.svg';
      }, { once: true });

      this.gridEl.appendChild(card);
    }
  }

  _renderPagination(pageData, onPageChange) {
    const { page, totalPages, total } = pageData;
    this.paginationEl.innerHTML = '';

    const info = document.createElement('span');
    info.className = 'pagination-info';
    info.textContent = `Página ${page} de ${totalPages} · ${total} libros en el catálogo`;

    const prevBtn = document.createElement('button');
    prevBtn.textContent = '← Anterior';
    prevBtn.disabled = page <= 1;
    prevBtn.addEventListener('click', () => onPageChange(page - 1));

    const nextBtn = document.createElement('button');
    nextBtn.textContent = 'Siguiente →';
    nextBtn.disabled = page >= totalPages;
    nextBtn.addEventListener('click', () => onPageChange(page + 1));

    this.paginationEl.appendChild(prevBtn);
    this.paginationEl.appendChild(info);
    this.paginationEl.appendChild(nextBtn);
  }
}
