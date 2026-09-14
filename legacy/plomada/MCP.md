# Plomada conversacional: MCP + Claude en el tablero

Plan de implementación para que cualquier IA (Claude, y a futuro Gemini) pueda
responder preguntas sobre los datos de Plomada **conversando desde el
tablero**, en vez de solo mirando gráficos y tablas. Este documento es para
el equipo y para quien trabaje el front — no requiere leer el resto del
código para entender qué construir y en qué orden.

**Estado: servidor MCP (7 tools), proxy de chat (BYOK: cada usuario usa su
propia API key, no hay ninguna key del equipo en el servidor), API REST
pública (`/v1`, ver [`API.md`](API.md)) y carga a Postgres, todo construido y
verificado contra un Postgres real con los datos completos. La topología de
producción está declarada en [`render.yaml`](render.yaml): al aplicar el
Blueprint se crean el servicio web y Postgres, y solo queda cargar el
warehouse y probar `/chat` contra la URL pública asignada. Eso no puede
ejecutarse desde este repositorio sin acceso a la cuenta de Render, porque
Claude corre en la nube de Anthropic y no puede alcanzar `localhost`.** Ver
"Orden de trabajo" más abajo.

## Por qué esta arquitectura

La API de Claude (Messages API) tiene un **MCP connector** nativo: le pasas
la URL de un servidor MCP en la propia llamada y Claude decide cuándo llamar
sus tools — no hay que escribir el loop de tool-calling a mano. Eso hace que
la pieza que hay que construir sea, en esencia, un servidor MCP con tools de
solo lectura sobre los datos que ya existen, más un proxy delgado que
guarde la API key.

Tres decisiones de diseño para no sobreconstruir:

1. **Un solo servicio, no tres.** El esqueleto `api/` (FastAPI + Dockerfile)
   ya existe y está vacío — el proxy de chat y el servidor MCP viven ahí
   mismo, como dos rutas de la misma app. No hace falta un servicio nuevo en
   Render por cada pieza.
2. **Postgres como fuente, no archivos locales.** `data/exports/*.parquet` y
   `web/data/*.json` están en `.gitignore` y no viajan con la imagen de
   Docker que se despliega — un contenedor recién construido no los tiene.
   `pipeline/load_postgres.py` los carga a Postgres, y las tools del MCP
   leen de ahí. Esto ya cierra el ítem 5 de "Pendiente" del README.
3. **Solo lectura por construcción.** La conexión DuckDB que usan las tools
   es read-only. No hay superficie de escritura que asegurar.

## Arquitectura

```
┌─────────────┐        POST /chat         ┌───────────────────────────────┐
│  web/ (front)│ ────────────────────────▶ │  api/ (Render, servicio web)  │
│  chat widget │ ◀──────────────────────── │  ┌─────────────────────────┐  │
└─────────────┘   streaming (SSE)          │  │ proxy de chat            │  │
                                            │  │ POST /chat               │  │
                                            │  │ - guarda ANTHROPIC_API_KEY│ │
                                            │  │ - llama a Claude con     │  │
                                            │  │   mcp_servers + toolset  │  │
                                            │  └───────────┬─────────────┘  │
                                            │              │ Claude llama   │
                                            │              │ tools MCP      │
                                            │  ┌───────────▼─────────────┐  │
                                            │  │ servidor MCP  (/mcp)     │  │
                                            │  │ tools de solo lectura    │  │
                                            │  └───────────┬─────────────┘  │
                                            └──────────────┼────────────────┘
                                                            │ DATABASE_URL
                                                            │ (red interna Render,
                                                            │  puerto no expuesto)
                                            ┌───────────────▼────────────────┐
                                            │  Postgres (Render, otro servicio)│
                                            │  tablas: puntajes, titulares,    │
                                            │  meta -- cargadas por            │
                                            │  pipeline/load_postgres.py       │
                                            └───────────────────────────────┘
```

El front **nunca** habla directo con Claude ni con el servidor MCP — solo con
`POST /chat` en `api/`. Eso es lo único que el agente del front necesita
integrar.

