"""Un solo servicio para presentar los cinco enfoques al equipo.

    uvicorn demo.app:app --port 8000

  /            la landing comercial de Pliego (plomada/landing.html), con
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

import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from pliego.checklist.app import app as checklist_app
from pliego.comun import fuente
from pliego.comun import web as W
from pliego.filtro import datos as filtro_datos
from pliego.filtro.app import app as filtro_app
from pliego.generador.app import app as generador_app
from pliego.radar.app import app as radar_app
from pliego.simulador.app import app as simulador_app

RAIZ = Path(__file__).resolve().parents[1]
PLOMADA = RAIZ / "plomada"
LANDING = PLOMADA / "landing.html"

ENFOQUES = [
    ("filtro", "Filtro de procesos", "Deje de presentarse a licitaciones que no puede ganar.",
     "36 de 565", "procesos abiertos valen su tiempo", "filtro"),
    ("checklist", "Checklist del pliego", "No vuelva a quedar por fuera por un papel.",
     "3 cosas", "faltan para quedar habilitado en Bucaramanga", "check"),
    ("simulador", "Simulador de oferta", "Oferte al precio que maximiza su puntaje, no al más bajo.",
     "94,5 %", "precio recomendado para Maripí · 58,9 de 60", "grafico"),
    ("radar", "Radar de competidores", "Sepa contra quién compite antes de presentarse.",
     "10", "competidores probables en el CTP de Bucaramanga", "radar"),
    ("generador", "Generador de propuesta", "Prepare la propuesta en horas, no en días.",
     "60 %", "de la propuesta lista · falta 1 cosa que la rechaza", "doc"),
]
# Rutas del concentrador que las apps montadas pueden enlazar sin que se
# les anteponga el prefijo (la sidebar de cada una lleva «Panel»).
RUTAS_HUB = ("/panel", "/login", "/salir", "/#")

W.ICONOS.setdefault("check", '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 11l3 3L22 4"></path><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>')
W.ICONOS.setdefault("radar", '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"></circle><circle cx="12" cy="12" r="4"></circle><path d="M12 3v3M12 18v3M3 12h3M18 12h3"></path></svg>')


# ------------------------------------------------------- prefijo en el HTML
class ConPrefijo:
    """ASGI: antepone `prefijo` a las URLs de raiz (href/src/action, fetch y
    location en JS) de las respuestas HTML de la app envuelta. Deja en paz
    las rutas del concentrador y las que ya llevan el prefijo."""

    _ATTR = re.compile(r'((?:href|src|action)=")/(?!/)')
    _JS = re.compile(r"""((?:fetch|open)\(\s*['"])/(?!/)""")
    _JS_STR = re.compile(r"""(['"])/(proceso|documento|requisito|entidad|competidor|api|pliego\.pdf|paquete\.zip)""")

    def __init__(self, app, prefijo: str):
        self.app, self.prefijo = app, prefijo

    def _reescribir(self, html: str) -> str:
        def attr(m):
            resto = html_resto = m.string[m.end() - 1:m.end() + 8]
            return m.group(0) if resto.startswith(RUTAS_HUB) or html_resto.startswith(self.prefijo + "/") else m.group(1) + self.prefijo + "/"
        html = self._ATTR.sub(attr, html)
        html = self._JS.sub(lambda m: m.group(1) + self.prefijo + "/", html)
        html = self._JS_STR.sub(lambda m: m.group(1) + self.prefijo + "/" + m.group(2), html)
        return html

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        partes: list[bytes] = []
        cabecera = {}

        async def send_(msg):
            if msg["type"] == "http.response.start":
                # Redirecciones absolutas (p. ej. / -> /proceso/x) tambien llevan prefijo.
                headers = []
                for k, v in msg.get("headers", []):
                    if k == b"location" and v.startswith(b"/") and not v.startswith(b"//") \
                            and not v.decode().startswith(RUTAS_HUB) and not v.startswith(self.prefijo.encode() + b"/"):
                        v = self.prefijo.encode() + v
                    headers.append((k, v))
                msg = {**msg, "headers": headers}
                cabecera.update(msg)
                ct = dict(headers).get(b"content-type", b"")
                cabecera["html"] = b"text/html" in ct
                if not cabecera["html"]:
                    await send(msg)
                return
            if msg["type"] == "http.response.body":
                if not cabecera.get("html"):
                    await send(msg)
                    return
                partes.append(msg.get("body", b""))
                if not msg.get("more_body"):
                    cuerpo = self._reescribir(b"".join(partes).decode("utf-8")).encode("utf-8")
                    headers = [(k, v) for k, v in cabecera["headers"] if k != b"content-length"]
                    headers.append((b"content-length", str(len(cuerpo)).encode()))
                    await send({"type": "http.response.start", "status": cabecera["status"], "headers": headers})
                    await send({"type": "http.response.body", "body": cuerpo})
                return
            await send(msg)

        await self.app(scope, receive, send_)


_SIDEBAR_ORIGINAL = W.sidebar


def _sidebar_con_panel():
    """Cada app monta su sidebar con W.sidebar; aqui se le agrega el enlace
    al panel arriba, sin tocar las apps."""
    original = _SIDEBAR_ORIGINAL

    def sidebar(items, actual, pie=""):
        html = original(items, actual, pie)
        volver = ('<a class="side-item" href="/panel" style="margin-bottom:6px;color:var(--ad-ink-55)">'
                  '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M19 12H5M12 19l-7-7 7-7"></path></svg>Panel</a>')
        return html.replace("</a>", "</a>" + volver, 1)   # justo despues del logo
    W.sidebar = sidebar


_sidebar_con_panel()

app = FastAPI(title="Pliego · demo para el equipo", version="0.1.0", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(PLOMADA / "static")), name="static")
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


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def _fecha_larga(d) -> str:
    return f"{d.day} de {MESES[d.month - 1]}"


@app.get("/panel", response_class=HTMLResponse)
def panel():
    tarjetas = ""
    for i, (ruta, nombre, promesa, cifra, sub, icono) in enumerate(ENFOQUES):
        hot = i == 0
        tarjetas += f"""<a class="pn-card{' hot' if hot else ''}" href="/{ruta}/">
  <div><div class="pn-top"><span class="pn-ico">{W.ICONOS[icono]}</span><span class="tag{'' if hot else ' tag-neutro'}">Enfoque {i + 1}</span></div>
  <div class="pn-nombre">{W.h(nombre)}</div><div class="pn-promesa">{W.h(promesa)}</div></div>
  <div><div class="pn-cifra num{' hot' if hot else ''}">{W.h(cifra)}</div><div class="pn-sub">{W.h(sub)}</div>
  <div class="pn-abrir"><span>Abrir</span><span>→</span></div></div></a>"""
    items = [(f"/{r}/", ic, n) for r, n, _, _, _, ic in ENFOQUES]
    # De donde salen los datos: el snapshot commiteado o Croma (ver
    # pliego/comun/fuente.py). El panel lo dice para que nadie confunda uno
    # con otro en una demo.
    est = fuente.estado()
    n_abiertos = len(filtro_datos.procesos())
    if est["fuente"] == "croma":
        kicker = f"Hoy · {_fecha_larga(fuente.hoy())} · datos de Croma al {W.h(str(est.get('as_of'))[:10])}"
        origen = f"Datos públicos del SECOP II vía Croma (as_of {W.h(str(est.get('as_of'))[:10])}, {est.get('llamadas')} consultas, {est.get('creditos_restantes')} créditos restantes)."
    else:
        kicker = f"Hoy · {_fecha_larga(fuente.hoy())} · 6:00 a. m. (snapshot)"
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
    css = """<style>
.pn-grid { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 14px; }
.pn-card { display: flex; flex-direction: column; justify-content: space-between; gap: 22px; padding: 26px 28px; border-radius: 18px; background: var(--ad-glass); border: 1px solid var(--ad-line); min-height: 250px; transition: border-color .3s, transform .3s var(--ad-ease); }
.pn-card:hover { border-color: var(--ad-line-3); transform: translateY(-2px); }
.pn-card.hot { border-color: rgba(255,255,255,.18); }
.pn-top { display: flex; align-items: center; justify-content: space-between; }
.pn-ico { display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 12px; background: var(--ad-fill); color: var(--ad-ink-85); }
.pn-card.hot .pn-ico { color: var(--ad-accent-2); }
.pn-ico svg { width: 20px; height: 20px; }
.pn-nombre { font-size: 20px; font-weight: 600; letter-spacing: -.02em; margin-top: 18px; }
.pn-promesa { font-size: 14px; color: var(--ad-ink-60); margin-top: 6px; line-height: 1.5; }
.pn-cifra { font-size: 28px; font-weight: 600; letter-spacing: -.03em; }
.pn-sub { font-size: 12px; color: var(--ad-ink-50); margin-top: 2px; }
.pn-abrir { display: flex; justify-content: space-between; margin-top: 16px; font-size: 14px; color: var(--ad-ink-85); }
.pn-nota { display: flex; flex-direction: column; justify-content: center; gap: 10px; padding: 26px 28px; border-radius: 18px; border: 1px dashed var(--ad-line-3); color: var(--ad-ink-55); font-size: 14px; line-height: 1.5; }
.pn-nota code { font-size: 12px; color: var(--ad-ink-75); }
@media (max-width: 1100px) { .pn-grid { grid-template-columns: repeat(2, minmax(0,1fr)); } }
</style>"""
    html = W.pagina("Panel", cuerpo, side, css)
    # el shell de pliego/ carga /static/base.css; en el hub /static es el de la landing
    return html.replace('href="/static/base.css"', 'href="/filtro/static/base.css"')


@app.get("/favicon.ico")
def favicon():
    return FileResponse(PLOMADA / "static" / "favicon.png")
