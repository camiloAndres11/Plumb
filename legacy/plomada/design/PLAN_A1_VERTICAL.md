<!-- Plan derivado del lienzo de diseno "Plomada — Nueva web", variante
     "A1 · Vertical" (pagina "Variantes A"):
     https://claude.ai/code/artifact/07eda5b5-8f95-434b-8b74-5cc8ce931e71
     Decision de tono ya tomada con el usuario: titulares que MIDEN, no que
     acusan. El mockup manda en intencion; este plan manda en implementacion. -->

# Plan A1 · Vertical — rediseno de la web de Plomada

Plan de accion para que un agente lo implemente sin mas contexto que este
archivo y el repo. Extiende (no reemplaza) `design/PLAN_DISENO.md`: el
sistema, los tokens y las vistas ya existen y funcionan; esto es una capa
encima. El nucleo del rediseno son **tres movimientos**:

1. Una **banda oscura estructural** arriba (nav + cabecera de portada) y
   abajo (pie) de cada vista, presente en los dos tonos.
2. Una **portada** con hero grande en la banda, linea de plomada colgante,
   franja de cifras con reglas de 2px por columna y una seccion nueva de
   tarjetas de vistas.
3. Un **titular que mide en vez de acusar**: sale "La plomada revela lo que
   esta torcido", entra "La obra publica, medida contra la vertical."

**Leer antes de tocar nada, en este orden:**

1. `design/VENDOR.md` — que es vendor, que es capa propia, como se compone `estilo.css`.
2. `design/modernist/readme.md` — el sistema: clases, tokens, Do/Don't.
3. `docs/PLAN_TEMA_API_MCP.md` §3–§4 — el conmutador de tono y por que
   `tema.css` se compone de ultimo.
4. `design/PLAN_DISENO.md` §1 — las restricciones no negociables originales.
5. `plomada/README.md` — las vistas, la prueba de privacidad, el vocabulario.

## 1. Restricciones NO negociables

Todas las de `design/PLAN_DISENO.md` §1 siguen vigentes. Las que mas pesan
aqui, mas las nuevas de este plan:

1. **`design/modernist/` no se edita.** Ni un caracter.
2. **`plomada/static/estilo.css` no se edita a mano.** Se regenera con
   `python3 design/construir.py` despues de CADA cambio de CSS.
3. **Cero dependencias externas en tiempo de carga.** El mockup del lienzo
   carga Archivo desde Google Fonts SOLO para previsualizar; el sitio real
   sigue con `design/plomada/fuentes.css` (auto-hospedada). No copiar el
   `<link>` de fonts.googleapis.com bajo ningun concepto:
   `construir.py` y `tests/test_privacidad_red.py` lo tumban.
4. **Mono acento.** Ningun hex nuevo. Todo color por token
   (`var(--color-*)`). Dentro de la banda oscura el acento correcto
   (`#ff5334`, afinado para fondo oscuro) lo entrega el propio sistema de
   tokens — no hardcodear ni "corregir" nada a mano.
5. **Radio 0, reglas de 2px (`--pl-regla`), todo flush left.** Nada centrado.
6. **Tono editorial: medir, no acusar.** Ningun titular nuevo puede afirmar
   conducta. El vocabulario prohibido de `plomada/test_privacy.py` tumba el
   build; ademas, por decision de este rediseno, "torcido" desaparece del H1.
   La salvedad ("indicio, no acusacion") se conserva en todos los lugares
   donde ya esta: `aviso_fijo()`, `.cierre`, pie.
7. **Cifras reales unicamente.** Este plan NO cambia ninguna cifra ni agrega
   ninguna: solo re-estiliza las que `build.py` ya emite.
8. **Sin cursivas en titulares, sin chrome falso, sin emoji.**
9. **Decoracion: sigue habiendo UN solo adorno** (Tier A, CSS puro): la linea
   de plomada. Este plan la muda de sitio y le da pesa nueva; no autoriza un
   segundo adorno.

## 2. La decision central: banda ESTRUCTURAL, no tono

La banda oscura del hero/pie de A1 es **estructura de pagina**, no el tema
del usuario. Conviven asi:

- El conmutador de tono sigue igual (`data-tema` en `<html>`, delta en
  `tema.css`). No se toca ni `TEMA_INLINE`, ni `static/tema.js`, ni el boton.
