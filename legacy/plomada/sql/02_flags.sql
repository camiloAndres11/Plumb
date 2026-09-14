-- =====================================================================
-- 02_flags.sql : indicadores de riesgo a nivel de CONTRATO.
--
-- Principio: cada bandera es (a) calculable con datos publicos,
-- (b) explicable en una frase a un periodista, y (c) acompanada de la
-- evidencia numerica que la disparo. Sin evidencia no se publica.
--
-- Riesgo != fraude. Estas son senales para PRIORIZAR investigacion.
-- =====================================================================

-- ---------------------------------------------------------------------
-- El dataset de procesos trae VARIAS filas por proceso (una por lote y
-- por adjudicacion). Unir directo duplicaria contratos y contaminaria
-- todos los conteos. Se colapsa a una fila por proceso ANTES de unir.
--   * los conteos de competencia se toman como el maximo del proceso
--   * el precio base se suma por lote (es el presupuesto del proceso)
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE procesos_1x AS
SELECT
  notice_uid,
  sum(DISTINCT precio_base)          AS precio_base,
  sum(valor_adjudicado)              AS valor_adjudicado,
  max(n_invitados)                   AS n_invitados,
  max(n_manifestaron)                AS n_manifestaron,
  max(n_respuestas)                  AS n_respuestas,
  max(n_oferentes_unicos)            AS n_oferentes_unicos,
  max(n_visualizaciones)             AS n_visualizaciones,
  max(n_lotes)                       AS n_lotes,
  min(fecha_publicacion)             AS fecha_publicacion,
  min(fecha_cierre_ofertas)          AS fecha_cierre_ofertas,
  min(fecha_adjudicacion)            AS fecha_adjudicacion,
  any_value(adjudicador)             AS adjudicador,
  any_value(estado_proceso)          AS estado_proceso,
  count(*)                           AS n_filas_proceso
FROM procesos
WHERE notice_uid IS NOT NULL
GROUP BY notice_uid;

-- ---------------------------------------------------------------------
-- Union contrato <-> proceso. Da acceso a los campos de competencia
-- (numero de oferentes, precio base, ventana de ofertas) que no estan
-- en el dataset de contratos.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE base AS
SELECT
  c.*,
  p.precio_base,
  p.valor_adjudicado,
  p.n_invitados,
  p.n_manifestaron,
  p.n_respuestas,
  p.n_oferentes_unicos,
  p.n_visualizaciones,
  p.fecha_publicacion,
  p.fecha_cierre_ofertas,
  p.adjudicador,
  -- dias que el mercado tuvo para preparar y presentar oferta
  CASE WHEN p.fecha_publicacion IS NOT NULL AND p.fecha_cierre_ofertas IS NOT NULL
       THEN date_diff('day', p.fecha_publicacion, p.fecha_cierre_ofertas) END AS dias_ventana,
  -- duracion original = plazo total menos lo que le adicionaron despues
  CASE WHEN c.fecha_inicio IS NOT NULL AND c.fecha_fin IS NOT NULL
       THEN greatest(date_diff('day', c.fecha_inicio, c.fecha_fin)
                     - coalesce(c.dias_adicionados, 0), 0) END AS dias_originales
FROM contratos c
LEFT JOIN procesos_1x p
  ON c.notice_uid = p.notice_uid;

-- ---------------------------------------------------------------------
-- Llaves de red: entidades distintas que comparten un identificador
-- que en principio deberia ser unico. Son la materia prima del grafo.
-- ---------------------------------------------------------------------

-- Cuentas bancarias usadas por MAS DE UN proveedor distinto.
-- Dos "competidores" que cobran a la misma cuenta no son competidores.
-- La cuenta jamas se publica: solo el hecho de que se comparte.
-- Se clasifica el tipo de red antes de usarla, porque no toda cuenta
-- compartida es un indicio:
--   * JUNTA DE ACCION COMUNAL / asociaciones comunitarias: el municipio
--     canaliza pagos a varias juntas por una misma cuenta. Es ruido
--     administrativo, NO un cartel. Se excluye de la bandera.
--   * CONSORCIO/UNION TEMPORAL con su propio miembro: esperable, porque
--     la cuenta del consorcio suele estar a nombre del lider. Se marca
--     aparte con menor fuerza probatoria.
--   * empresas juridicamente independientes: este es el indicio real.
CREATE OR REPLACE TABLE red_cuentas AS
WITH g AS (
  SELECT cuenta_key,
         count(DISTINCT doc_proveedor) AS n_proveedores,
         list(DISTINCT proveedor)      AS proveedores,
         count(DISTINCT CASE WHEN proveedor LIKE '%JUNTA DE ACCION COMUNAL%'
                              OR proveedor LIKE 'JAC %'
                              OR proveedor LIKE '%ACCION COMUNAL%'
                             THEN doc_proveedor END) AS n_jac,
         count(DISTINCT CASE WHEN proveedor LIKE '%CONSORCIO%'
                              OR proveedor LIKE '%UNION TEMPORAL%'
                              OR proveedor LIKE 'UT %'
                             THEN doc_proveedor END) AS n_consorcios
  FROM base
  WHERE cuenta_key IS NOT NULL AND doc_proveedor IS NOT NULL
  GROUP BY cuenta_key
  HAVING count(DISTINCT doc_proveedor) > 1
)
SELECT *,
  CASE
    WHEN n_jac >= 2                        THEN 'comunitaria'
    WHEN n_consorcios >= n_proveedores - 1  THEN 'consorcios'
    ELSE 'empresas_independientes'
  END AS tipo_red