El mismo servicio expone además la **API REST pública** en `/v1`
([`API.md`](API.md)), sobre las mismas tablas y con la misma capa de consulta:
quien prefiera consultar los datos él mismo en vez de preguntarle a un modelo
tiene por dónde, y las dos vías no pueden contradecirse.

## Piezas a construir

### 1. Servidor MCP — `api/app/mcp/server.py` (construido)

SDK oficial de Python (`mcp`, versión 2.x — **exige Python ≥3.10**; el
pipeline sigue fijado a 3.9, por eso `api/` tiene su propio entorno y sus
propias dependencias en `api/requirements.txt`, igual que ya hacía con
FastAPI/Postgres).

Tools implementadas hoy (cada una una consulta a Postgres acotada a
`LIMIT_DURO = 50` filas, para no volcar tablas completas al contexto del
modelo). Leen de Postgres vía `DATABASE_URL` — **no** de archivos locales:

| Tool | Qué responde |
|---|---|
| `resumen_indicios` | Cifras titulares, plata por indicio, cobertura y limitaciones |
| `glosario_banderas` | Las 26 banderas con su peso y su glosa, para explicarlas en palabras |
| `buscar_contratos_atipicos(entidad?, departamento?, tipo_contrato?, valor_minimo?, bandera?, limite=20)` | Lista de contratos marcados, con sus banderas |
| `detalle_contrato(id_contrato)` | Ficha completa con la **evidencia numérica** de cada bandera |
| `perfil_entidad(nombre_o_nit)` | Entidad: contratos, valor, atípicos, banderas frecuentes, top proveedores |
| `buscar_proveedor(nombre_o_documento)` | Proveedor y su red: contrapartes por llave compartida |
| `alertas_preadjudicacion(departamento?, entidad?, limite=20)` | Licitaciones abiertas con banderas |

**Este archivo ya no tiene SQL propio.** Todas las tools llaman a
`api/app/consultas.py`, la misma capa que usa la API REST (`/v1`, documentada
en [`API.md`](API.md)) sobre las tablas `api_*` que publica
`sql/90_serving.sql` y carga `pipeline/load_postgres.py` (`make load`).
Antes cada frente tenía sus propias consultas y su propia copia del umbral de
«atípico» — dos definiciones de la misma cifra, que es exactamente el bug que
este proyecto se pasa el README evitando. Ahora el REST y el MCP no pueden dar
respuestas distintas a la misma pregunta.

La única diferencia entre los dos frentes es el techo de filas: 200 en REST,
**50 en MCP**. Una respuesta de 200 filas es normal para un cliente HTTP y no
lo es para el contexto de un modelo.

Agregar una tool nueva es una función `@mcp.tool()` que llama a una función de
`consultas.py`. Las dos que quedaban pendientes en la versión anterior de este
documento (`buscar_proveedor` y `alertas_preadjudicacion`) ya están: con la
capa compartida salieron casi gratis.

Correr en local (necesita un Postgres — `docker compose up db` levanta el
que ya está definido en `docker-compose.yml`):
```
python pipeline/build.py --all                                # incluye el paso 90 (tablas api_*)
docker compose up -d db                                       # postgres:16-alpine en :5432
export DATABASE_URL=postgresql://plomada:plomada@localhost:5432/plomada
python pipeline/load_postgres.py                              # carga las tablas api_*

python -m venv .venv-mcp
.venv-mcp/Scripts/pip install -r api/requirements.txt
.venv-mcp/Scripts/python api/app/mcp/humo_mcp.py           # via stdio
cd api && ../.venv-mcp/Scripts/python -m app.mcp.server --http &   # http, puerto 8765
.venv-mcp/Scripts/python api/app/mcp/humo_mcp.py --http
```

**Sin `DATABASE_URL`, las tools fallan con un error de tool claro (no tumban
el servidor)** — probado: cada tool valida esto con una excepción normal, no
`sys.exit()`, precisamente porque este es un servidor de larga duración y no
un script de una sola corrida.

