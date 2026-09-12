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
import re
import zipfile

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from pliego.comun import web as W
from pliego.generador import datos, logica as L

app = FastAPI(title="Pliego · Generador de propuesta", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(W.STATIC)), name="static")

ESTADO = {L.LISTO: ("Listo", "tag tag-neutro"), L.CON_FALTANTES: ("Con faltantes", "tag"),
          L.ADJUNTAR: ("Adjuntar", "tag tag-borde"), L.NO_APLICA: ("No aplica", "tag tag-apagado")}
ORIGEN = {L.PLIEGO: "Pliego", L.PERFIL: "Perfil", L.CALCULADO: "Calculado", L.FALTANTE: "Falta", L.NOAP: "No aplica"}

EXTRA_CSS = """<style>
.tag-borde { background: transparent; border: 1px solid rgba(255,255,255,.2); color: var(--ad-ink-85); }
.o { padding: 3px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; white-space: nowrap; }
.o-pliego { background: var(--ad-accent-soft); color: var(--ad-accent-2); }
.o-perfil { background: rgba(255,255,255,.1); color: var(--ad-ink-85); }
.o-calculado { background: rgba(255,180,140,.12); color: var(--ad-accent-3); }
.o-faltante { border: 1px solid var(--ad-accent-2); color: var(--ad-accent-2); }
.o-no_aplica { border: 1px solid var(--ad-line-2); color: var(--ad-ink-50); }
.doc { display: grid; grid-template-columns: minmax(0,1fr) 260px 120px 70px; gap: 14px; align-items: center; padding: 12px 14px; border-radius: 12px; background: var(--ad-fill-4); }
.doc:hover { background: var(--ad-fill-2); }
.doc b { font-size: 15px; font-weight: 600; display: block; }
.doc small { display: block; font-size: 13px; color: var(--ad-ink-55); margin-top: 3px; }
.doc .pag { font-size: 13px; color: var(--ad-ink-70); text-align: right; }
.grid-8-4 { display: grid; grid-template-columns: minmax(0,8fr) minmax(0,4fr); gap: 18px; align-items: start; }
.falta { display: flex; justify-content: space-between; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--ad-line-soft); font-size: 14px; }
.falta:last-child { border-bottom: 0; }
.falta small { display: block; font-size: 12px; color: var(--ad-ink-55); margin-top: 2px; }
.papel { border-radius: 18px; background: var(--ad-paper); color: var(--ad-paper-ink); padding: 32px 36px; font-size: 15px; line-height: 1.6; }
.papel p { margin: 0 0 14px; } .papel ol, .papel ul { margin: 0 0 14px; padding-left: 22px; }
.papel table { border-collapse: collapse; width: 100%; font-size: 13px; margin: 0 0 14px; }
.papel th, .papel td { border-bottom: 1px solid rgba(26,26,28,.12); padding: 6px 8px; text-align: left; vertical-align: top; }
.papel th { font-size: 11px; letter-spacing: .04em; text-transform: uppercase; color: var(--ad-paper-mute); }
.papel mark { background: transparent; color: inherit; border-radius: 2px; padding: 0 2px; border-bottom: 2px solid; }
.papel mark.m-pliego { border-color: #ec3013; background: rgba(236,48,19,.08); }
.papel mark.m-perfil { border-color: #8a8580; background: rgba(26,26,28,.06); }
.papel mark.m-calculado { border-color: #ffb4a0; background: rgba(255,180,140,.18); }
.papel .leyenda { font-size: 12px; letter-spacing: .06em; text-transform: uppercase; color: var(--ad-paper-mute); margin-bottom: 14px; }
.campo { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 10px; padding: 9px 0; border-bottom: 1px solid var(--ad-line-soft); font-size: 13px; align-items: start; }
.campo:last-child { border-bottom: 0; }
.campo small { color: var(--ad-ink-55); font-size: 12px; display: block; }
.campo .src { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
.campo .src a, .campo .src span.f { font-size: 11px; color: var(--ad-ink-50); }
</style>"""


def _side(actual: str) -> str:
    c = datos.perfil()
    pie = f'<div class="side-foot"><div class="kicker">Perfil activo</div><b>{W.h(c["nombre"])}</b><small>{W.h(c["ciudad"])} · NIT {W.h(c["nit"])}</small></div>'
    return W.sidebar([("/", "doc", "Propuesta"), ("/perfil", "perfil", "Mi perfil")], actual, pie)


def _otag(o: str, extra: str = "") -> str:
    return f'<span class="o o-{o}">{ORIGEN[o]}{extra}</span>'


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
    return FileResponse(datos.FIXTURES / datos.pliego()["pdf"], media_type="application/pdf")


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
        z.writestr("00_origenes.json", __import__("json").dumps(
            [{"documento": d.id, "campos": [c.como_dict() for c in d.campos]} for d in docs], ensure_ascii=False, indent=1))
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="propuesta_{datos.PROCESO_ID}_grupo{lote}.zip"'})


