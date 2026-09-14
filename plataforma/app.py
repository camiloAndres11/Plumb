"""Pliego para empresas: el servicio que una constructora usa sola.

    uvicorn plataforma.app:app --port 8100

Convive con la demo (demo/app.py, puerto 8000): esta es la version con
cuentas reales, perfil real y datos de Croma por empresa; la demo sigue
siendo la vitrina con el perfil ficticio. Ver docs/enfoques/plataforma.md.

Que hay en cada carpeta:
  routers/publico.py   /, /login, /registro, /verificar, /olvide, /restablecer, /terminos, /privacidad
  routers/empresa.py   /empresa/perfil/{1,2,3}, /empresa/equipo, /invitar, /empresa/datos
  routers/panel.py     /panel
  routers/cuenta.py    /cuenta
  routers/admin.py     /admin (solo PLATAFORMA_ADMINS)
  sesiones.py          cookie -> request.state.usuario / .empresa
  contexto.py          fija la empresa actual para los enfoques (pliego/comun/contexto.py)
"""
from __future__ import annotations

import logging
import os
import re
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from plataforma import db, enfoques, extraccion, seguridad, sesiones, trabajos
from plataforma import vistas as V
from plataforma.config import RAIZ, VERSION, config
from pliego.comun import croma, warehouse

log = logging.getLogger("pliego.plataforma")
acceso = logging.getLogger("pliego.acceso")

# La plataforma SIEMPRE sirve los enfoques desde el warehouse por empresa
# (pliego/comun/fuente.py modo warehouse), aunque el .env compartido con la
# demo pida `croma` o nada.
os.environ["PLIEGO_FUENTE"] = "warehouse"
os.environ.setdefault("PLATAFORMA_DATOS", config.plataforma_datos)


class EstaticosDeDos(StaticFiles):
    """/static sirve la landing (plataforma/static: landing.css, favicon) y
    el shell de los enfoques (pliego/static: base.css) desde una sola ruta."""

    def get_directories(self, directory=None, packages=None):
        return [str(RAIZ / "plataforma" / "static"), str(RAIZ / "pliego" / "static")]


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.secret_key:
        log.warning("falta SECRET_KEY: las rutas con sesion responderan 503 (ver .env.example)")
    trabajos.arrancar()
    yield
    trabajos.parar()
    warehouse.cerrar()
    db.cerrar()


app = FastAPI(title="Pliego", version=VERSION, lifespan=lifespan, docs_url=None, redoc_url=None)
app.mount("/static", EstaticosDeDos(), name="static")
app.middleware("http")(sesiones.cargar)


# Los tokens de un uso (verificar, restablecer, invitacion) viajan en el
# path; un token de reset vale lo que la contrasena durante una hora, y no
# puede quedar en claro en un log que lee soporte o un agregador.
_TOKEN_EN_PATH = re.compile(r"^(/(?:verificar|restablecer|invitacion)/)[^/?#]+")


def ruta_para_log(path: str) -> str:
    return _TOKEN_EN_PATH.sub(r"\1<token>", path)


# TODO(F4): al sacar el CSS y el JS inline a archivos (plantillas Jinja),
# quitar 'unsafe-inline' de script-src y style-src.
CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
       "base-uri 'self'; form-action 'self'")


@app.middleware("http")
async def _cabeceras_seguridad(request: Request, call_next):
    """Sin CSP cualquier XSS futuro es explotacion total; sin frame-ancestors
    un iframe invisible sobre /pliegos/{id}/borrar es clickjacking."""
    respuesta = await call_next(request)
    h = respuesta.headers
    h.setdefault("Content-Security-Policy", CSP)
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.url.scheme == "https":
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return respuesta


@app.middleware("http")
async def _acceso(request: Request, call_next):
    """Una linea por peticion con usuario y empresa: es lo que hay que
    grepear cuando un cliente dice "no me funciona"."""
    t0 = time.monotonic()
    respuesta = await call_next(request)
    if not request.url.path.startswith("/static"):
        u, e = getattr(request.state, "usuario", None), getattr(request.state, "empresa", None)
        acceso.info("%s %s %s %dms usuario=%s empresa=%s", request.method, ruta_para_log(request.url.path),
                    respuesta.status_code, (time.monotonic() - t0) * 1000, u["id"] if u else "-", e["id"] if e else "-")
    return respuesta


def estado_detallado() -> dict:
    """Lo que antes devolvia /health a cualquiera: rutas en disco, errores de
    Postgres, ids de pliegos en cola, que llaves hay. Es reconocimiento
    gratis; ahora solo lo ve /admin."""
    ok, detalle = db.disponible()
    try:
        wh = warehouse.estado()
        wh_detalle = {"ok": True, "departamentos": len(wh["departamentos"]), "as_of": wh["as_of"], "ruta": str(warehouse.ruta())}
    except Exception as e:   # sin disco o corrupto: se reporta, no se cae
        wh_detalle = {"ok": False, "error": str(e)[:200]}
    ultimo = None
    if ok:
        fila = db.uno("SELECT max(ultima_ok) AS u FROM pliego.descargas_departamento")
        ultimo = fila["u"].isoformat() if fila and fila["u"] else None
    return {"ok": ok, "version": VERSION, "postgres": detalle, "warehouse": wh_detalle,
            "cola": trabajos.en_cola(), "ultimo_refresco": ultimo, "trabajos": bool(trabajos._hilos),
            "croma": croma.disponible(), "extraccion": extraccion.disponible(),
            "secret_key": bool(config.secret_key)}


@app.get("/health")
def health():
    """Para el health check del hosting: solo si la base responde."""
    ok, _ = db.disponible()
    return JSONResponse({"ok": ok, "version": VERSION}, status_code=200 if ok else 503)


@app.exception_handler(sesiones.Redirigir)
async def _redirigir(request: Request, exc: sesiones.Redirigir):
    return sesiones.redirigir(exc.url)


@app.exception_handler(sesiones.Prohibido)
async def _prohibido(request: Request, exc: sesiones.Prohibido):
    return HTMLResponse(V.publica("Sin permiso", f"<div><h1>Sin permiso.</h1><p class='sub'>{V.h(str(exc))}</p></div>"
                                  '<div class="lg-links"><a href="/panel">Ir al panel</a></div>'), status_code=403)


@app.exception_handler(db.BaseNoDisponible)
@app.exception_handler(seguridad.SinSecreto)
async def _sin_base(request: Request, exc: Exception):
    return JSONResponse({"error": {"codigo": "servicio_no_configurado", "mensaje": str(exc)}}, status_code=503)


from plataforma.routers import admin, cuenta, empresa, panel, perfil, pliegos, publico  # noqa: E402  (registran rutas sobre `app`)

for r in (publico, panel, empresa, perfil, cuenta, pliegos, admin):
    app.include_router(r.router)
enfoques.montar(app)
