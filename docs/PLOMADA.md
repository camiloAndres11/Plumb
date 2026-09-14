# Plomada (origen del proyecto, Platanus Hack 26)

> Este es el README original del proyecto. Sigue siendo la referencia metodológica del pipeline, las banderas y la API de Plomada. El README actual de la raíz describe el repo tal como está hoy: Pliego y la plataforma para empresas.

<img src="../project-logo.png" alt="Plomada" width="200" />

**Platanus Hack 26: Bogotá · Track 🔑 Access · team-15**

> La plomada es el instrumento que revela lo que está torcido.

Detección de riesgo de irregularidad en la **contratación de obra pública** de
Colombia, a partir de datos 100% públicos del SECOP II.

**Riesgo no es fraude.** Este proyecto produce indicios para priorizar
investigación periodística y control social. Ninguna cifra de aquí prueba un
delito, y el proyecto no afirma que lo pruebe.

---

## Qué lo diferencia de un buscador de contratos

Las herramientas existentes (BuscaSECOP y similares) son **buscadores de filas**:
filtras por entidad, objeto, cuantía y modalidad. Plomada trata los contratos
como **aristas de una red de personas** y se enfoca en un solo sector —
construcción — porque es el único donde puedes verificar físicamente si la obra
existe.

Y lo publica por una **API REST abierta** ([`API.md`](../API.md)), no solo como un
tablero: los mismos indicios se pueden filtrar, bajar en CSV o consultar desde otra
herramienta, con la evidencia numérica de cada bandera al lado.

Los campos que habilitan esto están en el dataset oficial y casi nadie los usa:

| Campo del SECOP II | Para qué sirve |
|---|---|
| `n_mero_de_documento_ordenador_del_gasto` | Cédula del funcionario que autorizó el gasto. Se lo puede seguir cuando cambia de entidad. |
| `n_mero_de_documento_supervisor` | Quién vigila la obra. |
| `identificaci_n_representante_legal` | Empresas que comparten representante legal. |
| `n_mero_de_cuenta` | Proveedores distintos cobrando a la misma cuenta. **Nunca se publica**: se usa como llave hasheada. |
| `direcci_n_de_ejecuci_n_del_contrato` | Geocodificable → verificación satelital de la obra. |
| `sistema_general_de_regal_as` y afines | Atribuir el riesgo a la fuente de la plata. |

## Universo

De los **5.975.627** contratos del SECOP II, 5.123.891 son prestación de
servicios. El universo de obra pública son **77.864** contratos, **$209
billones**:

| Tipo | Contratos |
|---|---|
| Obra | 52.355 |
| Interventoría | 13.074 |
| Consultoría | 11.482 |
| Asociación Público Privada | 715 |
| Concesión | 238 |

Interventoría y consultoría se incluyen **a propósito**: que el que vigila la
obra pertenezca a la misma red que el que la construye es el mecanismo central
del fraude en obra pública, y solo se ve si tienes los dos lados.

## Cómo correrlo

```bash
pip install -r requirements-dev.txt

python pipeline/ingest.py                            # ~4 min, reanudable
python pipeline/build.py                             # ~20 s, warehouse + base.parquet
python pipeline/build.py --steps 04 05 --no-export   # grafo: nodos y aristas
python pipeline/grafo.py                             # comunidades
python pipeline/build.py --steps 06 --no-export      # banderas de red
python pipeline/build.py --all                       # resto de pasos, incl. 90 (API)
python pipeline/report.py                            # rankings + CSVs en out/
python -m pytest tests/                              # puertas de calidad
```

Con Docker (fija Python 3.11 para todo el equipo): `docker compose up`.
El entorno local de Windows no tiene `make`; las recetas del `Makefile` son
one-liners a propósito, se pueden copiar tal cual.

## Decisiones metodológicas (verificadas contra los datos, no supuestas)

Estas son las trampas en las que cae cualquier port ingenuo de las "banderas
rojas" de la literatura al caso colombiano. Todas se descubrieron midiendo.

**1. La API oficial no sirve para analizar.** Las agregaciones (`$group`) sobre
los 6M de contratos se caen por timeout. Una página cruda de 10.000 filas baja
en ~30 s sin problema. Por eso se traen las filas a disco y toda la analítica
corre en local con DuckDB.

