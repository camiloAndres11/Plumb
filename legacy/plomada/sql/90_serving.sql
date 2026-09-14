-- =====================================================================
-- 90_serving.sql : vistas de serving para el API publica (api/).
--
-- Rango 90-99, reservado desde el primer commit para esto (ver el
-- contrato de datos en pipeline/build.py). Todo lo que sale por HTTP
-- sale de una tabla `api_*` construida aqui, nunca de una tabla interna.
-- Tres razones:
--
--   1. PRIVACIDAD. `cuenta_key` (la cuenta bancaria) es una llave de
--      union interna y JAMAS se publica. La puerta de calidad
--      test_el_snapshot_publico_no_lleva_cuentas recorre exactamente las
--      tablas con prefijo `api_`: mientras no existiera ninguna, ese
--      test no verificaba nada. Ahora cubre todo lo publicable.
--   2. CONTRATO ESTABLE. Las columnas se enumeran a mano, no `SELECT *`.
--      Agregar una columna en 02_flags.sql no debe cambiar en silencio
--      la respuesta de un endpoint publico.
--   3. COSTO. Las agregaciones (por entidad, por proveedor) se calculan
--      una vez aqui, no en cada request del API.
--
-- Requiere en orden: build 01 02 03 04 05 -> grafo.py -> build 06 10.
-- `pipeline/build.py --all` ya lo hace.
-- Las alertas pre-adjudicacion viven en 91_serving_alertas.sql, porque
-- dependen de un snapshot fechado que solo pipeline/alertas.py conoce.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Glosario de banderas. Es lo que hace auditable el puntaje: cualquiera
-- puede leer el peso y discutirlo. `evidencia` nombra las columnas ev_*
-- que sustentan cada bandera, para que /v1/contratos/{id} pueda armar
-- "bandera + peso + glosa + numero que la disparo" sin hardcodear el
-- mapeo en Python.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE api_banderas AS
SELECT bandera, peso, grupo, glosa, 'contrato' AS capa,
       -- La evidencia no siempre es una columna ev_*: para media docena de
       -- banderas el numero que las dispara ya esta en el propio contrato
       -- (n_oferentes_unicos = 1, valor vs precio_base...). Se listan igual,
       -- porque el compromiso publico es "sin evidencia no se publica" y una
       -- bandera que sale con la evidencia vacia lo incumple aunque el dato
       -- este tres campos mas abajo en la misma respuesta.
       CASE bandera
         WHEN 'f_proponente_unico'        THEN 'n_oferentes_unicos,n_invitados'
         WHEN 'f_obra_directa'            THEN 'tipo_contrato,modalidad'
         WHEN 'f_ratio_calcado'           THEN 'valor,precio_base,n_oferentes_unicos'
         WHEN 'f_invitacion_vacia'        THEN 'n_invitados,n_oferentes_unicos'
         WHEN 'f_ventana_corta'           THEN 'dias_ventana,ev_ventana_mediana_modalidad'
         WHEN 'f_cuenta_compartida'       THEN 'ev_proveedores_por_cuenta,ev_tipo_red_cuenta'
         WHEN 'f_cuenta_consorcios'       THEN 'ev_proveedores_por_cuenta,ev_tipo_red_cuenta'
         WHEN 'f_ordenador_es_supervisor' THEN 'doc_ordenador,doc_supervisor,ev_tasa_autosupervision_entidad'
         WHEN 'f_ordenador_concentrado'   THEN 'ev_share_top1_ordenador,ev_hhi_ordenador'
         WHEN 'f_ordenador_itinerante'    THEN 'ev_entidades_ordenador'
         WHEN 'f_supervisor_sobrecargado' THEN 'ev_contratos_supervisor'
         WHEN 'f_replegal_multiempresa'   THEN 'ev_empresas_por_replegal'
         WHEN 'f_sobrepago'               THEN 'valor,valor_pagado,valor_pend_ejecucion'
         WHEN 'f_anticipo_no_declarado'   THEN 'valor_anticipo'
         WHEN 'f_anticipo_al_tope'        THEN 'valor_anticipo,valor'
         WHEN 'f_prorroga_mayor'          THEN 'dias_originales,dias_adicionados'
         WHEN 'f_cierre_de_periodo'       THEN 'fecha_firma,periodo_gobierno'
         WHEN 'f_fraccionamiento'         THEN 'ev_hermanos_30d'
         WHEN 'f_al_tope_minima'          THEN 'valor,ev_tope_minima_entidad'
         WHEN 'f_sin_proceso'             THEN 'precio_base'
         WHEN 'f_valor_implausible'       THEN 'valor,valor_plausible'
         -- f_datos_faltantes se queda sin evidencia a proposito: lo que la
         -- dispara es la AUSENCIA de campos, y esos campos ya salen nulos en
         -- la respuesta. Apuntar a ellos seria evidencia vacia por partida doble.
       END AS evidencia
