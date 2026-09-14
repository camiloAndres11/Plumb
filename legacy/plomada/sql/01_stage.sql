-- =====================================================================
-- 01_stage.sql : normalizacion. Todo llega de Socrata como texto.
-- Reglas duras:
--   * Los documentos de identidad son la LLAVE FUERTE de este proyecto.
--     Se normalizan a digitos puros; vacio -> NULL.
--   * Las cuentas bancarias se usan SOLO como llave de union interna.
--     Nunca se exponen. Se descartan las basura (repetidas/cortas) porque
--     si no, las cuentas placeholder generan cliques falsos.
-- =====================================================================

CREATE OR REPLACE MACRO norm_id(x) AS
  nullif(regexp_replace(coalesce(CAST(x AS VARCHAR), ''), '[^0-9]', '', 'g'), '');

-- Texto comparable: sin tildes, sin dobles espacios, mayusculas.
CREATE OR REPLACE MACRO norm_txt(x) AS
  nullif(trim(regexp_replace(upper(strip_accents(coalesce(CAST(x AS VARCHAR), ''))), '\s+', ' ', 'g')), '');

-- Cuenta bancaria utilizable como llave: >=6 digitos y no todos iguales.
-- (RE2 no soporta backreferences, asi que la repeticion se detecta
--  comparando contra el primer digito repetido, no con '^(.)\1*$'.)
CREATE OR REPLACE MACRO norm_cuenta(x) AS
  CASE
    WHEN norm_id(x) IS NULL THEN NULL
    WHEN length(norm_id(x)) < 6 THEN NULL
    WHEN norm_id(x) = repeat(substr(norm_id(x), 1, 1), length(norm_id(x))) THEN NULL
    ELSE norm_id(x)
  END;

CREATE OR REPLACE TABLE contratos AS
SELECT
  id_contrato,
  proceso_de_compra,
  referencia_del_contrato,
  -- urlproceso llega de Socrata como STRUCT(url VARCHAR), no como texto.
  -- CAST(... AS VARCHAR) sobre un struct da su representacion Python
  -- "{'url': '...'}" en vez de la URL: eso rompe todo enlace clicable en
  -- reportes, CSVs y el tablero. Se extrae el campo real.
  urlproceso.url                                        AS urlproceso,
  -- LLAVE REAL contrato<->proceso. Los ids nativos estan en namespaces
  -- distintos (contratos usa CO1.BDOS.*, procesos usa CO1.REQ.*) y no
  -- cruzan. El unico puente comun es el noticeUID de la URL publica.
  nullif(regexp_extract(urlproceso.url, 'CO1\.NTC\.[0-9]+'), '') AS notice_uid,

  -- entidad contratante
  norm_id(nit_entidad)                                  AS nit_entidad,
  norm_txt(nombre_entidad)                              AS entidad,
  norm_txt(departamento)                                AS departamento,
  norm_txt(ciudad)                                      AS ciudad,
  norm_txt(orden)                                       AS orden,
  norm_txt(sector)                                      AS sector,
  norm_txt(rama)                                        AS rama,

  -- naturaleza del contrato
  norm_txt(tipo_de_contrato)                            AS tipo_contrato,
  norm_txt(modalidad_de_contratacion)                   AS modalidad,
  norm_txt(estado_contrato)                             AS estado,
  codigo_de_categoria_principal                         AS unspsc,
  descripcion_del_proceso                               AS descripcion,
  objeto_del_contrato                                   AS objeto,

  -- fechas
  try_cast(fecha_de_firma AS DATE)                      AS fecha_firma,
  try_cast(fecha_de_inicio_del_contrato AS DATE)        AS fecha_inicio,
  try_cast(fecha_de_fin_del_contrato AS DATE)           AS fecha_fin,

  -- dinero
  try_cast(valor_del_contrato AS DOUBLE)                AS valor,
  -- Valor saneado. 24 contratos vienen publicados con cifras imposibles
  -- (hasta 6e18 COP, mas que el PIB mundial) y entre los dos concentraban
  -- el 98.6% del "total" agregado. No se borran: se aislan, se cuentan
  -- como falla de publicacion y se excluyen de toda suma de dinero.
  -- Techo: 10 billones COP, por encima de cualquier megaobra real del pais.
  CASE WHEN try_cast(valor_del_contrato AS DOUBLE) BETWEEN 0 AND 1e13
       THEN try_cast(valor_del_contrato AS DOUBLE) END  AS valor_plausible,
  try_cast(valor_pagado AS DOUBLE)                      AS valor_pagado,
  try_cast(valor_facturado AS DOUBLE)                   AS valor_facturado,
  try_cast(valor_pendiente_de_ejecucion AS DOUBLE)      AS valor_pend_ejecucion,
  try_cast(valor_de_pago_adelantado AS DOUBLE)          AS valor_anticipo,
  norm_txt(habilita_pago_adelantado)                    AS habilita_anticipo,
  try_cast(dias_adicionados AS DOUBLE)                  AS dias_adicionados,

  -- fuente de los recursos (permite atribuir riesgo por bolsillo)
  try_cast(sistema_general_de_regal_as AS DOUBLE)                                AS rec_regalias,
  try_cast(sistema_general_de_participaciones AS DOUBLE)                         AS rec_sgp,
  try_cast(recursos_propios_alcald_as_gobernaciones_y_resguardos_ind_genas_ AS DOUBLE) AS rec_propios_terr,
  try_cast(presupuesto_general_de_la_nacion_pgn AS DOUBLE)                       AS rec_pgn,
  try_cast(recursos_de_credito AS DOUBLE)                                        AS rec_credito,

  -- PROVEEDOR
  norm_id(documento_proveedor)                          AS doc_proveedor,
  norm_txt(proveedor_adjudicado)                        AS proveedor,
  norm_txt(es_grupo)                                    AS es_grupo,
  norm_txt(es_pyme)                                     AS es_pyme,
  norm_id(identificaci_n_representante_legal)           AS doc_replegal,
  norm_txt(nombre_representante_legal)                  AS replegal,
  norm_txt(domicilio_representante_legal)               AS domicilio_replegal,
  norm_cuenta(n_mero_de_cuenta)                         AS cuenta_key,
  norm_txt(nombre_del_banco)                            AS banco,

  -- PERSONAS DEL LADO DEL ESTADO (el corazon del proyecto)
  norm_id(n_mero_de_documento_ordenador_del_gasto)      AS doc_ordenador,
  norm_txt(nombre_ordenador_del_gasto)                  AS ordenador,
  norm_id(n_mero_de_documento_supervisor)               AS doc_supervisor,
  norm_txt(nombre_supervisor)                           AS supervisor,
  norm_id(n_mero_de_documento_ordenador_de_pago)        AS doc_ord_pago,

  norm_txt(direcci_n_de_ejecuci_n_del_contrato)         AS dir_ejecucion,

  -- periodo de gobierno territorial (alcaldias/gobernaciones)
  CASE
    WHEN try_cast(fecha_de_firma AS DATE) <  DATE '2016-01-01' THEN 'pre-2016'
    WHEN try_cast(fecha_de_firma AS DATE) <= DATE '2019-12-31' THEN '2016-2019'
    WHEN try_cast(fecha_de_firma AS DATE) <= DATE '2023-12-31' THEN '2020-2023'
    WHEN try_cast(fecha_de_firma AS DATE) <= DATE '2027-12-31' THEN '2024-2027'
    ELSE NULL
  END                                                   AS periodo_gobierno,
  year(try_cast(fecha_de_firma AS DATE))                AS anio
