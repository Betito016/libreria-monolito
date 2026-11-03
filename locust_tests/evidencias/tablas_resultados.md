## Resumen por prueba y sistema (fila Aggregated de Locust)

| Perfil | Sistema | Usuarios (máx) | Duración (s) | Peticiones | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Errores | Umbral (p95 ≤ 1 s y errores ≤ 5 %) |
|---|---|---|---|---|---|---|---|---|---|---|
| smoke | monolito | 1 | 30 | 16 | 0.54 | 110 | 260 | 260 | 0.00 % (0) | cumple |
| smoke | microservicios | 1 | 30 | 18 | 0.60 | 140 | 240 | 240 | 0.00 % (0) | cumple |
| load | monolito | 5 | 121 | 295 | 2.45 | 110 | 170 | 300 | 0.00 % (0) | cumple |
| load | microservicios | 5 | 121 | 281 | 2.34 | 120 | 180 | 220 | 0.00 % (0) | cumple |
| stress | monolito | 20 | 91 | 478 | 5.27 | 110 | 240 | 560 | 0.00 % (0) | cumple |
| stress | microservicios | 20 | 91 | 472 | 5.16 | 160 | 350 | 520 | 0.00 % (0) | cumple |
| spike | monolito | 15 | 122 | 337 | 2.78 | 100 | 530 | 1700 | 0.00 % (0) | cumple |
| spike | microservicios | 15 | 122 | 326 | 2.71 | 160 | 770 | 1100 | 0.00 % (0) | cumple |
| soak | monolito | 3 | 241 | 337 | 1.41 | 110 | 390 | 620 | 0.00 % (0) | cumple |
| soak | microservicios | 3 | 241 | 324 | 1.35 | 160 | 610 | 860 | 0.00 % (0) | cumple |
| quiebre | monolito | 20 | 121 | 654 | 5.39 | 97 | 160 | 410 | 0.00 % (0) | cumple |
| quiebre | microservicios | 20 | 121 | 634 | 5.25 | 120 | 220 | 480 | 0.00 % (0) | cumple |

## Punto de quiebre

- **monolito**: Se llegó a 20 usuarios (fin de la rampa, 120 s) sin incumplir el umbral.
- **microservicios**: Se llegó a 20 usuarios (fin de la rampa, 120 s) sin incumplir el umbral.

## p95 (ms) por operación comparable

| Perfil | Catálogo mono | Catálogo micro | Búsqueda mono | Búsqueda micro | Detalle mono | Detalle micro | Autores mono | Autores micro |
|---|---|---|---|---|---|---|---|---|
| smoke | 130 | 190 | 58 | 130 | 100 | 120 | 110 | 130 |
| load | 170 | 190 | 88 | 140 | 120 | 140 | 150 | 150 |
| stress | 170 | 320 | 120 | 180 | 110 | 190 | 170 | 270 |
| spike | 350 | 500 | 290 | 330 | 200 | 390 | 200 | 350 |
| soak | 460 | 700 | 300 | 590 | 310 | 590 | 390 | 660 |
| quiebre | 130 | 180 | 76 | 150 | 90 | 140 | 140 | 140 |

## Detalle por ruta (todas las corridas)

