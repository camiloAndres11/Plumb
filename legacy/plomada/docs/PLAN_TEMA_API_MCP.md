# Plan: tema oscuro con conmutador, vista `/api/` y vista del asistente MCP

**Este archivo es autocontenido y es la única fuente de verdad para este
trabajo.** Fecha: 2026-08-23. Rama: `main` (las ramas ya se fusionaron; el
repo tiene el sitio, el API y el MCP juntos).

Supersede parcialmente a `design/PLAN_DISENO.md`, a
`design/plomada/VALIDACION.md` y a `MCP.md` §4 en los puntos listados en §3.
Donde este archivo y esos contradigan, manda este.

Cuatro entregables, en este orden:

| # | Fase | Qué entrega | Depende de |
|---|---|---|---|
| 1 | **F1** | Tokens de banda oscura + botón conmutador claro/oscuro en el nav | — |
| 2 | **F2** | Gráficos y mapa que se re-pintan al cambiar de tono | F1 |
| 3 | **F3** | Enlace «API» en la navegación + **la vista `/api/`, construida desde cero** | — |
| 4 | **F4** | **La vista `/asistente/`, construida desde cero**: chat con el MCP (BYOK) | F3 |

Cada fase deja el sitio publicable. Lee §9 (puntos de corte) antes de empezar.

---

## 0. Lo primero: dos vistas que NO existen y hay que construir

Esto es lo que más fácil se malinterpreta de este encargo, así que va antes
que nada. **El backend del API y del MCP está construido y desplegado. La cara
en el sitio no existe: hay que construirla.**

Comprobado en el repo, no supuesto:

```bash
# ¿Hay algo de chat o de MCP en el sitio? -> NADA. Cero resultados.
grep -rl "chat\|X-Anthropic\|mcp" plomada/static/ plomada/build.py plomada/contenido.py

# ¿Qué vistas escribe hoy build.py? -> ocho, ninguna es /api/ ni /asistente/
grep -n 'escribir("' plomada/build.py
#   contrato/  municipio/  tablero/  mapa/  buscar/  metodologia/  index  datos/
```

| Pieza | Estado real |
|---|---|
| Servidor MCP (`api/app/mcp/server.py`, 7 tools) | **construido y desplegado** |
| Proxy `/chat` BYOK (`api/app/main.py`) | **construido y desplegado** |
| API REST `/v1` (20 endpoints, `api/app/routers/`) | **construido y desplegado** |
| `API.md`, `MCP.md` | **escritos**, en la raíz del repo |
| **Vista `/api/` en el sitio** | **NO EXISTE — se construye en F3** |
| **Vista del asistente en el sitio** | **NO EXISTE — se construye en F4** |
| `plomada/static/chat.js` | **NO EXISTE — se escribe en F4** |
| Enlace «API» en el nav | **NO EXISTE — se agrega en F3** |

O sea: F3 y F4 son **trabajo de front en `plomada/`**, escribiendo funciones
`pagina_*()` nuevas en `plomada/build.py`, texto nuevo en
`plomada/contenido.py`, un módulo JS nuevo en `plomada/static/` y estilos
nuevos en `design/plomada/sitio.css`. **No es documentación ni configuración:
son dos páginas que hoy no existen y que el lector tiene que poder visitar.**

`MCP.md` §4 dice "para quien trabaje `web/` (o el proyecto Vercel nuevo)". Eso
quedó viejo: **el front del proyecto es `plomada/`**. `web/index.html` es el
tablero anterior y no se toca.

---

## 1. Cómo correr y verificar

`plomada/static/estilo.css` es un **artefacto generado**. `design/construir.py`
concatena, en este orden:

```
1. design/plomada/fuentes.css    @font-face auto-hospedados
2. design/modernist/styles.css   vendor TAL CUAL (su @import externo se filtra en memoria)
3. design/plomada/dataviz.css    tokens --viz-* de gráficos
4. design/plomada/sitio.css      layout y componentes de página
```

Como las piezas de `design/plomada/` van después del vendor, **un `:root` ahí
sobrescribe cualquier token de Modernist sin tocar `design/modernist/`.** Ese
es el mecanismo central de F1.

La cadena completa, que se corre **al cierre de cada fase**:

```bash
python3 design/construir.py            # compone estilo.css; falla si queda una URL externa
python3 plomada/build.py               # regenera plomada/site/; corre test_privacy y BORRA site/ si falla
python3 -m pytest tests/               # puertas de calidad del repo
python3 plomada/servir.py              # (o python3 -m http.server -d plomada/site 8765) y se mira
```

Si tocas `frontend/src/**` (solo si eliges la variante de isla de Vue en F4):

```bash
npm --prefix frontend install
npm --prefix frontend run build        # regenera el bundle Y el MANIFIESTO.txt
```

`plomada/test_privacy.py::test_bundle_corresponde_a_fuentes` compara el hash
de `frontend/src/**` contra `MANIFIESTO.txt`: si editas un `.vue` y no
recompilas, el build de Python falla. No es un test roto, es la puerta.

---

## 2. Estado verificado del proyecto

Todo lo de esta sección se comprobó contra el repo y contra producción hoy
(2026-08-23), después de la fusión de ramas.

### 2.1 El repo ya está unificado

`main` (`ccd9d86`) tiene todo junto: el sitio `plomada/`, el sistema de diseño
`design/`, el API `api/` completo (7 tools de MCP + los routers de `/v1`),
`API.md` y `MCP.md` en la raíz, y `render.yaml` con la topología de tres
servicios. **Ya no hay que ir a buscar nada a otra rama.**

### 2.2 El sitio

- Lo genera `plomada/build.py` a `plomada/site/` (en `.gitignore`).
  **`build.py` es el ÚNICO escritor de `site/`.**
- Las ocho vistas pasan todas por `pagina()` (`plomada/build.py:89`): **un
  solo shell HTML, un solo `<nav>`** (`nav()`, `build.py:54`). Cambiar el nav
  o el `<head>` en un solo lugar cambia el sitio entero.
- La plantilla emite `<html lang="es">` sin `<head>` explícito; todo lo que va
  antes de `<body>` termina en el head que crea el navegador.
- El sitio se hidrata en el navegador contra el API real
  (`window.PLOMADA_API_URL`, inyectado en `pagina()`, `build.py:102`).
  `plomada/static/api.js` es el único módulo que habla HTTP con `/v1`.
- Patrón a copiar para las vistas nuevas: `pagina_buscar()` (`build.py:516`)
  es una vista que se hidrata entera en JS; `pagina_datos()` (`build.py:857`)
  es una vista de puro texto. F3 se parece a la segunda, F4 a la primera.

