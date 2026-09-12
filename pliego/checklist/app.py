"""Servicio del checklist: paginas HTML + JSON.

    uvicorn pliego.checklist.app:app --port 8020 --reload

  /                     checklist del grupo (lote) elegido, agrupado por urgencia
  /requisito/{id}       el requisito sobre la pagina real del PDF, fragmento resaltado
  /carpeta              la carpeta de documentos de la constructora
  /pliego.pdf           el pliego completo (para abrirlo en el visor del navegador)
  /api/checklist?lote=  todo lo anterior en JSON
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from pliego.checklist import datos, logica
from pliego.comun import web as W

app = FastAPI(title="Pliego · Checklist de habilitantes", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(W.STATIC)), name="static")
app.mount("/paginas", StaticFiles(directory=str(datos.FIXTURES / "paginas")), name="paginas")

ESTADO = {
    logica.CUMPLE: ("Cumple", "tag tag-neutro", "check-on"),
    logica.NO_CUMPLE: ("No cumple", "tag", "check-no"),
    logica.FALTA: ("Falta documento", "tag tag-falta", "check-falta"),
    logica.REVISAR: ("Revisar", "tag tag-apagado", "check-rev"),
}
CATEGORIA = {"juridico": "Jurídico", "financiero": "Financiero", "tecnico": "Técnico", "experiencia": "Experiencia"}
ICONO_NO = ('<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#ff8a72" stroke-width="3" '
            'stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"></path></svg>')

EXTRA_CSS = """<style>
.check-no { border: 1.5px solid var(--ad-accent-2); }
.check-falta { border: 1.5px dashed var(--ad-ink-45); }
.check-rev { border: 1.5px solid var(--ad-ink-35); font-size: 11px; color: var(--ad-ink-60); }
.tag-falta { background: transparent; border: 1px solid var(--ad-accent-2); color: var(--ad-accent-2); }
.req { display: grid; grid-template-columns: 18px minmax(0,1fr) 150px 74px; gap: 14px; align-items: start; padding: 12px 14px; border-radius: 12px; background: var(--ad-fill-4); }
.req:hover { background: var(--ad-fill-2); }
.req b { font-size: 15px; font-weight: 600; display: block; }
.req small { display: block; font-size: 13px; color: var(--ad-ink-55); margin-top: 3px; }
.req .pag { font-size: 13px; color: var(--ad-ink-70); text-align: right; white-space: nowrap; }
.pdf { position: relative; width: 612px; margin: 0 auto; box-shadow: var(--ad-shadow); }
.pdf img { display: block; width: 612px; height: auto; }
.marca { position: absolute; background: rgba(236,48,19,.35); outline: 2px solid rgba(236,48,19,.6); border-radius: 2px; }
.stats-4 { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 12px; }
</style>"""


def _side(actual: str) -> str:
    c = datos.carpeta()["constructora"]
    pie = (f'<div class="side-foot"><div class="kicker">Carpeta de</div><b>{W.h(c["nombre"])}</b>'
           f'<small>{W.h(c["ciudad"])} · NIT {W.h(c["nit"])}</small></div>')
    return W.sidebar([("/", "check", "Checklist del pliego"), ("/carpeta", "doc", "Mi carpeta")], actual, pie)


W.ICONOS["check"] = ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
                     'stroke-linecap="round"><path d="M9 11l3 3L22 4"></path><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>')


def _icono(estado: str) -> str:
    _, _, clase = ESTADO[estado]
    dentro = {"check-on": W.ICONOS["check"], "check-no": ICONO_NO, "check-rev": "?"}.get(clase, "")
    return f'<span class="{clase}">{dentro}</span>'


def _fila(r: dict, lote: int) -> str:
    texto, tag, _ = ESTADO[r["estado"]]
    return (f'<a class="req" href="/requisito/{W.h(r["id"])}?lote={lote}">{_icono(r["estado"])}'
            f'<div><b>{W.h(r["titulo"])}</b><small>{W.h(r["detalle"])} · Sección {W.h(r["seccion"])} · '
            f'{CATEGORIA.get(r["categoria"], r["categoria"])}</small></div>'
            f'<span class="{tag}" style="justify-self:start">{texto}</span>'
            f'<span class="pag">p. {r["pagina"]} →</span></a>')


def _grupo(titulo: str, sub: str, filas: list[dict], lote: int) -> str:
    if not filas:
        return ""
    return (f'<div class="card" style="padding:18px 22px"><div class="card-head"><div class="card-title">{titulo}</div>'
            f'<div class="card-label">{sub}</div></div><div class="rows" style="margin-top:12px">'
            + "".join(_fila(r, lote) for r in filas) + "</div></div>")


# ------------------------------------------------------------------ JSON
@app.get("/api/checklist")
def api_checklist(lote: int = Query(1, ge=1)):
    try:
        return datos.checklist(lote)
    except KeyError:
        raise HTTPException(404, "ese lote no existe en el pliego")


@app.get("/api/carpeta")
def api_carpeta():
    return datos.carpeta()


@app.get("/pliego.pdf")
def pliego_pdf():
    return FileResponse(datos.FIXTURES / datos.extraccion()["proceso"]["pdf"], media_type="application/pdf")


# ------------------------------------------------------------------ HTML
@app.get("/", response_class=HTMLResponse)
def checklist(lote: int = Query(1, ge=1)):
    try:
        ck = datos.checklist(lote)
    except KeyError:
        raise HTTPException(404, "ese lote no existe en el pliego")
    p, lote_, res = ck["proceso"], ck["lote"], ck["resumen"]
    c = res["conteo"]
    reqs = ck["requisitos"]
    bloquean = [r for r in reqs if r["estado"] in (logica.NO_CUMPLE, logica.FALTA)]
    revisar = [r for r in reqs if r["estado"] == logica.REVISAR]
    ok = [r for r in reqs if r["estado"] == logica.CUMPLE]
    n_b = len(bloquean)
    titular = ("Queda habilitado en el Grupo %d; %d puntos por revisar." % (lote_["n"], len(revisar)) if not n_b else
               ("Le falta 1 cosa para quedar habilitado en el Grupo %d." % lote_["n"] if n_b == 1 else
                "Le faltan %d cosas para quedar habilitado en el Grupo %d." % (n_b, lote_["n"])))
    tabs = "".join(
        f'<a class="tab{" on" if x["n"] == lote_["n"] else ""}" href="/?lote={x["n"]}">Grupo {x["n"]} · {W.mill(x["presupuesto"])}</a>'
        for x in p["lotes"])

    def stat(label, n, clase=""):
        return (f'<div class="stat" style="padding:16px 20px"><div class="card-label">{label}</div>'
                f'<div class="big num {clase}" style="font-size:36px">{n}</div></div>')

    cuerpo = f"""
