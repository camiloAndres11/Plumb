"""Servicio del filtro de procesos: paginas HTML + JSON.

    uvicorn pliego.filtro.app:app --port 8010 --reload

Dos pantallas (docs/diseno/): la lista ordenada por recomendacion y el
detalle con las razones. Los mismos datos salen en JSON bajo /api/ para
que otro front (o el equipo) los consuma sin raspar HTML.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from pliego.comun import web as W
from pliego.filtro import datos, logica
from pliego.filtro import reglas as R

app = FastAPI(title="Pliego · Filtro de procesos", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(W.STATIC)), name="static")

ETIQUETA = {logica.PRESENTARSE: ("Presentarse", "tag"),
            logica.REVISAR: ("Revisar", "tag tag-neutro"),
            logica.NO_PRESENTARSE: ("No presentarse", "tag tag-apagado")}
MODALIDAD_CORTA = {
    "LICITACION PUBLICA OBRA PUBLICA": "Licitación pública", "LICITACION PUBLICA": "Licitación pública",
    "SELECCION ABREVIADA DE MENOR CUANTIA": "Selección abreviada",
    "SELECCION ABREVIADA MENOR CUANTIA SIN MANIFESTACION INTERES": "Selección abreviada",
    "CONCURSO DE MERITOS ABIERTO": "Concurso de méritos", "MINIMA CUANTIA": "Mínima cuantía",
    "CONTRATACION REGIMEN ESPECIAL (CON OFERTAS)": "Régimen especial",
}


# ------------------------------------------------------------------ JSON
@app.get("/api/perfil")
def api_perfil():
    return datos.perfil()


@app.get("/api/resumen")
def api_resumen():
    return datos.resumen()


@app.get("/api/procesos")
def api_procesos(recomendacion: str | None = Query(None), departamento: str | None = None,
                 limite: int = Query(50, ge=1, le=600)):
    evs = datos.evaluaciones()
    if recomendacion:
        if recomendacion not in ETIQUETA:
            raise HTTPException(400, "recomendacion debe ser presentarse | revisar | no_presentarse")
        evs = [x for x in evs if x["evaluacion"]["recomendacion"] == recomendacion]
    if departamento:
        evs = [x for x in evs if x["departamento"] == departamento.upper()]
    return {"total": len(evs), "datos": evs[:limite],
            "aviso": "Estimacion sobre datos publicos del SECOP II; cada razon trae su evidencia."}


@app.get("/api/procesos/{id_proceso}")
def api_proceso(id_proceso: str):
    x = datos.por_id(id_proceso)
    if not x:
        raise HTTPException(404, "proceso no esta en el snapshot accionable")
    return x


# ------------------------------------------------------------------ HTML
def _side(actual: str) -> str:
    p = datos.perfil()
    pie = (f'<div class="side-foot"><div class="kicker">Perfil activo</div><b>{W.h(p["nombre"])}</b>'
           f'<small>{W.h(" · ".join(W.titulo_caso(d) for d in p["departamentos_interes"]))}</small>'
           f'<div class="chips" style="margin-top:10px">'
           + "".join(f'<span class="chip" style="font-size:11px;padding:4px 9px">{W.h(c)}</span>'
                     for c in ("Vías", "Edificaciones", "Acueductos")) + '</div></div>')
    return W.sidebar([("/", "filtro", "Filtro de procesos"), ("/perfil", "perfil", "Mi perfil")], actual, pie)


def _resumen_corto(x: dict) -> str:
    """La razon mas fuerte, para la columna del medio de la lista."""
    ev = x["evaluacion"]
    fallas = [r for r in ev["razones"] if r["habilitante"] and r["cumple"] is False]
    if fallas:
        r = fallas[0]
        if r["codigo"] == "experiencia":
            return "Le faltan %s SMMLV de experiencia" % W.entero(r["evidencia"]["requerida_smmlv"] - r["evidencia"]["acreditada_smmlv"])
        if r["codigo"] == "objeto":
            return "No es su tipo de obra (familia %s)" % r["evidencia"]["familia"]
        if r["codigo"] == "capacidad_residual":
            return "Capacidad residual insuficiente"
        return r["codigo"].replace("_", " ").capitalize()
    sen = sorted([r for r in ev["razones"] if not r["habilitante"] and r["cumple"] is not None],
                 key=lambda r: -abs(r["peso"]))
    cortas = {"ganador_recurrente": "Siempre gana el mismo", "entidad_cerrada": "Entidad con proponente único",
              "entidad_competitiva": "Entidad con competencia real", "fuera_de_region": "Fuera de región",
              "departamento_interes": "En su región", "plazo_corto": "Cierra en %s días" % x.get("dias_restantes"),
              "mucha_competencia": "Mucha competencia", "codigo_raro": "Código UNSPSC raro",
              "experiencia_holgada": "Experiencia de sobra", "cuantia_fuera_rango": "Fuera de su rango de cuantía",
              "cuantia_objetivo": "Cuantía objetivo", "ventana_corta": "Plazo de ofertas corto",
              "capacidad_holgada": "Capacidad de sobra"}
    return " · ".join(cortas.get(r["codigo"], r["codigo"]) for r in sen[:2]) or "Sin señales"


def _fila(x: dict) -> str:
    ev = x["evaluacion"]
    texto, clase = ETIQUETA[ev["recomendacion"]]
    off = ev["recomendacion"] == logica.NO_PRESENTARSE
    hot = ev["recomendacion"] == logica.PRESENTARSE
    return (f'<a class="row{" off" if off else ""}" style="grid-template-columns:minmax(0,1fr) 190px 130px 70px" '
            f'href="/proceso/{W.h(x["id_del_proceso"])}">'
            f'<div><b>{W.h(W.frase(x["descripcion"] or "Sin descripción")[:110])}</b>'
            f'<small>{W.h(W.titulo_caso(x["entidad"]))} · {W.h(W.titulo_caso(x["departamento"]))} · '
            f'{W.h(MODALIDAD_CORTA.get(x["modalidad"], W.titulo_caso(x["modalidad"])))} · {W.mill(x["precio_base"])} · '
            f'cierra en {x["dias_restantes"]} días</small></div>'
            f'<div style="font-size:13px;color:var(--ad-ink-70)">{W.h(_resumen_corto(x))}</div>'
            f'<span class="{clase}" style="justify-self:start">{texto}</span>'
            f'<div class="pct{" hot" if hot else (" mute-50" if off else "")}">{ev["puntaje"]}</div></a>')


@app.get("/", response_class=HTMLResponse)
def lista(recomendacion: str | None = None):
    res = datos.resumen()
    evs = datos.evaluaciones()
    if recomendacion in ETIQUETA:
        evs = [x for x in evs if x["evaluacion"]["recomendacion"] == recomendacion]
    c = res["conteo"]
    tot = res["total"]

    def stat(label, n, clase_num, clase_bar):
        return (f'<div class="stat"><div class="card-label">{label}</div>'
                f'<div class="big num {clase_num}">{n}</div>'
                f'<div class="bar {clase_bar}"><span style="--w:{100 * n / tot:.0f}%"></span></div></div>')

    def tab(key, label, n):
        on = " on" if recomendacion == key or (key is None and recomendacion not in ETIQUETA) else ""
        href = "/" if key is None else f"/?recomendacion={key}"
        return f'<a class="tab{on}" href="{href}">{label} · {n}</a>'

    cuerpo = f"""
