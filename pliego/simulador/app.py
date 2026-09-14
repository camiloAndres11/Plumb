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

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from pliego.comun import fuente
from pliego.comun import web as W
from pliego.simulador import datos
from pliego.simulador.metodos import VERSIONES, VERSION_DEFECTO

app = FastAPI(title="Pliego · Simulador de oferta", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(W.STATIC)), name="static")

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

EXTRA_CSS = """<style>
.dos { display: grid; grid-template-columns: 300px minmax(0,1fr); gap: 24px; align-items: start; }
.lista { display: flex; flex-direction: column; gap: 8px; max-height: calc(100vh - 60px); overflow-y: auto; position: sticky; top: 30px; padding-right: 4px; }
.proc { display: block; padding: 12px 14px; border-radius: 12px; background: var(--ad-fill-4); }
.proc:hover { background: var(--ad-fill-2); }
.proc.on { background: var(--ad-fill-2); border: 1px solid var(--ad-line-soft); }
.proc b { display: block; font-size: 14px; font-weight: 600; line-height: 1.3; }
.proc small { display: block; font-size: 12px; color: var(--ad-ink-55); margin-top: 3px; }
.busca { display: flex; align-items: center; gap: 8px; padding: 9px 12px; border-radius: 999px; background: var(--ad-fill-2); border: 1px solid var(--ad-line); font-size: 13px; color: var(--ad-ink-50); }
.busca input { background: transparent; border: 0; outline: 0; width: 100%; color: var(--ad-ink); }
.grande { font-size: 64px; line-height: .95; font-weight: 600; letter-spacing: -.05em; color: var(--ad-accent-2); margin-top: 10px; }
.rango { position: relative; height: 6px; border-radius: 999px; background: var(--ad-line); margin-top: 8px; }
.rango span { position: absolute; height: 100%; border-radius: 999px; background: linear-gradient(90deg, var(--ad-accent), var(--ad-accent-2)); }
input[type=range] { width: 100%; margin: 14px 0 0; accent-color: #f2f0ee; }
.met { display: flex; justify-content: space-between; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--ad-line-soft); font-size: 14px; }
.met:last-child { border-bottom: 0; }
.met b { font-variant-numeric: tabular-nums; }
.met .trm { color: var(--ad-ink-50); font-size: 12px; margin-left: 8px; }
</style>"""


def _side(actual: str) -> str:
    return W.sidebar([("/", "grafico", "Simulador de oferta"), ("/backtest", "hoy", "Backtest")], actual)


def _f1(x) -> str:
    return f"{x:.1f}".replace(".", ",")


def _pct(x, dec=1) -> str:
    return f"{100 * x:.{dec}f}".replace(".", ",") + " %"


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
    for (y0, texto, hot), y in zip(etiquetas, ys):
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
def _lista(actual: str | None) -> str:
    filas = "".join(
        f'<a class="proc{" on" if a["id_del_proceso"] == actual else ""}" href="/proceso/{W.h(a["id_del_proceso"])}" data-busca="{W.h((a["entidad"] + " " + (a["descripcion"] or "")).lower())}">'
        f'<b>{W.h(W.frase(a["descripcion"] or "Sin descripción")[:80])}</b>'
        f'<small>{W.h(W.titulo_caso(a["entidad"]))} · {W.h(W.titulo_caso(a["departamento"]))} · {W.mill(a["precio_base"])} · cierra en {a["dias_restantes"]} días</small></a>'
        for a in datos.abiertos())
    return (f'<div class="lista"><div class="kicker">Procesos abiertos · licitación y selección abreviada</div>'
            f'<label class="busca"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.3-4.3"></path></svg>'
            f'<input id="busca" placeholder="Buscar entidad u objeto"></label>{filas}'
            f'<div class="mute-50" style="font-size:12px">{len(datos.abiertos())} procesos · {fuente.etiqueta_fecha()}</div></div>')


JS_LISTA = """<script>
(function(){var i=document.getElementById('busca');if(!i)return;var f=Array.prototype.slice.call(document.querySelectorAll('.proc'));
i.addEventListener('input',function(){var q=i.value.toLowerCase();f.forEach(function(a){a.hidden=q&&a.dataset.busca.indexOf(q)<0;});});})();
</script>"""


@app.get("/", response_class=HTMLResponse)
def inicio():
    return RedirectResponse("/proceso/" + datos.abiertos()[0]["id_del_proceso"])