FROM read_json_auto('__RAW__/contratos/*.jsonl', format='newline_delimited',
                    maximum_object_size=20000000, union_by_name=true, sample_size=-1);

CREATE OR REPLACE TABLE procesos AS
SELECT
  id_del_proceso,
  referencia_del_proceso,
  norm_id(nit_entidad)                                     AS nit_entidad,
  norm_txt(entidad)                                        AS entidad,
  norm_txt(departamento_entidad)                           AS departamento,
  norm_txt(ciudad_entidad)                                 AS ciudad,
  norm_txt(tipo_de_contrato)                               AS tipo_contrato,
  norm_txt(modalidad_de_contratacion)                      AS modalidad,
  norm_txt(estado_del_procedimiento)                       AS estado_proceso,
  norm_txt(adjudicado)                                     AS adjudicado,
  codigo_principal_de_categoria                            AS unspsc,
  descripci_n_del_procedimiento                            AS descripcion,

  try_cast(precio_base AS DOUBLE)                          AS precio_base,
  try_cast(valor_total_adjudicacion AS DOUBLE)             AS valor_adjudicado,

  -- COMPETENCIA: estos campos son los que habilitan la bandera #1
  try_cast(proveedores_invitados AS BIGINT)                AS n_invitados,
  try_cast(proveedores_que_manifestaron AS BIGINT)         AS n_manifestaron,
  try_cast(respuestas_al_procedimiento AS BIGINT)          AS n_respuestas,
  try_cast(proveedores_unicos_con AS BIGINT)               AS n_oferentes_unicos,
  try_cast(conteo_de_respuestas_a_ofertas AS BIGINT)       AS n_respuestas_ofertas,
  try_cast(visualizaciones_del AS BIGINT)                  AS n_visualizaciones,
  try_cast(numero_de_lotes AS BIGINT)                      AS n_lotes,

  try_cast(fecha_de_publicacion_del AS DATE)               AS fecha_publicacion,
  try_cast(fecha_de_recepcion_de AS DATE)                  AS fecha_cierre_ofertas,
  try_cast(fecha_adjudicacion AS DATE)                     AS fecha_adjudicacion,

  norm_txt(nombre_del_adjudicador)                         AS adjudicador,
  norm_id(nit_del_proveedor_adjudicado)                    AS doc_proveedor,
  norm_txt(nombre_del_proveedor)                           AS proveedor,
  urlproceso.url                                           AS urlproceso,
  nullif(regexp_extract(urlproceso.url, 'CO1\.NTC\.[0-9]+'), '') AS notice_uid
FROM read_json_auto('__RAW__/procesos/*.jsonl', format='newline_delimited',
                    maximum_object_size=20000000, union_by_name=true, sample_size=-1);
