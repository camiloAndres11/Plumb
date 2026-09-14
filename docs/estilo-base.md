# Estilo base: la landing de Pliego (`new-landing`)

Resumen de los tokens y componentes de `plataforma/static/landing.css` y
`plataforma/static/landing.html` (copiados de `legacy/plomada/plomada/`) en la rama `new-landing` (commit `06ce4fb`, "rebranding").
Es la referencia visual de todos los prototipos: **tema oscuro único, acento
rojo usado con avaricia, tipografía Archivo, pastillas redondas y paneles de
vidrio**. Cada rama `feature/*` copia este archivo y se lo pasa a `/design`.

## 1. Identidad

- Marca: **Pliego.** (con punto), logotipo de tres barras horizontales
  (`.ad-logo-mark`: la primera barra en rojo, las otras dos en tinta oscura
  sobre un cuadrado de papel).
- Tono: comercial, directo, en usted. Frases cortas: "Menos SECOP, más obra."
- Prefijo de clases: `ad-` (heredado de "Adjudica"). Los prototipos pueden usar
  su propio prefijo, pero deben reutilizar los **tokens `--ad-*`** tal cual.

## 2. Paleta (tokens `--ad-*`)

| Token | Valor | Uso |
|---|---|---|
| `--ad-bg` | `#0b0b0d` | Fondo de página. Único tono: **no hay modo claro** |
| `--ad-ink` | `#f2f0ee` | Texto principal |
| `--ad-ink-85/80/75/70/65/60/55/50/45/22` | `rgba(242,240,238,.NN)` | Escala de texto secundario. `.55` para metadatos, `.50` para kickers, `.22` para texto "apagado" |
| `--ad-accent` | `#ec3013` | El rojo de Modernist. Solo para: punto de la badge, barra "caliente", tag, número destacado. **Nunca fondos grandes** |
| `--ad-accent-2` | `#ff8a72` | Rojo claro para texto sobre oscuro (porcentajes, "por qué" positivo) |
| `--ad-accent-3` | `#ffb4a0` | Rojo aún más claro, brillos |
| `--ad-accent-soft` | `rgba(236,48,19,.18)` | Fondo de `.ad-tag` y del gradiente de paneles |
| `--ad-panel` / `-2` / `-3` | `#121214` / `#17171a` / `#141416` | Fondos de tarjeta, marco de maqueta |
| `--ad-glass` / `-2` | `rgba(20,20,23,.9/.85)` | Tarjetas de vidrio (`.ad-card`, `.ad-window`) |
| `--ad-warm` / `-2` | `#3a2a26` / `#2b1f1c` | Gradientes cálidos de fondo (hero, escenario) |
| `--ad-line` / `-2` / `-3` / `-soft` / `-faint` | `rgba(255,255,255,.10/.12/.15/.08/.06)` | Bordes. `.10` por defecto, `.06` separadores finos |
| `--ad-fill` / `-2` / `-3` / `-4` / `-hover` | `rgba(255,255,255,.07/.06/.05/.04/.08)` | Rellenos sutiles de filas y chips |
| `--ad-paper` / `--ad-paper-ink` / `--ad-paper-mute` | `#f2f0ee` / `#1a1a1c` / `#8a8580` | Botón primario "papel" (fondo claro, texto oscuro) y el bloque de borrador |

Semántica de estado (derivada del landing, para los prototipos):
- **Positivo / recomendado / "caliente"**: `--ad-accent-2` en texto, `.ad-bar-hot` (gradiente rojo).
- **Neutral / revisar**: tinta `.70` y barra gris (`--ad-ink-70`).
- **Negativo / descartado / apagado**: tinta `.50`–`.55`, sin acento.
- No hay verde ni amarillo en el sistema. Si un prototipo necesita "cumple",
  usar el check blanco sobre círculo de acento (`.ad-check-on`), y para "no
  cumple" el círculo hueco (`.ad-check-off`).

## 3. Tipografía

- Familia: `"Archivo", system-ui, sans-serif`, **auto-hospedada** en
  `/static/fonts/archivo-latin*.woff2` (pesos 400/600/800; 500/700 se interpolan).
  Sin Google Fonts en tiempo de carga.
- Escala:
  - H1 hero: 76px / 1.05 / letter-spacing −.035em / peso 500
  - H2 sección: 48px / 1.1 / −.03em / 500. Segunda línea en `.dim` (tinta .45)
  - H3: 32px / 1.15 / −.025em / 500
  - Intro grande: 32px / 1.3 / −.02em / 400
  - Título de ventana/tarjeta: 20–22px / 600 / −.02em
  - Cuerpo: 15–16px / 1.5–1.6; secundario 13–14px; kicker 12px mayúsculas con
    `letter-spacing: .06em` en tinta .50
  - Cifra grande ("72 %"): 28px/600 en filas; 96px / .9 / −.05em en tarjeta de
    probabilidad, color `--ad-accent-2`