@app.get("/proceso/{id_proceso}", response_class=HTMLResponse)
def proceso(id_proceso: str, version: str = VERSION_DEFECTO):
    if version not in VERSIONES:
        raise HTTPException(400, "version desconocida")
    try:
        r = datos.recomendar_para(id_proceso, version)
    except KeyError:
        raise HTTPException(404, "proceso no encontrado")
    p, pool, malla = r["proceso"], r["pool"], r["malla"]
    pt = next(x for x in malla if x["ratio"] == r["ratio"])
    lo, hi = r["rango"]
    metodos = "".join(
        f'<div class="met" data-metodo="{m["clave"]}"><span>{W.h(m["nombre"])}<span class="trm">TRM {m["centavos"][0]:02d}–{m["centavos"][1]:02d} ¢ · {_pct(m["probabilidad"], 0)}</span></span>'
        f'<b class="num val">{_f1(pt["por_metodo"][m["clave"]])}</b></div>'
        for m in r["metodos"])
    v = VERSIONES[version]
    cuerpo = f"""
<div class="dos">
  {_lista(id_proceso)}
  <div style="display:flex;flex-direction:column;gap:18px">
    <div><div class="kicker">{W.h(p['id_del_proceso'])} · {W.h(W.titulo_caso(p['entidad']))} · {MODALIDAD_CORTA.get(p['modalidad'], p['modalidad'])} · presupuesto {W.mill(p['precio_base'])}</div>
      <h1 class="titulo" style="font-size:26px">Oferte al {_pct(r['ratio'])}: {W.mill(r['precio_recomendado']).replace('$', '$').replace(' mill.', ' millones')}.</h1>
      <p class="mute" style="font-size:14px;margin-top:4px">{W.h(W.frase(p['descripcion'] or ''))[:140]}</p></div>
    <div class="grid-5-7">
      <div class="card" style="display:flex;flex-direction:column">
        <div class="card-label">Precio recomendado</div>
        <div class="grande num">{_pct(r['ratio'])}</div>
        <div style="font-size:14px;color:var(--ad-ink-60);margin-top:10px">del presupuesto oficial · <b class="num" style="color:var(--ad-ink)">{W.mill(r['precio_recomendado'])}</b></div>
        <div class="card-label" style="margin-top:18px">Rango con menos de 1 punto de diferencia</div>
        <div class="rango"><span style="left:{100 * (lo - 0.85) / 0.15:.0f}%;width:{100 * (hi - lo) / 0.15:.0f}%"></span></div>
        <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--ad-ink-50);margin-top:6px"><span>85 %</span><span class="num" style="color:var(--ad-ink-85)">{_pct(lo)} – {_pct(hi)} · {W.mill(r['rango_pesos'][0])} – {W.mill(r['rango_pesos'][1])}</span><span>100 %</span></div>
        <div class="grid-2" style="margin-top:18px">
          <div class="mini"><small>Puntaje esperado</small><b class="num" style="font-size:22px">{_f1(r['esperado'])} <span class="mute-50" style="font-size:12px;font-weight:400">de {int(v.puntaje_maximo)}</span></b></div>
          <div class="mini"><small>Queda primero</small><b class="num" style="font-size:22px">{_pct(pt['prob_primero'], 0)} <span class="mute-50" style="font-size:12px;font-weight:400">entre ~{int(pool['mediana_oferentes'] or 0)} ofertas</span></b></div>
        </div>
      </div>
      <div class="card">
        <div class="card-head"><div class="card-title">Puntaje esperado según el precio</div><div class="card-label">{r['n_sim']} escenarios · pool: {W.h(pool['descripcion'])} ({pool['n']} procesos)</div></div>
        <div style="margin-top:14px">{grafico_svg(malla, r['rango'], r['ratio'], r['metodos'])}</div>
        <div class="mute-50" style="font-size:12px;margin-top:6px">Línea roja: promedio ponderado por la probabilidad de cada método. Grises: cada método por separado. Banda: el rango recomendado.</div>
      </div>
    </div>
    <div class="grid-5-7">
      <div class="card">
        <div class="card-head"><div class="card-title">Su precio</div><div class="card-label">mueva y compare</div></div>
        <div style="display:flex;align-items:baseline;gap:10px;margin-top:12px"><span id="su-pct" class="num" style="font-size:30px;font-weight:600;letter-spacing:-.03em">{_pct(r['ratio'])}</span><span id="su-cop" class="num" style="font-size:14px;color:var(--ad-ink-60)">{W.mill(r['precio_recomendado'])}</span></div>
        <input type="range" id="slider" min="0" max="{len(malla) - 1}" step="1" value="{malla.index(pt)}" aria-label="Precio como fracción del presupuesto">
        <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--ad-ink-50);margin-top:4px"><span>85 %</span><span>100 %</span></div>
        <div style="margin-top:14px;font-size:13px;color:var(--ad-ink-55)">Competidores probables: la mediana de las ofertas ganadoras en {W.h(pool['descripcion'])} es {_pct(pool['mediana_ratio'])} con {int(pool['mediana_oferentes'] or 0)} oferentes por proceso.</div>
      </div>
      <div class="card">
        <div class="card-head"><div class="card-title">Puntaje por método a ese precio</div><div class="card-label">el método lo eligen los centavos de la TRM</div></div>
        <div style="margin-top:8px">{metodos}
          <div class="met"><span><b>Esperado</b><span class="trm">ponderado</span></span><b class="num hot" id="su-esp">{_f1(pt['esperado'])}</b></div>
          <div class="met"><span>Queda primero</span><b class="num" id="su-pri">{_pct(pt['prob_primero'], 0)}</b></div></div>
      </div>
    </div>
    <p class="foot-note">Fórmulas: {W.h(v.fuente)}. SECOP solo publica la oferta ganadora: los competidores se simulan con esa distribución. Es una estimación, no una garantía.
    Versión de documentos tipo: <code>{W.h(version)}</code> (configurable en <code>pliego/simulador/metodos.py</code>).</p>
  </div>
</div>
<script>
window.MALLA = {json.dumps(malla)}; window.PB = {p['precio_base']};
(function(){{
  var s=document.getElementById('slider'), M=window.MALLA;
  function f1(x){{return x.toFixed(1).replace('.',',');}}
  function pct(x,d){{return (100*x).toFixed(d).replace('.',',')+' %';}}
  function mill(x){{return '$'+Math.round(x/1e6).toString().replace(/\\B(?=(\\d{{3}})+(?!\\d))/g,'.')+' mill.';}}
  s.addEventListener('input',function(){{var p=M[+s.value];
    document.getElementById('su-pct').textContent=pct(p.ratio,1);
    document.getElementById('su-cop').textContent=mill(p.ratio*window.PB);
    document.getElementById('su-esp').textContent=f1(p.esperado);
    document.getElementById('su-pri').textContent=pct(p.prob_primero,0);
    document.querySelectorAll('.met[data-metodo]').forEach(function(el){{el.querySelector('.val').textContent=f1(p.por_metodo[el.dataset.metodo]);}});
    var c=document.getElementById('cursor'); if(c){{var x=46+(p.ratio-0.85)/0.15*(640-46-110); c.setAttribute('x1',x); c.setAttribute('x2',x);}}
  }});
}})();
</script>
{JS_LISTA}
"""
    return W.pagina(f"Simulador · {p['id_del_proceso']}", cuerpo, _side("/"), EXTRA_CSS)


