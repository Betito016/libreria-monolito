/**
 * Controller: conecta BookModel (datos) con CatalogView (presentación),
 * maneja la paginación (carga por petición: cada cambio de página dispara
 * una nueva llamada al microservicio, no se precargan todas las páginas).
 */
class CatalogController {
  constructor(view, config) {
    this.view = view;
    this.setConfig(config, { skipReload: true });
  }

  setConfig(config, { skipReload = false } = {}) {
    this.config = config;
    this.bookModel = new BookModel(config);
    this.page = 1;
    if (!skipReload) {
      this.loadPage(1);
    }
  }

  async loadPage(page) {
    this.page = page;
    this.view.showLoading();
    try {
      const pageData = await this.bookModel.fetchPage(page, this.config.pageSize);
      this.view.render(pageData, (newPage) => this.loadPage(newPage));
    } catch (err) {
      this.view.showError(err.message);
    }
  }
}
