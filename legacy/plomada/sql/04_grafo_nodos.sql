-- =====================================================================
-- 04_grafo_nodos.sql  |  Owner: A  |  Rango reservado 04-09 (grafo)
--
-- Los contratos no son filas: son aristas de una red de personas. Este
-- paso construye los nodos, y antes de eso la LISTA NEGRA de llaves,
-- que es lo que impide que el grafo se vuelva basura.
--
-- Por que la lista negra va primero: `domicilio_replegal` esta poblado
-- al 100% pero el 63% es la cadena 'NO DEFINIDO', que por si sola liga
-- 19.403 proveedores. Usada como arista crea UN clique de 19.403 nodos
-- que se traga el grafo entero y hace que la deteccion de comunidades
-- no signifique nada.
--
-- La regla es GENERALIZADA, no caso por caso: cualquier valor de llave
-- que ligue mas de 50 proveedores distintos se descarta, sea el que sea.
-- Asi tambien caen los placeholders que todavia no conocemos.
-- =====================================================================

CREATE OR REPLACE TABLE llaves_basura AS
WITH conteos AS (
  SELECT 'cuenta' AS tipo_llave, cuenta_key AS valor,
         count(DISTINCT doc_proveedor) AS n_proveedores
  FROM base
  WHERE cuenta_key IS NOT NULL AND doc_proveedor IS NOT NULL
  GROUP BY 2
  UNION ALL
  SELECT 'domicilio', domicilio_replegal, count(DISTINCT doc_proveedor)
  FROM base
  WHERE domicilio_replegal IS NOT NULL AND doc_proveedor IS NOT NULL
  GROUP BY 2
  UNION ALL
  SELECT 'replegal', doc_replegal, count(DISTINCT doc_proveedor)
  FROM base
  WHERE doc_replegal IS NOT NULL AND doc_proveedor IS NOT NULL
  GROUP BY 2
)
SELECT tipo_llave, valor, n_proveedores,
       CASE
         -- placeholders explicitos conocidos
         WHEN upper(valor) IN ('NO DEFINIDO','NO APLICA','NO REGISTRA','N/A','NA',
                               'SIN INFORMACION','SIN DEFINIR','NINGUNA','NINGUNO',
                               'POR DEFINIR','0','00','NO TIENE','NO')
           THEN 'placeholder_conocido'
         -- un solo caracter repetido: 000000, XXXXXX, ------
         WHEN length(valor) > 0 AND valor = repeat(substr(valor, 1, 1), length(valor))
           THEN 'caracter_repetido'
         -- regla generalizada: ninguna llave legitima liga tantos proveedores
         ELSE 'liga_demasiados_proveedores'
       END AS razon
FROM conteos
WHERE n_proveedores > 50
   OR upper(valor) IN ('NO DEFINIDO','NO APLICA','NO REGISTRA','N/A','NA',
                       'SIN INFORMACION','SIN DEFINIR','NINGUNA','NINGUNO',
                       'POR DEFINIR','0','00','NO TIENE','NO')
   OR (length(valor) > 0 AND valor = repeat(substr(valor, 1, 1), length(valor)));

-- Vista limpia: la unica fuente de llaves utilizables para aristas.
-- Todo lo de 04-09 debe leer de aqui, nunca de `base` directamente.
CREATE OR REPLACE VIEW llaves_limpias AS
SELECT
  b.id_contrato,
  b.doc_proveedor,
  b.proveedor,
  b.nit_entidad,
  b.valor_plausible,
  b.anio,
  b.tipo_contrato,
  CASE WHEN kc.valor IS NULL THEN b.cuenta_key END          AS cuenta_key,
  CASE WHEN kd.valor IS NULL THEN b.domicilio_replegal END   AS domicilio,
  CASE WHEN kr.valor IS NULL THEN b.doc_replegal END         AS doc_replegal,
  b.replegal,
  b.doc_ordenador, b.ordenador,
  b.doc_supervisor, b.supervisor
FROM base b
LEFT JOIN llaves_basura kc ON kc.tipo_llave = 'cuenta'    AND kc.valor = b.cuenta_key
LEFT JOIN llaves_basura kd ON kd.tipo_llave = 'domicilio' AND kd.valor = b.domicilio_replegal
LEFT JOIN llaves_basura kr ON kr.tipo_llave = 'replegal'  AND kr.valor = b.doc_replegal;

