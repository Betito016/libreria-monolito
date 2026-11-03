# Reflexión: pruebas de rendimiento con Locust

**1. Diferencias entre el monolito y los microservicios.** Ninguno de los dos incumplió el umbral en las 12 pruebas: 0 % de errores y p95 agregado ≤ 770 ms. Con las mismas operaciones, los microservicios tuvieron un p95 mayor en casi todas. En stress, el catálogo tuvo 170 ms en el monolito contra 320 ms en books; en soak, 460 ms contra 700 ms (tabla de comparables en `RESULTADOS.md`). El RPS fue prácticamente igual (stress: 5.27 contra 5.16), porque con pausas de 1 a 3 s el RPS lo fijan los usuarios y no el servidor. La evidencia más clara de la diferencia no es la arquitectura: el servidor de desarrollo de Flask responde `Connection: close` y cada petición abre una conexión TCP nueva, mientras que Node mantiene `keep-alive`. Lo comprobé con `curl`: en la segunda petición seguida el monolito no abrió conexión nueva (59 ms) y books sí (288 ms). Eso explica que una ruta pequeña tarde ~60 ms en el monolito y ~120 ms en los microservicios. El tamaño de la respuesta no lo explica: el detalle del monolito pesa 6.6 KB y tarda menos que el de books, que pesa 0.4 KB.

**2. Primera degradación.** `POST /login` en el spike: p95 de 1.8 s en el monolito y 1.2 s en el servicio login, por encima de 1 s. Lo determiné con tres evidencias que coinciden: la tabla por ruta de `spike_*_stats.csv`, la gráfica `spike_tiempo.png`, donde el p95 sube justo en el segundo 31, cuando entran 13 usuarios de golpe, y el `vmstat` de la instancia, que en ese mismo instante muestra 18 procesos esperando CPU. El login verifica la contraseña con bcrypt, que consume CPU a propósito, y 13 logins simultáneos en 2 vCPU compartidas se encolan. El p95 agregado no pasó de 1 s porque los logins son pocas peticiones dentro del total; por eso hay que mirar por ruta y no solo el agregado.

**3. Diferencias entre perfiles.**
- *Load* (5 usuarios fijos) mostró el comportamiento base: p95 de 170–180 ms, estable.
- *Stress* subió por escalones hasta 20 usuarios: el RPS creció casi lineal (≈ 1 → 10) sin que el p95 tuviera tendencia, así que no hubo saturación.
- *Spike* fue el único que mostró degradación temporal (la ráfaga de logins) y también recuperación: con 15 usuarios ya dentro, el p95 volvió a ~200 ms.
- *Soak* (3 usuarios, 4 min) no mostró deterioro con el tiempo: RPS plano en ~1.4 y p95 oscilante sin crecer.
- El *punto de quiebre* no se alcanzó: ambos llegaron a 20 usuarios sin incumplir. Solo puedo afirmar que el quiebre está por encima de 20 usuarios con estas rutas y pausas.

**4. Limitaciones.**
- **Red.** La más importante: probé desde la red de la universidad y la latencia base sin carga varió de 100 ms (smoke) a 439–960 ms (justo antes del spike). Por eso el soak, con 3 usuarios, tuvo un p95 mayor que el stress con 20. Esa diferencia es de la red, no del servidor, porque la CPU estuvo en 5–13 % de promedio.
- **Duración y concurrencia.** Las pruebas fueron cortas (stress de 90 s y quiebre de 2 min, por tiempo) y con poca concurrencia para encontrar el límite.
- **Generador y VM compartida.** Hubo un solo generador de carga, mi laptop. Stress, spike, soak y quiebre se corrieron con los dos sistemas en paralelo sobre la misma VM e2-medium; la condición fue igual para ambos, pero en el spike los logins de los dos compitieron por la CPU.
- **Datos.** Los dos sistemas no usan la misma base (`library_db` y `libreria_db`, unos 30 libros cada una).
- **Respuestas.** El monolito devuelve HTML y los servicios JSON; books además tiene caché Redis.
- **Rutas.** Solo se probaron lecturas.

