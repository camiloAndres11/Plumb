"""Servicio del filtro de procesos: paginas HTML + JSON.

    uvicorn pliego.filtro.app:app --port 8010 --reload

Dos pantallas (docs/diseno/): la lista ordenada por recomendacion y el
detalle con las razones. Los mismos datos salen en JSON bajo /api/ para
que otro front (o el equipo) los consuma sin raspar HTML.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from pliego.comun import fuente
from pliego.comun import web as W
from pliego.filtro import datos, logica
from pliego.filtro import reglas as R

app = FastAPI(title="Pliego · Filtro de procesos", version="0.1.0")
app.mount("/static", W.Estaticos(W.STATIC), name="static")
templates = W.plantillas(Path(__file__).parent / "templates")
ITEMS = [("/", "filtro", "Filtro de procesos"), ("/perfil", "perfil", "Mi perfil")]

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
def _pagina(request: Request, plantilla: str, titulo: str, actual: str, **ctx):
    return W.render(templates, request, plantilla, titulo=titulo, items=ITEMS, actual=actual, perfil=datos.perfil(),
                    ETIQUETA=ETIQUETA, MODALIDAD_CORTA=MODALIDAD_CORTA, PRESENTARSE=logica.PRESENTARSE,
                    NO_PRESENTARSE=logica.NO_PRESENTARSE, **ctx)


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


@app.get("/", response_class=HTMLResponse)
def lista(request: Request, recomendacion: str | None = None):
    res = datos.resumen()
    evs = datos.evaluaciones()
    if recomendacion in ETIQUETA:
        evs = [x for x in evs if x["evaluacion"]["recomendacion"] == recomendacion]
    c = res["conteo"]
    tot = res["total"]
    stats = [("Presentarse", c["presentarse"], "hot", "bar-hot"), ("Revisar", c["revisar"], "", ""),
             ("No presentarse", c["no_presentarse"], "mute", "bar-mute")]
    tabs = [(None, "Todos", tot), ("presentarse", "Presentarse", c["presentarse"]), ("revisar", "Revisar", c["revisar"]),
            ("no_presentarse", "No presentarse", c["no_presentarse"])]
    return _pagina(request, "filtro/lista.html", "Filtro de procesos", "/", res=res, evs=evs, c=c, tot=tot, stats=stats, tabs=tabs,
                   recomendacion=recomendacion, resumen_corto=_resumen_corto, etiqueta_fecha=fuente.etiqueta_fecha())


def _extra_check(r: dict) -> str:
    """La cifra que sustenta un habilitante, para la fila del detalle."""
    ev = r["evidencia"]
    if r["codigo"] == "capacidad_residual" and ev.get("precio_base"):
        return f'{W.mill(ev["capacidad_residual"])} / {W.mill(ev["precio_base"])}'
    if r["codigo"] == "experiencia":
        return (f'requerido = {int(100 * R.EXPERIENCIA_FRACCION_MIN)} % del presupuesto en SMMLV '
                f'({W.entero(ev["requerida_smmlv"])}) · familia {ev["familia"]}')
    if r["codigo"] == "financiero" and r["cumple"]:
        return " · ".join(f'{k.replace("_", " ")} {str(v).replace(".", ",")}' for k, v in ev.items())
    if r["codigo"] == "objeto" and r["cumple"] is not None:
        return "familias del perfil: " + ", ".join(ev["familias_perfil"])
    return ""


@app.get("/proceso/{id_proceso}", response_class=HTMLResponse)
def detalle(request: Request, id_proceso: str):
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

    chips = [MODALIDAD_CORTA.get(x["modalidad"], W.titulo_caso(x["modalidad"])), W.titulo_caso(x["departamento"]),
             W.mill(x["precio_base"]), f'Cierra {x["fecha_cierre"]} · {x["dias_restantes"]} días', f'UNSPSC {x["unspsc"]}']
    return _pagina(request, "filtro/detalle.html", f"{texto} · {x['id_del_proceso']}", "/", x=x, ev=ev, texto=texto, hot=hot, sub=sub,
                   consejo=consejo, chips=chips, hab=[(r, _extra_check(r)) for r in hab], n_ok=n_ok, sen=sen,
                   horas=logica.horas_de(x["modalidad"]))


@app.get("/perfil", response_class=HTMLResponse)
def perfil(request: Request):
    p = datos.perfil()
    return _pagina(request, "filtro/perfil.html", "Mi perfil", "/perfil", p=p, f=p["financiero"], o=p["organizacional"],
                   total_smmlv=sum(e["valor_smmlv"] for e in p["experiencia"]))