@app.get("/backtest", response_class=HTMLResponse)
def backtest(version: str = VERSION_DEFECTO):
    b = datos.backtest(version, BACKTEST_N, BACKTEST_SIM)
    filas = "".join(
        f'<tr><td>{W.h(W.titulo_caso(x["entidad"]))}</td><td class="mute">{x["fecha"][:7]}</td><td class="num">{W.mill(x["precio_base"])}</td>'
        f'<td class="num">{x["n_oferentes"]}</td><td class="num">{_pct(x["ratio_ganador"])}</td><td class="num hot">{_pct(x["ratio_recomendado"])}</td>'
        f'<td class="num">{_pct(x["gana_al_ganador"], 0)}</td><td class="num">{_pct(x["prob_primero"], 0)}</td></tr>'
        for x in reversed(b["resultados"]))
    med_of = sorted(x["n_oferentes"] for x in b["resultados"])[len(b["resultados"]) // 2] if b["n"] else 0
    cuerpo = f"""
<div><div class="kicker">Backtest · {b['n']} licitaciones recientes con 3 o más ofertas · fórmulas {W.h(version)}</div>
<h1 class="titulo" style="font-size:26px">El precio recomendado le habría ganado a la oferta ganadora real en el {_pct(b['pct_gana_al_ganador'], 0)} de los procesos.</h1></div>
<div class="stats">
  <div class="stat"><div class="card-label">Le gana al ganador real</div><div class="big num hot" style="font-size:44px">{_pct(b['pct_gana_al_ganador'], 0)}</div><div class="mute-50" style="font-size:12px;margin-top:8px">promedio sobre métodos, ponderado por su probabilidad</div></div>
  <div class="stat"><div class="card-label">Queda primero entre todos los simulados</div><div class="big num" style="font-size:44px">{_pct(b['pct_primero'], 0)}</div><div class="mute-50" style="font-size:12px;margin-top:8px">con una mediana de {med_of} ofertas por proceso; al azar sería ~{round(100 / max(med_of, 1))} %</div></div>
  <div class="stat"><div class="card-label">Procesos evaluados</div><div class="big num" style="font-size:44px">{b['n']}</div><div class="mute-50" style="font-size:12px;margin-top:8px">cada uno recomendado sin mirar su propio resultado · {b['n_sim']} escenarios</div></div>
</div>
<div class="card"><div class="card-head"><div class="card-title">Proceso a proceso</div><div class="card-label">"Ganó al" es la razón oferta ganadora / presupuesto oficial</div></div>
<table class="tabla" style="margin-top:12px"><thead><tr><th>Entidad</th><th>Fecha</th><th class="num">Presupuesto</th><th class="num">Ofertas</th><th class="num">Ganó al</th><th class="num">Recomendado</th><th class="num">Le gana al ganador</th><th class="num">Primero</th></tr></thead><tbody>{filas}</tbody></table></div>
<p class="foot-note">Cómo se mide: para cada proceso histórico se arma el pool de competidores sin ese proceso, se recomienda un precio, y se mete esa oferta junto con la ganadora real en escenarios simulados. "Le gana" = más puntaje que la ganadora real, ponderado por la probabilidad de cada método. Sin las ofertas perdedoras (SECOP no las publica) no hay mejor prueba.</p>
"""
    return W.pagina("Backtest", cuerpo, _side("/backtest"), EXTRA_CSS)
