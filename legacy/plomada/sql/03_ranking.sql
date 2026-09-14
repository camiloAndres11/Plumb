-- =====================================================================
-- 03_ranking.sql : del contrato al municipio y a la administracion.
--
-- El problema estadistico central de cualquier ranking territorial:
-- un municipio con 4 contratos y 2 marcados sale con 50% y encabeza la
-- lista por puro azar. La solucion aqui es encogimiento bayesiano
-- empirico (beta-binomial, momentos): las tasas de los municipios con
-- poca evidencia se jalan hacia la media nacional, y solo se separan
-- de ella cuando tienen volumen que lo sostenga.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Pesos de las banderas. Explicitos y publicables: cualquiera puede
-- discutirlos y recalcular. Escala: 3 = indicio fuerte, 1 = contexto.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE pesos (bandera VARCHAR, peso DOUBLE, grupo VARCHAR, glosa VARCHAR);
INSERT INTO pesos VALUES
 ('f_cuenta_compartida',      3, 'Red',         'Proveedores distintos cobrando a la misma cuenta bancaria'),
 ('f_ordenador_es_supervisor',3, 'Red',         'El mismo funcionario autoriza el gasto y supervisa la ejecucion'),
 ('f_sobrepago',              3, 'Dinero',      'Se pago mas del valor del contrato'),
 ('f_anticipo_no_declarado',  3, 'Dinero',      'Declara no tener anticipo pero registra anticipo girado'),
 ('f_anticipo_al_tope',       2, 'Dinero',      'Agota exactamente el anticipo maximo legal del 50%'),
 ('f_fraccionamiento',        3, 'Umbrales',    'Contratos hermanos al mismo proveedor, misma categoria, en 30 dias'),
 ('f_proponente_unico',       2, 'Competencia', 'Un solo oferente en el proceso'),
 ('f_obra_directa',           2, 'Competencia', 'Obra publica adjudicada por contratacion directa'),
 ('f_ratio_calcado',          2, 'Competencia', 'Adjudicado al 99.5-100% del presupuesto oficial, sin competencia'),
 ('f_invitacion_vacia',       2, 'Competencia', 'Cinco o mas invitados y un solo oferente efectivo'),
 ('f_replegal_multiempresa',  2, 'Red',         'Representante legal compartido por 3+ empresas proveedoras'),
 ('f_ordenador_concentrado',  2, 'Red',         'El ordenador concentra >50% de su valor en un solo proveedor'),
 ('f_al_tope_minima',         2, 'Umbrales',    'Valor pegado al techo de la minima cuantia de la entidad'),
 ('f_ventana_corta',          1, 'Competencia', 'Plazo de ofertas en el decil mas corto de su modalidad'),
 ('f_supervisor_sobrecargado',1, 'Red',         'Supervisor con 30+ contratos a cargo'),
 ('f_ordenador_itinerante',   1, 'Red',         'El ordenador ha firmado en 3+ entidades distintas'),
 ('f_prorroga_mayor',         1, 'Ejecucion',   'Plazo adicionado en mas del 50% del original'),
 ('f_cierre_de_periodo',      1, 'Ejecucion',   'Firmado en la segunda quincena de diciembre del ultimo ano de gobierno'),
 ('f_datos_faltantes',        1, 'Opacidad',    'Faltan campos de publicacion obligatoria'),
 ('f_sin_proceso',            1, 'Opacidad',    'El contrato no tiene proceso publicado en SECOP II'),
 ('f_valor_implausible',      1, 'Opacidad',    'Valor publicado imposible (por encima de 10 billones COP)'),
 ('f_cuenta_consorcios',      1, 'Red',         'Consorcio comparte cuenta con su propio miembro (indicio debil)');

