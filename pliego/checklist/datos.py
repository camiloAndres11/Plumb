"""Carga de datos del checklist y verificacion por lote. Unica capa con IO.

Sin contexto (demo, pruebas) lee los fixtures: el pliego SI-LP-004-2021
extraido a mano y la carpeta ficticia. Con una empresa en contexto que
tenga un pliego elegido (pliego/comun/contexto.py, `pliego`), lee de ahi:
  contexto.pliego = {"requisitos": {...}, "citas_bbox": {...}, "carpeta": {...},
                     "dir": Path con p<N>.png, "pdf": Path}
"""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from pliego.checklist import logica
from pliego.comun import contexto as _ctx

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PROCESO_ID = "SI-LP-004-2021"   # el pliego de los fixtures; el generador usa el mismo
PDF_FIXTURE = FIXTURES / f"pliego_{PROCESO_ID}.pdf"
_elegido = _ctx.pliego


def extraccion() -> dict:
    p = _elegido()
    return p["requisitos"] if p else _extraccion_fixture()


@lru_cache(maxsize=1)
def _extraccion_fixture() -> dict:
    return json.loads((FIXTURES / f"requisitos_{PROCESO_ID}.json").read_text(encoding="utf-8"))


def carpeta() -> dict:
    p = _elegido()
    return p["carpeta"] if p else _carpeta_fixture()


@lru_cache(maxsize=1)
def _carpeta_fixture() -> dict:
    return json.loads((FIXTURES / "documentos_constructora.json").read_text(encoding="utf-8"))


def cajas() -> dict:
    p = _elegido()
    return p.get("citas_bbox") or {} if p else _cajas_fixture()


@lru_cache(maxsize=1)
def _cajas_fixture() -> dict:
    f = FIXTURES / "citas_bbox.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def ruta_pdf() -> Path:
    p = _elegido()
    return Path(p["pdf"]) if p else PDF_FIXTURE


def ruta_pagina(n: int) -> Path:
    p = _elegido()
    return (Path(p["dir"]) if p else FIXTURES / "paginas") / f"p{n}.png"


def contexto() -> dict:
    p = extraccion()["proceso"]
    # Sin fecha de cierre en el pliego (el cronograma suele ser un anexo) se
    # toma hoy: las vigencias se miden contra la fecha en que se revisa.
    cierre = date.fromisoformat(p["fecha_cierre"]) if p.get("fecha_cierre") else date.today()
    return {"smmlv": p["smmlv"], "anticipo_pct": p.get("anticipo_pct") or 0, "fecha_cierre": cierre}


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