FROM pesos
UNION ALL
SELECT bandera, peso, grupo, glosa, 'red' AS capa,
       CASE bandera
         WHEN 'g_interventor_constructor'    THEN 'tipo_contrato,doc_proveedor,nit_entidad'
         WHEN 'g_cluster_vigila_y_construye' THEN 'cluster_id,ev_proveedores_cluster,ev_obras_cluster,ev_interventorias_cluster'
         WHEN 'g_cluster_multillave'         THEN 'cluster_id,ev_proveedores_cluster'
         WHEN 'g_cluster_grande'             THEN 'cluster_id,tamano_cluster,ev_proveedores_cluster'
       END AS evidencia
FROM pesos_grafo;

-- ---------------------------------------------------------------------
-- CONTRATOS. La tabla central del API: el universo completo con las 26
-- banderas, su evidencia y el puntaje de las dos capas (tramite y red).
--
-- `es_atipico` se materializa como COLUMNA. Hasta ahora solo existia en
-- la vista `atipicos`, asi que cada consumidor tenia que re-derivar
-- (n_banderas_fuertes >= 1 OR puntos_crudos >= 6) a mano -- y el
-- servidor MCP lo hacia, duplicando el umbral. El umbral vive en un
-- solo sitio: aqui.
--
-- NO lleva `cuenta_key` ni `banco`. Si lleva las cedulas de ordenador y
-- supervisor y los nombres: son campos del dataset oficial publico del
-- SECOP II y son justamente los que permiten seguir a un funcionario
-- entre entidades, que es el aporte del proyecto. La cuenta bancaria es
-- la unica excepcion y no se publica en ninguna forma.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE api_contratos AS
SELECT
  -- identificacion
  r.id_contrato,
  r.urlproceso,
  r.nit_entidad,
  r.entidad,
  r.departamento,
  r.ciudad,
  r.orden,
  r.tipo_contrato,
  r.modalidad,
  r.estado,
  r.unspsc,
  t.tipo_obra,
  r.descripcion,
  r.dir_ejecucion,
  r.fecha_firma,
  r.anio,
  r.periodo_gobierno,
  -- dinero (valor_plausible es NULL en los 24 contratos con valor
  -- imposible; es la columna que hay que sumar, nunca `valor`)
  r.valor,
  r.valor_plausible,
  r.valor_pagado,
  r.valor_pend_ejecucion,
  r.valor_anticipo,
  r.precio_base,
  -- competencia
  r.n_oferentes_unicos,
  r.n_invitados,
  r.dias_ventana,
  r.dias_originales,
  r.dias_adicionados,
  -- partes
  r.doc_proveedor,
  r.proveedor,
  r.doc_ordenador,
  r.ordenador,
  r.doc_supervisor,
  r.supervisor,
  r.doc_replegal,
  -- fuente de los recursos
  r.rec_regalias,
  r.rec_sgp,
  r.rec_propios_terr,
  -- puntajes: las dos capas se mantienen separadas a proposito
  r.puntos_crudos,
  r.score,
  r.n_banderas_fuertes,
  r.puntos_red,
  r.n_banderas_red_fuertes,
  (r.n_banderas_fuertes >= 1 OR r.puntos_crudos >= 6)   AS es_atipico,
  r.cluster_id,
  r.tamano_cluster,
  -- banderas de contrato (22)
  r.f_proponente_unico, r.f_obra_directa, r.f_ventana_corta, r.f_ratio_calcado,
  r.f_invitacion_vacia, r.f_cuenta_compartida, r.f_cuenta_consorcios,
  r.f_replegal_multiempresa, r.f_ordenador_concentrado, r.f_supervisor_sobrecargado,
  r.f_ordenador_itinerante, r.f_ordenador_es_supervisor, r.f_sobrepago,
  r.f_anticipo_no_declarado, r.f_anticipo_al_tope, r.f_prorroga_mayor,
  r.f_cierre_de_periodo, r.f_al_tope_minima, r.f_fraccionamiento,
  r.f_datos_faltantes, r.f_sin_proceso, r.f_valor_implausible,
  -- banderas de red (4)
  r.g_interventor_constructor, r.g_cluster_vigila_y_construye,
  r.g_cluster_multillave, r.g_cluster_grande,
  -- evidencia numerica: sin esto no se publica una bandera
  r.ev_share_top1_ordenador, r.ev_hhi_ordenador, r.ev_contratos_supervisor,
  r.ev_entidades_ordenador, r.ev_proveedores_por_cuenta, r.ev_tipo_red_cuenta,
  r.ev_empresas_por_replegal, r.ev_hermanos_30d, r.ev_ventana_mediana_modalidad,
  r.ev_tope_minima_entidad, r.ev_tasa_autosupervision_entidad,
  r.ev_proveedores_cluster, r.ev_obras_cluster, r.ev_interventorias_cluster
