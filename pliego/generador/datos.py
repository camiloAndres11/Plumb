"""Carga de fixtures del generador (unica capa con IO)."""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from pliego.generador import logica

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PROCESO_ID = "SI-LP-004-2021"
# Fecha de cierre SIMULADA (el cronograma es el Anexo 2, no viene en el PDF).
FECHA_CIERRE = date(2021, 7, 6)


@lru_cache(maxsize=1)
def pliego() -> dict:
    p = json.loads((FIXTURES / f"pliego_{PROCESO_ID}.json").read_text(encoding="utf-8"))
    p["fecha_cierre"] = FECHA_CIERRE.isoformat()
    return p


@lru_cache(maxsize=1)
def perfil() -> dict:
    return json.loads((FIXTURES / "perfil_constructora.json").read_text(encoding="utf-8"))


def lote(n: int) -> dict | None:
    return next((lote_ for lote_ in pliego()["lotes"] if lote_["n"] == n), None)


@lru_cache(maxsize=8)
def documentos(n_lote: int) -> list[logica.Documento]:
    lote_ = lote(n_lote)
    if lote_ is None:
        raise KeyError(n_lote)
    return logica.generar_todo(pliego(), perfil(), lote_, FECHA_CIERRE)


def documento(id_doc: str, n_lote: int) -> logica.Documento | None:
    return next((d for d in documentos(n_lote) if d.id == id_doc), None)


def paquete(n_lote: int) -> dict:
    docs = documentos(n_lote)
    return {"proceso": {k: v for k, v in pliego().items() if k != "campos"}, "lote": lote(n_lote), "constructora": perfil()["nombre"],
            "resumen": logica.resumen(docs), "faltantes": logica.lo_que_falta(docs), "documentos": [d.como_dict() for d in docs]}
