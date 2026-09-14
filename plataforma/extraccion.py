"""Extraer de un pliego (PDF) lo que checklist y generador necesitan, con Claude.

    resultado = extraer(pdf_bytes, nombre_archivo)      # dict con requisitos, extraccion, citas_bbox, paginas, costo_usd

Que produce (las mismas formas que los fixtures leidos a mano):
  requisitos   {"proceso": {...}, "requisitos": [...]}   como pliego/checklist/fixtures/requisitos_*.json
  extraccion   {"id", "pdf", "paginas", "smmlv", "campos": {clave: {"valor", "pagina"}}, "lotes", "formatos"}
               como pliego/generador/fixtures/pliego_*.json
  citas_bbox   {id_requisito: {"pagina", "ancho", "alto", "cajas": [...]}}   con poppler, como semilla.py
  paginas_png  {n: bytes}   las paginas citadas renderizadas a 72 dpi

Como: una sola llamada a Claude (claude-opus-5) con el PDF adjunto como
documento y una tool `registrar_extraccion` cuyo input_schema es el
contrato; el modelo esta obligado a usarla (tool_choice), asi que la
respuesta es JSON validado por la API y no texto que haya que parsear. La
llave es la de la plataforma (ANTHROPIC_API_KEY): es un servicio a la
empresa, no BYOK como el /chat de Plomada.

Lo que Claude NO decide: los umbrales de indicadores se leen del pliego;
si no estan, quedan con `umbral_simulado: true` (la logica del checklist ya
lo entiende asi). Las actividades de experiencia usan un vocabulario
cerrado (ACTIVIDADES) para poder cruzarlas con el RUP de la empresa.

Para las pruebas se inyecta `cliente` con un objeto que imita
`messages.create` (ver plataforma/tests/test_pliegos.py).
"""
from __future__ import annotations

import base64
import hashlib
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from pliego.comun import config as CFG

log = logging.getLogger("pliego.extraccion")

MODELO = "claude-opus-5"
MAX_TOKENS = 16000
# Precio orientativo por millon de tokens (entrada / salida) para el costo estimado.
USD_ENTRADA, USD_SALIDA = 5.0, 25.0
ACTIVIDADES = ["vias", "edificaciones", "espacio_publico", "acueductos_alcantarillados", "electricas", "otras"]
DOCUMENTOS = ["carta_presentacion", "tarjeta_profesional", "rup", "boletin_responsables_fiscales", "camara_comercio",
              "seguridad_social", "garantia_seriedad", "estados_financieros", "formato5_capacidad_residual",
              "antecedentes", "cedula_representante", "pacto_transparencia", "otro"]
TIPOS = ["documento", "indicador", "capital_trabajo", "capacidad_residual", "experiencia", "experiencia_actividades",
         "duracion_sociedad", "garantia", "revisar"]

INSTRUCCIONES = """Eres un analista de licitaciones de obra pública en Colombia. Lees el pliego de condiciones adjunto (SECOP II, normalmente con documentos tipo de Colombia Compra Eficiente) y registras, con la herramienta, TODO lo que una constructora necesita para saber si queda habilitada y para armar su propuesta.

Reglas:
- Cada dato lleva la página del PDF de donde salió (contando desde 1) y, en los requisitos, la cita textual (una o dos frases exactas del pliego, sin corregir ortografía) para poder resaltarla.
- Los requisitos habilitantes son los jurídicos, financieros, técnicos y de experiencia. Uno por fila; el `tipo` dice cómo se verifica: `documento` (existe un documento en la carpeta de la empresa), `indicador` (un índice financiero contra un umbral, con `campo`, `op` y `umbral`), `capital_trabajo` (con `pct_po`), `capacidad_residual`, `experiencia` (con la tabla de % del presupuesto según número de contratos), `experiencia_actividades`, `duracion_sociedad`, `garantia` (con `pct_po` y `meses_vigencia`) o `revisar` (lo que un humano debe leer).
- Si el pliego NO fija un umbral numérico (por ejemplo remite a un anexo), pon el umbral típico de los documentos tipo y marca `umbral_simulado: true`.
- Los lotes (o grupos) con su presupuesto oficial en pesos, plazo en meses y actividades exigidas usando SOLO este vocabulario: {ACTIVIDADES}.
- `smmlv` es el salario mínimo mensual del año del proceso en pesos. `anticipo_pct` entre 0 y 1 (0 si no hay anticipo).
- Los `formatos` son los anexos que la propuesta debe incluir (Formato 1, 2, ...), con nombre y página.
- No inventes: si algo no está en el pliego, omítelo o ponlo en null. Prefiere omitir a suponer.""".replace("{ACTIVIDADES}", ", ".join(ACTIVIDADES))

