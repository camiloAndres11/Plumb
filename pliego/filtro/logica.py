"""Elegibilidad y recomendacion: presentarse / no presentarse / revisar.

Pura: recibe dicts (perfil, proceso, historial de la entidad) y devuelve
una Evaluacion. Sin IO, sin SQL. Todo lo que decide sale con su razon y
la cifra que la sustenta, en el mismo espiritu de Plomada: sin evidencia
no se publica.

Dos capas:
  1. Habilitantes (duras): si una falla, la recomendacion es NO
     presentarse, sin importar lo demas. Si falta el dato, es REVISAR.
  2. Senales (blandas): suman o restan al puntaje que parte de 50.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from pliego.filtro import reglas as R

PRESENTARSE = "presentarse"
NO_PRESENTARSE = "no_presentarse"
REVISAR = "revisar"


@dataclass
class Razon:
    codigo: str
    texto: str
    cumple: bool | None      # None = no se pudo evaluar (dato faltante)
    evidencia: dict = field(default_factory=dict)
    habilitante: bool = False
    peso: int = 0


@dataclass
class Evaluacion:
    id_proceso: str
    recomendacion: str
    puntaje: int
    razones: list[Razon]
    horas_ahorradas: int

    def como_dict(self) -> dict:
        return asdict(self)


# ----------------------------------------------------------------- utiles
def familia(unspsc: str | None) -> str | None:
    """'V1.72141000' -> '7214'. Los codigos UNSPSC son jerarquicos:
    segmento (2), familia (4), clase (6), producto (8)."""
    if not unspsc or not unspsc.startswith("V1.") or len(unspsc) < 7:
        return None
    return unspsc[3:7]


def smmlv(cop: float | None) -> float | None:
    return None if cop is None else cop / R.SMMLV


def experiencia_en_familia(perfil: dict, fam: str | None) -> float:
    """SMMLV acreditados en contratos de la misma familia UNSPSC."""
    if fam is None:
        return 0.0
    return float(sum(e["valor_smmlv"] for e in perfil.get("experiencia", [])
                     if familia(e.get("unspsc")) == fam))


def horas_de(modalidad: str | None) -> int:
    return R.HORAS_POR_MODALIDAD.get(modalidad or "", R.HORAS_DEFECTO)


# ------------------------------------------------------------ habilitantes
def habilitantes(perfil: dict, proceso: dict) -> list[Razon]:
    razones: list[Razon] = []
    fam = familia(proceso.get("unspsc"))
    mis_familias = {familia(u) for u in perfil.get("unspsc", [])} - {None}

    # 1. Objeto: la familia UNSPSC del proceso esta entre las que trabaja
    if fam is None:
        razones.append(Razon("objeto", "El proceso no publica un codigo UNSPSC legible; "
                             "no se puede saber si es su tipo de obra.", None,
                             {"unspsc": proceso.get("unspsc")}, habilitante=True))
    else:
        ok = fam in mis_familias
        razones.append(Razon(
            "objeto",
            ("El objeto es de su tipo de obra (familia UNSPSC %s)." % fam) if ok else
            ("El objeto no es de su tipo de obra: familia UNSPSC %s, y usted trabaja %s."
             % (fam, ", ".join(sorted(mis_familias)))),
            ok, {"familia": fam, "familias_perfil": sorted(mis_familias)}, habilitante=True))

    # 2. RUP vigente
    rup = perfil.get("rup", {}).get("vigente")
    razones.append(Razon("rup", "RUP vigente." if rup else "El RUP no esta vigente: sin el no "
                         "se puede acreditar nada.", bool(rup), {"vigente": rup}, habilitante=True))

    # 3. Capacidad residual >= presupuesto oficial
    kr = perfil.get("capacidad_residual")
    pb = proceso.get("precio_base")
    if kr is None or not pb:
        razones.append(Razon("capacidad_residual", "Falta el presupuesto oficial o su capacidad "
                             "residual.", None, {"capacidad_residual": kr, "precio_base": pb},
                             habilitante=True))
    else:
        ok = kr >= pb
        razones.append(Razon(
            "capacidad_residual",
            "Su capacidad residual cubre el %d %% del presupuesto oficial." % round(100 * kr / pb)
            if ok else
            "Su capacidad residual (%s) no alcanza el presupuesto oficial (%s)." % (_mill(kr), _mill(pb)),
            ok, {"capacidad_residual": kr, "precio_base": pb, "cobertura": kr / pb}, habilitante=True))

    # 4. Experiencia en la familia >= fraccion del presupuesto en SMMLV
    if fam is not None and pb:
        req = smmlv(pb) * R.EXPERIENCIA_FRACCION_MIN
        acred = experiencia_en_familia(perfil, fam)
        ok = acred >= req
        razones.append(Razon(
            "experiencia",
            "Acredita %s SMMLV en obras de esta familia; el pliego tipo pide %s." % (_n(acred), _n(req))
            if ok else
            "Acredita %s SMMLV en esta familia y el pliego tipo pediria %s: le faltan %s."
            % (_n(acred), _n(req), _n(req - acred)),
            ok, {"acreditada_smmlv": acred, "requerida_smmlv": req, "familia": fam}, habilitante=True))

    # 5. Indicadores financieros y organizacionales
    f = perfil.get("financiero", {})
    o = perfil.get("organizacional", {})
    checks = [
        ("liquidez", f.get("liquidez"), R.LIQUIDEZ_MIN, ">="),
        ("endeudamiento", f.get("endeudamiento"), R.ENDEUDAMIENTO_MAX, "<="),
        ("cobertura_intereses", f.get("cobertura_intereses"), R.COBERTURA_INTERESES_MIN, ">="),
        ("rentabilidad_patrimonio", o.get("rentabilidad_patrimonio"), R.RENTABILIDAD_PATRIMONIO_MIN, ">="),
        ("rentabilidad_activo", o.get("rentabilidad_activo"), R.RENTABILIDAD_ACTIVO_MIN, ">="),
    ]
    fallan = [(k, v, u, op) for k, v, u, op in checks
              if v is not None and not (v >= u if op == ">=" else v <= u)]
    faltan = [k for k, v, _, _ in checks if v is None]
    if faltan:
        razones.append(Razon("financiero", "Faltan indicadores financieros: %s." % ", ".join(faltan),
                             None, {"faltan": faltan}, habilitante=True))
    elif fallan:
        razones.append(Razon("financiero", "No cumple %s." % "; ".join(
            "%s %s (pide %s %s)" % (k, _n(v), op, _n(u)) for k, v, u, op in fallan),
            False, {"fallan": [k for k, *_ in fallan]}, habilitante=True))
    else:
        razones.append(Razon("financiero", "Cumple los indicadores financieros y organizacionales "
                             "usuales de los documentos tipo.", True,
                             {k: v for k, v, _, _ in checks}, habilitante=True))
    return razones


# ----------------------------------------------------------------- senales
def senales(perfil: dict, proceso: dict, historial: dict | None,
            hist_familia: dict | None, frecuencia_codigo: int | None) -> list[Razon]:
    r: list[Razon] = []

    def add(codigo, texto, cumple, evidencia):
        r.append(Razon(codigo, texto, cumple, evidencia, peso=R.PESOS[codigo]))

    # Region
    dep = proceso.get("departamento")
    if dep in perfil.get("departamentos_interes", []):
        add("departamento_interes", "Esta en una de sus regiones (%s)." % dep, True, {"departamento": dep})
    else:
        add("fuera_de_region", "Esta fuera de sus regiones: %s." % dep, False, {"departamento": dep})

    # Cuantia objetivo
    pb = proceso.get("precio_base") or 0
    rango = perfil.get("cuantia_objetivo", {})
    if rango and rango.get("min", 0) <= pb <= rango.get("max", float("inf")):
        add("cuantia_objetivo", "El presupuesto (%s) esta en su rango objetivo." % _mill(pb), True,
            {"precio_base": pb})
    elif rango:
        add("cuantia_fuera_rango", "El presupuesto (%s) esta fuera de su rango objetivo (%s a %s)."
            % (_mill(pb), _mill(rango.get("min")), _mill(rango.get("max"))), False, {"precio_base": pb})

    # Holguras
    fam = familia(proceso.get("unspsc"))
    if fam and pb:
        req = smmlv(pb) * R.EXPERIENCIA_FRACCION_MIN
        acred = experiencia_en_familia(perfil, fam)
        if req and acred >= 2 * req:
            add("experiencia_holgada", "Acredita mas del doble de la experiencia requerida.", True,
                {"acreditada_smmlv": acred, "requerida_smmlv": req})
        kr = perfil.get("capacidad_residual") or 0
        if kr >= 1.5 * pb:
            add("capacidad_holgada", "Su capacidad residual cubre el %d %% del presupuesto." % round(100 * kr / pb),
                True, {"cobertura": kr / pb})

    # Historico de la entidad
    if historial and historial.get("n_contratos", 0) >= R.GANADOR_RECURRENTE_N:
        share = historial.get("share_top1") or 0
        tasa = historial.get("tasa_proponente_unico") or 0
        med = historial.get("mediana_oferentes") or 0
        if share >= R.GANADOR_RECURRENTE_SHARE:
            add("ganador_recurrente",
                "En esta entidad %s gano %d de %d procesos competitivos (%d %%)."
                % (historial.get("top1_proveedor"), historial.get("top1_n", 0),
                   historial["n_contratos"], round(100 * share)),
                False, {"share_top1": share, "top1_proveedor": historial.get("top1_proveedor"),
                        "n_contratos": historial["n_contratos"]})
        if tasa >= R.ENTIDAD_CERRADA_TASA:
            add("entidad_cerrada", "El %d %% de lo que adjudica esta entidad tuvo un solo proponente."
                % round(100 * tasa), False, {"tasa_proponente_unico": tasa})
        if med >= R.MUCHA_COMPETENCIA_MEDIANA:
            add("mucha_competencia", "Aqui se presentan %d oferentes en la mitad de los procesos."
                % med, False, {"mediana_oferentes": med})
        if share < 0.25 and tasa < 0.5 and 2 <= med < R.MUCHA_COMPETENCIA_MEDIANA:
            add("entidad_competitiva",
                "Entidad con competencia real: %d proveedores distintos en %d procesos, "
                "ninguno domina." % (historial.get("n_proveedores", 0), historial["n_contratos"]),
                True, {"n_proveedores": historial.get("n_proveedores"), "share_top1": share})
    # Ganador recurrente en la familia especifica, aunque la entidad en general sea abierta
    if hist_familia and hist_familia.get("n_contratos", 0) >= R.GANADOR_RECURRENTE_N \
            and not any(x.codigo == "ganador_recurrente" for x in r):
        share = hist_familia.get("share_top1") or 0
        if share >= R.GANADOR_RECURRENTE_SHARE:
            add("ganador_recurrente",
                "En obras de esta familia, %s gano el %d %% de los %d procesos de la entidad."
                % (hist_familia.get("top1_proveedor"), round(100 * share), hist_familia["n_contratos"]),
                False, {"share_top1": share, "familia": hist_familia.get("familia")})

    # Pliego con requisitos muy especificos (proxy: el codigo casi no se usa)
    if frecuencia_codigo is not None and str(proceso.get("unspsc") or "").startswith("V1.") \
            and frecuencia_codigo < R.CODIGO_RARO_N:
        add("codigo_raro", "El codigo UNSPSC del proceso aparece solo %d veces en todo el historico: "
            "revise si el pliego pide una experiencia a la medida." % frecuencia_codigo, False,
            {"frecuencia": frecuencia_codigo})

    # Tiempos
    if proceso.get("f_ventana_corta"):
        add("ventana_corta", "El plazo para ofertar (%s dias) es mas corto que el usual de su modalidad."
            % proceso.get("dias_ventana"), False, {"dias_ventana": proceso.get("dias_ventana"),
                                                    "p10": proceso.get("ev_ventana_p10_modalidad")})
    dr = proceso.get("dias_restantes")
    if dr is not None and dr <= R.PLAZO_CORTO_DIAS:
        add("plazo_corto", "Cierra en %d dias: no alcanza a armar una propuesta completa." % dr,
            False, {"dias_restantes": dr})
    if proceso.get("f_sin_interes_a_tiempo"):
        add("sin_interes_cerca_del_cierre", "Nadie ha manifestado interes y cierra en una semana o menos: "
            "puede ser oportunidad o un pliego a la medida de alguien.", None, {})
    if proceso.get("f_cierre_movido"):
        add("cierre_movido", "La fecha de cierre cambio desde el snapshot anterior.", None, {})
    return r


# ----------------------------------------------------------------- puntaje
def evaluar(perfil: dict, proceso: dict, historial: dict | None = None,
            hist_familia: dict | None = None, frecuencia_codigo: int | None = None) -> Evaluacion:
    hab = habilitantes(perfil, proceso)
    sen = senales(perfil, proceso, historial, hist_familia, frecuencia_codigo)

    puntaje = 50 + sum(s.peso for s in sen if s.cumple is not None)
    puntaje = max(0, min(100, puntaje))

    if any(h.cumple is False for h in hab):
        rec = NO_PRESENTARSE
    elif any(h.cumple is None for h in hab):
        rec = REVISAR
    elif puntaje >= R.PRESENTARSE_MIN:
        rec = PRESENTARSE
    elif puntaje < R.NO_PRESENTARSE_MAX:
        rec = NO_PRESENTARSE
    else:
        rec = REVISAR

    horas = horas_de(proceso.get("modalidad")) if rec == NO_PRESENTARSE else 0
    return Evaluacion(proceso.get("id_del_proceso", ""), rec, puntaje, hab + sen, horas)


# ---------------------------------------------------------------- formato
def _mill(x) -> str:
    if x is None:
        return "sin dato"
    return "$%s mill." % f"{x / 1e6:,.0f}".replace(",", ".")


def _n(x) -> str:
    return f"{x:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") if isinstance(x, float) \
        else str(x)
