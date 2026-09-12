"""Mapeo de campos del pliego y del perfil a cada documento de la oferta.

Pura. Cada dato que entra a un borrador es un Campo con su ORIGEN:

  pliego     salio del pliego, con la pagina exacta
  perfil     salio del perfil de la constructora (ruta al dato)
  calculado  se deriva de los dos, con la formula escrita
  faltante   hace falta y no esta en ninguno de los dos: hay que conseguirlo
  no_aplica  el documento o el campo no aplica a este proponente

Un documento esta LISTO cuando ningun campo esta faltante; con faltantes
es un borrador; ADJUNTAR es un documento de terceros (una poliza, un
certificado) del que solo se puede decir que pedir; NO APLICA se explica.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, timedelta

LISTO, CON_FALTANTES, ADJUNTAR, NO_APLICA = "listo", "con_faltantes", "adjuntar", "no_aplica"
PLIEGO, PERFIL, CALCULADO, FALTANTE, NOAP = "pliego", "perfil", "calculado", "faltante", "no_aplica"


@dataclass
class Campo:
    clave: str
    etiqueta: str
    valor: object
    origen: str
    fuente: str = ""            # ruta del dato (pliego.campos.x / perfil.a.b) o formula
    pagina: int | None = None
    critico: bool = False       # si falta, la oferta se rechaza (no es subsanable)

    def como_dict(self) -> dict:
        return asdict(self)


@dataclass
class Documento:
    id: str
    nombre: str
    descripcion: str
    estado: str
    campos: list[Campo]
    texto: str                  # borrador en markdown
    pagina: int | None = None   # donde el pliego lo exige
    faltantes: list[Campo] = field(default_factory=list)

    def como_dict(self) -> dict:
        d = asdict(self)
        return d


# ------------------------------------------------------------- lectura
def _p(pliego: dict, clave: str, etiqueta: str, critico=False) -> Campo:
    c = pliego["campos"].get(clave)
    if c is None or c.get("valor") in (None, ""):
        return Campo(clave, etiqueta, None, FALTANTE, f"pliego.campos.{clave}", None, critico)
    return Campo(clave, etiqueta, c["valor"], PLIEGO, f"pliego.campos.{clave}", c.get("pagina"), critico)


def _lote(lote: dict, clave: str, etiqueta: str) -> Campo:
    return Campo(f"lote.{clave}", etiqueta, lote.get(clave), PLIEGO, f"pliego.lotes[{lote['n']}].{clave}", lote.get("pagina"))


def _f(perfil: dict, ruta: str, etiqueta: str, critico=False, clave: str | None = None) -> Campo:
    v: object = perfil
    for parte in ruta.split("."):
        v = v.get(parte) if isinstance(v, dict) else None
        if v is None:
            break
    clave = clave or ruta.split(".")[-1]
    if v in (None, "", []):
        return Campo(clave, etiqueta, None, FALTANTE, f"perfil.{ruta}", None, critico)
    return Campo(clave, etiqueta, v, PERFIL, f"perfil.{ruta}", None, critico)


def _c(clave: str, etiqueta: str, valor, formula: str, critico=False) -> Campo:
    return Campo(clave, etiqueta, valor, CALCULADO, formula, None, critico)


def _mill(x) -> str:
    return "$%s" % f"{x:,.0f}".replace(",", ".")


def _n(x) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ------------------------------------------------------------ documentos
def formato1(pliego, perfil, lote, hoy: date) -> Documento:
    rl = perfil.get("representante_legal", {})
    campos = [
        _p(pliego, "entidad", "Entidad"), _p(pliego, "proceso", "Número del proceso"), _p(pliego, "objeto", "Objeto"),
        _lote(lote, "n", "Grupo al que se presenta"), _lote(lote, "nombre", "Nombre del grupo"), _lote(lote, "presupuesto", "Presupuesto oficial del grupo"),
        _lote(lote, "plazo_meses", "Plazo"),
        _f(perfil, "nombre", "Proponente", critico=True), _f(perfil, "nit", "NIT"), _f(perfil, "ciudad", "Ciudad"),
        _f(perfil, "direccion", "Dirección"), _f(perfil, "correo", "Correo para notificaciones"), _f(perfil, "telefono", "Teléfono"),
        _f(perfil, "representante_legal.nombre", "Representante legal", critico=True, clave="rl_nombre"),
        _f(perfil, "representante_legal.cedula", "Cédula del representante legal", clave="rl_cedula"),
        _f(perfil, "representante_legal.cargo", "Cargo", clave="rl_cargo"),
        _p(pliego, "pacto_transparencia", "Pacto de transparencia"),
    ]
    # Aval de ingeniero: solo si el representante legal no lo es (p. 14)
    aval = _p(pliego, "aval_ingeniero", "Regla del aval")
    prof = (rl.get("profesion") or "").lower()
    if any(k in prof for k in ("ingenier", "arquitect", "constructor")):
        campos.append(Campo("aval", "Aval de ingeniero", "No requiere aval aparte: el representante legal es %s (T.P. %s)." % (rl.get("profesion"), rl.get("tarjeta_profesional")),
                            CALCULADO, "perfil.representante_legal.profesion ∈ {ingeniería, arquitectura} → sin aval (pliego p. %s)" % aval.pagina, aval.pagina))
        campos.append(_f(perfil, "representante_legal.tarjeta_profesional", "Tarjeta profesional del RL", critico=True, clave="rl_tarjeta"))
    else:
        campos.append(_f(perfil, "avalador.nombre", "Ingeniero que avala la oferta", critico=True, clave="avalador"))
    v = {c.clave: c.valor for c in campos}
    texto = f"""**Señores**