| Perfil | Sistema | Petición | Peticiones | Fallas | p50 | p95 | p99 | RPS |
|---|---|---|---|---|---|---|---|---|
| smoke | monolito | `[monolito] GET /` | 3 | 0 | 56 | 56 | 56 | 0.10 |
| smoke | monolito | `[monolito] GET /admin/autores` | 1 | 0 | 110 | 110 | 110 | 0.03 |
| smoke | monolito | `[monolito] GET /libros` | 7 | 0 | 110 | 130 | 130 | 0.23 |
| smoke | monolito | `[monolito] GET /libros (preparacion)` | 1 | 0 | 120 | 120 | 120 | 0.03 |
| smoke | monolito | `[monolito] GET /libros/{id}` | 2 | 0 | 100 | 100 | 100 | 0.07 |
| smoke | monolito | `[monolito] GET /libros?q=` | 1 | 0 | 58 | 58 | 58 | 0.03 |
| smoke | monolito | `[monolito] POST /login` | 1 | 0 | 260 | 260 | 260 | 0.03 |
| smoke | microservicios | `[authors] GET /authors` | 2 | 0 | 130 | 130 | 130 | 0.07 |
| smoke | microservicios | `[books] GET /api/books (preparacion)` | 1 | 0 | 190 | 190 | 190 | 0.03 |
| smoke | microservicios | `[books] GET /api/books/{isbn}` | 1 | 0 | 120 | 120 | 120 | 0.03 |
| smoke | microservicios | `[books] GET /api/books?page_size=100` | 6 | 0 | 160 | 190 | 190 | 0.20 |
| smoke | microservicios | `[books] GET /api/books?titulo=` | 1 | 0 | 130 | 130 | 130 | 0.03 |
| smoke | microservicios | `[login] POST /login` | 1 | 0 | 240 | 240 | 240 | 0.03 |
| smoke | microservicios | `[pagos] GET /payments` | 2 | 0 | 120 | 120 | 120 | 0.07 |
| smoke | microservicios | `[pedidos] GET /orders` | 2 | 0 | 140 | 140 | 140 | 0.07 |
| smoke | microservicios | `[users] GET /users` | 2 | 0 | 130 | 130 | 130 | 0.07 |
| load | monolito | `[monolito] GET /` | 20 | 0 | 59 | 160 | 160 | 0.17 |
| load | monolito | `[monolito] GET /admin/autores` | 48 | 0 | 110 | 150 | 190 | 0.40 |
| load | monolito | `[monolito] GET /libros` | 102 | 0 | 110 | 170 | 360 | 0.85 |
| load | monolito | `[monolito] GET /libros (preparacion)` | 5 | 0 | 130 | 170 | 170 | 0.04 |
| load | monolito | `[monolito] GET /libros/{id}` | 71 | 0 | 65 | 120 | 160 | 0.59 |
| load | monolito | `[monolito] GET /libros?q=` | 44 | 0 | 62 | 88 | 93 | 0.36 |
| load | monolito | `[monolito] POST /login` | 5 | 0 | 280 | 300 | 300 | 0.04 |
| load | microservicios | `[authors] GET /authors` | 41 | 0 | 120 | 150 | 1100 | 0.34 |
| load | microservicios | `[books] GET /api/books (preparacion)` | 5 | 0 | 160 | 180 | 180 | 0.04 |
| load | microservicios | `[books] GET /api/books/{isbn}` | 53 | 0 | 120 | 140 | 170 | 0.44 |
| load | microservicios | `[books] GET /api/books?page_size=100` | 69 | 0 | 160 | 190 | 220 | 0.57 |
| load | microservicios | `[books] GET /api/books?titulo=` | 41 | 0 | 120 | 140 | 190 | 0.34 |
| load | microservicios | `[login] GET /session` | 18 | 0 | 120 | 1100 | 1100 | 0.15 |
| load | microservicios | `[login] POST /login` | 5 | 0 | 210 | 220 | 220 | 0.04 |
| load | microservicios | `[pagos] GET /payments` | 15 | 0 | 120 | 140 | 140 | 0.12 |
| load | microservicios | `[pedidos] GET /orders` | 12 | 0 | 120 | 150 | 150 | 0.10 |
| load | microservicios | `[users] GET /users` | 22 | 0 | 120 | 150 | 160 | 0.18 |
| stress | monolito | `[monolito] GET /` | 45 | 0 | 58 | 130 | 210 | 0.50 |
| stress | monolito | `[monolito] GET /admin/autores` | 72 | 0 | 110 | 170 | 240 | 0.79 |
| stress | monolito | `[monolito] GET /libros` | 158 | 0 | 110 | 170 | 590 | 1.74 |
| stress | monolito | `[monolito] GET /libros (preparacion)` | 20 | 0 | 130 | 250 | 250 | 0.22 |
| stress | monolito | `[monolito] GET /libros/{id}` | 103 | 0 | 67 | 110 | 150 | 1.14 |
| stress | monolito | `[monolito] GET /libros?q=` | 60 | 0 | 62 | 120 | 140 | 0.66 |
| stress | monolito | `[monolito] POST /login` | 20 | 0 | 450 | 600 | 600 | 0.22 |
| stress | microservicios | `[authors] GET /authors` | 60 | 0 | 160 | 270 | 460 | 0.66 |
| stress | microservicios | `[books] GET /api/books (preparacion)` | 20 | 0 | 220 | 320 | 320 | 0.22 |
| stress | microservicios | `[books] GET /api/books/{isbn}` | 88 | 0 | 160 | 190 | 260 | 0.96 |
| stress | microservicios | `[books] GET /api/books?page_size=100` | 113 | 0 | 220 | 320 | 630 | 1.24 |
| stress | microservicios | `[books] GET /api/books?titulo=` | 60 | 0 | 130 | 180 | 270 | 0.66 |
| stress | microservicios | `[login] GET /session` | 31 | 0 | 160 | 190 | 920 | 0.34 |
| stress | microservicios | `[login] POST /login` | 20 | 0 | 400 | 520 | 520 | 0.22 |
| stress | microservicios | `[pagos] GET /payments` | 22 | 0 | 160 | 180 | 240 | 0.24 |
| stress | microservicios | `[pedidos] GET /orders` | 26 | 0 | 140 | 240 | 310 | 0.28 |
| stress | microservicios | `[users] GET /users` | 32 | 0 | 130 | 310 | 340 | 0.35 |
| spike | monolito | `[monolito] GET /` | 21 | 0 | 56 | 120 | 300 | 0.17 |
| spike | monolito | `[monolito] GET /admin/autores` | 45 | 0 | 120 | 200 | 380 | 0.37 |
| spike | monolito | `[monolito] GET /libros` | 97 | 0 | 110 | 350 | 750 | 0.80 |
| spike | monolito | `[monolito] GET /libros (preparacion)` | 15 | 0 | 190 | 250 | 250 | 0.12 |
| spike | monolito | `[monolito] GET /libros/{id}` | 82 | 0 | 85 | 200 | 490 | 0.68 |
| spike | monolito | `[monolito] GET /libros?q=` | 49 | 0 | 82 | 290 | 810 | 0.40 |
| spike | monolito | `[monolito] POST /login` | 15 | 0 | 1600 | 1800 | 1800 | 0.12 |
| spike | monolito | `[monolito] POST /logout` | 13 | 0 | 130 | 190 | 190 | 0.11 |
| spike | microservicios | `[authors] GET /authors` | 33 | 0 | 160 | 350 | 420 | 0.27 |
| spike | microservicios | `[books] GET /api/books (preparacion)` | 15 | 0 | 240 | 330 | 330 | 0.12 |
| spike | microservicios | `[books] GET /api/books/{isbn}` | 51 | 0 | 150 | 390 | 640 | 0.42 |
| spike | microservicios | `[books] GET /api/books?page_size=100` | 74 | 0 | 170 | 500 | 670 | 0.61 |
| spike | microservicios | `[books] GET /api/books?titulo=` | 47 | 0 | 160 | 330 | 1500 | 0.39 |
| spike | microservicios | `[login] GET /session` | 21 | 0 | 160 | 600 | 940 | 0.17 |
| spike | microservicios | `[login] POST /login` | 15 | 0 | 1100 | 1200 | 1200 | 0.12 |
| spike | microservicios | `[login] POST /logout` | 13 | 0 | 190 | 250 | 250 | 0.11 |
| spike | microservicios | `[pagos] GET /payments` | 19 | 0 | 130 | 770 | 770 | 0.16 |
| spike | microservicios | `[pedidos] GET /orders` | 15 | 0 | 150 | 770 | 770 | 0.12 |
| spike | microservicios | `[users] GET /users` | 23 | 0 | 130 | 430 | 580 | 0.19 |
| soak | monolito | `[monolito] GET /` | 34 | 0 | 59 | 300 | 320 | 0.14 |
| soak | monolito | `[monolito] GET /admin/autores` | 54 | 0 | 160 | 390 | 470 | 0.23 |
| soak | monolito | `[monolito] GET /libros` | 99 | 0 | 150 | 460 | 750 | 0.41 |
| soak | monolito | `[monolito] GET /libros (preparacion)` | 3 | 0 | 160 | 240 | 240 | 0.01 |
| soak | monolito | `[monolito] GET /libros/{id}` | 89 | 0 | 79 | 310 | 400 | 0.37 |
| soak | monolito | `[monolito] GET /libros?q=` | 55 | 0 | 66 | 300 | 320 | 0.23 |
| soak | monolito | `[monolito] POST /login` | 3 | 0 | 780 | 780 | 780 | 0.01 |
| soak | microservicios | `[authors] GET /authors` | 53 | 0 | 120 | 660 | 740 | 0.22 |
| soak | microservicios | `[books] GET /api/books (preparacion)` | 3 | 0 | 330 | 340 | 340 | 0.01 |
| soak | microservicios | `[books] GET /api/books/{isbn}` | 56 | 0 | 160 | 590 | 900 | 0.23 |
| soak | microservicios | `[books] GET /api/books?page_size=100` | 88 | 0 | 230 | 700 | 930 | 0.37 |
| soak | microservicios | `[books] GET /api/books?titulo=` | 42 | 0 | 160 | 590 | 650 | 0.17 |
| soak | microservicios | `[login] GET /session` | 25 | 0 | 160 | 480 | 560 | 0.10 |
| soak | microservicios | `[login] POST /login` | 3 | 0 | 570 | 650 | 650 | 0.01 |
| soak | microservicios | `[pagos] GET /payments` | 18 | 0 | 190 | 740 | 740 | 0.07 |
| soak | microservicios | `[pedidos] GET /orders` | 14 | 0 | 160 | 430 | 430 | 0.06 |
| soak | microservicios | `[users] GET /users` | 22 | 0 | 130 | 520 | 860 | 0.09 |
| quiebre | monolito | `[monolito] GET /` | 59 | 0 | 56 | 71 | 90 | 0.49 |
| quiebre | monolito | `[monolito] GET /admin/autores` | 108 | 0 | 100 | 140 | 340 | 0.89 |
| quiebre | monolito | `[monolito] GET /libros` | 178 | 0 | 110 | 130 | 160 | 1.47 |
| quiebre | monolito | `[monolito] GET /libros (preparacion)` | 20 | 0 | 100 | 610 | 610 | 0.16 |
| quiebre | monolito | `[monolito] GET /libros/{id}` | 167 | 0 | 62 | 90 | 120 | 1.38 |
| quiebre | monolito | `[monolito] GET /libros?q=` | 102 | 0 | 59 | 76 | 190 | 0.84 |
| quiebre | monolito | `[monolito] POST /login` | 20 | 0 | 280 | 660 | 660 | 0.16 |
| quiebre | microservicios | `[authors] GET /authors` | 65 | 0 | 120 | 140 | 580 | 0.54 |
| quiebre | microservicios | `[books] GET /api/books (preparacion)` | 20 | 0 | 150 | 840 | 840 | 0.17 |
| quiebre | microservicios | `[books] GET /api/books/{isbn}` | 122 | 0 | 120 | 140 | 200 | 1.01 |
| quiebre | microservicios | `[books] GET /api/books?page_size=100` | 177 | 0 | 150 | 180 | 700 | 1.47 |
| quiebre | microservicios | `[books] GET /api/books?titulo=` | 79 | 0 | 120 | 150 | 480 | 0.65 |
| quiebre | microservicios | `[login] GET /session` | 47 | 0 | 120 | 130 | 130 | 0.39 |
| quiebre | microservicios | `[login] POST /login` | 20 | 0 | 230 | 390 | 390 | 0.17 |
| quiebre | microservicios | `[pagos] GET /payments` | 35 | 0 | 120 | 150 | 150 | 0.29 |
| quiebre | microservicios | `[pedidos] GET /orders` | 37 | 0 | 120 | 140 | 150 | 0.31 |
| quiebre | microservicios | `[users] GET /users` | 32 | 0 | 120 | 160 | 720 | 0.27 |

Generado por resumir.py el 2026-11-03T15:36:33.