ESQUEMA = {
    "type": "object",
    "properties": {
        "proceso": {"type": "object", "properties": {
            "id": {"type": "string", "description": "número del proceso, p. ej. SI-LP-004-2021"},
            "entidad": {"type": "string"}, "nit_entidad": {"type": ["string", "null"]},
            "objeto": {"type": "string"}, "modalidad": {"type": "string"},
            "lugar_ejecucion": {"type": ["string", "null"]}, "unspsc": {"type": ["string", "null"]},
            "smmlv": {"type": "integer"}, "anticipo_pct": {"type": "number"},
            "fecha_cierre": {"type": ["string", "null"], "description": "yyyy-mm-dd si el pliego la trae"},
            "lotes": {"type": "array", "items": {"type": "object", "properties": {
                "n": {"type": "integer"}, "nombre": {"type": "string"}, "presupuesto": {"type": "number"},
                "plazo_meses": {"type": "number"}, "actividades": {"type": "array", "items": {"type": "string", "enum": ACTIVIDADES}},
                "pagina": {"type": "integer"}}, "required": ["n", "nombre", "presupuesto", "plazo_meses", "actividades", "pagina"]}},
        }, "required": ["id", "entidad", "objeto", "modalidad", "smmlv", "anticipo_pct", "lotes"]},
        "requisitos": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string", "description": "identificador corto en snake_case, único"},
            "categoria": {"type": "string", "enum": ["juridico", "financiero", "tecnico", "experiencia"]},
            "titulo": {"type": "string"}, "tipo": {"type": "string", "enum": TIPOS},
            "documento": {"type": ["string", "null"], "enum": DOCUMENTOS + [None]},
            "pagina": {"type": "integer"}, "seccion": {"type": ["string", "null"]}, "cita": {"type": "string"},
            "campo": {"type": ["string", "null"], "enum": ["liquidez", "endeudamiento", "cobertura_intereses",
                                                            "rentabilidad_patrimonio", "rentabilidad_activo", None]},
            "op": {"type": ["string", "null"], "enum": [">=", "<=", None]}, "umbral": {"type": ["number", "null"]},
            "umbral_simulado": {"type": "boolean"}, "pct_po": {"type": ["number", "null"]},
            "meses_vigencia": {"type": ["integer", "null"]}, "vigente": {"type": "boolean"}, "en_firme": {"type": "boolean"},
            "max_dias_expedicion": {"type": ["integer", "null"]},
            "tabla": {"type": ["array", "null"], "items": {"type": "object", "properties": {
                "contratos_max": {"type": "integer"}, "pct": {"type": "number"}}, "required": ["contratos_max", "pct"]}},
        }, "required": ["id", "categoria", "titulo", "tipo", "pagina", "cita"]}},
        "campos": {"type": "object", "description": "datos sueltos para redactar la propuesta; cada uno {valor, pagina}",
                   "additionalProperties": {"type": "object", "properties": {"valor": {}, "pagina": {"type": "integer"}},
                                            "required": ["valor", "pagina"]}},
        "formatos": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "nombre": {"type": "string"}, "pagina": {"type": "integer"},
            "descripcion": {"type": ["string", "null"]}}, "required": ["id", "nombre", "pagina"]}},
    },
    "required": ["proceso", "requisitos", "campos", "formatos"],
}
CAMPOS_PROPUESTA = ["garantia_seriedad_pct", "garantia_seriedad_meses", "garantia_beneficiario", "puntaje_oferta_economica",
                    "puntaje_factor_calidad", "puntaje_industria_nacional", "puntaje_discapacidad", "experiencia_max_contratos",
                    "experiencia_tabla", "capital_trabajo_pct", "aval_ingeniero", "pacto_transparencia", "seguridad_social",
                    "vigencia_certificados_dias"]

HERRAMIENTA = {
    "name": "registrar_extraccion",
    "description": "Registra todo lo extraído del pliego. Llámala una sola vez con el resultado completo. "
                   "En `campos` incluye, cuando el pliego los trae, estas claves: " + ", ".join(CAMPOS_PROPUESTA) + ".",
    "input_schema": ESQUEMA,
}


