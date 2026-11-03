# Pruebas de rendimiento con Locust: monolito vs. microservicios

Compara el **monolito web** (`apps/web-monolito`, Express + EJS) con la **arquitectura de microservicios** (`services/`, 6 servicios Flask) usando las mismas operaciones de lectura, la misma carga y las mismas pausas.

| Archivo | Para qué |
|---|---|
| `locustfile.py` | Usuarios virtuales (`MonolitoUser`, `MicroserviciosUser`), tareas, validaciones y los 6 perfiles de carga |
| `ejecutar_prueba.ps1` | Corre **una** prueba sin interfaz y guarda CSV + HTML en `evidencias/` |
| `ejecutar_todas.ps1` | Corre las pruebas un sistema a la vez y además guarda la latencia base de la red y el `vmstat` de la instancia |
| `ejecutar_paralelo.ps1` | Corre cada perfil contra los dos sistemas al mismo tiempo (para ahorrar tiempo) con las mismas evidencias |
| `resumir.py` | Lee los CSV y genera las tablas de `RESULTADOS.md` y las gráficas de `evidencias/graficas/` |
| `RESULTADOS.md`, `REFLEXION.md` | Resultados medidos y su interpretación |
| `evidencias/` | CSV, reportes HTML, consola de Locust, latencia base, `vmstat` y gráficas |

## Contra qué se prueba

Las pruebas se ejecutan **contra la instancia GCP** (IP externa `34.135.84.31`), nunca contra `localhost` (el locustfile lo impide). Locust corre en la laptop; los sistemas corren en la instancia (e2-medium: 2 vCPU compartidas, 3.6 GB).

| Sistema | URL |
|---|---|
| Monolito | `http://34.135.84.31:3000` |
| login · books · pagos · pedidos · users · authors | `http://34.135.84.31:5000` … `:5005` |

## Rutas probadas (solo lecturas)

| Operación | Monolito (HTML) | Microservicios (JSON) | Peso `@task` |
|---|---|---|---|
| Catálogo completo | `GET /libros` | books `GET /api/books?page_size=100` | 4 |
| Búsqueda por título | `GET /libros?q=` | books `GET /api/books?titulo=` | 2 |
| Detalle de un libro | `GET /libros/{id}` | books `GET /api/books/{isbn}` | 3 |
| Autores | `GET /admin/autores` | authors `GET /authors` | 2 |
| Portada | `GET /` | — | 1 |
| Lecturas con JWT | — | users `GET /users`, pedidos `GET /orders`, pagos `GET /payments`, login `GET /session` | 1 c/u |

Las rutas salen del código del monolito (`src/app.js`, `src/modules/*/*.routes.js`) y de los OpenAPI / `app.py` de cada servicio. Cada usuario inicia sesión **una vez** al nacer (`POST /login`) y la cierra al terminar; no se crean, modifican ni borran datos. Las estadísticas separan cada destino por su prefijo: `[monolito]`, `[books]`, `[authors]`, `[users]`, `[pedidos]`, `[pagos]`, `[login]`. Las peticiones marcadas `(preparacion)` ocurren una vez por usuario (para obtener ids/ISBN reales) y no forman parte de la carga repetida.

## Perfiles (definidos en `locustfile.py`, variable `PERFIL`)

| Perfil | Usuarios | spawn_rate | Duración | Qué busca |
|---|---|---|---|---|
| `smoke` | 1 | 1/s | 30 s | Que el escenario y las rutas respondan bien |
| `load` | 5 | 1/s | 2 min | Comportamiento con la carga esperada |
| `stress` | 2 → 5 → 10 → 15 → 20 (18 s c/u) | 1–3/s | 90 s (el enunciado permite *hasta* 3 min) | Degradación al pasar de la carga esperada |
| `spike` | 2 → 15 (de golpe) → 2 | 15/s | 2 min (pico de 30 s) | Efecto del pico y recuperación |
| `soak` | 3 | 1/s | 4 min | Degradación sostenida (miniatura: un soak real dura horas) |
| `quiebre` | +1 cada 6 s, de 1 a 20 | 1/s | máx. 2 min (límite del enunciado: 4 min) | Usuarios con los que se incumple el umbral; al incumplir deja de subir, mantiene 20 s y termina |
| `exploratoria100` | rampa de 1/s hasta 100 | 1/s | 280 s | Opcional, fuera de lo requerido (no se ejecutó en la entrega) |

**Cómo se corrieron:** smoke y load, cada sistema por separado (`ejecutar_todas.ps1`). Stress, spike, soak y quiebre, por tiempo disponible, con los dos sistemas **en paralelo** (`ejecutar_paralelo.ps1`): comparten la misma VM durante esas pruebas, la condición es igual para ambos y el `vmstat` de la instancia muestra cuánta CPU se usó.

