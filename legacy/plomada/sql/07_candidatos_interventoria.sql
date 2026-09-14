-- =====================================================================
-- 07_candidatos_interventoria.sql  |  Owner: A  |  Rango reservado 04-09
--
-- Prepara los insumos para el emparejamiento obra <-> interventoria por
-- CONTRATO (no por proveedor: eso ya lo cubre interventor_constructor en
-- 05_grafo_aristas.sql). Es "A4": banderas_grafo.sql ya dice que la
-- autovigilancia en el MISMO contrato "la cierra A4 con el emparejamiento
-- obra<->interventoria", y grafo.py imprime los clusters obra+interventoria
-- como leads para esto.
--
-- Solo depende de `base` (no de clusters/clusters_perfil), asi que no
-- importa el orden frente a 04/05/06 dentro de build.py --all.
--
-- El cruce en si (similitud de texto) NO va aqui: TF-IDF/cosine no es
-- expresable en SQL de forma confiable (ver pipeline/emparejamiento_
-- interventoria.py). Este paso solo deja listas las dos tablas de insumo,
-- sin cross-join -- una entidad tiene hasta 3.749 obras, y acotar esa
-- combinatoria es mas simple en Python (agrupando por nit_entidad) que en
-- SQL.
-- =====================================================================

CREATE OR REPLACE TABLE obras_para_emparejar AS
SELECT
  id_contrato,
  nit_entidad,
  entidad,
  fecha_firma,
  valor_plausible,
  objeto
FROM base
WHERE tipo_contrato = 'OBRA'
  AND nit_entidad IS NOT NULL
  AND objeto IS NOT NULL
  AND upper(trim(objeto)) NOT IN ('NO DEFINIDO', 'SIN DESCRIPCION')
  AND length(objeto) > 15;

-- ---------------------------------------------------------------------
-- Algunas interventorias citan CASI LITERAL el objeto de la obra que
-- vigilan: "...AL CONTRATO DE OBRA CUYO OBJETO ES <texto>". Se extrae
-- ese texto cuando existe (~16% de las interventorias, medido). Cuando
-- no hay cita, `citado` queda NULL y el emparejamiento usa el objeto
-- completo de la interventoria (senal mas debil, ver pipeline/
-- emparejamiento_interventoria.py).
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE interventorias_para_emparejar AS
SELECT
  id_contrato,
  nit_entidad,
  entidad,
  fecha_firma,
  valor_plausible,
  objeto,
  nullif(
    regexp_extract(upper(objeto), '(?:CUYO OBJETO ES|OBJETO ES)[:.]?\s*(.*)', 1),
    ''
  )                                                             AS citado,
  (length(regexp_extract(upper(objeto), '(?:CUYO OBJETO ES|OBJETO ES)[:.]?\s*(.*)', 1)) > 15)
                                                                 AS tiene_cita
FROM base
WHERE tipo_contrato = 'INTERVENTORIA'
  AND nit_entidad IS NOT NULL
  AND objeto IS NOT NULL
  AND upper(trim(objeto)) NOT IN ('NO DEFINIDO', 'SIN DESCRIPCION')
  AND length(objeto) > 15;
