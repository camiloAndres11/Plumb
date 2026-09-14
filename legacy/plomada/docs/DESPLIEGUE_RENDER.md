# Desplegar Plomada en Render

El sitio es **estático + dinámico**: `plomada/build.py` genera `plomada/site/`
(unas 15 páginas, 2,3 MB) y el navegador hidrata las fichas, el buscador y los
municipios contra el API. Render solo sirve archivos; no hay servidor propio.

Todo lo de aquí está verificado contra este repo, no es genérico.

---

## 1. Qué se despliega (y qué no)

| Servicio | Qué es | Estado |
|---|---|---|
| **plomada-sitio** | Static Site. Lo que crea esta guía. | por crear |
| **plumb-duy6** | El API `/v1/*` + `/chat`. Ya existe. | ya desplegado |

El sitio **depende** del API en dos momentos distintos, y conviene no
confundirlos:

- **En el build**: unas 70 llamadas (el tablero, las cifras de portada y el
  sitemap de 12.678 fichas). Si el API falla aquí, el build termina pero
  `test_privacy.py` no deja publicar — y Render conserva el despliegue
  anterior. Eso es deliberado.
- **En cada visita**: el navegador del lector llama al API directamente. Si el
  API está caído entonces, cada vista muestra "No hay datos disponibles" y el
  aviso legal sigue visible, porque va en el HTML estático.

---

## 2. Requisitos previos

- El repo en GitHub, con `main` (o la rama que quieras) actualizada.
- Los archivos `render.yaml` y `plomada/requirements.txt` commiteados — los dos
  ya están en el repo.
- **No hace falta** `out/`, ni el warehouse, ni `duckdb`. El build solo instala
  `requests`. Verificado: construye con el Python del sistema sin duckdb
  instalado, cayendo a `plomada/fixtures/` para los pocos chequeos que aún
  leen datos locales.

---

## 3. Desplegar con el Blueprint (recomendado)

El repo ya trae `render.yaml`. Con eso Render configura todo solo, incluidas
las reglas de reescritura que son obligatorias (§5).

1. En Render: **New → Blueprint**.
2. Conecta el repositorio y elige la rama.
3. Render lee `render.yaml` y propone el servicio `plomada-sitio`. Revisa que
   diga:
   - Build command: `pip install -r plomada/requirements.txt && python3 plomada/build.py`
   - Publish directory: `./plomada/site`
4. **Apply**.

El primer build tarda ~2 min: casi todo es el recorrido de las 12.678 fichas
para el sitemap (64 llamadas al API, ~25 s) más la instalación de `requests`.

### Si prefieres hacerlo a mano (sin Blueprint)

**New → Static Site**, y luego:

| Campo | Valor |
|---|---|
| Build Command | `pip install -r plomada/requirements.txt && python3 plomada/build.py` |
| Publish Directory | `plomada/site` |
| Environment Variable | `PLOMADA_API_URL` = `https://plumb-duy6.onrender.com` |

Y **añade las reglas de §5 a mano**, o las fichas darán 404.

---

## 4. Variables de entorno

| Variable | Para qué | Valor |
|---|---|---|
| `PLOMADA_API_URL` | El API que consulta el navegador. Se inyecta en el `<head>` de cada página (`window.PLOMADA_API_URL`) y lo lee `static/api.js`. | `https://plumb-duy6.onrender.com` |
| `PYTHON_VERSION` | Render usa 3.11 por defecto en static sites; se fija para que no cambie bajo los pies. | `3.11` |
| `PLOMADA_OUT` | *(opcional)* Fuerza el directorio de datos locales. Sin ella, el build usa `out/` si existe y si no las fixtures. En Render no hace falta. | — |

Cambiar `PLOMADA_API_URL` **exige redesplegar**: el valor se hornea en el HTML
durante el build, no se lee en runtime.

---

## 5. Las reglas de reescritura (no son opcionales)

Este es el punto donde un despliegue se rompe en silencio.

Las fichas y los municipios **no son archivos**:
`/contrato/co1-pccntr-8462295/` no existe en disco. Se resuelve contra
`contrato/index.html`, que luego pide el contrato al API. Hay 12.678 URLs así
y 721 de municipios, todas en el `sitemap.xml`.

`render.yaml` ya las declara:

```yaml
routes:
  - type: rewrite
    source: /contrato/*
    destination: /contrato/index.html
  - type: rewrite
    source: /municipio/*
    destination: /municipio/index.html
```

Tiene que ser **`rewrite`**, no `redirect`: un redirect cambiaría la URL de la
barra y rompería el enlace que alguien compartió.

Si las configuras por la interfaz: **Settings → Redirects/Rewrites**, con
Action = *Rewrite*.

> El build también escribe `plomada/site/_redirects`, que es el formato de
> Netlify y Cloudflare Pages. Render lo ignora — usa `routes`. No pasa nada
> por que esté ahí; sirve si algún día se cambia de host.

---

## 6. Comprobar que quedó bien

En este orden. El paso 2 es el que detecta el error más común.

```bash
SITIO=https://plomada-sitio.onrender.com   # ajusta al dominio que te dé Render

# 1. La portada responde
curl -s -o /dev/null -w '%{http_code}\n' $SITIO/

# 2. LA PRUEBA CLAVE: una ficha por su URL real (no navegando)
curl -s -o /dev/null -w '%{http_code}\n' $SITIO/contrato/co1-pccntr-8462295/
#    200 -> las reescrituras funcionan
#    404 -> falta el paso §5

# 3. Un municipio
curl -s -o /dev/null -w '%{http_code}\n' $SITIO/municipio/antioquia-el-bagre/

# 4. El API quedó inyectado con el valor correcto
curl -s $SITIO/contrato/co1-pccntr-8462295/ | grep -o 'PLOMADA_API_URL=[^;]*'

# 5. El sitemap conserva las fichas
#    (grep -o, no grep -c: el sitemap va todo en una sola linea)
curl -s $SITIO/sitemap.xml | grep -o '/contrato/' | wc -l    # 12678
curl -s $SITIO/sitemap.xml | grep -o '/municipio/' | wc -l   # 721
```

