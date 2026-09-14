"""Servicio del generador: paginas HTML + JSON + exportacion.

    uvicorn pliego.generador.app:app --port 8050 --reload

  /?lote=N                      documentos de la oferta con estado y lo que falta
  /documento/{id}?lote=N        borrador con cada dato marcado por origen + tabla de fuentes
  /documento/{id}.md?lote=N     el borrador en markdown (descarga)
  /paquete.zip?lote=N           todos los borradores + lo_que_falta.md
  /perfil, /pliego.pdf, /api/paquete?lote=N
"""
from __future__ import annotations

import html as _html
import io
import json
import re
import zipfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from markupsafe import Markup

from pliego.comun import web as W
from pliego.generador import datos
from pliego.generador import logica as L

app = FastAPI(title="Pliego · Generador de propuesta", version="0.1.0")
app.mount("/static", W.Estaticos(W.STATIC), name="static")
templates = W.plantillas(Path(__file__).parent / "templates")
ITEMS = [("/", "doc", "Propuesta"), ("/perfil", "perfil", "Mi perfil")]

ESTADO = {L.LISTO: ("Listo", "tag tag-neutro"), L.CON_FALTANTES: ("Con faltantes", "tag"),
          L.ADJUNTAR: ("Adjuntar", "tag tag-borde"), L.NO_APLICA: ("No aplica", "tag tag-apagado")}
ORIGEN = {L.PLIEGO: "Pliego", L.PERFIL: "Perfil", L.CALCULADO: "Calculado", L.FALTANTE: "Falta", L.NOAP: "No aplica"}

def _pagina(request: Request, plantilla: str, titulo: str, actual: str, **ctx):
    c = datos.perfil()
    perfil_c = {"nombre": c.get("nombre"), "nit": c.get("nit"),
                "ciudad": c.get("ciudad") or ((c.get("sede") or {}).get("ciudad") or "").title()}
    return W.render(templates, request, plantilla, titulo=titulo, items=ITEMS, actual=actual, perfil_c=perfil_c,
                    ESTADO=ESTADO, ORIGEN=ORIGEN, L=L, **ctx)


def _fmt(v) -> str:
    if isinstance(v, bool):
        return "sí" if v else "no"
    if isinstance(v, (int, float)):
        return ("$" + f"{v:,.0f}".replace(",", ".")) if abs(v) >= 1000 else str(v).replace(".", ",")
    if isinstance(v, list):
        if v and isinstance(v[0], dict):
            return "%d elementos: %s" % (len(v), "; ".join(str(x.get("objeto") or x.get("nombre") or "…") for x in v[:3]))
        return ", ".join(str(x) for x in v)
    return str(v)


def md_a_html(md: str) -> str:
    """Conversor minimo: parrafos, negrita, cursiva, listas y tablas. Sin dependencias."""
    def inline(s):
        s = _html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"(?<![\w])_(.+?)_(?![\w])", r"<i>\1</i>", s)
        return s
    bloques = re.split(r"\n\s*\n", md.strip())
    out = []
    for b in bloques:
        lineas = b.split("\n")
        if all(lote_.strip().startswith("|") for lote_ in lineas):
            filas = [[c.strip() for c in lote_.strip().strip("|").split("|")] for lote_ in lineas if not re.match(r"^\|\s*-", lote_.strip())]
            if not filas:
                continue
            th = "".join(f"<th>{inline(c)}</th>" for c in filas[0])
            td = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in f) + "</tr>" for f in filas[1:])
            out.append(f"<table><thead><tr>{th}</tr></thead><tbody>{td}</tbody></table>")
        elif all(re.match(r"^\d+\. ", lote_.strip()) for lote_ in lineas):
            out.append("<ol>" + "".join(f"<li>{inline(re.sub(r'^\d+\. ', '', lote_.strip()))}</li>" for lote_ in lineas) + "</ol>")
        elif all(lote_.strip().startswith("- ") for lote_ in lineas):
            out.append("<ul>" + "".join(f"<li>{inline(lote_.strip()[2:])}</li>" for lote_ in lineas) + "</ul>")
        else:
            out.append("<p>" + "<br>".join(inline(lote_) for lote_ in lineas) + "</p>")
    return "".join(out)


def marcar(html_doc: str, campos: list[L.Campo]) -> str:
    """Subraya la primera aparicion del valor de cada campo con su origen.
    Best effort: valores cortos o numericos pueden no encontrarse."""
    hechos = set()
    for c in sorted(campos, key=lambda c: -len(_fmt(c.valor))):
        if c.origen not in (L.PLIEGO, L.PERFIL, L.CALCULADO) or c.valor in (None, "", [], True, False):
            continue
        for candidato in {_fmt(c.valor), str(c.valor)}:
            if len(candidato) < 3 or candidato in hechos:
                continue
            esc = _html.escape(candidato)
            idx = html_doc.find(esc)
            if idx >= 0 and "<mark" not in html_doc[max(0, idx - 40):idx]:
                html_doc = html_doc[:idx] + f'<mark class="m-{c.origen}" title="{W.h(c.etiqueta)} · {W.h(ORIGEN[c.origen])}{f" p. {c.pagina}" if c.pagina else ""}">{esc}</mark>' + html_doc[idx + len(esc):]
                hechos.add(candidato)
                break
    return html_doc


