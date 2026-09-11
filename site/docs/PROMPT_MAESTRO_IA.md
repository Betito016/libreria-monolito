# Prompt Maestro para Evolución Controlada con IA

Ejercicio 02 · Integración de Aplicaciones Computacionales · UDEM
Tarea 2e (Trabajo en Casa).

## Qué es esto

Este archivo documenta la **disciplina** que se siguió al pedirle cambios a un asistente de IA (Claude Code) sobre
este proyecto, y sirve como plantilla reutilizable para futuras mejoras. El objetivo no es "usar IA por usar IA",
sino que cada cambio quede acotado, sea verificable, y el estudiante pueda explicarlo sin la herramienta — tal
como lo exige la sección "Consideración sobre el uso de Inteligencia Artificial" del enunciado.

## Plantilla del prompt maestro

Para pedir una mejora pequeña y verificable, la estructura que se usó (y que se recomienda reutilizar) es:

```
Necesidad/problema: <qué está mal o falta, en una frase concreta — no "mejora el código"
                     sino algo específico y verificable>
Contexto relevante: <archivos/documentos involucrados>
Restricciones:
  - No rompas funcionalidad existente sin decirlo explícitamente.
  - Si no puedes probar el cambio en vivo (sin BD/infraestructura disponible), dilo
    explícitamente en vez de asumir que funciona.
  - Cambios pequeños y reversibles; nada especulativo fuera de lo pedido.
Pide:
  1. Diagnóstico breve de la causa.
  2. El cambio mínimo necesario.
  3. Cómo se verificó (comando ejecutado + resultado, o "pendiente de verificar contra
     entorno real" si no fue posible).
```

## Ejemplo real de esta sesión (prompt exacto conservado)

**Fecha:** 2026-08-31.
**Necesidad/problema:** los documentos generados usaban emojis de colores (marca de verificación, X, advertencia,
lupa, reloj de arena) como marcadores de estado, lo cual el usuario consideró poco profesional para un entregable
de ingeniería.

**Prompt exacto del usuario** (conservado tal cual, sin editar):

> "tambien te iba a comentar que si podemos evitar usar emojis porque le quitan un poco lo profesional, si es
> posible podemos usar symbols como este ✓, pero si no hay un remplazo o algo asi en symbol para un emoji solo no
> uses emojis porfavor"

**Respuesta relevante de la IA:** se definió un vocabulario de 3 símbolos de texto plano (`✓` completado/aprobado,
`~` parcial o verificado solo por revisión de código, `✗` pendiente/no implementado), consistente en todos los
documentos, y se reemplazaron mecánicamente los 6 emojis usados hasta ese momento (marca de verificación en
verde, X en rojo, advertencia con y sin variante de color, lupa, reloj de arena) por ese vocabulario mediante un
script que recorrió los 3 archivos `.md` existentes.

**Archivos modificados:** `docs/REQUIREMENTS.md`, `docs/SECURITY_REVIEW.md`, `docs/TEST_PLAN.md` (27, 21 y 70
reemplazos respectivamente).

**Riesgo introducido:** bajo — es un reemplazo de caracteres en texto Markdown, sin tocar código ejecutable ni
lógica. El único riesgo real era dejar un reemplazo a medias (un emoji sin sustituir, o un símbolo mal aplicado
que cambiara el significado de un estado).

**Pruebas ejecutadas:** un script de verificación (Node.js) que recorrió recursivamente todo el repositorio
(excluyendo `node_modules`/`.git`) buscando los 6 códigos de emoji originales, confirmando `0` coincidencias
después del cambio.

**Resultado:** aprobado — los tres archivos quedaron sin emojis, con el vocabulario `✓`/`~`/`✗` aplicado de forma
consistente, y ese mismo vocabulario se siguió usando en todos los documentos creados después (incluido este).

## Dónde ver el resto de las interacciones

Este fue un ejemplo pequeño y aislado, elegido porque es fácil de verificar de principio a fin. La sesión completa
tuvo muchas más interacciones (creación de `docs/`, corrección de brechas de seguridad, reorganización de `db/`,
verificación en vivo contra PostgreSQL local) — todas quedan registradas en `docs/AI_PROMPT_HISTORY.md` y
`docs/AI_CHANGELOG.md`, con el mismo nivel de detalle (qué se pidió, qué cambió, qué riesgo tenía, cómo se
verificó).
