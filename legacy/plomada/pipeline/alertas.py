"""Alertas pre-adjudicacion sobre licitaciones de obra publica ABIERTAS.

Requiere en orden:
    python pipeline/build.py            (01-03: nucleo + banderas historicas)
    python pipeline/ingest_abiertos.py  (snapshot de hoy; reanudable)
    python pipeline/alertas.py          (este script)

Por que esto no es solo SQL: la bandera de "addenda que movio el cierre"
necesita comparar el snapshot de hoy contra el de AYER, y el archivo de
ayer puede no existir (primera corrida, o un dia que se salto el cron).
DuckDB no tiene forma declarativa de decir "si este archivo no existe, usa
una tabla vacia" -- eso es control de flujo, y por eso vive en Python, no
en sql/30_procesos_abiertos.sql. Mismo patron que pipeline/grafo.py, que
tampoco es SQL puro por una razon estructural equivalente.

En la primera corrida, f_cierre_movido queda en NULL (no en False): NULL
significa "no hay con que comparar todavia", False significaria "se
comparo y no cambio", que seria una afirmacion falsa el primer dia.
"""
from __future__ import annotations

import glob
import os
import sys

import duckdb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "abiertos")
DB = os.path.join(ROOT, "data", "warehouse", "plomada.duckdb")
SQL_STAGE = os.path.join(ROOT, "sql", "30_procesos_abiertos.sql")
# Vista de serving del API. Vive aqui y no en build.py --all porque
# depende de `alertas`, que solo existe despues de este script.
SQL_SERVING = os.path.join(ROOT, "sql", "91_serving_alertas.sql")


def snapshots():
    return sorted(glob.glob(os.path.join(RAW, "*.jsonl")))


def main():
    files = snapshots()
    if not files:
        sys.exit("no hay snapshots; corre 'python pipeline/ingest_abiertos.py'")
    hoy_path, ayer_path = files[-1], (files[-2] if len(files) >= 2 else None)
    print("snapshot de hoy:      %s" % os.path.basename(hoy_path))
    print("snapshot anterior:    %s"
          % (os.path.basename(ayer_path) if ayer_path else "NINGUNO (primera corrida)"))

    if not os.path.exists(DB):
        sys.exit("no hay warehouse; corre 'python pipeline/build.py' primero")
    con = duckdb.connect(DB)

    needed = {"base_ventana", "tope_minima", "flags"}
    have = {r[0] for r in con.execute("SELECT table_name FROM duckdb_tables()").fetchall()}
    if not needed <= have:
        sys.exit(
            "faltan tablas del nucleo (%s); corre 'python pipeline/build.py' primero"
            % (needed - have)
        )

    with open(SQL_STAGE, "r", encoding="utf-8") as fh:
        sql = fh.read().replace("__ABIERTOS_HOY__", hoy_path.replace("\\", "/"))
    con.execute(sql)

    if ayer_path:
        con.execute(
            """
            CREATE OR REPLACE TABLE abiertos_ayer AS
            SELECT id_del_proceso,
                   try_cast(max(CAST(fecha_de_recepcion_de AS VARCHAR)) AS DATE) AS fecha_cierre_ayer
            FROM read_json_auto(?, format='newline_delimited', union_by_name=true, sample_size=-1)
            GROUP BY id_del_proceso
            """,
            [ayer_path.replace("\\", "/")],
        )
    else:
        con.execute(
            "CREATE OR REPLACE TABLE abiertos_ayer "
            "(id_del_proceso VARCHAR, fecha_cierre_ayer DATE)"
        )

    con.execute(
        """
        CREATE OR REPLACE TABLE alertas AS
        SELECT
          a.*,
          y.fecha_cierre_ayer,
          CASE WHEN y.fecha_cierre_ayer IS NULL THEN NULL
               ELSE a.fecha_cierre IS DISTINCT FROM y.fecha_cierre_ayer END AS f_cierre_movido,
          ( coalesce(f_ventana_corta::INT, 0)
          + coalesce(f_al_tope_minima::INT, 0)
          + coalesce(f_historial_proponente_unico::INT, 0)
          + coalesce(f_sin_interes_a_tiempo::INT, 0)
          + coalesce((y.fecha_cierre_ayer IS NOT NULL
                      AND a.fecha_cierre IS DISTINCT FROM y.fecha_cierre_ayer)::INT, 0)
          )                                                             AS n_banderas
        FROM abiertos_con_flags a
        LEFT JOIN abiertos_ayer y USING (id_del_proceso)
        """
    )

    # Publica las alertas para el API (/v1/alertas). Si nadie corre esto,
    # api_alertas no existe y el endpoint responde 503 con un mensaje
    # claro, igual que el tablero cuando falta alertas.json.
    with open(SQL_SERVING, "r", encoding="utf-8") as fh:
        con.execute(fh.read())

    tot = con.execute("SELECT count(*) FROM alertas").fetchone()[0]
    por_universo = con.execute(
        "SELECT universo, count(*) FROM alertas GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall()
    accionables = con.execute(
        "SELECT count(*) FROM alertas WHERE universo = 'accionable'"
    ).fetchone()[0]
    con_al = con.execute(
        "SELECT count(*) FROM alertas WHERE universo = 'accionable' AND n_banderas >= 1"
    ).fetchone()[0]

    print("\nprocesos en el snapshot: %d" % tot)
    for u, n in por_universo:
        print("  %-20s %6d  (%.1f%%)" % (u, n, 100.0 * n / tot))
    print(
        "\nDe los %d procesos con cierre vigente (los unicos donde hoy se puede\n"
        "actuar), %d tienen al menos una alerta. El resto del snapshot (sin\n"
        "fecha o con fecha vencida) es opacidad de publicacion, no riesgo de\n"
        "fraude, y se reporta aparte." % (accionables, con_al)
    )

    print("\n=== ACCIONABLES con mas alertas, plazo mas urgente primero ===")
    for r in con.execute(
        """SELECT entidad, ciudad, round(precio_base/1e6,1) AS precio_mm,
                  modalidad, dias_restantes, n_banderas, urlproceso
           FROM alertas
           WHERE universo = 'accionable' AND n_banderas >= 1
           ORDER BY n_banderas DESC, dias_restantes ASC LIMIT 12"""
    ).fetchall():
        print("  %-38s %-14s $%8s MM  %-22s faltan %s dias  alertas=%d"
              % (str(r[0])[:38], str(r[1])[:14], r[2], str(r[3])[:22], r[4], r[5]))

    con.close()


if __name__ == "__main__":
    main()
