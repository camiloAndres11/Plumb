"""Servicio del checklist: paginas HTML + JSON.

    uvicorn pliego.checklist.app:app --port 8020 --reload

  /                     checklist del grupo (lote) elegido, agrupado por urgencia
  /requisito/{id}       el requisito sobre la pagina real del PDF, fragmento resaltado
  /carpeta              la carpeta de documentos de la constructora
  /pliego.pdf           el pliego completo (para abrirlo en el visor del navegador)
  /api/checklist?lote=  todo lo anterior en JSON
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse

from pliego.checklist import datos, logica
from pliego.comun import web as W

app = FastAPI(title="Pliego · Checklist de habilitantes", version="0.1.0")
app.mount("/static", W.Estaticos(W.STATIC), name="static")
templates = W.plantillas(Path(__file__).parent / "templates")
ITEMS = [("/", "check", "Checklist del pliego"), ("/carpeta", "doc", "Mi carpeta")]


@app.get("/paginas/p{n}.png")
def pagina_png(n: int):
    """Paginas citadas del pliego (fixtures o el pliego de la empresa)."""
    ruta = datos.ruta_pagina(n)
    if not ruta.exists():
        raise HTTPException(404, "pagina no renderizada")
    return FileResponse(ruta, media_type="image/png")


ESTADO = {
    logica.CUMPLE: ("Cumple", "tag tag-neutro", "check-on"),
    logica.NO_CUMPLE: ("No cumple", "tag", "check-no"),
    logica.FALTA: ("Falta documento", "tag tag-falta", "check-falta"),
    logica.REVISAR: ("Revisar", "tag tag-apagado", "check-rev"),
}
CATEGORIA = {"juridico": "Jurídico", "financiero": "Financiero", "tecnico": "Técnico", "experiencia": "Experiencia"}
ETIQUETAS_EV = {"crp": "Capacidad residual (suya)", "crpc": "Capacidad residual del proceso", "presupuesto": "Presupuesto del lote",
                "anticipo": "Anticipo", "valor": "Su valor", "umbral": "Umbral", "capital_trabajo": "Capital de trabajo",
                "demandado": "Capital demandado", "acreditado_smmlv": "Acreditado (SMMLV)", "requerido_smmlv": "Requerido (SMMLV)",
                "contratos_usados": "Contratos usados", "presupuesto_smmlv": "Presupuesto (SMMLV)", "dias_antes_del_cierre": "Días antes del cierre",
                "maximo": "Máximo admitido", "valor_requerido": "Valor a asegurar", "valor_asegurado": "Valor asegurado",
                "duracion_hasta": "Dura hasta", "minimo": "Mínimo exigido", "fecha_expedicion": "Expedido"}


def _pagina(request: Request, plantilla: str, titulo: str, actual: str, **ctx):
    return W.render(templates, request, plantilla, titulo=titulo, items=ITEMS, actual=actual,
                    constructora=datos.carpeta()["constructora"], ESTADO=ESTADO, CATEGORIA=CATEGORIA, **ctx)


def _checklist(lote: int) -> dict:
    try:
        return datos.checklist(lote)
    except KeyError:
        raise HTTPException(404, "ese lote no existe en el pliego")


# ------------------------------------------------------------------ JSON
@app.get("/api/checklist")
def api_checklist(lote: int = Query(1, ge=1)):
    return _checklist(lote)


@app.get("/api/carpeta")
def api_carpeta():
    return datos.carpeta()


@app.get("/pliego.pdf")
def pliego_pdf():
    return FileResponse(datos.ruta_pdf(), media_type="application/pdf")


# ------------------------------------------------------------------ HTML
@app.get("/", response_class=HTMLResponse)
def checklist(request: Request, lote: int = Query(1, ge=1)):
    ck = _checklist(lote)
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
    stats = [("Cumple", c["cumple"], ""), ("No cumple", c["no_cumple"], "hot" if c["no_cumple"] else "mute"),
             ("Falta documento", c["falta_documento"], "hot" if c["falta_documento"] else "mute"), ("Revisar", c["revisar"], "mute")]
    return _pagina(request, "checklist/lista.html", f"Checklist · Grupo {lote_['n']}", "/", p=p, lote_=lote_, res=res,
                   titular=titular, stats=stats, bloquean=bloquean, revisar=revisar, ok=ok)


def _valor_ev(v) -> str:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return W.mill(v) if abs(v) >= 1e6 else (W.entero(v) if float(v).is_integer() else str(round(v, 2)).replace(".", ","))
    return str(v)


@app.get("/requisito/{id_req}", response_class=HTMLResponse)
def requisito(request: Request, id_req: str, lote: int = Query(1, ge=1)):
    ck = _checklist(lote)
    reqs = ck["requisitos"]
    idx = next((i for i, r in enumerate(reqs) if r["id"] == id_req), None)
    if idx is None:
        raise HTTPException(404, "requisito no encontrado")
    r = reqs[idx]
    sig = reqs[(idx + 1) % len(reqs)]
    cajas = (r.get("caja") or {}).get("cajas", [])
    minis = [(ETIQUETAS_EV[k], _valor_ev(v)) for k, v in (r["evidencia"] or {}).items() if k in ETIQUETAS_EV]
    docs = datos.carpeta()["documentos"]
    fuente_doc = docs[r["documento"]].get("archivo", "—") if r.get("documento") and r["documento"] in docs else None
    return _pagina(request, "checklist/requisito.html", f"{r['titulo'][:40]} · p. {r['pagina']}", "/", ck=ck, r=r, sig=sig,
                   lote=lote, cajas=cajas, minis=minis, fuente_doc=fuente_doc)


@app.get("/carpeta", response_class=HTMLResponse)
def carpeta(request: Request):
    c = datos.carpeta()
    documentos = []
    for k, d in c["documentos"].items():
        campos = {kk: vv for kk, vv in d.items() if kk not in ("archivo", "contratos", "contratos_en_ejecucion") and not isinstance(vv, (list, dict))}
        documentos.append((k, d, " · ".join(f"{kk.replace('_', ' ')}: {vv}" for kk, vv in list(campos.items())[:4])))
    faltan = sorted({r["documento"] for r in datos.extraccion()["requisitos"] if r.get("documento")} - set(c["documentos"]))
    return _pagina(request, "checklist/carpeta.html", "Mi carpeta", "/carpeta", documentos=documentos, faltan=faltan,
                   rup=c["documentos"]["rup"]["contratos"])
