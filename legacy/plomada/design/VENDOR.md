> `plomada/static/landing.css` (salida de `construir.py`) tiene una **copia
> commiteada en `plataforma/static/landing.css`**, junto con `landing.html`,
> `landing.js`, las fuentes y los favicons: la landing de Pliego ya no depende
> de este directorio. Si se regenera aquí, copiar a mano.

# Sistema de diseno: Modernist

Copia vendorizada del proyecto de diseno **Modernist** de claude.ai/design
(`projectId 3f907967-1c67-4833-907f-d9e806475462`, actualizado 2026-08-18).
Bajada el 2026-08-22.

`design/modernist/` es una copia FIEL del upstream. No se edita a mano: si el
sistema cambia, se vuelve a bajar completo. Todo lo que este proyecto agrega
encima vive en `design/plomada/`, nunca dentro de `modernist/`.

| Archivo | Que es |
|---|---|
| `modernist/styles.css` | Hoja unica: tokens (`:root`) + capa de componentes. |
| `modernist/theme.json` | Los parametros de los que se derivo el sistema. |
| `modernist/readme.md` | La guia de uso: que clase existe y como se combina. |

#> `plomada/static/landing.css` (salida de `construir.py`) tiene una **copia
> commiteada en `plataforma/static/landing.css`**, junto con `landing.html`,
> `landing.js`, las fuentes y los favicons: la landing de Pliego ya no depende
> de este directorio. Si se regenera aquí, copiar a mano.

# Desviaciones deliberadas del upstream

Se documentan aqui, se implementan en `design/plomada/`, y NO se parchean
dentro de `modernist/styles.css`.

1. **Archivo se auto-hospeda.** El upstream trae un `@import` a
   Google Fonts. Este sitio no depende de terceros en tiempo de carga: los
   pesos 400/600/800 (subconjuntos `latin` y `latin-ext`) se sirven desde
   `plomada/static/fonts/` con `@font-face` propio, declarado en
   `design/plomada/fuentes.css`. La regla `@import` se neutraliza desde la
   capa del proyecto — ver "Como se compone `estilo.css`" abajo.
2. **Extension de dataviz.** Modernist es mono a proposito: un solo acento,
   sin segundo (`--color-accent-2-*` es un relleno derivado a maquina, no un
   rol). El tablero necesita color categorico. La extension se declara en
   `design/plomada/dataviz.css` con su justificacion y sus contrastes
   medidos. Ningun hex suelto en JS ni en HTML.
3. **Iconos Lucide locales.** Sprite SVG en `plomada/static/iconos.svg`, sin
   CDN. Solo trae los iconos que de verdad se usan; no es el set completo de
   Lucide vendorizado.
4. **Capa de pagina en `design/plomada/sitio.css`.** Modernist trae tokens
   y componentes atomicos (`.btn`, `.card`, `.tag`, `.table`, `.nav`...) pero
   no layout de pagina: hero, cabeceras de seccion, franjas de cifras, ficha
   de contrato, avisos fijos, pie de pagina. Ese vocabulario es especifico
   de Plomada (ver `design/PLAN_DISENO.md`) y vive en `sitio.css`, nunca
   parcheado dentro de `modernist/`. Todo color y toda fuente en `sitio.css`
   referencian los tokens de Modernist por nombre; los unicos tokens nuevos
   son de tipografia/espacio/movimiento (`--pl-*`), porque Modernist no trae
   una escala de texto fluida ni duraciones de animacion.
5. **Leaflet vendorizado (Tanda B, B6).** `plomada/static/vendor/leaflet/`:
   `leaflet.js`, `leaflet.css`, `images/` (marcador + capas) y `LICENSE`,
   version **1.9.4**, licencia **BSD-2-Clause** (Volodymyr Agafonkin /
   CloudMade). Bajados de `unpkg.com/leaflet@1.9.4` el 2026-08-22 y servidos
   desde `/static/vendor/leaflet/` — `build.py` ya no enlaza a unpky.com. Los
   tiles satelitales de la ficha de contrato (Esri, `server.arcgisonline.com`)
   NO estan vendorizados ni se pueden estar: son imagenes del mundo, no una
   libreria. Por eso el mapa satelital es click-to-load (ver
   `static/mapa-satelital.js`): no se le pide nada a Esri hasta que el lector
   pulsa el boton, para no delatar interes investigativo a un tercero solo por
   abrir una ficha.
6. **Bundle de las islas de Vue (`docs/PLAN_VUE.md`, T1).**
   `plomada/static/vendor/islas/`: `islas.js` + los chunks de cada
   componente, compilados por `npm --prefix frontend run build` desde
   `frontend/src/`. **Commiteado**, mismo precedente que Leaflet — quien solo
   corre el sitio no necesita Node. `MANIFIESTO.txt` (tambien commiteado)
   guarda el hash sha256 de los fuentes; `plomada/test_privacy.py` falla si
   el bundle no corresponde a ese hash, para que un `.vue` editado sin
   recompilar nunca llegue a publicarse desfasado. Ver `frontend/README.md`.

#> `plomada/static/landing.css` (salida de `construir.py`) tiene una **copia
> commiteada en `plataforma/static/landing.css`**, junto con `landing.html`,
> `landing.js`, las fuentes y los favicons: la landing de Pliego ya no depende
> de este directorio. Si se regenera aquí, copiar a mano.

# Como se compone `estilo.css`

Nada en `plomada/static/estilo.css` se edita a mano: lo genera
`python3 design/construir.py`, que concatena, en este orden:

1. `design/plomada/fuentes.css` — los `@font-face` locales de Archivo.
2. `design/modernist/styles.css` — el vendor **tal cual**, con su unica
   linea de `@import` externo filtrada en memoria durante la composicion
   (el archivo en disco no se toca).
3. `design/plomada/dataviz.css` — la extension de color/graficos.
4. `design/plomada/sitio.css` — layout y componentes de pagina (hero,
   cabeceras, fichas, franjas de cifras, pie de pagina). Ver
   `design/PLAN_DISENO.md` para el plan de diseno completo.

`build.py` de Plomada sigue sirviendo el resultado en `/static/estilo.css`
(el nombre no cambia; cambia quien lo produce). El script falla fuerte
(`sys.exit`) si el resultado compuesto todavia contiene una URL externa, para
que un @import nuevo en el vendor no se cuele en silencio.

Correr `python3 design/construir.py` despues de cualquier cambio en
`fuentes.css`, `dataviz.css`, o al re-bajar `modernist/` completo.