<div class="cab">
  <div><div class="kicker">Procesos abiertos · snapshot {res['fecha_snapshot']} (se toma como hoy)</div>
  <h1 class="titulo">{tot} procesos abiertos, {c['presentarse']} valen su tiempo.</h1></div>
  <span class="badge"><span class="dot"></span>Se ahorra {W.entero(res['horas_ahorradas'])} horas de propuestas que no ganaría</span>
</div>
<div class="stats">
  {stat("Presentarse", c['presentarse'], "hot", "bar-hot")}
  {stat("Revisar", c['revisar'], "", "")}
  {stat("No presentarse", c['no_presentarse'], "mute", "bar-mute")}
</div>
<div class="tabs">{tab(None, "Todos", tot)}{tab("presentarse", "Presentarse", c['presentarse'])}{tab("revisar", "Revisar", c['revisar'])}{tab("no_presentarse", "No presentarse", c['no_presentarse'])}</div>
<div class="rows">{"".join(_fila(x) for x in evs)}</div>
<p class="foot-note">Fuente: procesos abiertos en SECOP II (universo accionable del snapshot) y adjudicaciones históricas de cada entidad.
La recomendación es una estimación: cada razón trae la cifra que la sustenta. Perfil evaluado: {W.h(res['perfil'])} (ficticio).</p>
"""
    return W.pagina("Filtro de procesos", cuerpo, _side("/"))


def _check(r: dict) -> str:
    if r["cumple"] is True:
        icono = f'<span class="check-on">{W.ICONOS["check"]}</span>'
    elif r["cumple"] is False:
        icono = '<span class="check-off"></span>'
    else:
        icono = '<span class="check-dudo"></span>'
    ev = r["evidencia"]
    extra = ""
    if r["codigo"] == "capacidad_residual" and ev.get("precio_base"):
        extra = f'{W.mill(ev["capacidad_residual"])} / {W.mill(ev["precio_base"])}'
    elif r["codigo"] == "experiencia":
        extra = (f'requerido = {int(100 * R.EXPERIENCIA_FRACCION_MIN)} % del presupuesto en SMMLV '
                 f'({W.entero(ev["requerida_smmlv"])}) · familia {ev["familia"]}')
    elif r["codigo"] == "financiero" and r["cumple"]:
        extra = " · ".join(f'{k.replace("_", " ")} {str(v).replace(".", ",")}' for k, v in ev.items())
    elif r["codigo"] == "objeto" and r["cumple"] is not None:
        extra = "familias del perfil: " + ", ".join(ev["familias_perfil"])
    return (f'<div>{icono}<div><div class="{"falla" if r["cumple"] is False else ""}">{W.h(r["texto"])}</div>'
            f'{f"<div class=ev>{W.h(extra)}</div>" if extra else ""}</div></div>')


def _senal(r: dict) -> str:
    clase = "" if r["cumple"] else ("neutro" if r["cumple"] is None else "minus")
    peso = "±0" if r["cumple"] is None else (f"+{r['peso']}" if r["peso"] > 0 else f"−{abs(r['peso'])}")
    return f'<div class="{clase}"><span>{W.h(r["texto"])}</span><b>{peso}</b></div>'


@app.get("/proceso/{id_proceso}", response_class=HTMLResponse)
def detalle(id_proceso: str):
    x = datos.por_id(id_proceso)
    if not x:
        raise HTTPException(404, "proceso no encontrado")
    ev = x["evaluacion"]
    texto, _ = ETIQUETA[ev["recomendacion"]]
    hab = [r for r in ev["razones"] if r["habilitante"]]
    # a favor primero, luego en contra, luego las que no mueven el puntaje
    sen = sorted([r for r in ev["razones"] if not r["habilitante"]],
                 key=lambda r: (0 if r["cumple"] else (2 if r["cumple"] is None else 1), -abs(r["peso"])))
    n_ok = sum(1 for r in hab if r["cumple"])
    fallas = [r for r in hab if r["cumple"] is False]
    hot = ev["recomendacion"] == logica.PRESENTARSE

    sub = ("todos los habilitantes se cumplen" if not fallas else
           ("un habilitante no se cumple" if len(fallas) == 1 else f"{len(fallas)} habilitantes no se cumplen"))
    if any(r["cumple"] is None for r in hab):
        sub = "falta un dato para decidir"

    # "Si igual quiere ir": la falla habilitante mas facil de nombrar
    consejo = "Presente la oferta con tiempo: cierra en %s días." % x["dias_restantes"]
    for r in fallas:
        if r["codigo"] == "experiencia":
            consejo = "Consiga un socio con %s SMMLV en la familia %s" % (
                W.entero(r["evidencia"]["requerida_smmlv"] - r["evidencia"]["acreditada_smmlv"]), r["evidencia"]["familia"])
        elif r["codigo"] == "capacidad_residual":
            consejo = "Necesita %s más de capacidad residual (o un consorcio)" % W.mill(
                r["evidencia"]["precio_base"] - r["evidencia"]["capacidad_residual"])
        elif r["codigo"] == "objeto":
            consejo = "No es su tipo de obra; solo en consorcio con alguien de la familia %s" % r["evidencia"]["familia"]
        break
    if not fallas and ev["recomendacion"] == logica.NO_PRESENTARSE:
        consejo = "Es elegible; lo que pesa son las señales de la entidad y la región."

    horas_card = (f'<div class="mini"><small>Se ahorra</small><b class="hot num">{ev["horas_ahorradas"]} h</b>'
                  f'<small>de preparar una propuesta ({MODALIDAD_CORTA.get(x["modalidad"], "modalidad").lower()})</small></div>'
                  if ev["horas_ahorradas"] else
                  f'<div class="mini"><small>Preparar la propuesta</small><b class="num">{logica.horas_de(x["modalidad"])} h</b>'
                  f'<small>estimadas para {MODALIDAD_CORTA.get(x["modalidad"], "esta modalidad").lower()}</small></div>')

    chips = "".join(f'<span class="chip">{W.h(t)}</span>' for t in (
        MODALIDAD_CORTA.get(x["modalidad"], W.titulo_caso(x["modalidad"])), W.titulo_caso(x["departamento"]),
        W.mill(x["precio_base"]), f'Cierra {x["fecha_cierre"]} · {x["dias_restantes"]} días',
        f'UNSPSC {x["unspsc"]}'))

    cuerpo = f"""
