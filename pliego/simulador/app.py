"""Servicio del simulador: paginas HTML + JSON.

    uvicorn pliego.simulador.app:app --port 8030 --reload

  /                      lista de procesos abiertos (licitacion y seleccion abreviada)
  /proceso/{id}          precio recomendado, control del precio y puntaje por metodo
  /backtest              en que porcentaje el precio recomendado habria quedado primero
  /api/recomendacion/{id}, /api/backtest, /api/procesos, /api/versiones
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from markupsafe import Markup

from pliego.comun import fuente
from pliego.comun import web as W
from pliego.simulador import datos
from pliego.simulador.metodos import VERSION_DEFECTO, VERSIONES

app = FastAPI(title="Pliego · Simulador de oferta", version="0.1.0")
app.mount("/static", W.Estaticos(W.STATIC), name="static")
templates = W.plantillas(Path(__file__).parent / "templates")
ITEMS = [("/", "grafico", "Simulador de oferta"), ("/backtest", "hoy", "Backtest")]

MODALIDAD_CORTA = {"LICITACION PUBLICA OBRA PUBLICA": "Licitación pública",
                   "SELECCION ABREVIADA DE MENOR CUANTIA": "Selección abreviada"}
TRAZO = {"mediana": "", "geometrica": "6 4", "aritmetica_baja": "2 3", "menor_valor": "10 4 2 4"}
BACKTEST_N, BACKTEST_SIM = 40, 80


def _precalentar():
    """El backtest tarda unos segundos la primera vez; se calcula en un hilo
    al arrancar para que la pagina responda al instante. Va aqui y no en
    el lifespan porque Starlette no propaga el lifespan de una app montada
    (la demo del equipo monta esta app bajo /simulador)."""
    try:
        datos.backtest(VERSION_DEFECTO, BACKTEST_N, BACKTEST_SIM)
    except Exception:   # nunca tumbar el servicio por precalentar
        pass


threading.Thread(target=_precalentar, daemon=True).start()

def _pagina(request: Request, plantilla: str, titulo: str, actual: str, **ctx):
    return W.render(templates, request, plantilla, titulo=titulo, items=ITEMS, actual=actual, MODALIDAD_CORTA=MODALIDAD_CORTA, **ctx)


_pct = W.pct
_f1 = W.num1


def grafico_svg(malla: list[dict], rango: list[float], ratio: float, metodos: list[dict]) -> str:
    W_, H_, L, R, T, B = 640, 260, 46, 110, 18, 34
    xs = [p["ratio"] for p in malla]
    lo, hi = min(xs), max(xs)
    ymin, ymax = 50, 60

    def X(x):
        return L + (x - lo) / (hi - lo) * (W_ - L - R)

    def Y(y):
        return T + (ymax - max(ymin, y)) / (ymax - ymin) * (H_ - T - B)

    def path(vals):
        return "M" + " L".join(f"{X(x):.1f},{Y(v):.1f}" for x, v in zip(xs, vals))

    s = [f'<svg viewBox="0 0 {W_} {H_}" style="display:block;width:100%;height:auto;overflow:visible" font-family="Archivo, system-ui, sans-serif">']
    for y in range(ymin, ymax + 1, 2):
        s.append(f'<line x1="{L}" x2="{W_ - R}" y1="{Y(y):.1f}" y2="{Y(y):.1f}" stroke="rgba(255,255,255,.08)"/>'
                 f'<text x="{L - 8}" y="{Y(y) + 4:.1f}" font-size="11" fill="rgba(242,240,238,.5)" text-anchor="end">{y}</text>')
    for x in (0.85, 0.90, 0.95, 1.00):
        s.append(f'<text x="{X(x):.1f}" y="{H_ - 12}" font-size="11" fill="rgba(242,240,238,.5)" text-anchor="middle">{int(round(x * 100))} %</text>')
    s.append(f'<rect x="{X(rango[0]):.1f}" y="{T}" width="{X(rango[1]) - X(rango[0]):.1f}" height="{H_ - T - B}" fill="rgba(236,48,19,.08)"/>')
    esp = [p["esperado"] for p in malla]
    # etiquetas directas al final de cada linea, separadas al menos 13 px
    etiquetas = [(Y(vals[-1]), W.h(m["nombre"]), False) for m in metodos
                 for vals in [[p["por_metodo"][m["clave"]] for p in malla]]] + [(Y(esp[-1]), "Esperado", True)]
    etiquetas.sort(key=lambda e: e[0])
    ys = []
    for y, *_ in etiquetas:
        ys.append(max(y, ys[-1] + 13) if ys else y)
    for m in metodos:
        vals = [p["por_metodo"][m["clave"]] for p in malla]
        s.append(f'<path d="{path(vals)}" fill="none" stroke="rgba(242,240,238,.45)" stroke-width="1.5" stroke-dasharray="{TRAZO.get(m["clave"], "")}"/>')
    s.append(f'<path d="{path(esp)}" fill="none" stroke="#ec3013" stroke-width="2.5"/>')
    for (_y0, texto, hot), y in zip(etiquetas, ys):
        s.append(f'<text x="{W_ - R + 6}" y="{y + 4:.1f}" font-size="11" fill="{"#ff8a72" if hot else "rgba(242,240,238,.6)"}"'
                 f'{" font-weight=\"600\"" if hot else ""}>{texto}</text>')
    pt = next(p for p in malla if p["ratio"] == ratio)
    s.append(f'<line id="cursor" x1="{X(ratio):.1f}" x2="{X(ratio):.1f}" y1="{T}" y2="{H_ - B}" stroke="#ff8a72" stroke-width="1" stroke-dasharray="3 3"/>'
             f'<circle cx="{X(ratio):.1f}" cy="{Y(pt["esperado"]):.1f}" r="6" fill="#ec3013" stroke="#121214" stroke-width="2"/>')
    s.append("</svg>")
    return "".join(s)


# ------------------------------------------------------------------ JSON
@app.get("/api/procesos")
def api_procesos():
    return {"total": len(datos.abiertos()), "datos": datos.abiertos()}


@app.get("/api/versiones")
def api_versiones():
    return {k: {"nombre": v.nombre, "fuente": v.fuente, "puntaje_maximo": v.puntaje_maximo,
                "metodos": [{"clave": m.clave, "nombre": m.nombre, "centavos": [m.centavos_desde, m.centavos_hasta],
                             "probabilidad": m.probabilidad} for m in v.metodos]} for k, v in VERSIONES.items()}


@app.get("/api/recomendacion/{id_proceso}")
def api_recomendacion(id_proceso: str, version: str = VERSION_DEFECTO, n_sim: int = Query(400, ge=20, le=2000)):
    if version not in VERSIONES:
        raise HTTPException(400, "version desconocida; ver /api/versiones")
    try:
        return datos.recomendar_para(id_proceso, version, n_sim)
    except KeyError:
        raise HTTPException(404, "proceso no esta en el snapshot")


@app.get("/api/backtest")
def api_backtest(version: str = VERSION_DEFECTO):
    return datos.backtest(version, BACKTEST_N, BACKTEST_SIM)


# ------------------------------------------------------------------ HTML
@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    return RedirectResponse(request.scope.get("root_path", "") + "/proceso/" + datos.abiertos()[0]["id_del_proceso"])


@app.get("/proceso/{id_proceso}", response_class=HTMLResponse)
def proceso(request: Request, id_proceso: str, version: str = VERSION_DEFECTO):
    if version not in VERSIONES:
        raise HTTPException(400, "version desconocida")
    try:
        r = datos.recomendar_para(id_proceso, version)
    except KeyError:
        raise HTTPException(404, "proceso no encontrado")
    p, pool, malla = r["proceso"], r["pool"], r["malla"]
    pt = next(x for x in malla if x["ratio"] == r["ratio"])
    lo, hi = r["rango"]
    return _pagina(request, "simulador/proceso.html", f"Simulador · {p['id_del_proceso']}", "/", r=r, p=p, pool=pool, malla=malla,
                   pt=pt, idx_pt=malla.index(pt), lo=lo, hi=hi, v=VERSIONES[version], version=version,
                   grafico=Markup(grafico_svg(malla, r["rango"], r["ratio"], r["metodos"])),
                   malla_json=Markup(json.dumps({"malla": malla, "precio_base": p["precio_base"]}).replace("</", "<\\/")),
                   abiertos=datos.abiertos(), etiqueta_fecha=fuente.etiqueta_fecha())


@app.get("/backtest", response_class=HTMLResponse)
def backtest(request: Request, version: str = VERSION_DEFECTO):
    b = datos.backtest(version, BACKTEST_N, BACKTEST_SIM)
    med_of = sorted(x["n_oferentes"] for x in b["resultados"])[len(b["resultados"]) // 2] if b["n"] else 0
    return _pagina(request, "simulador/backtest.html", "Backtest", "/backtest", b=b, version=version, med_of=med_of,
                   azar=round(100 / max(med_of, 1)))
