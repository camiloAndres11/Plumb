# Plan de accion: migracion del frontend a Vue

Plan autocontenido para que otro agente lo implemente sin mas contexto que
este archivo y el repo. Complementa `design/PLAN_DISENO.md` (capa visual);
este documento es la capa de **arquitectura de frontend**.

**Leer antes de tocar codigo, en este orden:**

1. `plomada/test_privacy.py` — la prueba que tumba la publicacion. **Es la
   restriccion que decide la arquitectura entera.** Seccion 2 de este plan.
2. `plomada/README.md` — las vistas, el contrato de datos, el vocabulario.
3. `design/VENDOR.md` — que es vendor, que es capa propia, como se compone `estilo.css`.
4. `design/PLAN_DISENO.md` — el plan visual; sus restricciones siguen vigentes.
5. `plomada/data.py` (docstring, L1-7) y `plomada/static/formato.js` (L1-9) —
   las dos mitades de la capa de formateo y como estan amarradas.

---

## 1. Estado actual (medido, no supuesto)

### 1.1 La migracion a Vue YA estaba prevista en el codigo

Esto no es un cambio de rumbo: es la "fase 2" que el propio codigo nombra.
Citas literales:

| Archivo:linea | Texto |
|---|---|
| `plomada/static/formato.js:3` | "El frontend final se alimenta por fetch y **termina en Vue**, asi que esta es la version que sobrevive" |
| `plomada/static/graficos/comun.js:4-6` | "en la **fase 2** cada uno de indicios.js/municipios.js/departamentos.js/red.js **se vuelve un componente Vue**, y comun.js se vuelve el equivalente a un **composable**" |
| `plomada/static/graficos/indicios.js:8` | "Un modulo = un grafico = una unidad de datos clara (**sera un componente Vue en fase 2**)" |
| `plomada/data.py:6` | "**Cuando esto sea una API**, se cambia solo este archivo." |
| `pipeline/export_web.py:11-13` | "prototipo funcional que el equipo puede portar a **Next.js** despues; la forma de los JSON es a proposito la misma que tendran los **endpoints** (`/titulares`, `/municipios`, `/departamentos`, `/red`)" |

Consecuencia practica: **el trabajo de preparacion ya esta hecho.** `formato.js`
es la capa de formateo que sobrevive, los cuatro modulos de `graficos/` ya
tienen forma de componente (entra `datos` resuelto, sale SVG + tabla gemela),
y `comun.js` ya es un composable en todo menos el nombre. La migracion es
mecanica, no un rediseno.

Nota de rumbo: `export_web.py:11` dice **Next.js**, no Vue. Esa linea quedo
desactualizada (el resto del codigo, mas reciente, dice Vue). Corregirla es
tarea de T5.

### 1.2 Que hay hoy en el frontend

Sitio **estatico pre-renderizado** por Python. Cero npm, cero bundler, cero
CDN en tiempo de carga. 246 URLs reales e indexables.

**Python (renderiza HTML):**

| Archivo | Lineas | Rol |
|---|---|---|
| `plomada/build.py` | 983 | Genera `site/`. Vistas: `pagina()` L68-94 (**shell unico**, con el slot `{js}`), `ficha_contrato()` L197-313 (117 lineas, la mayor), `pagina_municipio()` L317-363, `pagina_mapa()` L382-473, `pagina_buscar()` L477-533, `pagina_metodologia()` L537-635, `portada()` L639-708, `pagina_tablero()` L711-805, `pagina_datos()` L808-822. Helpers: `nav()` L50, `aviso_fijo()` L57, `migas()` L103, `dato()` L110, `barra_score()` L124, `bloque_banderas()` L136, `bloque_mapa()` L166. `main()` L847-949. |
| `plomada/data.py` | 451 | **Capa de datos, unico punto que toca los CSV.** `publicar()` L65-70 (saneamiento), `banderas_encendidas()` L356-378, `_ev()` L245-350 (106 lineas: flag → frase con su numero), formateo L82-155, `coords_contrato()` L438-451. |
| `plomada/contenido.py` | 136 | Textos editoriales largos, como constantes con HTML inline. `AVISO` L5-7 (footer de todas las paginas), `FALSOS_POSITIVOS` L11-48, `LIMITACIONES` L50-69, `PUNTAJE` L71-91, `INTRO_METODOLOGIA` L93-105, `PRIVACIDAD` L107-123, `FUENTES` L125-136. `AVISO_CORTO` L9 esta **sin usar** (0 referencias). |
| `plomada/test_privacy.py` | 345 | La prueba que borra `site/` si falla. |

**Cuanto de cada vista es cliente hoy** (define cuanto trabajo hay por vista):

| Vista | Pre-renderizado en Python | Cliente |
|---|---|---|
| `/contrato/`, `/municipio/`, `/metodologia/`, `/datos/` | **100%** | nada (salvo el satelital, tras clic) |
| `/` portada | hero, cifras fijas, tabla top-10, tarjetas | solo `#p-cifra` (`portada.js`) |
| `/mapa/` | **las 721 filas de la tabla municipal** (L420-429) | `#mapa` y `#panel` (`mapa.js`) |
| `/buscar/` | form y opciones de facetas (L493-513) | **todas las filas** (`<tbody>` vacio L524) |
| `/tablero/` | los textos editoriales de cada seccion | **todas las cifras y graficos** (19 ids vacios) |

**JavaScript (ES modules nativos, sin bundler) — 1.077 lineas en total:**