<nav class="migas"><a href="/">Filtro de procesos</a><span>/</span><span>{W.h(x['id_del_proceso'])}</span></nav>
<div class="grid-5-7">
  <div class="card" style="display:flex;flex-direction:column;justify-content:space-between;gap:24px;padding:28px">
    <div>
      <div class="card-label">{W.h(W.titulo_caso(x['entidad']))}</div>
      <div style="font-size:20px;font-weight:600;letter-spacing:-.02em;margin-top:8px;line-height:1.25">{W.h(W.frase(x['descripcion'] or 'Sin descripción'))}</div>
      <div class="chips" style="margin-top:14px">{chips}</div>
    </div>
    <div>
      <div class="kicker">Recomendación</div>
      <div style="font-size:56px;line-height:1;font-weight:600;letter-spacing:-.04em;margin-top:8px" class="{'hot' if hot else ('mute' if ev['recomendacion'] == logica.NO_PRESENTARSE else '')}">{texto}</div>
      <div style="display:flex;align-items:baseline;gap:10px;margin-top:14px"><span class="num" style="font-size:28px;font-weight:600;letter-spacing:-.03em">{ev['puntaje']}</span><span style="font-size:14px;color:var(--ad-ink-60)">de 100 · {sub}</span></div>
      <div class="bar bar-6 {'bar-hot' if hot else ''}" style="margin-top:12px"><span style="--w:{ev['puntaje']}%"></span></div>
    </div>
    <div class="grid-2">
      {horas_card}
      <div class="mini"><small>{'Si igual quiere ir' if ev['recomendacion'] != logica.PRESENTARSE else 'Siguiente paso'}</small><b class="txt">{W.h(consejo)}</b></div>
    </div>
  </div>
  <div style="display:flex;flex-direction:column;gap:14px">
    <div class="card">
      <div class="card-head"><div class="card-title">Habilitantes</div><div class="card-label">{n_ok} de {len(hab)} · según documentos tipo</div></div>
      <div class="check">{"".join(_check(r) for r in hab)}</div>
    </div>
    <div class="card">
      <div class="card-head"><div class="card-title">Señales</div><div class="card-label">parten de 50 · suman o restan</div></div>
      <div class="why">{"".join(_senal(r) for r in sen) or '<div><span class="mute">Sin señales sobre esta entidad.</span></div>'}</div>
    </div>
  </div>
