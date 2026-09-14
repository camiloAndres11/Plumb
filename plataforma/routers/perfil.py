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

from plataforma import db, esquemas, sesiones
from plataforma import vistas as V
from plataforma.catalogos import DEPARTAMENTOS, UNSPSC, UNSPSC_NOMBRE

router = APIRouter()
TITULOS = {1: "Dónde y qué construye", 2: "Capacidad", 3: "Experiencia"}


def _pasos(actual: int) -> str:
    return '<div class="pasos">' + " · ".join(
        f'<a href="/empresa/perfil/{n}" class="{"on" if n == actual else ""}">{n}. {t}</a>' for n, t in TITULOS.items()) + "</div>"


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
    # Los departamentos nuevos quedan pendientes de descarga (fase 3 los baja).
    for d in deptos:
        db.ejecutar("INSERT INTO pliego.descargas_departamento (departamento, estado) VALUES (%s, 'pendiente') "
                    "ON CONFLICT (departamento) DO NOTHING", [d])


def _pagina(request: Request, usuario: dict, paso: int, cuerpo_form: str, error: str | None = None) -> str:
    empresa = request.state.empresa
    cuerpo = (V.cabecera("Empresa", f"Perfil de {empresa['nombre']}", "Con esto Pliego decide qué procesos le muestra y cómo los evalúa.")
              + _pasos(paso)
              + V.mensajes(ok=request.query_params.get("ok"), error=error or request.query_params.get("error"), clase="msg")
              + f'<div class="card"><form method="post" action="/empresa/perfil/{paso}" class="form">'
                f'{V.csrf(sesiones.token_csrf(request))}{cuerpo_form}'
                f'<div style="display:flex;gap:12px;align-items:center"><button class="btn hot" type="submit">Guardar y seguir</button>'
                f'{"<a class=btn href=/empresa/perfil/" + str(paso - 1) + ">← Anterior</a>" if paso > 1 else ""}</div></form></div>')
    return V.privada(f"Perfil · paso {paso}", cuerpo, "/empresa/perfil", usuario, empresa, sesiones.token_csrf(request), js=_JS)


_JS = """<script>
(function(){
  var b = document.getElementById('agregar-exp'); if (!b) return;
  var tpl = document.getElementById('fila-exp').content;
  b.addEventListener('click', function(){ document.getElementById('exp').appendChild(document.importNode(tpl, true)); });
  document.getElementById('exp').addEventListener('click', function(e){ if (e.target.dataset.quitar !== undefined) e.target.closest('.exp-fila').remove(); });
})();
</script>"""


# ------------------------------------------------------------------ paso 1
def _form1(p: dict) -> str:
    sede = p.get("sede") or {}
    deptos = set(p.get("departamentos_interes") or [])
    codigos = list(p.get("unspsc") or [])
    otros = [c for c in codigos if c not in UNSPSC_NOMBRE]
    opciones_depto = "".join(f'<option value="{d}"{" selected" if d == sede.get("departamento") else ""}>{V.h(d.title())}</option>' for d in DEPARTAMENTOS)
    chk_deptos = "".join(
        f'<label class="chip"><input type="checkbox" name="departamentos_interes" value="{d}"{" checked" if d in deptos else ""}> {V.h(d.title())}</label>'
        for d in DEPARTAMENTOS)
    chk_unspsc = "".join(
        f'<label class="chip" title="{c}"><input type="checkbox" name="unspsc" value="{c}"{" checked" if c in codigos else ""}> {V.h(n)} <small>{c[3:7]}</small></label>'
        for c, n in UNSPSC)
    return (f'<div class="fila">{V.campo("ciudad", "Ciudad de la sede", valor=(sede.get("ciudad") or "").title(), clase="campo")}'
            f'<label class="campo">Departamento de la sede<select name="departamento" required><option value="">—</option>{opciones_depto}</select></label></div>'
            f'<div class="campo">Departamentos donde licita <small>Pliego descarga los procesos y contratos de estos departamentos; elija hasta 10.</small>'
            f'<div class="chips">{chk_deptos}</div></div>'
            f'<div class="campo">Qué construye (códigos UNSPSC) <small>Marque las clases que aparecen en sus contratos. La familia (4 dígitos) es lo que cuenta para la experiencia.</small>'
            f'<div class="chips">{chk_unspsc}</div></div>'
            f'{V.campo("unspsc_otros", "Otros códigos", valor=", ".join(otros), requerido=False, clase="campo", placeholder="V1.72141002, 72151100", ayuda="Separados por coma; con o sin el prefijo V1.")}')