| Archivo | Lineas | Que hace | Destino en Vue |
|---|---|---|---|
| `static/formato.js` | 121 | Espejo JS de `data.py`, amarrado por `tests/formato_casos.json` | **NO se toca.** Se importa tal cual. |
| `static/buscar.js` | 139 | Buscador: filtros, orden, paginacion, sync de query string, export CSV | `Buscador.vue` |
| `static/tablero.js` | 137 | Orquestador del tablero: fetch de 9 JSON, reparte a los graficos | `Tablero.vue` |
| `static/graficos/comun.js` | 156 | SVG a mano, tooltip, tabla gemela, lectura de tokens `--viz-*` | `composables/useViz.js` |
| `static/graficos/indicios.js` | 60 | Barras horizontales | `GraficoIndicios.vue` |
| `static/graficos/municipios.js` | 71 | Dumbbell cruda vs ajustada | `GraficoMunicipios.vue` |
| `static/graficos/departamentos.js` | 73 | Dispersion log | `GraficoDepartamentos.vue` |
| `static/graficos/red.js` | 113 | Grafo de proveedores | `GraficoRed.vue` |
| `static/mapa.js` | 126 | Coropleta Leaflet + panel + filtro de tabla | `MapaCoropletico.vue` + `TablaMunicipios.vue` |
| `static/mapa-satelital.js` | 42 | Click-to-load de tiles Esri | `MapaSatelital.vue` |
| `static/portada.js` | 39 | Cifra lider de la portada | `CifraLider.vue` |

**Hay dos generaciones de JS, y el esfuerzo por archivo no es el mismo:**

- **Ya con forma de componente** (mapeo casi 1:1): los cuatro de `graficos/` son
  funciones puras `dibujar(contenedor(es), datos)` — contrato de entrada
  explicito, no buscan el DOM, sin estado global. `tablero.js` es literalmente
  "el componente padre que pasa props" (asi se autodescribe en su L4-6).
  `comun.js` es el composable. `formato.js` es utilidad pura ya testeada contra
  Python.
- **Vanilla legacy** (`var`, IIFE, dependen del global `L` de Leaflet, arman HTML
  con strings): `mapa.js`, `mapa-satelital.js`, y el cuerpo de `buscar.js`
  (hibrido: `import` en L7 + IIFE L9-139). Estos se reescriben, no se portan.

**Diseno:** `design/construir.py` compone `plomada/static/estilo.css` de cuatro
piezas (`fuentes.css` + `modernist/styles.css` vendor + `dataviz.css` +
`sitio.css`). **Esta capa no se toca en toda la migracion**: los componentes Vue
consumen las mismas clases y los mismos tokens.

### 1.3 Lo que existe a medias y hay que saber antes de planear

- **`api/app/` NO EXISTE.** `api/Dockerfile` hace `COPY api/app/ ./app/`, asi que
  `docker compose up` **falla hoy** en el servicio `api`. Solo hay `Dockerfile`
  y `requirements.txt` (FastAPI + SQLAlchemy + psycopg declarados, sin una sola
  linea de codigo).
- **`pipeline/load_postgres.py` NO EXISTE**, pero el `Makefile` lo invoca
  (receta `load`).
- `docker-compose.yml` declara `CORS_ORIGINS: http://localhost:3000` — el puerto
  clasico de un dev server de SPA. La arquitectura cliente/servidor estaba
  prevista, pero **el servidor no se escribio.**
- `.gitignore` ya trae `node_modules/`, `.next/`, `.env.local`: el toolchain JS
  estaba anticipado.
- `web/index.html` (778 lineas) es el **tablero viejo, ya superado** por
  `plomada/`. Codigo muerto con su propia paleta y su propio modo oscuro.
- `CONTEXT.md` y `docs/adr/` que referencia `CLAUDE.md` **no existen todavia**.
- **El CI no corre la prueba de privacidad.** `.github/workflows/ci.yml` es
  Python-only: `ruff check pipeline api tests` + `pytest tests/`. Pero
  `test_privacy.py` vive en `plomada/`, **no** en `tests/`, y solo se dispara
  desde `plomada/build.py` — que el CI nunca invoca. Tampoco corre
  `design/construir.py` ni `tests/test_formato.mjs` (no hay job de Node). O sea:
  **hoy la compuerta que "tumba la publicacion" solo existe en la maquina de
  quien corra el build a mano.** Se arregla en T0.5.
- `pipeline/build.py` L26 reserva el rango de pasos SQL **90-99 para "vistas de
  serving para el API"**. Esta vacio: `sql/` solo llega a `11_plata_en_riesgo.sql`.

**Conclusion de alcance:** migrar a "Vue + API" son *dos* proyectos, y el
segundo esta en cero. Este plan migra el frontend a Vue **sobre el contrato de
datos que ya existe** (JSON estatico), y deja la API como fase posterior
explicita (seccion 9).

---

## 2. La restriccion que decide la arquitectura: `test_privacy.py`

**Esta es la seccion mas importante del plan. No se puede saltar.**

`plomada/build.py` L944-949 importa `test_privacy`, y si lanza `SystemExit` hace
`shutil.rmtree(SITE)` + `sys.exit`: **borra `site/` entero si la prueba falla.**
Es una compuerta destructiva, no una advertencia. La prueba es el valor central
del proyecto ("riesgo no es fraude", "sin evidencia no se publica"), no un extra.

`main()` (L320-339) **descubre los tests por convencion**
(`if nombre.startswith("test_")`), asi que agregar una funcion `test_*` la
incorpora sola. Hay **14**. De ellas, **6 leen HTML ya renderizado**: si el
contenido pasa a pintarse en el cliente, esas 6 dejan de ver nada.

