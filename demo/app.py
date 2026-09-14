"""Un solo servicio para presentar los cinco enfoques al equipo.

    uvicorn demo.app:app --port 8000

  /            la landing comercial de Pliego (plataforma/static/landing.html), con
               «Entrar» apuntando a /login
  /login       inicio de sesion SOLO DE VISTA: «Iniciar» lleva al panel
  /panel       una tarjeta por enfoque
  /filtro, /checklist, /simulador, /radar, /generador
               las cinco apps de pliego/, montadas tal cual bajo un prefijo

Las apps arman sus URLs con el root_path de la peticion, asi que montarlas
bajo un prefijo no exige reescribir nada. Un middleware deja en
request.state.hub el enlace «Panel» para que la sidebar de cada app lo
muestre (ver pliego/comun/templates/base.html).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse

from pliego.checklist.app import app as checklist_app
from pliego.comun import fuente
from pliego.comun import panel as P
from pliego.comun import web as W
from pliego.filtro import datos as filtro_datos
from pliego.filtro.app import app as filtro_app
from pliego.generador.app import app as generador_app
from pliego.radar.app import app as radar_app
from pliego.simulador.app import app as simulador_app

RAIZ = Path(__file__).resolve().parents[1]
ESTATICOS = RAIZ / "plataforma" / "static"
LANDING = ESTATICOS / "landing.html"
templates = W.plantillas(Path(__file__).parent / "templates", RAIZ / "plataforma" / "templates")

app = FastAPI(title="Pliego · demo para el equipo", version="0.1.0", docs_url=None, redoc_url=None)
app.mount("/static", W.Estaticos(ESTATICOS, W.STATIC), name="static")


@app.middleware("http")
async def _hub(request: Request, call_next):
    request.state.hub = {"volver": ("/panel", "Panel")}
    return await call_next(request)


for ruta, sub in [("/filtro", filtro_app), ("/checklist", checklist_app), ("/simulador", simulador_app),
                  ("/radar", radar_app), ("/generador", generador_app)]:
    app.mount(ruta, sub)


# ------------------------------------------------------------------ vistas
@app.get("/", response_class=HTMLResponse)
def landing():
    html = LANDING.read_text(encoding="utf-8")
    # «Entrar» lleva al login; el resto de la landing queda igual.
    return html.replace('href="/tablero/">Entrar', 'href="/login">Entrar')


@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    request.state.hub = None
    return W.render(templates, request, "login.html", titulo="Ingresar",
                    pie="Demo para el equipo · el inicio de sesión no tiene lógica todavía: «Iniciar» abre el panel.")


@app.get("/panel", response_class=HTMLResponse)
def panel(request: Request):
    request.state.hub = None
    # De donde salen los datos: el snapshot commiteado o Croma (ver
    # pliego/comun/fuente.py). El panel lo dice para que nadie confunda uno
    # con otro en una demo.
    est = fuente.estado()
    croma = est["fuente"] == "croma"
    if croma:
        kicker = f"Hoy · {P.fecha_larga(fuente.hoy())} · datos de Croma al {str(est.get('as_of'))[:10]}"
        detalle = f"{est['llamadas']} consultas, {est.get('creditos_restantes')} créditos restantes" if est.get("llamadas") else "desde la caché local del día"
        origen = f"Datos públicos del SECOP II vía Croma (as_of {str(est.get('as_of'))[:10]}, {detalle})."
    else:
        kicker = f"Hoy · {P.fecha_larga(fuente.hoy())} · 6:00 a. m. (snapshot)"
        origen = f"Datos públicos del SECOP II (snapshot {fuente.hoy().isoformat()})."
    items = [(f"/{r}/", ic, n) for r, n, _, ic in P.ENFOQUES]
    return W.render(templates, request, "panel.html", titulo="Panel", items=items, actual="/panel", kicker=kicker, origen=origen,
                    croma=croma, n_abiertos=len(filtro_datos.procesos()), tarjetas=P.tarjetas("/"))


@app.get("/favicon.ico")
def favicon():
    return FileResponse(ESTATICOS / "favicon.png")
