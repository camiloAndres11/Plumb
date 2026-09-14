-- =====================================================================
-- 30_procesos_abiertos.sql  |  Owner: E  |  Rango reservado 30-39 (alertas)
--
-- Universo: licitaciones de obra publica que TODAVIA ACEPTAN OFERTAS.
-- Todo el mundo hace autopsias sobre contratos ya firmados; esto alerta
-- MIENTRAS la licitacion se puede observar.
--
-- Requiere en orden:
--   python pipeline/build.py                (01-03: nucleo + banderas historicas)
--   python pipeline/ingest_abiertos.py       (snapshot de hoy)
--   python pipeline/alertas.py               (corre este archivo + el
--                                              cruce con el snapshot de
--                                              ayer, que necesita Python
--                                              porque el archivo de ayer
--                                              puede no existir)
--
-- Usa las macros norm_id/norm_txt definidas en 01_stage.sql: persisten en
-- el catalogo de DuckDB una vez creadas, asi que no hace falta redefinirlas
-- aqui siempre que 01_stage.sql se haya corrido antes en este warehouse.
-- =====================================================================

CREATE OR REPLACE TABLE abiertos_raw AS
SELECT * FROM read_json_auto('__ABIERTOS_HOY__', format='newline_delimited',
                              union_by_name=true, sample_size=-1);

-- ---------------------------------------------------------------------
-- Colapsa duplicados. El dataset publica varias filas IDENTICAS por
-- proceso incluso en este universo chico -- un proceso trajo 21 copias
-- en la prueba real del 2026-08-22. any_value() es seguro porque las
-- copias son identicas, no fragmentos distintos que haya que combinar.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE abiertos AS
SELECT
  id_del_proceso,
  -- mismo bug que en 01_stage.sql: urlproceso es STRUCT(url VARCHAR), no
  -- texto. Se extrae .url antes de buscar el noticeUID.
  any_value(nullif(regexp_extract(urlproceso.url, 'CO1\.NTC\.[0-9]+'), '')) AS notice_uid,
  any_value(norm_id(nit_entidad))                        AS nit_entidad,
  any_value(norm_txt(entidad))                           AS entidad,
  any_value(norm_txt(departamento_entidad))              AS departamento,
  any_value(norm_txt(ciudad_entidad))                    AS ciudad,
  any_value(norm_txt(tipo_de_contrato))                  AS tipo_contrato,
  any_value(norm_txt(modalidad_de_contratacion))         AS modalidad,
  any_value(codigo_principal_de_categoria)               AS unspsc,
  any_value(descripci_n_del_procedimiento)               AS descripcion,
  max(try_cast(precio_base AS DOUBLE))                   AS precio_base,
  max(try_cast(proveedores_invitados AS BIGINT))         AS n_invitados,
  max(try_cast(proveedores_que_manifestaron AS BIGINT))  AS n_manifestaron,
  max(try_cast(respuestas_al_procedimiento AS BIGINT))   AS n_respuestas,
  try_cast(max(CAST(fecha_de_publicacion_del AS VARCHAR)) AS DATE) AS fecha_publicacion,
  try_cast(max(CAST(fecha_de_recepcion_de AS VARCHAR)) AS DATE)    AS fecha_cierre,
  any_value(urlproceso.url)                              AS urlproceso
FROM abiertos_raw
GROUP BY id_del_proceso;

-- ---------------------------------------------------------------------
-- Tope de minima cuantia VIGENTE por entidad.
-- tope_minima (de 02_flags.sql) exige n>=20 por (entidad, anio). El 2026
-- apenas tiene 4 entidades con esa muestra -- el ano esta empezando --
-- asi que se usa el ANIO MAS RECIENTE DISPONIBLE de cada entidad, no el
-- ano en curso. Es una simplificacion documentada: el tope legal cambia
-- poco de un ano a otro (esta atado al SMMLV), asi que el del ano
-- anterior es una aproximacion razonable mientras se acumula muestra.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE tope_minima_vigente AS
SELECT nit_entidad, anio, cap, n
FROM (
  SELECT *, row_number() OVER (PARTITION BY nit_entidad ORDER BY anio DESC) AS rn
  FROM tope_minima
) WHERE rn = 1;

