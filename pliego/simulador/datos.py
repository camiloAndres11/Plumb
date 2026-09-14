"""Carga de datos del simulador y funciones de servicio (con cache).

Las filas vienen de pliego/comun/fuente: fixtures o Croma, mismo esquema.
"""
from __future__ import annotations

import random

from pliego.comun import cache, fuente
from pliego.simulador import logica
from pliego.simulador.metodos import VERSION_DEFECTO, VERSIONES


def _filas(nombre: str) -> list[dict]:
    return fuente.filas("simulador", nombre)


def fecha_snapshot():
    """La fecha de los datos que se muestran: la del snapshot con fixtures,
    la de hoy con Croma."""
    return fuente.hoy()


@cache.por_ambito()
def historico() -> list[dict]:
    return _filas("historico")


@cache.por_ambito()
def abiertos() -> list[dict]:
    return _filas("abiertos")


def proceso(id_proceso: str) -> dict | None:
    return next((a for a in abiertos() if a["id_del_proceso"] == id_proceso), None)


@cache.por_ambito(maxsize=64)
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


@cache.por_ambito(maxsize=4)
def backtest(version: str = VERSION_DEFECTO, n_procesos: int = 40, n_sim: int = 120) -> dict:
    return logica.backtest(historico(), VERSIONES[version], n_procesos=n_procesos, n_sim=n_sim,
                           rng=random.Random(11))
