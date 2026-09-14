"""Un solo servicio para presentar los cinco enfoques al equipo.

    uvicorn demo.app:app --port 8000

  /            la landing comercial de Pliego (plataforma/static/landing.html), con
               «Entrar» apuntando a /login
  /login       inicio de sesion SOLO DE VISTA: «Iniciar» lleva al panel
  /panel       una tarjeta por enfoque
  /filtro, /checklist, /simulador, /radar, /generador
               las cinco apps de pliego/, montadas tal cual bajo un prefijo

Las apps de cada enfoque enlazan con rutas absolutas (/proceso/..., /static/...)
porque nacieron para correr solas en su puerto. En vez de tocar las cinco,
`ConPrefijo` reescribe las URLs de raiz en el HTML que devuelven para que
apunten bajo su prefijo. Es un truco de demo, no de produccion, y esta
acotado a este archivo.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from pliego.checklist.app import app as checklist_app
from pliego.comun import fuente
from pliego.comun import panel as P
from pliego.comun import web as W
from pliego.comun.prefijo import ConPrefijo, sidebar_con_hub
from pliego.filtro import datos as filtro_datos
from pliego.filtro.app import app as filtro_app
from pliego.generador.app import app as generador_app
from pliego.radar.app import app as radar_app
from pliego.simulador.app import app as simulador_app

RAIZ = Path(__file__).resolve().parents[1]
ESTATICOS = RAIZ / "plataforma" / "static"
LANDING = ESTATICOS / "landing.html"

ENFOQUES = P.ENFOQUES

_SIDEBAR_ORIGINAL = W.sidebar
sidebar_con_hub("/panel")   # cada app montada gana el enlace «Panel» en su sidebar

app = FastAPI(title="Pliego · demo para el equipo", version="0.1.0", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(ESTATICOS)), name="static")
for ruta, sub in [("/filtro", filtro_app), ("/checklist", checklist_app), ("/simulador", simulador_app),
                  ("/radar", radar_app), ("/generador", generador_app)]:
    app.mount(ruta, ConPrefijo(sub, ruta))


# ------------------------------------------------------------------ vistas
@app.get("/", response_class=HTMLResponse)
def landing():
    html = LANDING.read_text(encoding="utf-8")
    # «Entrar» lleva al login; el resto de la landing queda igual.
    return html.replace('href="/tablero/">Entrar', 'href="/login">Entrar')


LOGIN_CSS = """
.lg { position: relative; min-height: 100vh; overflow: hidden; display: grid; grid-template-rows: auto 1fr auto; }
.lg-nav { position: relative; z-index: 2; display: flex; align-items: center; justify-content: space-between; max-width: var(--ad-max); width: 100%; margin: 0 auto; padding: 22px var(--ad-gutter); }
.lg-nav a:last-child { font-size: 15px; color: var(--ad-ink-80); }
.lg-centro { position: relative; z-index: 2; display: grid; place-items: center; padding: 24px var(--ad-gutter); }
.lg-card { width: min(440px, 100%); padding: 36px; border-radius: 22px; background: var(--ad-glass); border: 1px solid var(--ad-line); box-shadow: var(--ad-shadow); display: flex; flex-direction: column; gap: 22px; animation: adRise .9s var(--ad-ease) both; }
.lg-card h1 { font-size: 32px; line-height: 1.1; letter-spacing: -.03em; font-weight: 500; margin-top: 18px; }
.lg-card .sub { font-size: 15px; color: var(--ad-ink-60); margin-top: 8px; }
.lg-campos { display: flex; flex-direction: column; gap: 14px; }
.lg-campo { display: flex; flex-direction: column; gap: 8px; font-size: 13px; color: var(--ad-ink-60); }
.lg-campo input { padding: 14px 16px; border-radius: 12px; background: var(--ad-fill-3); border: 1px solid var(--ad-line); font: inherit; font-size: 15px; color: var(--ad-ink); outline: 0; }
.lg-campo input:focus { border-color: var(--ad-line-3); }
.lg-links { display: flex; justify-content: space-between; font-size: 13px; }
.lg-links a { color: var(--ad-ink-70); }
.lg-pie { position: relative; z-index: 2; text-align: center; font-size: 12px; color: var(--ad-ink-35); padding: 24px; }
"""


def _campo(label, valor="", tipo="text", placeholder=""):
    return (f'<label class="lg-campo">{label}<input type="{tipo}" value="{W.h(valor)}" placeholder="{W.h(placeholder)}" '
            f'autocomplete="off"></label>')


@app.get("/login", response_class=HTMLResponse)
def login():
    return f"""<!doctype html>
