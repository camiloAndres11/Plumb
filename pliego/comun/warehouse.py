"""El warehouse de la plataforma: un DuckDB EN DISCO con SECOP por departamento.

    $PLATAFORMA_DATOS/warehouse/pliego.duckdb   (o PLIEGO_WAREHOUSE; ver pliego/comun/config.py)

Tablas fisicas, todas con `departamento_descarga` (el departamento cuya
descarga trajo la fila) y `descargado_en`:
  base_todo       contratos de construccion  (esquema fuente.ESQUEMA_BASE)
  procesos_todo   procesos adjudicados        (fuente.ESQUEMA_PROCESO)
  abiertos_todo   procesos sin adjudicar      (fuente.ESQUEMA_PROCESO)
  base_ventana    p10 de dias de ventana por modalidad (se recalcula al escribir)
  hist_unico      tasa de proponente unico por entidad   (idem)
  meta            por departamento: as_of, descargado_en, filas
Y una vista `alertas_todo` con las banderas del filtro, calculada con
`current_date` para que `dias_restantes` no envejezca entre descargas.

Cada empresa consulta con `consultar(sql, ambito)`: un cursor propio donde
`base`, `procesos`, `abiertos` y `alertas` son vistas temporales filtradas
por sus departamentos, de modo que LAS MISMAS SQL de pliego/*/semilla.py
corren sin cambios. Dos empresas del mismo departamento comparten filas.

Un solo escritor (candado) y lectores con cursores: DuckDB lo permite dentro
de un proceso. Con varios workers de uvicorn habria que serializar por fuera;
por eso la plataforma corre con --workers 1 (ver plataforma/Dockerfile).
"""
from __future__ import annotations

import threading
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pyarrow as pa

from pliego.comun import config as CFG
from pliego.comun import fuente as F

_con: duckdb.DuckDBPyConnection | None = None
_candado = threading.RLock()
_version = 0   # sube con cada escritura; pliego/comun/cache.py lo usa como llave


def ruta() -> Path:
    return CFG.actual().warehouse


def _extra(esquema: pa.Schema) -> pa.Schema:
    return esquema.append(pa.field("departamento_descarga", pa.string())).append(pa.field("descargado_en", pa.timestamp("us")))


ESQUEMA_BASE = _extra(F.ESQUEMA_BASE)
ESQUEMA_PROCESO = _extra(F.ESQUEMA_PROCESO)

# Como fuente.SQL_ALERTAS, pero como VISTA sobre abiertos_todo y con las
# fechas relativas a current_date.
SQL_VISTA_ALERTAS = """
CREATE OR REPLACE VIEW alertas_todo AS
SELECT a.* EXCLUDE (dias_restantes, dias_ventana),
       date_diff('day', a.fecha_publicacion, a.fecha_cierre) AS dias_ventana,
       date_diff('day', current_date, a.fecha_cierre)         AS dias_restantes,
       CASE WHEN a.fecha_cierre IS NULL THEN 'sin_fecha_cierre'
            WHEN date_diff('day', current_date, a.fecha_cierre) < 0 THEN 'cierre_vencido'
            ELSE 'accionable' END                                            AS universo,
       (a.fecha_publicacion IS NOT NULL AND a.fecha_cierre IS NOT NULL AND v.p10 IS NOT NULL
          AND date_diff('day', a.fecha_publicacion, a.fecha_cierre) <= v.p10) AS f_ventana_corta,
       CAST(NULL AS BOOLEAN)                                                 AS f_al_tope_minima,
       (h.tasa >= 0.80)                                                      AS f_historial_proponente_unico,
       h.tasa                                                                AS ev_tasa_historica_entidad,
       h.n_historico                                                         AS ev_n_historico_entidad,
       (coalesce(a.n_invitados, 0) >= 5 AND coalesce(a.n_manifestaron, 0) = 0
          AND date_diff('day', current_date, a.fecha_cierre) BETWEEN 0 AND 7) AS f_sin_interes_a_tiempo,
       CAST(NULL AS BOOLEAN)                                                 AS f_cierre_movido,
       ( coalesce((a.fecha_publicacion IS NOT NULL AND a.fecha_cierre IS NOT NULL AND v.p10 IS NOT NULL
                   AND date_diff('day', a.fecha_publicacion, a.fecha_cierre) <= v.p10)::INT, 0)
       + coalesce((h.tasa >= 0.80)::INT, 0)
       + coalesce((coalesce(a.n_invitados, 0) >= 5 AND coalesce(a.n_manifestaron, 0) = 0
                   AND date_diff('day', current_date, a.fecha_cierre) BETWEEN 0 AND 7)::INT, 0) ) AS n_banderas
FROM abiertos_todo a
LEFT JOIN base_ventana v ON v.modalidad = a.modalidad
LEFT JOIN hist_unico h ON h.nit_entidad = a.nit_entidad;
"""