FROM g;

-- Representantes legales que figuran en varias empresas proveedoras.
CREATE OR REPLACE TABLE red_replegal AS
SELECT doc_replegal,
       any_value(replegal)           AS nombre,
       count(DISTINCT doc_proveedor) AS n_proveedores,
       list(DISTINCT proveedor)      AS proveedores
FROM base
WHERE doc_replegal IS NOT NULL AND doc_proveedor IS NOT NULL
GROUP BY doc_replegal
HAVING count(DISTINCT doc_proveedor) > 2;

-- ---------------------------------------------------------------------
-- Perfil del ordenador del gasto: el funcionario que firma la plata.
-- Concentracion medida con HHI sobre el reparto por proveedor.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE perfil_ordenador AS
WITH x AS (
  SELECT doc_ordenador, doc_proveedor, sum(valor_plausible) AS v
  FROM base
  WHERE doc_ordenador IS NOT NULL AND doc_proveedor IS NOT NULL AND valor_plausible > 0
  GROUP BY 1, 2
), t AS (
  SELECT doc_ordenador, sum(v) AS total, count(*) AS n_proveedores
  FROM x GROUP BY 1
)
SELECT
  t.doc_ordenador,
  t.total,
  t.n_proveedores,
  sum(power(x.v / t.total, 2))                       AS hhi,
  max(x.v / t.total)                                 AS share_top1,
  count(*)                                           AS n_pares
FROM x JOIN t USING (doc_ordenador)
GROUP BY 1, 2, 3;

-- Numero de contratos que cada ordenador ha firmado (volumen).
CREATE OR REPLACE TABLE vol_ordenador AS
SELECT doc_ordenador,
       any_value(ordenador)          AS nombre,
       count(*)                      AS n_contratos,
       sum(valor_plausible)          AS valor_total,
       count(DISTINCT nit_entidad)   AS n_entidades
FROM base
WHERE doc_ordenador IS NOT NULL
GROUP BY doc_ordenador;

-- Carga del supervisor: obras vigiladas simultaneamente por la misma persona.
CREATE OR REPLACE TABLE carga_supervisor AS
SELECT doc_supervisor,
       any_value(supervisor)       AS nombre,
       count(*)                    AS n_contratos,
       sum(valor_plausible)        AS valor_vigilado,
       count(DISTINCT nit_entidad) AS n_entidades
FROM base
WHERE doc_supervisor IS NOT NULL
GROUP BY doc_supervisor;

-- ---------------------------------------------------------------------
-- Entidades publicas que tambien aparecen como PROVEEDOR. Cuando el Estado
-- le contrata al Estado (convenio interadministrativo: ANI -> INVIAS,
-- empresas industriales y comerciales del Estado, ESEs) la contratacion
-- directa es la via legal y NO es adjudicacion a dedo. Sin este filtro,
-- la bandera de obra directa se llena de falsos positivos.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE proveedores_publicos AS
SELECT DISTINCT doc_proveedor
FROM base
WHERE doc_proveedor IS NOT NULL
  AND (doc_proveedor IN (SELECT DISTINCT nit_entidad FROM base WHERE nit_entidad IS NOT NULL)
       OR proveedor LIKE 'MUNICIPIO DE %'
       OR proveedor LIKE 'GOBERNACION%'
       OR proveedor LIKE '%EMPRESA INDUSTRIAL Y COMERCIAL%'
       OR proveedor LIKE '%E.S.E%'
       OR proveedor LIKE 'INVIAS%'
       OR proveedor LIKE '%FONDO FINANCIERO DE PROYECTOS%');

