"""El perfil de la empresa en tres pasos: sede y objeto, capacidad,
experiencia. Cada paso valida solo su parte (plataforma/esquemas.py) y
guarda en pliego.empresas.perfil (JSONB); `perfil_completo` se recalcula
en cada guardado. Los departamentos van ademas a la columna
`departamentos`, que es lo que decide que datos de Croma ve la empresa."""
from __future__ import annotations

import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import ValidationError

from plataforma import db, esquemas, sesiones, trabajos
from plataforma import vistas as V
from plataforma.catalogos import DEPARTAMENTOS, UNSPSC, UNSPSC_NOMBRE

router = APIRouter()
TITULOS = {1: "Dónde y qué construye", 2: "Capacidad", 3: "Experiencia"}


def _errores(e: ValidationError) -> str:
    partes = []
    for err in e.errors()[:6]:
        campo = ".".join(str(x) for x in err["loc"]) or "formulario"
        partes.append(f"{campo}: {err['msg']}")
    return " · ".join(partes)


def _guardar(empresa: dict, parte: dict) -> None:
    perfil = {**(empresa.get("perfil") or {}), **parte}
    completo = esquemas.perfil_completo(perfil)
    deptos = perfil.get("departamentos_interes") or []
    db.ejecutar("UPDATE pliego.empresas SET perfil = %s, departamentos = %s, perfil_completo = %s WHERE id = %s",
                [json.dumps(perfil), deptos, completo, empresa["id"]])
    # Los departamentos nuevos quedan pendientes y se encolan para descargar.
    for d in deptos:
        if db.ejecutar("INSERT INTO pliego.descargas_departamento (departamento, estado) VALUES (%s, 'pendiente') "
                       "ON CONFLICT (departamento) DO NOTHING", [d]):
            trabajos.encolar(d)


def _pagina(request: Request, usuario: dict, paso: int, p: dict, error: str | None = None):
    empresa, q = request.state.empresa, request.query_params
    ctx = {"paso": paso, "p": p, "TITULOS": TITULOS, "ok": q.get("ok"), "error": error or q.get("error")}
    if paso == 1:
        codigos = list(p.get("unspsc") or [])
        ctx.update(DEPARTAMENTOS=DEPARTAMENTOS, UNSPSC=UNSPSC, deptos=set(p.get("departamentos_interes") or []),
                   codigos=codigos, otros=[c for c in codigos if c not in UNSPSC_NOMBRE])
    return V.privada(request, f"perfil/paso{paso}.html", f"Perfil · paso {paso}", "/empresa/perfil", usuario, empresa,
                     sesiones.token_csrf(request), **ctx)


@router.get("/empresa/perfil/1", response_class=HTMLResponse)
def paso1(request: Request, usuario: dict = Depends(sesiones.requiere_sesion)):
    return _pagina(request, usuario, 1, request.state.empresa.get("perfil") or {})


@router.post("/empresa/perfil/1", response_class=HTMLResponse)
async def guardar1(request: Request, usuario: dict = Depends(sesiones.requiere_admin), _: None = Depends(sesiones.csrf)):
    f = await request.form()
    otros = [c.strip() for c in (f.get("unspsc_otros") or "").split(",") if c.strip()]
    datos = {"sede": {"ciudad": f.get("ciudad"), "departamento": f.get("departamento")},
             "departamentos_interes": f.getlist("departamentos_interes"),
             "unspsc": f.getlist("unspsc") + otros}
    try:
        parte = esquemas.PasoSede.model_validate(datos).model_dump()
    except ValidationError as e:
        return _pagina(request, usuario, 1, {**(request.state.empresa.get("perfil") or {}), **datos}, _errores(e))
    _guardar(request.state.empresa, parte)
    return sesiones.redirigir("/empresa/perfil/2?ok=" + quote("Sede y objeto guardados."))


# ------------------------------------------------------------------ paso 2
@router.get("/empresa/perfil/2", response_class=HTMLResponse)
def paso2(request: Request, usuario: dict = Depends(sesiones.requiere_sesion)):
    return _pagina(request, usuario, 2, request.state.empresa.get("perfil") or {})


@router.post("/empresa/perfil/2", response_class=HTMLResponse)
async def guardar2(request: Request, usuario: dict = Depends(sesiones.requiere_admin), _: None = Depends(sesiones.csrf)):
    f = await request.form()
    g = f.get
    datos = {"rup": {"vigente": g("rup_vigente") == "1", "renovado": g("rup_renovado") or None},
             "financiero": {k: g(k) for k in ("liquidez", "endeudamiento", "cobertura_intereses", "patrimonio", "capital_trabajo")},
             "organizacional": {k: g(k) for k in ("rentabilidad_patrimonio", "rentabilidad_activo")},
             "capacidad_residual": g("capacidad_residual"), "contratos_en_ejecucion": g("contratos_en_ejecucion"),
             "cuantia_objetivo": {"min": g("cuantia_min"), "max": g("cuantia_max")}}
    try:
        parte = esquemas.PasoCapacidad.model_validate(datos).model_dump()
    except ValidationError as e:
        return _pagina(request, usuario, 2, {**(request.state.empresa.get("perfil") or {}), **datos}, _errores(e))
    _guardar(request.state.empresa, parte)
    return sesiones.redirigir("/empresa/perfil/3?ok=" + quote("Capacidad guardada."))


# ------------------------------------------------------------------ paso 3
@router.get("/empresa/perfil/3", response_class=HTMLResponse)
def paso3(request: Request, usuario: dict = Depends(sesiones.requiere_sesion)):
    return _pagina(request, usuario, 3, request.state.empresa.get("perfil") or {})


@router.post("/empresa/perfil/3", response_class=HTMLResponse)
async def guardar3(request: Request, usuario: dict = Depends(sesiones.requiere_admin), _: None = Depends(sesiones.csrf)):
    f = await request.form()
    campos = ["exp_objeto", "exp_entidad", "exp_unspsc", "exp_valor_smmlv", "exp_anio", "exp_liquidado"]
    columnas = [f.getlist(c) for c in campos]
    filas = []
    for objeto, entidad, unspsc, valor, anio, liq in zip(*columnas):
        if not (objeto.strip() or entidad.strip()):
            continue   # fila vacia que dejo el boton "agregar"
        filas.append({"objeto": objeto.strip(), "entidad": entidad, "unspsc": unspsc, "valor_smmlv": valor,
                      "anio": anio, "liquidado": liq == "1"})
    try:
        parte = esquemas.PasoExperiencia.model_validate({"experiencia": filas}).model_dump()
    except ValidationError as e:
        return _pagina(request, usuario, 3, {"experiencia": filas}, _errores(e))
    _guardar(request.state.empresa, parte)
    empresa = db.uno("SELECT perfil_completo FROM pliego.empresas WHERE id = %s", [request.state.empresa["id"]])
    if empresa and empresa["perfil_completo"]:
        return sesiones.redirigir("/empresa/datos?ok=" + quote("Perfil completo. Ahora Pliego prepara los datos de sus departamentos."))
    return sesiones.redirigir("/empresa/perfil/1?error=" + quote("Falta algún paso: revise los tres."))


@router.get("/empresa/perfil", response_class=HTMLResponse)
def perfil_inicio():
    return sesiones.redirigir("/empresa/perfil/1")
