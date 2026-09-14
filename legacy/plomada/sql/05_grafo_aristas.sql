-- =====================================================================
-- 05_grafo_aristas.sql  |  Owner: A  |  Rango reservado 04-09
--
-- Aristas del grafo. Todo sale de `llaves_limpias` (definida en 04), que
-- ya tiene aplicada la lista negra. NUNCA leer `base` directamente aqui:
-- si lo haces, 'NO DEFINIDO' vuelve a entrar y el grafo se arruina.
--
-- Dos familias:
--   * proveedor -- proveedor : co-ocurrencia en una llave que deberia ser
--     unica. Es lo que forma los clusteres.
--   * persona -> proveedor   : quien le dio la plata a quien.
-- =====================================================================

-- ---------------------------------------------------------------------
-- PROVEEDOR -- PROVEEDOR
-- Se deduplica con doc_a < doc_b para no tener la arista dos veces.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE aristas_prov AS
WITH por_cuenta AS (
  SELECT DISTINCT
    least(a.doc_proveedor, b.doc_proveedor)    AS doc_a,
    greatest(a.doc_proveedor, b.doc_proveedor) AS doc_b,
    'comparte_cuenta'                          AS tipo,
    3                                          AS peso,
    a.cuenta_key                               AS llave
  FROM llaves_limpias a
  JOIN llaves_limpias b
    ON a.cuenta_key = b.cuenta_key
   AND a.doc_proveedor < b.doc_proveedor
  WHERE a.cuenta_key IS NOT NULL
),
por_replegal AS (
  SELECT DISTINCT
    least(a.doc_proveedor, b.doc_proveedor),
    greatest(a.doc_proveedor, b.doc_proveedor),
    'comparte_replegal', 3, a.doc_replegal
  FROM llaves_limpias a
  JOIN llaves_limpias b
    ON a.doc_replegal = b.doc_replegal
   AND a.doc_proveedor < b.doc_proveedor
  WHERE a.doc_replegal IS NOT NULL
),
por_domicilio AS (
  SELECT DISTINCT
    least(a.doc_proveedor, b.doc_proveedor),
    greatest(a.doc_proveedor, b.doc_proveedor),
    'comparte_domicilio', 2, a.domicilio
  FROM llaves_limpias a
  JOIN llaves_limpias b
    ON a.domicilio = b.domicilio
   AND a.doc_proveedor < b.doc_proveedor
  WHERE a.domicilio IS NOT NULL
)
SELECT * FROM por_cuenta
UNION ALL SELECT * FROM por_replegal
UNION ALL SELECT * FROM por_domicilio;

-- Vista colapsada: una arista por par, con el peso acumulado. Dos empresas
-- unidas por cuenta Y por representante legal pesan mas que por una sola.
CREATE OR REPLACE TABLE aristas_prov_1x AS
SELECT
  doc_a, doc_b,
  sum(peso)                    AS peso,
  count(DISTINCT tipo)         AS n_tipos,
  list(DISTINCT tipo)          AS tipos
FROM aristas_prov
GROUP BY doc_a, doc_b;

-- ---------------------------------------------------------------------
-- PERSONA -> PROVEEDOR
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE aristas_persona AS
SELECT 'persona:' || doc_ordenador AS src, 'proveedor:' || doc_proveedor AS dst,
       'adjudica' AS tipo, count(*) AS n_contratos, sum(valor_plausible) AS valor
FROM llaves_limpias
WHERE doc_ordenador IS NOT NULL AND doc_proveedor IS NOT NULL
GROUP BY 1, 2
UNION ALL
SELECT 'persona:' || doc_supervisor, 'proveedor:' || doc_proveedor,
       'supervisa', count(*), sum(valor_plausible)
FROM llaves_limpias
WHERE doc_supervisor IS NOT NULL AND doc_proveedor IS NOT NULL
GROUP BY 1, 2
UNION ALL
SELECT 'persona:' || doc_replegal, 'proveedor:' || doc_proveedor,
       'es_replegal', count(*), sum(valor_plausible)
FROM llaves_limpias
WHERE doc_replegal IS NOT NULL AND doc_proveedor IS NOT NULL
GROUP BY 1, 2;

-- ---------------------------------------------------------------------
-- SEGREGACION DE FUNCIONES
-- 4.478 contratos (10,9% de los que traen ambos datos, $6,26 billones)
-- tienen al MISMO funcionario como ordenador del gasto y como supervisor.
-- Es decir: la misma persona autoriza el pago y certifica que la obra se
-- hizo. No es un indicio indirecto, es una falla de control interno
-- visible en el propio dato que publica la entidad.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE autosupervision AS
SELECT
  id_contrato, nit_entidad, doc_ordenador AS doc_funcionario,
  ordenador AS funcionario, doc_proveedor, valor_plausible
FROM llaves_limpias
WHERE doc_ordenador IS NOT NULL
  AND doc_ordenador = doc_supervisor;

-- ---------------------------------------------------------------------
-- INTERVENTOR QUE TAMBIEN CONSTRUYE EN LA MISMA ENTIDAD
-- 517 interventorias. No prueba autovigilancia en el mismo contrato --
-- eso lo cierra A4 con el emparejamiento obra<->interventoria -- pero es
-- exactamente el universo donde hay que buscarla.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE interventor_constructor AS
SELECT DISTINCT
  i.id_contrato, i.nit_entidad, i.doc_proveedor, i.proveedor, i.valor_plausible
FROM llaves_limpias i
WHERE i.tipo_contrato = 'INTERVENTORIA'
  AND i.doc_proveedor IS NOT NULL
  AND EXISTS (
    SELECT 1 FROM llaves_limpias o
    WHERE o.tipo_contrato = 'OBRA'
      AND o.nit_entidad = i.nit_entidad
      AND o.doc_proveedor = i.doc_proveedor
  );

-- ---------------------------------------------------------------------
-- Resumen para la prueba de humo de A3.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW resumen_aristas AS
SELECT tipo, count(*) AS n_aristas, count(DISTINCT llave) AS n_llaves
FROM aristas_prov GROUP BY tipo
UNION ALL
SELECT 'total_pares_unicos', count(*), NULL FROM aristas_prov_1x;