# ------------------------------------------------------------------ JSON
@app.get("/api/paquete")
def api_paquete(lote: int = Query(1, ge=1)):
    try:
        return datos.paquete(lote)
    except KeyError:
        raise HTTPException(404, "ese lote no existe en el pliego")


@app.get("/pliego.pdf")
def pliego_pdf():
    return FileResponse(datos.ruta_pdf(), media_type="application/pdf")


@app.get("/documento/{id_doc}.md")
def documento_md(id_doc: str, lote: int = Query(1, ge=1)):
    d = datos.documento(id_doc, lote)
    if not d:
        raise HTTPException(404, "documento no encontrado")
    return PlainTextResponse(d.texto, media_type="text/markdown; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{id_doc}_grupo{lote}.md"'})


@app.get("/paquete.zip")
def paquete_zip(lote: int = Query(1, ge=1)):
    try:
        docs = datos.documentos(lote)
    except KeyError:
        raise HTTPException(404, "ese lote no existe en el pliego")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for d in docs:
            z.writestr(f"{d.id}.md", d.texto or f"_{d.nombre}: sin borrador._\n")
        falta = L.lo_que_falta(docs)
        z.writestr("00_lo_que_falta.md", "# Lo que falta\n\n" + "\n".join(
            f"- {'**[RECHAZO]** ' if f['critico'] else ''}{f['etiqueta']} — {f['documento_nombre']} ({f['fuente']})" for f in falta) + "\n")
        z.writestr("00_origenes.json", json.dumps(
            [{"documento": d.id, "campos": [c.como_dict() for c in d.campos]} for d in docs], ensure_ascii=False, indent=1))
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="propuesta_{datos.proceso_id()}_grupo{lote}.zip"'})


# ------------------------------------------------------------------ HTML
@app.get("/", response_class=HTMLResponse)
def inicio(request: Request, lote: int = Query(1, ge=1)):
    try:
        p = datos.paquete(lote)
    except KeyError:
        raise HTTPException(404, "ese lote no existe en el pliego")
    r, lote_ = p["resumen"], p["lote"]
    aplican = r["total"] - r["conteo"][L.NO_APLICA]
    pct = round(100 * r["conteo"][L.LISTO] / aplican) if aplican else 0
    nc = r["faltantes_criticos"]
    titular = (f"La propuesta está al {pct} %: {r['conteo'][L.LISTO]} borradores listos, "
               + ("nada la rechaza." if nc == 0 else ("falta 1 cosa que la rechaza." if nc == 1 else f"faltan {nc} cosas que la rechazan.")))
    documentos = [(d, {o: sum(1 for c in d["campos"] if c["origen"] == o) for o in ORIGEN}) for d in p["documentos"]]
    return _pagina(request, "generador/inicio.html", f"Propuesta · Grupo {lote}", "/", p=p, r=r, lote_=lote_, lote=lote,
                   titular=titular, documentos=documentos, entidad=datos.pliego()["campos"]["entidad"]["valor"])


@app.get("/documento/{id_doc}", response_class=HTMLResponse)
def documento(request: Request, id_doc: str, lote: int = Query(1, ge=1)):
    try:
        docs = datos.documentos(lote)
    except KeyError:
        raise HTTPException(404, "ese lote no existe en el pliego")
    idx = next((i for i, d in enumerate(docs) if d.id == id_doc), None)
    if idx is None:
        raise HTTPException(404, "documento no encontrado")
    d = docs[idx]
    ant, sig = docs[idx - 1], docs[(idx + 1) % len(docs)]
    # md_a_html escapa el texto antes de marcarlo: es HTML ya seguro.
    cuerpo_doc = Markup(marcar(md_a_html(d.texto), d.campos)) if d.texto else Markup('<p class="note">Sin borrador: faltan los datos de base.</p>')
    campos = [(c, _fmt(c.valor) if c.valor not in (None, "") else "—") for c in d.campos]
    return _pagina(request, "generador/documento.html", d.nombre, "/", d=d, ant=ant, sig=sig, lote=lote,
                   cuerpo_doc=cuerpo_doc, campos=campos)


@app.get("/perfil", response_class=HTMLResponse)
def perfil(request: Request):
    p = datos.perfil()
    return _pagina(request, "generador/perfil.html", "Mi perfil", "/perfil", p=p, rl=p["representante_legal"], f=p["financiero"])
