# Sitio de publicación — Ejercicio 02

Esta carpeta es el paquete listo para subir a `~/html/ejercicio02/` en `ubiquitous.udem.edu` (Parte 10 del
ejercicio), no un lugar para editar contenido directamente.

- `docs/` y `sql/` son **copias** de las carpetas `../docs/` y `../db/` del repositorio, aplanadas para cumplir
  la estructura exacta que pide el ejercicio. La fuente de verdad sigue siendo `../docs/` y `../db/` — si se
  edita algo ahí, hay que volver a copiarlo aquí antes de publicar (no editar los archivos dentro de `site/docs`
  ni `site/sql` directamente).
- `evidencias/` tiene la estructura de carpetas de `docs/EVIDENCE_GUIDE.md`, vacía hasta que se agreguen las
  capturas reales.
- `descargas/` recibirá `ejercicio02.tar.gz` cuando se empaquete el proyecto final.
- `index.html` sí es el archivo fuente real (no una copia) — se edita directamente aquí.

Para previsualizar localmente: `npx serve site -l 4173` (o usar el preview del harness con la configuración en
`.claude/launch.json`).