FROM riesgo_total r
LEFT JOIN tipo_obra t USING (id_contrato);

-- ---------------------------------------------------------------------
-- ENTIDADES CONTRATANTES. Precalculado: la tool `perfil_entidad` del MCP
-- hacia este GROUP BY en cada llamada, con any_value() (que ademas exige
-- Postgres >=16). Aqui se hace una vez y el API solo filtra.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE api_entidades AS
SELECT
  nit_entidad,
  mode(entidad)                              AS entidad,
  mode(departamento)                         AS departamento,
  mode(ciudad)                               AS ciudad,
  mode(orden)                                AS orden,
  count(*)                                   AS n_contratos,
  sum(valor_plausible)                       AS valor_total,
  count(*) FILTER (WHERE es_atipico)         AS n_atipicos,
  sum(CASE WHEN es_atipico THEN valor_plausible ELSE 0 END) AS valor_atipico,
  count(*) FILTER (WHERE es_atipico)::DOUBLE / count(*)     AS tasa_atipicos,
  count(*) FILTER (WHERE n_banderas_red_fuertes >= 1)       AS n_riesgo_red,
  count(DISTINCT doc_proveedor)              AS n_proveedores,
  min(anio)                                  AS primer_anio,
  max(anio)                                  AS ultimo_anio
FROM api_contratos
WHERE nit_entidad IS NOT NULL
GROUP BY nit_entidad;

-- ---------------------------------------------------------------------
-- PROVEEDORES. nodos_proveedor + el cluster al que pertenece, para que
-- /v1/proveedores/{doc} pueda saltar directo a su grupo economico.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE api_proveedores AS
SELECT
  p.doc,
  p.nombre,
  p.n_contratos,
  p.valor_total,
  p.n_entidades,
  p.n_obra,
  p.n_interventoria,
  p.hace_ambos,
  p.es_entidad_publica,
  p.primer_anio,
  p.ultimo_anio,
  c.cluster_id,
  c.tamano                                   AS tamano_cluster
FROM nodos_proveedor p
LEFT JOIN clusters c ON c.doc_proveedor = p.doc;

