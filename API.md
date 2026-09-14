# API pública de Plomada

> **Riesgo no es fraude.** Esta API devuelve **indicios** para priorizar
> investigación periodística y control social. Ninguna cifra de aquí prueba un
> delito, y el proyecto no afirma que lo pruebe. El aviso viaja en cada respuesta
> (`meta.aviso` en JSON, cabecera `X-Plomada-Aviso` en CSV) precisamente para que
> no se pueda citar una cifra sin él.

API REST de solo lectura sobre los indicios de riesgo en la **contratación de obra
pública de Colombia** (SECOP II) que calcula el pipeline de este repositorio.
Pública, sin autenticación y sin registro: los datos son del Estado colombiano y
ya son públicos.

- **Referencia interactiva (OpenAPI):** `GET /docs` · `GET /redoc` · `GET /openapi.json`
- **Índice de endpoints:** `GET /v1`
- **Código y metodología:** [docs/PLOMADA.md](docs/PLOMADA.md)
- **Capa conversacional (MCP + Claude):** [MCP.md](MCP.md)

---

## Índice

1. [Empezar en 30 segundos](#empezar-en-30-segundos)
2. [Convenciones](#convenciones)
   - [Sobre de respuesta](#sobre-de-respuesta)
   - [Paginación](#paginación)
   - [Formatos: JSON y CSV](#formatos-json-y-csv)
   - [Errores](#errores)
   - [Límites y uso justo](#límites-y-uso-justo)
3. [Antes de citar una cifra](#antes-de-citar-una-cifra)
4. [Referencia de endpoints](#referencia-de-endpoints)
   - [Catálogo](#catálogo)
   - [Agregados](#agregados)
   - [Contratos](#contratos)
   - [Actores: entidades y proveedores](#actores-entidades-y-proveedores)
   - [Red de proveedores](#red-de-proveedores)
   - [Alertas pre-adjudicación](#alertas-pre-adjudicación)
   - [Servicio y asistente](#servicio-y-asistente)
5. [Diccionario de datos](#diccionario-de-datos)
6. [Lo que la API no expone, y por qué](#lo-que-la-api-no-expone-y-por-qué)
7. [Correrla localmente](#correrla-localmente)
8. [Versionado y cambios](#versionado-y-cambios)
9. [Licencia y atribución](#licencia-y-atribución)

---

## Empezar en 30 segundos

```bash
BASE=http://localhost:8000        # o la URL pública del despliegue

# 1. Qué hay
curl -s $BASE/v1 | jq '.endpoints'

# 2. Qué NO se puede afirmar con estos datos (léelo primero)
curl -s $BASE/v1/meta | jq '.datos.limitaciones'

# 3. Las cifras de encabezado
curl -s $BASE/v1/titulares | jq '.datos'

# 4. Obra adjudicada a dedo en Santander, de mayor a menor valor
curl -s "$BASE/v1/contratos?departamento=SANTANDER&bandera=f_obra_directa&orden=-valor&limite=5" | jq '.datos[] | {entidad, proveedor, valor_plausible, banderas}'

# 5. Por qué está marcado ESE contrato, con la evidencia numérica
curl -s $BASE/v1/contratos/CO1.BDOS.XXXXXX | jq '.datos.banderas'

# 6. Lo mismo, en CSV para abrirlo en Excel
curl -s "$BASE/v1/contratos?departamento=SANTANDER&solo_atipicos=true&formato=csv" -o contratos.csv
```

---

## Convenciones

**URL base y versión.** Todos los endpoints de datos cuelgan de `/v1`. La versión
va en la ruta para poder cambiar el contrato más adelante sin romper a quien ya
integró. `/health` no está versionado.

**Idioma.** Los nombres de campo están en español y son **los mismos** que ya usan
los JSON del tablero (`web/data/*.json`). Ese vocabulario existe desde el primer
commit del proyecto; tener dos nombres para la misma cifra sería peor que tenerlos
en español.

**Métodos.** Solo `GET`. La API es de solo lectura por construcción: la base que
sirve solo contiene las tablas `api_*` que publica el paso `sql/90_serving.sql`.

**CORS.** Abierto por defecto (`*`). No hay cookies ni credenciales de servidor,
así que restringir orígenes no protegería nada.

### Sobre de respuesta

Toda respuesta con éxito en JSON tiene la misma forma:

```json
{
  "datos": [ ... ],
  "meta": {
    "version": "1.0.0",
    "fuente": "SECOP II - datos.gov.co (jbjy-vk9h contratos, p6dx-8zbt procesos)",
    "aviso": "Riesgo no es fraude. Estas cifras son indicios para priorizar investigacion periodistica y control social; ninguna prueba un delito.",
    "paginacion": { "limite": 50, "desplazamiento": 0, "total": 8944, "devueltas": 50 }
  }
}
```

Las **filas** de `datos` conservan exactamente la forma de los JSON del tablero: el
sobre es aditivo, no reemplaza nada.

### Paginación

| Parámetro | Tipo | Defecto | Máximo |
|---|---|---|---|
| `limite` | entero | 50 | **200** |
| `desplazamiento` | entero | 0 | — |

`meta.paginacion.total` es el número de filas que cumplen el filtro **sin paginar**,
así que sirve para calcular cuántas páginas hay sin recorrerlas.

El orden de cada endpoint termina siempre en una columna única (`id_contrato`,
`nit_entidad`, `doc`…). Sin ese desempate determinista, dos páginas consecutivas
podrían repetir u omitir filas cuando hay empates.

### Formatos: JSON y CSV

Todos los endpoints de listado aceptan `?formato=csv`. El CSV sale con cabecera,
con `Content-Disposition: attachment` y **con BOM UTF-8** — sin el BOM, Excel en
Windows rompe las tildes de los nombres de entidad, y el 90% los lleva.

Conversiones en CSV:

| Tipo | Se escribe como |
|---|---|
| `null` | celda vacía |
| booleano | `true` / `false` |
| fecha | ISO-8601 (`2023-12-20`) |
| lista (p.ej. `banderas`) | valores separados por `\|` |

En CSV se pierde el sobre — una hoja de cálculo no abre bien un archivo con
metadatos arriba — así que el aviso viaja en la cabecera `X-Plomada-Aviso`.

### Errores

Un solo formato, para que un cliente pueda programar contra él:

```json
{ "error": { "codigo": "parametro_invalido", "mensaje": "...", "detalle": null } }
```

| HTTP | `codigo` | Cuándo |
|---|---|---|
| `400` | `parametro_invalido` | Un `orden`, una `bandera` o un `universo` que no está en la lista permitida. El mensaje dice cuáles son válidos. |
| `404` | `no_encontrado` | No existe el contrato, la entidad, el proveedor o el grupo pedido. |
| `422` | `parametro_invalido` | Tipo o rango inválido (p.ej. `limite=9999`). `detalle` trae el desglose de FastAPI. |
| `503` | `datos_no_disponibles` | La base no está cargada, o el endpoint depende de un paso opcional del pipeline. El mensaje trae **el comando que falta correr**. |

Los valores de `codigo` son estables; los de `mensaje`, no.

### Límites y uso justo

No hay API key ni cuotas. Las protecciones son estructurales:

- `limite` tope duro de 200 filas por página.
- `orden` y `bandera` validados contra listas blancas **antes** de construir el SQL:
  un valor inventado devuelve `400` sin haber tocado la base.
- Ningún valor del cliente se interpola en una consulta; todos van parametrizados.

Si vas a bajar el universo completo, hazlo paginando con `limite=200` y un
`desplazamiento` creciente, o clona el repositorio y corre el pipeline: son ~4
minutos de ingesta y no golpeas este servicio.

---

## Antes de citar una cifra

`GET /v1/meta` devuelve la cobertura **medida** de cada campo y la lista de
limitaciones. No es letra chica: varias de esas limitaciones cambian cómo hay que
leer los números.

- **Solo SECOP II.** No incluye SECOP I ni entidades que publican mal.
- **La cédula del ordenador del gasto está en el 64,5%** de los contratos y la del
  supervisor en el 54,3%. El análisis de red cubre esa fracción, no el total.
- **La cuenta bancaria está en el 23,7%.** Las redes detectadas son un **piso**, no
  un censo.
- **No hay datos de oferentes perdedores**, solo el número de ofertas y el ganador.
- **El ranking municipal no está normalizado por población.**
- **El sobrecosto por unidad física no es calculable** con datos abiertos: solo el
  0,9% de las descripciones declara una cantidad con unidad.

Y dos trampas de aritmética que la API no puede evitar por ti:

1. **Suma `valor_plausible`, no `valor`.** Hay 24 contratos publicados con valores
   imposibles (hasta 6×10¹⁸ COP) que concentraban el 98,6% de cualquier total. No se
   borran: se aíslan con la bandera `f_valor_implausible` y quedan con
   `valor_plausible` nulo.
2. **Las filas de `/v1/indicios` no se suman entre sí.** Un contrato puede presentar
   varios indicios y se cuenta en cada uno. Cada línea se compara contra el total del
   universo, nunca contra las otras.

---

## Referencia de endpoints

### Catálogo

#### `GET /v1`
Índice de la API: versión, endpoints disponibles, licencia y dónde está esta
documentación. Sin parámetros.

#### `GET /v1/meta`
Cobertura de los datos, cifras de encabezado, el umbral explícito de «atípico» y la
lista de limitaciones.

```bash
curl -s $BASE/v1/meta | jq '.datos | {contratos, valor_total, cobertura, umbral_atipico}'
```

```json
{
  "contratos": 77864,
  "valor_total": 209134...,
  "cobertura": {
    "cedula_ordenador": 0.645, "cedula_supervisor": 0.543,
    "cuenta_bancaria": 0.237, "unido_a_proceso": 0.996, "tipo_obra": 0.493
  },
  "umbral_atipico": "n_banderas_fuertes >= 1 OR puntos_crudos >= 6"
}
```

#### `GET /v1/banderas`
Glosario de las **26 banderas** con su peso, su grupo, su glosa y las columnas de
evidencia que la sustentan. Los pesos son explícitos y discutibles: cualquiera puede
recalcular el puntaje con otros.

| Parámetro | Tipo | Defecto |
|---|---|---|
| `formato` | `json` \| `csv` | `json` |

```json
{ "bandera": "f_fraccionamiento", "peso": 3.0, "grupo": "Umbrales", "capa": "contrato",
  "glosa": "Contratos hermanos al mismo proveedor, misma categoria, en 30 dias",
  "evidencia": "ev_hermanos_30d" }
```

---

### Agregados

Espejo de las cifras del tablero. Salvo `/v1/municipios`, devuelven la tabla
completa (son de 3 a 40 filas) y aceptan `?formato=csv`.

| Endpoint | Devuelve |
|---|---|
| `GET /v1/titulares` | Cifras de encabezado: obra analizada, adjudicado sin competencia, clasificado atípico, con indicio fuerte de red… |
| `GET /v1/indicios` | Contratos y plata por categoría de indicio (18 filas). **No se suman entre sí.** |
| `GET /v1/departamentos` | Plata total, sin competencia, en riesgo, regalías, y las dos tasas por departamento. |
| `GET /v1/tipos-obra` | Plata por tipo de obra (vías, educativo, agua y saneamiento…). |
| `GET /v1/fuentes` | Plata por fuente de recursos: regalías, SGP, recursos propios territoriales. |
| `GET /v1/autosupervision` | Entidades donde el mismo funcionario ordena el gasto y supervisa en la mayoría de sus contratos. |

> **Sobre `/v1/titulares`:** «adjudicado sin competencia» es **mayor** que
> «clasificado atípico» y no es una contradicción. Un contrato con un solo oferente
> y nada más suma 2 puntos, y el umbral de atípico son 6 puntos o una bandera
> fuerte. Son dos preguntas distintas.

> **Sobre `/v1/tipos-obra`:** la clasificación cubre el 49,3% de los contratos y
> sirve **solo para segmentar**, nunca para comparar precios: el percentil 95 es 59
> veces la mediana en vías, así que comparar totales dentro de un tipo mide tamaño de
> proyecto, no sobreprecio.

> **Sobre `/v1/autosupervision`:** es un hallazgo de la **entidad**, reportado una
> sola vez. Marcar los 240 contratos de la misma alcaldía infla el conteo y
> distorsiona el ranking municipal cuando lo que hay es una costumbre de digitación
> institucional, no 240 fallas individuales de control.

#### `GET /v1/municipios`

| Parámetro | Tipo | Defecto | Notas |
|---|---|---|---|
| `departamento` | texto | — | Coincidencia parcial, insensible a mayúsculas |
| `min_contratos` | entero | `20` | Piso de volumen para entrar al ranking |
| `orden` | enum | `-tasa_ajustada` | `-tasa_ajustada` \| `-tasa_cruda` \| `-valor_atipico` \| `-contratos` |
| `limite` / `desplazamiento` / `formato` | | | Ver [Convenciones](#convenciones) |

Se devuelven **siempre las dos tasas**. La cruda encabeza la lista con municipios de
4 contratos y 2 marcados; la ajustada aplica encogimiento bayesiano empírico
(beta-binomial por momentos) y jala hacia la media nacional a quien no tiene volumen
que lo sostenga. Publicar una sola escondería el argumento metodológico. El defecto
`min_contratos=20` existe por la misma razón.

---

### Contratos

#### `GET /v1/contratos`

Universo: 77.864 contratos de construcción (obra, interventoría, consultoría,
concesión y APP).

| Parámetro | Tipo | Coincidencia | Notas |
|---|---|---|---|
| `entidad` | texto | parcial | |
| `nit_entidad` | texto | exacta | |
| `departamento`, `ciudad` | texto | parcial | |
| `tipo_contrato` | texto | exacta | `OBRA` \| `INTERVENTORIA` \| `CONSULTORIA` \| `CONCESION` \| `ASOCIACION PUBLICO PRIVADA` |
| `modalidad` | texto | parcial | p.ej. `DIRECTA`, `MINIMA CUANTIA` |
| `tipo_obra` | texto | exacta | `VIAS Y TRANSPORTE`, `EDUCATIVO`, `AGUA Y SANEAMIENTO`, `SALUD`, `DEPORTIVO Y PARQUES`, `VIVIENDA`, `EDIFICACION PUBLICA`, `ENERGIA` |
| `anio`, `anio_desde`, `anio_hasta` | entero | | |
| `proveedor` | texto | parcial | |
| `doc_proveedor` | texto | exacta | NIT o cédula |
| `cluster_id` | entero | exacta | Contratos de un grupo económico |
| `valor_min`, `valor_max` | número | | En COP, sobre `valor_plausible` |
| `texto` | texto | parcial | Busca en la descripción del objeto |
| `bandera` | enum | | **Repetible**, se combinan con AND. Nombres en `/v1/banderas` |
| `solo_atipicos` | booleano | | `true` = una bandera fuerte o 6+ puntos |
| `orden` | enum | | `-riesgo` (defecto) \| `riesgo` \| `-valor` \| `valor` \| `-fecha` \| `fecha` \| `-score` |
| `limite`, `desplazamiento`, `formato` | | | |

```bash
# Contratos con DOS indicios a la vez: proponente único Y fraccionamiento
curl -s "$BASE/v1/contratos?bandera=f_proponente_unico&bandera=f_fraccionamiento&limite=5"
```

Cada fila trae `banderas`, la lista de nombres de las banderas encendidas. Para el
detalle con evidencia, ve a la ficha.

#### `GET /v1/contratos/{id_contrato}`

La ficha completa, y el endpoint donde «sin evidencia no se publica» deja de ser una
frase del README y pasa a ser el contrato de la API. Agrupa el contrato en `dinero`,
`competencia`, `partes` y `riesgo`, y devuelve `banderas` con **el número que disparó
cada una en este contrato concreto**:

```json
{
  "datos": {
    "id_contrato": "CO1.BDOS.1234567",
    "urlproceso": "https://community.secop.gov.co/Public/Tendering/...",
    "entidad": "MUNICIPIO DE PIEDECUESTA",
    "riesgo": { "es_atipico": true, "puntos_crudos": 8, "n_banderas_fuertes": 1,
                "puntos_red": 3, "n_banderas_red_fuertes": 1, "cluster_id": 412 },
    "banderas": [
      { "bandera": "f_fraccionamiento", "peso": 3.0, "grupo": "Umbrales", "capa": "contrato",
        "glosa": "Contratos hermanos al mismo proveedor, misma categoria, en 30 dias",
        "evidencia": { "ev_hermanos_30d": 4 } },
      { "bandera": "f_proponente_unico", "peso": 2.0, "grupo": "Competencia", "capa": "contrato",
        "glosa": "Un solo oferente en el proceso", "evidencia": {} }
    ]
  }
}
```

`urlproceso` lleva al expediente público en SECOP II: úsalo para verificar antes de
publicar nada.

**404** si el `id_contrato` no está en el universo de obra pública analizado.

---

### Actores: entidades y proveedores

#### `GET /v1/entidades`

| Parámetro | Tipo | Notas |
|---|---|---|
| `q` | texto | Nombre parcial **o** NIT exacto |
| `departamento` | texto | parcial |
| `min_contratos` | entero | |
| `orden` | enum | `-valor` (defecto) \| `-contratos` \| `-atipicos` \| `-tasa` |

> Ordenar por `-tasa` sin `min_contratos` sube entidades con dos o tres contratos.
> Usa los dos parámetros juntos.

#### `GET /v1/entidades/{nit_entidad}`
Perfil de la entidad más `banderas_frecuentes` (sus diez banderas más comunes, con
glosa y peso) y `top_proveedores` (los diez con más plata adjudicada). **404** si el
NIT no existe.

#### `GET /v1/proveedores`

| Parámetro | Tipo | Notas |
|---|---|---|
| `q` | texto | Nombre parcial o documento exacto |
| `hace_ambos` | booleano | Los 766 proveedores que hacen obra **e** interventoría |
| `cluster_id` | entero | Miembros de un grupo económico |
| `min_contratos` | entero | |
| `orden` | enum | `-valor` (defecto) \| `-contratos` \| `-entidades` |

#### `GET /v1/proveedores/{doc}`
Perfil más:

- `contrapartes`: otros proveedores unidos a este por llaves que deberían ser únicas.
  `n_tipos` dice por cuántas llaves distintas — **dos o más es el indicio fuerte**
  (de 13.254 pares únicos, 9 están unidos por las tres a la vez y 2.237 por dos).
- `entidades`: a qué entidades le ha contratado.

**404** si el documento no existe.

---

### Red de proveedores

Los contratos no son filas: son aristas de una red de personas. Estos endpoints
exponen los grupos económicos detectados por detección de comunidades. La detección
encuentra 1.858 comunidades; la API publica las **1.857 de más de un proveedor**
(una empresa aislada no es una red).

#### `GET /v1/red/clusters`

| Parámetro | Tipo | Notas |
|---|---|---|
| `vigila_y_construye` | booleano | Grupos que concentran a la vez la obra y su interventoría |
| `min_proveedores` | entero ≥2 | |

Solo se publican grupos de más de un proveedor: un proveedor solo no es una red. La
marca `vigila_y_construye` **excluye** los grupos que contienen una entidad pública,
porque ahí la concentración es legal (convenios interadministrativos).

#### `GET /v1/red/clusters/{cluster_id}`
El subgrafo listo para dibujar: `nodos` (proveedores) y `aristas`. `tipos` dice por
qué están unidos —`comparte_cuenta`, `comparte_replegal`, `comparte_domicilio`— y
`n_tipos` cuántas de esas llaves coinciden.

**404** si el grupo no existe.

---

### Alertas pre-adjudicación

Todo lo demás mira contratos ya firmados. Esto mira licitaciones que **todavía
aceptan ofertas**: mientras siguen abiertas, una observación al pliego puede cambiar
el resultado. Después de adjudicado, ya es tarde.

Dependen de que alguien haya corrido `pipeline/alertas.py` contra un snapshot del
día. Si no, ambos endpoints responden **`503`** con el comando que falta.

#### `GET /v1/alertas`

| Parámetro | Tipo | Defecto |
|---|---|---|
| `universo` | enum | `accionable` \| `zombie_vencido` \| `sin_fecha_cierre` — defecto `accionable` |
| `departamento`, `entidad` | texto | parcial |
| `min_banderas` | entero | |

> **`universo` es una columna explícita a propósito.** Del snapshot medido el
> 2026-08-22, de 31.685 procesos que la plataforma marca como abiertos, el **85,5%**
> no tiene fecha de cierre publicada y el **12,9%** la tiene ya vencida. Solo el
> **1,6% (508 procesos)** admite hoy una observación con efecto. Un titular de
> «31.685 alertas» sería engañoso cuando el 98,4% no es accionable.

`f_cierre_movido` en `null` significa «no hay snapshot de ayer con que comparar», no
«se comparó y no cambió».

Orden: más banderas primero y, a igualdad, lo que cierra antes — el orden en que
sirve actuar.

#### `GET /v1/alertas/resumen`
Los tres números por universo más la fecha del snapshot.

---

### Servicio y asistente

| Endpoint | Qué es |
|---|---|
| `GET /health` | Salud del servicio. Responde aunque la base no esté cargada: es el health check del hosting, no un indicador de que haya datos. Para eso, `GET /v1/meta`. |
| `POST /chat` | Asistente conversacional sobre estos mismos datos. **BYOK**: cada usuario manda su propia API key de Anthropic en `X-Anthropic-Api-Key`; el servicio nunca la guarda. Responde en SSE. Contrato completo en [MCP.md](MCP.md). |
| `/mcp` | Servidor MCP (streamable-http) con las mismas consultas expuestas como tools, para clientes de IA. Ver [MCP.md](MCP.md). |

REST y MCP comparten la misma capa de consulta (`api/app/consultas.py`) sobre las
mismas tablas: no pueden dar cifras distintas para la misma pregunta.

---

## Diccionario de datos

### Campos clave de un contrato

| Campo | Significado |
|---|---|
| `id_contrato` | Identificador del contrato en SECOP II |
| `urlproceso` | Enlace al expediente público. Úsalo para verificar |
| `valor` | Valor publicado, tal cual |
| `valor_plausible` | `valor` si está en un rango posible, `null` si no. **Esta es la columna que se suma** |
| `precio_base` | Presupuesto oficial del proceso |
| `n_oferentes_unicos` | Cuántos oferentes efectivos hubo |
| `dias_ventana` | Días entre publicación y cierre de ofertas |
| `es_atipico` | `true` si enciende ≥1 bandera fuerte **o** acumula ≥6 puntos. Umbral explícito, no un modelo |
| `puntos_crudos` / `puntos_red` | Puntaje de la capa de trámite / de la capa de red. Separados a propósito |
| `score` | `puntos_crudos` normalizado a 0..1 |
| `cluster_id` | Grupo económico al que pertenece el proveedor |

### Las 26 banderas

Peso **3 = indicio fuerte**, 2 = intermedio, 1 = contexto. Consulta
`GET /v1/banderas` para la lista viva; esta tabla es la de referencia.

**Competencia**

| Bandera | Peso | Qué es |
|---|---|---|
| `f_proponente_unico` | 2 | Un solo oferente en el proceso |
| `f_obra_directa` | 2 | Obra pública adjudicada por contratación directa (excluye los 783 proveedores que son entidades públicas: ahí la directa es legal) |
| `f_ratio_calcado` | 2 | Adjudicado al 99,5–100% del presupuesto oficial, sin competencia |
| `f_invitacion_vacia` | 2 | Cinco o más invitados y un solo oferente efectivo |
| `f_ventana_corta` | 1 | Plazo de ofertas en el decil más corto de su modalidad |

**Red de personas**

| Bandera | Peso | Qué es |
|---|---|---|
| `f_cuenta_compartida` | 3 | Proveedores jurídicamente independientes cobrando a la misma cuenta |
| `f_ordenador_es_supervisor` | 3 | El mismo funcionario autoriza el gasto y supervisa, **y en su entidad eso es la excepción** |
| `f_replegal_multiempresa` | 2 | Representante legal compartido por 3+ empresas proveedoras |
| `f_ordenador_concentrado` | 2 | El ordenador concentra >50% de su valor en un solo proveedor |
| `f_supervisor_sobrecargado` | 1 | Supervisor con 30+ contratos a cargo |
| `f_ordenador_itinerante` | 1 | El ordenador ha firmado en 3+ entidades distintas |
| `f_cuenta_consorcios` | 1 | Consorcio comparte cuenta con su propio miembro (esperable; indicio débil) |
| `g_interventor_constructor` | 3 | El interventor también construye obra en la misma entidad |
| `g_cluster_vigila_y_construye` | 3 | Su grupo económico concentra a la vez la obra y su interventoría |
| `g_cluster_multillave` | 2 | Unido a otro proveedor por dos o más llaves que deberían ser únicas |
| `g_cluster_grande` | 1 | Pertenece a un grupo económico de 10 o más proveedores |

**Dinero y ejecución**

| Bandera | Peso | Qué es |
|---|---|---|
| `f_sobrepago` | 3 | Se pagó más del valor del contrato |
| `f_anticipo_no_declarado` | 3 | Declara no tener anticipo pero registra anticipo girado |
| `f_anticipo_al_tope` | 2 | Agota exactamente el anticipo máximo legal del 50% |
| `f_prorroga_mayor` | 1 | Plazo adicionado en más del 50% del original |
| `f_cierre_de_periodo` | 1 | Firmado en la segunda quincena de diciembre del último año de gobierno |

**Umbrales**

| Bandera | Peso | Qué es |
|---|---|---|
| `f_fraccionamiento` | 3 | Contratos hermanos al mismo proveedor, misma categoría, en 30 días |
| `f_al_tope_minima` | 2 | Valor pegado al techo de la mínima cuantía de la entidad |

**Opacidad**

| Bandera | Peso | Qué es |
|---|---|---|
| `f_datos_faltantes` | 1 | Faltan campos de publicación obligatoria |
| `f_sin_proceso` | 1 | El contrato no tiene proceso publicado en SECOP II |
| `f_valor_implausible` | 1 | Valor publicado imposible (por encima de 10 billones COP) |

### Evidencia (`ev_*`)

Cada bandera de `/v1/contratos/{id}` trae el número que la disparó:

| Columna | Qué mide |
|---|---|
| `ev_proveedores_por_cuenta` | Cuántos proveedores comparten esa cuenta |
| `ev_tipo_red_cuenta` | `empresas_independientes` \| `consorcios` \| `comunitaria` |
| `ev_empresas_por_replegal` | Cuántas empresas comparten ese representante legal |
| `ev_hermanos_30d` | Contratos hermanos en la ventana de 30 días |
| `ev_share_top1_ordenador` / `ev_hhi_ordenador` | Concentración del ordenador en un proveedor |
| `ev_entidades_ordenador` | En cuántas entidades ha firmado |
| `ev_contratos_supervisor` | Contratos a cargo de ese supervisor |
| `ev_ventana_mediana_modalidad` | Mediana de días de ofertas de esa modalidad |
| `ev_tope_minima_entidad` | Techo empírico de mínima cuantía de la entidad |
| `ev_tasa_autosupervision_entidad` | Qué tan habitual es autosupervisar en esa entidad |
| `ev_proveedores_cluster` / `ev_obras_cluster` / `ev_interventorias_cluster` | Tamaño y composición del grupo económico |

---

## Lo que la API no expone, y por qué

**La cuenta bancaria (`cuenta_key`, `banco`).** Se usa como llave de unión interna
para detectar proveedores distintos cobrando al mismo sitio, y **no se publica en
ninguna forma**: solo sale el *hecho* de que se comparte y cuántos la comparten. La
garantía está en tres capas: el paso `sql/90_serving.sql` no la copia a las tablas
`api_*`, el `response_model` de cada endpoint filtra lo que no está en el modelo, y
el CSV tiene su propia lista negra. Del lado de los datos lo verifica
`tests/test_calidad.py::test_el_snapshot_publico_no_lleva_cuentas`.

**El emparejamiento obra ↔ interventoría.** El pipeline produce candidatos de qué
interventoría vigila qué obra concreta (TF-IDF sobre los objetos, 88,2% de precisión
medida con score ≥0,6 sobre una muestra de 102 pares validados a mano). **No se
publica todavía**: la validación detectó contaminación real en el universo de obras
candidatas y 102 pares es muestra chica para fijar un umbral. El propio repositorio
no lo promovió a bandera puntuada; publicarlo por API le daría un estatus que el
proyecto deliberadamente no le dio.

**Un sobrecosto estimado en pesos.** No es calculable con datos abiertos y la API no
va a inventarlo. Lo que sí publica es una cifra aritmética y verificable: cuánta
plata pública pasó por contratos con indicios. No cuánta se robaron — eso requiere
una investigación judicial que este proyecto no hace ni reemplaza.

**Sí se publican** los nombres y documentos de ordenadores del gasto, supervisores y
representantes legales. Son campos del dataset oficial público del SECOP II y son
exactamente los que permiten seguir a un funcionario cuando cambia de entidad, que
es el aporte del proyecto.

---

## Correrla localmente

```bash
# 1. Datos (~4 min de ingesta la primera vez)
uv sync --extra legacy --extra dev   # o: pip install -e ".[legacy,dev]"
python pipeline/ingest.py
python pipeline/build.py --steps 01 02 03 04 05 --no-export
python pipeline/grafo.py
python pipeline/build.py --all          # incluye el paso 90 (tablas api_*)

# 2. Postgres y carga
docker compose up -d db
export DATABASE_URL=postgresql://plomada:plomada@localhost:5432/plomada
python pipeline/load_postgres.py        # o: make load

# 3. API
pip install -r api/requirements.txt
uvicorn app.main:app --app-dir api --reload
# http://localhost:8000/docs
```

Todo junto con Docker: `docker compose up` (API en `:8000`, Postgres en `:5432`).

Alertas pre-adjudicación (opcional, `/v1/alertas` responde 503 sin esto):

```bash
python pipeline/ingest_abiertos.py
python pipeline/alertas.py
python pipeline/load_postgres.py
```

Pruebas:

```bash
python -m pytest tests/            # puertas de calidad de los datos
uv sync --extra legacy --extra dev
python -m pytest api/tests/        # contrato del API, sin Postgres
python api/app/mcp/humo_mcp.py   # tools MCP contra un Postgres real
```

### Variables de entorno

| Variable | Obligatoria | Defecto | Para qué |
|---|---|---|---|
| `DATABASE_URL` | sí | — | Postgres con las tablas `api_*`. Acepta `postgresql://` y `postgresql+psycopg://` |
| `SELF_URL` | en producción | `http://127.0.0.1:8000` | URL pública del servicio. Alimenta el allowlist de Host de `/mcp` y la URL que Claude usa para alcanzarlo |
| `CORS_ORIGINS` | no | abierto (`*`) | Lista separada por comas para cerrar CORS |
| `PORT` | no | `8000` | Lo inyecta Render |

**`ANTHROPIC_API_KEY` no existe en el servidor**: `/chat` es BYOK.

---

## Versionado y cambios

La versión de la API va en la ruta (`/v1`) y en `meta.version` de cada respuesta.

- **Cambios compatibles** (campos nuevos, endpoints nuevos, filtros nuevos) suben la
  versión menor y no cambian la ruta. Un cliente debe ignorar los campos que no
  conozca.
- **Cambios incompatibles** (quitar o renombrar un campo, cambiar el significado de
  una cifra) estrenan `/v2`.
- Los valores de `error.codigo` son estables; los de `error.mensaje`, no: no
  programes contra el texto.

### 1.0.0

Primera versión pública. Catálogo, agregados, contratos con evidencia por bandera,
entidades, proveedores, red y alertas pre-adjudicación. Salida en JSON y CSV.

---

## Licencia y atribución

Los datos son **públicos y de propiedad del Estado colombiano** (SECOP II,
`jbjy-vk9h` y `p6dx-8zbt` en datos.gov.co). El código y la metodología de Plomada son
abiertos.

Si publicas algo basado en esta API, cita la fuente original (SECOP II) y, si la
metodología te sirvió, enlaza este repositorio. Y repite el aviso: **riesgo no es
fraude**.