-- ---------------------------------------------------------------------
-- Puntaje por contrato: suma ponderada normalizada a 0..1.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE puntajes AS
WITH w AS (SELECT sum(peso) AS wtot FROM pesos)
SELECT
  f.*,
  ( 3*coalesce(f_cuenta_compartida::INT,0)
  + 3*coalesce(f_ordenador_es_supervisor::INT,0)
  + 3*coalesce(f_sobrepago::INT,0)
  + 3*coalesce(f_anticipo_no_declarado::INT,0)
  + 2*coalesce(f_anticipo_al_tope::INT,0)
  + 3*coalesce(f_fraccionamiento::INT,0)
  + 2*coalesce(f_proponente_unico::INT,0)
  + 2*coalesce(f_obra_directa::INT,0)
  + 2*coalesce(f_ratio_calcado::INT,0)
  + 2*coalesce(f_invitacion_vacia::INT,0)
  + 2*coalesce(f_replegal_multiempresa::INT,0)
  + 2*coalesce(f_ordenador_concentrado::INT,0)
  + 2*coalesce(f_al_tope_minima::INT,0)
  + 1*coalesce(f_ventana_corta::INT,0)
  + 1*coalesce(f_supervisor_sobrecargado::INT,0)
  + 1*coalesce(f_ordenador_itinerante::INT,0)
  + 1*coalesce(f_prorroga_mayor::INT,0)
  + 1*coalesce(f_cierre_de_periodo::INT,0)
  + 1*coalesce(f_datos_faltantes::INT,0)
  + 1*coalesce(f_sin_proceso::INT,0)
  + 1*coalesce(f_valor_implausible::INT,0)
  + 1*coalesce(f_cuenta_consorcios::INT,0)
  )                                                     AS puntos_crudos,
  ( 3*coalesce(f_cuenta_compartida::INT,0)
  + 3*coalesce(f_ordenador_es_supervisor::INT,0)
  + 3*coalesce(f_sobrepago::INT,0)
  + 3*coalesce(f_anticipo_no_declarado::INT,0)
  + 2*coalesce(f_anticipo_al_tope::INT,0)
  + 3*coalesce(f_fraccionamiento::INT,0)
  + 2*coalesce(f_proponente_unico::INT,0)
  + 2*coalesce(f_obra_directa::INT,0)
  + 2*coalesce(f_ratio_calcado::INT,0)
  + 2*coalesce(f_invitacion_vacia::INT,0)
  + 2*coalesce(f_replegal_multiempresa::INT,0)
  + 2*coalesce(f_ordenador_concentrado::INT,0)
  + 2*coalesce(f_al_tope_minima::INT,0)
  + 1*coalesce(f_ventana_corta::INT,0)
  + 1*coalesce(f_supervisor_sobrecargado::INT,0)
  + 1*coalesce(f_ordenador_itinerante::INT,0)
  + 1*coalesce(f_prorroga_mayor::INT,0)
  + 1*coalesce(f_cierre_de_periodo::INT,0)
  + 1*coalesce(f_datos_faltantes::INT,0)
  + 1*coalesce(f_sin_proceso::INT,0)
  + 1*coalesce(f_valor_implausible::INT,0)
  + 1*coalesce(f_cuenta_consorcios::INT,0)
  ) / w.wtot                                            AS score,
  -- numero de banderas fuertes (peso 3) encendidas
  ( coalesce(f_cuenta_compartida::INT,0)
  + coalesce(f_ordenador_es_supervisor::INT,0)
  + coalesce(f_sobrepago::INT,0)
  + coalesce(f_anticipo_no_declarado::INT,0)
  + coalesce(f_fraccionamiento::INT,0) )                AS n_banderas_fuertes
FROM flags f CROSS JOIN w;

-- Un contrato se cuenta como ATIPICO si enciende una bandera fuerte o
-- acumula suficiente puntaje. Umbral explicito, no oculto en un modelo.
CREATE OR REPLACE VIEW atipicos AS
SELECT *, (n_banderas_fuertes >= 1 OR puntos_crudos >= 6) AS es_atipico
FROM puntajes;

-- ---------------------------------------------------------------------
-- Prior beta estimado por momentos sobre los municipios con volumen
-- suficiente. De aqui sale el encogimiento.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE prior_mpio AS
WITH t AS (
  SELECT departamento, ciudad,
         count(*) AS n,
         sum(es_atipico::INT) AS k
  FROM atipicos
  WHERE ciudad IS NOT NULL
  GROUP BY 1, 2
), s AS (
  SELECT avg(k::DOUBLE / n) AS m, var_samp(k::DOUBLE / n) AS v
  FROM t WHERE n >= 20
)
SELECT
  m,
  v,
  greatest(m * (m * (1 - m) / nullif(v, 0) - 1), 0.5) AS alpha,
  greatest((1 - m) * (m * (1 - m) / nullif(v, 0) - 1), 0.5) AS beta
