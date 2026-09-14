"""El panel de la empresa. Fase 1: pantalla de bienvenida con el estado de
la cuenta; fase 4 le pone las tarjetas con cifras."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from plataforma import db, sesiones
from plataforma import vistas as V

router = APIRouter()


@router.get("/panel", response_class=HTMLResponse)
def panel(request: Request, usuario: dict = Depends(sesiones.requiere_sesion)):
    empresa = request.state.empresa
    listos = db.uno("SELECT count(*) AS n FROM pliego.descargas_departamento WHERE estado = 'lista' AND departamento = ANY(%s)",
                    [empresa["departamentos"]])["n"] if empresa["departamentos"] else 0
    pasos = [
        ("Correo confirmado", True, "/verificar"),
        ("Perfil de la empresa", empresa["perfil_completo"], "/empresa/perfil/1"),
        (f"Datos de sus departamentos ({listos} de {len(empresa['departamentos'])} listos)", listos > 0, "/empresa/datos"),
    ]
    lista = "".join(
        f'<li style="margin:6px 0">{"✅" if ok else "⬜"} <a href="{V.h(ruta)}">{V.h(t)}</a></li>' for t, ok, ruta in pasos)
    cuerpo = (V.cabecera("Panel", f"Buenos días, {empresa['nombre']}.", "Lo que falta para que Pliego trabaje con sus datos.")
              + V.mensajes(ok=request.query_params.get("ok"), error=request.query_params.get("error"), clase="msg")
              + f'<div class="card"><ul style="list-style:none;padding:0;margin:0;font-size:15px">{lista}</ul></div>')
    return V.privada("Panel", cuerpo, "/panel", usuario, empresa, sesiones.token_csrf(request))