-- ---------------------------------------------------------------------
-- RED. red.json es un blob anidado (cluster -> nodos -> aristas) porque
-- el tablero lo carga entero de una vez. El API lo sirve normalizado en
-- tres tablas, para poder pedir UN cluster sin bajar los 40.
-- Se publican todos los clusters con mas de un proveedor, no solo los 40
-- del tablero: la API no tiene por que recortar como recorta una vista.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE api_clusters AS
SELECT
  cp.cluster_id,
  cp.n_proveedores,
  cp.n_contratos,
  cp.valor_total,
  cp.n_obra,
  cp.n_interventoria,
  cp.obra_e_interventoria                    AS vigila_y_construye,
  cp.tiene_entidad_publica
FROM clusters_perfil cp
WHERE cp.n_proveedores > 1;

CREATE OR REPLACE TABLE api_cluster_nodos AS
SELECT
  c.cluster_id,
  p.doc,
  p.nombre,
  p.n_obra,
  p.n_interventoria,
  p.n_contratos,
  coalesce(p.valor_total, 0)                 AS valor_total,
  p.n_entidades,
  p.es_entidad_publica
FROM clusters c
JOIN nodos_proveedor p ON p.doc = c.doc_proveedor
WHERE c.cluster_id IN (SELECT cluster_id FROM api_clusters);

-- Una arista pertenece a un cluster solo si sus DOS extremos estan en el
-- mismo cluster (misma condicion que usa export_web.py al armar red.json).
CREATE OR REPLACE TABLE api_cluster_aristas AS
SELECT
  ca.cluster_id,
  a.doc_a,
  a.doc_b,
  a.peso,
  a.n_tipos,
  array_to_string(a.tipos, ',')              AS tipos
FROM aristas_prov_1x a
JOIN clusters ca ON ca.doc_proveedor = a.doc_a
JOIN clusters cb ON cb.doc_proveedor = a.doc_b AND cb.cluster_id = ca.cluster_id
WHERE ca.cluster_id IN (SELECT cluster_id FROM api_clusters);

