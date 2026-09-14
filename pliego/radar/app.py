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
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from markupsafe import Markup

from pliego.comun import fuente
from pliego.comun import web as W
from pliego.radar import datos

app = FastAPI(title="Pliego · Radar de competidores", version="0.1.0")
templates = W.plantillas(Path(__file__).parent / "templates")
ITEMS = [("/", "radar", "Radar"), ("/entidades", "entidad", "Entidades"), ("/competidores", "gente", "Competidores")]


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
app.mount("/static", W.Estaticos(W.STATIC), name="static")

TIPOS = ["OBRA", "INTERVENTORIA", "CONSULTORIA"]
TIPO_NOMBRE = {"OBRA": "Obra", "INTERVENTORIA": "Interventoría", "CONSULTORIA": "Consultoría"}
ETIQUETA = {"predecible": ("predecible", "hot"), "abierta": ("abierta", "hot"), "intermedia": ("intermedia", ""),
            "sin_muestra": ("sin muestra suficiente", "mute")}
SAT = {"con_capacidad": ("Con capacidad", "tag tag-apagado"), "cargado": ("Cargado", "tag tag-neutro"),
       "saturado": ("Saturado", "tag")}
MODALIDAD_CORTA = {"LICITACION PUBLICA OBRA PUBLICA": "Licitación pública", "SELECCION ABREVIADA DE MENOR CUANTIA": "Selección abreviada",
                   "CONCURSO DE MERITOS ABIERTO": "Concurso de méritos", "MINIMA CUANTIA": "Mínima cuantía",
                   "LICITACION PUBLICA": "Licitación pública", "CONTRATACION REGIMEN ESPECIAL (CON OFERTAS)": "Régimen especial"}

def _pagina(request: Request, plantilla: str, titulo: str, actual: str, **ctx):
    return W.render(templates, request, plantilla, titulo=titulo, items=ITEMS, actual=actual, ETIQUETA=ETIQUETA, SAT=SAT,
                    MODALIDAD_CORTA=MODALIDAD_CORTA, TIPO_NOMBRE=TIPO_NOMBRE, **ctx)


_pct = W.pct


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
@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    return _pagina(request, "radar/inicio.html", "Radar", "/", ab=datos.abiertos()[:25], n_abiertos=len(datos.abiertos()),
                   etiqueta_fecha=fuente.etiqueta_fecha())


@app.get("/entidades", response_class=HTMLResponse)
def entidades(request: Request):
    filas = [{"href": f"/entidad/{x['nit']}", "nombre": x["entidad"], "sub": W.titulo_caso(x["departamento"]), "n": x["n"]}
             for x in datos.entidades_mas_activas(40)]
    return _pagina(request, "radar/ranking.html", "Entidades", "/entidades", kicker="Entidades",
                   titulo_pagina="Las 40 que más contratan por proceso competitivo", filas=filas)


@app.get("/competidores", response_class=HTMLResponse)
def competidores(request: Request):
    filas = [{"href": f"/competidor/{x['doc']}", "nombre": x["nombre"], "sub": f"NIT {x['doc']}", "n": x["n"]}
             for x in datos.competidores_mas_activos(40)]
    return _pagina(request, "radar/ranking.html", "Competidores", "/competidores", kicker="Competidores",
                   titulo_pagina="Los 40 que más ganan procesos competitivos", filas=filas)


@app.get("/entidad/{nit}", response_class=HTMLResponse)
def entidad(request: Request, nit: str, tipo: str = "OBRA"):
    tipo = tipo if tipo in TIPOS else "OBRA"
    e = datos.entidad(nit, tipo)
    if not e:
        raise HTTPException(404, "entidad no encontrada")
    et, cl = ETIQUETA[e["etiqueta"]]
    nombre = W.titulo_caso(e["entidad"])
    h = W.h
    titular = Markup({
        "abierta": f"{h(nombre)} adjudica de forma <span class='hot'>abierta</span>: nadie pasa del {h(_pct(e['share_top1']))}.",
        "predecible": f"{h(nombre)} adjudica de forma <span class='hot'>predecible</span>.",
        "intermedia": f"{h(nombre)} adjudica de forma <span class='{cl}'>intermedia</span>.",
        "sin_muestra": f"{h(nombre)}: <span class='mute'>sin muestra suficiente</span> en {h(TIPO_NOMBRE[tipo].lower())}.",
    }[e["etiqueta"]])
    tabs = [(t, dict(e["por_tipo"]).get(t, 0)) for t in TIPOS]
    gan = e["ganadores"][:8]
    anios = e["por_anio"]
    consejos = []
    if e["etiqueta"] == "abierta":
        consejos.append(("Nadie tiene la entidad tomada: vale la pena presentarse.", True))
    if e["etiqueta"] == "predecible":
        consejos.append((e["razon"] + " Presentarse solo con una ventaja clara o en consorcio con quien gana.", False))
    if e["mediana_oferentes"] and e["mediana_oferentes"] >= 10:
        consejos.append((f"{int(e['mediana_oferentes'])} oferentes por proceso: el precio decide, prepare el sobre 2.", True))
    if e["mediana_ratio"]:
        consejos.append((f"Se adjudica al {_pct(e['mediana_ratio'], 1)}: {'poco' if e['mediana_ratio'] > 0.96 else 'algo de'} margen sobre el presupuesto.", e["mediana_ratio"] <= 0.96))
    return _pagina(request, "radar/entidad.html", nombre, "/entidades", e=e, nit=nit, tipo=tipo, nombre=nombre, titular=titular,
                   tabs=tabs, gan=gan, mx=max((g["n"] for g in gan), default=1), anios=anios, mxa=max(anios.values(), default=1),
                   anios_min=min(anios) if anios else "", anios_max=max(anios) if anios else "", consejos=consejos)


@app.get("/competidor/{doc}", response_class=HTMLResponse)
def competidor(request: Request, doc: str):
    c = datos.competidor(doc)
    if not c:
        raise HTTPException(404, "proveedor no encontrado")
    nombre = W.titulo_caso(c["nombre"] or doc)
    nivel = {"con_capacidad": "con capacidad", "cargado": "cargado", "saturado": "saturado"}[c["nivel_saturacion"]]
    return _pagina(request, "radar/competidor.html", nombre, "/competidores", c=c, doc=doc, nombre=nombre,
                   nivel=nivel if c["n_en_ejecucion"] else "con capacidad", sat_w=min(100, 100 * c["saturacion"] / 3))


@app.get("/proceso/{id_proceso}", response_class=HTMLResponse)
def proceso(request: Request, id_proceso: str):
    p = datos.proceso(id_proceso)
    if not p:
        raise HTTPException(404, "proceso no encontrado")
    comp = datos.competidores_de(id_proceso, 10)
    e = datos.entidad(p["nit_entidad"], p["tipo_contrato"] if p["tipo_contrato"] in TIPOS else "OBRA")
    raz = {"entidad": "ganó %d aquí", "departamento_familia": "%d en " + W.titulo_caso(p["departamento"]) + ", misma familia",
           "familia": "%d de esta familia en el país"}
    dominante = comp and comp[0]["peso"] >= 0.4
    titular = (f"Contra quién compite: {len(comp)} proveedores probables, {'uno dominante' if dominante else 'ninguno dominante'}." if comp
               else "Sin historial parecido: nadie ha ganado obras así en esta entidad ni en esta familia.")
    return _pagina(request, "radar/proceso.html", f"Competidores · {id_proceso}", "/", p=p, id_proceso=id_proceso, comp=comp, e=e,
                   raz=raz, titular=titular, mxp=comp[0]["peso"] if comp else 1)
