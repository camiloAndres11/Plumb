"""La carpeta de documentos de la empresa, con la forma que el checklist
verifica (pliego/checklist/fixtures/documentos_constructora.json).

Parte sale del perfil (RUP y experiencia, indicadores financieros,
capacidad residual) y parte la declara la empresa en /empresa/documentos
(que documentos tiene, con fecha y datos clave). Todo vive en
pliego.empresas.perfil: `documentos` es un dict {clave: {...}}.

Las actividades de cada contrato de experiencia salen de la familia
UNSPSC (7214 -> vias, 7212 -> edificaciones...) para poder cruzarlas con
lo que el pliego exige (vocabulario de plataforma/extraccion.ACTIVIDADES).
"""
from __future__ import annotations

from pliego.filtro.logica import familia

ACTIVIDAD_POR_FAMILIA = {
    "7214": "vias", "7210": "edificaciones", "7212": "edificaciones", "7215": "edificaciones",
    "7211": "edificaciones", "7213": "edificaciones", "8110": "otras", "8010": "otras", "8310": "acueductos_alcantarillados",
}
ACTIVIDAD_POR_CLASE = {"V1.72151800": "acueductos_alcantarillados", "V1.72151900": "edificaciones", "V1.72151500": "electricas",
                       "V1.72153900": "espacio_publico", "V1.72141100": "vias", "V1.72141000": "vias", "V1.72141500": "vias"}

# Lo que la empresa declara en /empresa/documentos: (clave, etiqueta, campos extra).
DOCUMENTOS = [
    ("carta_presentacion", "Carta de presentación (Formato 1) firmada", [("firmada", "check", "Firmada por el representante legal")]),
    ("tarjeta_profesional", "Tarjeta profesional del avalador (ing. civil o arquitecto)",
     [("profesion", "text", "Profesión"), ("vigente", "check", "Certificado de vigencia al día"), ("fecha_certificado_vigencia", "date", "Fecha del certificado")]),
    ("rup", "Certificado RUP", [("fecha_expedicion", "date", "Fecha de expedición"), ("en_firme", "check", "En firme")]),
    ("camara_comercio", "Certificado de cámara de comercio", [("fecha_expedicion", "date", "Fecha de expedición"),
                                                              ("duracion_hasta", "date", "Duración de la sociedad hasta"),
                                                              ("objeto_social", "text", "Objeto social (resumen)")]),
    ("boletin_responsables_fiscales", "Certificado de la Contraloría", [("fecha", "date", "Fecha"), ("reportado", "check", "Aparece reportado")]),
    ("antecedentes", "Antecedentes (Procuraduría, Policía)", [("fecha", "date", "Fecha")]),
    ("seguridad_social", "Certificación de seguridad social (Formato 6)", [("fecha", "date", "Fecha")]),
    ("garantia_seriedad", "Garantía de seriedad", [("valor_asegurado", "number", "Valor asegurado (COP)"), ("vigencia_hasta", "date", "Vigente hasta")]),
    ("pacto_transparencia", "Pacto de transparencia", [("fecha", "date", "Fecha")]),
    ("cedula_representante", "Cédula del representante legal", []),
]


def actividades_de(unspsc: str | None) -> list[str]:
    if not unspsc:
        return []
    if unspsc in ACTIVIDAD_POR_CLASE:
        return [ACTIVIDAD_POR_CLASE[unspsc]]
    fam = familia(unspsc)
    return [ACTIVIDAD_POR_FAMILIA[fam]] if fam in ACTIVIDAD_POR_FAMILIA else ["otras"]


def carpeta_de(perfil: dict) -> dict:
    """El perfil de la empresa -> {"constructora": {...}, "documentos": {...}}."""
    declarados = {k: dict(v) for k, v in (perfil.get("documentos") or {}).items() if isinstance(v, dict) and v.get("tiene")}
    fin, org, rup = perfil.get("financiero") or {}, perfil.get("organizacional") or {}, perfil.get("rup") or {}
    docs = dict(declarados)
    # RUP: lo declarado + lo que ya sabe el perfil.
    contratos = [{"consecutivo": i + 1, "objeto": e.get("objeto"), "actividades": actividades_de(e.get("unspsc")),
                  "valor_smmlv": e.get("valor_smmlv"), "terminado": bool(e.get("liquidado"))}
                 for i, e in enumerate(perfil.get("experiencia") or [])]
    if rup.get("vigente") or "rup" in docs:
        docs["rup"] = {"archivo": "RUP", "vigente": bool(rup.get("vigente", True)), "fecha_expedicion": rup.get("renovado"),
                       "en_firme": True, **docs.get("rup", {}), "contratos": contratos}
    # Estados financieros: siempre, con los indicadores del perfil.
    docs["estados_financieros"] = {"archivo": "Estados financieros (perfil)", "liquidez": fin.get("liquidez"),
                                   "endeudamiento": fin.get("endeudamiento"), "cobertura_intereses": fin.get("cobertura_intereses"),
                                   "rentabilidad_patrimonio": org.get("rentabilidad_patrimonio"), "rentabilidad_activo": org.get("rentabilidad_activo"),
                                   "activo_corriente": fin.get("activo_corriente"), "pasivo_corriente": fin.get("pasivo_corriente"),
                                   **docs.get("estados_financieros", {})}
    if fin.get("capital_trabajo") is not None and docs["estados_financieros"].get("activo_corriente") is None:
        # Sin activo/pasivo corriente, el capital de trabajo del perfil se
        # expresa como activo corriente = CT y pasivo corriente = 0.
        docs["estados_financieros"]["activo_corriente"] = fin["capital_trabajo"]
        docs["estados_financieros"]["pasivo_corriente"] = 0
    if perfil.get("capacidad_residual") is not None:
        docs["formato5_capacidad_residual"] = {"archivo": "Formato 5 (perfil)", "capacidad_residual": perfil["capacidad_residual"]}
    for clave, valores in docs.items():
        valores.setdefault("archivo", clave.replace("_", " "))
    sede = perfil.get("sede") or {}
    return {"constructora": {"nombre": perfil.get("nombre"), "nit": perfil.get("nit"), "ciudad": (sede.get("ciudad") or "").title()},
            "documentos": docs}
