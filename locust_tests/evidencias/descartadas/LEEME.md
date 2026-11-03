# Corridas descartadas (no se usan en RESULTADOS.md)

## intento_stress_monolito_* (2026-10-30, desde la GUI de Locust)

1. **Primer intento (15:24–15:36):** la contraseña escrita en la terminal era incorrecta. Los 20 `POST /login` del monolito fallaron, los usuarios quedaron sin sesión y `/libros` redirigió a `/login`: **64 % de fallas**, causadas por la prueba y no por el sistema. Además, esta corrida reveló un error de validación en el locustfile: `/admin/autores` sin sesión redirige a la portada (`/`) con código 200 y se estaba contando como éxito (149 peticiones). Se corrigió `_html()` para exigir que la página final sea la pedida. El `intento_stress_monolito.html` es el reporte de este intento.
2. **Segundo intento (15:37–15:49):** con la contraseña correcta corrió sin fallas hasta 20 usuarios, pero al volver a presionar *Start* en la GUI las estadísticas se reiniciaron. El `_stats.csv` quedó en cero y el `_stats_history.csv` mezcla ambos intentos, así que no hay un resumen confiable.

El stress del monolito se repitió completo con `ejecutar_todas.ps1` (resultados en `../stress_monolito_*`).
