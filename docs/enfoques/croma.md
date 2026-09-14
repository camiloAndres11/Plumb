# Croma como fuente de datos de Pliego

Fecha del análisis: 2026-09-13. Fuentes: `https://usecroma.com/llms.txt`,
`https://docs.usecroma.com/guides/colombia/secop.md`, `/datasets.md`,
`/rate-limits.md`, `https://usecroma.com/es/pricing.md`, `https://usecroma.com/auth.md`.

## Qué es

Infraestructura de datos públicos para LatAm (CO, PE, MX, US, BR): ~150 endpoints
REST (`https://api.croma.run`) y un servidor MCP (`/mcp`). **SECOP I y II completos
como dataset propio**: no llaman a datos.gov.co en cada consulta, responden desde su
copia en milisegundos con `as_of` en cada respuesta.

**No es competidor de Pliego: es proveedor.** Vende acceso a datos crudos a equipos
técnicos; Pliego vende decisiones a constructoras. Lo único que se solapa es la
API/MCP de Plomada en producción, y esa capa Croma la hace mejor y más barata.

## Precios

| | Free | Hobby | Standard | Contrato |
|---|---|---|---|---|
| USD / mes | 0 | 20 | 99 | a medida |
| créditos / mes | 5.000 | 20.000 | 100.000 | — |

- Consulta a **dataset = 1 crédito** (todo SECOP, gacetas, normativa, jurisprudencia).
- Consulta **en vivo = 10 créditos** (RUES, antecedentes, Rama Judicial, RUNT, Supersociedades).
- Sin sobrecostos: agotados los créditos responde `402`. Los lotes cobran por elemento.
  Una respuesta de caché cuesta lo mismo que una nueva. Una que falla no cuesta.
- Cada respuesta trae `X-RateLimit-Remaining` y `X-RateLimit-Reset`.

Para Pliego: 100.000 consultas SECOP al mes por USD 99. Una constructora activa gasta
del orden de cientos al mes; el costo de datos es despreciable frente a lo que se le
cobra a cada cliente.

## Autenticación

Llave de organización (`croma_live_...`) creada por una persona en
`https://platform.usecroma.com` (sección API keys; se muestra una sola vez). Va como
`Authorization: Bearer <llave>` en cada request. No hay registro automático para
agentes: alguien del equipo tiene que crear la cuenta y la llave.

## Medido con llave real (2026-09-13)

Sonda `python -m pliego.comun.croma` más unas consultas a mano (9 créditos):

- **Latencia**: las búsquedas SECOP a dataset tardan **1,5–30 s por página**, no
  milisegundos; la primera de cada tipo es la lenta. Una llamada abandonada por
  timeout se cobra igual si el servidor la termina. Por eso `fuente.py` cachea cada
  búsqueda en `data/cache/croma/` (24 h) y descarga 4 en paralelo.
- **Frescura**: `as_of` de SECOP = el mismo día a las 10:11 UTC → refresco diario.
- **Volumen** (Santander, SECOP II, Obra): 472 procesos adjudicados desde 2025-01,
  341 sin adjudicar desde 2026-06, 1.881 contratos en total. Con el perfil de la
  demo (3 departamentos) el arranque en frío son ~60–100 páginas = créditos.
- **Cuota**: `/catalog` anuncia "100 requests / 24h" por endpoint, pero la respuesta
  real solo trae `ratelimit-policy: "credits";q=5000;w=2592000`. La cabecera manda
  (lo dice su propia doc). Ojo si en producción aparece la diaria.
- **Campos**: el contrato no trae `process_id` ni conteos de oferentes; el enlace es
  el `noticeUID` de su `url`. Trae `provider_is_group`, `provider_is_sme`,
  `legal_rep_name`, `supervisor_document`, desglose de fuentes de financiación
  (`funding_royalties`, `funding_own_territorial`…), `pending_execution_value`. El
  proceso SECOP II trae `notice_uid`, `bid_deadline`, `invited_providers`,
  `interested_providers`, `unique_responding_providers`, `provider_document` del
  adjudicatario, `phase` y `status`. SECOP I trae UNSPSC de 6 dígitos y sin
  conteos.

## Mapa: qué endpoint alimenta cada enfoque

Contraste entre las columnas de los parquet que hoy consume cada módulo
(`pliego/*/fixtures/`) y los campos que Croma devuelve.