class ExtraccionError(RuntimeError):
    pass


def disponible() -> bool:
    return bool(CFG.actual().anthropic_api_key)


# ------------------------------------------------------------------ Claude
def _cliente():
    import anthropic
    if not disponible():
        raise ExtraccionError("falta ANTHROPIC_API_KEY: la extracción de pliegos no está configurada")
    return anthropic.Anthropic(api_key=CFG.actual().anthropic_api_key)


def llamar_claude(pdf: bytes, cliente=None) -> tuple[dict, dict]:
    """Devuelve (input de la tool, uso de tokens)."""
    cliente = cliente or _cliente()
    respuesta = cliente.messages.create(
        model=MODELO, max_tokens=MAX_TOKENS, system=INSTRUCCIONES,
        tools=[HERRAMIENTA], tool_choice={"type": "tool", "name": "registrar_extraccion"},
        messages=[{"role": "user", "content": [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                            "data": base64.b64encode(pdf).decode()}},
            {"type": "text", "text": "Lee el pliego completo y registra la extracción."},
        ]}],
    )
    for bloque in respuesta.content:
        if getattr(bloque, "type", "") == "tool_use" and bloque.name == "registrar_extraccion":
            uso = getattr(respuesta, "usage", None)
            return dict(bloque.input), {"entrada": getattr(uso, "input_tokens", 0), "salida": getattr(uso, "output_tokens", 0)}
    raise ExtraccionError("Claude no devolvió la extracción (sin tool_use)")


def costo_usd(uso: dict) -> float:
    return round(uso.get("entrada", 0) / 1e6 * USD_ENTRADA + uso.get("salida", 0) / 1e6 * USD_SALIDA, 4)


# ---------------------------------------------------------------- formas
def _slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")
    return s or "req"


def a_formas(tool_input: dict, nombre_pdf: str, paginas: int) -> tuple[dict, dict]:
    """El input de la tool -> (requisitos.json, pliego.json) con las formas de
    los fixtures. Limpia ids repetidos y nulos que la logica no espera."""
    proc = dict(tool_input.get("proceso") or {})
    proc.setdefault("lotes", [])
    for i, lote in enumerate(proc["lotes"], 1):
        lote.setdefault("n", i)
        lote["cuantia_smmlv"] = round(lote["presupuesto"] / proc["smmlv"], 2) if proc.get("smmlv") else None
    proc["pdf"] = nombre_pdf
    proc["paginas"] = paginas
    vistos, requisitos = set(), []
    for r in tool_input.get("requisitos") or []:
        r = {k: v for k, v in r.items() if v is not None}
        rid = _slug(r.get("id") or r.get("titulo", ""))
        while rid in vistos:
            rid += "_"
        vistos.add(rid)
        r["id"] = rid
        if r.get("tipo") == "indicador" and "umbral" not in r:
            r["tipo"] = "revisar"
        requisitos.append(r)
    requisitos_json = {"proceso": proc, "requisitos": requisitos}
    campos = {k: v for k, v in (tool_input.get("campos") or {}).items() if isinstance(v, dict) and "valor" in v}
    for clave in ("entidad", "nit_entidad", "objeto", "modalidad", "lugar_ejecucion", "unspsc", "anticipo_pct"):
        if clave not in campos and proc.get(clave) is not None:
            campos[clave] = {"valor": proc[clave], "pagina": 1}
    campos.setdefault("proceso", {"valor": proc.get("id"), "pagina": 1})
    pliego_json = {"id": proc.get("id"), "pdf": nombre_pdf, "paginas": paginas, "smmlv": proc.get("smmlv"),
                   "fecha_cierre": proc.get("fecha_cierre"), "campos": campos,
                   "lotes": [{**lote} for lote in proc["lotes"]], "formatos": tool_input.get("formatos") or []}
    return requisitos_json, pliego_json


# ---------------------------------------------------------------- poppler
def poppler_disponible() -> bool:
    return bool(shutil.which("pdftotext") and shutil.which("pdftoppm"))


def n_paginas(pdf_ruta: Path) -> int:
    if shutil.which("pdfinfo"):
        salida = subprocess.run(["pdfinfo", str(pdf_ruta)], capture_output=True, text=True).stdout
        m = re.search(r"Pages:\s+(\d+)", salida)
        if m:
            return int(m.group(1))
    return 0


