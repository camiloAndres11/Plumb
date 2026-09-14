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
    q = request.query_params
    return V.privada(request, "cuenta.html", "Cuenta", "/cuenta", usuario, empresa, token, ok=q.get("ok"), error=q.get("error"),
                     sesiones_abiertas=sesiones.listar(usuario["id"]), sesion_id=sesion["id"])


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
