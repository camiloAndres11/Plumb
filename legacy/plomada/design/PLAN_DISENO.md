<!-- Hallmark · pre-emit critique: P5 H5 E4 S5 R5 V4 -->
<!-- Hallmark · plan: sistema-gestionado (Modernist) · genero: editorial ·
     macroestructura portada: Stat-Led · nav: .nav Modernist · pie: statement ·
     enriquecimiento: none (solo tipografia) · tema: bloqueado, no rota -->

# Plan de diseno web de Plomada

Plan de accion para que un agente lo implemente sin mas contexto que este
archivo y el repo. El objetivo NO es inventar un diseno nuevo: es **terminar
la capa de diseno que falta**, dentro del sistema ya elegido y vendorizado.

**Leer antes de tocar nada, en este orden:**

1. `design/VENDOR.md` — que es vendor, que es capa propia, como se compone `estilo.css`.
2. `design/modernist/readme.md` — el sistema: clases, tokens, Do/Don't.
3. `design/plomada/VALIDACION.md` — por que la dataviz codifica por FORMA y no por color.
4. `plomada/README.md` — las vistas, la prueba de privacidad, el vocabulario prohibido.
5. `README.md` raiz, seccion "Tablero" — decisiones ya tomadas (sin modo oscuro, Esri click-to-load).

## 0. Diagnostico (medido, no estimado)

El generador (`plomada/build.py`) emite HTML con dos vocabularios de clase, y
la hoja compuesta (`plomada/static/estilo.css`) solo cubre uno:

- **Clases de pagina sin NINGUNA regla CSS** (grep contra `estilo.css` da 0):
  `.hero .lema .bajada .cta .caja .principal .tarjeta .tarjetas .tabla .cifras
  .cab-grid .dato .pie .aviso .aviso-fijo .migas .saltar .nota .vacio .num
  .grande .destacado .tenue .cab .tipo .valor .sec`
- **Duplicados de componentes que Modernist ya trae con otro nombre**:
  `.tabla` (existe `.table`), `.btn sec` (existe `.btn-secondary`),
  `.tarjeta` (existe `.card` + `.card-kicker/-title/-meta`).

Resultado actual: el sitio renderiza con los estilos de elemento de Modernist
(body, h1-h4) y poco mas. Funciona, pero no esta disenado. Este plan cierra
esa brecha en dos movimientos: (a) alinear el HTML con los componentes que
Modernist ya tiene, (b) crear la capa de pagina que Modernist no tiene.

## 1. Restricciones NO negociables

Violarlas rompe tests o decisiones documentadas del proyecto:

1. **`design/modernist/` no se edita.** Ni un caracter. Todo lo nuevo vive en
   `design/plomada/` (VENDOR.md).
2. **`plomada/static/estilo.css` no se edita a mano.** Lo genera
   `python3 design/construir.py`. Cualquier cambio entra por una pieza de
   `design/plomada/`.
3. **Cero dependencias externas en tiempo de carga.** Sin CDN, sin
   Google Fonts, sin npm. `construir.py` falla si queda una URL externa;
   `tests/test_privacidad_red.py` vigila el resto. La unica excepcion es Esri
   (tiles satelitales), que ya es click-to-load y asi se queda.
4. **Dos bandas con conmutador explicito** (revocado el 2026-08-23 por
   `docs/PLAN_TEMA_API_MCP.md` §3, que supersede la decision del 2026-08-22).
   El delta oscuro vive en `design/plomada/tema.css`, colgado de
   `:root[data-tema="oscuro"]`. `prefers-color-scheme` se usa **solo** para
   el tono inicial de quien nunca eligio; tras su primer clic manda su
   eleccion. No agregar un `@media (prefers-color-scheme: dark)` suelto:
   duplicaria el bloque de tokens y crearia dos fuentes de verdad.
5. **Mono acento `#ec3013` usado con avaricia.** No introducir hues nuevos.
   La identidad de serie en graficos la lleva la FORMA (relleno vs aro),
   no el color — esta medido en VALIDACION.md. Si se toca un token de
   `dataviz.css`, hay que re-correr el validador y actualizar VALIDACION.md.
6. **Radio 0, reglas de 2px, todo flush left** — titulares, parrafos y
   etiquetas de boton. Nada centrado, nada redondeado (readme de Modernist).
