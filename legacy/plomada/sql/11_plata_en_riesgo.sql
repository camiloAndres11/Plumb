-- =====================================================================
-- 11_plata_en_riesgo.sql  |  Owner: C  |  Rango reservado 10-19
--
-- LA CIFRA EN PESOS. Requiere los pasos 01-06 (usa `riesgo_total`).
--
-- Que mide y que NO mide, porque esta distincion es la que sostiene el
-- proyecto legalmente:
--
--   MIDE:    cuanta plata publica paso por contratos que presentan
--            indicios verificables. Es un hecho aritmetico.
--   NO MIDE: cuanta plata se robaron. Eso requiere una investigacion
--            judicial y este proyecto no la hace ni la reemplaza.
--
-- El titular defendible es "$31 billones de obra publica se adjudicaron
-- sin competencia", no "se robaron $31 billones". La primera frase es
-- cierta y verificable contra el dato oficial; la segunda es una
-- acusacion sin sustento.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Plata por cada indicio. La suma de las filas NO es el total del
-- universo: un contrato puede tener varios indicios a la vez y se cuenta
-- en cada uno. Por eso se reporta cada linea contra el total del
-- universo, y nunca se suman entre si.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE plata_por_indicio AS
SELECT * FROM (
  SELECT 'Sin competencia: un solo oferente' AS indicio, 'Competencia' AS grupo,
         count(*) AS n_contratos, sum(valor_plausible) AS valor FROM riesgo_total WHERE f_proponente_unico
  UNION ALL SELECT 'Ventana de ofertas mas corta de su modalidad','Competencia',count(*),sum(valor_plausible) FROM riesgo_total WHERE f_ventana_corta
  UNION ALL SELECT 'Adjudicado al 99,5-100% del presupuesto oficial','Competencia',count(*),sum(valor_plausible) FROM riesgo_total WHERE f_ratio_calcado
  UNION ALL SELECT 'Obra adjudicada por contratacion directa','Competencia',count(*),sum(valor_plausible) FROM riesgo_total WHERE f_obra_directa
  UNION ALL SELECT 'Cinco o mas invitados, un solo oferente','Competencia',count(*),sum(valor_plausible) FROM riesgo_total WHERE f_invitacion_vacia
  UNION ALL SELECT 'Grupo economico que vigila y construye','Red',count(*),sum(valor_plausible) FROM riesgo_total WHERE g_cluster_vigila_y_construye
  UNION ALL SELECT 'Interventor que tambien construye en la entidad','Red',count(*),sum(valor_plausible) FROM riesgo_total WHERE g_interventor_constructor
  UNION ALL SELECT 'Mismo funcionario ordena el gasto y supervisa','Red',count(*),sum(valor_plausible) FROM riesgo_total WHERE f_ordenador_es_supervisor
  UNION ALL SELECT 'Proveedores distintos con la misma cuenta bancaria','Red',count(*),sum(valor_plausible) FROM riesgo_total WHERE f_cuenta_compartida
  UNION ALL SELECT 'Representante legal en tres o mas empresas','Red',count(*),sum(valor_plausible) FROM riesgo_total WHERE f_replegal_multiempresa
  UNION ALL SELECT 'Ordenador concentra mas del 50% en un proveedor','Red',count(*),sum(valor_plausible) FROM riesgo_total WHERE f_ordenador_concentrado
  UNION ALL SELECT 'Fraccionamiento: contratos hermanos en 30 dias','Umbrales',count(*),sum(valor_plausible) FROM riesgo_total WHERE f_fraccionamiento
  UNION ALL SELECT 'Pegado al techo de la minima cuantia','Umbrales',count(*),sum(valor_plausible) FROM riesgo_total WHERE f_al_tope_minima
  UNION ALL SELECT 'Declara no tener anticipo pero lo giro','Dinero',count(*),sum(valor_plausible) FROM riesgo_total WHERE f_anticipo_no_declarado
  UNION ALL SELECT 'Agota el anticipo maximo legal del 50%','Dinero',count(*),sum(valor_plausible) FROM riesgo_total WHERE f_anticipo_al_tope
  UNION ALL SELECT 'Se pago mas del valor del contrato','Dinero',count(*),sum(valor_plausible) FROM riesgo_total WHERE f_sobrepago
  UNION ALL SELECT 'Plazo adicionado en mas del 50%','Ejecucion',count(*),sum(valor_plausible) FROM riesgo_total WHERE f_prorroga_mayor
  UNION ALL SELECT 'Firmado al cierre del periodo de gobierno','Ejecucion',count(*),sum(valor_plausible) FROM riesgo_total WHERE f_cierre_de_periodo
) x
ORDER BY valor DESC;

