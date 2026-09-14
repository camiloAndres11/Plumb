-- =====================================================================
-- 10_tipo_obra.sql  |  Owner: C  |  Rango reservado 10-19 (valores)
--
-- Clasificacion del tipo de obra a partir del texto de la descripcion.
--
-- PARA QUE SIRVE: segmentar las cifras de riesgo ("$X billones sin
-- competencia en vias"). Cubre el 49,3% de las obras.
--
-- PARA QUE NO SIRVE, Y ES IMPORTANTE: NO sirve para inferir sobreprecio
-- comparando contra la mediana de su tipo. Se midio la dispersion dentro
-- de cada tipo y el percentil 95 es 59 veces la mediana en vias y 39 en
-- educativo. Comparar totales dentro de un tipo mide TAMANO DE PROYECTO,
-- no sobreprecio: un indicador "N veces la mediana" solo marcaria las
-- obras grandes. Por eso ese indicador no existe en este archivo.
--
-- El sobrecosto por unidad fisica (costo por km, por m2, por aula) NO es
-- calculable con datos abiertos: solo el 0,9% de las 52.355 descripciones
-- contiene una cantidad con unidad (258 mencionan km, 21 mencionan m2).
-- La unica via a precios unitarios reales es parsear los APU de los
-- pliegos en PDF, que es el pendiente C5 y es caro.
-- =====================================================================

CREATE OR REPLACE TABLE tipo_obra AS
SELECT
  id_contrato,
  CASE
    -- El orden importa: se evalua de mas especifico a mas general.
    WHEN regexp_matches(descripcion, '(?i)(acueducto|alcantarillad|ptap|ptar|red de agua|pozo profundo|saneamiento basico)')
      THEN 'AGUA Y SANEAMIENTO'
    WHEN regexp_matches(descripcion, '(?i)(colegio|escuela|instituci[oó]n educativa|sede educativa|\baula|restaurante escolar)')
      THEN 'EDUCATIVO'
    WHEN regexp_matches(descripcion, '(?i)(hospital|centro de salud|puesto de salud|\bE\.?S\.?E\b|unidad de salud)')
      THEN 'SALUD'
    WHEN regexp_matches(descripcion, '(?i)(polideportivo|cancha|escenario deportivo|coliseo|parque|gimnasio)')
      THEN 'DEPORTIVO Y PARQUES'
    WHEN regexp_matches(descripcion, '(?i)(vivienda|urbanizaci[oó]n|\bVIS\b|mejoramiento de casa)')
      THEN 'VIVIENDA'
    WHEN regexp_matches(descripcion, '(?i)(v[ií]a|pavimento|placa huella|carretera|calzada|anillo vial|puente|box culvert|and[eé]n|sardinel)')
      THEN 'VIAS Y TRANSPORTE'
    WHEN regexp_matches(descripcion, '(?i)(edificio|sede administrativa|palacio municipal|casa de la cultura|alcald[ií]a|biblioteca)')
      THEN 'EDIFICACION PUBLICA'
    WHEN regexp_matches(descripcion, '(?i)(alumbrado|red el[eé]ctrica|electrificaci[oó]n|subestaci[oó]n)')
      THEN 'ENERGIA'
    ELSE NULL
  END AS tipo_obra,
  -- Cantidad fisica cuando por casualidad esta declarada. Se guarda por
  -- completitud, pero con 0,9% de cobertura NO se agrega ni se promedia.
  CASE
    WHEN regexp_matches(descripcion, '(?i)\d+[.,]?\d*\s*(km|kil[oó]metro)') THEN 'km'
    WHEN regexp_matches(descripcion, '(?i)\d+[.,]?\d*\s*(m2|m²|metros? cuadrados?)') THEN 'm2'
    WHEN regexp_matches(descripcion, '(?i)\d+[.,]?\d*\s*(ml|metros? lineales?)') THEN 'ml'
    WHEN regexp_matches(descripcion, '(?i)\d+[.,]?\d*\s*(m3|m³|metros? c[uú]bicos?)') THEN 'm3'
    WHEN regexp_matches(descripcion, '(?i)\d+\s*(aulas?|salones?)') THEN 'aulas'
    WHEN regexp_matches(descripcion, '(?i)\d+\s*(viviendas?|soluciones? de vivienda)') THEN 'viviendas'
    ELSE NULL
  END AS unidad_declarada
FROM base
WHERE descripcion IS NOT NULL;
