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
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from plataforma import db
from plataforma.config import RAIZ, VERSION, config

log = logging.getLogger("pliego.plataforma")


class EstaticosDeDos(StaticFiles):
    """/static sirve la landing (plomada/static: landing.css, favicon) y el
    shell de los enfoques (pliego/static: base.css) desde una sola ruta."""

    def get_directories(self, directory=None, packages=None):
        return [str(RAIZ / "plomada" / "static"), str(RAIZ / "pliego" / "static")]


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.secret_key:
        log.warning("falta SECRET_KEY: las rutas con sesion responderan 503 (ver .env.example)")
    yield
    db.cerrar()


app = FastAPI(title="Pliego", version=VERSION, lifespan=lifespan, docs_url=None, redoc_url=None)
app.mount("/static", EstaticosDeDos(), name="static")


@app.get("/health")
def health():
    ok, detalle = db.disponible()
    return JSONResponse({"ok": ok, "version": VERSION, "postgres": detalle,
                         "secret_key": bool(config.secret_key)}, status_code=200 if ok else 503)


@app.exception_handler(db.BaseNoDisponible)
async def _sin_base(request: Request, exc: db.BaseNoDisponible):
    return JSONResponse({"error": {"codigo": "base_no_disponible", "mensaje": str(exc)}}, status_code=503)


from plataforma.routers import publico  # noqa: E402  (registra rutas sobre `app`)

app.include_router(publico.router)
