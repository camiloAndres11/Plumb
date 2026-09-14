"""Servicio del radar: paginas HTML + JSON.

    uvicorn pliego.radar.app:app --port 8040 --reload

  /                     buscador + procesos abiertos + entidades y competidores mas activos
  /proceso/{id}         competidores probables de un proceso abierto
  /entidad/{nit}?tipo=  perfil de entidad (quien gana ahi y como)
  /competidor/{doc}     perfil de competidor (donde gana, a que precio, saturacion)
  /api/...              lo mismo en JSON
"""
from __future__ import annotations

import threading

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from pliego.comun import fuente
from pliego.comun import web as W
from pliego.radar import datos

app = FastAPI(title="Pliego · Radar de competidores", version="0.1.0")


def _precalentar():
    """Cargar los 67k contratos e indexarlos tarda unos segundos; se hace
    en un hilo al importar para que la primera pagina no espere. No va en
    el lifespan porque Starlette no lo propaga a una app montada."""
    try:
        datos.entidades_mas_activas()
        datos.competidores_mas_activos()
    except Exception:
        pass


threading.Thread(target=_precalentar, daemon=True).start()
app.mount("/static", StaticFiles(directory=str(W.STATIC)), name="static")

TIPOS = ["OBRA", "INTERVENTORIA", "CONSULTORIA"]
TIPO_NOMBRE = {"OBRA": "Obra", "INTERVENTORIA": "Interventoría", "CONSULTORIA": "Consultoría"}
ETIQUETA = {"predecible": ("predecible", "hot"), "abierta": ("abierta", "hot"), "intermedia": ("intermedia", ""),
            "sin_muestra": ("sin muestra suficiente", "mute")}
SAT = {"con_capacidad": ("Con capacidad", "tag tag-apagado"), "cargado": ("Cargado", "tag tag-neutro"),
       "saturado": ("Saturado", "tag")}
MODALIDAD_CORTA = {"LICITACION PUBLICA OBRA PUBLICA": "Licitación pública", "SELECCION ABREVIADA DE MENOR CUANTIA": "Selección abreviada",
                   "CONCURSO DE MERITOS ABIERTO": "Concurso de méritos", "MINIMA CUANTIA": "Mínima cuantía",
                   "LICITACION PUBLICA": "Licitación pública", "CONTRATACION REGIMEN ESPECIAL (CON OFERTAS)": "Régimen especial"}

EXTRA_CSS = """<style>
.stats-4 { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 12px; }
.gana { display: flex; flex-direction: column; gap: 14px; margin-top: 16px; }
.gana .linea { display: flex; justify-content: space-between; gap: 16px; font-size: 14px; }
.gana .linea span:last-child { color: var(--ad-ink-70); white-space: nowrap; }
.gana .bar { margin-top: 8px; }
.rank { display: grid; grid-template-columns: 28px minmax(0,1fr) 150px 120px 90px; gap: 14px; align-items: center; padding: 12px 14px; border-radius: 12px; background: var(--ad-fill-4); }
.rank:hover { background: var(--ad-fill-2); }
.rank.on { background: var(--ad-fill-2); }
.rank b { font-size: 15px; font-weight: 600; display: block; }
.rank small { display: block; font-size: 13px; color: var(--ad-ink-55); margin-top: 3px; }
.rank .n { color: var(--ad-ink-50); font-size: 13px; font-variant-numeric: tabular-nums; }
.rank .peso { font-size: 20px; font-weight: 600; text-align: right; font-variant-numeric: tabular-nums; }
.grid-8-4 { display: grid; grid-template-columns: minmax(0,8fr) minmax(0,4fr); gap: 18px; align-items: start; }
.anios { display: flex; align-items: flex-end; gap: 8px; height: 90px; margin-top: 14px; }
.anios div { display: flex; flex-direction: column; align-items: center; gap: 6px; flex: 1; height: 100%; justify-content: flex-end; }
.anios i { display: block; width: 100%; border-radius: 4px 4px 0 0; background: var(--ad-ink-45); }
.anios span { font-size: 11px; color: var(--ad-ink-50); }
.lin { display: flex; justify-content: space-between; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--ad-line-soft); font-size: 14px; }
.lin:last-child { border-bottom: 0; }
.busca { display: flex; align-items: center; gap: 8px; padding: 10px 14px; border-radius: 999px; background: var(--ad-fill-2); border: 1px solid var(--ad-line); font-size: 14px; color: var(--ad-ink-50); max-width: 520px; }
.busca input { background: transparent; border: 0; outline: 0; width: 100%; color: var(--ad-ink); font-size: 14px; }
.res { display: flex; flex-direction: column; gap: 6px; margin-top: 10px; }
.res a { padding: 9px 12px; border-radius: 10px; background: var(--ad-fill-4); font-size: 14px; display: flex; justify-content: space-between; gap: 12px; }
.res a small { color: var(--ad-ink-50); }
</style>"""

