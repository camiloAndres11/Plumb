"""Carga de fixtures del radar e indices en memoria (unica capa con IO)."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from functools import lru_cache
from pathlib import Path

import duckdb

from pliego.radar import logica

FIXTURES = Path(__file__).resolve().parent / "fixtures"
HOY = date(2026, 8, 22)     # fecha del snapshot de abiertos; el prototipo la trata como hoy


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
def contratos() -> list[dict]:
    return _filas("contratos.parquet")


@lru_cache(maxsize=1)
def abiertos() -> list[dict]:
    return _filas("abiertos.parquet")


@lru_cache(maxsize=1)
def _por_entidad() -> dict[str, list[dict]]:
    d = defaultdict(list)
    for c in contratos():
        d[c["nit_entidad"]].append(c)
    return d


@lru_cache(maxsize=1)
def _por_proveedor() -> dict[str, list[dict]]:
    d = defaultdict(list)
    for c in contratos():
        d[c["doc_proveedor"]].append(c)
    return d


@lru_cache(maxsize=512)
def entidad(nit: str, tipo: str | None = "OBRA") -> dict | None:
    return logica.perfil_entidad(_por_entidad().get(nit, []), nit, HOY, tipo)


@lru_cache(maxsize=512)
def competidor(doc: str) -> dict | None:
    return logica.perfil_competidor(_por_proveedor().get(doc, []), doc, HOY)


def proceso(id_proceso: str) -> dict | None:
    return next((a for a in abiertos() if a["id_del_proceso"] == id_proceso), None)


@lru_cache(maxsize=256)
def competidores_de(id_proceso: str, n: int = 10) -> list[dict]:
    p = proceso(id_proceso)
    if p is None:
        raise KeyError(id_proceso)
    # Solo los contratos que pueden puntuar: misma entidad o misma familia.
    cand = [c for c in contratos() if c.get("nit_entidad") == p["nit_entidad"] or (p.get("familia") and c.get("familia") == p["familia"])]
    top = logica.competidores_probables(cand, p, HOY, n=n, perfiles=None)
    # los perfiles se calculan sobre TODO el historico del proveedor (saturacion real)
    for x in top:
        perf = competidor(x["doc"])
        if perf:
            x.update({"saturacion": perf["saturacion"], "nivel_saturacion": perf["nivel_saturacion"],
                      "mediana_ratio": perf["mediana_ratio"], "n_contratos": perf["n_contratos"]})
    return top


@lru_cache(maxsize=1)
def entidades_mas_activas(n: int = 40) -> list[dict]:
    cnt = Counter()
    nombres = {}
    for c in contratos():
        if logica.competitivo(c):
            cnt[c["nit_entidad"]] += 1
            nombres[c["nit_entidad"]] = (c.get("entidad"), c.get("departamento"))
    return [{"nit": k, "entidad": nombres[k][0], "departamento": nombres[k][1], "n": v} for k, v in cnt.most_common(n)]


@lru_cache(maxsize=1)
def competidores_mas_activos(n: int = 40) -> list[dict]:
    cnt = Counter()
    nombres = {}
    for c in contratos():
        if logica.competitivo(c):
            cnt[c["doc_proveedor"]] += 1
            nombres[c["doc_proveedor"]] = c.get("proveedor")
    return [{"doc": k, "nombre": nombres[k], "n": v} for k, v in cnt.most_common(n)]


def buscar(q: str, n: int = 20) -> dict:
    q = q.lower().strip()
    ents, provs, seen_e, seen_p = [], [], set(), set()
    if len(q) < 3:
        return {"entidades": [], "competidores": []}
    for c in contratos():
        e, pnom = (c.get("entidad") or "").lower(), (c.get("proveedor") or "").lower()
        if q in e and c["nit_entidad"] not in seen_e:
            seen_e.add(c["nit_entidad"]); ents.append({"nit": c["nit_entidad"], "entidad": c.get("entidad"), "departamento": c.get("departamento")})
        if q in pnom and c["doc_proveedor"] not in seen_p:
            seen_p.add(c["doc_proveedor"]); provs.append({"doc": c["doc_proveedor"], "nombre": c.get("proveedor")})
        if len(ents) >= n and len(provs) >= n:
            break
    return {"entidades": ents[:n], "competidores": provs[:n]}
