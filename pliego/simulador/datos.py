"""Carga de fixtures del simulador y funciones de servicio (con cache)."""
from __future__ import annotations

import random
from datetime import date
from functools import lru_cache
from pathlib import Path

import duckdb

from pliego.simulador import logica
from pliego.simulador.metodos import VERSIONES, VERSION_DEFECTO

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FECHA_SNAPSHOT = date(2026, 8, 22)


def _filas(nombre: str) -> list[dict]:
    cur = duckdb.connect().execute(f"SELECT * FROM '{FIXTURES / nombre}'")
    cols = [d[0] for d in cur.description]
    out = []
    for t in cur.fetchall():
        f = dict(zip(cols, t))
        for k, v in f.items():
            if isinstance(v, date):
                f[k] = v.isoformat()
        out.append(f)
    return out


@lru_cache(maxsize=1)
def historico() -> list[dict]:
    return _filas("historico.parquet")


@lru_cache(maxsize=1)
def abiertos() -> list[dict]:
    return _filas("abiertos.parquet")


def proceso(id_proceso: str) -> dict | None:
    return next((a for a in abiertos() if a["id_del_proceso"] == id_proceso), None)


@lru_cache(maxsize=64)
def recomendar_para(id_proceso: str, version: str = VERSION_DEFECTO, n_sim: int = 400) -> dict:
    p = proceso(id_proceso)
    if p is None:
        raise KeyError(id_proceso)
    v = VERSIONES[version]
    pool = logica.armar_pool(historico(), p)
    rec = logica.recomendar(pool, v, n_sim=n_sim, rng=random.Random(hash(id_proceso) % 10_000))
    d = rec.como_dict()
    d["proceso"] = p
    d["precio_recomendado"] = rec.ratio * p["precio_base"]
    d["rango_pesos"] = [rec.rango[0] * p["precio_base"], rec.rango[1] * p["precio_base"]]
    d["metodos"] = [{"clave": m.clave, "nombre": m.nombre, "probabilidad": m.probabilidad,
                     "centavos": [m.centavos_desde, m.centavos_hasta]} for m in v.metodos]
    return d


@lru_cache(maxsize=4)
def backtest(version: str = VERSION_DEFECTO, n_procesos: int = 40, n_sim: int = 120) -> dict:
    return logica.backtest(historico(), VERSIONES[version], n_procesos=n_procesos, n_sim=n_sim,
                           rng=random.Random(11))