- Números siempre con `font-variant-numeric: tabular-nums` (`.num`, `.ad-pct`).
- Español con tildes, unidades con espacio fino ("72 %", "$2.140 mill.").

## 4. Espaciado y forma

- Contenedor: `--ad-max: 1120px`, gutter `32px`.
- Secciones: `padding: 60px gutter 140px`; hero `120px` arriba.
- Radios: **999px** para pastillas, botones, tabs, barras; `12–14px` filas;
  `18px` tarjetas y ventanas; `22–28px` marcos grandes (escenario, maqueta).
- Sombra: `--ad-shadow: 0 30px 80px rgba(0,0,0,.5)`.
- Movimiento: `--ad-ease: cubic-bezier(.2,0,0,1)`; entrada `adRise` (36px →
  0, .9s); revelado al scroll condicionado a `html.ad-js` (sin JS todo visible).
- Grillas de dos columnas: `ad-grid-5-7`, `ad-grid-4-8`, cabecera `7fr/5fr`.

## 5. Componentes (con su HTML de referencia)

- **Nav** (`.ad-nav`): sticky, blur 14px, logo izquierda, enlaces 15px tinta .80,
  CTA en pastilla con relleno `.08` y borde `.12`.
- **Badge** (`.ad-badge`): pastilla con punto rojo (`.ad-dot`) + texto 14px.
  Variante `.ad-dot-mute` gris; `.ad-dot-pulse` parpadea.
- **Botón primario** (`.ad-btn`): papel claro sobre oscuro, 16px/28px,
  pastilla, sombra opcional. **Fantasma** (`.ad-btn-ghost`): borde `.20`.
- **Tag** (`.ad-tag`): 12px/600, fondo `--ad-accent-soft`, texto `--ad-accent-2`.
  Para "Nueva", "3 nuevas", "El más elegido".
- **Chip** (`.ad-chip`): 13px, relleno `.08`. Para categorías del perfil.
- **Barra** (`.ad-bar` 4px, `-6`, `-8`): pista `--ad-line`, relleno gris o
  `.ad-bar-hot` (gradiente `accent → accent-2`). Ancho via `--w`.
- **Fila de proceso** (`.ad-row` / `.ad-mock-row`): grid `1fr auto auto`,
  `<b>` título 15px, `<small>` metadatos 13px .55, tag y `.ad-pct` a la derecha.
  `.on` = seleccionada (relleno `.06`).
- **Ventana** (`.ad-window`): barra superior con texto 13px .55 y tres puntos,
  cuerpo 22px de padding, `.ad-window-title` 20px/600.
- **Tarjeta** (`.ad-card`): vidrio, borde `.10`, padding 28px, `.ad-card-label`
  13px .55 arriba.
- **Tarjeta de probabilidad** (`.ad-prob`): cifra 96px en accent-2 + subtítulo
  + barra 6px caliente.
- **Lista "por qué"** (`.ad-why`): filas `texto … +/−`, separadas por línea
  `.08`; el `+` en accent-2, el `−` y su fila en tinta .60/.50.
- **Competidores** (`.ad-comp`): nombre + "3 de 5 · ofrece al 97 %" + barra 8px;
  la fila propia (`.you`) en negrita y barra caliente.
- **Checklist** (`.ad-check`): filas con círculo (check blanco sobre acento =
  hecho; hueco = pendiente, fila en `.todo`).
- **Borrador** (`.ad-draft`): bloque de **papel** (fondo `--ad-paper`, texto
  `--ad-paper-ink`), kicker arriba, `.note` en `--ad-paper-mute`.
- **Maqueta de app** (`.ad-mock-frame`): sidebar 230px con items (icono 16px +
  texto 14px, `.on` con relleno) y área principal con gradiente cálido; es
  el layout de referencia para las pantallas internas del producto.
- **Tabs** (`.ad-tabs`): pastilla contenedora con borde, tab activo con fondo
  `--ad-line` y peso 600. Teclado con flechas.
- **Pie**: aviso legal en tinta .55: "Las probabilidades son estimaciones…".

## 6. Reglas para los prototipos

1. Fondo `--ad-bg` siempre; ningún modo claro.
2. El rojo es señal, no decoración: un elemento caliente por vista.
3. Toda cifra lleva su "por qué" al lado (lista `.ad-why`) y una nota de
   fuente/limitación en `.ad-foot-note`.
4. Layout interno = maqueta de app: sidebar de navegación + panel principal.
5. Sin dependencias de CDN; fuentes locales; JS vanilla sin bundler.