-- ---------------------------------------------------------------------
-- Tasa de autosupervision POR ENTIDAD.
--
-- Que el ordenador del gasto sea tambien el supervisor aparece en 4.478
-- contratos repartidos en 617 entidades, asi que es sistemico y no un
-- puñado de casos. Pero dentro de algunas entidades es el 92-100% de
-- todo lo que firman (EDUNA: 180 de 180; Piedecuesta: 240 de 260): eso es
-- una COSTUMBRE ADMINISTRATIVA, no 240 fallas individuales de control.
--
-- Mezclar las dos cosas infla el conteo y distorsiona el ranking
-- municipal. Se separan:
--   * si en su entidad es la EXCEPCION -> anomalia del contrato (bandera)
--   * si es la NORMA -> hallazgo de la entidad, se reporta aparte y una
--     sola vez, en `entidades_autosupervision`
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE tasa_autosupervision AS
SELECT
  nit_entidad,
  count(*) FILTER (WHERE doc_ordenador = doc_supervisor) AS n_auto,
  count(*)                                              AS n_con_ambos,
  count(*) FILTER (WHERE doc_ordenador = doc_supervisor)::DOUBLE / count(*) AS tasa
FROM base
WHERE doc_ordenador IS NOT NULL AND doc_supervisor IS NOT NULL
GROUP BY nit_entidad;

-- Entidades donde autosupervisar es la practica institucional. Es una
-- historia mas fuerte que la suma de sus contratos, y se cuenta una vez.
CREATE OR REPLACE TABLE entidades_autosupervision AS
SELECT
  t.nit_entidad,
  mode(b.entidad)        AS entidad,
  mode(b.departamento)   AS departamento,
  mode(b.ciudad)         AS ciudad,
  t.n_auto,
  t.n_con_ambos,
  t.tasa,
  sum(b.valor_plausible) FILTER (WHERE b.doc_ordenador = b.doc_supervisor) AS valor_auto
FROM tasa_autosupervision t
JOIN base b USING (nit_entidad)
WHERE t.tasa >= 0.5 AND t.n_con_ambos >= 20
GROUP BY t.nit_entidad, t.n_auto, t.n_con_ambos, t.tasa;

-- ---------------------------------------------------------------------
-- Tope empirico de minima cuantia POR ENTIDAD.
-- No hardcodeamos la tabla legal en SMMLV: la deducimos del propio
-- comportamiento de la entidad (percentil 99 de sus minimas cuantias).
-- Asi el indicador se auto-calibra por entidad y por ano.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE tope_minima AS
SELECT nit_entidad, anio,
       quantile_cont(valor_plausible, 0.99) AS cap,
       count(*)                   AS n
FROM base
WHERE modalidad LIKE '%MINIMA CUANTIA%' AND valor_plausible > 0 AND anio IS NOT NULL
GROUP BY 1, 2
HAVING count(*) >= 20;

-- Mediana de la ventana de ofertas por modalidad: linea base para
-- juzgar si un plazo fue anormalmente corto.
CREATE OR REPLACE TABLE base_ventana AS
SELECT modalidad,
       quantile_cont(dias_ventana, 0.10) AS p10,
       median(dias_ventana)              AS p50,
       count(*)                          AS n
FROM base
WHERE dias_ventana IS NOT NULL AND dias_ventana >= 0
GROUP BY modalidad
HAVING count(*) >= 30;

-- ---------------------------------------------------------------------
-- Fraccionamiento: la misma entidad partiendo un objeto en varios
-- contratos al mismo proveedor en una ventana corta, lo que evita
-- tener que licitar. Se cuenta cuantos hermanos tiene cada contrato.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE fraccionamiento AS
SELECT a.id_contrato,
       count(*) AS n_hermanos_30d,
       sum(b.valor_plausible) AS valor_hermanos
FROM base a
JOIN base b
  ON a.nit_entidad = b.nit_entidad
 AND a.doc_proveedor = b.doc_proveedor
 AND substr(a.unspsc, 1, 6) = substr(b.unspsc, 1, 6)
 AND a.id_contrato <> b.id_contrato
 AND abs(date_diff('day', a.fecha_firma, b.fecha_firma)) <= 30
WHERE a.doc_proveedor IS NOT NULL AND a.fecha_firma IS NOT NULL
GROUP BY a.id_contrato;

