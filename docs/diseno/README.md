# Diseño del checklist de habilitantes

Producido con `/design`, base visual `new-landing` ([`../estilo-base.md`](../estilo-base.md)).

- Lienzo publicado: https://claude.ai/code/artifact/3aad237a-22d1-41ac-be9c-9f341cbb9ad0
- Artboards: `Main.dc.html` (checklist por grupo), `Visor.dc.html` (requisito
  sobre la página real del PDF), `p37.jpg` (página 37 reducida), `canvas.json`.

## Decisiones

1. **Titular accionable**: "Le faltan 3 cosas para quedar habilitado en el
   Grupo 1", no "20 requisitos". Selector de grupo/lote como tabs-pastilla.
2. **Cuatro estados con cuatro iconos**: check sobre acento = cumple; ✕ en
   acento-2 = no cumple; círculo punteado = falta documento; "?" = revisar.
   El rojo se reserva a lo que impide presentarse (no cumple / falta).
3. **Agrupado por urgencia**, no por categoría: primero "lo que impide
   presentarse hoy", luego "revisar", luego lo que cumple. La categoría
   (jurídico/financiero/técnico/experiencia) es un chip, no una sección.
4. **Cada fila enlaza a la página** ("p. 37 →") y el visor muestra la página
   renderizada con el fragmento resaltado en acento translúcido; a la
   izquierda el requisito, su verificación con las cifras, y el fragmento
   citado en bloque de papel.
5. Umbrales que no vienen en el PDF (Matriz 2) quedan en "revisar" aunque el
   dato cumpla, y la nota al pie lo dice.
