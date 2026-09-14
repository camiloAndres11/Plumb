"""El panel de la empresa: los pasos que faltan o, cuando ya hay datos,
una tarjeta por enfoque con cifras de la empresa (pliego/comun/panel.py)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from plataforma import db, enfoques, sesiones
from plataforma import vistas as V
from pliego.comun import contexto, fuente
from pliego.comun import panel as P

router = APIRouter()


@router.get("/panel", response_class=HTMLResponse)
def panel(request: Request, usuario: dict = Depends(sesiones.requiere_sesion)):
    empresa = request.state.empresa
    q = request.query_params
    listos = db.uno("SELECT count(*) AS n FROM pliego.descargas_departamento WHERE estado = 'lista' AND departamento = ANY(%s)",
                    [empresa["departamentos"]])["n"] if empresa["departamentos"] else 0
    pasos = [
        ("Correo confirmado", True, "/verificar"),
        ("Perfil de la empresa", empresa["perfil_completo"], "/empresa/perfil/1"),
        (f"Datos de sus departamentos ({listos} de {len(empresa['departamentos'])} listos)", listos > 0, "/empresa/datos"),
    ]
    listo = empresa["perfil_completo"] and enfoques.datos_listos(contexto.ambito())
    ctx = {"listo": listo, "pasos": pasos, "ok": q.get("ok"), "error": q.get("error")}
    if listo:
        est = fuente.estado()
        e = contexto.get()
        activos = set(enfoques.ACTIVOS) | (set(enfoques.CON_PLIEGO) if (e and e.pliego) else set())
        from pliego.filtro import datos as filtro_datos
        deptos = ", ".join(d.title() for d in empresa["departamentos"])
        ctx.update(n_abiertos=len(filtro_datos.procesos()), deptos=deptos, tarjetas=P.tarjetas("/app/", activos),
                   pliego=e.pliego if e else None,
                   kicker=f"Hoy · {P.fecha_larga(fuente.hoy())} · datos al {str(est.get('as_of') or '')[:10]} · {deptos}")
    return V.privada(request, "panel.html", "Panel", "/panel", usuario, empresa, sesiones.token_csrf(request), **ctx)