def citas_y_paginas(pdf_ruta: Path, requisitos_json: dict, destino: Path) -> dict:
    """Con poppler: localiza cada cita en su pagina (cajas 0-1) y renderiza
    las paginas citadas a destino/p<N>.png. Sin poppler devuelve {} y las
    paginas no se ven, pero el checklist funciona igual."""
    if not poppler_disponible():
        log.warning("sin poppler: no hay resaltado ni paginas del pliego")
        return {}
    from pliego.checklist.semilla import localizar, palabras_pagina
    destino.mkdir(parents=True, exist_ok=True)
    reqs = requisitos_json["requisitos"]
    paginas = sorted({r["pagina"] for r in reqs if r.get("pagina")} | {lote_["pagina"] for lote_ in requisitos_json["proceso"]["lotes"] if lote_.get("pagina")})
    cache, salida = {}, {}
    for n in paginas:
        try:
            cache[n] = palabras_pagina(pdf_ruta, n)
            subprocess.run(["pdftoppm", "-r", "72", "-png", "-f", str(n), "-l", str(n), str(pdf_ruta), str(destino / "p")],
                           check=True, capture_output=True)
            for f in destino.glob("p-*.png"):
                f.rename(destino / f"p{int(f.stem.split('-')[1])}.png")
        except Exception as e:   # una pagina rara no tumba la extraccion
            log.warning("pagina %s: %s", n, e)
    no_localizadas = []
    for r in reqs:
        if r.get("pagina") not in cache:
            continue
        w, h, palabras = cache[r["pagina"]]
        cajas = localizar(r.get("cita", ""), palabras)
        if not cajas and r.get("cita") and r.get("tipo") != "revisar":
            # El texto del PDF entra en el mismo canal que las instrucciones
            # del modelo. Una cita que no esta en la pagina que dice estar
            # puede ser una alucinacion o un pliego adulterado: no se toma
            # como hecho verificable, se manda a lectura humana.
            r["tipo_original"], r["tipo"], r["cita_no_localizada"] = r["tipo"], "revisar", True
            no_localizadas.append(r["id"])
        salida[r["id"]] = {"pagina": r["pagina"], "ancho": w, "alto": h,
                           "cajas": [[round(x0 / w, 4), round(y0 / h, 4), round(x1 / w, 4), round(y1 / h, 4)] for x0, y0, x1, y1 in cajas]}
    if no_localizadas:
        log.warning("citas no localizadas en su pagina (pasan a 'revisar'): %s", no_localizadas)
    return salida


# ------------------------------------------------------------------ todo
class DemasiadasPaginas(ExtraccionError):
    pass


def extraer(pdf: bytes, nombre: str, carpeta_paginas: Path | None = None, cliente=None,
            max_paginas: int | None = None) -> dict:
    """PDF -> {requisitos, extraccion, citas_bbox, paginas, costo_usd, uso}.
    Escribe las paginas PNG en carpeta_paginas si se da. Cuenta las paginas
    ANTES de llamar a Claude: un PDF por encima de `max_paginas` se rechaza
    sin gastar."""
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "pliego.pdf"
        ruta.write_bytes(pdf)
        paginas = n_paginas(ruta)
        if max_paginas and paginas > max_paginas:
            raise DemasiadasPaginas(f"el pliego tiene {paginas} páginas y el tope es {max_paginas}")
        tool_input, uso = llamar_claude(pdf, cliente)
        requisitos_json, pliego_json = a_formas(tool_input, nombre, paginas)
        cajas = citas_y_paginas(ruta, requisitos_json, carpeta_paginas) if carpeta_paginas else {}
    return {"requisitos": requisitos_json, "extraccion": pliego_json, "citas_bbox": cajas, "paginas": paginas,
            "costo_usd": costo_usd(uso), "uso": uso, "sha256": hashlib.sha256(pdf).hexdigest()}


def validar(tool_input: dict) -> list[str]:
    """Chequeos minimos sobre lo que devolvio el modelo (para el log)."""
    avisos = []
    p = tool_input.get("proceso") or {}
    if not p.get("lotes"):
        avisos.append("sin lotes")
    if not (p.get("smmlv") or 0) > 500_000:
        avisos.append("smmlv raro")
    if len(tool_input.get("requisitos") or []) < 5:
        avisos.append("menos de 5 requisitos")
    n = sum(1 for r in tool_input.get("requisitos") or [] if r.get("cita_no_localizada"))
    if n:
        avisos.append(f"{n} cita(s) no encontradas en su página; quedan para revisar")
    return avisos