# ------------------------------------------------------------------ HTML
@app.get("/", response_class=HTMLResponse)
def inicio(lote: int = Query(1, ge=1)):
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
    tabs = "".join(f'<a class="tab{" on" if x["n"] == lote_["n"] else ""}" href="/?lote={x["n"]}">Grupo {x["n"]}</a>' for x in p["proceso"]["lotes"])
    filas = ""
    for d in p["documentos"]:
        n = {o: sum(1 for c in d["campos"] if c["origen"] == o) for o in ORIGEN}
        orig = " ".join(_otag(o, f" · {n[o]}") for o in (L.PLIEGO, L.PERFIL, L.CALCULADO) if n[o]) + (" " + _otag(L.FALTANTE, f" · {n[L.FALTANTE]}") if n[L.FALTANTE] else "")
        t, cl = ESTADO[d["estado"]]
        filas += (f'<a class="doc" href="/documento/{d["id"]}?lote={lote}"><div><b>{W.h(d["nombre"])}</b><small>{W.h(d["descripcion"])}</small></div>'
                  f'<div class="chips" style="gap:6px">{orig}</div><span class="{cl}" style="justify-self:start">{t}</span><span class="pag">p. {d["pagina"]} →</span></a>')
    falta = "".join(f'<div class="falta"><span><b class="{"hot" if f["critico"] else ""}">{W.h(f["etiqueta"])}</b><small>{W.h(f["documento_nombre"])} · {W.h(f["fuente"])}</small></span>{_otag(L.FALTANTE, " · rechazo" if f["critico"] else "")}</div>'
                    for f in p["faltantes"]) or '<span class="mute" style="font-size:13px">Nada: todo lo que el pliego pide está en el perfil.</span>'
    cuerpo = f"""
<div class="cab"><div><div class="kicker">{W.h(p['proceso']['id'])} · {W.h(datos.pliego()['campos']['entidad']['valor'])} · Grupo {lote_['n']} · {W.mill(lote_['presupuesto'])}</div>
<h1 class="titulo" style="font-size:26px">{W.h(titular)}</h1>
<p class="mute" style="font-size:14px;margin-top:6px">{r['origenes'][L.PLIEGO]} datos salieron del pliego, {r['origenes'][L.PERFIL]} del perfil, {r['origenes'][L.CALCULADO]} se calcularon y {r['origenes'][L.FALTANTE]} faltan.</p></div>
<div style="display:flex;gap:10px;align-items:center"><div class="tabs">{tabs}</div><a class="btn" style="padding:11px 20px;font-size:14px" href="/paquete.zip?lote={lote}">Exportar paquete (.zip)</a></div></div>
<div class="grid-8-4">
  <div class="card"><div class="card-head"><div class="card-title">Documentos de la oferta</div><div class="card-label">en el orden del pliego · cada dato con su origen</div></div><div class="rows" style="margin-top:14px">{filas}</div></div>
  <div style="display:flex;flex-direction:column;gap:14px">
    <div class="card"><div class="card-head"><div class="card-title">Lo que falta, en orden</div><div class="card-label">primero lo que rechaza la oferta</div></div><div style="margin-top:6px">{falta}</div></div>
    <div class="card"><div class="card-label">Cómo leer los orígenes</div><div style="display:flex;flex-direction:column;gap:8px;margin-top:10px;font-size:13px;color:var(--ad-ink-75)">
      <div>{_otag(L.PLIEGO)} sale del pliego, con la página</div><div>{_otag(L.PERFIL)} sale de su perfil</div><div>{_otag(L.CALCULADO)} se deriva de los dos, con la fórmula</div><div>{_otag(L.FALTANTE)} no está en ninguno: hay que conseguirlo</div></div></div>
  </div>
</div>
<p class="foot-note">Los borradores se redactan con los datos del pliego y de su perfil; revíselos y ajústelos antes de firmar. El pliego es real (SECOP II, <a href="/pliego.pdf" target="_blank" style="color:var(--ad-ink-85)">abrir PDF</a>); el perfil es ficticio.</p>
"""
    return W.pagina(f"Propuesta · Grupo {lote}", cuerpo, _side("/"), EXTRA_CSS)