- La banda estructural es un wrapper `.banda-oscura` que recibe el MISMO
  delta de tokens. En tono claro, la pagina es clara con cabecera y pie
  oscuros (el diseno A1); en tono oscuro, banda y pagina comparten fondo y
  la cabecera se funde con el contenido — **deliberado, no un bug**: los
  separa el layout, no un borde extra.

### 2.1 `design/plomada/tema.css` — un solo cambio, quirurgico

El bloque de tokens oscuros pasa de un ambito a dos, **sin duplicar una sola
declaracion** (misma prohibicion de dos fuentes de verdad que ya rige para
`prefers-color-scheme`):

```css
/* antes */
:root[data-tema="oscuro"] {

/* despues */
:root[data-tema="oscuro"],
.banda-oscura {
```

Nada mas cambia en ese archivo. Las custom properties se heredan, asi que
todo lo que caiga dentro de `.banda-oscura` (nav, botones, kicker, hero)
resuelve los tokens oscuros solo: acento `#ff5334`, tinta `#f2ebe8`,
sombras de banda oscura. Actualizar el comentario de cabecera del archivo
para que documente el segundo ambito.

`color-scheme: dark` queda incluido en el bloque: correcto, los controles
nativos dentro de la banda (el boton de tema) acompanan.

## 3. Plantilla: `plomada/build.py`

### 3.1 `pagina()` gana el parametro `cabecera`

Firma nueva (parametro con default, ninguna llamada existente se rompe):

```python
def pagina(titulo, descripcion, cuerpo, ruta, head="", js="", clase="", cabecera=""):
```

El esqueleto del body cambia de:

```html
<a class="saltar" ...>...</a>
{nav(canon)}
<main id="principal">...</main>
<footer class="pie">...</footer>
```

a:

```html
<a class="saltar" ...>...</a>
<div class="banda-oscura banda-cab">
{nav(canon)}
{cabecera}
</div>
<main id="principal">...</main>
<footer class="banda-oscura banda-pie">
  <div class="pie">
    <p class="aviso">{C.AVISO}</p>
    <p>Datos públicos del SECOP II. <a href="/metodologia/">Cómo se calcula</a> ·
       <a href="/datos/">Descargar los datos</a></p>
  </div>
</footer>
```

- El pie conserva su contenido EXACTO (arquetipo statement, decidido en
  `sitio.css`); solo se envuelve para que el fondo oscuro sangre a todo el
  ancho mientras `.pie` conserva su medida de 1100px.
- `cabecera=""` (el default) da a toda vista interior una banda delgada:
  solo el nav sobre fondo oscuro. **Unicamente la portada pasa cabecera.**

### 3.2 `nav()`: el Asistente entra como CTA

`/asistente/` hoy no esta en la navegacion (solo se llega desde el tablero
y desde `/api/`). En A1 es el CTA del nav. En `nav()`:

```python
def nav(ruta_actual):
    enlaces = "".join(...)  # igual que hoy
    actual = ' aria-current="page"' if ruta_actual.rstrip("/") == "/asistente" else ""
    cta = f'<a class="btn btn-primary nav-cta" href="/asistente/"{actual}>Asistente</a>'
    return (f'<header class="nav"><a class="nav-brand" href="/">Plomada</a>'
            f'{enlaces}{cta}{BOTON_TEMA}</header>')
```

`NAV_ENLACES` no se toca (el CTA es un elemento distinto, no un enlace mas).
El texto del brand sigue siendo `Plomada` en el HTML; la version PLOMADA en
mayusculas la pone CSS (§5.1) — asi lectores de pantalla siguen oyendo
"Plomada".

### 3.3 `portada()`: el hero se muda a la banda

El bloque `<header class="hero">...</header>` sale de `cuerpo` y se pasa
como `cabecera=` en la llamada a `pagina()`. Dentro del hero, dos cambios
de texto y ninguno mas:

- H1: `La obra pública, medida contra la vertical.`
- Se agrega, tras la `.bajada`, la salvedad corta ya existente como parrafo
  `<p class="bajada">{C.AVISO_CORTO} <a href="/metodologia/">Cómo se calcula.</a></p>`
  — reutiliza `contenido.py`, no redacta nada nuevo.

