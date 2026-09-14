-- =====================================================================
-- 91_serving_alertas.sql : vista de serving de las alertas pre-adjudicacion.
--
-- Vive aparte de 90_serving.sql porque `alertas` no existe cuando corre
-- `build.py --all`: se construye en pipeline/alertas.py, que necesita
-- inyectar la ruta del snapshot fechado del dia (y comparar contra el de
-- ayer, que puede no existir). Por eso lo ejecuta ese script al final,
-- no el orquestador generico.
--
-- El API sirve estas filas en /v1/alertas y responde 503 con un mensaje
-- claro si la tabla no esta cargada -- mismo criterio que el tablero con
-- alertas.json, que es opcional a proposito.
-- =====================================================================
-- requiere: alertas

CREATE OR REPLACE TABLE api_alertas AS
SELECT
  id_del_proceso,
  urlproceso,
  nit_entidad,
  entidad,
  departamento,
  ciudad,
  tipo_contrato,
  modalidad,
  unspsc,
  descripcion,
  coalesce(precio_base, 0)              AS precio_base,
  fecha_publicacion,
  fecha_cierre,
  dias_ventana,
  dias_restantes,
  n_invitados,
  n_manifestaron,
  n_respuestas,
  -- 'accionable' | 'zombie_vencido' | 'sin_fecha_cierre'. La distincion
  -- es explicita a proposito: solo el 1,6% del snapshot es accionable
  -- hoy, y mezclarlos bajo "alertas" seria enganoso.
  universo,
  n_banderas,
  f_ventana_corta,
  f_al_tope_minima,
  f_historial_proponente_unico,
  f_sin_interes_a_tiempo,
  -- NULL en la primera corrida: significa "no hay snapshot de ayer con
  -- que comparar", no "se comparo y no cambio".
  f_cierre_movido,
  f_cierre_vencido,
  f_sin_fechas,
  ev_ventana_p10_modalidad,
  ev_tasa_historica_entidad,
  ev_n_historico_entidad
FROM alertas;

-- Una fila por universo + la fecha del snapshot, para que /v1/alertas/resumen
-- no tenga que agregar 31.685 filas en cada request.
CREATE OR REPLACE TABLE api_alertas_resumen AS
SELECT
  universo,
  count(*)                                          AS n_procesos,
  count(*) FILTER (WHERE n_banderas >= 1)           AS n_con_alerta,
  sum(precio_base)                                  AS precio_base_total,
  current_date                                      AS construido
FROM api_alertas
GROUP BY universo
ORDER BY n_procesos DESC;