**{v.get('entidad') or '[ENTIDAD]'}**
Proceso {v.get('proceso') or '[PROCESO]'}
Ciudad

**Referencia:** Carta de presentación de la oferta — Grupo {v.get('lote.n')}: {v.get('lote.nombre')}

{v.get('nombre') or '[PROPONENTE]'}, identificada con NIT {v.get('nit') or '[NIT]'}, representada legalmente por {v.get('rl_nombre') or '[REPRESENTANTE LEGAL]'}, identificada con cédula de ciudadanía {v.get('rl_cedula') or '[CÉDULA]'}, en calidad de {v.get('rl_cargo') or '[CARGO]'}, presenta oferta para el proceso de licitación de obra pública {v.get('proceso')} cuyo objeto es «{v.get('objeto')}», en el **Grupo {v.get('lote.n')}** ({v.get('lote.nombre')}), con presupuesto oficial de {_mill(v.get('lote.presupuesto') or 0)} y plazo de {v.get('lote.plazo_meses')} meses.

Declaro bajo la gravedad del juramento que:

1. Conozco y acepto el pliego de condiciones, sus anexos, formatos, matrices y adendas, y las condiciones del contrato.
2. La oferta tiene una validez de tres (3) meses contados desde la fecha de cierre, y la garantía de seriedad la respalda.
3. Ni la sociedad ni su representante legal están incursos en inhabilidades, incompatibilidades o conflictos de interés para contratar con el Estado.
4. No estamos reportados en el Boletín de Responsables Fiscales de la Contraloría General de la República.
5. {v.get('pacto_transparencia')}
6. {v.get('aval') or ('La oferta va avalada por ' + str(v.get('avalador') or '[INGENIERO QUE AVALA]') + ', conforme al artículo 20 de la Ley 842 de 2003.')}

Para notificaciones: {v.get('direccion') or '[DIRECCIÓN]'}, {v.get('ciudad') or '[CIUDAD]'} · {v.get('correo') or '[CORREO]'} · {v.get('telefono') or '[TELÉFONO]'}.

Atentamente,