</div>
<p class="foot-note">Los umbrales habilitantes son los usuales de los documentos tipo de obra pública; el pliego real puede fijar otros.
<a href="{W.h(x['urlproceso'] or '#')}" target="_blank" rel="noopener" style="color:var(--ad-ink-85)">Abrir el proceso en SECOP II →</a></p>
"""
    return W.pagina(f"{texto} · {x['id_del_proceso']}", cuerpo, _side("/"))


@app.get("/perfil", response_class=HTMLResponse)
def perfil():
    p = datos.perfil()
    f, o = p["financiero"], p["organizacional"]
    exp = "".join(
        f'<tr><td>{W.h(e["objeto"])}</td><td>{W.h(W.titulo_caso(e["entidad"]))}</td><td>{e["unspsc"]}</td>'
        f'<td class="num">{W.entero(e["valor_smmlv"])}</td><td class="num">{e["anio"]}</td></tr>' for e in p["experiencia"])
    cuerpo = f"""
<div class="cab"><div><div class="kicker">Mi perfil · ficticio, para el prototipo</div><h1 class="titulo">{W.h(p['nombre'])}</h1></div>
<span class="badge"><span class="dot dot-mute"></span>RUP {'vigente' if p['rup']['vigente'] else 'vencido'} · renovado {p['rup']['renovado']}</span></div>
<div class="grid-5-7">
  <div class="card">
    <div class="card-title">Capacidad</div>
    <div class="grid-2" style="margin-top:16px">
      <div class="mini"><small>Capacidad residual</small><b class="num">{W.mill(p['capacidad_residual'])}</b></div>
      <div class="mini"><small>Cuantía objetivo</small><b class="num" style="font-size:18px">{W.mill(p['cuantia_objetivo']['min'])} – {W.mill(p['cuantia_objetivo']['max'])}</b></div>
      <div class="mini"><small>Liquidez</small><b class="num">{str(f['liquidez']).replace('.', ',')}</b></div>
      <div class="mini"><small>Endeudamiento</small><b class="num">{W.pct(f['endeudamiento'])}</b></div>
      <div class="mini"><small>Cobertura de intereses</small><b class="num">{str(f['cobertura_intereses']).replace('.', ',')}</b></div>
      <div class="mini"><small>Rentabilidad del patrimonio</small><b class="num">{W.pct(o['rentabilidad_patrimonio'])}</b></div>
    </div>
    <div class="card-label" style="margin-top:18px">Regiones y familias UNSPSC</div>
    <div class="chips" style="margin-top:8px">{"".join(f'<span class="chip">{W.h(W.titulo_caso(d))}</span>' for d in p['departamentos_interes'])}{"".join(f'<span class="chip">{u}</span>' for u in p['unspsc'])}</div>
  </div>
  <div class="card">
    <div class="card-head"><div class="card-title">Experiencia acreditada</div><div class="card-label">{len(p['experiencia'])} contratos · {W.entero(sum(e['valor_smmlv'] for e in p['experiencia']))} SMMLV</div></div>
    <table class="tabla" style="margin-top:16px"><thead><tr><th>Objeto</th><th>Entidad</th><th>UNSPSC</th><th class="num">SMMLV</th><th class="num">Año</th></tr></thead><tbody>{exp}</tbody></table>
  </div>
</div>
<p class="foot-note">El perfil vive en pliego/filtro/fixtures/perfil_constructora.json. En producción saldría del RUP y de los estados financieros del cliente.</p>
"""
    return W.pagina("Mi perfil", cuerpo, _side("/perfil"))