Kicker, lema, bajada y los dos CTAs (`Buscar un contrato` primario,
`Ver el mapa` secundario) se conservan letra por letra.

`cuerpo` queda entonces: isla `cifra-lider` → `.cab-grid.cifras` →
municipios → tarjetas de contratos → **seccion nueva de vistas (§3.4)** →
`.cierre`. El `.cierre` (campo de acento con "Un indicio no es una
acusación.") **se conserva tal cual**: es el activo de tono del proyecto y
en A1 sigue siendo el unico campo de acento de la portada.

### 3.4 Seccion nueva: las cuatro puertas

Entre las tarjetas de contratos y el `.cierre`, una seccion `caja` con
cuatro tarjetas Modernist (`.card`) en una reticula propia `.vistas`:

```html
<section class="caja"><h2>Cómo explorar Plomada</h2>
  <div class="vistas">
    <a class="card elev-sm" href="/tablero/"><span class="card-kicker">Vista</span>
      <b class="card-title">Tablero</b>
      <span class="card-meta">Los indicios agregados, por grupo y por departamento.</span></a>
    <a class="card elev-sm" href="/mapa/"><span class="card-kicker">Vista</span>
      <b class="card-title">Mapa</b>
      <span class="card-meta">Cada obra sobre el territorio, hasta el municipio.</span></a>
    <a class="card elev-sm" href="/buscar/"><span class="card-kicker">Vista</span>
      <b class="card-title">Buscador</b>
      <span class="card-meta">Por entidad, contratista o proceso, con su evidencia.</span></a>
    <a class="card elev-sm" href="/asistente/"><span class="card-kicker">Nuevo</span>
      <b class="card-title">Asistente</b>
      <span class="card-meta">Pregúntele a los datos en lenguaje natural, vía MCP.</span></a>
  </div>
</section>
```

Sin iconos, sin emoji: tipografia y las clases de tarjeta que Modernist ya
trae. El kicker "Nuevo" hereda el acento de `.card-kicker`: suficiente.

## 4. Que vista recibe que

| Vista | Banda de cabecera | Cambios propios |
|---|---|---|
| `/` portada | Profunda: nav + hero completo | §3.3, §3.4, §5 |
| tablero, mapa, buscar, metodologia, datos, api, asistente | Delgada: solo nav | Ninguno (su `.cab`/hero interior queda en `main`, banda clara) |
| contrato, municipio (shells hidratados) | Delgada: solo nav | Ninguno. Nada de la banda depende de JS |

No mover los `.cab` interiores a la banda en esta pasada: las fichas se
hidratan en cliente y la banda no debe contener nada dinamico. Si mas
adelante se quiere cabecera profunda en vistas interiores, sera otro plan.

## 5. CSS: bloques a agregar en `design/plomada/sitio.css`

Todo va en una seccion nueva al final, titulada
`/* ─── A1 · Vertical: banda estructural ─── */`. Solo tokens; cero hex.

### 5.1 Banda y nav

```css
.banda-oscura { background: var(--color-bg); color: var(--color-text); }
.banda-cab { display: flex; flex-direction: column; }
/* bajo la banda, en tono claro, la transicion banda→pagina la hace el
   contraste mismo; no agregar borde (en tono oscuro dibujaria una regla
   fantasma en mitad de un fondo continuo) */

.nav .nav-brand {
  text-transform: uppercase; letter-spacing: 0.06em;
  font-family: var(--font-heading); font-weight: var(--font-heading-weight);
}
.nav .nav-cta { padding: var(--space-2) var(--space-3); font-size: var(--pl-text-sm); }
```

Comprobar en `design/modernist/readme.md` como dimensiona `.btn` Modernist:
si el `.btn` ya queda bien a escala de nav, la regla de `.nav-cta` sobra —
preferir siempre la clase vendor tal cual antes que corregirla.

### 5.2 Hero en banda: medidas y linea de plomada

El hero ya no vive dentro de `main#principal`, asi que carga su propio
contenedor de 1100px. El riel izquierdo actual (`.hero::before/::after`,
que sigue sirviendo al `.caja.hero` del tablero) se anula en este contexto
y la plomada pasa a colgar a la derecha, de arriba del todo hasta la base
del hero, rematada en pesa:

```css
.banda-cab .hero {
  max-width: 1100px; margin-inline: auto; width: 100%;
  padding: var(--pl-space-12) var(--space-4) var(--pl-space-16);
}
@media (min-width: 768px) { .banda-cab .hero { padding-inline: var(--space-8); } }

.banda-cab .hero h1 {
  font-size: var(--pl-text-display); line-height: 1.02; max-width: 18ch;
  letter-spacing: -0.02em;
}
.banda-cab .hero .lema, .banda-cab .hero .bajada { max-width: 52ch; }

/* la plomada: linea que cae desde la regla del nav */
.banda-cab .hero { position: relative; padding-left: var(--space-4); }
.banda-cab .hero::before {
  left: auto; right: var(--space-8);
  top: 0; bottom: var(--pl-space-12);
}
.banda-cab .hero::after {
  left: auto; right: calc(var(--space-8) - 6px); bottom: calc(var(--pl-space-12) - 18px);
  width: 14px; height: 20px;
  clip-path: polygon(0 0, 100% 0, 100% 45%, 50% 100%, 0 45%);
}

/* el nav comparte la reticula de la pagina, o la plomada no cae donde debe */
@media (min-width: 768px) { .nav { padding-inline: var(--space-8); } }
@media (max-width: 959px) {
  .banda-cab .hero::before, .banda-cab .hero::after { display: none; }
}
@media (min-width: 768px) {
  .banda-cab .hero { padding-left: var(--space-8); }
}
```

Notas de intencion, para no "corregir" lo correcto:

- `top: 0` es el borde superior del hero, que ES el borde inferior del nav:
  la plomada cuelga DESDE la estructura, ese es el gesto del mockup, pero
  sin atravesarla. (La primera version decia `top: calc(-1 * var(--pl-space-12))`
  para "descontar el padding del hero"; es un error de caja: un pseudo-elemento
  absoluto se posiciona contra la caja de RELLENO, no contra el contenido, asi
  que esos 48px metian la linea dentro del nav, encima del conmutador de tono.)
- La pesa remata `--pl-space-12` por encima del filo inferior de la banda, no
  pegada a el: en tono claro ese filo es el corte oscuro/claro de la pagina y
  una pesa que lo cruza se lee como recortada, no como rematada.
- El nav tiene que llevar el MISMO padding lateral que `main#principal`, `.pie`
  y el hero (16px, 32px desde 768px). Modernist se lo fija en 16px siempre; sin
  el override el nav queda 16px corrido a la izquierda respecto de todo lo demas
  y la plomada, que cuelga del borde derecho de la columna de texto, cae encima
  del ultimo elemento del nav.
- La pesa es el mismo pseudo-elemento cuadrado de siempre con `clip-path`
  de cinco puntos: CSS puro, cero SVG nuevo.
- A menos de 960px linea y pesa desaparecen: en pantallas angostas no hay
  margen derecho del que colgar sin pisar texto.
- Los colores no se declaran: `::before/::after` ya usan
  `var(--color-accent)`, que dentro de la banda resuelve al acento afinado
  para oscuro. No tocar.

### 5.3 Pie en banda

```css
.banda-pie .pie { border-top: 0; }
/* la regla superior del pie la reemplaza el cambio de banda; conservarla
   dibujaria un hairline duplicado en tono oscuro */
```

`.pie` conserva su medida, padding y jerarquia actuales.

### 5.4 Franja de cifras con reglas por columna

Sustituir el borde de bloque por una regla de 2px POR COLUMNA, y subir el
numero sobre la etiqueta (solo presentacion; el DOM `dt/dd` no cambia):

```css
.cab-grid.cifras { border-block: 0; }
.cab-grid.cifras .dato {
  flex-direction: column-reverse; justify-content: flex-end;
  border-top: var(--pl-regla) solid var(--color-text);
  padding-top: var(--space-3);
}
.cab-grid.cifras .dato dd { font-size: var(--pl-text-2xl);
  font-family: var(--font-heading); font-weight: var(--font-heading-weight); }
```

El tablero hereda `.cifras` en sus tiles: ese cambio de estilo alcanza al
tablero A PROPOSITO — es lo que mantiene una sola franja de cifras en todo
el sitio. Verificarlo visualmente en `/tablero/`, no "arreglarlo".

### 5.5 Reticula de vistas

```css
.vistas { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--space-3); }
@media (min-width: 640px) { .vistas { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (min-width: 960px) { .vistas { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
.vistas .card { text-decoration: none; color: inherit;
  transition: box-shadow var(--pl-dur) var(--pl-ease); }
.vistas .card:hover { box-shadow: var(--shadow-md); }
.vistas .card:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
```

## 6. Textos que cambian (lista COMPLETA)

| Donde | Antes | Despues |
|---|---|---|
| `portada()`, H1 | `La plomada revela lo que está torcido` | `La obra pública, medida contra la vertical.` |
| `portada()`, hero | — | Parrafo nuevo con `C.AVISO_CORTO` + enlace a metodologia (§3.3) |
| `portada()`, seccion nueva | — | El bloque literal de §3.4 |
| `nav()` | — | CTA `Asistente` (§3.2) |

**Nada mas.** `LEMA`, `C.AVISO`, lema, bajada, `.cierre`, metadescripciones
y todo el contenido de las demas vistas quedan letra por letra como estan.
Un cambio de texto fuera de esta tabla es un error de implementacion.

## 7. Orden de trabajo

Cada paso deja el repo verde (build + tests). Un commit por paso.

1. **Banda minima.** §2.1 (`tema.css`) + §3.1 (`pagina()`) + §5.1 y §5.3
   (CSS) + `python3 design/construir.py`. Resultado visible: todas las
   vistas con nav y pie en banda oscura, contenido intacto.
2. **Nav CTA.** §3.2 + su CSS. Resultado: Asistente accesible desde todo el
   sitio.
3. **Portada.** §3.3 + §5.2 (hero y plomada) + §5.4 (cifras). Resultado: la
   portada A1 completa menos la seccion de vistas.
4. **Vistas.** §3.4 + §5.5. Resultado: portada A1 completa.
5. **Pasada de verificacion** (§8) y captura de pantalla de portada y
   tablero en claro y oscuro para el registro del PR.

## 8. Verificacion (obligatoria, en este orden)

```bash
python3 design/construir.py          # regenera estilo.css; falla si hay URL externa
cd plomada && python3 build.py       # borra site/ si la prueba de privacidad falla
cd .. && python3 -m pytest tests/ -q # formato, calidad, privacidad de red
node --test tests/test_formato.mjs   # si el runner de mjs no corre via pytest
```

Checklist visual (servir con `python3 -m http.server -d plomada/site 8765`),
en 320px, 768px y 1280px, en tono claro Y oscuro:

- [ ] Portada: banda oscura arriba con nav + hero; H1 nuevo; plomada
      colgando a la derecha en ≥960px, ausente debajo; sin scroll
      horizontal en ninguna anchura.
- [ ] Cifras: cuatro columnas con regla de 2px arriba, numero sobre
      etiqueta; el tablero muestra el mismo tratamiento en sus tiles.
- [ ] Vistas: 1 / 2 / 4 columnas segun anchura; foco visible al tabular.
- [ ] `.cierre` (campo rojo) sigue presente y es el unico campo de acento.
- [ ] Pie oscuro en todas las vistas; sin hairline duplicado en oscuro.
- [ ] Tono oscuro: la banda se funde con el fondo (deliberado) y NADA mas
      cambia respecto a hoy en el contenido de `main`.
- [ ] Conmutador de tono: funciona dentro de la banda, icono visible,
      focus-visible legible sobre fondo oscuro.
- [ ] Sin peticiones de red externas: pestana Network limpia (solo
      excepciones ya documentadas: Esri click-to-load en fichas).
- [ ] `grep -ri "googleapis" plomada/site/` devuelve vacio.

## 9. Fuera de alcance / prohibido en esta pasada

- Tocar `design/modernist/`, `dataviz.css`, `VALIDACION.md` o cualquier
  grafico. La dataviz vive en banda clara de `main` y no participa.
- Cambiar cifras, agregar metricas, testimonios o logos.
- Mover los `.cab` de vistas interiores a la banda (§4).
- Un `@media (prefers-color-scheme: dark)` nuevo, donde sea.
- Redisenar `.cierre`, el aviso fijo o cualquier texto fuera de §6.
- Google Fonts, CDNs, SVGs nuevos, fuentes de iconos, imagenes.