**{v.get('rl_nombre') or '[REPRESENTANTE LEGAL]'}**
C.C. {v.get('rl_cedula') or '[CÉDULA]'} · {v.get('rl_cargo') or ''}
{v.get('nombre') or ''} · NIT {v.get('nit') or ''}
"""
    return _armar("formato1", "Formato 1 – Carta de presentación de la oferta",
                  "La carta que firma el representante legal; con ella se acepta el pacto de transparencia.", campos, texto, 14)


def formato2(pliego, perfil, lote, hoy) -> Documento:
    tipo = _f(perfil, "tipo_proponente", "Tipo de proponente")
    if tipo.valor == "individual":
        c = Campo("aplica", "Aplica", "No: el proponente es individual (no consorcio ni unión temporal).", NOAP, "perfil.tipo_proponente", 64)
        return Documento("formato2", "Formato 2 – Conformación de proponente plural", "Solo para consorcios y uniones temporales.",
                         NO_APLICA, [tipo, c], "_No aplica: %s se presenta como proponente individual._" % perfil.get("nombre"), 64)
    campos = [tipo, _f(perfil, "integrantes", "Integrantes y participación", critico=True)]
    return _armar("formato2", "Formato 2 – Conformación de proponente plural", "Integrantes, participación y representante.", campos,
                  "Documento de conformación del proponente plural: integrantes, porcentaje de participación y representante legal designado.", 64)


def formato3(pliego, perfil, lote, hoy) -> Documento:
    tabla = _p(pliego, "experiencia_tabla", "Tabla de % por número de contratos")
    maxc = _p(pliego, "experiencia_max_contratos", "Máximo de contratos")
    rup = _f(perfil, "rup.contratos", "Contratos del RUP", critico=True, clave="contratos")
    campos = [tabla, maxc, rup, _lote(lote, "presupuesto", "Presupuesto oficial del grupo"), _lote(lote, "actividades", "Actividades exigidas")]
    if rup.origen == FALTANTE:
        return _armar("formato3", "Formato 3 – Experiencia", "Los contratos que acreditan la experiencia, con el consecutivo del RUP.", campos, "", 25)
    validos = sorted([c for c in rup.valor if c.get("terminado") and set(c.get("actividades", [])) & set(lote["actividades"])],
                     key=lambda c: -c["valor_smmlv"])[:maxc.valor or 6]
    po_smmlv = lote["presupuesto"] / pliego["smmlv"]
    elegidos, req = [], None
    for k in range(1, len(validos) + 1):
        pct = next(t["pct"] for t in tabla.valor if k <= t["contratos_max"])
        req = pct * po_smmlv
        elegidos = validos[:k]
        if sum(c["valor_smmlv"] for c in elegidos) >= req:
            break
    suma = sum(c["valor_smmlv"] for c in elegidos)
    campos += [
        _c("presupuesto_smmlv", "Presupuesto en SMMLV", round(po_smmlv, 2), "lote.presupuesto / pliego.smmlv"),
        _c("requerido_smmlv", "Experiencia requerida (SMMLV)", round(req or 0, 2), "% de la tabla según nº de contratos × presupuesto en SMMLV (p. 34)"),
        _c("elegidos", "Contratos elegidos", [c["consecutivo"] for c in elegidos], "los terminados en las actividades del grupo, de mayor a menor, hasta cumplir"),
        _c("acreditado_smmlv", "Experiencia acreditada (SMMLV)", suma, "suma de los elegidos"),
    ]
    if suma < (req or 0):
        campos.append(Campo("brecha", "Experiencia que falta", "%s SMMLV" % _n((req or 0) - suma), FALTANTE,
                            "perfil.rup.contratos: no alcanza; conseguir un socio o más certificaciones", None, True))
    filas = "\n".join(f"| {c['consecutivo']} | {c['objeto']} | {c['entidad']} | {', '.join(c['actividades']).replace('_', ' ')} | {_n(c['valor_smmlv'])} | {c['anio']} |" for c in elegidos)
    texto = f"""**Formato 3 – Experiencia** · Grupo {lote['n']} · presupuesto {_n(po_smmlv)} SMMLV