@app.get("/documento/{id_doc}", response_class=HTMLResponse)
def documento(id_doc: str, lote: int = Query(1, ge=1)):
    try:
        docs = datos.documentos(lote)
    except KeyError:
        raise HTTPException(404, "ese lote no existe en el pliego")
    idx = next((i for i, d in enumerate(docs) if d.id == id_doc), None)
    if idx is None:
        raise HTTPException(404, "documento no encontrado")
    d = docs[idx]
    ant, sig = docs[idx - 1], docs[(idx + 1) % len(docs)]
    t, cl = ESTADO[d.estado]
    cuerpo_doc = marcar(md_a_html(d.texto), d.campos) if d.texto else '<p class="note">Sin borrador: faltan los datos de base.</p>'
    filas = ""
    for c in d.campos:
        if c.origen == L.PLIEGO and c.pagina:
            src = f'<a href="/pliego.pdf#page={c.pagina}" target="_blank">p. {c.pagina} →</a>'
        elif c.origen == L.PERFIL:
            src = f'<span class="f">{W.h(c.fuente.replace("perfil.", ""))}</span>'
        else:
            src = f'<span class="f" title="{W.h(c.fuente)}">{W.h(c.fuente[:48])}{"…" if len(c.fuente) > 48 else ""}</span>'
        val = _fmt(c.valor) if c.valor not in (None, "") else "—"
        filas += (f'<div class="campo"><div><small>{W.h(c.etiqueta)}{" · rechazo si falta" if c.critico and c.origen == L.FALTANTE else ""}</small>'
                  f'<div style="margin-top:2px;line-height:1.35" class="{"hot" if c.origen == L.FALTANTE else ""}">{W.h(val[:90])}{"…" if len(val) > 90 else ""}</div></div>'
                  f'<div class="src">{_otag(c.origen)}{src}</div></div>')
    cuerpo = f"""
<nav class="migas"><a href="/?lote={lote}">Propuesta</a><span>/</span><span>Grupo {lote}</span><span>/</span><span>{W.h(d.nombre)}</span></nav>
<div class="cab"><div><div class="kicker">Borrador · el pliego lo exige en la p. {d.pagina}</div><h1 class="titulo" style="font-size:24px">{W.h(d.nombre)}</h1></div>
<div style="display:flex;gap:10px;align-items:center"><span class="{cl}">{t}</span><a class="btn-ghost" style="padding:11px 20px;font-size:14px" href="/documento/{ant.id}?lote={lote}">← Anterior</a>
<a class="btn-ghost" style="padding:11px 20px;font-size:14px" href="/documento/{sig.id}?lote={lote}">Siguiente →</a><a class="btn" style="padding:11px 20px;font-size:14px" href="/documento/{d.id}.md?lote={lote}">Descargar .md</a></div></div>
<div class="grid-7-5" style="align-items:start">
  <div class="papel"><div class="leyenda">Vista previa · subrayado por origen: <span style="border-bottom:2px solid #ec3013">pliego</span> · <span style="border-bottom:2px solid #8a8580">perfil</span> · <span style="border-bottom:2px solid #ffb4a0">calculado</span></div>{cuerpo_doc}</div>
  <div class="card"><div class="card-head"><div class="card-title">De dónde sale cada dato</div><div class="card-label">{len(d.campos)} campos · {len(d.faltantes)} faltan</div></div><div style="margin-top:6px">{filas}</div>
  <div class="mute-50" style="font-size:12px;margin-top:12px">Cada "p. N" abre el pliego en esa página. Los cálculos muestran su fórmula.</div></div>
</div>
"""
    return W.pagina(d.nombre, cuerpo, _side("/"), EXTRA_CSS)


@app.get("/perfil", response_class=HTMLResponse)
def perfil():
    p = datos.perfil()
    rl, f = p["representante_legal"], p["financiero"]
    rup = "".join(f'<tr><td>{c["consecutivo"]}</td><td>{W.h(c["objeto"])}</td><td>{W.h(c["entidad"])}</td><td class="num">{W.entero(c["valor_smmlv"])}</td><td>{"sí" if c["terminado"] else "no"}</td></tr>' for c in p["rup"]["contratos"])
    cuerpo = f"""
<div class="cab"><div><div class="kicker">Mi perfil · ficticio, para el prototipo</div><h1 class="titulo">{W.h(p['nombre'])}</h1></div></div>
<div class="grid-5-7">
  <div class="card"><div class="card-title">Datos que entran a los borradores</div>
    <div class="grid-2" style="margin-top:16px">
      <div class="mini"><small>NIT</small><b class="txt">{W.h(p['nit'])}</b></div><div class="mini"><small>Representante legal</small><b class="txt">{W.h(rl['nombre'])} · {W.h(rl['profesion'])}</b></div>
      <div class="mini"><small>Dirección</small><b class="txt">{W.h(p['direccion'])}, {W.h(p['ciudad'])}</b></div><div class="mini"><small>Correo</small><b class="txt">{W.h(p['correo'])}</b></div>
      <div class="mini"><small>Capacidad residual</small><b class="num">{W.mill(p['capacidad_residual']['crp'])}</b></div><div class="mini"><small>Estados financieros</small><b class="txt">corte {f['corte']} · {W.h(f['revisor_fiscal'])}</b></div>
    </div></div>
  <div class="card"><div class="card-head"><div class="card-title">Contratos en el RUP</div><div class="card-label">{len(p['rup']['contratos'])} · expedido {p['rup']['fecha_expedicion']}</div></div>
    <table class="tabla" style="margin-top:12px"><thead><tr><th>#</th><th>Objeto</th><th>Entidad</th><th class="num">SMMLV</th><th>Terminado</th></tr></thead><tbody>{rup}</tbody></table></div>
</div>
<p class="foot-note">El perfil vive en pliego/generador/fixtures/perfil_constructora.json. Lo que no esté aquí sale como "Falta" en los borradores.</p>
"""
    return W.pagina("Mi perfil", cuerpo, _side("/perfil"), EXTRA_CSS)
