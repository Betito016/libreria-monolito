/**
 * Model: persistencia de la configuración del cliente (URL base, endpoint,
 * tamaño de página) usando LocalStorage, tal como exige el enunciado.
 */
class ConfigModel {
  static STORAGE_KEY = 'catalogo-libros-config';

  static DEFAULTS = {
    // Library API Gateway: único punto de entrada; /api/soap lleva al servicio SOAP/REST (:5006).
    baseUrl: 'http://34.135.84.31/api/soap',
    endpoint: '/books',
    pageSize: 12
  };

  static load() {
    try {
      const raw = localStorage.getItem(ConfigModel.STORAGE_KEY);
      if (!raw) {
        return { ...ConfigModel.DEFAULTS };
      }
      const parsed = JSON.parse(raw);
      return { ...ConfigModel.DEFAULTS, ...parsed };
    } catch (err) {
      console.warn('No se pudo leer la configuración guardada, usando valores por defecto.', err);
      return { ...ConfigModel.DEFAULTS };
    }
  }

  static save(config) {
    localStorage.setItem(ConfigModel.STORAGE_KEY, JSON.stringify(config));
  }
}
