"""Carga de datos del generador (unica capa con IO).

Sin contexto (demo, pruebas) lee los fixtures. Con una empresa en contexto
que tenga un pliego elegido (pliego/comun/contexto.py), el pliego es
contexto.pliego["extraccion"] y el perfil el de la empresa.
"""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from pliego.comun import contexto as _ctx
from pliego.generador import logica

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PROCESO_ID = "SI-LP-004-2021"
# Fecha de cierre SIMULADA (el cronograma es el Anexo 2, no viene en el PDF).
FECHA_CIERRE = date(2021, 7, 6)


def _elegido() -> dict | None:
    e = _ctx.get()
    return e.pliego if e and e.pliego else None


def pliego() -> dict:
    p = _elegido()
    if p:
        d = dict(p["extraccion"])
        d.setdefault("fecha_cierre", None)
        return d
    return _pliego_fixture()


@lru_cache(maxsize=1)
def _pliego_fixture() -> dict:
    p = json.loads((FIXTURES / f"pliego_{PROCESO_ID}.json").read_text(encoding="utf-8"))
    p["fecha_cierre"] = FECHA_CIERRE.isoformat()
    return p


def perfil() -> dict:
    e = _ctx.get()
    return e.perfil if e else _perfil_fixture()


@lru_cache(maxsize=1)
def _perfil_fixture() -> dict:
    return json.loads((FIXTURES / "perfil_constructora.json").read_text(encoding="utf-8"))


def fecha_cierre() -> date:
    p = pliego()
    return date.fromisoformat(p["fecha_cierre"]) if p.get("fecha_cierre") else date.today()


def ruta_pdf() -> Path:
    p = _elegido()
    return Path(p["pdf"]) if p else FIXTURES / _pliego_fixture()["pdf"]


def proceso_id() -> str:
    return pliego().get("id") or PROCESO_ID


def lote(n: int) -> dict | None:
    return next((lote_ for lote_ in pliego()["lotes"] if lote_["n"] == n), None)


def documentos(n_lote: int) -> list[logica.Documento]:
    lote_ = lote(n_lote)
    if lote_ is None:
        raise KeyError(n_lote)
    return logica.generar_todo(pliego(), perfil(), lote_, fecha_cierre())


def documento(id_doc: str, n_lote: int) -> logica.Documento | None:
    return next((d for d in documentos(n_lote) if d.id == id_doc), None)


def paquete(n_lote: int) -> dict:
    docs = documentos(n_lote)
    return {"proceso": {k: v for k, v in pliego().items() if k != "campos"}, "lote": lote(n_lote), "constructora": perfil()["nombre"],
            "resumen": logica.resumen(docs), "faltantes": logica.lo_que_falta(docs), "documentos": [d.como_dict() for d in docs]}