-- ---------------------------------------------------------------------
-- Titulares: las cifras que se citan textualmente. Cada una es una resta
-- o una division sobre el dato oficial, nada mas.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE titulares AS
SELECT 'Obra publica analizada'          AS concepto, count(*) AS n_contratos, sum(valor_plausible) AS valor FROM riesgo_total
UNION ALL SELECT 'Adjudicado sin competencia real', count(*), sum(valor_plausible) FROM riesgo_total WHERE f_proponente_unico
-- NOTA: 'sin competencia' es mayor que 'atipico' y no es contradiccion.
-- Un contrato con un solo oferente y nada mas suma 2 puntos, y el umbral
-- de atipico son 6 puntos o una bandera fuerte. Son dos preguntas
-- distintas: cuanta plata se adjudico sin competencia, vs cuantos
-- contratos acumulan indicios suficientes para priorizar investigacion.
UNION ALL SELECT 'Clasificado atipico (indicio fuerte o 6+ puntos)', count(*), sum(valor_plausible) FROM riesgo_total WHERE n_banderas_fuertes >= 1 OR puntos_crudos >= 6
UNION ALL SELECT 'Con indicio fuerte de red', count(*), sum(valor_plausible) FROM riesgo_total WHERE n_banderas_red_fuertes >= 1
UNION ALL SELECT 'Con indicios de tramite Y de red', count(*), sum(valor_plausible) FROM riesgo_total
  WHERE (n_banderas_fuertes >= 1 OR puntos_crudos >= 6) AND n_banderas_red_fuertes >= 1
UNION ALL SELECT 'Publicado con valor imposible', count(*), 0 FROM riesgo_total WHERE f_valor_implausible;

-- ---------------------------------------------------------------------
-- Por fuente de recursos. Aqui esta la historia mas fuerte: no es lo
-- mismo un indicio sobre recursos propios de una alcaldia grande que
-- sobre regalias en un municipio chico.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE plata_por_fuente AS
SELECT * FROM (
  SELECT 'Regalias' AS fuente, sum(rec_regalias) AS total,
         sum(CASE WHEN n_banderas_fuertes >= 1 OR puntos_crudos >= 6 THEN rec_regalias ELSE 0 END) AS en_riesgo
  FROM riesgo_total WHERE rec_regalias > 0
  UNION ALL SELECT 'Sistema General de Participaciones', sum(rec_sgp),
         sum(CASE WHEN n_banderas_fuertes >= 1 OR puntos_crudos >= 6 THEN rec_sgp ELSE 0 END)
  FROM riesgo_total WHERE rec_sgp > 0
  UNION ALL SELECT 'Recursos propios territoriales', sum(rec_propios_terr),
         sum(CASE WHEN n_banderas_fuertes >= 1 OR puntos_crudos >= 6 THEN rec_propios_terr ELSE 0 END)
  FROM riesgo_total WHERE rec_propios_terr > 0
) x
ORDER BY total DESC;

-- ---------------------------------------------------------------------
-- Por tipo de obra (segmentacion, no comparacion de precios).
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE plata_por_tipo_obra AS
SELECT
  coalesce(t.tipo_obra, 'SIN CLASIFICAR')                        AS tipo_obra,
  count(*)                                                       AS n_contratos,
  sum(r.valor_plausible)                                         AS total,
  count(*) FILTER (WHERE r.n_banderas_fuertes >= 1 OR r.puntos_crudos >= 6) AS n_riesgo,
  sum(CASE WHEN r.n_banderas_fuertes >= 1 OR r.puntos_crudos >= 6
           THEN r.valor_plausible ELSE 0 END)                     AS en_riesgo,
  sum(CASE WHEN r.f_proponente_unico THEN r.valor_plausible ELSE 0 END) AS sin_competencia
FROM riesgo_total r
LEFT JOIN tipo_obra t USING (id_contrato)
GROUP BY 1
ORDER BY total DESC;

-- ---------------------------------------------------------------------
-- Por departamento, con la plata. Complementa ranking_departamentos, que
-- solo trae tasas.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE plata_por_departamento AS
SELECT
  departamento,
  count(*)                                                       AS n_contratos,
  sum(valor_plausible)                                           AS total,
  sum(CASE WHEN f_proponente_unico THEN valor_plausible ELSE 0 END) AS sin_competencia,
  sum(CASE WHEN n_banderas_fuertes >= 1 OR puntos_crudos >= 6
           THEN valor_plausible ELSE 0 END)                       AS en_riesgo,
  sum(CASE WHEN n_banderas_red_fuertes >= 1 THEN valor_plausible ELSE 0 END) AS riesgo_red,
  sum(coalesce(rec_regalias, 0))                                  AS regalias
FROM riesgo_total
WHERE departamento IS NOT NULL
GROUP BY 1
ORDER BY total DESC;
