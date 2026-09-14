"""El usuario: nombre, contrasena y sesiones abiertas."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from plataforma import cuentas, seguridad, sesiones
from plataforma import vistas as V

router = APIRouter()


@router.get("/cuenta", response_class=HTMLResponse)
def cuenta(request: Request, usuario: dict = Depends(sesiones.requiere_sesion)):
    empresa, token, sesion = request.state.empresa, sesiones.token_csrf(request), request.state.sesion
    filas = ""
    for s in sesiones.listar(usuario["id"]):
        actual = s["id"] == sesion["id"]
        filas += (f'<tr><td>{s["ultimo_uso"].strftime("%Y-%m-%d %H:%M")}{" (esta)" if actual else ""}</td>'
                  f'<td>{V.h(s["ip"] or "")}</td><td style="max-width:360px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{V.h(s["agente"] or "")}</td></tr>')
    cuerpo = (V.cabecera("Cuenta", usuario["nombre"], usuario["email"] + " · " + usuario["rol"] + " en " + empresa["nombre"])
              + V.mensajes(ok=request.query_params.get("ok"), error=request.query_params.get("error"), clase="msg")
              + f'<div class="card"><div class="card-head"><div class="card-title">Nombre</div></div>'
                f'<form method="post" action="/cuenta/nombre" class="form">{V.csrf(token)}'
                f'{V.campo("nombre", "Cómo aparece en el equipo", valor=usuario["nombre"], clase="campo", autocomplete="name")}'
                f'<div><button class="btn" type="submit">Guardar</button></div></form></div>'
              + f'<div class="card" style="margin-top:24px"><div class="card-head"><div class="card-title">Contraseña</div></div>'
                f'<form method="post" action="/cuenta/contrasena" class="form">{V.csrf(token)}'
                f'{V.campo("actual", "Contraseña actual", "password", clase="campo", autocomplete="current-password")}'
                f'<div class="fila">{V.campo("nueva", "Nueva", "password", clase="campo", autocomplete="new-password", ayuda="Mínimo 10 caracteres")}'
                f'{V.campo("nueva2", "Repítala", "password", clase="campo", autocomplete="new-password")}</div>'
                f'<div><button class="btn" type="submit">Cambiar</button></div></form></div>'
              + f'<div class="card" style="margin-top:24px"><div class="card-head"><div class="card-title">Sesiones abiertas</div></div>'
                f'<table class="tabla"><tr><th>Último uso</th><th>IP</th><th>Navegador</th></tr>{filas}</table>'
                f'<form method="post" action="/cuenta/cerrar-otras" style="margin-top:14px">{V.csrf(token)}'
                f'<button class="btn peligro" type="submit">Cerrar las demás sesiones</button></form></div>')
    return V.privada("Cuenta", cuerpo, "/cuenta", usuario, empresa, token)


@router.post("/cuenta/nombre")
def nombre(request: Request, usuario: dict = Depends(sesiones.requiere_sesion), _: None = Depends(sesiones.csrf),
           nombre: str = Form("")):
    if len(nombre.strip()) < 2:
        return sesiones.redirigir("/cuenta?error=" + quote("Escriba un nombre."))
    cuentas.cambiar_nombre(usuario["id"], nombre.strip()[:120])
    return sesiones.redirigir("/cuenta?ok=" + quote("Nombre guardado."))


@router.post("/cuenta/contrasena")
def contrasena(request: Request, usuario: dict = Depends(sesiones.requiere_sesion), _: None = Depends(sesiones.csrf),
               actual: str = Form(""), nueva: str = Form(""), nueva2: str = Form("")):
    error = ("Las contraseñas nuevas no coinciden." if nueva != nueva2 else None) or seguridad.validar_contrasena(nueva, usuario["email"])
    if not error and not cuentas.cambiar_contrasena(usuario["id"], actual, nueva):
        error = "La contraseña actual no es correcta."
    if error:
        return sesiones.redirigir("/cuenta?error=" + quote(error))
    sesiones.cerrar_todas(usuario["id"], salvo=request.state.sesion["id"])
    return sesiones.redirigir("/cuenta?ok=" + quote("Contraseña cambiada; las demás sesiones se cerraron."))


@router.post("/cuenta/cerrar-otras")
def cerrar_otras(request: Request, usuario: dict = Depends(sesiones.requiere_sesion), _: None = Depends(sesiones.csrf)):
    n = sesiones.cerrar_todas(usuario["id"], salvo=request.state.sesion["id"])
    return sesiones.redirigir("/cuenta?ok=" + quote(f"{n} sesión(es) cerrada(s)."))
