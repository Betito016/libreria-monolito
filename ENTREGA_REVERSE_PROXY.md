# Entrega: Reverse Proxy / API Gateway (nginx) — Library

Dónde está cada elemento solicitado:

| # | Se pide | Dónde |
|---|---|---|
| 1 | Monorepo con las apps de escritorio configuradas para el Reverse Proxy | Todo el monorepo. Apps: **Electron** `apps/electron-catalog/` (URL base `http://34.135.84.31/api/soap`), **Python Tkinter** `apps/Python_app/` (URLs `http://34.135.84.31/api/<servicio>`), **Java Swing** `apps/java-desktop/` (dirección del gateway `http://34.135.84.31`; `libreria-java.jar` listo para ejecutar con `java -jar`) |
| 2 | Evidencias del funcionamiento | `gateway/evidencias/`: capturas de las tres apps, pruebas funcionales (18/18), pruebas de falla (round robin, instancia caída, 503, 504, 404), límite de tasa (429), registro del gateway con request id, Locust directo vs gateway, puertos directos cerrados |
| 3 | Archivos de configuración de nginx | `gateway/nginx/`: `library-gateway.conf` (upstreams, límites, registro, servidor :8080), `library-web.conf` (servidor :80, monolito + API), `rutas-api.conf` (rutas y políticas comunes). Complementos: `gateway/salud/`, `gateway/systemd/`, `gateway/config/`, `gateway/desplegar.sh` |
| 4 | Reflexión (implementación, ventajas, desventajas/retos) | `gateway/REFLEXION.md` |

Documentación completa (diagrama antes/después, tabla de rutas, instalación, pruebas y resultados): [`gateway/README.md`](gateway/README.md).

URLs en la instancia GCP (sin dominio):

- Monolito web: `http://34.135.84.31/`
- APIs: `http://34.135.84.31/api/{login,books,pagos,pedidos,users,autores,soap}/...` (también en `:8080`)
- Salud agregada: `http://34.135.84.31/health`