### 2.3 El API y el MCP están vivos (verificado con `curl`)

El servicio en producción **hoy** es `https://plumb-duy6.onrender.com`:

| Ruta | Estado | Nota |
|---|---|---|
| `GET /health` | 200 | |
| `GET /openapi.json` | 200 | 22 rutas, `info.title` = "Plomada API", v1.0.0 |
| `GET /docs` · `GET /redoc` | 200 | Swagger y ReDoc |
| `GET /v1` | 200 | catálogo de endpoints |
| `POST /chat` sin header | **422** | `{"error":{"codigo":"parametro_invalido","detalle":[{"loc":["header","X-Anthropic-Api-Key"],...}]}}` |
| `POST /mcp/` | 200 | `initialize` responde. **`/mcp` sin barra da 307** |

Endpoints `/v1`: `/v1`, `/v1/meta`, `/v1/banderas`, `/v1/titulares`,
`/v1/indicios`, `/v1/municipios`, `/v1/departamentos`, `/v1/tipos-obra`,
`/v1/fuentes`, `/v1/autosupervision`, `/v1/contratos`,
`/v1/contratos/{id_contrato}`, `/v1/entidades`, `/v1/entidades/{nit_entidad}`,
`/v1/proveedores`, `/v1/proveedores/{doc}`, `/v1/red/clusters`,
`/v1/red/clusters/{cluster_id}`, `/v1/alertas`, `/v1/alertas/resumen`.

Las 7 tools del MCP (verificado con `tools/list` contra producción, y coinciden
con `api/app/mcp/server.py`):

| Tool | Qué responde |
|---|---|
| `resumen_indicios` | cifras titulares y limitaciones |
| `buscar_contratos_atipicos` | contratos marcados, con filtros |
| `detalle_contrato` | ficha completa con cada bandera encendida |
| `perfil_entidad` | resumen de una entidad contratante |
| `buscar_proveedor` | perfil de un proveedor y su red |
| `alertas_preadjudicacion` | licitaciones que todavía aceptan ofertas |
| `glosario_banderas` | las 26 banderas con su peso |

**CORS está abierto** (`access-control-allow-origin: *`) en `/v1/*` y en
`/chat`, y el preflight de `/chat` ya permite `x-anthropic-api-key`
(`api/app/config.py:43` — `cors_origins` vacío significa abierto, a propósito:
los datos son públicos). **No hay ningún blocker de infraestructura: F3 y F4
se construyen y se prueban hoy contra producción.**

### 2.4 Dos URLs del API conviven — no hardcodees ninguna

`render.yaml` (recién actualizado) declara tres servicios y llama al API
`plomada-api`, con `SELF_URL: https://plomada-api.onrender.com`. **Ese host
todavía no existe: responde 404.** El Blueprint aún no se ha aplicado. Mientras
tanto:

- el que está vivo es `plumb-duy6.onrender.com`;
- `render.yaml` sigue apuntando el sitio a `PLOMADA_API_URL: https://plumb-duy6.onrender.com`;
- `plomada/build.py:25`, `plomada/static/api.js:32` y
  `pipeline/api_cliente.py:40` tienen ese mismo host como valor por defecto.

**Consecuencia para este plan:** las vistas nuevas toman la base del API de
`API_URL` (`build.py:25`, configurable con `PLOMADA_API_URL`) y de
`API_BASE` (`static/api.js`). **Ni una URL de API escrita a mano en el HTML
ni en el JS nuevo.** El día que se aplique el Blueprint, se cambia una
variable de entorno y las dos vistas se mudan solas.

Vale la pena avisarlo en el PR: `SELF_URL` y `PLOMADA_API_URL` de `render.yaml`
apuntan hoy a hosts distintos. No lo arregles desde este plan (es decisión de
quien maneje Render), pero no construyas nada que dependa de que coincidan.

### 2.5 Dónde ya está resuelto el color oscuro

Existe un set de tokens oscuros ya diseñado y con contraste razonado, de un
rebrand que quedó sin aplicar:

```
/home/rarechimera87/Server/Backups/Plumb-rebrand-2026-08-22/copias/design/PLAN_REBRAND.md   §3
```

Ese plan proponía **banda oscura única, sin conmutador**. Aquí se pide otra
cosa (dos tonos con conmutador), así que **no lo apliques tal cual**: lo que se
reutiliza son los **valores de token**, transplantados a un bloque
`[data-tema="oscuro"]`. Ya están copiados en §4.2 — no necesitas abrir el
backup, pero ahí está el razonamiento largo.

Ese backup también trae un cambio de tipografía (Instrument Serif) y una
paleta categórica nueva. **Nada de eso entra aquí.** Fuera de alcance.

---

## 3. Restricciones inviolables

Violar cualquiera tumba el build, el test o el proyecto.

1. **Cero dependencias externas en tiempo de carga.** Sin CDN, sin Google
   Fonts, sin npm en runtime. `design/construir.py` hace `sys.exit` si queda
   una URL externa en el CSS compuesto, y
   `test_privacy.py::test_bundle_sin_url_externa` hace lo mismo con el bundle.
2. **`design/modernist/` no se edita. Ni un carácter.** Todo va en
   `design/plomada/`. `git diff design/modernist/` debe quedar vacío.
3. **`plomada/static/estilo.css` no se edita a mano.** Lo genera
   `python3 design/construir.py`. Está commiteado: hay que commitear el
   regenerado, nunca editarlo.
4. **`plomada/build.py` es el único escritor de `plomada/site/`.**
5. **Cifras reales únicamente.** Prohibido inventar métricas o ejemplos con
   números falsos. Si falta un dato: `—` con nota "sin dato".
6. **Vocabulario prohibido.** `corrupt*`, `fraude*`, `fraudulent*`, `delito*`,
   `delictiv*` y similares tumban el build
   (`test_vocabulario`, más `test_vocabulario_json` que barre `site/**/*.json`
   y `test_vocabulario_fuentes` que barre `frontend/src/**`). El tono es
   **"indicio, no acusación"**. **Aplica a todo el texto nuevo de F3 y F4**,
   incluido el mensaje de bienvenida del asistente.
7. **Sin `v-html`** (`test_sin_v_html`) y sin `innerHTML` con texto que venga
   del API o del modelo. En F4 la respuesta del asistente se inserta con
   `textContent`, nunca como HTML.
8. **Leyenda siempre visible** en todo gráfico de 2+ series, y cada gráfico
   conserva su gemelo en tabla. F2 no puede romper esto.