7. **Vocabulario.** "corrupto", "fraude", "delito", "robo", "culpable" y
   similares tumban el build (`test_privacy.py`). El tono editorial es
   "indicio, no acusacion" y la salvedad viaja con cada cifra.
8. **Cifras reales unicamente.** Toda cifra visible sale de los datos
   (`site/datos/*.json`, CSVs) o de las que build.py ya emite. **Prohibido
   inventar metricas, testimonios o logos.** Si falta un dato: `—` con nota
   "por confirmar", nunca un numero plausible.
9. **Sin cursivas en titulares** (`font-style: normal` en display). Enfasis
   con peso 800 o con el acento, no con italica.
10. **Sin chrome falso**: nada de barras de navegador dibujadas, marcos de
    telefono ni ventanas de codigo con puntitos.

## 2. Arquitectura CSS: una pieza nueva

Crear **`design/plomada/sitio.css`** — la capa de pagina del proyecto — y
registrarla en `design/construir.py` como pieza 4 de la composicion:

```
1. design/plomada/fuentes.css    (Archivo auto-hospedada)
2. design/modernist/styles.css   (vendor, sin su @import)
3. design/plomada/dataviz.css    (extension de graficos)
4. design/plomada/sitio.css      (NUEVO: layout y componentes de pagina)
5. design/plomada/tema.css       (agregada despues: delta de la banda oscura)
```

Primera linea de `sitio.css` (registro durable de este plan):

```css
/* Hallmark · macrostructure: Stat-Led · tone: editorial-arquitectonico · anchor hue: 25 (rojo #ec3013)
 * sistema: Modernist vendorizado · pie: statement · enriquecimiento: none */
```

Reglas internas de `sitio.css`:

- **Solo tokens.** Cada color y fuente referencia `var(--color-*)` /
  `var(--font-*)` de Modernist. Cero hex sueltos. Si hace falta un valor
  nuevo (p. ej. escala tipografica), se declara como token propio con
  prefijo `--pl-` en un bloque `:root` al inicio de `sitio.css` y se
  referencia por nombre.
- **Tokens nuevos permitidos** (unicos):

  ```css
  :root {
    /* escala tipografica (Modernist no trae una) */
    --pl-text-display: clamp(2.5rem, 1.2rem + 5vw, 4.25rem); /* la cifra lider */
    --pl-text-3xl:     clamp(1.9rem, 1.1rem + 3vw, 2.75rem); /* h1 de pagina  */
    --pl-text-2xl:     1.5rem;    /* h2 de seccion */
    --pl-text-xl:      1.19rem;   /* h3 / lema     */
    --pl-text-md:      1rem;      /* cuerpo        */
    --pl-text-sm:      0.875rem;  /* meta, notas   */
    --pl-text-xs:      0.75rem;   /* kickers       */
    /* extension de la escala de espacio de Modernist (4pt) */
    --pl-space-12: 48px;
    --pl-space-16: 64px;
    --pl-space-24: 96px;
    /* medida de lectura */
    --pl-medida: 65ch;
    /* movimiento */
    --pl-dur: 140ms;
    --pl-ease: cubic-bezier(0.2, 0, 0, 1);
  }
  ```
- Numeros tabulares en toda celda numerica:
  `font-variant-numeric: tabular-nums` en `.table .num, .cifras, .valor`.

## 3. Alinear el HTML con Modernist (en `plomada/build.py`)

Donde Modernist ya tiene el componente, usarlo y borrar el duplicado:

| Hoy en build.py | Cambiar a | Nota |
|---|---|---|
| `class="tabla"` | `class="table"` | El `.num/.destacado/.tenue` se conservan como modificadores propios. |
| `class="btn sec"` | `class="btn btn-secondary"` | |
| `class="tarjeta"` | `class="card elev-sm"` con `card-kicker` (n de senales), `card-title` (objeto), `card-meta` (entidad · municipio · valor) | El kicker en `--color-accent` ya lo da Modernist. |
| `class="tag ..."` para banderas | `.tag-accent` (fuerte) / `.tag-neutral` (contexto) / `.tag-outline` (atenuada, p. ej. consorcios) | Mapea 1:1 con los pesos del glosario. |

**Antes de renombrar, grep obligatorio** en `plomada/static/*.js`,
`plomada/static/graficos/*.js` y `tests/` (hay tests .mjs/.py de formato):
cualquier selector `.tabla`/`.tarjeta` usado por JS o tests se actualiza en el
mismo commit. No renombrar a ciegas.

