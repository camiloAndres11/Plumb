"""Verificacion de cada requisito habilitante contra la carpeta de documentos.

Pura: recibe el requisito (dict del JSON extraido), el lote elegido, los
documentos de la constructora y el contexto del proceso; devuelve una
Verificacion con uno de cuatro estados:

  cumple            el documento esta y el dato satisface la regla
  no_cumple         el documento esta pero el dato no satisface la regla
  falta_documento   no hay documento que permita verificarlo
  revisar           hace falta juicio humano, o el umbral no viene en el pliego

Cada verificacion lleva la evidencia numerica y la pagina del pliego de
donde salio el requisito: sin evidencia no se publica.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, timedelta

CUMPLE, NO_CUMPLE, FALTA, REVISAR = "cumple", "no_cumple", "falta_documento", "revisar"
ORDEN_ESTADO = {NO_CUMPLE: 0, FALTA: 1, REVISAR: 2, CUMPLE: 3}


@dataclass
class Verificacion:
    id: str
    categoria: str
    titulo: str
    estado: str
    detalle: str
    pagina: int
    seccion: str
    cita: str
    evidencia: dict = field(default_factory=dict)
    documento: str | None = None

    def como_dict(self) -> dict:
        return asdict(self)


def _fecha(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


def _smmlv(cop: float, smmlv: int) -> float:
    return cop / smmlv


# ------------------------------------------------------------ reglas
def _documento(req, doc, ctx):
    if doc is None:
        return FALTA, "No hay %s en la carpeta." % req["documento"].replace("_", " "), {}
    ev = {"archivo": doc.get("archivo")}
    if req.get("vigente") and not doc.get("vigente", True):
        return NO_CUMPLE, "El documento no esta vigente.", ev
    if req.get("en_firme") and not doc.get("en_firme", True):
        return NO_CUMPLE, "El RUP no esta en firme.", ev
    if req["documento"] == "boletin_responsables_fiscales" and doc.get("reportado"):
        return NO_CUMPLE, "Aparece reportado en el boletin.", ev
    if req["documento"] == "carta_presentacion" and not doc.get("firmada"):
        return NO_CUMPLE, "La carta no esta firmada.", ev
    dias_max = req.get("max_dias_expedicion")
    if dias_max:
        exp, cierre = _fecha(doc.get("fecha_expedicion")), ctx["fecha_cierre"]
        if exp is None:
            return REVISAR, "El documento no tiene fecha de expedicion legible.", ev
        dias = (cierre - exp).days
        ev.update({"fecha_expedicion": exp.isoformat(), "dias_antes_del_cierre": dias, "maximo": dias_max})
        if dias > dias_max:
            return NO_CUMPLE, ("Expedido %d dias antes del cierre; el pliego admite maximo %d. "
                               "Hay que pedir uno nuevo." % (dias, dias_max)), ev
        if dias < 0:
            return REVISAR, "La fecha de expedicion es posterior al cierre.", ev
        return CUMPLE, "Expedido %d dias antes del cierre (maximo %d)." % (dias, dias_max), ev
    return CUMPLE, "Documento en la carpeta: %s." % doc.get("archivo", ""), ev


def _indicador(req, doc, ctx):
    if doc is None:
        return FALTA, "No hay estados financieros en la carpeta.", {}
    v = doc.get(req["campo"])
    if v is None:
        return REVISAR, "Los estados financieros no traen el indicador %s." % req["campo"], {}
    ok = v >= req["umbral"] if req["op"] == ">=" else v <= req["umbral"]
    ev = {"valor": v, "umbral": req["umbral"], "op": req["op"], "umbral_simulado": req.get("umbral_simulado", False)}
    texto = "%s %s %s %s" % (req["campo"].replace("_", " "), _n(v), "≥" if req["op"] == ">=" else "≤", _n(req["umbral"]))
    if req.get("umbral_simulado"):
        # El pliego remite a la Matriz 2 (un anexo que no viene en el PDF):
        # el umbral usado es el usual de los documentos tipo. Aunque el dato
        # cumpla, alguien tiene que confirmar el umbral real.
        return (REVISAR, texto + (" con el umbral usual de los documentos tipo; el pliego remite a la Matriz 2, "
                                  "que no viene en el PDF: confirmar el umbral real."), ev)
    return (CUMPLE if ok else NO_CUMPLE), texto + ("." if ok else ": no cumple."), ev


def _capital_trabajo(req, doc, ctx, lote):
    if doc is None:
        return FALTA, "No hay estados financieros en la carpeta.", {}
    ac, pc = doc.get("activo_corriente"), doc.get("pasivo_corriente")
    if ac is None or pc is None:
        return REVISAR, "Faltan activo o pasivo corriente.", {}
    ct = ac - pc
    ctd = req["pct_po"] * lote["presupuesto"]
    ev = {"capital_trabajo": ct, "demandado": ctd, "pct_po": req["pct_po"], "presupuesto": lote["presupuesto"]}
    if ct >= ctd:
        return CUMPLE, "CT = %s ≥ CTd = %s (%d %% del presupuesto del lote)." % (_mill(ct), _mill(ctd), 100 * req["pct_po"]), ev
    return NO_CUMPLE, "CT = %s < CTd = %s." % (_mill(ct), _mill(ctd)), ev


def _capacidad_residual(req, doc, ctx, lote):
    if doc is None:
        return FALTA, "No hay Formato 5 de capacidad residual en la carpeta.", {}
    crp = doc.get("capacidad_residual")
    if crp is None:
        return REVISAR, "El Formato 5 no trae la capacidad residual calculada.", {}
    poe = lote["presupuesto"]
    anticipo = ctx.get("anticipo_pct", 0) * poe
    crpc = poe - anticipo
    if lote.get("plazo_meses", 0) > 12:
        crpc = crpc * 12 / lote["plazo_meses"]
    ev = {"crp": crp, "crpc": crpc, "presupuesto": poe, "anticipo": anticipo, "plazo_meses": lote.get("plazo_meses")}
    if crp >= crpc:
        return CUMPLE, "CRP = %s ≥ CRPC = %s (presupuesto − anticipo del %d %%)." % (
            _mill(crp), _mill(crpc), round(100 * ctx.get("anticipo_pct", 0))), ev
    return NO_CUMPLE, "CRP = %s < CRPC = %s." % (_mill(crp), _mill(crpc)), ev


def _experiencia(req, doc, ctx, lote):
    if doc is None:
        return FALTA, "No hay certificado RUP en la carpeta.", {}
    validos = [c for c in doc.get("contratos", [])
               if c.get("terminado") and set(c.get("actividades", [])) & set(lote["actividades"])]
    validos = sorted(validos, key=lambda c: -c["valor_smmlv"])[:6]
    po_smmlv = _smmlv(lote["presupuesto"], ctx["smmlv"])
    # El % exigido sube con el numero de contratos que se usan (75/120/150).
    # Se prueba con 1, 2, ... contratos (los de mayor valor primero) y se
    # toma el primer k que cumple; si ninguno, se reporta el ultimo.
    mejor = None
    for k in range(1, len(validos) + 1):
        suma = sum(c["valor_smmlv"] for c in validos[:k])
        pct = next(t["pct"] for t in req["tabla"] if k <= t["contratos_max"])
        mejor = (k, suma, pct, pct * po_smmlv)
        if suma >= pct * po_smmlv:
            break
    ev = {"contratos_validos": [c["consecutivo"] for c in validos], "presupuesto_smmlv": po_smmlv}
    if not validos:
        return NO_CUMPLE, "Ningun contrato terminado del RUP esta en las actividades del lote.", ev
    k, suma, pct, req_smmlv = mejor
    ev.update({"contratos_usados": k, "acreditado_smmlv": suma, "pct_requerido": pct, "requerido_smmlv": req_smmlv})
    if suma >= req_smmlv:
        return CUMPLE, "Con %d contrato(s) acredita %s SMMLV; con %d contratos el pliego pide %d %% del presupuesto = %s SMMLV." % (
            k, _n(suma), k, round(100 * pct), _n(req_smmlv)), ev
    return NO_CUMPLE, "Con los %d contratos validos acredita %s SMMLV y el pliego pide %s (%d %% del presupuesto): faltan %s." % (
        k, _n(suma), _n(req_smmlv), round(100 * pct), _n(req_smmlv - suma)), ev


def _experiencia_actividades(req, doc, ctx, lote):
    if doc is None:
        return FALTA, "No hay certificado RUP en la carpeta.", {}
    exigidas = set(lote["actividades"])
    cubiertas = set()
    for c in doc.get("contratos", []):
        if c.get("terminado"):
            cubiertas |= set(c.get("actividades", [])) & exigidas
    ev = {"exigidas": sorted(exigidas), "cubiertas": sorted(cubiertas)}
    if exigidas <= cubiertas:
        return CUMPLE, "Los contratos terminados cubren %s." % ", ".join(sorted(exigidas)).replace("_", " "), ev
    faltan = exigidas - cubiertas
    return NO_CUMPLE, "Falta experiencia terminada en: %s." % ", ".join(sorted(faltan)).replace("_", " "), ev


def _duracion(req, doc, ctx, lote):
    if doc is None:
        return FALTA, "No hay certificado de camara de comercio.", {}
    hasta = _fecha(doc.get("duracion_hasta"))
    if hasta is None:
        return REVISAR, "El certificado no dice hasta cuando dura la sociedad.", {}
    minimo = ctx["fecha_cierre"] + timedelta(days=30 * lote["plazo_meses"] + 365)
    ev = {"duracion_hasta": hasta.isoformat(), "minimo": minimo.isoformat()}
    if hasta >= minimo:
        return CUMPLE, "Dura hasta %s; el plazo (%d meses) mas un ano vence %s." % (hasta, lote["plazo_meses"], minimo), ev
    return NO_CUMPLE, "Dura hasta %s, antes de %s (plazo + 1 ano)." % (hasta, minimo), ev


def _garantia(req, doc, ctx, lote):
    if doc is None:
        return FALTA, "No hay garantia de seriedad en la carpeta. Hay que expedirla: %s, vigente %d meses desde el cierre." % (
            _mill(req["pct_po"] * lote["presupuesto"]), req["meses_vigencia"]), {
            "valor_requerido": req["pct_po"] * lote["presupuesto"]}
    valor = doc.get("valor_asegurado", 0)
    requerido = req["pct_po"] * lote["presupuesto"]
    ev = {"valor_asegurado": valor, "valor_requerido": requerido}
    if valor >= requerido:
        return CUMPLE, "Asegura %s (requerido %s)." % (_mill(valor), _mill(requerido)), ev
    return NO_CUMPLE, "Asegura %s, menos que el %d %% del presupuesto (%s)." % (_mill(valor), 100 * req["pct_po"], _mill(requerido)), ev


def verificar(req: dict, documentos: dict, ctx: dict, lote: dict) -> Verificacion:
    doc = documentos.get(req.get("documento")) if req.get("documento") else None
    tipo = req["tipo"]
    if tipo == "documento":
        estado, detalle, ev = _documento(req, doc, ctx)
    elif tipo == "indicador":
        estado, detalle, ev = _indicador(req, doc, ctx)
    elif tipo == "capital_trabajo":
        estado, detalle, ev = _capital_trabajo(req, doc, ctx, lote)
    elif tipo == "capacidad_residual":
        estado, detalle, ev = _capacidad_residual(req, doc, ctx, lote)
    elif tipo == "experiencia":
        estado, detalle, ev = _experiencia(req, doc, ctx, lote)
    elif tipo == "experiencia_actividades":
        estado, detalle, ev = _experiencia_actividades(req, doc, ctx, lote)
    elif tipo == "duracion_sociedad":
        estado, detalle, ev = _duracion(req, doc, ctx, lote)
    elif tipo == "garantia":
        estado, detalle, ev = _garantia(req, doc, ctx, lote)
    elif tipo == "revisar":
        if req.get("documento") and doc is None:
            estado, detalle, ev = FALTA, "No hay documento para revisarlo.", {}
        else:
            estado, detalle, ev = REVISAR, "Requiere lectura humana; no es verificable automaticamente.", {}
    else:
        raise ValueError("tipo de requisito desconocido: %s" % tipo)
    return Verificacion(req["id"], req["categoria"], req["titulo"], estado, detalle,
                        req["pagina"], req.get("seccion", ""), req["cita"], ev, req.get("documento"))


def verificar_todo(requisitos: list[dict], documentos: dict, ctx: dict, lote: dict) -> list[Verificacion]:
    return [verificar(r, documentos, ctx, lote) for r in requisitos]


def resumen(verificaciones: list[Verificacion]) -> dict:
    conteo = {CUMPLE: 0, NO_CUMPLE: 0, FALTA: 0, REVISAR: 0}
    for v in verificaciones:
        conteo[v.estado] += 1
    total = len(verificaciones)
    return {"total": total, "conteo": conteo,
            "habil": conteo[NO_CUMPLE] == 0 and conteo[FALTA] == 0,
            "pendientes": conteo[NO_CUMPLE] + conteo[FALTA] + conteo[REVISAR]}


# ---------------------------------------------------------------- formato
def _mill(x) -> str:
    return "$%s mill." % f"{x / 1e6:,.0f}".replace(",", ".")


def _n(x) -> str:
    if isinstance(x, float):
        s = f"{x:,.2f}".rstrip("0").rstrip(".")
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    return str(x)