**5. Uso de IA.** Una sugerencia útil fue definir los seis perfiles como `LoadTestShape` dentro del locustfile y validar cada respuesta con `catch_response`, en lugar de confiar solo en el código 200. Tuve que corregir y comprobar varias cosas:
- **Validación incompleta.** En mi primer stress del monolito escribí mal la contraseña: el 64 % de las peticiones falló porque las rutas redirigían a `/login`. Esa misma corrida mostró un error de la validación generada: `/admin/autores` sin sesión redirige a la portada con un 200 y se estaba contando como éxito (149 peticiones). Se corrigió para exigir que la página final sea la pedida, y el intento quedó documentado en `evidencias/descartadas/`.
- **Monolito no accesible.** Verifiqué que el monolito escuchaba solo en `127.0.0.1` y no era accesible por la IP externa.
- **Sesión real.** Verifiqué en el CSV que cada usuario hace un solo login y que el catálogo devuelve 15.9 KB (con sesión), y no la página de login de 1.4 KB.
- **Causa de la latencia.** Comprobé con `curl` el `Connection: close` de Flask antes de aceptar cualquier explicación.

Aprendí por mí mismo que un p95 solo significa algo junto con su contexto (latencia base de la red, CPU, número de muestras) y que un 0 % de errores no prueba nada si la validación acepta la página equivocada.

**6. Qué cambiaría.**
- **Servidor de producción para Flask.** Correr los servicios con gunicorn y keep-alive (o detrás de nginx con keep-alive al backend), porque el servidor de desarrollo cierra cada conexión y añade un viaje de red por petición.
- **Escalar el login.** Darle más workers o CPU al login, o limitar ráfagas de logins, porque bcrypt es lo primero que se satura.
- **Generador cerca de la instancia.** Lanzar Locust desde otra VM en la misma región de GCP, para que la red de la universidad no domine el p95.
- **Pruebas más completas.** Cada sistema por separado, con las duraciones completas del enunciado y una rampa más allá de 20 usuarios para encontrar el quiebre real.

**7. Qué indican las gráficas** (`evidencias/graficas/*_tiempo.png` y los reportes HTML). Cada gráfica tiene tres paneles con el tiempo en el eje X:
- **Usuarios activos:** confirma que el perfil se aplicó, por ejemplo la escalera 2-5-10-15-20 del stress o el salto 2→15→2 del spike.
- **p95 "actual":** ventana de unos 10 s, contra la línea roja de 1 s.
- **RPS y fallas por segundo.**

Qué muestra cada perfil:
- **Stress:** el RPS sube en escalones paralelos a los usuarios y el p95 se queda entre 150 y 480 ms. Los pequeños saltos coinciden con cada escalón, cuando entran usuarios nuevos y hacen login. Un sistema saturado mostraría el RPS estancado y el p95 subiendo; aquí no pasa.
- **Spike:** al entrar el pico el p95 cruza la línea de 1 s unos 10 s (monolito 1.8 s, microservicios 1.1 s) y luego cae a ~200 ms mientras el RPS se triplica (~7.5/s). La carga sostenida no era el problema; lo era la ráfaga de logins. Al volver a 2 usuarios aparece un pico de 1.5 s en microservicios con muy poco tráfico: con pocas peticiones en la ventana, una sola lenta (red) mueve el percentil.
- **Soak:** el RPS es plano y el p95 oscila entre 200 y 900 ms sin pendiente, así que no hay degradación acumulada. La oscilación es la red.
- **Comparables (`*_comparables_p95.png`):** en cada perfil la barra de microservicios queda por encima de la del monolito en catálogo, búsqueda y detalle, de forma consistente con el costo extra de la conexión nueva por petición.

En ninguna gráfica la línea de fallas sale de cero.
