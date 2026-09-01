# Tarea 2c — Evaluación Arquitectónica

Ejercicio 02 · Integración de Aplicaciones Computacionales · UDEM
Trabajo en Casa. ~600 palabras. No cambia la arquitectura del ejercicio — analiza sus trade-offs como ingeniero.

---

El monolito server-side (Node.js + Express + EJS, acceso directo a PostgreSQL) es la decisión correcta para este
ejercicio específico, y lo es por razones que van más allá de que el enunciado lo exija. El sistema tiene siete
entidades relacionadas entre sí (libros, autores, géneros, formatos, conceptos, imágenes, usuarios), un solo rol
con privilegios de escritura (Administrador), y lo construye una sola persona en un plazo acotado. En ese
contexto, un monolito minimiza la variable que más cuesta en un proyecto pequeño: la coordinación. No hay que
versionar un contrato de API entre frontend y backend, no hay que decidir dónde vive la validación (¿cliente o
servidor?, aquí la respuesta es "servidor, siempre"), y un solo `git clone` más `npm install` deja el sistema
completo funcionando. La organización por módulos (`routes/controller/model/views` por entidad, más una fábrica
compartida para los cuatro catálogos idénticos) ya da la separación de responsabilidades que normalmente se usa
para justificar romper un sistema en servicios — se puede tener disciplina de diseño sin pagar el costo operativo
de una arquitectura distribuida.

Comparado con una **solución desacoplada por componentes** (API REST/GraphQL detrás, un frontend SPA como React
consumiendo esa API), la diferencia central es dónde vive la complejidad. Una SPA mejoraría la experiencia de
usuario (actualizaciones parciales de página, estado de UI más rico) a cambio de introducir un segundo lenguaje de
formato de intercambio (JSON), un segundo conjunto de validaciones (cliente y servidor tienen que estar de
acuerdo), y la necesidad de exponer un backend que hoy no existe como superficie pública. Para un catálogo de
libros con CRUD y navegación por página completa, ese costo no se paga con nada: el patrón Post/Redirect/Get que
ya usa la aplicación resuelve la usabilidad básica (evita reenvíos de formulario al recargar) sin la complejidad
adicional. Donde una arquitectura desacoplada sí ganaría es en **mantenibilidad a largo plazo con equipos más
grandes**: un equipo de frontend y uno de backend pueden trabajar en paralelo sin pisarse, algo irrelevante cuando
el equipo es una sola persona.

Frente a **microservicios**, la comparación es todavía más desfavorable para el escenario actual. Microservicios
resuelven un problema que este sistema no tiene: escalar de forma independiente partes con perfiles de carga muy
distintos (por ejemplo, un servicio de búsqueda con mucho más tráfico que el de administración de usuarios), o
permitir que equipos autónomos desplieguen sin coordinarse entre sí. A cambio, exigen infraestructura que aquí no
existe ni se justifica: descubrimiento de servicios, comunicación entre procesos (colas, gRPC, o REST interno),
observabilidad distribuida (trazas que crucen varios servicios), y una estrategia de consistencia de datos cuando
cada servicio tiene su propia base — nada de esto tiene sentido para 32 libros y un solo administrador. El
**tamaño del equipo** es, de hecho, el factor más determinante de los seis pedidos: la regla práctica (a veces
llamada "ley de Conway invertida") es que la arquitectura de software tiende a reflejar la estructura del equipo
que la construye; forzar microservicios sobre un equipo de una persona solo multiplica el trabajo de
infraestructura sin ningún beneficio de paralelización real.

En **seguridad**, el monolito no es automáticamente más o menos seguro — depende de la disciplina aplicada, no de
la arquitectura. Aquí se ganó en superficie de ataque (no hay una API pública adicional que asegurar, un solo
punto de entrada detrás del reverse proxy) pero se perdió aislamiento de fallos: un error no manejado en el
módulo de imágenes comparte el mismo proceso que el de autenticación, mientras que en microservicios un fallo
suele quedar contenido a un solo servicio.

**Qué condición futura justificaría migrar:** si el catálogo creciera a miles de títulos con búsqueda pesada, si
se necesitara una app móvil nativa consumiendo los mismos datos, o si el equipo creciera a varias personas
trabajando en paralelo sobre partes independientes, ahí sí valdría la pena pagar el costo de desacoplar — hoy,
para este alcance, sería sobre-ingeniería.