Lo que NO se renombra (capa de pagina, no existe en Modernist): `.hero .caja
.cifras .pie .aviso-fijo .migas .saltar .nota .cab`. Esas las define
`sitio.css`.

## 4. Diseno por vista

Todas las vistas comparten: nav Modernist arriba (ya en el HTML), reglas
horizontales de 2px (`--color-divider`) entre secciones mayores, contenido en
retícula visible, ancho maximo de pagina 1100px con gutter `--space-4` (16px)
en movil y `--space-8` en escritorio.

### 4.1 Portada `/` — macroestructura Stat-Led

La cifra ES el argumento. Estructura en orden DOM:

1. **Hero tipografico, flush left, sin imagen.**
   - Kicker (`.card-kicker` suelto o clase propia): `Obra publica · SECOP II · datos abiertos`.
   - H1 en `--pl-text-3xl`, ≤50 caracteres:
     `La plomada revela lo que esta torcido.` (roman, peso 800).
   - El lema y la bajada actuales se conservan como parrafos (`--pl-text-xl`
     y `--pl-text-md`, medida ≤ `--pl-medida`).
   - CTAs actuales (`Buscar un contrato` primario, `Ver el mapa` secundario),
     etiquetas flush left dentro del boton (lo da Modernist).
   - **Motivo de plomada (unico adorno permitido, Tier A, CSS puro):** una
     linea vertical de 2px en `--color-accent` que cae desde el borde superior
     del hero hasta la cifra lider, rematada en un cuadrado de 8px (la pesa).
     Es un `::before` posicionado; en movil se oculta. Nada mas de decoracion.
2. **La cifra lider** (nueva seccion, el "stat" del Stat-Led): tomar la fila
   mas fuerte de `La cifra en pesos` que ya exporta el pipeline —
   `$31,2 billones adjudicados sin competencia real (un solo oferente)` — en
   `--pl-text-display`, con su salvedad pegada en `--pl-text-sm`:
   `14,9% del universo · indicio, no acusacion`. Fuente del dato:
   `site/datos/` (no hardcodear si el JSON ya lo trae; si no lo trae, usar la
   cifra que build.py ya emite).
3. **Franja de cifras** `.cifras` (ya existe en HTML): 4 celdas de igual
   ancho separadas por reglas verticales de 1px, numero en `--pl-text-2xl`
   peso 800, etiqueta arriba en `--pl-text-xs` mayusculas con tracking.
4. **Tabla de municipios** (ya existe): pasa a `.table`; la nota metodologica
   ("nunca por la cruda") se queda visible encima, no en tooltip.
5. **Contratos con mas senales** → 6 `.card` en reticula de 3 (escritorio) /
   1 (movil).
6. **Banda de cierre en acento** (el "poster statement" que el readme de
   Modernist reserva para el cierre de landing): fondo `--color-accent`,
   texto `--color-bg`, display grande flush left:
   `Un indicio no es una acusacion.` + una linea que explica y enlaza
   metodologia y descarga de datos. Es el UNICO lugar de la portada donde el
   rojo corre como campo.

### 4.2 Ficha de contrato `/contrato/<id>/`

- Migas (`.migas`) en `--pl-text-sm`, separador `·`.
- Cabecera: objeto del contrato como H1 (`--pl-text-2xl`, puede ser largo:
  `overflow-wrap: anywhere`), debajo entidad, municipio, valor en fila de
  metadatos.
- **La barra de puntaje** (`barra_score`): barra horizontal plana, relleno
  `--color-accent-600`, fondo `--color-neutral-200`, altura 8px, radio 0,
  con el umbral (6 puntos) marcado como regla vertical de 2px de tinta.
- **Banderas por grupo**: cada grupo bajo un H2 con regla 2px; cada bandera
  es una fila (no card): tag de peso a la izquierda, nombre, y la evidencia
  `ev_*` en mono-espaciado no — en Archivo `--pl-text-sm` `--color-neutral-700`.
  Las atenuadas (consorcios) en `.tag-outline` + texto de la razon visible.
- Aviso fijo "indicio, no acusacion" (`.aviso-fijo`): franja
  `--color-accent-100`, texto `--color-accent-800`, borde superior e inferior
  1px `--color-accent-300`, sticky NO (estatico arriba del contenido).