| Verificacion | Linea | Que lee | Sobrevive a un SPA? |
|---|---|---|---|
| `test_vocabulario` | 147 | `SITE.rglob("*.html")`, con `texto_visible()` que **borra los bloques `<script>`** | **NO.** Ver 2.1 |
| `test_fichas_verificables` | 154 | `site/contrato/**/index.html`: exige "secop.gov.co" y "Indicio, no acusacion" en el HTML | **NO** sin pre-render |
| `test_urls_compartibles` | 166 | Exige `index.html` en cada ruta + uno por municipio + uno por contrato | **NO** sin pre-render |
| `test_tasa_ajustada` | 179 | Extrae el ORDEN de los `href="/municipio/..."` del HTML de la portada (b), y exige "Tasa cruda"+"Tasa ajustada" en portada y mapa (c) | **PARCIAL**: (a) sobre datos si; (b) y (c) no |
| `test_banderas_del_csv` | 201 | Exige que la glosa de cada bandera aparezca en el HTML de metodologia | **PARCIAL**: el resto son unit tests de `data.py` |
| `test_valor_plausible` | 251 | Exige "falla de publicacion" en el HTML de la ficha | **PARCIAL**: los dos chequeos numericos si |
| `test_columnas_prohibidas` | 45 | Todos los artefactos (incluye `.json` y `.csv`) | **Si** |
| `test_valores_prohibidos` | 60 | Todos los artefactos. **El de verdad**: compara VALORES reales del CSV fuente | **Si** — y no se debilita mientras el JSON siga en `site/` |
| `test_serializador` | 86 | Python puro: `publicar()`, `es_persona_juridica()` | **Si** |
| `test_red_sin_documentos` | 97 | `site/datos/red.json`, estructural | **Si** |
| `test_presentacion` | 226 | Python puro sobre `data.py` | **Si**, pero ver nota abajo |
| `test_mapa_no_pinta_el_defecto` | 273 | **Llama `build.bloque_mapa()`, funcion Python** | Solo si `bloque_mapa` sigue en Python |
| `test_mapa_sin_html_crudo_en_popup` | 297 | **Lee el fuente de `static/mapa-satelital.js`** y prohibe `innerHTML` | **NO**: hay que portarla, ver 2.2 |
| `test_geocache_no_bloquea_sin_red` | 312 | **Llama `build.bloque_mapa()`** con cache vacia | Solo si `bloque_mapa` sigue en Python |

El patron es nitido: **lo que barre bytes de archivos (`.json`, `.csv`) sigue
funcionando; lo que hace `substring in html` o regex sobre HTML deja de
funcionar.**

Dos notas que importan al portar:

- **`test_presentacion` puede quedar cubriendo la implementacion equivocada.** Es
  un unit test de `data.py`; si el formateo visible se mueve a `formato.js`, este
  test valida una rama que ya casi nadie ejecuta. El puente que lo salva es
  `tests/formato_casos.json`, que corre las mismas 71 entradas contra las dos
  implementaciones. **Hay que decidir explicitamente quien queda como fuente de
  verdad del formato** (hoy `data.py` lo es, por `formato.js` L7-8) y dejarlo
  escrito.
- **El formato de los mensajes de fallo es funcional, no cosmetico.** `main()`
  L326-335 deduplica agrupando por el prefijo anterior a `" en "`, para imprimir
  un ejemplo por tipo en vez de 245 lineas. Cualquier mensaje nuevo debe
  respetar la forma `"FUGA: ... en <archivo>"` o pierde la agrupacion.

### 2.1 El agujero que la migracion abriria (hay que taparlo ANTES)

`test_vocabulario` (L147-150) tiene **dos huecos** que hoy no importan y con Vue
serian graves:

1. Solo itera `*.html`. **Los `.json` no se revisan por vocabulario**, aunque si
   se revisan por identificadores. Si un texto editorial se mueve a un JSON que
   el cliente pinta, la palabra prohibida entra al sitio sin que nadie la vea.
2. `texto_visible()` (L37-41) **elimina los bloques `<script>` completos** antes
   de buscar. Los `.js` ni figuran en `artefactos()` (L33-34: solo `.html`,
   `.json`, `.csv`, `.xml`, `.txt`, `.geojson`). Un bundle de Vue con texto
   dentro es **invisible** para la puerta de vocabulario.

**Regla dura de este plan: no se escribe una linea de Vue hasta que la puerta de
vocabulario cubra `.json` y los fuentes JS/Vue.** Se tapa en T0. No se desmonta
la red antes de escalar.

### 2.2 `innerHTML` → el equivalente en Vue es `v-html`

