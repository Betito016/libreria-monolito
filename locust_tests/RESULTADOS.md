# Resultados: monolito vs. microservicios (Locust)

**Generador de carga:** laptop en la red de la UDEM, Locust 2.47.0 / Python 3.14.
**Destino:** instancia GCP `34.135.84.31` (e2-medium: 2 vCPU compartidas, 3.6 GB). Monolito en `:3000`, microservicios en `:5000–5005`.
**Fechas:** smoke y load el 2026-10-30; stress, spike, soak y quiebre el 2026-11-03.
**Umbral:** degradado si **p95 > 1 s** o **errores > 5 %**.
**Pausa entre tareas:** 1–3 s. **Rutas:** solo lecturas, con los mismos pesos en ambos sistemas (ver [README.md](README.md)).

Todos los valores salen de los CSV de `evidencias/` (fila *Aggregated* de `<perfil>_<sistema>_stats.csv`), procesados por `resumir.py` → [`evidencias/tablas_resultados.md`](evidencias/tablas_resultados.md). El agregado incluye el `POST /login` y la petición `(preparacion)` que cada usuario hace una sola vez.

## Una fila por prueba y destino

| Perfil | Destino | Usuarios | Duración | RPS | p95 | Errores | Umbral | Hipótesis (anotada antes de ejecutar) | Conclusión |
|---|---|---|---|---|---|---|---|---|---|
| Smoke | Monolito | 1 | 30 s | 0.54 | 260 ms | 0.00 % | Cumple | 0 % errores; p95 ≈ 150–400 ms, dominado por la red | Confirmada: login y las 5 rutas de navegación responden 200 con el contenido correcto |
| Smoke | Microservicios | 1 | 30 s | 0.60 | 240 ms | 0.00 % | Cumple | Igual que el monolito | Confirmada: los 6 servicios responden (login, books, authors, users, pedidos y pagos). `GET /session` no salió sorteado con 1 usuario en 30 s; sí se ejecutó en las demás pruebas |
| Load | Monolito | 5 | 121 s | 2.45 | 170 ms | 0.00 % | Cumple | Ambos cumplen el umbral | Confirmada: p95 estable alrededor de 120–300 ms |
| Load | Microservicios | 5 | 121 s | 2.34 | 180 ms | 0.00 % | Cumple | Ambos cumplen; books más estable por la caché Redis | Cumple; no se observa ventaja de la caché (la red y el `Connection: close` de Flask pesan más) |
| Stress | Monolito | 2→20 | 91 s | 5.27 | 240 ms | 0.00 % | Cumple | El monolito sería el primero en degradarse | **No confirmada:** con 20 usuarios el RPS crece lineal y el p95 no tiene tendencia |
| Stress | Microservicios | 2→20 | 91 s | 5.16 | 350 ms | 0.00 % | Cumple | Flask (servidor de desarrollo) y los 2 vCPU podrían saturarse | Cumple; p95 mayor que el monolito, pero sin saturación (CPU de la VM: 13 % promedio) |
| Spike | Monolito | 2→15→2 | 122 s | 2.78 | 530 ms | 0.00 % | Cumple (agregado) | Subida brusca del p95 en el pico y recuperación | Confirmada: p95 de 1.8 s ~10 s al entrar el pico y luego ~200 ms. **`POST /login` superó 1 s** (p95 1.8 s) |
| Spike | Microservicios | 2→15→2 | 122 s | 2.71 | 770 ms | 0.00 % | Cumple (agregado) | Igual | Confirmada: pico de 1.1 s al entrar; **`[login] POST /login` superó 1 s** (p95 1.2 s) |
| Soak | Monolito | 3 | 241 s | 1.41 | 390 ms | 0.00 % | Cumple | Latencia estable, sin crecimiento | Confirmada: sin tendencia en 4 min; oscilaciones por la red |
| Soak | Microservicios | 3 | 241 s | 1.35 | 610 ms | 0.00 % | Cumple | Igual | Confirmada: sin tendencia; p95 mayor que en stress por la red (base 201–497 ms antes de la prueba) |
| Quiebre | Monolito | 1→20 | 121 s | 5.39 | 160 ms | 0.00 % | **No se alcanzó el quiebre** | Quizá ninguno incumpla antes de 20 usuarios | Confirmada: llegó a 20 usuarios sin incumplir (`quiebre_monolito.json`) |
| Quiebre | Microservicios | 1→20 | 121 s | 5.25 | 220 ms | 0.00 % | **No se alcanzó el quiebre** | Igual | Confirmada: llegó a 20 usuarios sin incumplir (`quiebre_microservicios.json`) |