@router.get("/empresa/perfil/1", response_class=HTMLResponse)
def paso1(request: Request, usuario: dict = Depends(sesiones.requiere_sesion)):
    return _pagina(request, usuario, 1, _form1(request.state.empresa.get("perfil") or {}))


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
        return _pagina(request, usuario, 1, _form1({**(request.state.empresa.get("perfil") or {}), **datos}), _errores(e))
    _guardar(request.state.empresa, parte)
    return sesiones.redirigir("/empresa/perfil/2?ok=" + quote("Sede y objeto guardados."))


# ------------------------------------------------------------------ paso 2
def _num(nombre, etiqueta, valor, paso="any", ayuda="", requerido=True):
    return V.campo(nombre, etiqueta, "number", valor="" if valor in (None, "") else valor, clase="campo", ayuda=ayuda,
                   requerido=requerido, extra=f'step="{paso}" inputmode="decimal"')


def _form2(p: dict) -> str:
    rup, fin, org, cu = p.get("rup") or {}, p.get("financiero") or {}, p.get("organizacional") or {}, p.get("cuantia_objetivo") or {}
    return (f'<div class="fila"><label class="campo">RUP<span class="lg-check" style="margin-top:8px"><input type="checkbox" name="rup_vigente" value="1"{" checked" if rup.get("vigente") else ""}> Inscripción vigente en el Registro Único de Proponentes</span></label>'
            f'{V.campo("rup_renovado", "Última renovación", "date", valor=rup.get("renovado") or "", requerido=False, clase="campo")}</div>'
            f'<div class="kicker" style="margin-top:8px">Indicadores financieros (del RUP)</div><div class="fila">'
            f'{_num("liquidez", "Índice de liquidez", fin.get("liquidez"), "0.01", "activo corriente / pasivo corriente")}'
            f'{_num("endeudamiento", "Nivel de endeudamiento", fin.get("endeudamiento"), "0.01", "pasivo total / activo total, entre 0 y 1")}'
            f'{_num("cobertura_intereses", "Razón de cobertura de intereses", fin.get("cobertura_intereses"), "0.01")}'
            f'{_num("patrimonio", "Patrimonio (COP)", fin.get("patrimonio"), "1")}'
            f'{_num("capital_trabajo", "Capital de trabajo (COP)", fin.get("capital_trabajo"), "1")}</div>'
            f'<div class="kicker" style="margin-top:8px">Indicadores organizacionales</div><div class="fila">'
            f'{_num("rentabilidad_patrimonio", "Rentabilidad del patrimonio", org.get("rentabilidad_patrimonio"), "0.001", "utilidad operacional / patrimonio")}'
            f'{_num("rentabilidad_activo", "Rentabilidad del activo", org.get("rentabilidad_activo"), "0.001")}</div>'
            f'<div class="kicker" style="margin-top:8px">Capacidad</div><div class="fila">'
            f'{_num("capacidad_residual", "Capacidad residual de contratación (COP)", p.get("capacidad_residual"), "1", "lo que puede comprometer hoy")}'
            f'{_num("contratos_en_ejecucion", "Contratos en ejecución", p.get("contratos_en_ejecucion"), "1")}'
            f'{_num("cuantia_min", "Cuantía mínima que le interesa (COP)", cu.get("min"), "1")}'
            f'{_num("cuantia_max", "Cuantía máxima (COP)", cu.get("max"), "1")}</div>')