SQL_AGREGADOS = """
CREATE OR REPLACE TABLE base_ventana AS
SELECT modalidad, quantile_cont(dias_ventana, 0.10) AS p10, count(*) AS n
FROM procesos_todo WHERE dias_ventana IS NOT NULL AND dias_ventana >= 0
GROUP BY 1 HAVING count(*) >= 5;

CREATE OR REPLACE TABLE hist_unico AS
SELECT nit_entidad,
       avg(CASE WHEN n_oferentes_unicos <= 1 THEN 1 ELSE 0 END) AS tasa,
       count(*) AS n_historico
FROM base_todo
WHERE n_oferentes_unicos IS NOT NULL AND modalidad NOT LIKE 'CONTRATACION DIRECTA%'
GROUP BY 1 HAVING count(*) >= 5;
"""


def _tipo_sql(t: pa.DataType) -> str:
    return {"string": "VARCHAR", "double": "DOUBLE", "int64": "BIGINT", "bool": "BOOLEAN",
            "timestamp[us]": "TIMESTAMP"}[str(t)]


def _ddl(nombre: str, esquema: pa.Schema, clave: str, fechas: tuple[str, ...]) -> str:
    cols = []
    for f in esquema:
        tipo = "DATE" if f.name in fechas else _tipo_sql(f.type)
        cols.append(f"{f.name} {tipo}" + (" PRIMARY KEY" if f.name == clave else ""))
    return f"CREATE TABLE IF NOT EXISTS {nombre} ({', '.join(cols)})"


FECHAS_BASE = ("fecha_firma", "fecha_inicio", "fecha_fin", "fecha_cierre_ofertas")
FECHAS_PROCESO = ("fecha_publicacion", "fecha_cierre", "fecha_adjudicacion")


def conexion() -> duckdb.DuckDBPyConnection:
    """La conexion del proceso (se abre una vez y crea el esquema si falta).
    Quien consulta pide `conexion().cursor()`; nunca comparte esta."""
    global _con
    with _candado:
        if _con is None:
            r = ruta()
            r.parent.mkdir(parents=True, exist_ok=True)
            con = duckdb.connect(str(r))
            con.execute(_ddl("base_todo", ESQUEMA_BASE, "id_contrato", FECHAS_BASE))
            con.execute(_ddl("procesos_todo", ESQUEMA_PROCESO, "id_del_proceso", FECHAS_PROCESO))
            con.execute(_ddl("abiertos_todo", ESQUEMA_PROCESO, "id_del_proceso", FECHAS_PROCESO))
            con.execute("CREATE TABLE IF NOT EXISTS meta (departamento VARCHAR PRIMARY KEY, as_of VARCHAR, "
                        "descargado_en TIMESTAMP, n_base BIGINT, n_procesos BIGINT, n_abiertos BIGINT)")
            con.execute("CREATE TABLE IF NOT EXISTS base_ventana (modalidad VARCHAR, p10 DOUBLE, n BIGINT)")
            con.execute("CREATE TABLE IF NOT EXISTS hist_unico (nit_entidad VARCHAR, tasa DOUBLE, n_historico BIGINT)")
            con.execute(SQL_VISTA_ALERTAS)
            _con = con
        return _con


def cerrar() -> None:
    global _con
    with _candado:
        if _con is not None:
            _con.close()
            _con = None


def version() -> int:
    return _version


# ------------------------------------------------------------------ escribir
def _fechas(filas: list[dict], claves: tuple[str, ...]) -> list[dict]:
    """Las fechas ISO del mapeo a `date`, para las columnas DATE."""
    out = []
    for f in filas:
        g = dict(f)
        for k in claves:
            v = g.get(k)
            g[k] = date.fromisoformat(v) if isinstance(v, str) else v
        out.append(g)
    return out


