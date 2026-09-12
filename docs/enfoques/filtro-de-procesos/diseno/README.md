# Diseño del filtro de procesos

Producido con `/design` (Claude Design dentro de Claude Code), usando como
base el estilo de `new-landing` según [`../estilo-base.md`](../estilo-base.md).

- Lienzo publicado: https://claude.ai/code/artifact/1b5a1bec-077a-4d90-af35-3fdf327a68fa
- Artboards (fuente, se pueden re-sembrar): `Main.dc.html` (lista de
  procesos), `Detalle.dc.html` (detalle con razones), `canvas.json` (layout).

## Decisiones de diseño

1. **Layout de app** (sidebar 230 px + panel principal con gradiente cálido),
   el mismo de la maqueta del hero de la landing: la pantalla interna se ve
   como lo que la landing promete.
2. **El rojo solo marca lo recomendado.** "Presentarse" lleva tag en
   `--ad-accent-soft` y puntaje en `--ad-accent-2`; "Revisar" va en tinta
   neutra; "No presentarse" se apaga (tinta .50, tag con borde y sin relleno).
3. **Tres cifras arriba** (presentarse / revisar / no presentarse) con barra
   proporcional, y una pastilla con las horas ahorradas: es la promesa
   ("deje de presentarse a lo que no puede ganar") convertida en número.
4. **Detalle en 5/7**: izquierda el veredicto (recomendación grande, puntaje,
   horas que se ahorra y "si igual quiere ir"), derecha dos tarjetas:
   habilitantes como checklist (check rojo = cumple, círculo hueco = no) y
   señales como lista "por qué" con `+N`/`−N` a la derecha.
5. Toda cifra lleva la evidencia en tinta .50 al lado, y cada pantalla cierra
   con una nota de fuente/limitación (`.ad-foot-note`).
