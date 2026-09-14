"""Fixtures del simulador desde el warehouse de Plomada (solo lectura).

    python -m pliego.simulador.semilla

  historico.parquet   contratos de licitacion publica y seleccion abreviada de obra
                      con precio base, valor adjudicado y numero de oferentes: es la
                      unica huella publica de las ofertas (solo se conoce la ganadora)
  abiertos.parquet    procesos abiertos accionables de esas modalidades (snapshot 2026-08-22)
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[2]
WAREHOUSE = RAIZ / "legacy" / "plomada" / "data" / "warehouse" / "plomada.duckdb"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

MODALIDADES = "('LICITACION PUBLICA OBRA PUBLICA', 'SELECCION ABREVIADA DE MENOR CUANTIA')"

HISTORICO = f"""
SELECT id_contrato, notice_uid, nit_entidad, entidad, departamento, ciudad, modalidad,
       unspsc, substr(unspsc, 4, 4) AS familia, descripcion,
       precio_base, valor_adjudicado, valor_adjudicado / precio_base AS ratio,
       n_oferentes_unicos, n_respuestas, fecha_firma, fecha_cierre_ofertas, anio,
       doc_proveedor, proveedor
FROM base
WHERE modalidad IN {MODALIDADES} AND tipo_contrato = 'OBRA'
  AND precio_base > 0 AND valor_adjudicado > 0
  AND valor_adjudicado / precio_base BETWEEN 0.5 AND 1.05
ORDER BY fecha_firma
"""

ABIERTOS = f"""
SELECT id_del_proceso, urlproceso, nit_entidad, entidad, departamento, ciudad, modalidad,
       unspsc, substr(unspsc, 4, 4) AS familia, descripcion, precio_base,
       n_invitados, n_manifestaron, n_respuestas, fecha_publicacion, fecha_cierre, dias_restantes
FROM alertas
WHERE universo = 'accionable' AND tipo_contrato = 'OBRA' AND modalidad IN {MODALIDADES}
  AND precio_base > 0
ORDER BY fecha_cierre
"""


def main() -> int:
    if not WAREHOUSE.exists():
        print(f"no existe {WAREHOUSE}; corre legacy/plomada/pipeline/build.py y .../alertas.py primero")
        return 1
    FIXTURES.mkdir(exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    for nombre, sql in [("historico", HISTORICO), ("abiertos", ABIERTOS)]:
        destino = FIXTURES / f"{nombre}.parquet"
        con.execute(f"COPY ({sql}) TO '{destino}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        n = con.execute(f"SELECT count(*) FROM '{destino}'").fetchone()[0]
        print(f"{destino.name:20s} {n:>6} filas  {destino.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