<div class="cab">
  <div><div class="kicker">{W.h(p['id'])} · {W.h(W.titulo_caso(p['entidad']))} · Licitación de obra pública</div>
  <h1 class="titulo" style="font-size:26px;max-width:820px">{W.h(titular)}</h1>
  <p class="mute" style="font-size:14px;margin-top:6px">{W.h(lote_['nombre'])} · plazo {lote_['plazo_meses']} meses · {W.entero(lote_['cuantia_smmlv'])} SMMLV</p></div>
  <div class="tabs">{tabs}</div>
</div>
<div class="stats-4">{stat("Cumple", c['cumple'])}{stat("No cumple", c['no_cumple'], "hot" if c['no_cumple'] else "mute")}
{stat("Falta documento", c['falta_documento'], "hot" if c['falta_documento'] else "mute")}{stat("Revisar", c['revisar'], "mute")}</div>
{_grupo("Lo que impide presentarse hoy", "primero lo que no se subsana solo", bloquean, lote_['n'])}
{_grupo("Revisar", "juicio humano o umbral que no viene en el PDF", revisar, lote_['n'])}
{_grupo("Cumple", f"{len(ok)} de {res['total']}", ok, lote_['n'])}
<p class="foot-note">Cada requisito enlaza a la página exacta del pliego donde está escrito. Los umbrales financieros no vienen en el PDF (Matriz 2): se marcan para revisar aunque el dato cumpla.
La extracción de requisitos es manual en este prototipo; la carpeta de documentos es ficticia. <a href="/pliego.pdf" target="_blank" style="color:var(--ad-ink-85)">Abrir el pliego completo →</a></p>
"""
    return W.pagina(f"Checklist · Grupo {lote_['n']}", cuerpo, _side("/"), EXTRA_CSS)


@app.get("/requisito/{id_req}", response_class=HTMLResponse)
def requisito(id_req: str, lote: int = Query(1, ge=1)):
    try:
        ck = datos.checklist(lote)
    except KeyError:
        raise HTTPException(404, "ese lote no existe en el pliego")
    reqs = ck["requisitos"]
    idx = next((i for i, r in enumerate(reqs) if r["id"] == id_req), None)
    if idx is None:
        raise HTTPException(404, "requisito no encontrado")
    r = reqs[idx]
    sig = reqs[(idx + 1) % len(reqs)]
    texto, tag, _ = ESTADO[r["estado"]]
    caja = r.get("caja") or {}
    marcas = "".join(
        f'<div class="marca" style="left:{100 * x0:.2f}%;top:{100 * y0:.2f}%;width:{100 * (x1 - x0):.2f}%;height:{100 * (y1 - y0):.2f}%"></div>'
        for x0, y0, x1, y1 in caja.get("cajas", []))
    ev = r["evidencia"]
    minis = ""
    if ev:
        etiquetas = {"crp": "Capacidad residual (suya)", "crpc": "Capacidad residual del proceso", "presupuesto": "Presupuesto del lote",
                     "anticipo": "Anticipo", "valor": "Su valor", "umbral": "Umbral", "capital_trabajo": "Capital de trabajo",
                     "demandado": "Capital demandado", "acreditado_smmlv": "Acreditado (SMMLV)", "requerido_smmlv": "Requerido (SMMLV)",
                     "contratos_usados": "Contratos usados", "presupuesto_smmlv": "Presupuesto (SMMLV)", "dias_antes_del_cierre": "Días antes del cierre",
                     "maximo": "Máximo admitido", "valor_requerido": "Valor a asegurar", "valor_asegurado": "Valor asegurado",
                     "duracion_hasta": "Dura hasta", "minimo": "Mínimo exigido", "fecha_expedicion": "Expedido"}
        partes = []
        for k, v in ev.items():
            if k not in etiquetas:
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                s = W.mill(v) if abs(v) >= 1e6 else (W.entero(v) if float(v).is_integer() else str(round(v, 2)).replace(".", ","))
            else:
                s = str(v)
            partes.append(f'<div class="mini"><small>{etiquetas[k]}</small><b class="num" style="font-size:18px">{W.h(s)}</b></div>')
        minis = f'<div class="grid-2" style="margin-top:16px">{"".join(partes)}</div>' if partes else ""
    fuente = (f'<div class="card-label" style="margin-top:14px">Fuente del dato: {W.h(datos.carpeta()["documentos"].get(r["documento"], {}).get("archivo", "—"))} de su carpeta.</div>'
              if r.get("documento") and r["documento"] in datos.carpeta()["documentos"] else
              (f'<div class="card-label" style="margin-top:14px">En su carpeta no hay ningún documento de tipo «{W.h((r.get("documento") or "").replace("_", " "))}».</div>' if r.get("documento") else ""))
    cuerpo = f"""