### 2. Proxy de chat — `api/app/main.py` (construido)

- `POST /chat`, recibe `{mensaje, historial?}`, responde streaming (SSE).
- Llama a la Messages API de Claude con:
  ```python
  client.beta.messages.stream(
      model="claude-opus-5", max_tokens=4096,
      betas=["mcp-client-2025-11-20"],
      mcp_servers=[{"type": "url", "url": MCP_SERVER_URL, "name": "plomada"}],
      tools=[{"type": "mcp_toolset", "mcp_server_name": "plomada"}],
      messages=messages,
  )
  ```
  Las dos partes (`mcp_servers` + `tools` con `mcp_toolset`) son obligatorias
  — mandar una sin la otra lo rechaza la API.
- **BYOK (bring your own key), no una key del equipo.** No existe
  `ANTHROPIC_API_KEY` en el servidor. Cada request manda la key del usuario
  en el header `X-Anthropic-Api-Key`; el servicio la usa para construir un
  cliente de Anthropic nuevo en esa sola llamada y la descarta — nunca la
  guarda, nunca la loguea. Investigué esto antes de construirlo: Anthropic
  **no** ofrece un "Sign in with Claude" público para que un tercero deje a
  sus usuarios loguearse con su cuenta de Claude.ai — la única forma real de
  que cada usuario pague lo suyo es que provea su propia API key.
  - Sin el header: `422` inmediato de FastAPI (probado).
  - Header con una key inválida: evento SSE `{"error": "Tu API key de
    Anthropic no es valida"}` (probado con una key falsa real).
- Otros errores (rate limit, MCP inalcanzable) también se devuelven como
  evento SSE `{"error": "..."}` en vez de tumbar la conexión — el front debe
  leer ese caso y mostrar el mensaje.

**Detalle técnico importante para quien lo toque:** `/mcp` y `/chat` viven en
el **mismo proceso FastAPI** (necesario en Render, que solo expone un puerto
por servicio) montando el sub-app del servidor MCP (`mcp.streamable_http_app()`)
dentro de la app de FastAPI. Eso por sí solo **no alcanza**: Starlette no
propaga el lifespan de un sub-app montado automáticamente, así que el
"session manager" del MCP nunca arranca y toda request a `/mcp` revienta con
`RuntimeError: Task group is not initialized`. Se resuelve combinando los
lifespans a mano con `AsyncExitStack` (ver `api/app/main.py`, función
`lifespan`) — verificado con una prueba real antes de dejarlo así, no es
una suposición.

Esto de paso le da un uso real al esqueleto `api/` que llevaba vacío desde
antes (ver ítem 5 de "Pendiente" en el README).

### 3. Postgres en Render

Desplegar `postgres:16-alpine` (la misma imagen que ya usa
`docker-compose.yml`) como **su propio servicio** en Render, separado del
servicio `api/`:

- **Disco persistente obligatorio.** A diferencia de `api/` (sin estado —
  puede perder su filesystem en cada redeploy sin problema), Postgres
  necesita un Disk de Render adjunto o pierde los datos en cada reinicio del
  contenedor.
- **No exponer el puerto de Postgres a internet.** Los *datos* son públicos
  (SECOP II, ya están en el tablero), pero la base en sí solo necesita ser
  alcanzable por el servicio `api/` — conéctense por la red interna de
  Render, no publiquen el puerto 5432 al público.
- `DATABASE_URL` (formato `postgresql://usuario:clave@host:puerto/db`) va
  como variable de entorno en **dos lugares**: en el servicio `api/` (lectura,
  las tools del MCP) y en donde se corra `pipeline/load_postgres.py`
  (escritura — puede ser a mano desde una laptop apuntando al host público
  de Render mientras no haya CI para esto, o un job aparte más adelante).
  Puede ser el mismo valor en ambos si usan un solo usuario, o separar
  lectura/escritura con dos usuarios de Postgres si quieren ser más
  estrictos — no es necesario para arrancar.