W.ICONOS["radar"] = ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">'
                     '<circle cx="12" cy="12" r="9"></circle><circle cx="12" cy="12" r="4"></circle><path d="M12 3v3M12 18v3M3 12h3M18 12h3"></path></svg>')
W.ICONOS["entidad"] = ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">'
                       '<path d="M3 21h18M5 21V7l7-4 7 4v14M9 21v-6h6v6"></path></svg>')


def _side(actual: str) -> str:
    return W.sidebar([("/", "radar", "Radar"), ("/entidades", "entidad", "Entidades"), ("/competidores", "gente", "Competidores")], actual)


def _pct(x, dec=0) -> str:
    return "sin dato" if x is None else (f"{100 * x:.{dec}f}".replace(".", ",") + " %")


def _stat(label, val, sub="", hot=False):
    return (f'<div class="stat" style="padding:16px 20px"><div class="card-label">{label}</div>'
            f'<div class="big num{" hot" if hot else ""}" style="font-size:36px">{val}</div>'
            f'{f"<div class=mute-50 style=font-size:12px;margin-top:6px>{sub}</div>" if sub else ""}</div>')


def _tag_sat(nivel):
    t, c = SAT.get(nivel, ("—", "tag tag-apagado"))
    return f'<span class="{c}">{t}</span>'


# ------------------------------------------------------------------ JSON
@app.get("/api/entidad/{nit}")
def api_entidad(nit: str, tipo: str | None = "OBRA"):
    e = datos.entidad(nit, tipo if tipo in TIPOS else None)
    if not e:
        raise HTTPException(404, "entidad no encontrada en el universo de construcción")
    return e


@app.get("/api/competidor/{doc}")
def api_competidor(doc: str):
    c = datos.competidor(doc)
    if not c:
        raise HTTPException(404, "proveedor no encontrado")
    return c


@app.get("/api/proceso/{id_proceso}/competidores")
def api_competidores(id_proceso: str, n: int = Query(10, ge=1, le=30)):
    try:
        return {"proceso": datos.proceso(id_proceso), "competidores": datos.competidores_de(id_proceso, n)}
    except KeyError:
        raise HTTPException(404, "proceso no esta en el snapshot")


@app.get("/api/buscar")
def api_buscar(q: str):
    return datos.buscar(q)


# ------------------------------------------------------------------ HTML
JS_BUSCA = """<script>
(function(){var i=document.getElementById('q'),r=document.getElementById('res');if(!i)return;var t;
i.addEventListener('input',function(){clearTimeout(t);t=setTimeout(function(){var q=i.value.trim();if(q.length<3){r.innerHTML='';return;}
fetch('/api/buscar?q='+encodeURIComponent(q)).then(function(x){return x.json()}).then(function(d){r.innerHTML=
d.entidades.map(function(e){return '<a href="/entidad/'+encodeURIComponent(e.nit)+'"><span>'+e.entidad+'</span><small>entidad · '+(e.departamento||'')+'</small></a>'}).join('')+
d.competidores.map(function(c){return '<a href="/competidor/'+encodeURIComponent(c.doc)+'"><span>'+c.nombre+'</span><small>competidor</small></a>'}).join('')||'<span class="mute" style="font-size:13px">Nada con ese nombre.</span>';});},200);});})();
</script>"""