9. **El satelital de Esri sigue siendo click-to-load.**

### Reglas que este plan REVOCA

| Regla revocada | Dónde está escrita | Reemplazo |
|---|---|---|
| "Banda clara. No hay modo oscuro en esta fase. No agregar `prefers-color-scheme`." | `design/PLAN_DISENO.md` §1.4 (líneas 51–52) | **Dos bandas con conmutador explícito.** `prefers-color-scheme` se usa **solo** para el tono inicial de quien nunca eligió; tras su primer clic manda su elección. |
| "Modo oscuro: DECIDIDO, queda fuera de la fase 1." | `design/plomada/VALIDACION.md` §3 (líneas 71–75) | Se ejecuta ahora. |
| Comentario "se pierde en esta fase a propósito… recuperarlo exige un set de tokens oscuros" | `design/plomada/dataviz.css` líneas 25–27 | El set existe (§4.2). Reescribe el comentario. |
| "Widget de chat… para quien trabaje `web/` (o el proyecto Vercel nuevo)" | `MCP.md` §4 | El front es `plomada/`. El widget se construye como una **vista propia del sitio** (F4). |

**Actualiza esos cuatro archivos** al cerrar la fase correspondiente. Si los
dejas contradiciendo el código, el próximo que lea el repo implementa la regla
vieja.

Lo que **no** cambia: mono acento (sin hues nuevos), radio 0, reglas de 2px,
flush left, tipografía Archivo. Esto es un cambio de **banda de color**, no un
rebranding.

---

## 4. F1 — Tokens de banda oscura y conmutador

La fase de mayor impacto y la más barata. Si solo alcanzas a hacer una, esta.

### 4.1 Una quinta pieza de CSS: `design/plomada/tema.css`

No metas los tokens oscuros dentro de `sitio.css` (ya tiene 491 líneas de
layout y se vuelve imposible de auditar). Crea una pieza nueva y **regístrala
en el build**.

**Editar `design/construir.py`:**

```python
TEMA = DESIGN / "plomada" / "tema.css"
...
def main():
    fuentes = leer(FUENTES)
    modernist = leer(MODERNIST)
    dataviz = leer(DATAVIZ)
    sitio = leer(SITIO)
    tema = leer(TEMA)
    ...
    piezas = [CABECERA, fuentes.strip(), filtrado.strip(), dataviz.strip(),
              sitio.strip(), tema.strip(), ""]
```

**`tema.css` va de ÚLTIMO**, después de `sitio.css`: `sitio.css` declara
tokens `--pl-*` y colores derivados, y el bloque de tema tiene que poder
ganarle a todo lo anterior sin depender de especificidad accidental.

En el mismo commit actualiza:
- la constante `CABECERA` de `construir.py` (dice "cuatro piezas", pasan a cinco)
  — se escribe literal en `estilo.css`;
- el docstring de `construir.py`, que las enumera;
- `design/VENDOR.md`, si menciona la composición de cuatro piezas.

### 4.2 El contenido de `design/plomada/tema.css`

El tono claro **no se redefine** (Modernist ya es claro; tocarlo duplicaría el
sistema). Solo se declara el delta oscuro, colgado del atributo `data-tema`
del `<html>`.

```css
/* ═══════════════════════════════════════════════════════════════════════
   Banda oscura de Plomada. Se compone de ULTIMO (design/construir.py), asi
   que estas declaraciones ganan sobre Modernist y sobre sitio.css sin
   tocar design/modernist/ (VENDOR.md lo prohibe).

   El tono claro NO se redefine aqui: Modernist ya es un sistema de banda
   clara y su :root es la definicion. Este archivo solo describe el delta
   oscuro. Un solo set de tokens cambia de valor; ni un componente, ni un
   grafico, ni una linea de JS sabe que existe un tema.

   El atributo lo pone el script anti-parpadeo del <head> (plomada/build.py,
   funcion pagina()) ANTES del primer pintado. Sin JS el sitio queda claro:
   es la degradacion deliberada, no un olvido.
   ═══════════════════════════════════════════════════════════════════════ */

:root { color-scheme: light; }

:root[data-tema="oscuro"] {
  color-scheme: dark;   /* scrollbars y controles nativos acompanan */

  /* fondo y superficies: negro calido, tenido al hue del acento */
  --color-bg:      #14100f;
  --color-surface: #1c1715;

  /* tinta: blanco roto calido, NUNCA #fff puro (deslumbra sobre negro) */
  --color-text:    #f2ebe8;

  /* divisores: hairline claro sobre fondo oscuro */
  --color-divider: color-mix(in srgb, #f2ebe8 14%, transparent);

  /* rampa neutra INVERTIDA: 100 = mas oscuro (rellenos), 900 = mas claro
     (texto sobre rellenos). El ROL de cada paso se conserva; lo que cambia
     es la direccion de la luz. Sin invertirla, todo componente que usa
     --color-neutral-200 como relleno pinta un bloque casi blanco. */
  --color-neutral-100: #1a1513;
  --color-neutral-200: #241d1a;
  --color-neutral-300: #332a26;
  --color-neutral-400: #493d38;
  --color-neutral-500: #6b5c56;
  --color-neutral-600: #8d7d76;
  --color-neutral-700: #b0a099;
  --color-neutral-800: #d2c5bf;
  --color-neutral-900: #f2ebe8;

  /* la rampa de acento NO se invierte: Modernist ya la disena para las dos
     bandas (usa el paso 600 sobre claro y el 400 sobre oscuro). Solo suben
     de luminosidad para respirar sobre #14100f. */
  --color-accent: #ff5334;
  --color-accent-100: #2b120c;
  --color-accent-200: #3f1810;
  --color-accent-300: #5c1f14;
  --color-accent-400: #8a2a17;
  --color-accent-500: #c23a1e;
  --color-accent-600: #ff5334;
  --color-accent-700: #ff7a60;
  --color-accent-800: #ffa593;
  --color-accent-900: #ffd0c6;

  /* --color-accent-2-* es un relleno derivado a maquina en Modernist, no un
     rol real. Se alinea con el acento para que no quede un hue huerfano. */
  --color-accent-2:     #ff5334;
  --color-accent-2-100: #2b120c;
  --color-accent-2-200: #3f1810;
  --color-accent-2-300: #5c1f14;
  --color-accent-2-400: #8a2a17;
  --color-accent-2-500: #c23a1e;
  --color-accent-2-600: #ff5334;
  --color-accent-2-700: #ff7a60;
  --color-accent-2-800: #ffa593;
  --color-accent-2-900: #ffd0c6;

  /* sombras: las de Modernist son ink-tinted sobre fondo claro y sobre negro
     son invisibles. En banda oscura el trabajo de separar lo hace el
     hairline superior (simula luz cenital); la sombra queda como oscuridad
     ambiental. */
  --shadow-sm: 0 1px 2px rgb(0 0 0 / 0.40), inset 0 1px 0 color-mix(in srgb, #f2ebe8 8%, transparent);
  --shadow-md: 0 6px 18px rgb(0 0 0 / 0.50), inset 0 1px 0 color-mix(in srgb, #f2ebe8 8%, transparent);
  --shadow-lg: 0 16px 44px rgb(0 0 0 / 0.60), inset 0 1px 0 color-mix(in srgb, #f2ebe8 8%, transparent);
}
```

