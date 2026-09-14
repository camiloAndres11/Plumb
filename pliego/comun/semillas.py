"""Exportar fixtures (parquet) desde el warehouse de Plomada, en solo lectura.

Los tres semilla.py de filtro, radar y simulador hacian lo mismo con
distintas SQL: abrir legacy/plomada/data/warehouse/plomada.duckdb y copiar
cada consulta a <enfoque>/fixtures/<nombre>.parquet. Aqui vive ese paso;
cada semilla.py aporta sus SQL y llama a exportar().

    python -m pliego.radar.semilla
"""
from __future__ import annotations

from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[2]
WAREHOUSE = RAIZ / "legacy" / "plomada" / "data" / "warehouse" / "plomada.duckdb"


def exportar(fixtures: Path, tablas: list[tuple[str, str]], warehouse: Path = WAREHOUSE) -> int:
    """tablas: [(nombre, sql)] -> fixtures/<nombre>.parquet. 1 si no hay warehouse."""
    if not warehouse.exists():
        print(f"no existe {warehouse}; corre legacy/plomada/pipeline/build.py y .../alertas.py primero")
        return 1
    fixtures.mkdir(exist_ok=True)
    con = duckdb.connect(str(warehouse), read_only=True)
    ancho = max(len(n) for n, _ in tablas) + 9
    for nombre, sql in tablas:
        destino = fixtures / f"{nombre}.parquet"
        con.execute(f"COPY ({sql}) TO '{destino}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        n = con.execute(f"SELECT count(*) FROM '{destino}'").fetchone()[0]
        print(f"{destino.name:{ancho}s} {n:>7} filas  {destino.stat().st_size / 1024:.0f} KB")
    return 0