@app.get("/", response_class=HTMLResponse)
def inicio():
    ab = datos.abiertos()[:25]
    filas = "".join(
        f'<a class="row" style="grid-template-columns:minmax(0,1fr) 120px" href="/proceso/{W.h(a["id_del_proceso"])}"><div><b>{W.h(W.frase(a["descripcion"] or "Sin descripción")[:100])}</b>'
        f'<small>{W.h(W.titulo_caso(a["entidad"]))} · {W.h(W.titulo_caso(a["departamento"]))} · {MODALIDAD_CORTA.get(a["modalidad"], W.titulo_caso(a["modalidad"]))} · {W.mill(a["precio_base"])} · cierra en {a["dias_restantes"]} días</small></div>'
        f'<span class="mute" style="font-size:13px;text-align:right">¿contra quién? →</span></a>' for a in ab)
    cuerpo = f"""
<div class="cab"><div><div class="kicker">Radar · sepa contra quién compite antes de presentarse</div><h1 class="titulo">¿Quién gana ahí, y cómo?</h1></div></div>
<div><label class="busca"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.3-4.3"></path></svg><input id="q" placeholder="Buscar una entidad o un competidor (mínimo 3 letras)"></label><div class="res" id="res"></div></div>
<div class="card"><div class="card-head"><div class="card-title">Procesos abiertos</div><div class="card-label">{len(datos.abiertos())} accionables · {fuente.etiqueta_fecha()} · los 25 que cierran antes</div></div>
<div class="rows" style="margin-top:12px">{filas}</div></div>
<p class="foot-note">Fuente: contratos de construcción del SECOP II. "Probable" = ha ganado procesos parecidos; SECOP no publica quién se presentó y perdió.</p>
"""
    return W.pagina("Radar", cuerpo, _side("/"), EXTRA_CSS, JS_BUSCA)


@app.get("/entidades", response_class=HTMLResponse)
def entidades():
    filas = "".join(f'<a class="row" style="grid-template-columns:minmax(0,1fr) 100px" href="/entidad/{W.h(x["nit"])}"><div><b>{W.h(W.titulo_caso(x["entidad"]))}</b><small>{W.h(W.titulo_caso(x["departamento"]))}</small></div><span class="pct">{x["n"]}</span></a>'
                    for x in datos.entidades_mas_activas(40))
    cuerpo = f'<div class="cab"><div><div class="kicker">Entidades</div><h1 class="titulo">Las 40 que más contratan por proceso competitivo</h1></div></div><div class="rows">{filas}</div>'
    return W.pagina("Entidades", cuerpo, _side("/entidades"), EXTRA_CSS)


@app.get("/competidores", response_class=HTMLResponse)
def competidores():
    filas = "".join(f'<a class="row" style="grid-template-columns:minmax(0,1fr) 100px" href="/competidor/{W.h(x["doc"])}"><div><b>{W.h(W.titulo_caso(x["nombre"]))}</b><small>NIT {W.h(x["doc"])}</small></div><span class="pct">{x["n"]}</span></a>'
                    for x in datos.competidores_mas_activos(40))
    cuerpo = f'<div class="cab"><div><div class="kicker">Competidores</div><h1 class="titulo">Los 40 que más ganan procesos competitivos</h1></div></div><div class="rows">{filas}</div>'
    return W.pagina("Competidores", cuerpo, _side("/competidores"), EXTRA_CSS)