`test_mapa_sin_html_crudo_en_popup` (L297-309) prohibe `innerHTML` y
``bindPopup(` `` en `mapa-satelital.js`, porque la especificacion original
interpolaba una direccion (dato de la fuente) dentro de un string de HTML.

Al portar hay dos cosas que hacer y una trampa:

- **Prohibir `v-html`** en todo `.vue` del proyecto. Es exactamente el mismo
  riesgo con otro nombre.
- **Beneficio real de Vue aqui:** `buscar.js` L18-22 mantiene un `esc()` a mano y
  L64-69 arma filas con `insertAdjacentHTML`. La interpolacion de Vue
  (`{{ }}`) escapa por defecto, asi que ese `esc()` casero **desaparece** y con
  el toda una clase de bug. Es un argumento a favor de migrar, no solo un costo.
- **Trampa:** el runtime de Vue usa `innerHTML` internamente. Si la puerta se
  aplica al bundle compilado, **falla siempre**. La verificacion tiene que
  apuntar a los **fuentes** (`frontend/src/**`), nunca al artefacto compilado.

### 2.3 El sitio le PROMETE al lector que esta prueba existe

`plomada/contenido.py` L118-122 — texto publicado en `/metodologia/#privacidad`:

> *"Esto no es una politica escrita: es un serializador en la capa de datos y una
> **prueba automatica que tumba la publicacion del sitio** si una columna
> prohibida alcanza a llegar a un archivo."*

Si la migracion debilita el barrido, **ese parrafo pasa a ser falso** y el sitio
esta afirmandole al lector una garantia que ya no tiene. Es la razon por la que
T0 va primero y no es negociable.

### 2.4 Conclusion arquitectonica (no negociable)

> **El pre-renderizado a HTML por ruta es obligatorio, no una preferencia de SEO.**
> Seis puertas de privacidad leen HTML renderizado. Un SPA que pinte el contenido
> en cliente no "empeora el SEO": **desmantela la red de seguridad que es el
> valor central del proyecto**, y desmiente un parrafo publicado.

De ahi que la arquitectura destino sea **islas de Vue sobre el HTML que Python
ya pre-renderiza**, y no un SPA. Detalle en la seccion 4.

Para el registro, `plomada/build.py` L1-6 nombra las tres razones que un SPA
rompe: *"cada contrato, municipio y busqueda tiene una URL real y compartible,
el HTML sale ya renderizado (indexable) y no hay servidor que mantener"*.
Ninguna de las tres es incompatible con Vue; las tres son incompatibles con
Vue-como-SPA.

---

## 3. Restricciones no negociables (heredadas)

Violarlas rompe tests o decisiones ya documentadas:

0. **`plomada/build.py` es el UNICO que escribe `site/`.** Es el invariante que
   hace posible que `test_privacy.py` barra todo el artefacto publicado de una
   sola pasada (`build.py` L16-20 y `README.md` L281-284: *"asi
   `plomada/test_privacy.py` controla TODO el artefacto, tablero incluido, de
   una sola pasada"*). **Un `dist/` de Vite servido aparte seria un segundo
   escritor y rompe el invariante.** Por eso el bundle se emite dentro de
   `plomada/static/vendor/islas/` y entra a `site/` por el `copytree` que
   `build.py` ya hace en L851 — pasa por el escritor unico, y queda dentro del
   barrido, sin que `build.py` aprenda nada de Vue.
1. **`design/modernist/` no se edita.** Ni un caracter (VENDOR.md).
2. **`plomada/static/estilo.css` no se edita a mano.** Lo genera
   `design/construir.py`. Los componentes Vue **no traen CSS propio de colores**:
   consumen las clases y tokens que ya existen. Si hace falta una clase nueva,
   entra por `design/plomada/sitio.css` y se regenera.
3. **Cero dependencias externas en tiempo de carga.** Sin CDN, sin Google Fonts.
   Unica excepcion: los tiles de Esri, que siguen siendo **click-to-load**.
   `construir.py` falla si queda una URL externa en el CSS; la puerta equivalente
   para el bundle JS se agrega en T0.
4. **`formato.js` NO se reescribe.** Es el espejo de `data.py`, amarrado por
   `tests/formato_casos.json` (71 casos, corren en Python y en Node). Se importa
   tal cual desde los componentes. Tocar su semantica obliga a tocar `data.py` y
   regenerar el fixture.
5. **`data.py` sigue siendo el unico punto que toca los CSV.**
6. **Vocabulario prohibido** (`corrupto`, `fraude`, `delito`, `robo`, `culpable`…)
   tumba el build. Aplica tambien a los textos que entren en componentes Vue.
7. **Cifras reales unicamente.** Ninguna metrica inventada. Si falta un dato:
   `—` con su nota, nunca un numero plausible.
8. **Cada grafico conserva su gemelo en tabla** y **la leyenda es obligatoria con
   2+ series** (`design/plomada/VALIDACION.md` §3).
9. **La identidad de serie la lleva la FORMA, no el color.** No se le agregan hues
   a Modernist. Si se toca un token de `dataviz.css`, hay que re-correr el
   validador y actualizar `VALIDACION.md`.
10. **Sin modo oscuro** en esta fase (decision del 2026-08-22).
11. **El piso responsive de `design/PLAN_DISENO.md` §6 sigue vigente**:
    320/375/414/768px, sin scroll horizontal, sin clicables a dos lineas,
    `minmax(0,1fr)` en grids con contenido flexible.

---

## 4. Arquitectura destino: islas de Vue sobre HTML pre-renderizado

### 4.1 Reparto de responsabilidades

```
Python (build.py)                        Vue (islas)
─────────────────────────────────        ──────────────────────────────
Shell de pagina, nav, pie                Buscador (filtros/orden/CSV)
Hero, cifras, banda de cierre            Tablero (4 graficos + tabla gemela)
Tabla de municipios de la portada        Mapa coropletico (Leaflet)
Ficha de contrato completa               Tabla de municipios filtrable
Metodologia (glosas del CSV)             Mapa satelital (click-to-load)
Paginas de municipio                     Cifra lider de la portada
Sitemap, robots, CSV de descarga
```

La regla para decidir de que lado va algo:

> **Si `test_privacy.py` lo lee, o si un lector sin JS tiene que poder leerlo, lo
> renderiza Python.** Vue solo se hace cargo de lo que es genuinamente
> interactivo: estado de filtros, dibujo de SVG, mapas.

Esto **no** es "Vue a medias": es la arquitectura correcta para un sitio de
datos publicos que tiene que ser indexable, auditable por un escaner estatico, y
legible sin JavaScript. Los 1.077 renglones de JS actuales son exactamente el
alcance que pasa a Vue; el HTML pre-renderizado no era JS y no tenia por que
volverse JS.

### 4.2 Estructura de directorios

```
frontend/                          NUEVO — fuentes de las islas
├── package.json
├── vite.config.js
├── src/
│   ├── islas.js                   punto de entrada unico: monta por data-isla
│   ├── componentes/
│   │   ├── Buscador.vue
│   │   ├── Tablero.vue
│   │   ├── GraficoIndicios.vue
│   │   ├── GraficoMunicipios.vue
│   │   ├── GraficoDepartamentos.vue
│   │   ├── GraficoRed.vue
│   │   ├── MapaCoropletico.vue
│   │   ├── TablaMunicipios.vue
│   │   ├── MapaSatelital.vue
│   │   ├── CifraLider.vue
│   │   └── TablaGemela.vue        el gemelo en tabla, reutilizable
│   └── composables/
│       ├── useViz.js              ex-graficos/comun.js (SVG, tooltip, tokens)
│       └── useDatos.js            fetch + degradacion ("avisa, no revienta")
└── README.md                      como correr el toolchain

plomada/static/
├── formato.js                     SE QUEDA (lo importa el bundle)
├── vendor/
│   ├── leaflet/                   ya existe
│   └── islas/                     NUEVO — bundle compilado, COMMITEADO
│       ├── islas.js
│       └── MANIFIESTO.txt         version, fecha, hash del fuente
└── (los .js viejos se borran solo cuando su isla ya funciona)
```

### 4.3 Como se montan las islas

Un solo entry point, montaje declarativo por atributo. `build.py` no aprende
nada de Vue: solo emite un `<div data-isla="...">` y, una vez por pagina, el
script del bundle.

```js
// frontend/src/islas.js
import { createApp } from 'vue'

const ISLAS = {
  buscador:       () => import('./componentes/Buscador.vue'),
  tablero:        () => import('./componentes/Tablero.vue'),
  'mapa-coropleta': () => import('./componentes/MapaCoropletico.vue'),
  'mapa-satelital': () => import('./componentes/MapaSatelital.vue'),
  'cifra-lider':  () => import('./componentes/CifraLider.vue'),
}

for (const el of document.querySelectorAll('[data-isla]')) {
  const cargar = ISLAS[el.dataset.isla]
  if (!cargar) continue
  cargar()
    .then(({ default: Componente }) => {
      // Los props entran por data-* : el servidor decide, el cliente pinta.
      createApp(Componente, { ...el.dataset }).mount(el)
    })
    // Degradar avisando, nunca romper: el patron ya vigente en tablero.js
    // y data.py. Si una isla no monta, el HTML pre-renderizado sigue ahi.
    .catch((e) => console.error(`isla ${el.dataset.isla}:`, e))
}
```

En `build.py`, el seam ya existe: el parametro `js=` de `pagina()` (L68). Un
helper unico:

```python
ISLAS_JS = '<script type="module" src="/static/vendor/islas/islas.js"></script>'

def isla(nombre, **props):
    """Contenedor de una isla de Vue. El HTML de adentro es el fallback que
    ve un lector sin JS y que lee test_privacy.py: nunca se deja vacio."""
    attrs = "".join(f' data-{k.replace("_", "-")}="{h(v)}"' for k, v in props.items())
    return f'<div data-isla="{h(nombre)}"{attrs}>'
```

**Regla del fallback:** todo `data-isla` envuelve contenido pre-renderizado que
tiene sentido por si solo. La isla lo *reemplaza* al montar; no lo *crea*. Asi
el sitio no depende de JS para ser legible ni para pasar la prueba de privacidad.

### 4.4 De donde salen los datos

No cambia el contrato: `site/datos/*.json`, que `build.py` ya escribe
(`escribir_json()` L932) y copia de `out_web/` (`copiar_datos_tablero()` L806).
`useDatos.js` centraliza el fetch con la misma degradacion que hoy tiene
`tablero.js` (L48-58: si un JSON falta, avisa y no revienta).

Cuando exista la API (fase posterior), cambia **solo** `useDatos.js` — el
equivalente en JS de lo que `data.py:6` promete para Python.

---

## 5. Decision de toolchain (la unica que el equipo debe confirmar)

El proyecto presume de "sin npm". Hay que ser exacto sobre que significa eso hoy:
el `README.md` L286-289 **ya se corrigio a si mismo**: *"esta seccion decia 'sin
build step, sin npm, sin CDN'. Ya no es cierto y no lo era del todo ni antes: hay
build step (`python3 design/construir.py`)"*. Lo que queda vigente, y es lo que
de verdad importa, es **sin npm para servir** y **sin CDN en tiempo de carga**.

### Recomendada: Vite + SFC, con el bundle vendorizado y commiteado

```
npm --prefix frontend install
npm --prefix frontend run build     # escribe plomada/static/vendor/islas/
python3 design/construir.py
python3 plomada/build.py
```

- **El bundle compilado se commitea** en `plomada/static/vendor/islas/`, igual
  que Leaflet (188 KB, ya commiteado, precedente exacto en VENDOR.md §5).
- **Preserva el invariante del escritor unico** (restriccion 0 de la seccion 3):
  el bundle no se sirve desde un `dist/` propio, entra a `site/` por el
  `copytree` que `build.py` ya hace. Un solo escritor, un solo barrido de
  privacidad. Esta es la razon de peso de la eleccion, no la comodidad.
- **Quien solo corre el sitio no necesita Node.** `python3 plomada/build.py` +
  servir funciona con el bundle commiteado. Solo quien *cambia un componente*
  necesita npm. Esto respeta al lider en Windows y mantiene el deploy como
  hosting estatico.
- **Cero dependencias en tiempo de carga**: el bundle se auto-hospeda. La
  restriccion real queda intacta.
- Vue 3 + Vite estan disponibles en este equipo: **Node v26.7.0, npm 11.19.0**
  (verificado).
- **Costo honesto:** un artefacto compilado en git puede quedar desfasado del
  fuente. Se mitiga en T1 con `MANIFIESTO.txt` (hash de los fuentes) y una
  puerta que falla si el bundle no corresponde. Sin esa puerta, no se acepta.

### Alternativa si el equipo rechaza npm por completo

Vendorizar `vue.esm-browser.prod.js` y escribir los componentes como objetos con
`template:` en string, sin `.vue` ni build step.

- A favor: cero toolchain, coherente al 100% con el discurso actual.
- En contra: no hay SFC ni `<style scoped>`; las plantillas viven en strings de
  JS (sin resaltado ni chequeo); hay que embarcar el **compilador** de plantillas
  en runtime (~40 KB extra) porque compilar en el navegador lo exige.

**Recomendacion:** la primera. El valor que el proyecto defiende (no pedirle nada
a un tercero cuando el lector abre la pagina) se conserva entero, y el equipo gana
SFC. Si se elige la alternativa, todo el resto de este plan sigue valido salvo la
extension de archivo de los componentes.

---

## 6. Mapeo isla por isla

### 6.1 `Buscador.vue` — el mayor rendimiento del cambio

Reemplaza `static/buscar.js` (139 lineas). Hoy: estado en el DOM, filtros
imperativos, `esc()` casero, `insertAdjacentHTML`, paginacion manual.

Modelo de estado en Vue (todo lo que hoy esta disperso):

```
filtros    reactive: q, departamento, municipio, entidad, anio, periodo,
                     tipo, modalidad, bandera, vmin, vmax    (buscar.js L24-28)
orden      ref: { campo, asc }                               (buscar.js L11)
pagina     ref: cuantos lotes de 50 se muestran              (buscar.js L10)
vista      computed: filtrar(datos, filtros) -> ordenar       (buscar.js L30-53)
resumen    computed: n de m + plata(suma)                     (buscar.js L56-58)
URL        watch(filtros+orden) -> history.replaceState       (buscar.js L75-84)
```

- **La query string sigue siendo la fuente de verdad compartible** (buscar.js
  L1-2). Al montar se lee (`desdeURL`, L86-94); al cambiar se escribe con
  `history.replaceState`. **Sin vue-router**: es una isla, no una SPA.
- `esc()` (L18-22) **se borra**: la interpolacion de Vue escapa por defecto.
- El export CSV (L102-118) pasa a un metodo. **Conservar el BOM** `﻿` (L112)
  y su comentario: es lo que evita que Excel en es-CO destroce las tildes.
- **Cerrar aqui la deuda de `design/PLAN_DISENO.md` §4.3**: los 8 estados
  (default, hover, focus-visible, active, disabled, **cargando**, **error/vacio**,
  **exito**). Hoy solo existen tres a medias (`buscar.js` L57, L138).

### 6.2 `Tablero.vue` + 4 graficos + `useViz`

Reemplaza `tablero.js` + `graficos/*.js`. Es la migracion que el propio
`comun.js:4-6` describe: cada grafico → componente, `comun.js` → composable.

- **El dibujo de SVG se queda a mano.** No entra ninguna libreria de graficos:
  `dataviz.css` + `VALIDACION.md` definen forma, contraste y rampa medidos. Una
  libreria traeria su propia paleta y sus esquinas redondeadas (Modernist es
  radio 0, `indicios.js` L4-7 lo dice explicitamente).
- `tonosViz()` (comun.js L17-20) lee los tokens `--viz-*` con `getComputedStyle`.
  **Se conserva tal cual**: es lo que garantiza que un cambio de color en el CSS
  se refleje sin tocar JS. En Vue va en `useViz()`.
- `tabla()` (comun.js L107-135) → `TablaGemela.vue`, con `<td>{{ valor }}</td>`
  en vez de `textContent`. **Sigue siendo obligatoria en los cuatro graficos.**
- La leyenda (comun.js L144-151) sigue siendo obligatoria con 2+ series.
- Los `<details class="tbl">` y los `id="t-*"` que hoy usa el HTML pueden
  desaparecer del markup de Python: pasan a ser estructura interna del
  componente. **Excepcion:** lo que `test_privacy.py` o el CSS referencien por id
  se mantiene (revisar `design/plomada/sitio.css` regla `[id^="t-tbl-"]`).

### 6.3 `MapaCoropletico.vue` + `TablaMunicipios.vue`

Reemplaza `mapa.js` (126 lineas), que hoy hace dos cosas distintas: el mapa
Leaflet y el filtro de la tabla de municipios. Se separan.

- Leaflet es imperativo: el componente es un envoltorio fino. Instancia en
  `onMounted`, `map.remove()` en `onUnmounted`. Leaflet **sigue vendorizado**
  (`/static/vendor/leaflet/`), importado como global o como dep de npm — si se
  hace lo segundo, verificar que el bundle no quede con una URL externa (puerta
  de T0) y actualizar VENDOR.md §5.
- `mapa.js` L45-68 arma el panel con **strings de HTML** (`innerHTML`,
  `'<dl class="dl">' + ...`). Al portar, plantilla Vue. **Nada de `v-html`.**
- La rampa de la coropleta (`--viz-seq-1..5`) y los cortes **fijos** no se tocan:
  estan validados en `VALIDACION.md` §2 y los cortes son fijos a proposito para
  que el mapa sea comparable consigo mismo entre cargas.
- `TablaMunicipios.vue`: la tabla llega **pre-renderizada por Python** (la lee
  `test_privacy.py` L194-197, que exige "Tasa cruda" y "Tasa ajustada" juntas).
  La isla solo agrega el filtro. **No la re-renderiza desde JSON.**

### 6.4 `MapaSatelital.vue` — el que mas cuidado exige

Reemplaza `mapa-satelital.js` (42 lineas). Tres invariantes que **no** pueden
perderse:

1. **Click-to-load.** No se le pide un tile a Esri hasta que el lector pulsa el
   boton. El motivo esta en VENDOR.md §5: no delatarle a un tercero que
   coordenadas mira un periodista solo por abrir una ficha.
2. **El popup se arma con DOM/interpolacion, nunca con HTML en string.**
   `test_privacy.py` L297-303 lo verifica leyendo el fuente. Al portar hay que
   **actualizar esa prueba** para que lea `frontend/src/componentes/MapaSatelital.vue`
   y prohiba `v-html` (y siga prohibiendo `innerHTML` y ``bindPopup(` ``).
3. El contenedor conserva `id="mapa-satelital"` y sus `data-lat`/`data-lon`/
   `data-direccion`: `test_privacy.py` L286-289 los exige, y `build.bloque_mapa()`
   (Python, `build.py` L166) los emite. **`bloque_mapa()` se queda en Python**
   porque `test_mapa_no_pinta_el_defecto` (L273-294) la llama directamente.

### 6.5 `CifraLider.vue`

Reemplaza `static/portada.js` (39 lineas). Es la isla mas simple y la mas nueva:
usar de piloto en T1. Conserva:
- El dato sale de `titulares.json` + `meta.json` (los mismos del tablero). **No
  se inventa una cifra.**
- Si el JSON no esta, la seccion **queda oculta** (`hidden`) y la portada se
  apoya en la franja de cifras fijas de mas abajo.
- La salvedad ("Indicio, no acusacion") viaja **con** la cifra, siempre.

---

## 7. Tandas, en orden, con criterio de aceptacion

Cada tanda termina con **todo** esto en verde antes de pasar a la siguiente:

```bash
npm --prefix frontend run build     # desde T1
python3 design/construir.py
python3 plomada/build.py            # corre test_privacy y borra site/ si falla
python3 tests/test_formato.py
node    tests/test_formato.mjs
python3 tests/test_privacidad_red.py
python3 tests/test_contrato_banderas.py
python -m pytest tests/             # si hay pytest en el entorno
```

> Nota de entorno: en este equipo **no hay pytest ni pip** (`python3 -m pip`
> falla). Los cuatro scripts de arriba corren solos a proposito y son la puerta
> real disponible. No lo trates como que "los tests no existen".

### T0 — Blindar la red ANTES de migrar (obligatoria, primera)

Sin esto, la migracion abre el agujero de la seccion 2.1.

1. `test_vocabulario` (`test_privacy.py` L147): extender a los `.json` de
   `site/datos/` y a los **fuentes** de `frontend/src/**` (`.vue`, `.js`).
2. Nueva puerta: **prohibir `v-html`** en cualquier `.vue`. Aplicar a fuentes,
   **nunca al bundle** (el runtime de Vue usa `innerHTML` internamente y la
   puerta fallaria siempre).
3. Nueva puerta: el bundle de `static/vendor/islas/` **no puede contener una URL
   externa** (`http://`, `https://`, `fonts.googleapis`, `unpkg`, `cdn`), espejo
   de la que ya tiene `design/construir.py` L77-78. Excepcion documentada:
   `server.arcgisonline.com` solo si aparece en `MapaSatelital`.
4. Nueva puerta: **el bundle corresponde a los fuentes** (hash en
   `MANIFIESTO.txt`). Si alguien edita un `.vue` y no recompila, el build falla.
5. **Hacer que el CI corra la compuerta.** Hoy no la corre (seccion 1.3). Agregar
   a `.github/workflows/ci.yml` un paso que ejecute, sin warehouse y con las
   fixtures sinteticas:
   ```yaml
   - run: python3 design/construir.py
   - run: python3 plomada/gen_synthetic.py
   - run: python3 plomada/build.py          # dispara test_privacy.py
   - uses: actions/setup-node@v4
     with: { node-version: "22" }
   - run: node tests/test_formato.mjs       # hoy nunca corre en CI
   ```
   Desde T1 se suma `npm --prefix frontend ci && npm --prefix frontend run build`
   antes de `plomada/build.py`, mas la puerta de bundle-al-dia. Una puerta que no
   corre en CI no es una puerta.

*Aceptacion:* las 5 puertas fallan cuando deben — probarlas **a proposito**:
meter "fraude" en un JSON y en un `.vue`, meter un `v-html`, meter una URL de CDN
en el bundle, editar un fuente sin recompilar, y abrir un PR con una fuga para
ver el CI rojo. Todas pasan con el repo limpio. **Sin Vue todavia.**

### T1 — Toolchain y una isla piloto, sin cambiar ninguna vista

1. `frontend/` con `package.json`, `vite.config.js` (salida a
   `plomada/static/vendor/islas/`, `base: '/static/vendor/islas/'`), `islas.js`.
2. Portar **solo** `CifraLider.vue` (la mas simple y la mas nueva).
3. `build.py`: helper `isla()` + `ISLAS_JS`; la portada usa la isla en vez de
   `portada.js`. **Borrar `portada.js` solo cuando la isla funcione.**
4. `MANIFIESTO.txt` + la puerta de T0.4 activa.
5. `frontend/README.md`: como instalar, como compilar, y **que no hace falta Node
   para correr el sitio**.
6. Actualizar `design/VENDOR.md` (nueva entrada de vendor: el bundle) y el
   `Makefile` (receta `front`).

*Aceptacion:* la portada se ve **identica** a la captura previa (mismos anchos
320/375/414/1280); `test_privacy` pasa; `git status` no muestra cambios en
`design/modernist/`; el sitio sigue funcionando si se borra `node_modules/`.

### T2 — `Tablero.vue` + 4 graficos + `useViz`

Segun 6.2. **Va antes que el buscador a proposito**, por dos razones medidas:
el tablero ya es 95% cliente (19 ids vacios que llena JS), asi que migrarlo no
puede romper una puerta de privacidad que lea HTML — la unica que lo toca es
`test_red_sin_documentos`, que es estructural sobre `red.json` y sobrevive; y sus
cuatro modulos **ya son funciones puras** `dibujar(contenedor(es), datos)`, o sea
el mapeo a componente es mecanico. Es la tanda donde se establece el patron
(composable + props + tabla gemela) con el menor riesgo.

*Aceptacion:* los cinco graficos se ven igual que antes (comparar capturas);
**cada uno conserva su tabla gemela**; leyenda presente donde hay 2+ series; los
tokens `--viz-*` siguen leyendose del CSS (probar: cambiar un token en
`dataviz.css`, recomponer, y ver el cambio sin tocar JS); si falta un JSON, el
tablero avisa y no revienta.

### T3 — `Buscador.vue`

Segun 6.1, incluidos los 8 estados de `PLAN_DISENO.md` §4.3.

*Aceptacion:* paridad funcional verificable a mano — filtrar por cada campo,
ordenar por cada columna, "Ver mas", "Limpiar", exportar CSV (abrir el archivo y
confirmar tildes), **y recargar con la URL de filtros puesta y obtener el mismo
resultado**. Sin scroll horizontal a 320px. `esc()` eliminado.

### T4 — Mapa: coropleta, tabla filtrable y satelital

Segun 6.3 y 6.4.

*Aceptacion:* la coropleta pinta con la rampa validada y cortes fijos;
"sin dato" sigue con trama, no como escalon bajo; el satelital **no pide un tile
hasta el clic** (verificar en la pestana de red del navegador: cero peticiones a
`arcgisonline.com` al cargar la ficha); `test_mapa_sin_html_crudo_en_popup`
actualizada y en verde; ningun `v-html` en el repo.

### T5 — Limpieza, documentacion y decisiones pendientes

1. Borrar los `.js` ya reemplazados — **uno por uno, solo tras verificar su
   isla**. `formato.js` **se queda**.
2. Corregir `pipeline/export_web.py:11` ("Next.js" → Vue, o quitar la mencion).
3. Actualizar `README.md` (seccion "Tablero") y `plomada/README.md`: hay
   toolchain de frontend, pero no hace falta para correr el sitio. Ojo:
   `plomada/README.md` L3-5 ya esta **desactualizado** hoy (dice que el navegador
   "carga Leaflet desde CDN", y Leaflet se vendorizo en la Tanda B).
4. Borrar `AVISO_CORTO` (`contenido.py` L9): constante sin un solo uso.
4. Escribir el ADR de la decision: `docs/adr/0001-islas-vue-sobre-html-prerenderizado.md`,
   con el razonamiento de la seccion 2 (las puertas de privacidad obligan al
   pre-render). `docs/agents/domain.md` pide no crear ADRs por adelantado — pero
   esta es justamente una decision resuelta, que es cuando si corresponde.
5. **Requiere confirmacion del equipo, no hacerlo por cuenta propia:**
   `web/index.html` (778 lineas) es el tablero viejo ya superado. Proponer su
   borrado y esperar respuesta. Igual con la receta `web:` del `Makefile`, que
   apunta ahi.

### T6 — FUERA de esta migracion (documentar, no hacer)

La API y el SPA completo. Ver seccion 9.

---

## 8. Riesgos y como se controlan

| Riesgo | Por que importa | Control |
|---|---|---|
| Mover texto editorial a JS/JSON burla la puerta de vocabulario | Publicar "fraude" en un sitio cuya tesis es "riesgo no es fraude" | T0.1 antes de cualquier Vue |
| `v-html` reintroduce el bug que ya se cerro en el popup | Inyeccion desde un campo de la fuente | T0.2, puerta sobre fuentes |
| Aplicar la puerta de `innerHTML` al bundle | El runtime de Vue lo usa: la puerta fallaria siempre y alguien la desactivaria | Puerta **solo** sobre `frontend/src/**` |
| El bundle commiteado se desfasa del fuente | Se depura un bug que ya estaba arreglado en el fuente | `MANIFIESTO.txt` + puerta T0.4 |
| Perder el pre-render de una vista "por comodidad" | Rompe 6 puertas de privacidad y la indexabilidad | Regla 4.1 + los tests fallan solos |
| El satelital empieza a pedir tiles al cargar | Delata interes investigativo a un tercero | Verificacion manual en T4 + VENDOR.md §5 |
| Meter una libreria de graficos | Trae su paleta y sus esquinas redondeadas; invalida VALIDACION.md | Prohibido en 6.2 |
| Reescribir `formato.js` | Divergiria de `data.py` y el fixture de 71 casos lo cazaria… o no | Restriccion 4 de la seccion 3 |
| Node no disponible en la maquina de un companero | Bloquea a quien solo quiere correr el sitio | Bundle commiteado; Node solo para editar componentes |

---

## 9. Fuera de alcance (decidido, no olvidado)

- **La API FastAPI y el SPA completo.** Lo que falta para eso, medido:
  `api/app/` **no existe** (el `Dockerfile` copia un directorio ausente, asi que
  `docker compose up` falla en el servicio `api`), `pipeline/load_postgres.py`
  **no existe** (el `Makefile` lo invoca), y el rango de pasos SQL **90-99
  reservado para "vistas de serving para el API"** (`pipeline/build.py` L26) esta
  vacio. Son tres piezas en cero, no un refactor. Convertir el sitio en SPA
  contra esa API exigiria ademas reescribir las 6 puertas de privacidad que leen
  HTML (seccion 2) y perder la indexabilidad de 246 URLs. Si algun dia se hace,
  el camino es **SSG con Nuxt o `vite-ssg`** (pre-renderiza por ruta, conserva
  las puertas y el escritor unico), nunca un SPA pelado. Del lado del cliente,
  el unico punto a cambiar seria `useDatos.js`.
- **Modo oscuro.** Exige un set de tokens oscuros elegido y re-validado
  (`VALIDACION.md` §3), no un volteo automatico.
- **`vue-router`.** No hace falta: son islas sobre paginas reales. La query string
  del buscador se maneja con `history.replaceState`, como hoy.
- **Rediseno visual.** Lo cubre `design/PLAN_DISENO.md`. Esta migracion es
  paridad funcional y visual: si algo se ve distinto despues de una tanda, es un
  bug de la tanda.
- **Vuex/Pinia.** Ninguna isla comparte estado con otra. Si algun dia lo hacen,
  reevaluar.
- **Capa municipal del mapa.** Sigue esperando el crosswalk DIVIPOLA de otro frente.

---

## 10. Checklist de salida (copiar al PR)

- [ ] Las 4 puertas nuevas de T0 existen y se probo que fallan cuando deben.
- [ ] `design/modernist/` intacto (`git diff` vacio ahi).
- [ ] `estilo.css` regenerado por `construir.py`; ningun componente Vue trae
      colores ni fuentes propios (todo por token).
- [ ] `formato.js` sin cambios de semantica; los 71 casos del fixture en verde en
      Python y en Node.
- [ ] Escrito quien es la **fuente de verdad del formato** (`data.py` o
      `formato.js`) y por que — ver la nota al final de la seccion 2.
- [ ] El CI corre `plomada/build.py` (o sea, `test_privacy`) y
      `tests/test_formato.mjs`. Comprobado con un PR de prueba en rojo.
- [ ] Ningun `v-html` en el repo. `esc()` casero de `buscar.js` eliminado.
- [ ] Cada `data-isla` envuelve contenido pre-renderizado que se lee sin JS.
- [ ] Las 246 URLs siguen existiendo como HTML; `sitemap.xml` intacto.
- [ ] Cada grafico conserva su tabla gemela; leyenda con 2+ series.
- [ ] El satelital no pide nada a Esri hasta el clic (verificado en la pestana de red).
- [ ] 320/375/414/768px: sin scroll horizontal, sin clicables a dos lineas.
- [ ] `prefers-reduced-motion` respetado; `:focus-visible` sin animar.
- [ ] Bundle commiteado + `MANIFIESTO.txt` al dia; el sitio corre sin `node_modules/`.
- [ ] `test_privacy` en verde y los cuatro scripts de `tests/` tambien.
- [ ] Capturas antes/despues de las 6 vistas en los 4 anchos, adjuntas al PR.
- [ ] ADR escrito. `README.md` y `plomada/README.md` al dia.
- [ ] El borrado de `web/index.html` **no** se hizo sin confirmacion del equipo.
