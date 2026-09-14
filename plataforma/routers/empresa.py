"""La empresa: equipo e invitaciones (fase 1); perfil y datos (fases 2-3)."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from plataforma import cuentas, seguridad, sesiones
from plataforma import vistas as V

router = APIRouter()


def _fecha(d) -> str:
    return d.strftime("%Y-%m-%d") if d else "—"


@router.get("/empresa/equipo", response_class=HTMLResponse)
def equipo(request: Request, usuario: dict = Depends(sesiones.requiere_sesion)):
    empresa, token = request.state.empresa, sesiones.token_csrf(request)
    admin = usuario["rol"] == "admin"
    filas = ""
    for u in cuentas.equipo(empresa["id"]):
        acciones = ""
        if admin and u["id"] != usuario["id"]:
            otro = "miembro" if u["rol"] == "admin" else "admin"
            acciones = (f'<form method="post" action="/empresa/equipo/rol" style="display:inline">{V.csrf(token)}'
                        f'<input type="hidden" name="usuario_id" value="{u["id"]}"><input type="hidden" name="rol" value="{otro}">'
                        f'<button class="btn" type="submit">Hacer {otro}</button></form> '
                        f'<form method="post" action="/empresa/equipo/quitar" style="display:inline" onsubmit="return confirm(\'¿Quitar a {V.h(u["nombre"])} de la empresa?\')">{V.csrf(token)}'
                        f'<input type="hidden" name="usuario_id" value="{u["id"]}"><button class="btn peligro" type="submit">Quitar</button></form>')
        filas += (f'<tr><td>{V.h(u["nombre"])}{" (usted)" if u["id"] == usuario["id"] else ""}</td><td>{V.h(u["email"])}</td>'
                  f'<td>{V.h(u["rol"])}</td><td>{"sí" if u["email_verificado"] else "pendiente"}</td>'
                  f'<td>{_fecha(u["ultimo_acceso"])}</td><td>{acciones}</td></tr>')
    pendientes = ""
    for t in cuentas.invitaciones_pendientes(empresa["id"]):
        revocar = (f'<form method="post" action="/empresa/equipo/revocar" style="display:inline">{V.csrf(token)}'
                   f'<input type="hidden" name="token" value="{V.h(t["id"])}"><button class="btn peligro" type="submit">Revocar</button></form>') if admin else ""
        pendientes += f'<tr><td>{V.h(t["email"])}</td><td>{V.h(t["rol"])}</td><td>vence {_fecha(t["expira"])}</td><td>{revocar}</td></tr>'
    invitar = ""
    if admin:
        invitar = (f'<div class="card" style="margin-top:24px"><div class="card-head"><div class="card-title">Invitar a alguien</div></div>'
                   f'<form method="post" action="/invitar" class="form">{V.csrf(token)}<div class="fila">'
                   f'{V.campo("email", "Correo", "email", clase="campo", autocomplete="off")}'
                   f'<label class="campo">Rol<select name="rol"><option value="miembro">Miembro</option><option value="admin">Administrador</option></select></label></div>'
                   f'<div><button class="btn hot" type="submit">Enviar invitación</button></div></form></div>')
    cuerpo = (V.cabecera("Empresa", "Equipo", "Quiénes pueden entrar a Pliego por " + empresa["nombre"] + ".")
              + V.mensajes(ok=request.query_params.get("ok"), error=request.query_params.get("error"), clase="msg")
              + f'<div class="card"><table class="tabla"><tr><th>Nombre</th><th>Correo</th><th>Rol</th><th>Verificado</th><th>Último acceso</th><th></th></tr>{filas}</table></div>'
              + (f'<div class="card" style="margin-top:24px"><div class="card-head"><div class="card-title">Invitaciones pendientes</div></div>'
                 f'<table class="tabla"><tr><th>Correo</th><th>Rol</th><th></th><th></th></tr>{pendientes}</table></div>' if pendientes else "")
              + invitar)
    return V.privada("Equipo", cuerpo, "/empresa/equipo", usuario, empresa, token)


@router.post("/invitar")
def invitar(request: Request, usuario: dict = Depends(sesiones.requiere_admin), _: None = Depends(sesiones.csrf),
            email: str = Form(""), rol: str = Form("miembro")):
    e = seguridad.email_valido(email)
    if not e:
        return sesiones.redirigir("/empresa/equipo?error=" + quote("El correo no es válido."))
    if rol not in ("admin", "miembro"):
        rol = "miembro"
    if not seguridad.permitir("invitar:" + str(request.state.empresa["id"]), 20, 3600):
        return sesiones.redirigir("/empresa/equipo?error=" + quote("Demasiadas invitaciones en una hora."))
    if cuentas.invitar(request.state.empresa, usuario, e, rol) is None:
        return sesiones.redirigir("/empresa/equipo?error=" + quote("Ese correo ya tiene una cuenta en Pliego."))
    return sesiones.redirigir("/empresa/equipo?ok=" + quote(f"Invitación enviada a {e}."))


@router.post("/empresa/equipo/rol")
def cambiar_rol(request: Request, usuario: dict = Depends(sesiones.requiere_admin), _: None = Depends(sesiones.csrf),
                usuario_id: int = Form(...), rol: str = Form(...)):
    error = cuentas.cambiar_rol(request.state.empresa["id"], usuario_id, rol)
    return sesiones.redirigir("/empresa/equipo?" + ("error=" + quote(error) if error else "ok=" + quote("Rol actualizado.")))


@router.post("/empresa/equipo/quitar")
def quitar(request: Request, usuario: dict = Depends(sesiones.requiere_admin), _: None = Depends(sesiones.csrf),
           usuario_id: int = Form(...)):
    if usuario_id == usuario["id"]:
        return sesiones.redirigir("/empresa/equipo?error=" + quote("No puede quitarse a sí mismo."))
    error = cuentas.quitar_usuario(request.state.empresa["id"], usuario_id)
    return sesiones.redirigir("/empresa/equipo?" + ("error=" + quote(error) if error else "ok=" + quote("Usuario retirado.")))


@router.post("/empresa/equipo/revocar")
def revocar(request: Request, usuario: dict = Depends(sesiones.requiere_admin), _: None = Depends(sesiones.csrf),
            token: str = Form(...)):
    cuentas.revocar_invitacion(request.state.empresa["id"], token)
    return sesiones.redirigir("/empresa/equipo?ok=" + quote("Invitación revocada."))