@app.get("/entidad/{nit}", response_class=HTMLResponse)
def entidad(nit: str, tipo: str = "OBRA"):
    tipo = tipo if tipo in TIPOS else "OBRA"
    e = datos.entidad(nit, tipo)
    if not e:
        raise HTTPException(404, "entidad no encontrada")
    et, cl = ETIQUETA[e["etiqueta"]]
    nombre = W.titulo_caso(e["entidad"])
    top_share = e["share_top1"]
    titular = {"abierta": f"{nombre} adjudica de forma <span class='hot'>abierta</span>: nadie pasa del {_pct(top_share)}.",
               "predecible": f"{nombre} adjudica de forma <span class='hot'>predecible</span>.",
               "intermedia": f"{nombre} adjudica de forma <span class='{cl}'>intermedia</span>.",
               "sin_muestra": f"{nombre}: <span class='mute'>sin muestra suficiente</span> en {TIPO_NOMBRE[tipo].lower()}."}[e["etiqueta"]]
    tabs = "".join(f'<a class="tab{" on" if t == tipo else ""}" href="/entidad/{W.h(nit)}?tipo={t}">{TIPO_NOMBRE[t]} · {n}</a>'
                   for t, n in [(t, dict(e["por_tipo"]).get(t, 0)) for t in TIPOS])
    gan = e["ganadores"][:8]
    mx = max((g["n"] for g in gan), default=1)
    filas = "".join(
        f'<div><div class="linea"><a href="/competidor/{W.h(g["doc"])}">{W.h(W.titulo_caso(g["nombre"] or g["doc"]))}{" · consorcio" if g["es_grupo"] else ""}</a>'
        f'<span class="num">{g["n"]} de {e["n_competitivos"]} · {_pct(g["share"], 1)}{f" · ofrece al {_pct(g["mediana_ratio"], 1)}" if g["mediana_ratio"] else ""} · último {g["ultimo_anio"]}</span></div>'
        f'<div class="bar bar-8{" bar-hot" if i == 0 else ""}"><span style="--w:{100 * g["n"] / mx:.0f}%"></span></div></div>'
        for i, g in enumerate(gan))
    anios = e["por_anio"]
    mxa = max(anios.values(), default=1)
    spark = "".join(f'<div><i style="height:{max(3, 60 * v / mxa):.0f}px"></i><span>{str(y)[2:]}</span></div>' for y, v in anios.items())
    consejos = []
    if e["etiqueta"] == "abierta":
        consejos.append(("Nadie tiene la entidad tomada: vale la pena presentarse.", True))
    if e["etiqueta"] == "predecible":
        consejos.append((e["razon"] + " Presentarse solo con una ventaja clara o en consorcio con quien gana.", False))
    if e["mediana_oferentes"] and e["mediana_oferentes"] >= 10:
        consejos.append((f"{int(e['mediana_oferentes'])} oferentes por proceso: el precio decide, prepare el sobre 2.", True))
    if e["mediana_ratio"]:
        consejos.append((f"Se adjudica al {_pct(e['mediana_ratio'], 1)}: {'poco' if e['mediana_ratio'] > 0.96 else 'algo de'} margen sobre el presupuesto.", e["mediana_ratio"] <= 0.96))
    why = "".join(f'<div class="{"" if ok else "minus"}"><span>{W.h(t)}</span><b>{"+" if ok else "−"}</b></div>' for t, ok in consejos)
    cuerpo = f"""
<div class="cab"><div><div class="kicker">Entidad · NIT {W.h(nit)} · {W.h(W.titulo_caso(e['departamento']))} · {TIPO_NOMBRE[tipo].lower()}s</div>
<h1 class="titulo" style="font-size:26px">{titular}</h1><p class="mute" style="font-size:14px;margin-top:6px">{W.h(e['razon'])}</p></div><div class="tabs">{tabs}</div></div>
<div class="stats-4">
  {_stat("Procesos competitivos", e['n_competitivos'], f"{e['n_proveedores']} proveedores distintos")}
  {_stat("Oferentes por proceso", int(e['mediana_oferentes']) if e['mediana_oferentes'] else "—", "mediana")}
  {_stat("Adjudica al", _pct(e['mediana_ratio'], 1), f"del presupuesto · margen mediano {_pct(e['margen_mediano'], 1)}", True)}
  {_stat("Proponente único", _pct(e['tasa_proponente_unico']), "de sus procesos")}
</div>
<div class="grid-7-5">
  <div class="card"><div class="card-head"><div class="card-title">Quién gana aquí</div><div class="card-label">{TIPO_NOMBRE[tipo].lower()}s competitivas · {min(anios) if anios else ''}–{max(anios) if anios else ''}</div></div>
    <div class="gana">{filas or '<span class="mute">Sin procesos competitivos de este tipo.</span>'}</div>
    <div class="mute-50" style="font-size:12px;margin-top:16px">"Ofrece al" es la mediana de sus ofertas ganadoras frente al presupuesto oficial. SECOP no publica las perdedoras: "gana" es lo único que se ve.</div></div>
  <div style="display:flex;flex-direction:column;gap:14px">
    <div class="card"><div class="card-title">Procesos por año</div><div class="anios">{spark}</div></div>
    <div class="card"><div class="card-title">Qué significa para usted</div><div class="why">{why or '<div><span class="mute">Sin señales.</span></div>'}</div></div>
  </div>
</div>
<p class="foot-note">"Predecible" = un proveedor gana ≥ 40 %, o HHI ≥ 0,25, o ≥ 60 % con proponente único. "Abierta" = nadie pasa del 20 % y hay ≥ 5 oferentes por proceso. Solo contratos de construcción del SECOP II.</p>
"""
    return W.pagina(f"{nombre}", cuerpo, _side("/entidades"), EXTRA_CSS)


