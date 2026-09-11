/**
 * View: panel de configuración (URL base, endpoint, tamaño de página).
 * Solo lee/escribe el formulario; la persistencia real vive en ConfigModel.
 */
class SettingsView {
  constructor({ panelEl, formEls }) {
    this.panelEl = panelEl;
    this.formEls = formEls; // { baseUrl, endpoint, pageSize }
  }

  open(config) {
    this.formEls.baseUrl.value = config.baseUrl;
    this.formEls.endpoint.value = config.endpoint;
    this.formEls.pageSize.value = config.pageSize;
    this.panelEl.classList.remove('hidden');
  }

  close() {
    this.panelEl.classList.add('hidden');
  }

  readForm() {
    const pageSize = Math.max(1, Math.min(50, Number(this.formEls.pageSize.value) || 12));
    return {
      baseUrl: this.formEls.baseUrl.value.trim().replace(/\/+$/, ''),
      endpoint: this.formEls.endpoint.value.trim() || '/books',
      pageSize
    };
  }
}
