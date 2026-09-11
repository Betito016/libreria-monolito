/**
 * Controller: conecta ConfigModel (persistencia en LocalStorage) con
 * SettingsView (formulario), y notifica al resto de la app cuando la
 * configuración cambia.
 */
class SettingsController {
  constructor(view, onSave) {
    this.view = view;
    this.onSave = onSave;
  }

  open() {
    this.view.open(ConfigModel.load());
  }

  save() {
    const config = this.view.readForm();
    ConfigModel.save(config);
    this.view.close();
    this.onSave(config);
  }

  cancel() {
    this.view.close();
  }
}