def upsert(departamento: str, contratos: list[dict], adjudicados: list[dict], abiertos: list[dict],
           as_of: str | None = None, incremental: bool = False) -> dict:
    """Escribe lo descargado de un departamento. Completo: reemplaza todo lo
    del departamento. Incremental: mete o reemplaza por id contratos y
    adjudicados, y reemplaza los abiertos (siempre se traen todos los de la
    ventana). Recalcula agregados y sube la version."""
    global _version
    hoy = date.today()
    base, procesos, abiertos_f = F.registros_a_filas(contratos, adjudicados, abiertos, hoy)
    ahora = datetime.now(UTC).replace(tzinfo=None)
    for fila in base + procesos + abiertos_f:
        fila["departamento_descarga"] = departamento
        fila["descargado_en"] = ahora
    t_base = pa.Table.from_pylist(_fechas(base, FECHAS_BASE), schema=_esquema_fechas(ESQUEMA_BASE, FECHAS_BASE))
    t_proc = pa.Table.from_pylist(_fechas(procesos, FECHAS_PROCESO), schema=_esquema_fechas(ESQUEMA_PROCESO, FECHAS_PROCESO))
    t_abie = pa.Table.from_pylist(_fechas(abiertos_f, FECHAS_PROCESO), schema=_esquema_fechas(ESQUEMA_PROCESO, FECHAS_PROCESO))
    with _candado:
        cur = conexion().cursor()
        cur.register("_base", t_base)
        cur.register("_procesos", t_proc)
        cur.register("_abiertos", t_abie)
        cur.begin()
        try:
            if not incremental:
                cur.execute("DELETE FROM base_todo WHERE departamento_descarga = ?", [departamento])
                cur.execute("DELETE FROM procesos_todo WHERE departamento_descarga = ?", [departamento])
            cur.execute("DELETE FROM abiertos_todo WHERE departamento_descarga = ?", [departamento])
            # Dedupe dentro del lote (Croma puede repetir una fila entre paginas).
            cur.execute("INSERT OR REPLACE INTO base_todo SELECT * EXCLUDE (rn) FROM (SELECT *, row_number() OVER (PARTITION BY id_contrato) AS rn FROM _base) WHERE rn = 1 AND id_contrato IS NOT NULL")
            cur.execute("INSERT OR REPLACE INTO procesos_todo SELECT * EXCLUDE (rn) FROM (SELECT *, row_number() OVER (PARTITION BY id_del_proceso) AS rn FROM _procesos) WHERE rn = 1 AND id_del_proceso IS NOT NULL")
            cur.execute("INSERT OR REPLACE INTO abiertos_todo SELECT * EXCLUDE (rn) FROM (SELECT *, row_number() OVER (PARTITION BY id_del_proceso) AS rn FROM _abiertos) WHERE rn = 1 AND id_del_proceso IS NOT NULL")
            cur.execute(SQL_AGREGADOS)
            n = {t: cur.execute(f"SELECT count(*) FROM {t} WHERE departamento_descarga = ?", [departamento]).fetchone()[0]
                 for t in ("base_todo", "procesos_todo", "abiertos_todo")}
            cur.execute("INSERT OR REPLACE INTO meta VALUES (?, ?, ?, ?, ?, ?)",
                        [departamento, as_of, ahora, n["base_todo"], n["procesos_todo"], n["abiertos_todo"]])
            cur.commit()
        except Exception:
            cur.rollback()
            raise
        finally:
            cur.close()
        _version += 1
    return {"departamento": departamento, "as_of": as_of, "n_base": n["base_todo"],
            "n_procesos": n["procesos_todo"], "n_abiertos": n["abiertos_todo"]}


def _esquema_fechas(esquema: pa.Schema, fechas: tuple[str, ...]) -> pa.Schema:
    campos = [pa.field(f.name, pa.date32()) if f.name in fechas else f for f in esquema]
    return pa.schema(campos)


# --------------------------------------------------------------------- leer
def consultar(sql: str, ambito: tuple[str, ...]) -> list[dict]:
    """Corre una SQL de semilla (que habla de base/alertas/procesos/abiertos)
    viendo solo los departamentos de `ambito`."""
    cur = conexion().cursor()
    try:
        _vistas(cur, ambito)
        return F._dicts(cur.execute(sql))
    finally:
        cur.close()


def _vistas(cur, ambito: tuple[str, ...]) -> None:
    """Las vistas por empresa son la frontera entre tenants: los
    departamentos entran como una tabla registrada en el cursor, no
    concatenados en el SQL (DuckDB no admite parametros en CREATE VIEW).
    Sin departamentos, la tabla esta vacia y no casa con nada."""
    cur.register("_ambito", pa.Table.from_pylist([{"d": d} for d in ambito], schema=pa.schema([("d", pa.string())])))
    for nombre in ("base", "procesos", "abiertos", "alertas"):
        cur.execute(f"CREATE OR REPLACE TEMP VIEW {nombre} AS SELECT * FROM {nombre}_todo "
                    f"WHERE departamento_descarga IN (SELECT d FROM _ambito)")


def estado(ambito: tuple[str, ...] = ()) -> dict:
    cur = conexion().cursor()
    try:
        filas = F._dicts(cur.execute("SELECT * FROM meta ORDER BY departamento"))
        if ambito:
            filas = [f for f in filas if f["departamento"] in ambito]
        return {"departamentos": filas, "as_of": max((f["as_of"] or "" for f in filas), default=None) or None,
                "n_base": sum(f["n_base"] or 0 for f in filas), "n_abiertos": sum(f["n_abiertos"] or 0 for f in filas),
                "version": _version}
    finally:
        cur.close()