| Consecutivo RUP | Objeto | Entidad contratante | Actividades | Valor (SMMLV) | Año |
|---|---|---|---|---|---|
{filas}

**Total acreditado:** {_n(suma)} SMMLV con {len(elegidos)} contrato(s). **Requerido:** {_n(req or 0)} SMMLV ({int(100 * (req or 0) / po_smmlv) if po_smmlv else 0} % del presupuesto, por usar {len(elegidos)} contrato(s) — tabla de la sección 3.5.8).
"""
    return _armar("formato3", "Formato 3 – Experiencia", "Los contratos que acreditan la experiencia, con el consecutivo del RUP.", campos, texto, 25)


def formato4(pliego, perfil, lote, hoy) -> Documento:
    f = perfil.get("financiero", {})
    campos = [_f(perfil, "financiero.corte", "Corte de los estados financieros", clave="corte"),
              _f(perfil, "financiero.activo_corriente", "Activo corriente", critico=True, clave="ac"),
              _f(perfil, "financiero.pasivo_corriente", "Pasivo corriente", critico=True, clave="pc"),
              _f(perfil, "financiero.pasivo_total", "Pasivo total", clave="pt"), _f(perfil, "financiero.activo_total", "Activo total", clave="at"),
              _f(perfil, "financiero.utilidad_operacional", "Utilidad operacional", clave="uo"), _f(perfil, "financiero.gastos_interes", "Gastos de interés", clave="gi"),
              _f(perfil, "financiero.patrimonio", "Patrimonio", clave="pat"),
              _f(perfil, "financiero.contador", "Contador", clave="contador"), _f(perfil, "financiero.revisor_fiscal", "Revisor fiscal", clave="revisor"),
              _p(pliego, "capital_trabajo_pct", "% de capital de trabajo demandado"), _lote(lote, "presupuesto", "Presupuesto oficial del grupo")]
    if all(f.get(k) for k in ("activo_corriente", "pasivo_corriente", "pasivo_total", "activo_total", "utilidad_operacional", "patrimonio")):
        liq = f["activo_corriente"] / f["pasivo_corriente"]
        end = f["pasivo_total"] / f["activo_total"]
        cob = f["utilidad_operacional"] / f["gastos_interes"] if f.get("gastos_interes") else float("inf")
        roe = f["utilidad_operacional"] / f["patrimonio"]
        roa = f["utilidad_operacional"] / f["activo_total"]
        ct = f["activo_corriente"] - f["pasivo_corriente"]
        ctd = pliego["campos"]["capital_trabajo_pct"]["valor"] * lote["presupuesto"]
        campos += [_c("liquidez", "Índice de liquidez", round(liq, 2), "activo corriente / pasivo corriente (p. 34)"),
                   _c("endeudamiento", "Nivel de endeudamiento", round(end, 3), "pasivo total / activo total (p. 34)"),
                   _c("cobertura", "Cobertura de intereses", round(cob, 2) if cob != float("inf") else "sin gastos de interés", "utilidad operacional / gastos de interés (p. 34)"),
                   _c("roe", "Rentabilidad del patrimonio", round(roe, 3), "utilidad operacional / patrimonio (p. 36)"),
                   _c("roa", "Rentabilidad del activo", round(roa, 3), "utilidad operacional / activo total (p. 36)"),
                   _c("ct", "Capital de trabajo", ct, "activo corriente − pasivo corriente (p. 35)"),
                   _c("ctd", "Capital de trabajo demandado", ctd, "10 % × presupuesto del grupo (p. 35)")]
        texto = f"""**Formato 4 – Capacidad financiera y organizacional** · corte {f.get('corte')}

