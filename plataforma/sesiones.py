"""Sesiones en servidor y lo que cuelga de ellas: cookie, CSRF, guardias.

La cookie `pliego_sesion` lleva SOLO el id de sesion, firmado
(itsdangerous); en pliego.sesiones esta su SHA-256 (seguridad.huella), con
quien es, cuando se uso y el token CSRF. request.state.sesion["id"] es el
id de la base (la huella). Eso permite listar y cerrar sesiones desde /cuenta y expirar
por inactividad (config.sesion_dias) sin tocar la cookie.

En la app:
    app.middleware("http")(cargar)            pone request.state.usuario / .empresa / .sesion
    usuario: dict = Depends(requiere_sesion)   redirige a /login si no hay
    _: None = Depends(csrf)                    exige el campo `csrf` en todo POST
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from fastapi import Form, Request
from fastapi.responses import RedirectResponse, Response

from plataforma import db, seguridad
from plataforma.config import config
from pliego.comun import contexto

COOKIE = "pliego_sesion"
COOKIE_LOGIN = "pliego_login"      # token de doble envio del formulario de login (sin sesion aun)
TOCAR_CADA = timedelta(minutes=5)


class Redirigir(Exception):
    """Un guardia decidio mandar al usuario a otra parte (login, wizard...)."""

    def __init__(self, url: str):
        super().__init__(url)
        self.url = url


class Prohibido(Exception):
    """403: sesion valida pero sin permiso (rol, CSRF)."""


# ------------------------------------------------------------------ crear
def crear(usuario_id: int, request: Request) -> tuple[str, str]:
    """Devuelve (id, csrf). El id va firmado en la cookie."""
    sid, csrf_token = seguridad.nuevo_token(), seguridad.nuevo_token()
    ip = seguridad.ip_cliente(request)
    db.ejecutar("INSERT INTO pliego.sesiones (id, usuario_id, csrf, ip, agente) VALUES (%s, %s, %s, %s, %s)",
                [seguridad.huella(sid), usuario_id, csrf_token, ip, (request.headers.get("user-agent") or "")[:300]])
    db.ejecutar("UPDATE pliego.usuarios SET ultimo_acceso = now() WHERE id = %s", [usuario_id])
    return sid, csrf_token


def _segura(request: Request | None) -> bool:
    """Secure si la peticion llego por https (uvicorn ya aplico
    X-Forwarded-Proto del proxy de confianza) o si BASE_URL lo es: un typo
    en BASE_URL no debe dejar la cookie viajando en claro."""
    return bool(request is not None and request.url.scheme == "https") or config.cookies_seguras


def poner_cookie(respuesta: Response, sid: str, request: Request | None = None) -> None:
    respuesta.set_cookie(COOKIE, seguridad.firmar(sid), max_age=config.sesion_dias * 86400,
                         httponly=True, samesite="lax", secure=_segura(request), path="/")


def quitar_cookie(respuesta: Response, request: Request | None = None) -> None:
    # Mismos atributos que al ponerla: si no coinciden, el navegador ignora
    # el borrado y la cookie sobrevive al logout.
    respuesta.delete_cookie(COOKIE, path="/", httponly=True, samesite="lax", secure=_segura(request))


# ------------------------------------------------------ csrf sin sesion
def token_login(request: Request) -> str:
    """El token del formulario de login: viaja en una cookie y en un campo
    oculto (doble envio). Sin esto un sitio ajeno podia iniciar sesion en
    la cuenta del atacante desde el navegador de la victima."""
    return request.cookies.get(COOKIE_LOGIN) or seguridad.nuevo_token()


def poner_cookie_login(respuesta: Response, token: str, request: Request | None = None) -> None:
    respuesta.set_cookie(COOKIE_LOGIN, token, max_age=3600, httponly=True, samesite="lax",
                         secure=_segura(request), path="/login")


def csrf_login(request: Request, csrf: str = Form("")) -> None:
    esperado = request.cookies.get(COOKIE_LOGIN, "")
    if not esperado or not csrf or not secrets.compare_digest(csrf, esperado):
        raise Prohibido("formulario vencido o manipulado: vuelva a cargar la página")


def cerrar(sid: str) -> None:
    db.ejecutar("DELETE FROM pliego.sesiones WHERE id = %s", [sid])


def cerrar_todas(usuario_id: int, salvo: str | None = None) -> int:
    if salvo:
        return db.ejecutar("DELETE FROM pliego.sesiones WHERE usuario_id = %s AND id <> %s", [usuario_id, salvo])
    return db.ejecutar("DELETE FROM pliego.sesiones WHERE usuario_id = %s", [usuario_id])


def listar(usuario_id: int) -> list[dict]:
    return db.todos("SELECT id, creada, ultimo_uso, ip, agente FROM pliego.sesiones WHERE usuario_id = %s "
                    "ORDER BY ultimo_uso DESC", [usuario_id])


# ------------------------------------------------------------------- leer
def _cargar_desde_cookie(request: Request) -> tuple[dict | None, dict | None, dict | None]:
    try:
        sid = seguridad.leer_firma(request.cookies.get(COOKIE), config.sesion_dias * 86400)
    except seguridad.SinSecreto:
        return None, None, None
    if not sid:
        return None, None, None
    sid = seguridad.huella(sid)
    fila = db.uno("""
        SELECT s.id AS sid, s.csrf, s.ultimo_uso, s.creada,
               u.id, u.empresa_id, u.email, u.nombre, u.rol, u.email_verificado, u.creado, u.pliego_actual,
               e.nit, e.nombre AS empresa_nombre, e.perfil, e.departamentos, e.perfil_completo
        FROM pliego.sesiones s
        JOIN pliego.usuarios u ON u.id = s.usuario_id
        JOIN pliego.empresas e ON e.id = u.empresa_id
        WHERE s.id = %s""", [sid])
    if not fila:
        return None, None, None
    limite = datetime.now(UTC) - timedelta(days=config.sesion_dias)
    # Vence por inactividad y tambien en absoluto (config.sesion_max_dias
    # desde que se creo): una sesion robada no vive para siempre solo
    # porque se siga usando.
    if fila["ultimo_uso"] < limite or fila["creada"] < datetime.now(UTC) - timedelta(days=config.sesion_max_dias):
        cerrar(sid)
        return None, None, None
    if datetime.now(UTC) - fila["ultimo_uso"] > TOCAR_CADA:
        db.ejecutar("UPDATE pliego.sesiones SET ultimo_uso = now() WHERE id = %s", [sid])
    usuario = {k: fila[k] for k in ("id", "empresa_id", "email", "nombre", "rol", "email_verificado", "creado", "pliego_actual")}
    empresa = {"id": fila["empresa_id"], "nit": fila["nit"], "nombre": fila["empresa_nombre"],
               "perfil": fila["perfil"] or {}, "departamentos": list(fila["departamentos"] or []),
               "perfil_completo": fila["perfil_completo"]}
    return usuario, empresa, {"id": sid, "csrf": fila["csrf"]}


async def cargar(request: Request, call_next):
    """Middleware: la sesion, si hay, queda en request.state. Nunca falla:
    sin base o sin secreto, simplemente no hay sesion."""
    usuario = empresa = sesion = None
    if COOKIE in request.cookies:
        try:
            usuario, empresa, sesion = _cargar_desde_cookie(request)
        except db.BaseNoDisponible:
            pass
    request.state.usuario, request.state.empresa, request.state.sesion = usuario, empresa, sesion
    # La empresa queda en contexto para los enfoques (pliego/comun/contexto.py)
    # mientras dura esta peticion; despues se limpia.
    token = None
    if empresa:
        perfil = _perfil_para_enfoques(empresa)
        token = contexto.set(empresa["id"], perfil, empresa["departamentos"], pliego=_pliego_elegido(usuario, empresa, perfil))
    try:
        respuesta = await call_next(request)
    finally:
        if token is not None:
            contexto.reset(token)
    if COOKIE in request.cookies and usuario is None and "set-cookie" not in respuesta.headers:
        quitar_cookie(respuesta, request)   # cookie huerfana (sesion cerrada o vencida)
    return respuesta


def _pliego_elegido(usuario: dict, empresa: dict, perfil: dict) -> dict | None:
    """El pliego con el que trabajan checklist y generador, si hay uno listo."""
    try:
        from plataforma import pliegos
        fila = pliegos.elegido_para(usuario, empresa)
        return pliegos.para_contexto(fila, perfil) if fila else None
    except db.BaseNoDisponible:
        return None


def _perfil_para_enfoques(empresa: dict) -> dict:
    """El JSONB mas nombre y NIT, con la forma de perfil_constructora.json."""
    return {**(empresa.get("perfil") or {}), "nombre": empresa["nombre"], "nit": empresa["nit"]}


# --------------------------------------------------------------- guardias
def actual(request: Request) -> dict | None:
    return getattr(request.state, "usuario", None)


def requiere_sesion(request: Request) -> dict:
    usuario = actual(request)
    if not usuario:
        destino = request.url.path + (("?" + request.url.query) if request.url.query else "")
        raise Redirigir("/login?siguiente=" + quote(destino, safe=""))
    if not usuario.get("email_verificado"):
        raise Redirigir("/verificar")
    return usuario


def requiere_admin(request: Request) -> dict:
    usuario = requiere_sesion(request)
    if usuario["rol"] != "admin":
        raise Prohibido("solo un administrador de la empresa puede hacer esto")
    return usuario


def csrf(request: Request, csrf: str = Form("")) -> None:
    sesion = getattr(request.state, "sesion", None)
    if not sesion or not csrf or not secrets.compare_digest(csrf, sesion["csrf"]):
        raise Prohibido("formulario vencido o manipulado: vuelva a cargar la página")


def reautenticar(request: Request, clave: str = Form("")) -> None:
    """Para lo que no se deshace facil (cambiar roles, quitar gente, borrar
    pliegos): el formulario trae la contrasena actual y se verifica de
    nuevo, aunque la sesion sea valida. Una sesion abierta en un equipo
    ajeno no basta."""
    from plataforma import cuentas
    usuario = actual(request)
    if not usuario or not clave or not cuentas.verificar_clave(usuario["id"], clave):
        raise Prohibido("confirme la acción con su contraseña actual")


def token_csrf(request: Request) -> str:
    sesion = getattr(request.state, "sesion", None)
    return sesion["csrf"] if sesion else ""


def redirigir(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)