@app.get("/competidor/{doc}", response_class=HTMLResponse)
def competidor(doc: str):
    c = datos.competidor(doc)
    if not c:
        raise HTTPException(404, "proveedor no encontrado")
    nombre = W.titulo_caso(c["nombre"] or doc)
    nivel = {"con_capacidad": "con capacidad", "cargado": "cargado", "saturado": "saturado"}[c["nivel_saturacion"]]
    titular = (f"{nombre} está <span class='hot'>{nivel}</span>: {W.mill(c['saldo_pendiente'])} por ejecutar." if c["n_en_ejecucion"] else
               f"{nombre} está <span class='hot'>con capacidad</span>: nada vigente en SECOP II.")
    ents = "".join(f'<div class="lin"><a href="/entidad/{W.h(x["nit"])}">{W.h(W.titulo_caso(x["entidad"]))}</a><b class="num">{x["n"]}</b></div>' for x in c["entidades"][:8])
    chips = "".join(f'<span class="chip">{W.h(W.titulo_caso(d))} · {n}</span>' for d, n in c["departamentos"][:5]) + \
        "".join(f'<span class="chip">UNSPSC {W.h(f)} · {n}</span>' for f, n in c["familias"][:4])
    ejec = "".join(
        f'<div class="row" style="grid-template-columns:minmax(0,1fr) auto"><div><b style="font-size:14px">{W.h(W.frase(x["objeto"] or "")[:80])}</b>'
        f'<small>{W.h(W.titulo_caso(x["entidad"]))} · termina {x["fecha_fin"][:10] or "sin fecha"}</small></div><b class="num" style="font-size:15px">{W.mill(x["saldo"])}</b></div>'
        for x in c["en_ejecucion"][:6]) or '<span class="mute" style="font-size:13px">Sin contratos vigentes en SECOP II.</span>'
    sat_w = min(100, 100 * c["saturacion"] / 3)
    cuerpo = f"""
<div><div class="kicker">Competidor · NIT {W.h(doc)} · {c['primer_anio']}–{c['ultimo_anio']}{' · consorcio' if c['es_grupo'] else ''}</div>
<h1 class="titulo" style="font-size:26px">{titular}</h1><p class="mute" style="font-size:14px;margin-top:6px">{W.h(c['razon_saturacion'])}</p></div>
<div class="stats-4">
  {_stat("Contratos ganados", c['n_contratos'], f"{c['n_obra']} obras · {c['n_interventoria']} interventorías")}
  {_stat("Ofrece al", _pct(c['mediana_ratio'], 1), "mediana de sus ofertas ganadoras", True)}
  {_stat("En ejecución", c['n_en_ejecucion'], f"saldo {W.mill(c['saldo_pendiente'])}")}
  {_stat("Ritmo anual", W.mill(c['valor_anual']), "valor adjudicado por año")}
</div>
<div class="grid-5-7">
  <div class="card"><div class="card-head"><div class="card-title">Dónde gana</div><div class="card-label">contratos competitivos por entidad</div></div>
    <div style="margin-top:6px">{ents or '<span class="mute">Solo contratación directa.</span>'}</div><div class="chips" style="margin-top:16px">{chips}</div></div>
  <div class="card"><div class="card-head"><div class="card-title">Saturación · lo que tiene entre manos</div><div class="card-label">saldo pendiente / ritmo anual = {str(round(c['saturacion'], 1)).replace('.', ',')} años</div></div>
    <div class="bar bar-8 bar-hot" style="margin-top:14px"><span style="--w:{sat_w:.0f}%"></span></div>
    <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--ad-ink-50);margin-top:6px"><span>con capacidad</span><span>1 año · cargado</span><span>2 años · saturado</span><span>3+</span></div>
    <div class="rows" style="margin-top:16px">{ejec}</div></div>
</div>
<p class="foot-note">Saturación = saldo por ejecutar de los contratos vigentes dividido por lo que adjudica al año. Un competidor saturado tiene menos capacidad residual para el siguiente proceso. Solo contratos publicados en SECOP II.</p>
"""
    return W.pagina(nombre, cuerpo, _side("/competidores"), EXTRA_CSS)