<nav class="migas"><a href="/?lote={lote}">Checklist del pliego</a><span>/</span><span>Grupo {lote}</span><span>/</span><span>{W.h(r['titulo'][:48])}{'…' if len(r['titulo']) > 48 else ''} · p. {r['pagina']}</span></nav>
<div class="grid-5-7" style="align-items:start">
  <div style="display:flex;flex-direction:column;gap:14px">
    <div class="card" style="padding:24px 28px">
      <div class="card-label">Requisito {CATEGORIA.get(r['categoria'], r['categoria']).lower()} · sección {W.h(r['seccion'])}</div>
      <div style="font-size:20px;font-weight:600;letter-spacing:-.02em;margin-top:8px;line-height:1.25">{W.h(r['titulo'])}</div>
      <div style="display:flex;align-items:center;gap:12px;margin-top:16px">{_icono(r['estado'])}<span class="{tag}">{texto}</span></div>
      <div style="font-size:15px;margin-top:14px;line-height:1.5">{W.h(r['detalle'])}</div>
      {minis}{fuente}
    </div>
    <div class="draft" style="padding:20px 24px"><div class="kicker">Fragmento del pliego · p. {r['pagina']}</div>
      <p style="margin-top:10px">«{W.h(r['cita'])}»</p></div>
    <div style="display:flex;gap:10px"><a class="btn" style="padding:11px 20px;font-size:14px" href="/pliego.pdf#page={r['pagina']}" target="_blank">Abrir el PDF completo</a>
      <a class="btn-ghost" style="padding:11px 20px;font-size:14px" href="/requisito/{W.h(sig['id'])}?lote={lote}">Siguiente requisito →</a></div>
  </div>
  <div class="card" style="padding:18px;background:var(--ad-panel-2)">
    <div class="card-head" style="margin-bottom:12px"><span class="card-label">{W.h(ck['proceso']['pdf'])} · página {r['pagina']} de {ck['proceso']['paginas']}</span></div>
    <div class="pdf"><img src="/paginas/p{r['pagina']}.png" alt="Página {r['pagina']} del pliego">{marcas}</div>
  </div>
