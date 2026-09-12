"""Perfiles de entidades y competidores, y competidores probables de un
proceso abierto. Puro: listas de dicts (contratos) -> dicts con cifras.

Todo sale del historico de contratos firmados (SECOP II). No hay datos de
oferentes perdedores: "se presenta" aqui significa "ha ganado", que es
la unica huella publica. Se dice en cada pantalla.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

ESTADOS_CERRADOS = {"TERMINADO", "CERRADO", "CANCELADO", "LIQUIDADO", "CEDIDO"}
ANIOS_RECIENTES = 3          # los contratos de los ultimos 3 anos pesan completo; los demas, la mitad
PISO_PERFIL = 5              # minimo de contratos para etiquetar una entidad


def _mediana(xs):
    s = sorted(x for x in xs if x is not None)
    n = len(s)
    if not n:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def _anio(c) -> int | None:
    if c.get("anio"):
        return int(c["anio"])
    f = c.get("fecha_firma")
    return int(str(f)[:4]) if f else None


def competitivo(c: dict) -> bool:
    """Un contrato ensena algo sobre 'quien gana' solo si vino de un proceso
    con presupuesto y no fue contratacion directa."""
    return bool(c.get("precio_base")) and c.get("precio_base") > 0 and c.get("valor_adjudicado") \
        and not str(c.get("modalidad", "")).startswith("CONTRATACION DIRECTA")


def en_ejecucion(c: dict, hoy: date) -> bool:
    if str(c.get("estado", "")).upper() in ESTADOS_CERRADOS:
        return False
    fin = c.get("fecha_fin")
    if fin:
        fin_d = date.fromisoformat(str(fin)[:10])
        return fin_d >= hoy
    return str(c.get("estado", "")).upper() in {"EN EJECUCION", "MODIFICADO", "SUSPENDIDO"}


# --------------------------------------------------------------- entidad
def perfil_entidad(contratos: list[dict], nit: str, hoy: date) -> dict | None:
    mios = [c for c in contratos if c.get("nit_entidad") == nit]
    if not mios:
        return None
    comp = [c for c in mios if competitivo(c)]
    por_prov: dict[str, list[dict]] = defaultdict(list)
    for c in comp:
        por_prov[c["doc_proveedor"]].append(c)
    n = len(comp)
    ganadores = []
    for doc, cs in por_prov.items():
        ganadores.append({
            "doc": doc, "nombre": cs[-1].get("proveedor"), "n": len(cs), "share": len(cs) / n if n else 0,
            "valor": sum(c.get("valor_plausible") or 0 for c in cs),
            "mediana_ratio": _mediana([c.get("ratio") for c in cs if c.get("ratio")]),
            "ultimo_anio": max((_anio(c) or 0) for c in cs),
            "es_grupo": any(str(c.get("es_grupo")).upper() == "SI" for c in cs),
        })
    ganadores.sort(key=lambda g: (-g["n"], -g["valor"]))
    hhi = sum(g["share"] ** 2 for g in ganadores)
    ratios = [c["ratio"] for c in comp if c.get("ratio") and 0.5 <= c["ratio"] <= 1.2]
    oferentes = [c["n_oferentes_unicos"] for c in comp if c.get("n_oferentes_unicos") is not None]
    tasa_unico = sum(1 for o in oferentes if o <= 1) / len(oferentes) if oferentes else None
    share_top1 = ganadores[0]["share"] if ganadores else 0
    med_of = _mediana(oferentes)
    if n < PISO_PERFIL:
        etiqueta, razon = "sin_muestra", "Menos de %d procesos competitivos: no se puede decir cómo adjudica." % PISO_PERFIL
    elif share_top1 >= 0.4 or hhi >= 0.25 or (tasa_unico or 0) >= 0.6:
        etiqueta = "predecible"
        razon = ("%s gana el %d %% de lo competitivo." % (ganadores[0]["nombre"], round(100 * share_top1)) if share_top1 >= 0.4 else
                 ("El %d %% de sus procesos tuvo un solo proponente." % round(100 * (tasa_unico or 0)) if (tasa_unico or 0) >= 0.6 else
                  "Pocos proveedores concentran la adjudicación (HHI %.2f)." % hhi))
    elif share_top1 < 0.2 and (med_of or 0) >= 5:
        etiqueta, razon = "abierta", "Ningún proveedor pasa del 20 %% y hay %d oferentes en la mitad de los procesos." % med_of
    else:
        etiqueta, razon = "intermedia", "Ni concentrada ni claramente abierta."
    por_anio = Counter(_anio(c) for c in comp if _anio(c))
    modalidades = Counter(c.get("modalidad") for c in mios)
    return {
        "nit": nit, "entidad": mios[-1].get("entidad"), "departamento": mios[-1].get("departamento"),
        "ciudad": mios[-1].get("ciudad"), "orden": mios[-1].get("orden"),
        "n_contratos": len(mios), "n_competitivos": n, "valor_total": sum(c.get("valor_plausible") or 0 for c in mios),
        "n_proveedores": len(por_prov), "ganadores": ganadores[:10],
        "share_top1": share_top1, "hhi": hhi, "tasa_proponente_unico": tasa_unico,
        "mediana_oferentes": med_of, "mediana_ratio": _mediana(ratios),
        "margen_mediano": (1 - _mediana(ratios)) if ratios else None,
        "etiqueta": etiqueta, "razon": razon,
        "por_anio": dict(sorted(por_anio.items())), "modalidades": modalidades.most_common(5),
        "familias": Counter(c.get("familia") for c in comp if c.get("familia")).most_common(5),
    }


# ------------------------------------------------------------ competidor
def perfil_competidor(contratos: list[dict], doc: str, hoy: date) -> dict | None:
    mios = [c for c in contratos if c.get("doc_proveedor") == doc]
    if not mios:
        return None
    comp = [c for c in mios if competitivo(c)]
    ejec = [c for c in mios if en_ejecucion(c, hoy)]
    saldo = sum(c.get("valor_pend_ejecucion") or 0 for c in ejec)
    anios = [a for a in (_anio(c) for c in mios) if a]
    primer, ultimo = (min(anios), max(anios)) if anios else (None, None)
    span = max(1, (ultimo - primer + 1)) if anios else 1
    valor_total = sum(c.get("valor_plausible") or 0 for c in mios)
    valor_anual = valor_total / span
    saturacion = saldo / valor_anual if valor_anual else 0.0
    if saturacion >= 2:
        nivel, razon_sat = "saturado", "Tiene %s de saldo por ejecutar, más de dos años de su ritmo (%s al año)." % (_mill(saldo), _mill(valor_anual))
    elif saturacion >= 1:
        nivel, razon_sat = "cargado", "Saldo por ejecutar de %s, cerca de un año de su ritmo." % _mill(saldo)
    else:
        nivel, razon_sat = "con_capacidad", "Saldo por ejecutar de %s frente a %s al año." % (_mill(saldo), _mill(valor_anual))
    ratios = [c["ratio"] for c in comp if c.get("ratio") and 0.5 <= c["ratio"] <= 1.2]
    entidades = Counter((c.get("nit_entidad"), c.get("entidad")) for c in comp)
    return {
        "doc": doc, "nombre": mios[-1].get("proveedor"), "es_grupo": any(str(c.get("es_grupo")).upper() == "SI" for c in mios),
        "n_contratos": len(mios), "n_competitivos": n_c(comp), "valor_total": valor_total,
        "n_obra": sum(1 for c in mios if c.get("tipo_contrato") == "OBRA"),
        "n_interventoria": sum(1 for c in mios if c.get("tipo_contrato") == "INTERVENTORIA"),
        "primer_anio": primer, "ultimo_anio": ultimo,
        "mediana_ratio": _mediana(ratios), "ratios_recientes": sorted(ratios)[-12:],
        "entidades": [{"nit": k[0], "entidad": k[1], "n": v} for k, v in entidades.most_common(8)],
        "departamentos": Counter(c.get("departamento") for c in mios).most_common(5),
        "familias": Counter(c.get("familia") for c in mios if c.get("familia")).most_common(5),
        "en_ejecucion": [{"id": c["id_contrato"], "entidad": c.get("entidad"), "objeto": c.get("descripcion"),
                          "saldo": c.get("valor_pend_ejecucion") or 0, "fecha_fin": str(c.get("fecha_fin") or "")}
                         for c in sorted(ejec, key=lambda c: -(c.get("valor_pend_ejecucion") or 0))[:8]],
        "n_en_ejecucion": len(ejec), "saldo_pendiente": saldo, "valor_anual": valor_anual,
        "saturacion": saturacion, "nivel_saturacion": nivel, "razon_saturacion": razon_sat,
    }


def n_c(xs):
    return len(xs)


# ------------------------------------------------- competidores probables
def competidores_probables(contratos: list[dict], proceso: dict, hoy: date, n: int = 10,
                           perfiles: dict[str, dict] | None = None) -> list[dict]:
    """Puntaje por proveedor: 3 por cada contrato competitivo ganado en la
    misma entidad, 1 por cada uno en el mismo departamento y familia, 0,5
    por cada uno en la familia en todo el pais (tope 6 contratos: los grandes nacionales no deben tapar a los locales). Los contratos de
    hace mas de ANIOS_RECIENTES anos pesan la mitad. La saturacion resta
    hasta un 50 %. Se devuelve el peso normalizado (suma 1) como
    'probabilidad de que se presente' -- es un orden, no una probabilidad
    calibrada, y asi se rotula."""
    nit, dep, fam = proceso.get("nit_entidad"), proceso.get("departamento"), proceso.get("familia")
    puntos: dict[str, float] = defaultdict(float)
    razones: dict[str, Counter] = defaultdict(Counter)
    nombres: dict[str, str] = {}
    for c in contratos:
        if not competitivo(c):
            continue
        doc = c["doc_proveedor"]
        a = _anio(c)
        peso = 1.0 if a and a >= hoy.year - ANIOS_RECIENTES else 0.5
        if c.get("nit_entidad") == nit:
            puntos[doc] += 3 * peso; razones[doc]["entidad"] += 1
        elif c.get("departamento") == dep and c.get("familia") == fam and fam:
            puntos[doc] += 1 * peso; razones[doc]["departamento_familia"] += 1
        elif c.get("familia") == fam and fam:
            if razones[doc]["familia"] < 6:
                puntos[doc] += 0.5 * peso; razones[doc]["familia"] += 1
        else:
            continue
        nombres[doc] = c.get("proveedor")
    if not puntos:
        return []
    salida = []
    for doc, p in puntos.items():
        perfil = (perfiles or {}).get(doc) or perfil_competidor(contratos, doc, hoy)
        sat = perfil["saturacion"] if perfil else 0.0
        ajuste = 1 - min(0.5, sat / 4)
        salida.append({"doc": doc, "nombre": nombres[doc], "puntos": p * ajuste, "puntos_brutos": p,
                       "razones": dict(razones[doc]), "saturacion": sat,
                       "nivel_saturacion": perfil["nivel_saturacion"] if perfil else None,
                       "mediana_ratio": perfil["mediana_ratio"] if perfil else None,
                       "n_contratos": perfil["n_contratos"] if perfil else None})
    salida.sort(key=lambda x: -x["puntos"])
    top = salida[:n]
    total = sum(x["puntos"] for x in top)
    for x in top:
        x["peso"] = x["puntos"] / total if total else 0
    return top


def _mill(x) -> str:
    return "$%s mill." % f"{(x or 0) / 1e6:,.0f}".replace(",", ".")