@app.get("/proceso/{id_proceso}", response_class=HTMLResponse)
def proceso(id_proceso: str):
    p = datos.proceso(id_proceso)
    if not p:
        raise HTTPException(404, "proceso no encontrado")
    comp = datos.competidores_de(id_proceso, 10)
    e = datos.entidad(p["nit_entidad"], p["tipo_contrato"] if p["tipo_contrato"] in TIPOS else "OBRA")
    raz = {"entidad": "ganó %d aquí", "departamento_familia": "%d en " + W.titulo_caso(p["departamento"]) + ", misma familia",
           "familia": "%d de esta familia en el país"}
    mxp = comp[0]["peso"] if comp else 1
    filas = "".join(
        f'<a class="rank{" on" if i == 0 else ""}" href="/competidor/{W.h(x["doc"])}"><span class="n">{i + 1}</span>'
        f'<div><b>{W.h(W.titulo_caso(x["nombre"] or x["doc"]))}</b><small>{" · ".join(raz[k] % v for k, v in x["razones"].items())} · {x["n_contratos"]} contratos</small></div>'
        f'<span class="num" style="font-size:13px;color:var(--ad-ink-70)">{f"ofrece al {_pct(x["mediana_ratio"], 1)}" if x["mediana_ratio"] else "sin razón conocida"}</span>'
        f'{_tag_sat(x["nivel_saturacion"])}<div><div class="peso{" hot" if i == 0 else ""}">{_pct(x["peso"])}</div>'
        f'<div class="bar" style="margin-top:4px"><span style="--w:{100 * x["peso"] / mxp:.0f}%"></span></div></div></a>'
        for i, x in enumerate(comp))
    dominante = comp and comp[0]["peso"] >= 0.4
    titular = (f"Contra quién compite: {len(comp)} proveedores probables, {'uno dominante' if dominante else 'ninguno dominante'}." if comp
               else "Sin historial parecido: nadie ha ganado obras así en esta entidad ni en esta familia.")
    ent_card = ""
    if e:
        et, cl = ETIQUETA[e["etiqueta"]]
        ent_card = (f'<div class="card"><div class="card-label">La entidad</div><div style="font-size:18px;font-weight:600;margin-top:6px">Adjudica de forma {et}</div>'
                    f'<div class="mute" style="font-size:13px;margin-top:6px">{e["n_proveedores"]} proveedores en {e["n_competitivos"]} procesos · {int(e["mediana_oferentes"]) if e["mediana_oferentes"] else "—"} oferentes por proceso · al {_pct(e["mediana_ratio"], 1)} del presupuesto.</div>'
                    f'<a href="/entidad/{W.h(p["nit_entidad"])}?tipo={p["tipo_contrato"]}" style="display:inline-block;margin-top:12px;font-size:13px;color:var(--ad-ink-85)">Ver perfil de la entidad →</a></div>')
    cuerpo = f"""
<nav class="migas"><a href="/">Radar</a><span>/</span><span>Procesos abiertos</span><span>/</span><span>{W.h(id_proceso)}</span></nav>
<div><div class="kicker">{W.h(id_proceso)} · {W.h(W.titulo_caso(p['entidad']))} · {MODALIDAD_CORTA.get(p['modalidad'], W.titulo_caso(p['modalidad']))} · {W.mill(p['precio_base'])} · cierra en {p['dias_restantes']} días</div>
<h1 class="titulo" style="font-size:26px;max-width:900px">{titular}</h1><p class="mute" style="font-size:14px;margin-top:6px">{W.h(W.frase(p['descripcion'] or '')[:140])}</p></div>
<div class="grid-8-4">
  <div class="card"><div class="card-head"><div class="card-title">Competidores probables</div><div class="card-label">peso relativo, no probabilidad calibrada</div></div>
    <div class="rows" style="margin-top:14px">{filas or '<span class="mute">Nada que mostrar.</span>'}</div></div>
  <div style="display:flex;flex-direction:column;gap:14px">{ent_card}
    <div class="card"><div class="card-label">Cómo se calcula</div><div style="display:flex;flex-direction:column;gap:10px;margin-top:10px;font-size:13px;color:var(--ad-ink-75)">
      <div>3 puntos por cada {TIPO_NOMBRE.get(p['tipo_contrato'], 'contrato').lower()} ganada en esta entidad</div><div>1 por cada una en {W.h(W.titulo_caso(p['departamento']))}, misma familia UNSPSC</div>
      <div>0,5 por cada una de la familia en el país (tope 6)</div><div>Lo de hace más de 3 años pesa la mitad</div><div>La saturación resta hasta un 50 %</div></div></div>
  </div>
</div>
<p class="foot-note">"Probable" = ha ganado procesos parecidos. SECOP no publica quién se presentó y perdió; esto es lo que se puede ver, y por eso el peso es un orden, no una probabilidad. <a href="{W.url_segura(p['urlproceso'])}" target="_blank" rel="noopener" style="color:var(--ad-ink-85)">Abrir en SECOP II →</a></p>
"""
    return W.pagina(f"Competidores · {id_proceso}", cuerpo, _side("/"), EXTRA_CSS)