| Enfoque | Fixture que consume hoy | Endpoint Croma | Cobertura |
|---|---|---|---|
| **Filtro** | `procesos_abiertos` (precio_base, n_invitados, n_manifestaron, n_respuestas, fecha_cierre, unspsc, modalidad, depto) | `processes-search` con `department`, `unspsc_code`, `modality`, `contract_type`, `from_date`, `min/max_value`, `awarded: no`. Devuelve `invited_providers`, `interested_providers`, `unique_responding_providers`, `bid_deadline`, `base_price` | Completa. Las banderas (`f_*`) se siguen calculando aquí |
| | `entidades_historial`, `entidad_familia` (share_top1, tasa_proponente_unico, mediana_oferentes) | `contracts-search` por `entity_nit` + `awards-search` + `bidders-search` → se agrega localmente | Completa pero derivada: Croma da las filas, el agregado es IP de Pliego |
| **Radar** | `contratos` (doc_proveedor, valor_adjudicado, ratio, n_oferentes_unicos, es_grupo, valor_pagado, valor_pend_ejecucion) | `contracts-search` por `provider_document` / `department` / `unspsc_code`; `profile` por documento (contratista y entidad a la vez); `bidders-search` (quién se presentó a qué, con puntaje en SECOP I) | Completa y mejor: `is_group`, `is_sme`, `legal_rep_document`, `paid_value`, `pending_execution_value` vienen listos. `bidders-search` dice a quién se le pierde, no solo quién gana |
| | — | `sanctions-by-provider`, `modifications-search` (adiciones y prórrogas), `supersociedades/financial-statements`, `rues/entity-by-nit` | Nuevo: perfil financiero y de riesgo del competidor sin construir nada |
| **Simulador** | `historico` (precio_base, valor_adjudicado, ratio, n_oferentes_unicos, fecha_cierre_ofertas) | `processes-search` con `awarded: yes` (trae `base_price`, `awarded_value`, `unique_responding_providers`, `bid_deadline`, `award_date` en un solo registro) | Completa. El ratio y la distribución por número de oferentes se calculan aquí; el backtest sigue siendo de Pliego |
| **Checklist** | `pliego_*.pdf` + `requisitos_*.json` (parseo del pliego) | Ninguno para el núcleo: Croma **no entrega documentos del proceso** ("Documentos Tipo, Cuestionario, document downloads… not part of these responses"). Sí cubre la *verificación*: `procuraduria/disciplinary-records`, `contraloria/fiscal-records`, `policia/criminal-records`, `contaduria/state-delinquent-debtors`, `rues` | No cubre el parseo (que es lo defendible). Cubre el "está inhabilitado / en mora" de cada ítem, en vivo |
| **Generador** | `pliego_*.json` + `perfil_constructora.json` | Tampoco (necesita el pliego). Insumos: `profile` del cliente (su experiencia SECOP para el capítulo de experiencia), `ancp-cce/conceptos-search` (conceptos de Colombia Compra Eficiente para citar) | Parcial |
| **Nuevo posible** | — | `plans-search` (Plan Anual de Adquisiciones por año y entidad) | Ver qué va a licitar una entidad antes de que salga el proceso |

## Lectura

1. Tres de cinco enfoques (filtro, radar, simulador) corren enteros sobre Croma, todo
   dataset, 1 crédito por llamada. El ingestor propio de SECOP y los parquet pasan a
   ser respaldo.
2. Los dos que no cubre (checklist, generador) dependen del pliego PDF, y ese parseo es
   de Pliego. Croma lo excluye explícitamente. Es la parte más defendible del producto.
3. Lo que Croma agrega y no había: antecedentes en vivo (checklist), estados financieros
   y RUES (radar), modificaciones de contratos (sobrecostos), PAA (enfoque nuevo).
4. Riesgos: (a) el `as_of` real de SECOP en Croma — el filtro vive de procesos que
   cierran en días; (b) `modality`, `status`, `department` se filtran "exactamente como
   SECOP los escribe", así que la normalización actual sigue haciendo falta;
   (c) dependencia de un proveedor pequeño: el ingestor propio queda como plan B.

## Plan de integración

### Principio

Los tres `datos.py` no leen SECOP: leen parquet que `semilla.py` genera con SQL sobre
dos tablas del warehouse, `base` (contratos de construcción) y `alertas` (procesos
abiertos con banderas). Si Croma alimenta esas dos tablas en un DuckDB en memoria,
**las mismas SQL de las semillas producen las mismas filas** y ni `logica.py` ni
`app.py` cambian.