-- ---------------------------------------------------------------------
-- NODOS PERSONA
-- Una cedula es UN nodo, no tres. La misma persona puede ser ordenador
-- del gasto en una entidad y supervisor en otra: eso es precisamente lo
-- que queremos poder ver, y se pierde si se crea un nodo por rol.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE nodos_persona AS
WITH roles AS (
  SELECT doc_ordenador AS doc, ordenador AS nombre, 'ordenador' AS rol,
         valor_plausible AS v, nit_entidad, id_contrato
  FROM llaves_limpias WHERE doc_ordenador IS NOT NULL
  UNION ALL
  SELECT doc_supervisor, supervisor, 'supervisor', valor_plausible, nit_entidad, id_contrato
  FROM llaves_limpias WHERE doc_supervisor IS NOT NULL
  UNION ALL
  SELECT doc_replegal, replegal, 'replegal', valor_plausible, nit_entidad, id_contrato
  FROM llaves_limpias WHERE doc_replegal IS NOT NULL
)
SELECT
  'persona:' || doc                                       AS node_id,
  'persona'                                               AS tipo,
  doc,
  mode(nombre)                                            AS nombre,
  count(DISTINCT id_contrato)                             AS n_contratos,
  sum(v)                                                  AS valor_total,
  count(DISTINCT nit_entidad)                             AS n_entidades,
  bool_or(rol = 'ordenador')                              AS es_ordenador,
  bool_or(rol = 'supervisor')                             AS es_supervisor,
  bool_or(rol = 'replegal')                               AS es_replegal,
  count(DISTINCT rol)                                     AS n_roles
FROM roles
GROUP BY doc;

-- ---------------------------------------------------------------------
-- NODOS PROVEEDOR
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE nodos_proveedor AS
SELECT
  'proveedor:' || l.doc_proveedor                          AS node_id,
  'proveedor'                                              AS tipo,
  l.doc_proveedor                                          AS doc,
  mode(l.proveedor)                                        AS nombre,
  count(*)                                                 AS n_contratos,
  sum(l.valor_plausible)                                   AS valor_total,
  count(DISTINCT l.nit_entidad)                            AS n_entidades,
  count(*) FILTER (WHERE l.tipo_contrato = 'OBRA')          AS n_obra,
  count(*) FILTER (WHERE l.tipo_contrato = 'INTERVENTORIA') AS n_interventoria,
  -- un proveedor que hace obra E interventoria es de interes por si mismo
  (count(*) FILTER (WHERE l.tipo_contrato = 'OBRA') > 0
   AND count(*) FILTER (WHERE l.tipo_contrato = 'INTERVENTORIA') > 0) AS hace_ambos,
  (pp.doc_proveedor IS NOT NULL)                            AS es_entidad_publica,
  min(l.anio)                                               AS primer_anio,
  max(l.anio)                                               AS ultimo_anio
FROM llaves_limpias l
LEFT JOIN proveedores_publicos pp ON pp.doc_proveedor = l.doc_proveedor
WHERE l.doc_proveedor IS NOT NULL
GROUP BY l.doc_proveedor, pp.doc_proveedor;

-- ---------------------------------------------------------------------
-- NODOS ENTIDAD
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE nodos_entidad AS
SELECT
  'entidad:' || nit_entidad     AS node_id,
  'entidad'                     AS tipo,
  nit_entidad                   AS doc,
  mode(entidad)                 AS nombre,
  count(*)                      AS n_contratos,
  sum(valor_plausible)          AS valor_total,
  mode(departamento)            AS departamento,
  mode(ciudad)                  AS ciudad,
  mode(orden)                   AS orden
FROM base
WHERE nit_entidad IS NOT NULL
GROUP BY nit_entidad;

CREATE OR REPLACE VIEW nodos AS
SELECT node_id, tipo, doc, nombre, n_contratos, valor_total FROM nodos_persona
UNION ALL
SELECT node_id, tipo, doc, nombre, n_contratos, valor_total FROM nodos_proveedor
UNION ALL
SELECT node_id, tipo, doc, nombre, n_contratos, valor_total FROM nodos_entidad;
