/**
 * Entry point del renderer: instancia Models, Views y Controllers (MVC) y
 * cablea los eventos del DOM. No contiene lógica de negocio ni de fetch.
 */
document.addEventListener('DOMContentLoaded', () => {
  const gridEl = document.getElementById('cards-grid');
  const statusEl = document.getElementById('status');
  const paginationEl = document.getElementById('pagination');

  const catalogView = new CatalogView({ gridEl, statusEl, paginationEl });

  const settingsPanelEl = document.getElementById('settings-panel');
  const formEls = {
    baseUrl: document.getElementById('setting-base-url'),
    endpoint: document.getElementById('setting-endpoint'),
    pageSize: document.getElementById('setting-page-size')
  };
  const settingsView = new SettingsView({ panelEl: settingsPanelEl, formEls });

  const initialConfig = ConfigModel.load();
  const catalogController = new CatalogController(catalogView, initialConfig);

  const settingsController = new SettingsController(settingsView, (newConfig) => {
    catalogController.setConfig(newConfig);
  });

  document.getElementById('settings-btn').addEventListener('click', () => settingsController.open());
  document.getElementById('settings-save').addEventListener('click', () => settingsController.save());
  document.getElementById('settings-cancel').addEventListener('click', () => settingsController.cancel());

  catalogController.loadPage(1);
});
