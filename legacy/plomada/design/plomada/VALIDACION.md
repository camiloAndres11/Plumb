# Registro de validacion de la paleta

Generado con el validador del sistema de diseno (`scripts/validate_palette.js`
de la skill `dataviz`), contra la superficie clara de Modernist `#f3f2f2`.
Las cifras NO se estimaron a ojo: se corrieron. Si alguien cambia un token de
`dataviz.css`, tiene que volver a correr esto y actualizar el registro.

## 1. Por que no hay paleta categorica

La pregunta era si los pasos neutros de Modernist podian portar identidad de
serie junto al acento. La respuesta es no, y es medible:

```

Palette (light, surface #f3f2f2, categorical): 2 slots
  [FAIL] Lightness band         outside band: [["#2d2b2b",0.291]]
  [FAIL] Chroma floor           below floor (reads gray): [["#2d2b2b",0.003]]
  [PASS] CVD separation         worst all-pairs #2d2b2b↔#ec3013 ΔE 22.4 (protan) · tritan 42.2
  [PASS] Normal-vision floor    worst all-pairs #2d2b2b↔#ec3013 ΔE 39.0 (normal)
  [PASS] Contrast vs surface    all 2 >= 3:1

  → FAILED — fix the marked checks  (CVD in the 6–8 floor band is legal ONLY with secondary encoding: direct labels, gaps, or texture)
  scope: categorical palettes only. For a lone status/text color check WCAG text contrast; for a sequential ramp, lightness monotonicity.

```

Lo que dice: la SEPARACION es enorme (ΔE 39,0 normal / 22,4 protanopia, muy por
encima de los pisos de 15 y 8). Lo que reprueba es el piso de croma — un gris
con C=0,003 se lee como "sin marcar", no como "la categoria B". Distinguibles
si; categorias no.

Por eso el grafo y el dumbbell codifican identidad por FORMA (relleno vs hueco)
y reservan el acento para el hallazgo. No se le agrego ningun hue a Modernist.

## 2. La rampa secuencial de la coropleta

Primero se probaron los pasos claros del acento. Todos reprueban el extremo
claro contra el fondo:

```
contraste de los pasos de la rampa accent contra el fondo #f3f2f2
  accent-100 #fff2ef  1.02:1
  accent-200 #ffe0d9  1.11:1
  accent-300 #ffc4b8  1.36:1
  accent-400 #ff9783  1.88:1
  accent-500 #ff563c  2.83:1
  accent-600 #dd2b0f  4.25:1
  accent-700 #ae1800  6.41:1
  accent-800 #7c1405  9.59:1
  accent-900 #4d170e  13.01:1

```

accent-100 a accent-400 se quedan entre 1,02:1 y 1,88:1 contra `#f3f2f2`, bajo
el piso de 2:1. El metodo manda "snap al paso valido mas cercano": accent-500.
Con cinco clases desde ahi, todo pasa:

```

Palette (light, surface #f3f2f2, ordinal ramp): 5 slots
  [PASS] Lightness monotone     steps read light→dark
  [PASS] Adjacent ΔL            all gaps >= 0.06
  [PASS] Light-end contrast     #ff563c at 2.83:1 vs surface
  [PASS] Single hue             hue spread 0°

  → ALL CHECKS PASS  (ordinal: one hue, monotone L, visible step gaps, light end clears surface)
```

## 3. Lo que queda pendiente y por que

- **Modo oscuro: HECHO** (2026-08-23, `docs/PLAN_TEMA_API_MCP.md` F1). Ya no
  queda fuera de alcance: el set de tokens oscuros esta ELEGIDO y razonado en
  `design/plomada/tema.css`, colgado de `:root[data-tema="oscuro"]`, y se
  conmuta con un boton en el nav. La rampa neutra va invertida a proposito
  (100 = mas oscuro, relleno; 900 = mas claro, texto sobre relleno): se
  conserva el ROL de cada paso y cambia la direccion de la luz. La rampa de
  acento NO se invierte, solo sube de luminosidad para respirar sobre
  `#14100f`.
  **Sigue pendiente** re-correr `validate_palette.js --mode dark --surface
  #14100f` sobre la rampa secuencial y anotar aqui el resultado: el contraste
  de la banda oscura se verifico a ojo, no con el validador.
- **La leyenda no es opcional.** Con 2 o mas series va siempre, porque la
  identidad no puede depender del color solo.
- **Cada grafico conserva su gemelo en tabla.** Ya era requisito del proyecto y
  aqui ademas es el relieve que exige el metodo.
