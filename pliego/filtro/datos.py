"""Carga los datos del filtro en memoria y evalua.

Es la unica capa con IO del enfoque. Las filas vienen de pliego/comun/fuente:
los fixtures commiteados en pliego/filtro/fixtures/ (los genera semilla.py
desde el warehouse) o, con PLIEGO_FUENTE=croma, la API de Croma pasada por
la misma SQL de la semilla. El prototipo corre sin warehouse ni Postgres.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pliego.comun import contexto, fuente
from pliego.filtro import logica

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _filas(nombre: str) -> list[dict]:
    return fuente.filas("filtro", nombre)


def perfil() -> dict:
    """El de la empresa en contexto (plataforma) o el ficticio de los fixtures."""
    e = contexto.get()
    return e.perfil if e else _perfil_fixture()


@lru_cache(maxsize=1)
def _perfil_fixture() -> dict:
    return json.loads((FIXTURES / "perfil_constructora.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def procesos() -> list[dict]:
    return _filas("procesos_abiertos")


@lru_cache(maxsize=1)
def historial_entidades() -> dict[str, dict]:
    return {f["nit_entidad"]: f for f in _filas("entidades_historial")}


@lru_cache(maxsize=1)
def historial_familias() -> dict[tuple[str, str], dict]:
    return {(f["nit_entidad"], f["familia"]): f for f in _filas("entidad_familia")}


@lru_cache(maxsize=1)
def frecuencia_unspsc() -> dict[str, int]:
    return {f["unspsc"]: int(f["n"]) for f in _filas("unspsc_frecuencia")}


def evaluar_proceso(p: dict, perf: dict | None = None) -> logica.Evaluacion:
    perf = perf or perfil()
    nit = p.get("nit_entidad")
    fam = logica.familia(p.get("unspsc"))
    return logica.evaluar(
        perf, p,
        historial=historial_entidades().get(nit),
        hist_familia=historial_familias().get((nit, fam)) if fam else None,
        frecuencia_codigo=frecuencia_unspsc().get(p.get("unspsc"), 0),
    )


@lru_cache(maxsize=1)
def evaluaciones() -> list[dict]:
    """Todos los procesos abiertos evaluados contra el perfil, ordenados:
    presentarse primero, luego revisar, luego no presentarse; dentro de
    cada grupo por puntaje y luego por lo que cierra antes."""
    orden = {logica.PRESENTARSE: 0, logica.REVISAR: 1, logica.NO_PRESENTARSE: 2}
    salida = []
    for p in procesos():
        ev = evaluar_proceso(p)
        salida.append({**p, "evaluacion": ev.como_dict()})
    salida.sort(key=lambda x: (orden[x["evaluacion"]["recomendacion"]],
                               -x["evaluacion"]["puntaje"], x["fecha_cierre"] or ""))
    return salida


def por_id(id_proceso: str) -> dict | None:
    for x in evaluaciones():
        if x["id_del_proceso"] == id_proceso:
            return x
    return None


def resumen() -> dict:
    evs = evaluaciones()
    conteo = {logica.PRESENTARSE: 0, logica.REVISAR: 0, logica.NO_PRESENTARSE: 0}
    horas = 0
    for x in evs:
        conteo[x["evaluacion"]["recomendacion"]] += 1
        horas += x["evaluacion"]["horas_ahorradas"]
    return {"total": len(evs), "conteo": conteo, "horas_ahorradas": horas,
            "fecha_snapshot": fuente.hoy().isoformat(), "perfil": perfil()["nombre"]}