</div>
"""
    return W.pagina(f"{r['titulo'][:40]} · p. {r['pagina']}", cuerpo, _side("/"), EXTRA_CSS)


@app.get("/carpeta", response_class=HTMLResponse)
def carpeta():
    c = datos.carpeta()
    filas = []
    for k, d in c["documentos"].items():
        campos = {kk: vv for kk, vv in d.items() if kk not in ("archivo", "contratos", "contratos_en_ejecucion") and not isinstance(vv, (list, dict))}
        resumen = " · ".join(f"{kk.replace('_', ' ')}: {vv}" for kk, vv in list(campos.items())[:4])
        filas.append(f'<div class="req" style="grid-template-columns:18px minmax(0,1fr)"><span class="check-on">{W.ICONOS["check"]}</span>'
                     f'<div><b>{W.h(d.get("archivo", k))}</b><small>{W.h(k.replace("_", " "))} · {W.h(resumen)}</small></div></div>')
    faltan = sorted({r["documento"] for r in datos.extraccion()["requisitos"] if r.get("documento")} - set(c["documentos"]))
    for k in faltan:
        filas.append(f'<div class="req" style="grid-template-columns:18px minmax(0,1fr)"><span class="check-falta"></span>'
                     f'<div><b class="hot">{W.h(k.replace("_", " "))}</b><small>El pliego lo pide y no está en la carpeta.</small></div></div>')
    rup = c["documentos"]["rup"]["contratos"]
    tabla = "".join(f'<tr><td>{x["consecutivo"]}</td><td>{W.h(x["objeto"])}</td><td>{", ".join(x["actividades"]).replace("_", " ")}</td>'
                    f'<td class="num">{W.entero(x["valor_smmlv"])}</td><td>{"sí" if x["terminado"] else "en ejecución"}</td></tr>' for x in rup)
    cuerpo = f"""
<div class="cab"><div><div class="kicker">Mi carpeta · ficticia, para el prototipo</div><h1 class="titulo">{W.h(c['constructora']['nombre'])}</h1></div></div>
<div class="grid-5-7">
  <div class="card"><div class="card-head"><div class="card-title">Documentos</div><div class="card-label">{len(c['documentos'])} en carpeta · {len(faltan)} faltan</div></div>
    <div class="rows" style="margin-top:12px">{"".join(filas)}</div></div>
  <div class="card"><div class="card-head"><div class="card-title">Contratos en el RUP</div><div class="card-label">{len(rup)} contratos</div></div>
    <table class="tabla" style="margin-top:12px"><thead><tr><th>#</th><th>Objeto</th><th>Actividades</th><th class="num">SMMLV</th><th>Terminado</th></tr></thead><tbody>{tabla}</tbody></table></div>
</div>
<p class="foot-note">La carpeta vive en pliego/checklist/fixtures/documentos_constructora.json. En producción los campos los extrae el pipeline de cada PDF del cliente.</p>
"""
    return W.pagina("Mi carpeta", cuerpo, _side("/carpeta"), EXTRA_CSS)
