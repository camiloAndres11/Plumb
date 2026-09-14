"""Genera los fixtures del filtro a partir del warehouse de Plomada.

Se corre UNA vez (o cuando se quiera refrescar) y sus salidas se commitean en
pliego/filtro/fixtures/, para que el prototipo y sus pruebas corran sin el
warehouse (300 MB, no versionado). Lee en modo solo-lectura: DuckDB admite
un solo escritor y este script no es el.

    python -m pliego.filtro.semilla            # usa data/warehouse/plomada.duckdb

Salidas (parquet, zstd):
  procesos_abiertos.parquet   los procesos del universo `accionable` del
                              snapshot 2026-08-22, con sus banderas (tabla `alertas`)
  entidades_historial.parquet agregados por entidad: quien gana, cuantas veces,
                              con cuanta competencia (tabla `base`)
  entidad_familia.parquet     lo mismo por entidad x familia UNSPSC (4 digitos)
  unspsc_frecuencia.parquet   cuantas veces aparece cada codigo UNSPSC en el
                              historico (para "codigo raro")
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[2]
WAREHOUSE = RAIZ / "legacy" / "plomada" / "data" / "warehouse" / "plomada.duckdb"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

PROCESOS = """
SELECT id_del_proceso, urlproceso, nit_entidad, entidad, departamento, ciudad,
       tipo_contrato, modalidad, unspsc, descripcion, precio_base,
       n_invitados, n_manifestaron, n_respuestas,
       fecha_publicacion, fecha_cierre, dias_ventana, dias_restantes,
       n_banderas, f_ventana_corta, f_al_tope_minima, f_historial_proponente_unico,
       f_sin_interes_a_tiempo, f_cierre_movido,
       ev_tasa_historica_entidad, ev_n_historico_entidad
FROM alertas
WHERE universo = 'accionable'
ORDER BY fecha_cierre, id_del_proceso
"""

# Solo contratos que vienen de un proceso competitivo con precio base: es
# donde tiene sentido hablar de "quien gana" y "con cuanta competencia".
ENTIDADES = """
WITH h AS (
  SELECT nit_entidad, entidad, doc_proveedor, proveedor, valor_plausible,
         n_oferentes_unicos, valor_adjudicado / precio_base AS ratio, anio
  FROM base
  WHERE precio_base > 0 AND valor_adjudicado > 0
    AND modalidad NOT LIKE 'CONTRATACION DIRECTA%'
),
top AS (
  SELECT nit_entidad, doc_proveedor, proveedor, count(*) AS n,
         row_number() OVER (PARTITION BY nit_entidad ORDER BY count(*) DESC, sum(valor_plausible) DESC) AS rk
  FROM h GROUP BY 1, 2, 3
)
SELECT h.nit_entidad, any_value(h.entidad) AS entidad,
       count(*) AS n_contratos,
       count(DISTINCT h.doc_proveedor) AS n_proveedores,
       any_value(t.proveedor) AS top1_proveedor,
       any_value(t.doc_proveedor) AS top1_doc,
       any_value(t.n) AS top1_n,
       any_value(t.n) * 1.0 / count(*) AS share_top1,
       avg(CASE WHEN h.n_oferentes_unicos <= 1 THEN 1 ELSE 0 END) AS tasa_proponente_unico,
       median(h.n_oferentes_unicos) AS mediana_oferentes,
       median(CASE WHEN h.ratio BETWEEN 0.5 AND 1.2 THEN h.ratio END) AS mediana_ratio_adjudicado,
       max(h.anio) AS ultimo_anio
FROM h LEFT JOIN top t ON t.nit_entidad = h.nit_entidad AND t.rk = 1
GROUP BY h.nit_entidad
"""

ENTIDAD_FAMILIA = """
WITH h AS (
  SELECT nit_entidad, substr(unspsc, 4, 4) AS familia, doc_proveedor, proveedor,
         n_oferentes_unicos
  FROM base
  WHERE precio_base > 0 AND valor_adjudicado > 0
    AND modalidad NOT LIKE 'CONTRATACION DIRECTA%'
    AND unspsc LIKE 'V1.%'
),
top AS (
  SELECT nit_entidad, familia, doc_proveedor, proveedor, count(*) AS n,
         row_number() OVER (PARTITION BY nit_entidad, familia ORDER BY count(*) DESC) AS rk
  FROM h GROUP BY 1, 2, 3, 4
)
SELECT h.nit_entidad, h.familia, count(*) AS n_contratos,
       count(DISTINCT h.doc_proveedor) AS n_proveedores,
       any_value(t.proveedor) AS top1_proveedor,
       any_value(t.n) * 1.0 / count(*) AS share_top1,
       avg(CASE WHEN h.n_oferentes_unicos <= 1 THEN 1 ELSE 0 END) AS tasa_proponente_unico
FROM h LEFT JOIN top t ON t.nit_entidad = h.nit_entidad AND t.familia = h.familia AND t.rk = 1
GROUP BY h.nit_entidad, h.familia
"""

UNSPSC = """
SELECT unspsc, count(*) AS n FROM base WHERE unspsc LIKE 'V1.%' GROUP BY 1
"""


def main() -> int:
    if not WAREHOUSE.exists():
        print(f"no existe {WAREHOUSE}; corre legacy/plomada/pipeline/build.py y .../alertas.py primero")
        return 1
    FIXTURES.mkdir(exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    for nombre, sql in [("procesos_abiertos", PROCESOS), ("entidades_historial", ENTIDADES),
                        ("entidad_familia", ENTIDAD_FAMILIA), ("unspsc_frecuencia", UNSPSC)]:
        destino = FIXTURES / f"{nombre}.parquet"
        con.execute(f"COPY ({sql}) TO '{destino}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        n = con.execute(f"SELECT count(*) FROM '{destino}'").fetchone()[0]
        print(f"{destino.name:32s} {n:>7} filas  {destino.stat().st_size/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