- Mapa satelital: se conserva el click-to-load; el boton es `.btn
  btn-secondary` y explica por que hay que pulsar ("no se le pide nada a Esri
  hasta que usted lo pida").

### 4.3 Buscador `/buscar/`

- Filtros con `.field/.input/.seg` de Modernist (ya existen los componentes).
- **8 estados en los controles**: default, hover, focus-visible, active,
  disabled, cargando (busqueda en curso), error (sin resultados: mensaje
  `.nota .vacio` con sugerencia de aflojar filtros), exito (n resultados).
  Modernist ya da hover/focus/disabled; `sitio.css` agrega cargando/vacio.
- Resultados en `.table` ordenable; boton de exportar CSV como `.btn-ghost`.

### 4.4 Mapa `/mapa/` y municipio `/municipio/<slug>/`

- La coropleta ya usa la rampa validada (accent-500→900, VALIDACION.md §2).
  No tocarla. Leyenda SIEMPRE visible (no opcional).
- La tabla gemela del mapa se mantiene al lado/debajo — cada grafico conserva
  su gemelo en tabla (requisito del proyecto).
- Pagina de municipio: misma anatomia que la ficha (migas, H1, franja de
  cifras chica, tabla de contratos).

### 4.5 Metodologia `/metodologia/` — macroestructura Long Document

- Medida de lectura `--pl-medida`, H2 con regla 2px, tabla de banderas en
  `.table` con el peso como `.tag`.
- Aqui SI se permite numeracion de secciones (contenido genuinamente ordinal:
  las decisiones metodologicas 1-12), apilada vertical: numero arriba,
  titulo debajo, misma columna. **Prohibido** el patron etiqueta-izquierda /
  titulo-derecha en dos columnas.

### 4.6 Tablero `/tablero/`

Ya disenado y validado (dataviz.css + VALIDACION.md). Este plan NO lo
redisena. Solo: (a) heredara la tipografia de `sitio.css`, (b) verificar tras
el cambio que los 5 graficos siguen legibles en 320px, (c) `.caja .hero
.valor .grande` del tablero pasan a estar definidos por `sitio.css` en vez de
no existir.

### 4.7 Pie de pagina (todas las vistas) — arquetipo statement

No es el pie de 4 columnas de enlaces. Es: regla 2px arriba, el aviso
("indicio, no acusacion") como parrafo destacado `--pl-text-md` en medida de
lectura, y UNA fila de enlaces (`Metodologia · Datos · SECOP II · GitHub`) en
`--pl-text-sm`. Flush left todo.

## 5. Interaccion y movimiento

- Presupuesto de movimiento: **3 primitivas maximo** — (1) tint de hover que
  Modernist ya trae, (2) pressed `translateY(1px)` en `.btn:active`,
  (3) transicion de opacidad ≤`--pl-dur` al cargar resultados del buscador.
  Nada de scroll-reveal, parallax ni contadores animados.
- Solo se animan `transform` y `opacity`, con `--pl-ease`. Nunca `ease` del
  navegador, nunca rebote.
- `prefers-reduced-motion: reduce` → toda transicion espacial colapsa a
  opacidad ≤150ms.
- `:focus-visible` ya lo da Modernist (anillo acento 2px): **no re-estilizar
  por pagina y no animar su aparicion**.
- `.saltar` (skip link): visualmente oculto hasta `:focus-visible`, entonces
  aparece arriba-izquierda como `.btn` primario. Hoy no tiene estilo: es de
  las primeras reglas a escribir.

## 6. Responsive — piso duro, verificar en 320 / 375 / 414 / 768 px

1. `html, body { overflow-x: clip; }` (clip, no hidden). Sin scroll
   horizontal en ninguna vista.
2. Toda reticula con contenido flexible usa `minmax(0, 1fr)`, nunca `1fr`
   pelado. `.cifras` colapsa 4→2→1 columnas; `.tarjetas` 3→1.
3. Ningun texto clicable a dos lineas: botones, enlaces de nav, migas y CTAs
   en una linea (`white-space: nowrap` + reducir padding en movil). Si la nav
   no cabe a 320px, se permite scroll horizontal SOLO dentro de la barra de
   nav (`overflow-x: auto` local), no de la pagina.
4. Titulares largos (objetos de contrato): `overflow-wrap: anywhere;
   min-width: 0`.
5. Tablas anchas (buscador): envolver en `.tabla-scroll { overflow-x: auto }`
   con sombra-indicio de borde; la pagina no se desborda.
6. La cifra lider usa `clamp()` (ya en el token) — nunca desborda a 320px.

## 7. Orden de implementacion (tandas con criterio de aceptacion)

Cada tanda termina con TODOS estos comandos en verde antes de seguir:

```bash
python3 design/construir.py       # compone estilo.css; falla si hay URL externa
python3 plomada/build.py          # regenera site/; corre test_privacy y borra site/ si falla
python -m pytest tests/           # puertas de calidad del repo
```

- **T0 · Linea base.** Correr los tres comandos tal cual esta el repo y
  guardar captura de la portada a 375px y 1280px para comparar despues.
- **T1 · Cimientos.** Crear `design/plomada/sitio.css` (stamp + tokens `--pl-*`
  + `.saltar` + `.migas` + `.aviso-fijo` + `.pie` + `.caja` + `.cifras` +
  modificadores `.num/.destacado/.tenue/.grande/.nota/.vacio` + reglas
  responsive de §6). Registrar la pieza 4 en `construir.py`. Actualizar
  `design/VENDOR.md` (seccion "Como se compone estilo.css") con la pieza nueva.
  *Aceptacion:* el sitio entero se ve ordenado sin tocar build.py.
- **T2 · Vocabulario.** Renombrar en `build.py`: `.tabla`→`.table`,
  `.btn sec`→`.btn btn-secondary`, `.tarjeta`→`.card` (+ subclases), banderas
  a `.tag-*`. Actualizar los selectores en `static/*.js` y tests que los usen
  (grep primero). *Aceptacion:* cero clases duplicadas de componentes; script
  de huerfanas (abajo) no reporta componentes.
- **T3 · Portada** segun §4.1, incluida la banda de cierre y el motivo de
  plomada. *Aceptacion:* sin scroll horizontal a 320px; cifra lider con
  salvedad visible; un solo campo rojo en la pagina.
- **T4 · Ficha + municipio** (§4.2, §4.4b).
- **T5 · Buscador + mapa + metodologia + datos** (§4.3-4.5) con los 8 estados
  del buscador.
- **T6 · Verificacion final.** Checklist §8 completa + capturas en los 4
  anchos + comparar contra las capturas de T0.

Script de clases huerfanas (correr en T2 y T6; debe tender a cero):

```bash
grep -rho 'class="[^"]*"' plomada/site --include='*.html' \
  | tr ' "' '\n' | grep -v '^class=$\|^$' | sort -u \
  | while read c; do grep -q "\.$c[ ,{:.]" plomada/static/estilo.css || echo "SIN CSS: $c"; done
```

## 8. Checklist de salida (el implementador la copia al PR)

- [ ] `design/modernist/` intacto (git diff vacio en ese directorio).
- [ ] `estilo.css` regenerado por `construir.py`, sin URLs externas.
- [ ] Cero hex/fuentes hardcodeadas fuera de los bloques de tokens.
- [ ] Cero cursivas en titulares; todo flush left; radio 0 en todo.
- [ ] Un solo campo rojo por pagina (banda de cierre de la portada).
- [ ] Ninguna cifra inventada; toda cifra con su salvedad al lado.
- [ ] Vocabulario prohibido ausente (lo vigila test_privacy, pero revisarlo
      en textos nuevos ANTES de correr el build).
- [ ] 320/375/414/768px sin scroll horizontal, sin clicables a dos lineas.
- [ ] `prefers-reduced-motion` respetado; focus-visible sin animar.
- [ ] Leyenda visible en todo grafico de 2+ series; cada grafico con su
      gemelo en tabla.
- [ ] Mapa satelital sigue siendo click-to-load.
- [ ] `pytest tests/` verde; capturas de los 4 anchos adjuntas al PR.

## 9. Fuera de alcance (decidido, no olvidado)

- Modo oscuro (bloque aparte, posterior; exige tokens re-validados).
- Paleta categorica nueva (VALIDACION.md demuestra por que no).
- Redisenar el tablero o sus 5 graficos.
- Capa municipal del mapa (espera el crosswalk DIVIPOLA de otro frente).
- Cualquier cambio dentro de `design/modernist/`.