@router.get("/empresa/perfil/2", response_class=HTMLResponse)
def paso2(request: Request, usuario: dict = Depends(sesiones.requiere_sesion)):
    return _pagina(request, usuario, 2, _form2(request.state.empresa.get("perfil") or {}))


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
        return _pagina(request, usuario, 2, _form2({**(request.state.empresa.get("perfil") or {}), **datos}), _errores(e))
    _guardar(request.state.empresa, parte)
    return sesiones.redirigir("/empresa/perfil/3?ok=" + quote("Capacidad guardada."))


# ------------------------------------------------------------------ paso 3
def _fila_exp(e: dict | None = None) -> str:
    e = e or {}
    paso_decimal, rango_anio = 'step="0.1"', 'min="1990" max="2100"'
    return (f'<div class="exp-fila card" style="padding:14px;margin-bottom:10px"><div class="fila">'
            f'{V.campo("exp_objeto", "Objeto del contrato", valor=e.get("objeto", ""), clase="campo")}'
            f'{V.campo("exp_entidad", "Entidad contratante", valor=(e.get("entidad") or "").title(), clase="campo")}</div>'
            f'<div class="fila" style="grid-template-columns:1fr 1fr 1fr 1fr">'
            f'{V.campo("exp_unspsc", "UNSPSC", valor=e.get("unspsc", ""), clase="campo", placeholder="V1.72141000")}'
            f'{V.campo("exp_valor_smmlv", "Valor (SMMLV)", "number", valor=e.get("valor_smmlv", ""), clase="campo", extra=paso_decimal)}'
            f'{V.campo("exp_anio", "Año", "number", valor=e.get("anio", ""), clase="campo", extra=rango_anio)}'
            f'<label class="campo">Liquidado<select name="exp_liquidado"><option value="1"{" selected" if e.get("liquidado", True) else ""}>Sí</option>'
            f'<option value="0"{"" if e.get("liquidado", True) else " selected"}>No</option></select></label></div>'
            f'<div style="margin-top:8px"><button type="button" class="btn peligro" data-quitar>Quitar</button></div></div>')


def _form3(p: dict) -> str:
    filas = "".join(_fila_exp(e) for e in (p.get("experiencia") or []))
    return (f'<div class="campo">Contratos que acreditan experiencia <small>Los que están en el RUP. La experiencia se suma por familia UNSPSC (4 dígitos), '
            f'así que un contrato de pavimentación cuenta para toda la familia 7214.</small></div>'
            f'<div id="exp">{filas}</div>'
            f'<template id="fila-exp">{_fila_exp()}</template>'
            f'<div><button type="button" class="btn" id="agregar-exp">+ Agregar contrato</button></div>')


@router.get("/empresa/perfil/3", response_class=HTMLResponse)
def paso3(request: Request, usuario: dict = Depends(sesiones.requiere_sesion)):
    return _pagina(request, usuario, 3, _form3(request.state.empresa.get("perfil") or {}))


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
        return _pagina(request, usuario, 3, _form3({"experiencia": filas}), _errores(e))
    _guardar(request.state.empresa, parte)
    empresa = db.uno("SELECT perfil_completo FROM pliego.empresas WHERE id = %s", [request.state.empresa["id"]])
    if empresa and empresa["perfil_completo"]:
        return sesiones.redirigir("/empresa/datos?ok=" + quote("Perfil completo. Ahora Pliego prepara los datos de sus departamentos."))
    return sesiones.redirigir("/empresa/perfil/1?error=" + quote("Falta algún paso: revise los tres."))


@router.get("/empresa/perfil", response_class=HTMLResponse)
def perfil_inicio():
    return sesiones.redirigir("/empresa/perfil/1")