-- ---------------------------------------------------------------------
-- AGREGADOS. Espejo exacto de web/data/*.json: mismos nombres de campo,
-- para que quien ya lee el tablero no tenga que aprender otro vocabulario
-- (ver el docstring de pipeline/export_web.py). La diferencia es que aqui
-- no hay recortes: el API pagina, el tablero recortaba con LIMIT.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE api_titulares AS
SELECT concepto, n_contratos, coalesce(valor, 0) AS valor FROM titulares;

CREATE OR REPLACE TABLE api_indicios AS
SELECT indicio, grupo, n_contratos, coalesce(valor, 0) AS valor
FROM plata_por_indicio ORDER BY valor DESC;

-- Las DOS tasas siempre juntas: la comparacion cruda vs ajustada ES el
-- argumento metodologico (encogimiento bayesiano) y no se puede esconder.
CREATE OR REPLACE TABLE api_municipios AS
SELECT ciudad, departamento, n_contratos, n_atipicos,
       tasa_cruda, tasa_ajustada,
       coalesce(valor_total, 0)   AS valor_total,
       coalesce(valor_atipico, 0) AS valor_atipico,
       share_valor_atipico,
       n_proponente_unico, n_obra_directa, n_cuenta_compartida, n_fraccionamiento
FROM ranking_municipios;

CREATE OR REPLACE TABLE api_departamentos AS
SELECT d.departamento, d.n_contratos,
       coalesce(d.total, 0)           AS total,
       coalesce(d.sin_competencia, 0) AS sin_competencia,
       coalesce(d.en_riesgo, 0)       AS en_riesgo,
       coalesce(d.riesgo_red, 0)      AS riesgo_red,
       coalesce(d.regalias, 0)        AS regalias,
       r.tasa_cruda, r.tasa_ajustada
FROM plata_por_departamento d
LEFT JOIN ranking_departamentos r USING (departamento);

CREATE OR REPLACE TABLE api_tipos_obra AS
SELECT tipo_obra, n_contratos,
       coalesce(total, 0)           AS total,
       coalesce(en_riesgo, 0)       AS en_riesgo,
       coalesce(sin_competencia, 0) AS sin_competencia
FROM plata_por_tipo_obra;

CREATE OR REPLACE TABLE api_fuentes AS
SELECT fuente, coalesce(total, 0) AS total, coalesce(en_riesgo, 0) AS en_riesgo
FROM plata_por_fuente;

CREATE OR REPLACE TABLE api_autosupervision AS
SELECT nit_entidad, entidad, departamento, ciudad, n_auto, n_con_ambos, tasa,
       coalesce(valor_auto, 0) AS valor_auto
FROM entidades_autosupervision;

-- ---------------------------------------------------------------------
-- LIMITACIONES. Lo que hay que decir en voz alta. Viaja CON los datos a
-- proposito: el API no puede servir una cifra sin su salvedad al lado
-- (sale en GET /v1/meta y la lee la tool resumen_indicios del MCP).
--
-- DEUDA CONOCIDA: esta lista tambien vive como literal de Python en
-- pipeline/export_web.py, que la mete en web/data/meta.json para el
-- tablero. Son dos copias del mismo texto y pueden desincronizarse. Lo
-- correcto es que export_web.py lea de aqui, pero eso ata el tablero al
-- paso 90 y el tablero se toca aparte: se deja para quien lo mantenga.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE api_limitaciones (orden INTEGER, texto VARCHAR);
INSERT INTO api_limitaciones VALUES
 (1, 'Riesgo no es fraude: son indicios para priorizar investigacion.'),
 (2, 'Solo SECOP II. No incluye SECOP I ni entidades que publican mal.'),
 (3, 'La cedula del ordenador del gasto esta en el 64,5% de los contratos y la del supervisor en el 54,3%: el analisis de red cubre esa fraccion.'),
 (4, 'La cuenta bancaria esta en el 23,7%: las redes detectadas son un piso, no un censo.'),
 (5, 'No hay datos de oferentes perdedores, solo el numero de ofertas y el ganador.'),
 (6, 'El sobrecosto por unidad fisica no es calculable: solo el 0,9% de las descripciones declara una cantidad con unidad.'),
 (7, 'El ranking municipal no esta normalizado por poblacion.'),
 (8, 'De los procesos que la plataforma marca como abiertos, el 85,5% no tiene fecha de cierre publicada y el 12,9% tiene la fecha ya vencida: solo el 1,6% es realmente accionable hoy.');

-- ---------------------------------------------------------------------
-- META. Una sola fila: cobertura del dataset y cifras de encabezado.
-- Las fracciones de cobertura se miden aqui, no se copian de un README
-- que puede quedar desactualizado.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE api_meta AS
SELECT
  1                                                                   AS id,
  count(*)                                                            AS contratos,
  sum(valor_plausible)                                                AS valor_total,
  count(*) FILTER (WHERE es_atipico)                                  AS contratos_atipicos,
  (SELECT count(*) FROM api_clusters)                                 AS n_clusters,
  (SELECT count(*) FROM api_proveedores)                              AS n_proveedores,
  (SELECT count(*) FROM api_entidades)                                AS n_entidades,
  min(anio)                                                           AS primer_anio,
  max(anio)                                                           AS ultimo_anio,
  count(*) FILTER (WHERE doc_ordenador   IS NOT NULL)::DOUBLE / count(*) AS cobertura_cedula_ordenador,
  count(*) FILTER (WHERE doc_supervisor  IS NOT NULL)::DOUBLE / count(*) AS cobertura_cedula_supervisor,
  count(*) FILTER (WHERE precio_base     IS NOT NULL)::DOUBLE / count(*) AS cobertura_unido_a_proceso,
  count(*) FILTER (WHERE tipo_obra       IS NOT NULL)::DOUBLE / count(*) AS cobertura_tipo_obra,
  -- la cuenta bancaria no se publica, pero SU COBERTURA si: es la que
  -- dice que las redes detectadas son un piso y no un censo.
  (SELECT count(*) FILTER (WHERE cuenta_key IS NOT NULL)::DOUBLE / count(*)
     FROM base)                                                       AS cobertura_cuenta_bancaria,
  current_date                                                        AS construido
FROM api_contratos;