### p95 (ms) por operación comparable

| Perfil | Catálogo mono / micro | Búsqueda mono / micro | Detalle mono / micro | Autores mono / micro |
|---|---|---|---|---|
| Smoke | 130 / 190 | 58 / 130 | 100 / 120 | 110 / 130 |
| Load | 170 / 190 | 88 / 140 | 120 / 140 | 150 / 150 |
| Stress | 170 / 320 | 120 / 180 | 110 / 190 | 170 / 270 |
| Spike | 350 / 500 | 290 / 330 | 200 / 390 | 200 / 350 |
| Soak | 460 / 700 | 300 / 590 | 310 / 590 | 390 / 660 |
| Quiebre | 130 / 180 | 76 / 150 | 90 / 140 | 140 / 140 |

## Evidencias que ayudan a interpretar

| Perfil | Latencia base de la red sin carga (`red_*.txt`) | CPU de la instancia (`vmstat_*.txt`) |
|---|---|---|
| Smoke | 100–107 ms | 7 % promedio, 38 % máx. |
| Load | 107–125 ms | 5 % promedio, 21 % máx. |
| Stress | 145–192 ms | 13 % promedio, 33 % máx. |
| Spike | **439–960 ms** | 9 % promedio, 38 % máx.; **18 procesos en cola** al entrar el pico |
| Soak | 201–497 ms | 7 % promedio, 46 % máx. |
| Quiebre | 162–694 ms | 12 % promedio, 22 % máx. |

- La CPU de la VM nunca se saturó. Las variaciones grandes del p95 (soak y spike) coinciden con una red más lenta antes de la prueba, no con más carga.
- La única saturación breve de CPU coincide con la ráfaga de logins del spike (bcrypt verifica la contraseña y consume CPU a propósito).
- **Conexiones:** el monolito (Node) responde `Connection: keep-alive` y reutiliza la conexión; los microservicios (servidor de desarrollo de Flask, Werkzeug 3.1.8) responden `Connection: close`, así que cada petición abre una conexión TCP nueva (≈ un viaje de red extra). Se comprobó con `curl` (2 peticiones seguidas: monolito 0 conexiones nuevas, books 1). Esto explica buena parte de la diferencia de p50: ~60 ms frente a ~120 ms en rutas pequeñas.
- En load, `[login] GET /session` tuvo p95 = 1100 ms con solo 18 peticiones. Con tan pocas muestras, una sola petición lenta (red) basta para mover el p95.

## Desviaciones respecto al enunciado y pruebas no completadas

| Qué | Por qué | Efecto |
|---|---|---|
| **Stress de 90 s** (en lugar de hasta 3 min), escalones de 18 s | Tiempo disponible; el enunciado dice "hasta 3 minutos" | Cada escalón dura menos; suficiente para ver la rampa 2→20, no para estabilizar cada nivel |
| **Quiebre: +1 usuario cada 6 s** (máx. 2 min) | Tiempo disponible; dentro del límite de 4 min | Cada nivel se observa 6 s; con pocos usuarios hay pocas muestras por evaluación |
| **Stress, spike, soak y quiebre con los dos sistemas en paralelo** (`ejecutar_paralelo.ps1`) | Tiempo disponible | Comparten la VM durante la prueba. La condición es igual para ambos y la CPU no pasó de 46 %, pero los logins del spike compitieron por CPU entre sistemas |
| **Primer stress del monolito descartado** (`evidencias/descartadas/`) | 1.er intento: contraseña incorrecta (64 % de fallas causadas por la prueba). 2.º intento: estadísticas reiniciadas en la GUI | Se repitió completo; no se usa en los resultados |
| **Prueba exploratoria de 100 usuarios: no ejecutada** | Fuera de lo requerido; se canceló por tiempo | — |
| **Punto de quiebre no encontrado** | Ningún sistema incumplió el umbral con 20 usuarios | Solo se puede afirmar que el quiebre está por encima de 20 usuarios con estas rutas y pausas, no la capacidad real |
| No se usó `levanta_todo.ps1` | Los servicios corren en la instancia GCP como servicios `systemd` (el enunciado exige probar contra GCP, no contra localhost) | Antes de cada prueba se verificó `GET /health?format=json` de los 6 servicios y `GET /` del monolito desde la IP externa |