- **Pausa entre tareas (`wait_time`)**: 1 a 3 s aleatorios, igual en los dos sistemas.
- **Umbral de servicio**: degradado si el **p95 > 1 s** o los **errores > 5 %** (el de la práctica).
- **Timeout por petición**: 30 s; una petición más lenta cuenta como falla.
- Los perfiles se implementan con `LoadTestShape`, así que en la GUI los campos de usuarios y spawn rate los fija el perfil.

## Instalación (Windows 11, PowerShell)

```powershell
cd locust_tests
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
.\venv\Scripts\locust --version
```

## Credenciales

Algunas rutas exigen sesión (monolito) o JWT (users, pedidos, pagos, login `/session`). El correo y la contraseña se leen de variables de entorno **de la terminal actual**; no se escriben en ningún archivo:

```powershell
$env:LOCUST_EMAIL = 'correo-del-administrador'
$env:LOCUST_PASSWORD = Read-Host 'Contraseña'      # o deja que los scripts la pidan
```

## Uso con la interfaz web (GUI) en Windows 11

1. Abre PowerShell en `locust_tests` y define las credenciales (arriba) y el perfil:
   ```powershell
   $env:PERFIL = 'load'          # smoke | load | stress | spike | soak | quiebre
   ```
2. Inicia Locust con la IP de la instancia y el sistema a probar:
   ```powershell
   .\venv\Scripts\locust -f locustfile.py --host http://34.135.84.31 MonolitoUser
   ```
   (o `MicroserviciosUser`). Si Windows Defender pregunta por el acceso a la red, permite **redes privadas**.
3. Abre **http://localhost:8089** en el navegador (es la interfaz de Locust en tu máquina; la carga va a la instancia).
4. Revisa que *Host* sea `http://34.135.84.31` y presiona **Start**. Como el perfil es un `LoadTestShape`, Locust ajusta solo los usuarios.
5. Pestañas útiles:
   - **Statistics**: por cada petición, número, fallas, mediana, p95, p99, RPS.
   - **Charts**: RPS, tiempos de respuesta (mediana y p95) y número de usuarios en el tiempo.
   - **Failures**: qué peticiones fallaron y por qué (el locustfile da el motivo).
   - **Download Data**: CSV y reporte HTML de la corrida.
6. Para detener antes de tiempo: **Stop**. Para otra corrida, cambia `$env:PERFIL`, cierra Locust (Ctrl+C) y vuelve al paso 2.

## Uso sin interfaz (para las evidencias)

```powershell
.\ejecutar_prueba.ps1 -Perfil load -Sistema monolito
.\ejecutar_prueba.ps1 -Perfil load -Sistema microservicios
.\ejecutar_todas.ps1                     # todas, un sistema a la vez, con latencia base y vmstat
.\ejecutar_paralelo.ps1                  # stress, spike, soak y quiebre con ambos sistemas a la vez
.\ejecutar_prueba.ps1 -Perfil spike -Sistema monolito -Gui   # verla en vivo en http://localhost:8089
.\venv\Scripts\python resumir.py         # tablas y gráficas
```

Cada corrida deja en `evidencias/`: `<perfil>_<sistema>_stats.csv` (resumen por petición), `_stats_history.csv` (evolución cada segundo), `_failures.csv`, `<perfil>_<sistema>.html` (reporte con gráficas), `consola_*.txt`, `red_*.txt` (latencia base sin carga) y `vmstat_*.txt` (CPU/memoria de la instancia; columnas `us`/`sy` = CPU ocupada, `id` = libre, `r` = procesos esperando CPU).

## Cómo leer las métricas

- **RPS**: peticiones por segundo que el sistema atendió. Con pausas de 1–3 s, cada usuario genera ~0.5 RPS: el RPS está limitado por los usuarios, no por el servidor, mientras no haya saturación.
- **Mediana (p50)** y **p95**: la mitad / el 95 % de las peticiones tardó eso o menos. El p95 refleja la experiencia de los usuarios con peor suerte; un promedio puede esconderlos.
- **% errores**: fallas / peticiones. Incluye códigos distintos de 200 y respuestas con contenido incorrecto (p. ej. un redireccionamiento al login).
- Todo tiempo medido incluye la red laptop → GCP (~100 ms sin carga, ver `red_*.txt`). Una diferencia pequeña entre sistemas puede ser solo ruido de red.
- Un punto de quiebre medido en una prueba corta, con un solo generador de carga en una red compartida, **no** es la capacidad máxima real del sistema.
