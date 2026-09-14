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
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from plataforma import db, seguridad, sesiones, trabajos
from plataforma import vistas as V
from plataforma.config import RAIZ, VERSION, config
from pliego.comun import warehouse

log = logging.getLogger("pliego.plataforma")

# La plataforma SIEMPRE sirve los enfoques desde el warehouse por empresa
# (pliego/comun/fuente.py modo warehouse), aunque el .env compartido con la
# demo pida `croma` o nada.
os.environ["PLIEGO_FUENTE"] = "warehouse"
os.environ.setdefault("PLATAFORMA_DATOS", config.plataforma_datos)


class EstaticosDeDos(StaticFiles):
    """/static sirve la landing (plomada/static: landing.css, favicon) y el
    shell de los enfoques (pliego/static: base.css) desde una sola ruta."""

    def get_directories(self, directory=None, packages=None):
        return [str(RAIZ / "plomada" / "static"), str(RAIZ / "pliego" / "static")]


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


@app.get("/health")
def health():
    ok, detalle = db.disponible()
    try:
        wh = warehouse.estado()
        wh_detalle = {"ok": True, "departamentos": len(wh["departamentos"]), "as_of": wh["as_of"], "ruta": str(warehouse.ruta())}
    except Exception as e:   # sin disco o corrupto: se reporta, no se cae
        wh_detalle = {"ok": False, "error": str(e)[:200]}
    return JSONResponse({"ok": ok, "version": VERSION, "postgres": detalle, "warehouse": wh_detalle,
                         "cola": trabajos.en_cola(), "secret_key": bool(config.secret_key)},
                        status_code=200 if ok else 503)


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


from plataforma.routers import cuenta, empresa, panel, perfil, publico  # noqa: E402  (registran rutas sobre `app`)

for r in (publico, panel, empresa, perfil, cuenta):
    app.include_router(r.router)