**2. Las llaves nativas contrato↔proceso no cruzan.** El dataset de contratos
usa el namespace `CO1.BDOS.*` y el de procesos `CO1.REQ.*`; el match exacto da
**cero**. El único puente común es el `noticeUID=CO1.NTC.*` que va dentro de la
URL pública de ambos. Con eso el join sube a **99,6%** de cobertura, y es lo que
habilita las banderas de competencia.

**3. El dataset de procesos trae varias filas por proceso** (una por lote y por
adjudicación). Unir directo duplica contratos y contamina todos los conteos. Se
colapsa a una fila por proceso *antes* de unir.

**4. 24 contratos traen valores imposibles** (hasta 6×10¹⁸ COP, más que el PIB
mundial) y entre ellos concentraban el **98,6% del "total"** agregado. No se
borran: se aíslan, se cuentan como falla de publicación (`f_valor_implausible`)
y se excluyen de toda suma de dinero.

**5. Buscar anticipos por encima del 50% legal es inútil.** El máximo observado
en los 1.590 contratos con anticipo es exactamente **0,500**: la plataforma
impone el tope. Esa bandera clásica no puede dispararse nunca. Lo que sí informa
es quién **agota** el tope (589 contratos), y los 271 que declaran *no* tener
anticipo pero registran plata girada.

**6. "Pagado mucho con ejecución pendiente" es imposible por construcción.**
`valor_pagado + valor_pend_ejecucion = valor` se cumple en 72.110 de 76.576
contratos (94%): es una identidad contable, no una señal. Se reemplazó por las
**violaciones** de esa identidad, que sí son anomalías (9 sobrepagos).

**7. No toda cuenta bancaria compartida es un indicio.** Se clasifica el tipo de
red antes de usarla:
   - *comunitaria* (4 grupos): el municipio canaliza pagos a varias Juntas de
     Acción Comunal por una misma cuenta. Ruido administrativo. **Se excluye.**
   - *consorcios* (63 grupos): la cuenta del consorcio suele estar a nombre del
     líder. Esperable; se marca aparte con menor fuerza probatoria.
   - *empresas independientes* (30 grupos): **este es el indicio real.**

   Sin esta separación, la bandera reportaría 651 contratos; con ella, 239.

**8. Cuando el Estado le contrata al Estado, la directa es legal.** Los
convenios interadministrativos (ANI→INVIAS, empresas industriales y comerciales
del Estado, ESEs) usan contratación directa por vía legal. Filtrando los 783
proveedores que son entidades públicas, `f_obra_directa` baja de 12.154 a
**8.944**: el **26% eran falsos positivos**.

**9. Los municipios chicos no pueden encabezar el ranking por azar.** Un
municipio con 4 contratos y 2 marcados da 50% y gana la lista sin significar
nada. Se corrige con **encogimiento bayesiano empírico** (beta-binomial por
momentos): las tasas con poca evidencia se jalan hacia la media nacional y solo
se separan cuando hay volumen que lo sostenga. Se reportan la tasa cruda y la
ajustada, siempre las dos.

## Las banderas

20 indicadores en 6 grupos, con pesos explícitos y discutibles (3 = indicio
fuerte, 1 = contexto). El glosario completo y sus pesos están en
`out/banderas_glosario.csv` y en `sql/03_ranking.sql`. Cada contrato marcado
lleva las columnas `ev_*` con la evidencia numérica que disparó cada bandera:
sin evidencia no se publica.

Un contrato cuenta como **atípico** si enciende al menos una bandera fuerte o
acumula 6 puntos. Umbral explícito, no escondido en un modelo.

## Limitaciones que hay que decir en voz alta

- **Solo SECOP II.** SECOP I (pre-2015 y entidades rezagadas) no está incluido.
- **La cédula del ordenador del gasto está en el 64,5%** de los contratos y la
  del supervisor en el 54,3%. El análisis de red cubre esa fracción, no el total.
- **La cuenta bancaria está en el 23,7%.** Las redes detectadas son un piso, no
  un censo.
- **No hay datos de oferentes perdedores** en los datos abiertos, solo el número
  de ofertas y el ganador. Eso limita la detección de colusión a indicios
  indirectos: no se puede ver quién compitió contra quién.
- **Falta normalizar por población** (DANE) para el ranking municipal.
- **Falta la línea de precios unitarios**, que es lo que convertiría el riesgo en
  una cifra de sobrecosto en pesos.