- `any_value()` (usado en la tool `perfil_entidad`) requiere **Postgres ≥16**
  — no bajen la versión de la imagen sin ajustar esa query.

### 4. La cara en el sitio — **construida** (2026-08-23)

> **Esta sección quedó vieja y ya se ejecutó.** Decía «para quien trabaje
> `web/` (o el proyecto Vercel nuevo)» y planteaba un *widget* flotante. Dos
> correcciones, según `docs/PLAN_TEMA_API_MCP.md` §3 y F4:
>
> - **El front del proyecto es `plomada/`.** `web/index.html` es el tablero
>   anterior y no se toca.
> - **No es un widget: son dos vistas del sitio, con URL propia y en el
>   sitemap.** `/api/` documenta el API y el servidor MCP (con la URL
>   `{API_URL}/mcp/`, **barra final incluida**, y las 7 tools), y
>   `/asistente/` es el chat. Un asistente que solo existe como burbuja no se
>   puede enlazar ni compartir, que es justo la tesis del sitio.
>
> Dónde vive: `pagina_api()` y `pagina_asistente()` en `plomada/build.py`, el
> texto en `plomada/contenido.py`, el cliente en `plomada/static/chat.js` y
> los estilos en `design/plomada/sitio.css`.

El contrato de abajo es el que `static/chat.js` implementa, y sigue vigente:

- **Endpoint:** `POST {API_URL}/chat`
- **Header obligatorio:** `X-Anthropic-Api-Key: <key del usuario>`.
- **Body:** `{ "mensaje": "...", "historial": [...] }`.
- **Respuesta:** streaming de texto (SSE) — el widget debe leer un stream,
  no esperar un JSON completo. Cada línea es `data: {"delta": "..."}` hasta
  un `data: {"done": true}` final, o `data: {"error": "..."}` si algo falló.
- **La key del usuario:**
  - Pedirla una vez (input tipo password, con un link a
    console.anthropic.com/settings/keys explicando de dónde sacarla) y
    guardarla en `localStorage` — nunca en una cookie ni en el servidor.
  - Mandarla en el header de cada `/chat`. Si el servidor responde `422`
    (falta el header) o un evento `{"error": "Tu API key de Anthropic no es
    valida"}`, hay que volver a pedirla — no reintentar en silencio.
  - Plomada no gestiona billing de nadie: cada usuario ve su propio consumo
    en su cuenta de Anthropic.
- `API_URL` sale de una variable de entorno/config, para que el mismo front
  sirva en local y en producción sin cambiar código.
- Si el backend no responde (network error, no un error de key), degradar
  con un mensaje tipo "el asistente no está disponible ahora" — mismo patrón
  que ya usa el tablero con `alertas.json` cuando nadie corrió
  `pipeline/alertas.py` (ver `web/index.html`, función `drawAlertas`).
- Cold start: Render duerme el servicio, así que si no llega el primer
  `delta` a los ~3 s hay que avisar que está despertando. `chat.js` reusa el
  umbral de `static/api.js` (`AVISO_DESPERTANDO`).
- **Techos del servicio** (BYOK cuida la plata del lector; esto cuida el
  servicio, ver `api/app/config.py`):
  - Por IP: `chat_max_por_ip` peticiones por `chat_ventana_seg` segundos
    (6/60 s por defecto). Al excederlo el servidor responde **HTTP 429**
    con el sobre de error (`codigo: "limite_alcanzado"`); `chat.js` devuelve
    la pregunta al cuadro de texto y pide esperar un minuto.
  - Streams concurrentes: `chat_max_concurrentes` (8 por defecto) en todo el
    servicio. Con el cupo lleno llega un evento SSE
    `{"error": "Hay muchas conversaciones abiertas..."}` — sin haber creado
    cliente de Anthropic ni gastado la key de nadie.

## Orden de trabajo — qué ya está hecho