**Lo que NO hay que tocar, y por qué:** `design/plomada/dataviz.css` **no
tiene un solo hex** — todos sus `--viz-*` son `var(--color-*)` (verificado:
`--viz-superficie: var(--color-bg)`, `--viz-tinta: var(--color-text)`,
`--viz-seq-1..5: var(--color-accent-500..900)`,
`--viz-sin-dato: var(--color-neutral-300)`). Al re-tokenizar, los cinco
gráficos y la coropleta se re-colorean solos. **No dupliques tokens `--viz-*`
en `tema.css`.** Lo único que se toca en `dataviz.css` es el comentario
obsoleto de las líneas 25–27.

Después de escribir el bloque, corre este grep y **revisa cada uso a ojo en el
navegador**. La inversión de la rampa es lo más fácil de arruinar; son ~19
usos, acotados:

```bash
grep -n 'color-neutral-' design/modernist/styles.css design/plomada/*.css
```

Atención a `.aviso-fijo`, que usa `accent-100` de fondo y `accent-800` de
texto: con esta rampa queda relleno `#2b120c` con texto `#ffa593`, que es
correcto — pero **confírmalo**, porque es el componente que lleva la salvedad
legal y tiene que ser legible siempre.

### 4.3 El atributo `data-tema` y el script anti-parpadeo

Sin esto, una recarga en modo oscuro pinta medio segundo de blanco. El script
tiene que ser **inline y síncrono, en el `<head>`, antes del primer pintado**.
No puede ser un `<script src>` diferido.

**Editar `plomada/build.py`, función `pagina()` (línea 89).** Después de
`<link rel="stylesheet" href="/static/estilo.css">` y antes de la línea de
`window.PLOMADA_API_URL`:

```python
# Script anti-parpadeo: fija data-tema ANTES del primer pintado. Inline y
# sincrono a proposito -- un <script src> diferido dejaria un flash blanco
# en cada recarga en modo oscuro. Va en pagina(), o sea en TODAS las vistas
# a la vez (las ocho de hoy mas /api/ y /asistente/), porque el shell es uno.
TEMA_INLINE = (
    '<script>(function(){try{'
    "var t=localStorage.getItem('plomada:tema');"
    "if(t!=='claro'&&t!=='oscuro'){"
    "t=window.matchMedia('(prefers-color-scheme: dark)').matches?'oscuro':'claro';}"
    "document.documentElement.setAttribute('data-tema',t);"
    '}catch(e){}})();</script>'
)
```

Reglas que este script codifica:

- **Clave de `localStorage`: `plomada:tema`.** Valores válidos `"claro"` |
  `"oscuro"`; cualquier otra cosa se ignora y se cae al sistema. (El prefijo
  `plomada:` es el que ya usa `static/api.js` en `sessionStorage`.)
- **Sin elección guardada → manda `prefers-color-scheme`.** Con elección
  guardada → manda la elección, siempre.
- **El `try/catch` no es decorativo:** en modo privado de algunos navegadores
  `localStorage` lanza al leer. Si lanza, queda claro y el sitio funciona.
- Sin JS: no hay atributo, el sitio queda claro. Degradación aceptada. **No**
  agregues un `@media (prefers-color-scheme: dark)` suelto para cubrirlo:
  duplicaría el bloque de tokens y crearía dos fuentes de verdad que se
  desincronizan.

### 4.4 El botón, en `nav()`

**Editar `plomada/build.py`, función `nav()` (línea 54).** Va al final,
después de los enlaces:

```python
BOTON_TEMA = (
    '<button type="button" class="nav-tema" id="conmutar-tema" '
    'aria-pressed="false" title="Cambiar entre tono claro y oscuro">'
    '<span class="nav-tema-icono" aria-hidden="true"></span>'
    '<span class="nav-tema-texto">Tono oscuro</span>'
    '</button>'
)
```

Accesibilidad, no negociable:

- Es un `<button type="button">`, **no** un `<a>` ni un `<div>`. Se enfoca con
  Tab y se activa con Enter y Espacio gratis.
- `aria-pressed` refleja el estado y lo actualiza el JS en cada cambio. El HTML
  lo emite en `false` porque el servidor no sabe el tema del lector; el JS lo
  corrige al montar, antes de cualquier interacción.
- El texto visible cambia con el estado: en claro dice **"Tono oscuro"** (la
  acción, no el estado), en oscuro **"Tono claro"**. Si prefieres solo icono,
  `.nav-tema-texto` pasa a ser texto para lectores de pantalla — **nunca un
  botón sin nombre accesible**.
- El icono se dibuja **en CSS** (un círculo con `box-shadow` que se vuelve
  luna) o se agrega un `<symbol>` a `plomada/static/iconos.svg`, que hoy solo
  tiene `id="info"`. **No** metas un SVG externo ni una fuente de iconos.

`.nav` tiene `overflow-x: auto` (en `sitio.css`) y
`.nav-brand { margin-right: auto }`, así que el botón cae a la derecha y a
320px entra en el scroll horizontal del propio nav. En F3 se le suma el enlace
«API»: **revisa el nav a 320px al cerrar F3, no antes**.

### 4.5 `plomada/static/tema.js`

Módulo nuevo. `build.py` ya copia `static/` entero a `site/`, así que no hay
que registrar nada; solo cargarlo desde `pagina()` para todas las vistas.

Contrato del módulo — respétalo, F2 depende de él:

```js
/* Conmutador de tono. El tema YA esta aplicado cuando esto corre: lo fijo el
 * script inline del <head> (build.py, TEMA_INLINE) antes del primer pintado.
 * Este modulo solo (a) sincroniza el boton con el estado real y (b) conmuta.
 *
 * Emite un evento 'plomada:tema' en document cuando el tono cambia, con
 * detail = { tema: 'claro' | 'oscuro' }. Los graficos y el mapa se
 * suscriben a eso para re-leer los tokens --viz-* (F2). El CSS no necesita
 * el evento: los tokens cambian solos.
 */
const CLAVE = 'plomada:tema';

export function temaActual() {
  return document.documentElement.getAttribute('data-tema') === 'oscuro' ? 'oscuro' : 'claro';
}

export function aplicar(tema) {
  document.documentElement.setAttribute('data-tema', tema);
  try { localStorage.setItem(CLAVE, tema); } catch { /* modo privado: se pierde al cerrar, no rompe */ }
  sincronizarBoton();
  document.dispatchEvent(new CustomEvent('plomada:tema', { detail: { tema } }));
}
// ... sincronizarBoton() actualiza aria-pressed y el texto del boton
// ... el listener del click llama aplicar(temaActual() === 'oscuro' ? 'claro' : 'oscuro')
```

Detalle que se olvida siempre: **si el lector nunca eligió, el sitio debe
seguir al sistema en vivo.** Suscríbete a
`matchMedia('(prefers-color-scheme: dark)')` con `addEventListener('change', …)`
y aplica el cambio **solo si `localStorage` no tiene valor guardado**. En
cuanto el lector pulsa el botón una vez, esa suscripción deja de mandar.

### 4.6 CSS del botón, en `design/plomada/sitio.css`

Va en `sitio.css` (es un componente de página), no en `tema.css` (solo tokens).
Junto al bloque `─── nav ───` que ya existe:

- Hereda tipografía y tamaño de `.nav a` (14px) pero **no** sus reglas: `.nav a`
  no aplica a un `<button>`. Escribe `.nav-tema` explícito.
- `background: none; border: 0; color: inherit; cursor: pointer;` y
  `white-space: nowrap` (como `.nav a`, para el scroll a 320px).
- Hover y `:focus-visible` como los enlaces del nav
  (`color: var(--color-accent)`), con `outline: 2px solid` visible en las dos
  bandas.
- Alto de toque mínimo 44px en móvil (padding, no `height` fija).
- Transición con `--pl-dur` / `--pl-ease`, que ya existen.
  **Respeta `@media (prefers-reduced-motion: reduce)`**: sin transición.

Opcional y recomendado: transición corta de `background-color` y `color` en
`body` para que el cambio no sea un salto seco. Máximo `--pl-dur` (140ms), y
también dentro del guard de `prefers-reduced-motion`.

### Aceptación de F1

- [ ] Los comandos de §1 en verde. `git diff design/modernist/` vacío.
- [ ] `estilo.css` regenerado y commiteado; su cabecera dice "cinco piezas".
- [ ] Las ocho vistas cargan en oscuro **sin un solo bloque blanco huérfano**.
- [ ] Recarga en oscuro: **cero destello blanco**.
- [ ] La elección sobrevive a recargar, navegar, y cerrar y reabrir la pestaña.
- [ ] Sin elección guardada, el sitio sigue el tono del sistema **en vivo**.
- [ ] Tras pulsar el botón, el tono del sistema ya no lo pisa.
- [ ] Ningún texto por debajo de **4,5:1** contra su fondo en ninguna banda.
      Revisa `.aviso-fijo`, `.migas`, `.tenue`, `.nota`, y todos los
      `color-mix(... 50%/55%/60% ...)` de `sitio.css`: sobre negro adelgazan
      mucho más que sobre hueso.
- [ ] El botón se alcanza con Tab, se activa con Enter y Espacio, y su
      `aria-pressed` cambia.
- [ ] `PLAN_DISENO.md` §1.4, `VALIDACION.md` §3 y el comentario de
      `dataviz.css` actualizados.

---

## 5. F2 — Que los gráficos y el mapa acompañen el cambio

**El problema, verificado:** el CSS cambia solo, pero los gráficos **no**.
Todos leen los tokens con `getComputedStyle` **una vez, al dibujar**, y pintan
SVG con los valores ya resueltos. Al conmutar quedan con los colores de la
banda anterior — texto oscuro sobre fondo oscuro.

Los tres puntos exactos:

| Archivo | Qué hace |
|---|---|
| `plomada/static/graficos/comun.js:17` | `export function tonosViz()` — la llama cada gráfico al inicio de su `dibujar()` |
| `plomada/static/mapa.js:16` | `function leerTonosViz()`, cacheada en `var TONO = leerTonosViz()` **al cargar el módulo** |
| `plomada/static/graficos/{municipios,departamentos,indicios,red}.js` | cada uno hace `const T = tonosViz()` dentro de su `dibujar()` |

La buena noticia: **como cada `dibujar()` re-lee los tonos, basta con volver a
llamarlo.** No hay que refactorizar los gráficos.

### 5.1 Tablero — `plomada/static/tablero.js`

Ya tiene las funciones de re-dibujo que usa al cambiar un filtro:
`dibujarTerritorio(D)` (línea 120) y `dibujarRed(D)` (línea 137), más
`Indicios.dibujar(...)` en el arranque. Suscribe lo mismo al evento:

```js
document.addEventListener('plomada:tema', () => {
  // mismo camino que un cambio de filtro: cada dibujar() vuelve a leer
  // tonosViz(), asi que no hay que tocar los modulos de grafico.
  dibujarTerritorio(D);
  dibujarRed(D);
  // y el grafico de indicios, que hoy solo se pinta en cargar()
});
```

Cuidado con el alcance de `D` (los datos cargados): vive dentro de `cargar()`.
Registra el listener **dentro de ese alcance**, después de que `D` exista, no
en el tope del módulo.

Verifica que re-dibujar no duplique nodos: los `dibujar()` deben limpiar su
contenedor antes de pintar (hoy lo hacen, porque el cambio de filtro ya
funciona — confírmalo, no lo asumas).

### 5.2 Mapa — `plomada/static/mapa.js`

Aquí sí hay una línea que corregir: `var TONO = leerTonosViz();` (línea 14)
cachea los tonos **al cargar el módulo**. Hay que reasignar y re-estilar la
capa de Leaflet:

```js
document.addEventListener('plomada:tema', function () {
  TONO = leerTonosViz();           // reasignar, no crear una variable nueva
  if (capa) capa.setStyle(estilo);  // estilo(f) ya usa TONO por closure
  // si hay un departamento seleccionado, re-aplicar su estilo de seleccion
  // y repintar la leyenda si esta dibujada con colores resueltos en JS
});
```

`estilo(f)` (línea 37) lee `TONO` por closure, así que con reasignar y llamar
`setStyle` la coropleta entera se recolorea. **La coropleta no tiene tile
layer** (`mapa.js` nunca llama `L.tileLayer`): es GeoJSON sobre el fondo de la
página, así que el fondo se oscurece gratis.

