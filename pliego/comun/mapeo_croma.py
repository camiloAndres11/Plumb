"""Registro de Croma -> fila con el esquema del warehouse (`base` / `alertas`).

Funciones puras, sin IO, para que se prueben con dicts a mano. La meta es
que una fila salida de aqui sea indistinguible de una del warehouse para
las SQL de pliego/*/semilla.py: mismos nombres de columna, textos en
MAYUSCULAS sin tildes (como norm_txt en sql/01_stage.sql), fechas ISO,
montos en COP como float.

Lo que la doc de Croma fija se lee por su nombre. Lo que no fija (el enlace
contrato -> proceso, si el contrato trae conteos de oferentes) se busca en
varios nombres plausibles y, si no aparece, queda en None: la SQL de las
semillas ya tolera nulos ahi. La sonda (python -m pliego.comun.croma) es la
manera de ver los nombres reales y ajustar `ALIAS` en un solo sitio.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

_NTC = re.compile(r"CO1\.NTC\.\d+")
_ESPACIOS = re.compile(r"\s+")


def norm_txt(x) -> str | None:
    """Como la macro norm_txt del warehouse: sin tildes, un solo espacio, mayusculas."""
    if x is None:
        return None
    s = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode()
    s = _ESPACIOS.sub(" ", s.upper()).strip()
    return s or None


def norm_doc(x) -> str | None:
    """NIT o cedula como llave: solo digitos, sin digito de verificacion
    (900.195.855-1 -> 900195855). Es como Croma los acepta y como el
    warehouse los guarda."""
    if x is None:
        return None
    s = str(x).strip()
    if "-" in s:
        s = s.split("-", 1)[0]
    s = re.sub(r"\D", "", s)
    return s or None


def numero(x) -> float | None:
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def entero(x) -> int | None:
    v = numero(x)
    return int(v) if v is not None else None


def fecha(x) -> str | None:
    """'yyyy-mm-dd' o None. Croma ya normaliza a yyyy-mm-dd; se recorta por
    si llega con hora."""
    if not x:
        return None
    s = str(x)[:10]
    try:
        date.fromisoformat(s)
    except ValueError:
        return None
    return s


def notice_uid(*candidatos) -> str | None:
    """El CO1.NTC.* que enlaza contrato y proceso, sacado de cualquier campo
    que lo contenga (un id, una url). Mismo truco que sql/01_stage.sql."""
    for c in candidatos:
        if c:
            m = _NTC.search(str(c))
            if m:
                return m.group(0)
    return None


def unspsc(x) -> str | None:
    """Al formato del warehouse, 'V1.72141000'. SECOP II ya viene asi; SECOP I
    trae 6 digitos ('721410', nivel clase) y a veces 'UNSPECIFIED'."""
    if not x:
        return None
    s = str(x).strip()
    if s.startswith("V1."):
        return s
    if s.isdigit() and 4 <= len(s) <= 8:
        return "V1." + s.ljust(8, "0")
    return None


def _primero(r: dict, *nombres):
    for n in nombres:
        v = r.get(n)
        if v not in (None, ""):
            return v
    return None


# Nombres alternativos para lo que la doc de Croma no fija. Un solo sitio
# que ajustar tras correr la sonda.
ALIAS = {
    "es_grupo": ("provider_is_group", "is_group"),
    "proceso_id": ("process_id", "notice_uid", "process_notice_uid", "process_url", "url"),
    "oferentes_unicos": ("unique_responding_providers", "unique_bidders", "responding_providers"),
    "respuestas": ("responses", "offer_responses"),
    "cierre_ofertas": ("bid_deadline", "offers_deadline"),
    "precio_base": ("base_price", "estimated_value"),
}


# ------------------------------------------------------------------ procesos
def proceso_a_fila(r: dict, hoy: date) -> dict:
    """Un proceso (de processes-search o process-record) -> fila de `alertas`
    sin las banderas: esas las calcula fuente.py en SQL, con contexto."""
    pub, cierre = fecha(_primero(r, "published_date", "publish_date")), fecha(_primero(r, *ALIAS["cierre_ofertas"]))
    d_pub, d_cierre = _d(pub), _d(cierre)
    uid = notice_uid(r.get("notice_uid"), r.get("url"), r.get("id"), r.get("process_id"))
    return {
        "id_del_proceso": id_proceso(r),
        "notice_uid": uid,
        "urlproceso": r.get("url"),
        "nit_entidad": norm_doc(r.get("entity_nit")),
        "entidad": norm_txt(r.get("entity")),
        "departamento": norm_txt(r.get("entity_department")),
        "ciudad": norm_txt(r.get("entity_city")),
        "tipo_contrato": norm_txt(r.get("contract_type")),
        "modalidad": norm_txt(r.get("modality")),
        "unspsc": unspsc(r.get("unspsc_code")),
        "descripcion": r.get("description") or r.get("name"),
        "precio_base": numero(_primero(r, *ALIAS["precio_base"])),
        "valor_adjudicado": numero(r.get("awarded_value")),
        "adjudicado": _adjudicado(r),
        "n_invitados": entero(r.get("invited_providers")),
        "n_manifestaron": entero(r.get("interested_providers")),
        "n_respuestas": entero(_primero(r, *ALIAS["respuestas"])),
        "n_oferentes_unicos": entero(_primero(r, *ALIAS["oferentes_unicos"])),
        "fecha_publicacion": pub,
        "fecha_cierre": cierre,
        "fecha_adjudicacion": fecha(r.get("award_date")),
        "dias_ventana": (d_cierre - d_pub).days if d_pub and d_cierre else None,
        "dias_restantes": (d_cierre - hoy).days if d_cierre else None,
    }


def id_proceso(r: dict) -> str | None:
    """`id` viene con prefijo de plataforma (secop_ii:CO1.REQ.123); el
    warehouse guarda el CO1.REQ.* pelado."""
    v = _primero(r, "process_id", "id", "reference")
    if v is None:
        return None
    s = str(v)
    return s.split(":", 1)[1] if ":" in s else s


def _adjudicado(r: dict) -> bool | None:
    v = r.get("awarded")
    if isinstance(v, bool):
        return v
    if v is None:
        return None
    return str(v).strip().lower() in ("yes", "si", "sí", "true", "1")


# ----------------------------------------------------------------- contratos
def contrato_a_fila(r: dict, proceso: dict | None = None) -> dict:
    """Un contrato (de contracts-search o contract-record) -> fila de `base`.

    `proceso` es la fila (ya mapeada) del proceso que lo origino, si se
    encontro: de ahi salen precio_base, oferentes y cierre de ofertas cuando
    el contrato no los trae."""
    p = proceso or {}
    valor = numero(r.get("value"))
    firma = fecha(r.get("sign_date"))
    uid = notice_uid(*(r.get(n) for n in ALIAS["proceso_id"]), r.get("process_url"))
    grupo = _primero(r, *ALIAS["es_grupo"])
    return {
        "id_contrato": _id_contrato(r),
        "notice_uid": uid or p.get("notice_uid"),
        "nit_entidad": norm_doc(r.get("entity_nit")) or p.get("nit_entidad"),
        "entidad": norm_txt(r.get("entity")) or p.get("entidad"),
        "departamento": norm_txt(_primero(r, "entity_department", "department")) or p.get("departamento"),
        "ciudad": norm_txt(_primero(r, "entity_city", "city")) or p.get("ciudad"),
        "orden": norm_txt(_primero(r, "entity_order", "order")),
        "modalidad": norm_txt(r.get("modality")) or p.get("modalidad"),
        "tipo_contrato": norm_txt(r.get("contract_type")) or p.get("tipo_contrato"),
        "unspsc": unspsc(r.get("unspsc_code")) or p.get("unspsc"),
        "descripcion": (r.get("object") or r.get("description") or p.get("descripcion") or "")[:120] or None,
        "precio_base": numero(_primero(r, *ALIAS["precio_base"])) or p.get("precio_base"),
        "valor_adjudicado": valor,
        # Mismo techo que sql/01_stage.sql: 10 billones COP.
        "valor_plausible": valor if valor is not None and 0 <= valor <= 1e13 else None,
        "n_oferentes_unicos": entero(_primero(r, *ALIAS["oferentes_unicos"])) or p.get("n_oferentes_unicos"),
        "n_respuestas": entero(_primero(r, *ALIAS["respuestas"])) or p.get("n_respuestas"),
        "fecha_firma": firma,
        "fecha_inicio": fecha(r.get("start_date")),
        "fecha_fin": fecha(r.get("end_date")),
        "fecha_cierre_ofertas": p.get("fecha_cierre"),
        "estado": norm_txt(r.get("status")),
        "anio": int(firma[:4]) if firma else None,
        "doc_proveedor": norm_doc(_primero(r, "provider_document", "provider_nit")),
        "proveedor": norm_txt(r.get("provider")),
        "es_grupo": "SI" if grupo is True else "NO" if grupo is False else norm_txt(grupo),
        "valor_pagado": numero(r.get("paid_value")),
        "valor_pend_ejecucion": numero(r.get("pending_execution_value")),
    }


def _id_contrato(r: dict) -> str | None:
    v = _primero(r, "contract_id", "id", "reference")
    if v is None:
        return None
    s = str(v)
    return s.split(":", 1)[1] if ":" in s else s


def _d(iso: str | None) -> date | None:
    return date.fromisoformat(iso) if iso else None