| Indicador | Fórmula | Valor |
|---|---|---|
| Índice de liquidez | AC / PC | {_n(liq)} |
| Nivel de endeudamiento | PT / AT | {_n(end)} |
| Razón de cobertura de intereses | UO / GI | {_n(cob) if cob != float('inf') else 'N/A (sin gastos de interés)'} |
| Rentabilidad del patrimonio | UO / Patrimonio | {_n(roe)} |
| Rentabilidad del activo | UO / AT | {_n(roa)} |
| Capital de trabajo | AC − PC | {_mill(ct)} |
| Capital de trabajo demandado (Grupo {lote['n']}) | 10 % × PO | {_mill(ctd)} |

Certifican: {f.get('contador') or '[CONTADOR]'} ({f.get('tarjeta_contador') or 'T.P.'}) y {f.get('revisor_fiscal') or '[REVISOR FISCAL]'}. Los umbrales exigidos están en la Matriz 2 del proceso (no incluida en el PDF del pliego).
"""
    else:
        texto = ""
    return _armar("formato4", "Formato 4 – Capacidad financiera y organizacional", "Indicadores con corte al 31 de diciembre, certificados por contador y revisor fiscal.", campos, texto, 36)


def formato5(pliego, perfil, lote, hoy) -> Documento:
    cr = perfil.get("capacidad_residual", {})
    campos = [_lote(lote, "presupuesto", "Presupuesto oficial del grupo"), _lote(lote, "plazo_meses", "Plazo"),
              _p(pliego, "anticipo_pct", "Anticipo"),
              _f(perfil, "capacidad_residual.contratos_en_ejecucion", "Contratos en ejecución", critico=True, clave="ejecucion"),
              _f(perfil, "capacidad_residual.crp", "Capacidad residual del proponente (CRP)", critico=True, clave="crp")]
    poe = lote["presupuesto"]
    ant = pliego["campos"]["anticipo_pct"]["valor"] * poe
    crpc = poe - ant
    if lote["plazo_meses"] > 12:
        crpc = crpc * 12 / lote["plazo_meses"]
    campos += [_c("anticipo", "Anticipo del grupo", ant, "anticipo % × presupuesto (p. 64)"),
               _c("crpc", "Capacidad residual del proceso (CRPC)", crpc, "presupuesto − anticipo, × 12/plazo si el plazo > 12 meses (p. 38)")]
    ejec = cr.get("contratos_en_ejecucion") or []
    saldo = 0.0
    filas = []
    for c in ejec:
        # SCE lineal: valor / plazo × dias pendientes × participacion (p. 43)
        ini = date.fromisoformat(c["fecha_inicio"])
        fin = ini + timedelta(days=c["plazo_dias"])
        # dias pendientes acotados al plazo: si aun no arranca, esta todo pendiente
        pend = min(c["plazo_dias"], max(0, (fin - hoy).days))
        sce = c["valor"] / c["plazo_dias"] * pend * c.get("participacion", 1)
        saldo += sce
        filas.append(f"| {c['objeto']} | {c['entidad']} | {_mill(c['valor'])} | {c['plazo_dias']} | {pend} | {_mill(sce)} |")
    campos.append(_c("sce", "Saldo de contratos en ejecución (SCE)", saldo, "Σ valor / plazo × días pendientes × participación (p. 43)"))
    if cr.get("crp") is not None:
        campos.append(_c("habil", "¿CRP ≥ CRPC?", cr["crp"] >= crpc, "CRP ≥ CRPC (p. 37)", critico=True))
    texto = f"""**Formato 5 – Capacidad residual** · Grupo {lote['n']}

**Capacidad residual del proceso (CRPC):** {_mill(poe)} − anticipo {_mill(ant)} = **{_mill(crpc)}**{' (anualizado por plazo > 12 meses)' if lote['plazo_meses'] > 12 else ''}.

Contratos en ejecución a la fecha de cierre:

| Objeto | Entidad | Valor | Plazo (días) | Días pendientes | SCE |
|---|---|---|---|---|---|
{chr(10).join(filas) or '| — | — | — | — | — | — |'}