El mapa **satelital** de la ficha (`mapa-satelital.js`, tiles de Esri) es una
foto: no tiene tema y no se toca. Lo que sí hay que revisar es el marco, los
controles y el texto de atribución alrededor.

### 5.3 Leaflet

`plomada/static/vendor/leaflet/leaflet.css` es **vendor**: no se edita. Sus
controles (`.leaflet-control-zoom`, `.leaflet-popup`,
`.leaflet-control-attribution`) traen fondo blanco y texto oscuro fijos: en
banda oscura quedan como parches blancos.

Solución: **overrides en `design/plomada/sitio.css`**, colgados de
`:root[data-tema="oscuro"]` y escritos con `var(--color-*)`, nunca con hex. Es
el mismo mecanismo que ya usa el proyecto para no parchear el vendor.

### 5.4 Islas de Vue

`CifraLider.vue` es el único componente hoy. Si pinta con colores resueltos en
JS, aplica lo mismo; si solo usa clases CSS, no hay nada que hacer.
**Compruébalo antes de tocar nada**, y si tocas `frontend/src/**` recuerda
`npm --prefix frontend run build` o el build de Python falla por el hash del
manifiesto.

### Aceptación de F2

- [ ] Conmutar en `/tablero/`: los cinco gráficos se re-pintan legibles, con
      leyenda y tabla gemela intactas.
- [ ] Conmutar en `/mapa/`: la coropleta cambia de rampa, los bordes de
      departamento se ven, el panel lateral acompaña.
- [ ] Los controles de Leaflet no quedan como parches blancos.
- [ ] Conmutar varias veces seguidas no duplica nodos ni deja tooltips colgados.
- [ ] Conmutar con un filtro aplicado **conserva el filtro** (solo re-dibuja,
      no re-consulta el API).
- [ ] Todas las vistas, no solo tablero y mapa: ficha de contrato, municipio,
      buscador y metodología también pintan cosas en JS.

---

## 6. F3 — Construir la vista `/api/` y ponerla en la navegación

**Esta vista no existe. Se construye entera en esta fase.** No es documentación
en Markdown: es una página del sitio, generada por `build.py`, que un lector
visita en `https://<sitio>/api/`.

### 6.1 Decisión: el enlace del nav apunta a una vista del sitio, no al Swagger

| Opción | Veredicto |
|---|---|
| **A. Nav → `/api/`, vista propia que documenta y enlaza a `/docs`, `/v1` y `/mcp/`** | **Elegida.** El nav no sale del sitio en ningún enlace hoy; el primero no debería mandar a un Swagger crudo, sin la marca ni el aviso "indicio, no acusación". Además el API está en Render free tier y tarda 30–60 s en despertar: un enlace directo desde el nav parecería un sitio caído. La vista local carga instantánea y avisa. Y es donde cuelga, en F4, la entrada al asistente. |
| B. Nav → `https://…/docs` en pestaña nueva | Rechazada por lo anterior. Se conserva **dentro** de `/api/` como enlace destacado. |

### 6.2 Cambios en `plomada/build.py`

1. **`NAV_ENLACES`** (línea 48): agregar `("/api/", "API")`, **después de
   `/datos/`** — «Datos» son descargas para lectores, «API» es acceso
   programático; el orden va de más general a más técnico.
2. **`pagina_api()`**: función nueva, con el patrón de `pagina_datos()`
   (`build.py:857`) y `pagina_metodologia()` (`build.py:584`). Devuelve
   `pagina(titulo="API", descripcion=…, cuerpo=…, ruta="/api/")`.
3. **`main()`**: `escribir("api/index.html", pagina_api())`.
4. **Sitemap** (línea 1107): agregar `"/api/"` a la lista de URLs estáticas.
   Si no, la página existe pero no se indexa.
5. **Texto largo → `plomada/contenido.py`**, no incrustado en `build.py`. Ese
   archivo existe para que el texto editorial se corrija sin tocar código.
   Añade ahí las constantes (`API_INTRO`, `API_CONVENCIONES`, …).

### 6.3 Qué contiene la vista

Todo verificable contra producción: **no inventes ni un endpoint ni un campo**.
La referencia canónica es `API.md`, **que ahora está en la raíz del repo** (ya
no hay que sacarlo de otra rama), y el `openapi.json` en vivo.

1. **Qué es y qué no.** Datos 100% públicos del SECOP II, solo lectura, sin
   autenticación. Repetir la salvedad: **indicio para priorizar revisión, no
   acusación**. Usa el bloque `aviso_fijo()` que ya existe (`build.py:78`) — no
   escribas un aviso nuevo.
2. **Empezar en 30 segundos:** dos o tres `curl` reales y copiables (por
   ejemplo `GET /v1/meta` y
   `GET /v1/contratos?departamento=SANTANDER&limite=5`). **Córrelos antes de
   publicarlos.**
3. **Convenciones:** el sobre `{datos, meta}`, los errores
   `{error:{codigo,mensaje,detalle}}`, la paginación (`limite` tope 200,
   `desplazamiento`, `meta.paginacion.total`) y `?formato=csv` en los listados.
4. **Tabla de los 20 endpoints `/v1`** (lista exacta en §2.3), una línea cada
   uno. No dupliques `API.md` entero: enlaza a `/docs` para el detalle.
5. **Advertencia de cold start.** Render free tier: la primera llamada puede
   tardar 30–60 s. Dilo, con el mismo tono con que `static/api.js` ya avisa
   "el servicio está despertando".
6. **Enlaces salientes** (`rel="noopener"`, marcados visualmente como que salen
   del sitio): `/docs`, `/redoc`, `/openapi.json`, `/v1`.
7. **La sección del MCP y la entrada al asistente**, que llena F4 (§7.1).

Detalles de implementación:

- **La base del API no se hardcodea en el HTML**: sale de `API_URL`
  (`build.py:25`), configurable con `PLOMADA_API_URL`. Los `curl` de ejemplo se
  construyen interpolando esa variable en Python, no escribiéndola a mano.
  Razón concreta: `render.yaml` ya declara un host futuro distinto (§2.4).
- **Escapa todo con `h()`.** `test_privacy.py` revisa que no haya markup crudo.
- Vocabulario: cero palabras prohibidas (§3.6).

### Aceptación de F3

- [ ] **`/api/` existe**: `plomada/site/api/index.html` se genera y abre en el
      navegador.