<html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ingresar — Pliego</title><meta name="theme-color" content="#0b0b0d">
<link rel="icon" type="image/png" href="/static/favicon-32.png" sizes="32x32">
<link rel="stylesheet" href="/static/landing.css">
<style>{LOGIN_CSS}</style>
<body>
<div class="lg">
  <div class="ad-hero-bg" aria-hidden="true"></div><div class="ad-glow-a" aria-hidden="true"></div><div class="ad-glow-b" aria-hidden="true"></div>
  <header class="lg-nav"><a class="ad-logo" href="/"><span class="ad-logo-mark" aria-hidden="true"><span></span><span></span><span></span></span>Pliego.</a><a href="/">← Volver a la landing</a></header>
  <main class="lg-centro">
    <form class="lg-card" action="/panel" method="get">
      <div><span class="ad-badge"><span class="ad-dot"></span>Para constructoras que licitan obra pública</span>
        <h1>Ingrese a Pliego.</h1><p class="sub">Sus licitaciones de hoy, listas a las 6:00.</p></div>
      <div class="lg-campos">{_campo("Correo", "licitaciones@constructoraandina.co", "email")}{_campo("Contraseña", "", "password", "••••••••••")}</div>
      <button class="ad-btn ad-btn-shadow" type="submit">Iniciar</button>
      <div class="lg-links"><a href="#">¿Olvidó su contraseña?</a><a href="/#precios">Probar 14 días gratis</a></div>
    </form>
  </main>
  <p class="lg-pie">Demo para el equipo · el inicio de sesión no tiene lógica todavía: «Iniciar» abre el panel.</p>
</div>
"""


@app.get("/panel", response_class=HTMLResponse)
def panel():
    tarjetas = P.tarjetas("/")
    items = [(f"/{r}/", ic, n) for r, n, _, ic in ENFOQUES]
    # De donde salen los datos: el snapshot commiteado o Croma (ver
    # pliego/comun/fuente.py). El panel lo dice para que nadie confunda uno
    # con otro en una demo.
    est = fuente.estado()
    n_abiertos = len(filtro_datos.procesos())
    if est["fuente"] == "croma":
        kicker = f"Hoy · {P.fecha_larga(fuente.hoy())} · datos de Croma al {W.h(str(est.get('as_of'))[:10])}"
        if est.get("llamadas"):
            detalle = f"{est['llamadas']} consultas, {est.get('creditos_restantes')} créditos restantes"
        else:
            detalle = "desde la caché local del día"
        origen = f"Datos públicos del SECOP II vía Croma (as_of {W.h(str(est.get('as_of'))[:10])}, {detalle})."
    else:
        kicker = f"Hoy · {P.fecha_larga(fuente.hoy())} · 6:00 a. m. (snapshot)"
        origen = f"Datos públicos del SECOP II (snapshot {fuente.hoy().isoformat()})."
    side = _SIDEBAR_ORIGINAL(items, "/panel", (
        '<div class="side-foot"><div class="kicker">Sesión</div><b>Constructora Andina S.A.S.</b>'
        '<small>licitaciones@constructoraandina.co</small><a href="/" style="display:inline-block;margin-top:10px;font-size:12px;color:var(--ad-ink-70)">Salir →</a></div>'))
    cuerpo = f"""
<div class="cab"><div><div class="kicker">{kicker}</div>
<h1 class="titulo">Buenos días, Constructora Andina. Cinco maneras de ganar más obra.</h1>
<p class="mute" style="font-size:14px;margin-top:6px">Cada tarjeta es un enfoque de producto; todos corren sobre los mismos datos públicos del SECOP II.</p></div>
<span class="badge"><span class="dot"></span>{n_abiertos} procesos abiertos {'ahora' if est['fuente'] == 'croma' else 'en el snapshot'}</span></div>
<div class="pn-grid">{tarjetas}
  <div class="pn-nota"><div class="kicker">Para el equipo</div><p style="margin:0">El flujo completo: landing → Ingresar → login → Iniciar → este panel → cada enfoque. Cada uno tiene su <code>ENFOQUE.md</code> en <code>docs/enfoques/</code> con lo que está simulado y las preguntas abiertas.</p></div>
</div>
<p class="foot-note">{origen} Perfil de constructora ficticio. Las probabilidades y recomendaciones son estimaciones; no garantizan un resultado.</p>
"""
    css = P.CSS
    html = W.pagina("Panel", cuerpo, side, css)
    # el shell de pliego/ carga /static/base.css; en el hub /static es el de la landing
    return html.replace('href="/static/base.css"', 'href="/filtro/static/base.css"')


@app.get("/favicon.ico")
def favicon():
    return FileResponse(ESTATICOS / "favicon.png")
