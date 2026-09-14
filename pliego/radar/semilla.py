"""Fixtures del radar desde el warehouse de Plomada (solo lectura).

    python -m pliego.radar.semilla

  contratos.parquet   el universo de construccion con lo que hace falta para
                      perfilar entidades y competidores: quien gano, cuanto,
                      a que fraccion del presupuesto, con cuanta competencia,
                      y que le falta por ejecutar (saturacion)
  abiertos.parquet    procesos abiertos accionables (snapshot 2026-08-22)
"""
from __future__ import annotations

import sys
from pathlib import Path

from pliego.comun.semillas import exportar

FIXTURES = Path(__file__).resolve().parent / "fixtures"

CONTRATOS = """
SELECT id_contrato, nit_entidad, entidad, departamento, ciudad, orden, modalidad, tipo_contrato,
       unspsc, substr(unspsc, 4, 4) AS familia, left(descripcion, 120) AS descripcion,
       precio_base, valor_adjudicado,
       CASE WHEN precio_base > 0 AND valor_adjudicado > 0 THEN valor_adjudicado / precio_base END AS ratio,
       n_oferentes_unicos, fecha_firma, fecha_inicio, fecha_fin, estado, anio,
       doc_proveedor, proveedor, es_grupo, valor_plausible, valor_pagado, valor_pend_ejecucion
FROM base
WHERE doc_proveedor IS NOT NULL AND tipo_contrato IN ('OBRA', 'INTERVENTORIA', 'CONSULTORIA')
ORDER BY fecha_firma
"""

ABIERTOS = """
SELECT id_del_proceso, urlproceso, nit_entidad, entidad, departamento, ciudad, tipo_contrato, modalidad,
       unspsc, substr(unspsc, 4, 4) AS familia, descripcion, precio_base,
       n_invitados, n_manifestaron, n_respuestas, fecha_publicacion, fecha_cierre, dias_restantes
FROM alertas
WHERE universo = 'accionable' AND precio_base > 0
ORDER BY fecha_cierre
"""


def main() -> int:
    return exportar(FIXTURES, [("contratos", CONTRATOS), ("abiertos", ABIERTOS)])


if __name__ == "__main__":
    sys.exit(main())