```
                 ┌──────────────┐  parquet   ┌──────────┐
  fixtures  ───► │              │ ─────────► │          │
                 │ comun/fuente │            │ datos.py │ ──► logica ──► app
  Croma API ───► │  (DuckDB en  │  semilla   │ (igual)  │
   base+alertas  │   memoria)   │  SQL       │          │
                 └──────────────┘            └──────────┘
```

### Fases

| Fase | Entrega | Estado |
|---|---|---|
| 1 | `pliego/comun/croma.py`: cliente HTTP (bearer, reintentos por 429 con `Retry-After`, `402` → `SinCreditos`, `401` → `ClaveInvalida`, paginación de búsquedas dataset). Sonda `python -m pliego.comun.croma` que gasta 4 créditos y muestra los campos reales | hecha |
| 1 | `pliego/comun/mapeo_croma.py`: registro Croma → fila con el esquema de `base` / `alertas` (normalización a MAYÚSCULAS sin tildes como `sql/01_stage.sql`, `notice_uid` por regex, `familia`, `ratio`) | hecha |
| 1 | `pliego/comun/fuente.py`: conmutador `PLIEGO_FUENTE=croma` + `CROMA_API_KEY`; sin ellos, parquet como hasta hoy. Con Croma: trae contratos y procesos para los departamentos y tipos del perfil, arma `base` y `alertas` en memoria y corre las SQL de las semillas | hecha |
| 1 | `datos.py` de filtro, radar y simulador leen por `fuente.filas(...)`; `hoy()` es la fecha real con Croma y la del snapshot con fixtures | hecha |
| 1 | Pruebas con transporte falso (sin red ni llave) | hecha |
| 2 | Llave creada, sonda corrida, campos confirmados (ver "Medido con llave real"); caché en disco y descargas en paralelo por la latencia | hecha |
| 2 | Medir el `as_of` de SECOP durante una semana antes de escoger plan | pendiente |
| 3 | Radar: `profile`, `sanctions-by-provider`, `modifications-search`, `supersociedades` en la ficha del competidor | pendiente |
| 3 | Checklist: verificación en vivo de inhabilidades (Procuraduría, Contraloría, BDME) por ítem | pendiente |
| 4 | Enfoque nuevo sobre `plans-search` (PAA) | idea |

### Variables de entorno

| Variable | Efecto |
|---|---|
| `PLIEGO_FUENTE` | `croma` para leer de Croma; cualquier otra cosa (o ausente) usa los fixtures |
| `CROMA_API_KEY` | llave de organización `croma_live_...` |
| `CROMA_API_URL` | base de la API; por defecto `https://api.croma.run` |
| `CROMA_MAX_PAGINAS` | tope de páginas (de 100) por búsqueda; por defecto 30 |
| `CROMA_DESDE_ANIO` | primer año del histórico a traer; por defecto hace 4 años |
| `CROMA_CACHE_HORAS` | vigencia de la caché en disco por búsqueda; por defecto 24, `0` la desactiva |
| `CROMA_HILOS` | búsquedas en paralelo; por defecto 4 |

### Presupuesto de créditos

Con el perfil de la demo (3 departamentos × 3 tipos de contrato, 4 años) el arranque
en frío son del orden de 100–300 consultas a dataset = 100–300 créditos. El plan Free
(5.000) alcanza para desarrollar y para la demo; Standard para clientes.

### Banderas del filtro con Croma

| Bandera | Con fixtures | Con Croma |
|---|---|---|
| `f_ventana_corta` | p10 de días de ventana por modalidad, sobre todo el warehouse | igual, sobre los procesos adjudicados traídos |
| `f_historial_proponente_unico` | tasa ≥ 0,80 con n ≥ 5 por entidad | igual, sobre `base` en memoria |
| `f_sin_interes_a_tiempo` | invitados ≥ 5, 0 manifestaron, cierra en ≤ 7 días | igual |
| `f_al_tope_minima` | p99 del valor de mínima cuantía por entidad y año | `NULL`: no hay suficiente histórico de mínima cuantía en lo traído |
| `f_cierre_movido` | compara con el snapshot de ayer | `NULL`: no hay snapshot anterior (fase 2: guardar `bid_deadline` entre corridas) |
