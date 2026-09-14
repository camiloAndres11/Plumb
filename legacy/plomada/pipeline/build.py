"""Construye el warehouse DuckDB y publica el snapshot compartido.

Uso:
    python pipeline/build.py                # corre 01-03 (el nucleo compartido)
    python pipeline/build.py --steps 01 02  # solo esos pasos
    python pipeline/build.py --all          # todos los .sql de sql/ en orden
    python pipeline/build.py --no-export    # sin publicar base.parquet

CONTRATO DE DATOS
-----------------
DuckDB admite UN SOLO escritor. Cinco personas no pueden construir contra
el mismo .duckdb a la vez. Por eso este script publica
`data/exports/base.parquet`, que es el UNICO artefacto compartido:

  * `base.parquet` es de SOLO LECTURA para los frentes de precios (C),
    satelital (D) y alertas (E). Nadie lo modifica.
  * Se regenera unicamente corriendo este script con los pasos 01-03.
  * Cada frente escribe su propio archivo DuckDB, nunca el de otro.

Rangos de numeracion SQL reservados (para no chocar en el mismo archivo):
    01-03  compartido, CONGELADO   staging, banderas, ranking
    04-09  A+B   grafo: nodos, aristas, comunidades, interventoria
    10-19  C     cantidades, deflactor, modelo hedonico
    20-29  D     geocodificacion, series satelitales
    30-39  E     procesos abiertos, alertas pre-adjudicacion
    90-99  E     vistas de serving para el API
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys
import time

import duckdb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
SQL = os.path.join(ROOT, "sql")
EXPORTS = os.path.join(ROOT, "data", "exports")
DB = os.path.join(ROOT, "data", "warehouse", "plomada.duckdb")

NUCLEO = ["01", "02", "03"]

# Tablas que se publican como parquet para los otros frentes.
SNAPSHOT = {
    "base": "base.parquet",              # el universo normalizado + competencia
    "puntajes": "puntajes.parquet",      # base + las 20 banderas + score
}


def sql_files(prefixes=None):
    """Devuelve los .sql de sql/ ordenados, filtrando por prefijo numerico."""
    out = []
    for path in sorted(glob.glob(os.path.join(SQL, "*.sql"))):
        m = re.match(r"^(\d+)_", os.path.basename(path))
        if not m:
            continue
        if prefixes is None or m.group(1) in prefixes:
            out.append(path)
    return out


def tablas(con):
    return {r[0] for r in con.execute("SELECT table_name FROM duckdb_tables()").fetchall()}


def run_sql_file(con, path, allow_skip=False):
    with open(path, "r", encoding="utf-8") as fh:
        sql = fh.read()
    # las rutas de los JSONL se inyectan aqui para que el SQL sea portable
    sql = sql.replace("__RAW__", RAW.replace("\\", "/"))
    # Un paso puede declarar de que tablas depende con una linea
    # `-- requiere: a, b` en su cabecera. Si falta alguna y estamos en un
    # lote, se omite con un mensaje claro en vez de reventar. Es el mismo
    # criterio que la guardia de placeholders de abajo: los pasos con un
    # orquestador propio (91 necesita pipeline/alertas.py) no pueden
    # correr como SQL suelto dentro de --all.
    req = re.search(r"^--\s*requiere:\s*(.+)$", sql, re.MULTILINE)
    if req:
        faltan = {t.strip() for t in req.group(1).split(",")} - tablas(con)
        if faltan:
            msg = (
                "%s necesita tablas que no existen (%s): corre antes el paso "
                "que las construye." % (os.path.basename(path), ", ".join(sorted(faltan)))
            )
            if allow_skip:
                print("   omitido: %s" % msg, flush=True)
                return
            sys.exit(msg)
    # Algunos pasos (30_procesos_abiertos.sql y cualquier futuro paso que
    # necesite un snapshot fechado, p.ej. el satelital en 20-29) llevan un
    # placeholder que solo su propio script de orquestacion sabe rellenar
    # (ver pipeline/alertas.py). Si queda un __ALGO__ sin resolver, ese
    # archivo no se puede correr como SQL suelto.
    quedan = re.findall(r"__[A-Z_]+__", sql)
    if quedan:
        msg = (
            "%s tiene placeholders sin resolver (%s): no se ejecuta asi. "
            "Usa el script de orquestacion de ese paso (p.ej. pipeline/alertas.py)."
            % (os.path.basename(path), ", ".join(sorted(set(quedan))))
        )
        if allow_skip:
            print("   omitido: %s" % msg, flush=True)
            return
        sys.exit(msg)
    con.execute(sql)


def export_snapshot(con):
    """Publica el snapshot compartido. Este es el contrato con C, D y E."""
    os.makedirs(EXPORTS, exist_ok=True)
    print("\n>> snapshot compartido -> data/exports/", flush=True)
    for tbl, fname in SNAPSHOT.items():
        exists = con.execute(
            "SELECT count(*) FROM duckdb_tables() WHERE table_name = ?", [tbl]
        ).fetchone()[0]
        if not exists:
            print("   %-12s AUSENTE (corre los pasos 01-03 primero)" % tbl)
            continue
        path = os.path.join(EXPORTS, fname).replace("\\", "/")
        con.execute("COPY %s TO '%s' (FORMAT PARQUET, COMPRESSION ZSTD)" % (tbl, path))
        n = con.execute("SELECT count(*) FROM %s" % tbl).fetchone()[0]
        mb = os.path.getsize(path) / 1e6
        print("   %-12s %7d filas  %6.1f MB  %s" % (tbl, n, mb, fname))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", nargs="+", help="prefijos a correr, p.ej. 01 02 04")
    ap.add_argument("--all", action="store_true", help="corre todos los .sql")
    ap.add_argument("--no-export", action="store_true", help="no publicar el snapshot")
    args = ap.parse_args()

    prefixes = None if args.all else (args.steps or NUCLEO)
    steps = sql_files(prefixes)
    if not steps:
        sys.exit("no hay .sql que coincidan con %s" % (prefixes,))

    # el nucleo necesita los JSONL crudos; los pasos derivados no
    if prefixes is None or "01" in prefixes:
        for folder in ("contratos", "procesos"):
            if not glob.glob(os.path.join(RAW, folder, "*.jsonl")):
                sys.exit("falta la ingesta: corre 'python pipeline/ingest.py'")

    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = duckdb.connect(DB)
    con.execute("SET preserve_insertion_order=false")

    for path in steps:
        t0 = time.time()
        print("\n>> %s" % os.path.basename(path), flush=True)
        run_sql_file(con, path, allow_skip=(len(steps) > 1))
        print("   ok (%.1fs)" % (time.time() - t0), flush=True)

    print("")
    for tbl in ("contratos", "procesos", "base", "flags", "puntajes"):
        n = con.execute(
            "SELECT count(*) FROM duckdb_tables() WHERE table_name = ?", [tbl]
        ).fetchone()[0]
        if n:
            print("%-12s %8d filas" % (tbl, con.execute("SELECT count(*) FROM %s" % tbl).fetchone()[0]))

    if not args.no_export:
        export_snapshot(con)

    con.close()
    print("\nwarehouse -> %s" % DB)


if __name__ == "__main__":
    main()