**SCE total:** {_mill(saldo)}. **Capacidad residual del proponente (CRP):** {_mill(cr.get('crp') or 0)} → {'**hábil**' if (cr.get('crp') or 0) >= crpc else '**NO hábil**'} (CRP {'≥' if (cr.get('crp') or 0) >= crpc else '<'} CRPC).

Firma: representante legal y contador público.
"""
    return _armar("formato5", "Formato 5 – Capacidad residual", "Contratos en ejecución y el cálculo de la capacidad residual frente a la del proceso.", campos, texto, 37)


def formato6(pliego, perfil, lote, hoy) -> Documento:
    campos = [_p(pliego, "seguridad_social", "Qué exige el pliego"), _f(perfil, "seguridad_social.al_dia", "Al día en aportes", critico=True, clave="al_dia"),
              _f(perfil, "seguridad_social.meses_certificados", "Meses certificados", clave="meses"), _f(perfil, "seguridad_social.firma", "Quién firma", clave="firma"),
              _f(perfil, "financiero.revisor_fiscal", "Revisor fiscal", clave="revisor"), _f(perfil, "nombre", "Proponente"), _f(perfil, "nit", "NIT")]
    v = {c.clave: c.valor for c in campos}
    texto = f"""**Formato 6 – Certificación de pagos de seguridad social y aportes legales**

{v.get('revisor') or '[REVISOR FISCAL]'}, en calidad de {v.get('firma') or 'revisor fiscal'} de {v.get('nombre')} (NIT {v.get('nit')}), certifica que la sociedad se encuentra al día en el pago de aportes al Sistema de Seguridad Social Integral (salud, pensión y riesgos laborales) y aportes parafiscales (SENA, ICBF y cajas de compensación) durante los últimos {v.get('meses') or 6} meses anteriores a la fecha de cierre del proceso {pliego['campos']['proceso']['valor']}.

Se expide para el Municipio de Bucaramanga, conforme al artículo 50 de la Ley 789 de 2002.
"""
    return _armar("formato6", "Formato 6 – Pagos de seguridad social y aportes legales", "Certificación de los últimos seis meses, firmada por el revisor fiscal.", campos, texto, 24)


def formato7(pliego, perfil, lote, hoy) -> Documento:
    campos = [_p(pliego, "puntaje_factor_calidad", "Puntos en juego"),
              _f(perfil, "factor_calidad.plan_gerencia_proyectos", "Plan de gerencia de proyectos", critico=False, clave="plan")]
    texto = ("**Formato 7 – Factor de calidad** (%s puntos)\n\nCompromiso de implementar el programa de gerencia de proyectos descrito en el numeral 4.2.1. "
             "_Falta el plan: es un documento técnico propio de cada oferta; el generador no lo redacta._" % pliego["campos"]["puntaje_factor_calidad"]["valor"])
    return _armar("formato7", "Formato 7 – Factor de calidad", "Compromiso del programa de gerencia de proyectos (19 puntos).", campos, texto, 50)


def formato8(pliego, perfil, lote, hoy) -> Documento:
    campos = [_p(pliego, "puntaje_discapacidad", "Puntos en juego"),
              _f(perfil, "discapacidad.certificado_mintrabajo", "Certificado del Ministerio de Trabajo", clave="certificado")]
    texto = ("**Formato 8 – Vinculación de personas con discapacidad** (1 punto)\n\nSolo se obtiene el punto con el certificado del Ministerio de Trabajo de que al menos "
             "el 10 % de la nómina está en condición de discapacidad. _Sin certificado, no se presenta y se renuncia al punto._")
    return _armar("formato8", "Formato 8 – Vinculación de personas con discapacidad", "1 punto; exige certificado del Ministerio de Trabajo.", campos, texto, 52)


def formato9(pliego, perfil, lote, hoy) -> Documento:
    campos = [_p(pliego, "puntaje_industria_nacional", "Puntos en juego"),
              _f(perfil, "industria_nacional.origen_servicios", "Origen de los servicios", critico=True, clave="origen"),
              _f(perfil, "industria_nacional.personal_nacional_pct", "Personal nacional", clave="personal"),
              _f(perfil, "nombre", "Proponente"), _f(perfil, "representante_legal.nombre", "Representante legal", clave="rl_nombre")]
    v = {c.clave: c.valor for c in campos}
    texto = f"""**Formato 9 – Puntaje de industria nacional** ({v.get('puntaje_industria_nacional')} puntos)

