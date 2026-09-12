"""Simulacion de la oferta economica.

Lo que se sabe del historico es solo la oferta GANADORA de cada proceso
(SECOP no publica las perdedoras) y cuantos oferentes hubo. Con eso:

  1. Se arma el pool de competidores probables: la distribucion empirica
     de la razon valor adjudicado / presupuesto oficial en procesos
     parecidos (misma entidad si hay muestra; si no, mismo departamento y
     familia UNSPSC; si no, la familia en todo el pais; si no, todo).
  2. Se simula: n competidores (n sale del historico) con razones tomadas
     al azar del pool, mas nuestra oferta. Para cada metodo se califica y
     se promedia; el puntaje esperado pondera cada metodo por su
     probabilidad (los centavos de la TRM).
  3. Se recorre una malla de precios y se devuelve el que maximiza el
     puntaje esperado, con el rango de precios que quedan a menos de un
     punto del maximo.

Pura salvo por el generador aleatorio, que se recibe (semilla fija en las
pruebas).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, asdict

from pliego.simulador.metodos import Version

PISO_MUESTRA = 10   # minimo de procesos para usar un nivel del pool


@dataclass
class Pool:
    nivel: str          # entidad | departamento_familia | familia | nacional
    descripcion: str
    ratios: list[float]
    oferentes: list[int]

    @property
    def n(self) -> int:
        return len(self.ratios)


@dataclass
class PuntoMalla:
    ratio: float
    esperado: float
    por_metodo: dict[str, float]
    prob_primero: float


@dataclass
class Recomendacion:
    ratio: float
    esperado: float
    rango: tuple[float, float]
    malla: list[PuntoMalla]
    pool: dict
    n_sim: int
    version: str

    def como_dict(self) -> dict:
        d = asdict(self)
        d["rango"] = list(self.rango)
        return d


# ------------------------------------------------------------------ pool
def armar_pool(historico: list[dict], proceso: dict, piso: int = PISO_MUESTRA,
               excluir_id: str | None = None) -> Pool:
    """Elige el nivel mas especifico que tenga al menos `piso` procesos con
    competencia real (>= 2 oferentes). `excluir_id` deja fuera un contrato
    (para el backtest: no mirar el proceso que se esta evaluando)."""
    filas = [h for h in historico if (h.get("n_oferentes_unicos") or 0) >= 2
             and h["modalidad"] == proceso["modalidad"] and h.get("id_contrato") != excluir_id]
    niveles = [
        ("entidad", "misma entidad (%s)" % proceso.get("entidad"),
         lambda h: h["nit_entidad"] == proceso.get("nit_entidad")),
        ("departamento_familia", "mismo departamento y familia UNSPSC %s" % proceso.get("familia"),
         lambda h: h["departamento"] == proceso.get("departamento") and h["familia"] == proceso.get("familia")),
        ("familia", "familia UNSPSC %s en todo el país" % proceso.get("familia"),
         lambda h: h["familia"] == proceso.get("familia")),
        ("nacional", "toda la modalidad en el país", lambda h: True),
    ]
    for nivel, desc, cond in niveles:
        sel = [h for h in filas if cond(h)]
        if len(sel) >= piso:
            return Pool(nivel, desc, [float(h["ratio"]) for h in sel], [int(h["n_oferentes_unicos"]) for h in sel])
    return Pool("nacional", "toda la modalidad en el país", [float(h["ratio"]) for h in filas],
                [int(h["n_oferentes_unicos"]) for h in filas])


# ------------------------------------------------------------- simulacion
def simular_escenarios(pool: Pool, n_sim: int, rng: random.Random, max_oferentes: int = 40) -> list[list[float]]:
    """Cada escenario es la lista de razones de los competidores. El numero
    de competidores se toma del historico (menos uno, que somos nosotros),
    acotado para que la simulacion no se dispare con procesos de 60 ofertas."""
    escenarios = []
    for _ in range(n_sim):
        n = min(max(1, rng.choice(pool.oferentes) - 1), max_oferentes)
        escenarios.append([rng.choice(pool.ratios) for _ in range(n)])
    return escenarios


def evaluar_precio(ratio: float, escenarios: list[list[float]], version: Version) -> PuntoMalla:
    por_metodo = {}
    primero = 0
    for m in version.metodos:
        total = 0.0
        for comp in escenarios:
            vals = comp + [ratio]
            total += version.puntaje(m, vals, ratio)
        por_metodo[m.clave] = total / len(escenarios)
    # probabilidad de quedar primero: promedio sobre metodos (ponderado por
    # su probabilidad) de la fraccion de escenarios donde nuestro puntaje es
    # el maximo del grupo
    for comp in escenarios:
        vals = comp + [ratio]
        p = 0.0
        for m in version.metodos:
            nuestro = version.puntaje(m, vals, ratio)
            mejor = max(version.puntaje(m, vals, x) for x in vals)
            p += m.probabilidad * (1.0 if nuestro >= mejor - 1e-9 else 0.0)
        primero += p
    esperado = sum(m.probabilidad * por_metodo[m.clave] for m in version.metodos)
    return PuntoMalla(ratio, esperado, por_metodo, primero / len(escenarios))


def recomendar(pool: Pool, version: Version, n_sim: int = 400, rng: random.Random | None = None,
               malla: list[float] | None = None, tolerancia: float = 1.0) -> Recomendacion:
    rng = rng or random.Random(7)
    malla = malla or [round(0.85 + i * 0.005, 3) for i in range(31)]   # 0,850 .. 1,000
    escenarios = simular_escenarios(pool, n_sim, rng)
    puntos = [evaluar_precio(r, escenarios, version) for r in malla]
    mejor = max(puntos, key=lambda p: p.esperado)
    cerca = [p.ratio for p in puntos if p.esperado >= mejor.esperado - tolerancia]
    return Recomendacion(mejor.ratio, mejor.esperado, (min(cerca), max(cerca)), puntos,
                         {"nivel": pool.nivel, "descripcion": pool.descripcion, "n": pool.n,
                          "mediana_ratio": _mediana(pool.ratios), "mediana_oferentes": _mediana(pool.oferentes)},
                         n_sim, version.clave)


# ---------------------------------------------------------------- backtest
@dataclass
class ResultadoBacktest:
    id_contrato: str
    entidad: str
    fecha: str
    precio_base: float
    ratio_ganador: float
    ratio_recomendado: float
    n_oferentes: int
    prob_primero: float          # con nuestra oferta recomendada, en escenarios simulados
    gana_al_ganador: float       # fraccion de metodos (ponderada) donde le ganamos al ganador real
    nivel_pool: str


def backtest(historico: list[dict], version: Version, n_procesos: int = 40, n_sim: int = 120,
             rng: random.Random | None = None, min_oferentes: int = 3) -> dict:
    """Sobre procesos historicos con competencia, recomienda el precio SIN
    mirar ese proceso (se excluye del pool) y mide dos cosas:

      prob_primero    en escenarios simulados con nuestra oferta dentro, con
                      que frecuencia quedamos primeros (promedio sobre metodos)
      gana_al_ganador la oferta recomendada, metida en un escenario simulado
                      junto con la oferta REAL que gano, obtiene mas puntaje
                      que ella (ponderado por la probabilidad de cada metodo)

    La segunda es la mas honesta que permite el dato publico: no conocemos
    las ofertas perdedoras, pero si la que gano, y contra esa nos medimos."""
    rng = rng or random.Random(11)
    candidatos = [h for h in historico if (h.get("n_oferentes_unicos") or 0) >= min_oferentes
                  and h.get("fecha_firma")]
    candidatos = sorted(candidatos, key=lambda h: str(h["fecha_firma"]))[-n_procesos:]
    resultados = []
    for h in candidatos:
        pool = armar_pool(historico, h, excluir_id=h["id_contrato"])
        rec = recomendar(pool, version, n_sim=n_sim, rng=rng)
        escenarios = simular_escenarios(pool, n_sim, rng)
        gana = 0.0
        for comp in escenarios:
            vals = comp + [rec.ratio, float(h["ratio"])]
            for m in version.metodos:
                if version.puntaje(m, vals, rec.ratio) >= version.puntaje(m, vals, float(h["ratio"])) - 1e-9:
                    gana += m.probabilidad
        punto = next(p for p in rec.malla if p.ratio == rec.ratio)
        resultados.append(ResultadoBacktest(
            h["id_contrato"], h["entidad"], str(h.get("fecha_firma")), float(h["precio_base"]), float(h["ratio"]),
            rec.ratio, int(h["n_oferentes_unicos"]), punto.prob_primero, gana / len(escenarios), pool.nivel))
    n = len(resultados)
    return {
        "n": n,
        "pct_primero": sum(r.prob_primero for r in resultados) / n if n else 0.0,
        "pct_gana_al_ganador": sum(r.gana_al_ganador for r in resultados) / n if n else 0.0,
        "resultados": [asdict(r) for r in resultados],
        "version": version.clave, "n_sim": n_sim,
    }


def _mediana(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