FROM s;

-- ---------------------------------------------------------------------
-- RANKING DE MUNICIPIOS
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE ranking_municipios AS
WITH t AS (
  SELECT departamento, ciudad,
         count(*)                                        AS n_contratos,
         sum(es_atipico::INT)                            AS n_atipicos,
         sum(valor_plausible)                                      AS valor_total,
         sum(CASE WHEN es_atipico THEN valor_plausible ELSE 0 END) AS valor_atipico,
         sum(CASE WHEN es_atipico THEN coalesce(rec_regalias,0) ELSE 0 END) AS regalias_atipicas,
         avg(score)                                      AS score_medio,
         sum(f_proponente_unico::INT)                    AS n_proponente_unico,
         sum(f_obra_directa::INT)                         AS n_obra_directa,
         sum(f_cuenta_compartida::INT)                    AS n_cuenta_compartida,
         sum(f_fraccionamiento::INT)                      AS n_fraccionamiento,
         sum(coalesce(f_anticipo_no_declarado::INT,0))    AS n_anticipo_no_declarado,
         sum(coalesce(f_sobrepago::INT,0))                AS n_sobrepago
  FROM atipicos
  WHERE ciudad IS NOT NULL
  GROUP BY 1, 2
)
SELECT
  t.*,
  t.n_atipicos::DOUBLE / t.n_contratos                       AS tasa_cruda,
  (t.n_atipicos + p.alpha) / (t.n_contratos + p.alpha + p.beta) AS tasa_ajustada,
  t.valor_atipico / nullif(t.valor_total, 0)                 AS share_valor_atipico,
  p.alpha, p.beta
FROM t CROSS JOIN prior_mpio p
ORDER BY tasa_ajustada DESC;

-- ---------------------------------------------------------------------
-- RANKING DE ADMINISTRACIONES (entidad x periodo de gobierno)
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE ranking_administraciones AS
WITH t AS (
  SELECT nit_entidad, entidad, departamento, ciudad, orden, periodo_gobierno,
         count(*)                                        AS n_contratos,
         sum(es_atipico::INT)                            AS n_atipicos,
         sum(valor_plausible)                                      AS valor_total,
         sum(CASE WHEN es_atipico THEN valor_plausible ELSE 0 END) AS valor_atipico,
         avg(score)                                      AS score_medio
  FROM atipicos
  WHERE periodo_gobierno IS NOT NULL
  GROUP BY 1, 2, 3, 4, 5, 6
  HAVING count(*) >= 10
)
SELECT
  t.*,
  t.n_atipicos::DOUBLE / t.n_contratos                          AS tasa_cruda,
  (t.n_atipicos + p.alpha) / (t.n_contratos + p.alpha + p.beta) AS tasa_ajustada,
  t.valor_atipico / nullif(t.valor_total, 0)                    AS share_valor_atipico
FROM t CROSS JOIN prior_mpio p
ORDER BY tasa_ajustada DESC;

-- ---------------------------------------------------------------------
-- RANKING DE DEPARTAMENTOS (vista agregada para el mapa)
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE ranking_departamentos AS
WITH t AS (
  SELECT departamento,
         count(*) AS n_contratos,
         sum(es_atipico::INT) AS n_atipicos,
         sum(valor_plausible) AS valor_total,
         sum(CASE WHEN es_atipico THEN valor_plausible ELSE 0 END) AS valor_atipico
  FROM atipicos WHERE departamento IS NOT NULL GROUP BY 1
)
SELECT t.*,
       t.n_atipicos::DOUBLE / t.n_contratos AS tasa_cruda,
       (t.n_atipicos + p.alpha) / (t.n_contratos + p.alpha + p.beta) AS tasa_ajustada,
       t.valor_atipico / nullif(t.valor_total, 0) AS share_valor_atipico
FROM t CROSS JOIN prior_mpio p
ORDER BY tasa_ajustada DESC;
