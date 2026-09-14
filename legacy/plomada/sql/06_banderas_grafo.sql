-- =====================================================================
-- 06_banderas_grafo.sql  |  Owner: A/B  |  Rango reservado 04-09
--
-- Banderas que solo existen una vez construido el grafo. Van en CAPA
-- APARTE, no dentro de 02_flags.sql, por una razon estructural: 02 corre
-- antes de 04/05, asi que meter aqui una bandera que dependa de
-- `clusters` crearia una dependencia circular. La capa de contrato y la
-- capa de red se calculan por separado y se unen al final en `riesgo_total`.
--
-- Requiere en orden: build --steps 01 02 03 04 05  ->  grafo.py  ->  este.
-- =====================================================================

CREATE OR REPLACE TABLE pesos_grafo (bandera VARCHAR, peso DOUBLE, grupo VARCHAR, glosa VARCHAR);
INSERT INTO pesos_grafo VALUES
 ('g_interventor_constructor', 3, 'Red', 'El interventor tambien construye obra en la misma entidad'),
 ('g_cluster_vigila_y_construye', 3, 'Red', 'Su grupo economico concentra a la vez la obra y su interventoria'),
 ('g_cluster_multillave', 2, 'Red', 'Unido a otro proveedor por dos o mas llaves que deberian ser unicas'),
 ('g_cluster_grande', 1, 'Red', 'Pertenece a un grupo economico de 10 o mas proveedores');

-- Pares de proveedores unidos por 2+ tipos de llave distintos: cuenta Y
-- representante legal, o cuenta Y domicilio. Mucho mas fuerte que una sola.
CREATE OR REPLACE TABLE proveedor_multillave AS
SELECT doc_a AS doc_proveedor FROM aristas_prov_1x WHERE n_tipos >= 2
UNION
SELECT doc_b FROM aristas_prov_1x WHERE n_tipos >= 2;

CREATE OR REPLACE TABLE banderas_grafo AS
SELECT
  b.id_contrato,
  b.doc_proveedor,
  c.cluster_id,
  c.tamano                                       AS tamano_cluster,

  -- G1: este proveedor de interventoria tambien construye en esta entidad.
  (ic.id_contrato IS NOT NULL)                   AS g_interventor_constructor,

  -- G2: su grupo economico tiene a la vez obras e interventorias. Es el
  -- mecanismo central del fraude en obra publica: el que vigila y el que
  -- construye son la misma red. Se excluyen los grupos que contienen una
  -- entidad publica, porque ahi la concentracion es legal.
  (cp.obra_e_interventoria AND cp.n_proveedores > 1
     AND NOT cp.tiene_entidad_publica)           AS g_cluster_vigila_y_construye,

  -- G3: unido a otro proveedor por dos o mas llaves independientes.
  (mk.doc_proveedor IS NOT NULL)                 AS g_cluster_multillave,

  -- G4: grupo economico grande.
  (c.tamano >= 10)                               AS g_cluster_grande,

  -- evidencia
  cp.n_proveedores                               AS ev_proveedores_cluster,
  cp.n_obra                                      AS ev_obras_cluster,
  cp.n_interventoria                             AS ev_interventorias_cluster,
  cp.valor_total                                 AS ev_valor_cluster
FROM base b
LEFT JOIN clusters c                ON c.doc_proveedor = b.doc_proveedor
LEFT JOIN clusters_perfil cp        ON cp.cluster_id = c.cluster_id
LEFT JOIN interventor_constructor ic ON ic.id_contrato = b.id_contrato
LEFT JOIN proveedor_multillave mk    ON mk.doc_proveedor = b.doc_proveedor;

-- ---------------------------------------------------------------------
-- Riesgo total = capa de contrato (20 banderas) + capa de red (4).
-- Se mantienen los dos puntajes separados a proposito: permite decir
-- "este contrato es atipico por su red" vs "por su tramite", que es una
-- distincion que importa al reportarlo.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW riesgo_total AS
SELECT
  p.*,
  g.cluster_id,
  g.tamano_cluster,
  g.g_interventor_constructor,
  g.g_cluster_vigila_y_construye,
  g.g_cluster_multillave,
  g.g_cluster_grande,
  g.ev_proveedores_cluster,
  g.ev_obras_cluster,
  g.ev_interventorias_cluster,
  ( 3*coalesce(g.g_interventor_constructor::INT, 0)
  + 3*coalesce(g.g_cluster_vigila_y_construye::INT, 0)
  + 2*coalesce(g.g_cluster_multillave::INT, 0)
  + 1*coalesce(g.g_cluster_grande::INT, 0) )            AS puntos_red,
  ( coalesce(g.g_interventor_constructor::INT, 0)
  + coalesce(g.g_cluster_vigila_y_construye::INT, 0) )  AS n_banderas_red_fuertes
FROM puntajes p
LEFT JOIN banderas_grafo g USING (id_contrato);