1. ✅ Servidor MCP corriendo local, probado con un cliente MCP real
   (`api/app/mcp/humo_mcp.py`) por **stdio y por HTTP**, contra datos
   reales del warehouse.
2. ✅ `/chat` construido en `api/app/main.py`, con `/mcp` montado en el mismo
   proceso (verificado: arranca, `/health` responde, `/mcp` responde).
3. ✅ **Confirmado el límite que ya preveíamos:** al probar `/chat` de
   verdad (con una API key real, pidiéndole a Claude una pregunta), la
   respuesta de Anthropic fue exactamente:
   > `"Connection error while communicating with MCP server. The server may
   > be unavailable or unresponsive."`

   porque `MCP_SERVER_URL` apuntaba a `http://127.0.0.1:8000/mcp` — Claude
   corre en la nube de Anthropic y no puede alcanzar `localhost`. Esto no es
   un bug: es exactamente la limitación que ya estaba documentada antes de
   escribir código. **Sin excepción, no hay forma de probar el flujo
   completo sin una URL pública** (ni siquiera ejecutando todo en la misma
   máquina).

4. ✅ `pipeline/load_postgres.py` construido, y `api/app/mcp/server.py`
   reescrito para leer de Postgres (`psycopg`) en vez de archivos locales.
   Sin Postgres disponible en este entorno no pude correr el flujo real
   contra una base viva — verificado que el servidor arranca, responde
   `initialize`/`list_tools`, y que sin `DATABASE_URL` cada tool falla con un
   error normal (no tumba el proceso). La prueba con datos reales de Postgres
   queda a cargo del equipo (ver comandos en la sección 1 de arriba).

5. ✅ **Verificado contra un Postgres real con los datos completos**
   (77.864 contratos): `sql/90_serving.sql` publica las tablas `api_*`,
   `pipeline/load_postgres.py` carga las 18 con sus índices, y las 7 tools
   pasan el smoke test por **stdio y por HTTP montado en la app FastAPI**.
   La API REST responde en `/v1` sobre esa misma base. Lo único que sigue sin
   poder probarse en local es el round-trip completo de `/chat`, por el motivo
   del punto 3.

## Puesta en producción — requiere acceso a Render

6. **Aplicar el Blueprint**: crear los servicios definidos en `render.yaml`.
7. **Cargar el warehouse**: desde un entorno que tenga los datos generados,
   ejecutar `python pipeline/load_postgres.py` usando el `DATABASE_URL` de la
   base de Render. El contenedor de la API arranca sin datos y devuelve 503
   deliberadamente hasta que este paso termina.
8. **Configurar `SELF_URL`** con la URL pública del servicio web y, si aplica,
   `CORS_ORIGINS` con el origen del front. Render expone `PORT` por defecto.
   **`ANTHROPIC_API_KEY` NO va aquí, es BYOK** (ver sección 2).
9. Probar el round-trip de `/chat` con una key propia de Anthropic y conectar
   el widget del front apuntando a esa URL, con el
   input para pedir la key del usuario (ver sección 4).

## Decisiones que faltan por tomar en equipo

- **Historial de conversación:** ¿vive solo en el navegador (se manda
  completo en cada request) o se guarda sesión en el servidor? Empezar por
  lo simple (solo navegador) hasta que el volumen de contexto lo justifique.
- **Rate limiting / abuso de `/chat`:** con BYOK cada usuario paga lo suyo,
  así que ya no es un riesgo de costo para el equipo, pero sigue siendo un
  riesgo de abuso del servidor (alguien podría usar `/chat` como proxy
  gratis hacia Claude con SU propia key, sin que le sirva de mucho, pero
  igual consume recursos del servicio). No urgente para un demo de hackathon.
- **Gemini queda fuera de este plan v1.** El connector directo de MCP en la
  API de Claude no tiene un equivalente igual de simple documentado para
  Gemini; si se quiere soportar Gemini más adelante, el proxy tendría que
  correr su propio loop de tool-calling contra el mismo servidor MCP en vez
  de delegárselo a la API como con Claude.
