"""Carga de fixtures del checklist y verificacion por lote. Unica capa con IO."""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from pliego.checklist import logica

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PROCESO_ID = "SI-LP-004-2021"


@lru_cache(maxsize=1)
def extraccion() -> dict:
    return json.loads((FIXTURES / f"requisitos_{PROCESO_ID}.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def carpeta() -> dict:
    return json.loads((FIXTURES / "documentos_constructora.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def cajas() -> dict:
    f = FIXTURES / "citas_bbox.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def contexto() -> dict:
    p = extraccion()["proceso"]
    return {"smmlv": p["smmlv"], "anticipo_pct": p["anticipo_pct"], "fecha_cierre": date.fromisoformat(p["fecha_cierre"])}


def lote(n: int) -> dict | None:
    return next((lote_ for lote_ in extraccion()["proceso"]["lotes"] if lote_["n"] == n), None)


def verificaciones(n_lote: int) -> list[logica.Verificacion]:
    lote_ = lote(n_lote)
    if lote_ is None:
        raise KeyError(n_lote)
    return logica.verificar_todo(extraccion()["requisitos"], carpeta()["documentos"], contexto(), lote_)


def checklist(n_lote: int) -> dict:
    vs = verificaciones(n_lote)
    filas = []
    for v in vs:
        d = v.como_dict()
        d["caja"] = cajas().get(v.id)
        filas.append(d)
    return {"proceso": extraccion()["proceso"], "lote": lote(n_lote), "constructora": carpeta()["constructora"],
            "resumen": logica.resumen(vs), "requisitos": filas}


def requisito(id_req: str, n_lote: int) -> dict | None:
    return next((r for r in checklist(n_lote)["requisitos"] if r["id"] == id_req), None)