{v.get('rl_nombre')}, representante legal de {v.get('nombre')}, declara bajo juramento que los servicios ofrecidos son de origen **{v.get('origen')}** y que el {int(100 * (v.get('personal') or 0))} % del personal que ejecutará el contrato es de nacionalidad colombiana, para efectos del puntaje de apoyo a la industria nacional (Ley 816 de 2003).
"""
    return _armar("formato9", "Formato 9 – Puntaje de industria nacional", "Declaración del origen de los servicios (20 puntos).", campos, texto, 51)


def garantia(pliego, perfil, lote, hoy) -> Documento:
    pct = _p(pliego, "garantia_seriedad_pct", "Porcentaje", critico=True)
    meses = _p(pliego, "garantia_seriedad_meses", "Vigencia (meses)")
    benef = _p(pliego, "garantia_beneficiario", "Asegurado / beneficiario")
    po = _lote(lote, "presupuesto", "Presupuesto oficial del grupo")
    valor = pct.valor * lote["presupuesto"]
    campos = [pct, meses, benef, po, _f(perfil, "nombre", "Tomador (razón social exacta)", critico=True), _f(perfil, "nit", "NIT del tomador"),
              _c("valor_asegurado", "Valor asegurado", valor, "% × presupuesto del grupo (p. 59)", critico=True),
              _c("vigencia", "Vigencia", "%d meses desde la fecha de cierre" % meses.valor, "meses desde el cierre (p. 59)"),
              Campo("poliza", "Póliza expedida", None, FALTANTE, "aseguradora: pedir con estos datos", None, True)]
    texto = f"""**Garantía de seriedad de la oferta** — solicitud a la aseguradora

- **Tomador:** {perfil.get('nombre')} (NIT {perfil.get('nit')}), con la razón social exacta del certificado de cámara de comercio.
- **Asegurado / beneficiario:** {benef.valor}
- **Valor asegurado:** {_mill(valor)} ({int(100 * pct.valor)} % del presupuesto oficial del Grupo {lote['n']}, {_mill(lote['presupuesto'])}).
- **Vigencia:** {meses.valor} meses contados desde la fecha de cierre del proceso.
- **Amparos:** los del artículo 2.2.1.2.3.1.6 del Decreto 1082 de 2015.
- **Clase:** póliza de seguro, patrimonio autónomo o garantía bancaria.