- [ ] «API» aparece en el nav de todas las vistas y marca `aria-current="page"`
      en `/api/`.
- [ ] Se ve bien **en claro y en oscuro**, incluidos los `<pre>` de código.
- [ ] Cada `curl` de la página, copiado y pegado, funciona.
- [ ] Cada endpoint listado existe en `openapi.json`. Cero endpoints inventados.
- [ ] Ninguna URL de API escrita a mano en el HTML generado: todas salen de
      `API_URL`.
- [ ] `/api/` está en `sitemap.xml`.
- [ ] El nav a **320px** sigue usable con el enlace nuevo más el botón de tono.
- [ ] `python3 plomada/build.py` pasa `test_privacy`.

---

## 7. F4 — Construir la vista del asistente (MCP)

**Antes de escribir una línea: el servidor MCP no hay que construirlo.** Está
en `api/app/mcp/server.py`, desplegado y verificado: 7 tools en
`https://plumb-duy6.onrender.com/mcp/` (§2.3). Lo que falta es **la vista**, y
hay que construirla desde cero: hoy no hay una sola línea de chat en
`plomada/` (§0).

Dos piezas.

### 7.1 Pieza A — Sección «Conecta tu propio cliente» dentro de `/api/`

La más barata y la que más valor entrega por línea escrita. Un bloque en la
vista de F3 que explique que los mismos datos están disponibles como servidor
MCP, para quien use Claude Desktop, Claude Code o cualquier cliente con
soporte de MCP remoto.

Contenido, todo verificado:

- **URL del servidor:** `{API_URL}/mcp/` — **con barra final**. Sin ella el
  servicio responde 307 y algunos clientes no siguen el redirect en un POST.
  Dilo explícitamente en la página.
- **Transporte:** streamable-http. Sin autenticación: solo lectura sobre datos
  públicos.
- **Tabla de las 7 tools** con una línea de qué responde cada una (§2.3).
- **Un bloque de configuración copiable** para el cliente. Escríbelo contra la
  forma que documente el cliente al que apuntes; no lo inventes de memoria. Si
  no puedes verificar el formato exacto, publica **solo la URL y el
  transporte** y enlaza a la documentación del cliente: mejor eso que un JSON
  que no funcione.
- **La misma salvedad de siempre:** el servidor declara en sus `instructions`
  que "riesgo" es indicio, no prueba. Decirlo también en la página.
- Enlaces a `MCP.md` y `API.md` en GitHub para el detalle de arquitectura.

Esta pieza **no necesita JavaScript**: es HTML generado por `build.py`. Si el
tiempo se acaba, esto solo ya cumple "el MCP está en el sitio".

### 7.2 Pieza B — La vista `/asistente/`

**Decisión: el chat es una vista propia con URL propia, no un widget flotante
pegado en una esquina.** Razones, en orden:

1. Es la tesis del sitio: *"cada contrato, municipio y búsqueda tiene una URL
   real y compartible"* (`build.py`, docstring). Un asistente que solo existe
   como burbuja no se puede enlazar, ni compartir, ni entrar al sitemap.
2. El flujo BYOK necesita espacio: pedir la key, explicar de dónde sale,
   explicar que Plomada no cobra nada. En una burbuja de 320×400 eso es un
   embudo apretado.
3. Es una vista más que pasa por `pagina()`, así que hereda nav, pie, aviso
   legal y tema sin trabajo extra.

**No** va en el nav (ya entra «API» en F3; siete entradas es demasiado). Se
llega desde: un enlace destacado en `/api/` (pieza A), y un botón en
`/tablero/` («Pregúntale a los datos»), que es donde el lector tiene cifras
delante y le nacen las preguntas.

Construcción, en paralelo a `pagina_buscar()` (`build.py:516`), que es la vista
del sitio que más se le parece (shell estático + hidratación en JS):

1. **`pagina_asistente()`** en `plomada/build.py` → `pagina(titulo="Asistente",
   …, ruta="/asistente/")`, con el fallback sin JS pre-renderizado (un mensaje
   que explique que el asistente necesita JavaScript y enlace a `/buscar/` y
   `/api/` como alternativas).
2. **`escribir("asistente/index.html", pagina_asistente())`** en `main()`.
3. **`"/asistente/"` al sitemap** (línea 1107).
4. **`plomada/static/chat.js`**, módulo nuevo.
5. **Texto editorial en `plomada/contenido.py`** (`ASISTENTE_INTRO`,
   `ASISTENTE_KEY_AYUDA`, …).
6. **Estilos en `design/plomada/sitio.css`**, con tokens, cero hex.

#### El contrato del backend, ya verificado contra producción

| | |
|---|---|
| **Endpoint** | `POST {API_URL}/chat` |
| **Header obligatorio** | `X-Anthropic-Api-Key: <la key del usuario>` |
| **Body** | `{"mensaje": "...", "historial": [{"role":"user"\|"assistant","content":"..."}]}` |
| **Respuesta** | stream SSE: líneas `data: {"delta":"..."}` hasta un `data: {"done":true}`, o `data: {"error":"..."}` |
| **Sin el header** | HTTP **422** con `{"error":{"codigo":"parametro_invalido","detalle":[{"loc":["header","X-Anthropic-Api-Key"],…}]}}` |
| **Key inválida** | evento SSE `{"error":"Tu API key de Anthropic no es valida"}` |
| **CORS** | abierto (`*`); el preflight ya permite `x-anthropic-api-key` |

#### BYOK: cada usuario usa su propia API key

No existe una key del equipo en el servidor y **no debe existir una en el
front**. Reglas que no se negocian:

- Se pide **una vez**, en un `<input type="password">`, con un enlace
  explicando de dónde se saca (`console.anthropic.com/settings/keys`).
- Se guarda en **`localStorage`**, nunca en cookie, nunca en el servidor,
  nunca en la URL.
- Se manda en el header de cada `/chat`. Si vuelve 422 o el evento de key
  inválida, **se borra la guardada y se vuelve a pedir** — no reintentar en
  silencio.
- Una línea visible: Plomada no gestiona el cobro de nadie; cada quien ve su
  consumo en su cuenta de Anthropic.
- **Nunca loguear la key**, ni en `console.log` ni dentro de un mensaje de
  error.
- Un botón para **olvidar la key guardada**. Es la contraparte honesta de
  pedirla.

#### Implementación de `chat.js`

- **JS plano**, siguiendo el patrón de los otros módulos de `static/`.
  **Recomendado sobre la isla de Vue**: es un formulario más un stream, no
  necesita reactividad profunda, y evita recompilar el bundle y el manifiesto
  en cada ajuste. Si aun así prefieres una isla, va en
  `frontend/src/componentes/` y **hay que correr
  `npm --prefix frontend run build`** en cada cambio.