-- =====================================================================
-- TABLA DE BANDERAS
-- =====================================================================
CREATE OR REPLACE TABLE flags AS
SELECT
  b.id_contrato,
  b.nit_entidad, b.entidad, b.departamento, b.ciudad, b.orden,
  b.tipo_contrato, b.modalidad, b.estado, b.unspsc,
  b.fecha_firma, b.anio, b.periodo_gobierno,
  b.valor, b.valor_plausible, b.valor_pagado, b.valor_pend_ejecucion, b.valor_anticipo,
  b.doc_proveedor, b.proveedor, b.doc_ordenador, b.ordenador,
  b.doc_supervisor, b.supervisor, b.doc_replegal,
  b.rec_regalias, b.rec_sgp, b.rec_propios_terr,
  b.dias_ventana, b.dias_originales, b.dias_adicionados,
  b.precio_base, b.n_oferentes_unicos, b.n_invitados, b.urlproceso,
  b.descripcion, b.dir_ejecucion,

  -- ===== A. FALTA DE COMPETENCIA =====
  -- A1: un solo oferente. La bandera roja mas robusta de la literatura.
  (b.n_oferentes_unicos = 1 OR b.n_respuestas = 1)                       AS f_proponente_unico,
  -- A2: obra publica adjudicada a dedo.
  (b.tipo_contrato = 'OBRA' AND b.modalidad LIKE '%DIRECTA%'
     AND pp.doc_proveedor IS NULL)                                       AS f_obra_directa,
  -- A3: ventana de ofertas en el decil mas corto de su propia modalidad.
  (b.dias_ventana IS NOT NULL AND v.p10 IS NOT NULL
     AND b.dias_ventana <= v.p10)                                        AS f_ventana_corta,
  -- A4: adjudicado por casi exactamente el presupuesto oficial, y sin
  -- competencia. Precision sospechosa = presupuesto conocido de antemano.
  (b.precio_base > 0 AND b.valor / b.precio_base BETWEEN 0.995 AND 1.0
     AND coalesce(b.n_oferentes_unicos, 1) = 1)                          AS f_ratio_calcado,
  -- A5: invitaron a muchos y respondio uno solo.
  (b.n_invitados >= 5 AND coalesce(b.n_oferentes_unicos, 0) = 1)         AS f_invitacion_vacia,

  -- ===== B. RED DE PERSONAS =====
  -- B1: el proveedor cobra a una cuenta que comparte con otro proveedor.
  (rc.tipo_red = 'empresas_independientes')                              AS f_cuenta_compartida,
  -- variante debil: consorcios que comparten cuenta con su propio miembro
  (rc.tipo_red = 'consorcios')                                           AS f_cuenta_consorcios,
  -- B2: su representante legal aparece en 3+ empresas proveedoras.
  (rr.doc_replegal IS NOT NULL)                                          AS f_replegal_multiempresa,
  -- B3: el ordenador concentra mas de la mitad de su plata en un solo
  -- proveedor, teniendo de donde escoger.
  (po.share_top1 >= 0.5 AND po.n_proveedores >= 5)                       AS f_ordenador_concentrado,
  -- B4: supervisor con mas obras de las que es fisicamente posible vigilar.
  (cs.n_contratos >= 30)                                                 AS f_supervisor_sobrecargado,
  -- B5: el ordenador del gasto ha firmado en varias entidades distintas
  -- (senal de red que se mueve con el funcionario).
  (vo.n_entidades >= 3)                                                  AS f_ordenador_itinerante,
  -- B6: el MISMO funcionario autoriza el gasto y supervisa la ejecucion,
  -- Y en su entidad eso es la excepcion. Quien ordena el pago es quien
  -- certifica que la obra se hizo: falla de segregacion de funciones.
  -- Se exige tasa < 50% en la entidad para no marcar 240 veces lo que en
  -- realidad es una costumbre de publicacion (ver tasa_autosupervision).
  (b.doc_ordenador IS NOT NULL
     AND b.doc_ordenador = b.doc_supervisor
     AND coalesce(ta.tasa, 0) < 0.5)                                     AS f_ordenador_es_supervisor,

  -- ===== C. EJECUCION Y DINERO =====
  -- NOTA METODOLOGICA (verificada contra los datos, no supuesta):
  -- 1) Buscar anticipos POR ENCIMA del 50% legal es inutil en SECOP II:
  --    el maximo observado en los 1.590 contratos con anticipo es
  --    exactamente 0.500. La plataforma impone el tope, asi que esa
  --    bandera clasica de la literatura nunca puede dispararse aqui.
  --    Lo que si informa es quien AGOTA el tope.
  -- 2) 'Pagado mucho con ejecucion pendiente' tambien es imposible por
  --    construccion: valor_pagado + valor_pend_ejecucion = valor se
  --    cumple en 72.110 de 76.576 contratos (94%). Es una identidad
  --    contable, no una senal. Se reemplaza por las violaciones de esa
  --    identidad, que si son anomalias reales.

  -- C1: agota el anticipo maximo que permite la ley (Ley 80, art. 40).
  -- Plata girada antes de que exista obra.
  (b.valor_plausible > 0 AND b.valor_anticipo > 0
     AND abs(b.valor_anticipo / b.valor_plausible - 0.5) < 0.001)         AS f_anticipo_al_tope,
  -- C2: se pago mas de lo que vale el contrato.
  (b.valor_plausible > 0 AND b.valor_pagado > b.valor_plausible * 1.01)   AS f_sobrepago,
  -- C3: el contrato declara que NO tiene anticipo, pero registra plata
  -- girada como anticipo. 271 contratos, $377.800 millones.
  (b.habilita_anticipo = 'NO' AND b.valor_anticipo > 0)                   AS f_anticipo_no_declarado,
  -- C3: le adicionaron mas de la mitad del plazo original.
  (b.dias_originales > 0
     AND b.dias_adicionados / b.dias_originales > 0.5)                   AS f_prorroga_mayor,
  -- C4: firmado en los ultimos 45 dias del periodo de gobierno
  -- (contratacion de ultima hora antes de entregar la alcaldia).
  (b.fecha_firma IS NOT NULL AND b.periodo_gobierno IS NOT NULL
     AND month(b.fecha_firma) = 12 AND day(b.fecha_firma) >= 16
     AND b.anio IN (2019, 2023, 2027))                                   AS f_cierre_de_periodo,

  -- ===== D. UMBRALES Y FRACCIONAMIENTO =====
  -- D1: pegado al techo de su propia minima cuantia.
  (tm.cap IS NOT NULL AND b.modalidad LIKE '%MINIMA CUANTIA%'
     AND b.valor >= 0.97 * tm.cap)                                       AS f_al_tope_minima,
  -- D2: varios contratos hermanos al mismo proveedor, misma categoria,
  -- en 30 dias.
  (coalesce(fr.n_hermanos_30d, 0) >= 2)                                  AS f_fraccionamiento,

  -- ===== E. OPACIDAD =====
  -- E1: faltan datos que la norma obliga a publicar. La mala calidad del
  -- dato es en si misma un predictor (VigIA lo usa como bandera).
  (b.doc_ordenador IS NULL OR b.doc_supervisor IS NULL
     OR b.doc_proveedor IS NULL OR b.valor IS NULL
     OR b.fecha_firma IS NULL)                                           AS f_datos_faltantes,
  -- E2: el contrato no tiene proceso asociado en SECOP II.
  (b.precio_base IS NULL AND b.fecha_publicacion IS NULL)                AS f_sin_proceso,
  -- E3: valor publicado imposible (por encima del techo de 10 billones COP).
  -- No es ruido a barrer: es incumplimiento del deber de publicar
  -- informacion veraz, y distorsiona cualquier agregado que lo incluya.
  (b.valor IS NOT NULL AND b.valor_plausible IS NULL)                    AS f_valor_implausible,

  -- evidencia para el explicador
  po.share_top1        AS ev_share_top1_ordenador,
  po.hhi               AS ev_hhi_ordenador,
  cs.n_contratos       AS ev_contratos_supervisor,
  vo.n_entidades       AS ev_entidades_ordenador,
  rc.n_proveedores     AS ev_proveedores_por_cuenta,
  rc.tipo_red          AS ev_tipo_red_cuenta,
  rr.n_proveedores     AS ev_empresas_por_replegal,
  fr.n_hermanos_30d    AS ev_hermanos_30d,
  v.p50                AS ev_ventana_mediana_modalidad,
  tm.cap               AS ev_tope_minima_entidad,
  ta.tasa              AS ev_tasa_autosupervision_entidad
FROM base b
LEFT JOIN red_cuentas      rc USING (cuenta_key)
LEFT JOIN proveedores_publicos pp USING (doc_proveedor)
LEFT JOIN red_replegal     rr USING (doc_replegal)
LEFT JOIN perfil_ordenador po USING (doc_ordenador)
LEFT JOIN vol_ordenador    vo USING (doc_ordenador)
LEFT JOIN carga_supervisor cs USING (doc_supervisor)
LEFT JOIN base_ventana     v  USING (modalidad)
LEFT JOIN tasa_autosupervision ta USING (nit_entidad)
LEFT JOIN fraccionamiento  fr USING (id_contrato)
LEFT JOIN tope_minima      tm ON b.nit_entidad = tm.nit_entidad AND b.anio = tm.anio;