-- ---------------------------------------------------------------------
-- Historial de proponente unico por (entidad, categoria UNSPSC a 2
-- digitos). Umbral MEDIDO, no supuesto: sobre 1.701 grupos historicos
-- con n>=5, el percentil 90 de la tasa de proponente unico es 0,818 y el
-- percentil 95 es 0,923. Se marca cuando una entidad esta en ese decil
-- superior para la categoria del proceso abierto: no es que haya tenido
-- UN caso de proponente unico, es que ese es su PATRON en esa categoria.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE historial_proponente_unico AS
SELECT
  nit_entidad,
  substr(unspsc, 1, 2)                          AS categoria,
  count(*)                                      AS n_historico,
  sum(f_proponente_unico::INT)                  AS n_proponente_unico,
  sum(f_proponente_unico::INT)::DOUBLE / count(*) AS tasa
FROM flags
WHERE nit_entidad IS NOT NULL AND unspsc IS NOT NULL
GROUP BY 1, 2
HAVING count(*) >= 5;

-- ---------------------------------------------------------------------
-- BANDERAS PRE-ADJUDICACION (las que se pueden calcular con UNA sola
-- foto). La bandera de addenda que mueve el cierre necesita comparar dos
-- snapshots y se calcula en pipeline/alertas.py, no aqui.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE abiertos_con_flags AS
SELECT
  a.*,
  date_diff('day', a.fecha_publicacion, a.fecha_cierre)   AS dias_ventana,
  date_diff('day', current_date, a.fecha_cierre)          AS dias_restantes,
  v.p10                                                   AS ev_ventana_p10_modalidad,

  -- Clasificacion de universo. MEDIDA, no supuesta: del snapshot del
  -- 2026-08-22, el 85,5% de los procesos "abiertos" NO TIENE fecha de
  -- cierre publicada, y otro 12,9% tiene la fecha ya vencida (la entidad
  -- no actualizo el estado). Solo el 1,6% (508 de 31.685) es un proceso
  -- donde hoy se puede radicar una observacion con efecto real. Mezclar
  -- los tres grupos bajo "alertas" seria enganoso: el titular no puede
  -- ser "31.685 alertas" cuando el 98,4% no es accionable ahora mismo.
  CASE
    WHEN a.fecha_cierre IS NULL THEN 'sin_fecha_cierre'
    WHEN a.fecha_cierre < current_date THEN 'zombie_vencido'
    ELSE 'accionable'
  END                                                      AS universo,

  -- P1: plazo de ofertas mas corto que el decil mas bajo de su modalidad.
  (a.fecha_publicacion IS NOT NULL AND a.fecha_cierre IS NOT NULL
     AND v.p10 IS NOT NULL
     AND date_diff('day', a.fecha_publicacion, a.fecha_cierre) <= v.p10)   AS f_ventana_corta,

  -- P2: presupuesto pegado al techo de minima cuantia de la entidad.
  (a.modalidad LIKE '%MINIMA CUANTIA%' AND tm.cap IS NOT NULL
     AND a.precio_base >= 0.97 * tm.cap)                                   AS f_al_tope_minima,

  -- P3: la entidad tiene, en esta categoria, un patron historico de
  -- proponente unico (decil superior medido: tasa >= 0.80 con n>=5).
  (h.tasa >= 0.80)                                                         AS f_historial_proponente_unico,
  h.tasa                                                                   AS ev_tasa_historica_entidad,
  h.n_historico                                                            AS ev_n_historico_entidad,

  -- P4 (opacidad, no riesgo de fraude): la plataforma dice "abierto" pero
  -- el plazo ya vencio. La entidad no actualizo el estado.
  (a.fecha_cierre IS NOT NULL AND a.fecha_cierre < current_date)           AS f_cierre_vencido,

  -- P5 (opacidad): no se puede evaluar el plazo porque falta una fecha.
  (a.fecha_publicacion IS NULL OR a.fecha_cierre IS NULL)                  AS f_sin_fechas,

  -- P6: invitaron a varios y de momento nadie ha manifestado interes,
  -- a menos de una semana del cierre. Alerta temprana de proceso vacio.
  (a.n_invitados >= 5 AND coalesce(a.n_manifestaron, 0) = 0
     AND date_diff('day', current_date, a.fecha_cierre) BETWEEN 0 AND 7)   AS f_sin_interes_a_tiempo

FROM abiertos a
LEFT JOIN base_ventana v ON v.modalidad = a.modalidad
LEFT JOIN tope_minima_vigente tm ON tm.nit_entidad = a.nit_entidad
LEFT JOIN historial_proponente_unico h
  ON h.nit_entidad = a.nit_entidad AND h.categoria = substr(a.unspsc, 1, 2);