## Grafo de personas (Pilar 1)

Los contratos no son filas: son aristas de una red de personas. El grafo es
pequeño — **6.361 proveedores conectados, 13.254 pares únicos** — así que corre
con `networkx` en memoria. Nada de Neo4j.

```
python pipeline/build.py --steps 04 05 --no-export   # nodos y aristas
python pipeline/grafo.py                              # comunidades
python pipeline/build.py --steps 06 --no-export       # banderas de red
```

| Nodo | Cantidad |
|---|---|
| Proveedores | 28.811 |
| Personas (cédulas) | 20.081 |
| Entidades | 2.530 |

**Una cédula es un nodo, no tres.** La misma persona puede ser ordenador del gasto
en una entidad y supervisor en otra: hay **1.723 personas multi-rol**, y un modelo
de un nodo por rol las habría perdido.

Aristas proveedor–proveedor por llaves que deberían ser únicas: **9.793** por
domicilio, **5.497** por representante legal, **219** por cuenta bancaria. De los
13.254 pares únicos, **9 están unidos por las tres llaves a la vez** y 2.237 por
dos — esos son los indicios fuertes.

Resultado: **1.858 comunidades, la mayor de 50 proveedores**.

### Hallazgos del grafo

- **766 proveedores hacen obra e interventoría a la vez.** `CONSORCIO INTEGRAL MLF`
  tiene 29 obras y 21 interventorías; `CONSORCIO RT`, 7 y 7.
- **517 interventorías** donde el interventor también construyó en la misma entidad.
- El clúster más grande concentra **91 obras y 60 interventorías** entre 50
  proveedores, $369,9 mil millones.
- **1.072 contratos marcados por las dos capas a la vez** (trámite y red). Esos son
  los primeros de la fila.
- `PEDRO JOSE CORREDOR BECERRA` figura como representante legal de **24 empresas**
  proveedoras.

### Emparejamiento obra ↔ interventoría (candidatos, validados por muestra)

Lo de arriba detecta a nivel de **proveedor** que interventor y constructor son
la misma red. Esto va un paso más allá: **qué interventoría vigila qué obra
específica**, contrato a contrato.

```
python pipeline/build.py --steps 07 --no-export
python pipeline/emparejamiento_interventoria.py
```

Obra e interventoría no comparten `noticeUID` ni ningún identificador común, así
que el emparejamiento es en dos niveles, medidos contra los **13.074** contratos
de interventoría:

1. **Citación explícita (16,9%, 2.075 casos).** Algunas interventorías citan
   casi literal el objeto de la obra que vigilan ("...AL CONTRATO DE OBRA CUYO
   OBJETO ES `<texto>`"). Se extrae ese texto y se compara contra los objetos
   de obra de la misma entidad. Es una cota inferior: solo se reconoce la
   frase exacta "cuyo objeto es"/"objeto es", así que variantes como "objeto
   corresponde a" quedan en el nivel 2.
2. **Similitud de texto (el resto).** Se probó primero `jaccard()` nativo de
   DuckDB (q-gramas de caracteres) y **no sirve**: dos objetos de obra sin
   ninguna relación puntuaban 0,69 solo por compartir vocabulario común del
   sector ("CONSTRUCCION", "MUNICIPIO", "MEJORAMIENTO"...). Se usa en cambio
   TF-IDF (`scikit-learn`, ya era dependencia del proyecto) fiteado sobre el
   corpus completo de objetos de obra, restringido a candidatos de la misma
   entidad, con coseno como score.

Cobertura medida: **99,8%** de las interventorías tiene al menos un candidato
en su propia entidad (score mediana 0,68); el 0,2% restante son entidades sin
ninguna obra registrada en el universo de construcción.

**La fecha de firma no se usa como filtro.** Se midió la brecha entre
interventoría y obra en los matches de citación explícita con score alto
(≥0,6): el **18% está a más de 2 años de distancia**, porque algunas entidades
reusan el mismo objeto en contratos de mantenimiento recurrente año a año.
Filtrar por fecha habría descartado matches legítimos; queda como columna
informativa (`dias_diferencia_firma`), no como filtro duro.

**Validación manual sobre 102 pares** (`out/muestra_validacion_interventoria.csv`,
estratificados por método y banda de score): el **score predice el acierto
mucho mejor que el método** (citación explícita vs. similitud de texto).

| Banda de score | Precisión medida |
|---|---|
| bajo (&lt;0,3) | 11,8% |
| medio (0,3–0,6) | 55,9% |
| **alto (≥0,6)** | **88,2%** |

Con texto no truncado, la citación explícita con score alto es casi siempre
un acierto por cita verbatim. Falla sistemáticamente cuando coincide entidad +
tipo de proyecto pero no el sitio/beneficiario específico (dos jardines
infantiles distintos en la misma ciudad, dos veredas distintas del mismo
municipio). La validación también encontró **contaminación real en el
universo de obras candidatas**: algunas filas marcadas `tipo_contrato='OBRA'`
son en realidad otras interventorías, y hay colisiones donde dos
interventorías distintas caen en el mismo `id_obra` — pendiente de investigar
en el dataset fuente, no es un bug del script de emparejamiento.

Dado esto, **score ≥ 0,6 es un candidato razonablemente confiable (88%); por
debajo de 0,3 el método no sirve**. Aun así no se ha promovido a una bandera
puntuada en `06_banderas_grafo.sql` — 102 pares es una muestra chica para fijar
un umbral de producción, y primero hay que resolver la contaminación del
universo de obras. `pipeline/emparejamiento_interventoria.py` sigue exportando
la muestra para poder ampliar la validación.

### Decisión metodológica 10: el placeholder que se traga el grafo

`domicilio_replegal` está poblado al 100%, pero el **63% es la cadena
'NO DEFINIDO'**, que por sí sola liga **19.403 proveedores**. Usada como arista
crea un único clique de 19.403 nodos y la detección de comunidades deja de
significar nada.

La regla es **generalizada, no caso por caso**: cualquier valor de llave que ligue
más de 50 proveedores distintos entra a la lista negra, sea el que sea. Así también
caen los placeholders que todavía no conocemos. `pipeline/grafo.py` **falla en vez
de escribir** si algún clúster supera 200 proveedores.

### Decisión metodológica 11: costumbre administrativa vs. anomalía

**4.478 contratos (10,9%) tienen al mismo funcionario como ordenador del gasto y
como supervisor** — quien autoriza el pago es quien certifica que la obra se hizo.
Está repartido en **617 entidades**, así que es sistémico.

Pero dentro de algunas entidades es el 92–100% de todo lo que firman (EDUNA: 180 de
180; Piedecuesta: 240 de 260). Eso es una **costumbre de digitación institucional**,
no 240 fallas individuales de control. Marcar cada contrato infla el conteo y
distorsiona el ranking municipal.

Se separó en dos indicadores:

- Donde en su entidad es la **excepción** (tasa <50%) → bandera de contrato:
  **1.773 contratos**.
- Donde es la **norma** → hallazgo de la entidad, reportado una sola vez:
  **33 entidades, $1,97 billones** en `entidades_autosupervision`.

## La cifra en pesos

```
python pipeline/build.py --steps 10 11 --no-export
```

De los **$209 billones** de obra pública analizada:

| Indicio | Contratos | Valor | % del universo |
|---|---|---|---|
| **Sin competencia: un solo oferente** | 19.116 | **$31,2 billones** | **14,9%** |
| Ventana de ofertas más corta de su modalidad | 11.050 | $13,3 billones | 6,4% |
| Adjudicado al 99,5-100% del presupuesto oficial | 10.077 | $10,4 billones | 5,0% |
| Obra adjudicada por contratación directa | 8.944 | $8,6 billones | 4,1% |
| Grupo económico que vigila y construye | 4.793 | $4,6 billones | 2,2% |
| Mismo funcionario ordena el gasto y supervisa | 1.773 | $3,5 billones | 1,7% |
| Fraccionamiento: contratos hermanos en 30 días | 3.993 | $3,0 billones | 1,4% |

Las filas **no se suman entre sí**: un contrato puede presentar varios indicios y se
cuenta en cada uno. Cada línea se compara contra el total del universo.

Por fuente de recursos, el SGP tiene la tasa más alta de indicios (**17,9%**), por
encima de regalías (10,7%) y recursos propios territoriales (11,1%). Y Cundinamarca
adjudicó **44,2%** de su obra pública sin competencia.

### Decisión metodológica 12: el sobrecosto por unidad no es calculable

El plan original era un modelo hedónico de costo por unidad física — costo por
kilómetro, por m², por aula — y calcular el sobrecosto como residual. **No es posible
con datos abiertos**: solo el **0,9%** de las 52.355 descripciones de obra declara una
cantidad con unidad (258 mencionan km, 21 mencionan m²).

Tampoco sirve el atajo de comparar contra la mediana del mismo tipo de obra: se midió
la dispersión y el percentil 95 es **59 veces la mediana** en vías y 39 en educativo.
Comparar totales dentro de un tipo mide **tamaño de proyecto, no sobreprecio**; un
indicador "N veces la mediana" solo marcaría las obras grandes. Por eso no existe.

Lo que sí se publica es una cifra aritmética y verificable: **cuánta plata pública pasó
por contratos con indicios**. No cuánta se robaron — eso requiere una investigación
judicial que este proyecto no hace ni reemplaza. La clasificación por tipo de obra
(49,3% de cobertura) se usa **solo para segmentar**, nunca para comparar precios.

La única vía a precios unitarios reales es parsear los APU de los pliegos en PDF, que
sigue pendiente y es caro.

## Tablero

```
python pipeline/export_web.py     # JSON estatico a out_web/ (raiz del repo)
python3 plomada/build.py          # copia out_web/ a site/datos/ y genera el sitio
python3 -m http.server -d plomada/site 8765
```

(Tanda A de la unificacion de frontends: `export_web.py` ya no escribe
directo a `web/`. `plomada/build.py` es ahora el unico que escribe el sitio
publicado — asi `plomada/test_privacy.py` controla TODO el artefacto,
tablero incluido, de una sola pasada.)

Correccion (Tanda B): esta seccion decia "sin build step, sin npm, sin CDN".
Ya no es cierto y no lo era del todo ni antes: hay build step
(`python3 design/construir.py` compone `plomada/static/estilo.css`) y hasta hace
poco el tablero cargaba Leaflet desde unpkg.com. Hoy: sin npm (los modulos JS son
ES nativos, sin bundler), Leaflet vendorizado en `plomada/static/vendor/leaflet/`
(BSD-2, ver `design/VENDOR.md`), y el UNICO CDN que queda es Esri
(`server.arcgisonline.com`) para las imagenes satelitales de la ficha de contrato —
esas no se pueden vendorizar (son el mundo), asi que el mapa satelital es
click-to-load: no le dice a Esri que coordenadas mira nadie hasta que el lector
pulsa el boton.

El tablero (`/tablero/`, generado por `plomada/build.py`, ya no un HTML aparte)
tiene cinco vistas: la cifra lider, la plata por indicio, un **dumbbell** de tasa
cruda contra tasa ajustada por municipio (la forma *es* el argumento metodologico:
se ve el jalon hacia la media donde hay poca evidencia), una dispersion de
departamentos, y un explorador de la red de proveedores.

Paleta: el sistema de diseno es **Modernist** (`design/modernist/`, vendorizado,
no se parchea), mono a proposito — un acento rojo usado con avaricia. El tablero
no le fuerza una paleta categorica: la identidad de serie la lleva la FORMA
(relleno solido vs. aro hueco vs. el acento para el hallazgo del proyecto), medido
y documentado en `design/plomada/VALIDACION.md`. No hay modo oscuro en esta fase
(decision explicita: Modernist es un sistema de banda clara, y volver a uno oscuro
exige tokens propios re-validados, no un volteo automatico). Cada grafico conserva
su gemelo en tabla, y las limitaciones viajan **con** los datos (`meta.json`) para
que el tablero no pueda mostrar una cifra sin su salvedad.

## API pública

El tablero es una lectura de los datos; la API es **todas las demás**. Un periodista
que quiere el CSV de su departamento, otra herramienta que quiere cruzar los indicios
con su propia base, o un agente de IA que no sea Claude: ninguno tenía por dónde
entrarle sin clonar el repo y correr 4 minutos de ingesta.

```bash
python pipeline/build.py --all          # incluye el paso 90: tablas api_*
docker compose up -d db
export DATABASE_URL=postgresql://plomada:plomada@localhost:5432/plomada
python pipeline/load_postgres.py        # make load
uvicorn app.main:app --app-dir api      # make api  ->  http://localhost:8000/docs
```

REST de solo lectura, versionada en `/v1`, sin autenticación —los datos son
públicos— y con referencia OpenAPI en `/docs`. **Documentación completa en
[`API.md`](../API.md).**

| Endpoint | Qué devuelve |
|---|---|
| `GET /v1/meta` | Cobertura medida de cada campo y las limitaciones |
| `GET /v1/banderas` | Glosario de las 26 banderas con sus pesos |
| `GET /v1/titulares` · `/indicios` · `/fuentes` · `/tipos-obra` | Las cifras del tablero |
| `GET /v1/municipios` · `/departamentos` · `/autosupervision` | Rankings territoriales y hallazgos por entidad |
| `GET /v1/contratos` | Búsqueda con 18 filtros, incluido `bandera` repetible |
| `GET /v1/contratos/{id}` | Ficha con **cada bandera y la evidencia numérica que la disparó** |
| `GET /v1/entidades` · `/entidades/{nit}` | Entidades contratantes y su perfil |
| `GET /v1/proveedores` · `/proveedores/{doc}` | Proveedores y sus contrapartes en la red |
| `GET /v1/red/clusters` · `/clusters/{id}` | Grupos económicos y su subgrafo |
| `GET /v1/alertas` · `/alertas/resumen` | Licitaciones abiertas con banderas |

Cuatro decisiones que la definen:

1. **El aviso viaja con cada respuesta.** `meta.aviso` en JSON, `X-Plomada-Aviso` en
   CSV. Mismo criterio que `meta.json` en el tablero: no se puede sacar una cifra sin
   su salvedad. `GET /v1/meta` trae además las limitaciones completas.
2. **`/v1/contratos/{id}` publica la evidencia.** Cada bandera encendida sale con su
   peso, su glosa y el número que la disparó en ese contrato (`ev_hermanos_30d: 4`,
   `ev_proveedores_por_cuenta: 3`). «Sin evidencia no se publica» deja de ser una
   frase del README y pasa a ser el contrato de la API.
3. **`?formato=csv` en todo listado.** El público objetivo es periodístico: que el
   resultado de un filtro se abra en Excel sin escribir código es la diferencia entre
   que se use y que no. Con BOM, porque sin él Excel en Windows rompe las tildes de
   los nombres de entidad.
4. **REST y MCP comparten la capa de consulta.** `api/app/consultas.py` es el único
   sitio del servicio con SQL, y lo usan tanto los endpoints como las tools del
   servidor MCP. Antes el MCP tenía su propia copia del umbral de «atípico»: dos
   definiciones de la misma cifra es exactamente el bug que este proyecto se pasa el
   README evitando.

Lo que sale por HTTP lo decide `sql/90_serving.sql` (rango 90-99, reservado para
esto desde el primer commit): materializa tablas `api_*` con las columnas enumeradas
a mano, y `pipeline/load_postgres.py` copia esas y solo esas a Postgres. La cuenta
bancaria no está en ninguna, y la puerta de calidad
`test_el_snapshot_publico_no_lleva_cuentas` —que recorre exactamente las tablas con
prefijo `api_`, y hasta ahora no verificaba nada porque no existía ninguna— por fin
tiene qué revisar.

## Alertas pre-adjudicación (Pilar 4)

Todo lo de arriba mira contratos ya firmados. Esto mira licitaciones que
**todavía aceptan ofertas**: mientras siguen abiertas, una observación al
pliego puede cambiar el resultado. Después de adjudicado, ya es tarde.

```
python pipeline/ingest_abiertos.py   # snapshot de hoy (~1 min, reanudable)
python pipeline/alertas.py           # requiere haber corrido build.py antes
python pipeline/export_web.py        # agrega alertas.json al tablero
```

Guarda un snapshot fechado en `data/raw/abiertos/YYYY-MM-DD.jsonl` y nunca lo
borra: comparar contra el de ayer es lo que permite detectar addendas que
mueven la fecha de cierre.

`.github/workflows/alertas-diarias.yml` corre este flujo una vez al día
(cron, con `workflow_dispatch` para correrlo a mano). Como todavía no hay
hosting configurado (`deploy-url` sin llenar), el `alertas.json` resultante
queda como artefacto descargable del workflow, no publicado. Los snapshots
se acumulan entre corridas vía cache de Actions (nunca se comitean: siguen
en `.gitignore`), y el núcleo (`ingest.py` + `build.py --all`) se reconstruye
solo una vez por semana para no golpear datos.gov.co a diario.

### Decisión metodológica 13: "abierto" no significa "accionable"

Se midió la plataforma en vivo antes de asumir nada. El filtro `estado_del_procedimiento
in ('Publicado','Abierto') AND adjudicado='No'` da **31.685 procesos** en el universo de
construcción el 2026-08-22. Pero:

- **85,5%** no tiene fecha de cierre de ofertas publicada.
- **12,9%** tiene esa fecha **ya vencida** — la entidad no actualizó el estado.
- Solo **1,6% (508 procesos)** tiene el plazo vigente hoy: ese es el único universo donde
  una alerta sirve para algo.

Mezclar los tres grupos bajo "alertas" habría sido engañoso — el titular no puede ser
"31.685 alertas" cuando el 98,4% no es accionable ahora mismo. Por eso `universo` es una
columna explícita (`accionable` / `zombie_vencido` / `sin_fecha_cierre`) y el tablero
reporta los tres números, no solo el bonito.

De los 508 procesos accionables, **43 presentan al menos una alerta**.

### Las banderas

| Bandera | Base |
|---|---|
| Plazo de ofertas más corto que el usual en su modalidad | Reutiliza `base_ventana` (percentil 10 histórico), ya calculado en el paso 02 |
| Presupuesto pegado al techo de mínima cuantía de la entidad | El año en curso casi nunca tiene muestra propia suficiente (2026 solo tenía 4 entidades con n≥20): se usa el año más reciente disponible por entidad, documentado como simplificación |
| La entidad tiene un patrón histórico de proponente único en esa categoría | Umbral **medido**, no supuesto: sobre 1.701 grupos históricos (entidad × categoría UNSPSC) con n≥5, el percentil 90 de la tasa de proponente único es 0,818. Se marca el decil superior (≥0,80), no "tuvo un caso" |
| Nadie ha manifestado interés y el cierre es en una semana o menos | Alerta temprana de proceso que puede quedar vacío |
| La fecha de cierre cambió desde el snapshot anterior | Requiere dos días de historial; en la primera corrida queda en `NULL` (no en `false`, que afirmaría falsamente que no hubo cambio) |

### El bug que esto destapó, y que llevaba desde el primer commit

Al construir esto encontré que `urlproceso` llega de Socrata como `STRUCT(url VARCHAR)`,
no como texto. `CAST(urlproceso AS VARCHAR)` sobre un struct da su representación Python
literal — `"{'url': 'https://...'}"` — en vez de la URL. Eso rompía **todo enlace clicable**
del proyecto: los CSVs de `out/`, la consola de `report.py`, y ahora iba a romper también
la tabla de alertas. Estaba ahí desde `sql/01_stage.sql` en el primer commit.

No rompía el *join* (el regex de `notice_uid` encontraba el patrón igual, embebido en el
texto mal formado), así que ninguna cifra agregada estaba mal — pero cualquier periodista
que intentara hacer clic en un contrato se habría encontrado con basura. Se corrigió
extrayendo `urlproceso.url` en la fuente (`01_stage.sql` y `30_procesos_abiertos.sql`), y
se agregó una prueba de regresión (`test_urlproceso_es_una_url_no_un_struct`) para que no
vuelva a colarse.

### Limitación de diseño en `build.py --all`

`--all` corría los pasos 04-06 (grafo) confiando en que `clusters`/`clusters_perfil` ya
existieran de una corrida manual anterior de `pipeline/grafo.py` — nunca lo invocaba él
mismo. Y con el paso 30 nuevo, `--all` directamente reventaba porque ese archivo necesita
que `pipeline/alertas.py` le inyecte la ruta del snapshot del día antes de ejecutarlo.
Se agregó una guardia genérica en `build.py`: cualquier `.sql` con un placeholder
`__ALGO__` sin resolver se **omite con un mensaje claro** en vez de fallar, cuando se corre
como parte de un lote (`--all` o `--steps` con varios pasos). Esto protege también a
cualquier paso futuro del satelital (20-29) que necesite el mismo patrón de snapshot fechado.

## Puertas de calidad

`python -m pytest tests/` — **35 puertas** sobre los datos. Cada una existe porque el
error correspondiente ya ocurrió en este proyecto y produjo números falsos. Fallan el
PR, no son advertencias.

`python -m pytest api/tests/` — **19 pruebas** sobre el contrato de la API, en su
propio entorno (el SDK de MCP exige Python ≥3.10 y el pipeline está fijado a 3.9). No
necesitan Postgres: la capa de consulta se sustituye por dobles, así que corren en
cada PR. Verifican lo que es responsabilidad de la API y no de los datos — que el
aviso viaje en toda respuesta, que un `orden` o una `bandera` fuera de la lista blanca
den 400 **antes** de tocar el SQL, y que ninguna respuesta pueda filtrar la cuenta
bancaria.

`python api/app/mcp/test_smoke.py` — las 7 tools del MCP contra un Postgres real.

## Contrato de datos entre frentes

DuckDB admite **un solo escritor**: cinco personas no pueden construir contra el
mismo `.duckdb`. El único artefacto compartido es `data/exports/base.parquet`
(17 MB), de solo lectura. Cada frente escribe su propio archivo y su propio rango
de numeración SQL (`04-09` grafo, `10-19` precios, `20-29` geo, `30-39` alertas,
`90-99` serving). Los pasos `01-03` están congelados: tocarlos le cambia el piso a
todos.

## Pendiente

1. Precios unitarios de construcción → sobrecosto estimado en pesos.
2. Emparejamiento obra↔interventoría (ver "Grafo de personas"): la validación
   sobre 102 pares dio 88,2% de precisión con score ≥0,6. Antes de promoverlo
   a una bandera puntuada en `06_banderas_grafo.sql` falta (a) investigar la
   contaminación detectada en el universo de obras candidatas (filas de
   interventoría mezcladas ahí) y (b) ampliar la muestra validada más allá de
   102 pares.
3. Verificación satelital (Sentinel-1/2) sobre `direcci_n_de_ejecuci_n_del_contrato`,
   validada contra el Registro Nacional de Obras Civiles Inconclusas.
4. Publicar el tablero en algún hosting (`deploy-url` en
   `platanus-hack-project.jsonc` sigue vacío) y conectar ahí el `alertas.json`
   diario que ya genera `.github/workflows/alertas-diarias.yml`, en vez de
   dejarlo como artefacto descargable.
5. Capa de serving (`api/`, Postgres): construida. `sql/90_serving.sql` publica
   las tablas `api_*`, `pipeline/load_postgres.py` las carga (`make load`) y la
   API REST (`/v1`, ver [`API.md`](../API.md)) y el servidor MCP leen de ahí por la
   misma capa de consulta. La topología de producción está declarada en
   [`render.yaml`](../render.yaml); después de aplicar el Blueprint solo hay que
   cargar el warehouse en la base creada.
6. Tablero conversacional (MCP + Claude): servidor MCP y proxy de chat ya
   construidos (`api/app/mcp/server.py`, `api/app/main.py`), documentados en
   [`MCP.md`](../MCP.md). El mismo servicio queda desplegado por el Blueprint.
7. Tras aplicar el Blueprint, cargar el warehouse con
   `pipeline/load_postgres.py` y conectar el front a la URL asignada.

## Fuentes

- SECOP II – Contratos Electrónicos: `jbjy-vk9h` en datos.gov.co
- SECOP II – Procesos de Contratación: `p6dx-8zbt` en datos.gov.co
- Antecedente académico: *VigIA: prioritizing public procurement oversight with
  machine learning models and risk indices*, Data & Policy (Cambridge, 2024).
  Sus autores señalan como trabajo pendiente justamente el análisis de red de
  proveedores con métodos de grafos.

## Licencia

Código y metodología abiertos. Los datos son públicos y de propiedad del Estado
colombiano.

## Equipo — team-15

- Andres Alejandro Niño Araujo ([@anothercoolcoder](https://github.com/anothercoolcoder))
- Santiago Reina Diaz ([@rarechimera87](https://github.com/rarechimera87))
- Jose Luis Salamanca Lopez ([@joseslk](https://github.com/joseslk))
- Camilo Andres Niño Amaya ([@camiloAndres11](https://github.com/camiloAndres11))
- Diego Andrés Combariza Puerto ([@diegocombariza11](https://github.com/diegocombariza11))
