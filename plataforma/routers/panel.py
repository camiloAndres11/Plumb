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
    listos = db.uno("SELECT count(*) AS n FROM pliego.descargas_departamento WHERE estado = 'lista' AND departamento = ANY(%s)",
                    [empresa["departamentos"]])["n"] if empresa["departamentos"] else 0
    pasos = [
        ("Correo confirmado", True, "/verificar"),
        ("Perfil de la empresa", empresa["perfil_completo"], "/empresa/perfil/1"),
        (f"Datos de sus departamentos ({listos} de {len(empresa['departamentos'])} listos)", listos > 0, "/empresa/datos"),
    ]
    lista = "".join(
        f'<li style="margin:6px 0">{"✅" if ok else "⬜"} <a href="{V.h(ruta)}">{V.h(t)}</a></li>' for t, ok, ruta in pasos)
    mensajes = V.mensajes(ok=request.query_params.get("ok"), error=request.query_params.get("error"), clase="msg")
    listo = empresa["perfil_completo"] and enfoques.datos_listos(contexto.ambito())
    if not listo:
        cuerpo = (V.cabecera("Panel", f"Buenos días, {empresa['nombre'].rstrip('.')}.", "Lo que falta para que Pliego trabaje con sus datos.")
                  + mensajes + f'<div class="card"><ul style="list-style:none;padding:0;margin:0;font-size:15px">{lista}</ul></div>')
        return V.privada("Panel", cuerpo, "/panel", usuario, empresa, sesiones.token_csrf(request))
    est = fuente.estado()
    from pliego.filtro import datos as filtro_datos
    n_abiertos = len(filtro_datos.procesos())
    deptos = ", ".join(d.title() for d in empresa["departamentos"])
    kicker = f"Hoy · {P.fecha_larga(fuente.hoy())} · datos al {V.h(str(est.get('as_of') or '')[:10])} · {V.h(deptos)}"
    cuerpo = (f'<div class="cab"><div><div class="kicker">{kicker}</div>'
              f'<h1 class="titulo">Buenos días, {V.h(empresa["nombre"].rstrip("."))}. Cinco maneras de ganar más obra.</h1>'
              f'<p class="mute" style="font-size:14px;margin-top:6px">Cada tarjeta es un enfoque; todos corren sobre los procesos y contratos de sus departamentos.</p></div>'
              f'<span class="badge"><span class="dot"></span>{n_abiertos} procesos abiertos ahora</span></div>'
              + mensajes
              + f'<div class="pn-grid">{P.tarjetas("/app/", set(enfoques.ACTIVOS))}'
                f'<div class="pn-nota"><div class="kicker">Sus datos</div><p style="margin:0">{V.h(deptos)}: procesos abiertos y contratos de construcción del SECOP II, '
                f'refrescados a diario. <a href="/empresa/datos">Ver estado</a> · <a href="/empresa/perfil/1">Editar perfil</a></p></div></div>'
              + '<p class="foot-note">Datos públicos del SECOP II vía Croma. Las probabilidades y recomendaciones son estimaciones; no garantizan un resultado.</p>')
    return V.privada("Panel", cuerpo, "/panel", usuario, empresa, sesiones.token_csrf(request), extra_head=P.CSS)