Y en el navegador, con las DevTools abiertas:

- `/buscar/` → escribe "puente". Deben aparecer resultados en menos de 1 s y la
  URL debe quedar como `/buscar/?q=puente`. **No debe descargarse ningún JSON
  de más de 100 KB**: si ves `contratos.json` (8,5 MB), quedó código viejo.
- `/contrato/co1-pccntr-8462295/` → la ficha con sus señales y la evidencia.
- Pestaña de red: la ficha entera debe pesar menos de 50 KB.

---

## 7. Sobre los créditos: qué conviene pagar

Tienes créditos, así que la decisión importante no es el sitio sino el API.

**El sitio estático es gratis y no duerme.** Render sirve static sites desde su
CDN; no hay instancia que se suspenda. No necesita plan de pago.

**El API sí duerme en el plan gratuito.** Y aquí sí duele: `cf-cache-status:
DYNAMIC` — nada se cachea en el borde, así que **cada visita** pega al origen.
Si el servicio lleva ~15 min sin tráfico, el primer lector paga entre 30 y 60
segundos mirando "Despertando el servicio…". Con el sitio dinámico, eso ya no
afecta a una sección: afecta a la ficha, al buscador y al municipio.

Para saber si te está pasando (no lo pude medir por ti):

```bash
# deja el API 20 min sin tocarlo, luego:
curl -o /dev/null -s -w 'primera respuesta: %{time_total}s\n' \
  https://plumb-duy6.onrender.com/v1/meta
```

- Menos de ~2 s → está en un plan que no duerme; no gastes créditos ahí.
- Más de ~10 s → **sube `plumb-duy6` a un plan de instancia siempre activa.**
  Es el mejor uso de los créditos para este proyecto: mejora las tres vistas a
  la vez.

Latencias medidas con el servicio despierto, desde Bogotá, para que tengas
referencia de qué es normal: ficha 123 ms, búsqueda 724 ms, municipios 132 ms.

---

## 8. Despliegue continuo

Con el Blueprint, cada push a la rama configurada redespliega.

Ojo con una consecuencia del diseño: **el sitio no se actualiza solo cuando
cambian los datos**. Las cifras de portada, el tablero y el sitemap se hornean
en el build. Si el API recibe datos nuevos, hay que redesplegar para que la
portada los refleje — aunque las fichas y el buscador sí los muestren al
instante, porque consultan en vivo.

Si quieres que se refresque a diario, un Cron Job de Render que dispare el
Deploy Hook:

```
curl -X POST https://api.render.com/deploy/srv-XXXX?key=YYYY
```

(El Deploy Hook está en **Settings → Deploy Hook** del servicio.)

---

## 9. Cuando algo falla

| Síntoma | Causa | Arreglo |
|---|---|---|
| Las fichas dan **404**, la portada funciona | Faltan las reescrituras | §5 |
| Build falla: `site/ borrado: no se publica` | `test_privacy.py` encontró algo. Casi siempre: el API no respondió y la portada quedó sin datos | Mira el log, busca las líneas `✗`. Si son todas "sin dato", reintenta el build cuando el API responda |
| Todas las vistas dicen "No hay datos disponibles" | El API está caído o dormido | §7. El sitio está bien; el problema es el API |
| "Despertando el servicio…" en cada visita | El API duerme | §7, subirlo de plan |
| La portada muestra cifras viejas | Normal: se hornean en el build | Redesplegar (§8) |
| `ADMINISTRACIONES: sin dato` en la portada | Esperado. El API no expone `periodo_gobierno`, así que no se puede calcular | No es un error; se corrige el día que el API lo publique |

### Un aviso que no es un error

En el log del build verás:

```
[plomada/data.py] AVISO: no hay .../out ni $PLOMADA_OUT —
usando fixtures SINTETICAS. Esto NO son datos reales.
```

Es correcto en Render. `out/` está en `.gitignore` y ya casi nada del sitio
depende de él: lo que se publica sale del API. Las fixtures solo alimentan un
puñado de comprobaciones internas de `test_privacy.py`.

---

## 10. Antes de que el sitio sea público

Tres cosas pendientes que no dependen del despliegue, pero sí de si esto puede
publicarse tranquilo. Están en detalle en el plan
(`plomada-api-dinamico.md`, §4):

1. **El API devuelve documentos personales** (`doc_ordenador` es una cédula) en
   `/v1/contratos/{id}` y en el listado. `static/api.js::sanear()` impide que
   Plomada los pinte o exporte, pero **viajan igual hasta el navegador y se ven
   en las DevTools**. Ningún front puede arreglar eso: va en el serializador
   del API. `tests/test_api_privacidad.py` lo tiene documentado como `xfail`;
   el día que se cierre, ese test rompe el build para que se convierta en
   puerta real.
2. **El listado no devuelve `descripcion`**, así que el buscador pide el
   detalle de las 25 filas visibles para poder mostrar el objeto contractual.
   Funciona, pero son 25 llamadas por página que un campo evitaría.
3. **`alpha`/`beta` no están en `/v1/municipios`**, y la página de metodología
   promete publicarlos para que el cálculo sea reproducible.