_La no entrega de la garantía no es subsanable: sin ella la oferta se rechaza._
"""
    return _armar("garantia", "Garantía de seriedad de la oferta", "Lo que hay que pedirle a la aseguradora; sin esto la oferta se rechaza.", campos, texto, 59, adjuntar=True)


def anexos(pliego, perfil, lote, hoy) -> Documento:
    dias = pliego["campos"]["vigencia_certificados_dias"]["valor"]
    def vig(clave, etiqueta, fecha):
        if not fecha:
            return Campo(clave, etiqueta, None, FALTANTE, "perfil." + clave, None, True)
        return Campo(clave, etiqueta, fecha, PERFIL, "perfil." + clave, None, True)
    campos = [_p(pliego, "vigencia_certificados_dias", "Vigencia máxima de certificados (días)"),
              vig("camara_comercio.fecha_expedicion", "Certificado de existencia y representación legal", perfil.get("camara_comercio", {}).get("fecha_expedicion")),
              vig("rup.fecha_expedicion", "Certificado RUP", perfil.get("rup", {}).get("fecha_expedicion")),
              _f(perfil, "representante_legal.cedula", "Copia de la cédula del representante legal", critico=True, clave="cedula"),
              _f(perfil, "representante_legal.tarjeta_profesional", "Tarjeta profesional y certificado de vigencia", critico=True, clave="tarjeta"),
              _f(perfil, "financiero.corte", "Estados financieros con notas y dictamen", critico=True, clave="ef"),
              Campo("contraloria", "Certificado de antecedentes fiscales (Contraloría)", "lo consulta la entidad; conviene adjuntarlo", CALCULADO, "pliego p. 20: la entidad consulta en línea", 20),
              Campo("procuraduria", "Antecedentes disciplinarios (Procuraduría)", "lo consulta la entidad; conviene adjuntarlo", CALCULADO, "pliego p. 20", 20)]
    texto = f"""**Certificaciones y anexos a adjuntar** (todos con fecha de expedición no mayor a {dias} días antes del cierre)

1. Certificado de existencia y representación legal (cámara de comercio) — expedido {perfil.get('camara_comercio', {}).get('fecha_expedicion') or '[PEDIR]'}.
2. Certificado RUP vigente y en firme — expedido {perfil.get('rup', {}).get('fecha_expedicion') or '[PEDIR]'}.
3. Cédula del representante legal.
4. Tarjeta profesional y certificado de vigencia (COPNIA) de {perfil.get('representante_legal', {}).get('nombre')}.
5. Estados financieros a {perfil.get('financiero', {}).get('corte')} con notas, dictamen y tarjeta del contador.
6. Certificados de antecedentes fiscales y disciplinarios (la entidad los consulta; adjuntarlos evita un requerimiento).
"""
    return _armar("anexos", "Certificaciones y anexos a adjuntar", "Lo que hay que pedir a terceros o sacar del archivo, con su vigencia.", campos, texto, 20, adjuntar=True)


DOCUMENTOS = [formato1, formato2, formato3, formato4, formato5, formato6, formato7, formato8, formato9, garantia, anexos]


def _armar(id_, nombre, descripcion, campos, texto, pagina, adjuntar=False) -> Documento:
    faltantes = [c for c in campos if c.origen == FALTANTE]
    estado = ADJUNTAR if adjuntar and not faltantes else (CON_FALTANTES if faltantes else LISTO)
    if adjuntar and faltantes:
        estado = CON_FALTANTES
    return Documento(id_, nombre, descripcion, estado, campos, texto, pagina, faltantes)


def generar_todo(pliego: dict, perfil: dict, lote: dict, hoy: date) -> list[Documento]:
    return [f(pliego, perfil, lote, hoy) for f in DOCUMENTOS]


def lo_que_falta(docs: list[Documento]) -> list[dict]:
    """Faltantes ordenados: primero los criticos (rechazo), luego por documento."""
    out = []
    for d in docs:
        for c in d.faltantes:
            out.append({"documento": d.id, "documento_nombre": d.nombre, "campo": c.clave, "etiqueta": c.etiqueta,
                        "fuente": c.fuente, "critico": c.critico, "pagina": d.pagina})
    out.sort(key=lambda x: (not x["critico"], x["documento"]))
    return out


def resumen(docs: list[Documento]) -> dict:
    conteo = {LISTO: 0, CON_FALTANTES: 0, ADJUNTAR: 0, NO_APLICA: 0}
    for d in docs:
        conteo[d.estado] += 1
    origenes = {PLIEGO: 0, PERFIL: 0, CALCULADO: 0, FALTANTE: 0, NOAP: 0}
    for d in docs:
        for c in d.campos:
            origenes[c.origen] += 1
    return {"total": len(docs), "conteo": conteo, "origenes": origenes,
            "faltantes_criticos": sum(1 for d in docs for c in d.faltantes if c.critico)}