- **Toma la base del API de `API_BASE` de `static/api.js`.** No releas
  `window.PLOMADA_API_URL` por tu cuenta y no escribas el host a mano (§2.4).
  `/chat` no encaja en `pedir()` (es SSE, no el sobre `{datos, meta}`), así que
  `chat.js` hace su propio `fetch` — pero la **base** es la misma.
- **Leer el stream** con `fetch` + `response.body.getReader()` y un
  `TextDecoder`, partiendo por `\n\n` y quitando el prefijo `data: `.
  `EventSource` **no sirve**: no permite headers ni POST. Acumula el buffer
  entre chunks — un evento SSE puede llegar partido.
- **Renderizar el texto del modelo con `textContent`, jamás `innerHTML`**
  (§3.7). Para saltos de línea, `white-space: pre-wrap` en CSS.
- **Historial en el navegador**, mandado completo en cada request (decisión ya
  tomada en `MCP.md`). Pon un tope de turnos y avisa al truncar.
- **Estados que hay que dibujar**, no solo el feliz:
  - sin key → pedirla;
  - key inválida / 422 → mensaje claro y volver a pedirla;
  - error de red → "el asistente no está disponible ahora";
  - **cold start**: si no hay primer `delta` a los ~3 s, "el servicio está
    despertando". `static/api.js` ya tiene ese patrón
    (`AVISO_DESPERTANDO = 3000`): cópialo, no lo reinventes;
  - `abort` al enviar otra pregunta o al salir: cancela con `AbortController`.
- **Accesibilidad:** el área de respuesta es `aria-live="polite"`; el input
  tiene `<label>`; Enter envía y Shift+Enter hace salto de línea; el foco va al
  input al cargar.
- **Aviso permanente:** la vista muestra `AVISO_CORTO` de `contenido.py`
  ("Indicio para revisión, no acusación") siempre visible. Una respuesta del
  modelo es una cifra más y lleva la misma salvedad que las demás.
- **Preguntas de arranque** (3 o 4 sugeridas, clicables) para que la vista no
  sea un cuadro de texto vacío. Escríbelas contra las tools que existen —
  "¿qué contratos atípicos hay en Santander?" funciona porque existe
  `buscar_contratos_atipicos`; no sugieras nada que ninguna tool pueda
  responder.

### Aceptación de F4

- [ ] **`/asistente/` existe**: `plomada/site/asistente/index.html` se genera,
      abre, y está en el sitemap.
- [ ] Se llega desde `/api/` y desde `/tablero/`.
- [ ] Sin JavaScript, la vista muestra el fallback y no una página en blanco.
- [ ] `/api/` documenta el servidor MCP con la URL correcta **con barra final**
      y las 7 tools reales.
- [ ] Con una API key válida, una pregunta como "¿cuántos contratos atípicos
      hay en Santander?" devuelve respuesta en streaming que **cita datos
      reales** (se nota porque el modelo llamó a las tools).
- [ ] Sin key: se pide. Con key basura: mensaje claro y se vuelve a pedir. Con
      el API apagado: mensaje de no disponible, sin excepción en consola.
- [ ] La key **no aparece** en ningún log, ni en la URL, ni en el DOM. El botón
      de olvidarla funciona.
- [ ] La vista se ve bien en claro y en oscuro, y en móvil.
- [ ] `python3 plomada/build.py` pasa `test_privacy`, incluido
      `test_vocabulario_fuentes` si tocaste `frontend/src/**`.
- [ ] Si tocaste `frontend/src/**`: bundle y `MANIFIESTO.txt` regenerados.

---

## 8. Lo que este plan NO pide

Para que no se te vaya el tiempo:

- **No** reconstruir el servidor MCP, el proxy `/chat` ni los routers `/v1`.
  Están construidos y desplegados. En F3 y F4 **solo se consumen**.
- **No** tocar `api/`, `pipeline/`, `sql/` ni `render.yaml`. Todo el trabajo es
  `plomada/` + `design/` + `docs/`.
- **No** aplicar el Blueprint de Render ni migrar de `plumb-duy6` a
  `plomada-api`. Es decisión de quien maneje la cuenta. Este plan solo exige
  que nada quede hardcodeado para que esa migración sea una variable de entorno.
- **No** el rebranding del backup (Instrument Serif, radios suaves, paleta
  categórica). Esto cambia la **banda de color**, no el sistema.
- **No** tocar `design/modernist/` ni `web/index.html` (el tablero anterior).
- **No** soporte para Gemini (`MCP.md` lo deja fuera de v1 con razón).
- **No** rate limiting de `/chat` ni historial en servidor.

---

## 9. Puntos de corte y orden de commits

**F2 depende de F1** (sin el evento `plomada:tema` no hay a qué suscribirse).
**F4 depende de F3** (la sección de MCP y la entrada al asistente viven en la
vista `/api/`). F3 es independiente de F1–F2 y puede adelantarse si conviene,
pero entonces revísala después en oscuro.

| Si paras después de… | El sitio queda… |
|---|---|
| **F1** | Publicable. Dos tonos, conmutador funcionando. Los gráficos y el mapa se ven con los colores de la banda anterior hasta recargar — **feo pero no roto**. |
| **F2** | Publicable y coherente. Corte natural del trabajo de tema. |
| **F3** | Publicable. Nav con «API» y una vista que ya sirve sola. |
| **F4 pieza A** | Publicable. El MCP documentado y conectable desde cualquier cliente, sin chat en el sitio. **Corte recomendado si el tiempo aprieta.** |
| **F4 pieza B** | Todo el encargo. |

Un commit por fase, mínimo. En cada commit incluye el `estilo.css` regenerado
si tocaste CSS (está commiteado y el build lo verifica), y **nunca**
`plomada/site/` (está en `.gitignore`).

### Checklist final

```bash
python3 design/construir.py
python3 plomada/build.py
python3 -m pytest tests/
git diff --stat design/modernist/          # tiene que salir vacío
git status --porcelain                     # ningún site/ ni artefacto suelto
ls plomada/site/api/index.html plomada/site/asistente/index.html   # las dos vistas nuevas
```

Y a ojo, en el navegador, en las dos bandas: `/`, `/tablero/`, `/mapa/`,
`/buscar/`, `/metodologia/`, `/datos/`, **`/api/`**, **`/asistente/`**, una
ficha de contrato y una de municipio. Diez vistas por dos tonos: veinte
pantallas. Míralas.
