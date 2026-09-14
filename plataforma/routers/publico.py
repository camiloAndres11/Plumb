"""Lo que se ve sin sesion: landing, registro, verificacion, login, logout,
olvide/restablecer, invitacion, terminos y privacidad.

Reglas que valen para todo el archivo:
  - Registro, "olvide" y reenvio responden IGUAL exista o no el correo.
  - Todo POST publico pasa por un rate limit por IP (y por email donde
    aplica); todo POST con sesion exige el campo csrf.
  - Los mensajes van en la query (?ok=/?error=) porque aqui no hay sesion.
"""
from __future__ import annotations

from urllib.parse import quote, urlparse

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from plataforma import cuentas, seguridad, sesiones
from plataforma import vistas as V
from plataforma.config import RAIZ

router = APIRouter()
LANDING = RAIZ / "plomada" / "landing.html"
BADGE = '<span class="ad-badge"><span class="ad-dot"></span>Para constructoras que licitan obra pública</span>'


def _ip(request: Request) -> str:
    return seguridad.ip_cliente(request)


def _siguiente(request: Request, valor: str | None) -> str:
    """Solo rutas internas: nunca un host ajeno."""
    v = valor or request.query_params.get("siguiente") or ""
    return v if v.startswith("/") and not v.startswith("//") and not urlparse(v).netloc else "/panel"


# ---------------------------------------------------------------- landing
@router.get("/", response_class=HTMLResponse)
def landing(request: Request):
    if sesiones.actual(request):
        return sesiones.redirigir("/panel")
    html = LANDING.read_text(encoding="utf-8")
    # La landing es la misma de la demo; aqui «Entrar» y «Empezar» llevan
    # al login y al registro reales.
    return (html.replace('href="/tablero/">Entrar', 'href="/login">Entrar')
                .replace('class="ad-nav-cta" href="#precios">Empezar', 'class="ad-nav-cta" href="/registro">Empezar')
                .replace('class="ad-btn" href="#precios">Probar 14 días gratis', 'class="ad-btn" href="/registro">Probar 14 días gratis'))


# --------------------------------------------------------------- registro
def _form_registro(valores: dict, error: str | None = None) -> str:
    return (f'<div>{BADGE}<h1>Cree la cuenta de su empresa.</h1>'
            f'<p class="sub">Usted queda como administrador y puede invitar a su equipo.</p></div>'
            f'{V.mensajes(error=error)}'
            f'<form method="post" action="/registro" class="lg-campos">'
            f'<div class="lg-fila">{V.campo("empresa", "Nombre de la empresa", valor=valores.get("empresa", ""), placeholder="Constructora Andina S.A.S.", autocomplete="organization")}'
            f'{V.campo("nit", "NIT", valor=valores.get("nit", ""), placeholder="900.123.456-7", ayuda="Con o sin dígito de verificación")}</div>'
            f'{V.campo("nombre", "Su nombre", valor=valores.get("nombre", ""), autocomplete="name")}'
            f'{V.campo("email", "Correo de trabajo", "email", valor=valores.get("email", ""), autocomplete="email")}'
            f'{V.campo("clave", "Contraseña", "password", autocomplete="new-password", ayuda="Mínimo 10 caracteres")}'
            f'<label class="lg-check"><input type="checkbox" name="acepta" value="1" required> Acepto los '
            f'<a href="/terminos" target="_blank">términos</a> y la <a href="/privacidad" target="_blank">política de privacidad</a>.</label>'
            f'<button class="ad-btn ad-btn-shadow" type="submit">Crear cuenta</button></form>'
            f'<div class="lg-links"><a href="/login">Ya tengo cuenta</a><a href="/">Volver</a></div>')


@router.get("/registro", response_class=HTMLResponse)
def registro(request: Request):
    if sesiones.actual(request):
        return sesiones.redirigir("/panel")
    return V.publica("Crear cuenta", _form_registro({}))


@router.post("/registro", response_class=HTMLResponse)
def registrar(request: Request, empresa: str = Form(""), nit: str = Form(""), nombre: str = Form(""),
              email: str = Form(""), clave: str = Form(""), acepta: str = Form("")):
    valores = {"empresa": empresa.strip()[:200], "nit": nit.strip()[:30], "nombre": nombre.strip()[:120], "email": email.strip()[:254]}
    if not seguridad.permitir("registro:ip:" + _ip(request), 5, 3600):
        return V.publica("Crear cuenta", _form_registro(valores, "Demasiados intentos desde esta red. Espere una hora."))
    e = seguridad.email_valido(email)
    n = seguridad.nit_valido(nit)
    error = (None if acepta == "1" else "Debe aceptar los términos.") \
        or (None if len(valores["empresa"]) >= 3 else "Escriba el nombre de la empresa.") \
        or (None if n else "El NIT no es válido (revise el dígito de verificación).") \
        or (None if len(valores["nombre"]) >= 2 else "Escriba su nombre.") \
        or (None if e else "El correo no es válido.") \
        or seguridad.validar_contrasena(clave, e or "")
    if error:
        return V.publica("Crear cuenta", _form_registro(valores, error))
    cuentas.registrar(valores["nombre"], e, clave, valores["empresa"], n)
    # Misma respuesta exista o no: no se revela que cuentas hay.
    return sesiones.redirigir("/verificar?enviado=" + quote(e))


# ------------------------------------------------------------ verificar
@router.get("/verificar", response_class=HTMLResponse)
def verificar_pendiente(request: Request, enviado: str = ""):
    usuario = sesiones.actual(request)
    if usuario and usuario.get("email_verificado"):
        return sesiones.redirigir("/panel")
    email = (usuario or {}).get("email") or enviado
    reenviar = ""
    if usuario:
        reenviar = (f'<form method="post" action="/verificar/reenviar">{V.csrf(sesiones.token_csrf(request))}'
                    f'<button class="ad-btn-ghost" type="submit">Reenviar el correo</button></form>')
    return V.publica("Revise su correo", (
        f'<div>{BADGE}<h1>Revise su correo.</h1>'
        f'<p class="sub">Si <b>{V.h(email)}</b> es una cuenta nueva, le enviamos un enlace para confirmarla. '
        f'Vale por 24 horas. Si no llega, mire la carpeta de spam.</p></div>'
        f'{V.mensajes(ok=request.query_params.get("ok"), error=request.query_params.get("error"))}{reenviar}'
        f'<div class="lg-links"><a href="/login">Ir al inicio de sesión</a><a href="/">Volver</a></div>'))


@router.post("/verificar/reenviar")
def reenviar(request: Request, _: None = Depends(sesiones.csrf)):
    usuario = sesiones.actual(request)
    if usuario and seguridad.permitir("reenviar:" + usuario["email"], 3, 3600):
        cuentas.reenviar_verificacion(usuario)
    return sesiones.redirigir("/verificar?ok=" + quote("Si la cuenta existe, el correo va en camino."))


@router.get("/verificar/{token}")
def verificar(request: Request, token: str):
    usuario = cuentas.verificar(token)
    if not usuario:
        return sesiones.redirigir("/login?error=" + quote("El enlace no es válido o ya venció. Pida uno nuevo al ingresar."))
    sid, _ = sesiones.crear(usuario["id"], request)
    respuesta = sesiones.redirigir("/empresa/perfil/1?ok=" + quote("Correo confirmado. Ahora cuéntenos de su empresa."))
    sesiones.poner_cookie(respuesta, sid, request)
    return respuesta


# ------------------------------------------------------------------ login
def _form_login(email: str = "", error: str | None = None, ok: str | None = None, siguiente: str = "",
                token: str = "") -> str:
    sig = f'<input type="hidden" name="siguiente" value="{V.h(siguiente)}">' if siguiente else ""
    return (f'<div>{BADGE}<h1>Ingrese a Pliego.</h1><p class="sub">Sus licitaciones de hoy, listas a las 6:00.</p></div>'
            f'{V.mensajes(ok=ok, error=error)}'
            f'<form method="post" action="/login" class="lg-campos">{sig}{V.csrf(token)}'
            f'{V.campo("email", "Correo", "email", valor=email, autocomplete="email")}'
            f'{V.campo("clave", "Contraseña", "password", autocomplete="current-password")}'
            f'<button class="ad-btn ad-btn-shadow" type="submit">Iniciar</button></form>'
            f'<div class="lg-links"><a href="/olvide">¿Olvidó su contraseña?</a><a href="/registro">Crear una cuenta</a></div>')


def _pagina_login(request: Request, **kw) -> HTMLResponse:
    token = sesiones.token_login(request)
    respuesta = HTMLResponse(V.publica("Ingresar", _form_login(token=token, **kw)))
    sesiones.poner_cookie_login(respuesta, token, request)
    return respuesta


@router.get("/login", response_class=HTMLResponse)
def login(request: Request):
    if sesiones.actual(request):
        return sesiones.redirigir("/panel")
    q = request.query_params
    return _pagina_login(request, error=q.get("error"), ok=q.get("ok"), siguiente=q.get("siguiente", ""))


@router.post("/login", response_class=HTMLResponse)
def iniciar(request: Request, _: None = Depends(sesiones.csrf_login), email: str = Form(""), clave: str = Form(""),
            siguiente: str = Form("")):
    e = seguridad.email_valido(email) or ""
    if not seguridad.permitir("login:ip:" + _ip(request), 10, 900) or (e and not seguridad.permitir("login:email:" + e, 5, 900)):
        return _pagina_login(request, email=email, error="Demasiados intentos. Espere 15 minutos.", siguiente=siguiente)
    usuario = cuentas.autenticar(e, clave) if e else None
    if not usuario:
        return _pagina_login(request, email=email, error="Correo o contraseña incorrectos.", siguiente=siguiente)
    sid, _ = sesiones.crear(usuario["id"], request)
    destino = "/verificar" if not usuario["email_verificado"] else _siguiente(request, siguiente)
    respuesta = sesiones.redirigir(destino)
    sesiones.poner_cookie(respuesta, sid, request)
    return respuesta


@router.post("/logout")
def salir(request: Request, _: None = Depends(sesiones.csrf)):
    sesion = request.state.sesion
    if sesion:
        sesiones.cerrar(sesion["id"])
    respuesta = sesiones.redirigir("/login?ok=" + quote("Sesión cerrada."))
    sesiones.quitar_cookie(respuesta, request)
    return respuesta


# ------------------------------------------------------------------ reset
@router.get("/olvide", response_class=HTMLResponse)
def olvide(request: Request):
    return V.publica("Recuperar contraseña", (
        f'<div>{BADGE}<h1>Recupere su contraseña.</h1><p class="sub">Le enviamos un enlace para elegir una nueva.</p></div>'
        f'{V.mensajes(ok=request.query_params.get("ok"))}'
        f'<form method="post" action="/olvide" class="lg-campos">{V.campo("email", "Correo", "email", autocomplete="email")}'
        f'<button class="ad-btn ad-btn-shadow" type="submit">Enviar enlace</button></form>'
        f'<div class="lg-links"><a href="/login">Volver al inicio de sesión</a></div>'))


@router.post("/olvide")
def pedir_reset(request: Request, email: str = Form("")):
    e = seguridad.email_valido(email)
    if e and seguridad.permitir("reset:ip:" + _ip(request), 10, 3600) and seguridad.permitir("reset:email:" + e, 3, 3600):
        cuentas.pedir_reset(e)
    return sesiones.redirigir("/olvide?ok=" + quote("Si el correo está registrado, el enlace va en camino."))


def _form_restablecer(token: str, error: str | None = None) -> str:
    return (f'<div>{BADGE}<h1>Elija una contraseña nueva.</h1></div>{V.mensajes(error=error)}'
            f'<form method="post" action="/restablecer/{V.h(token)}" class="lg-campos">'
            f'{V.campo("clave", "Contraseña nueva", "password", autocomplete="new-password", ayuda="Mínimo 10 caracteres")}'
            f'{V.campo("clave2", "Repítala", "password", autocomplete="new-password")}'
            f'<button class="ad-btn ad-btn-shadow" type="submit">Guardar</button></form>')


@router.get("/restablecer/{token}", response_class=HTMLResponse)
def restablecer(token: str):
    if not cuentas.leer_token(token, "reset"):
        return sesiones.redirigir("/olvide?ok=" + quote("Ese enlace ya no sirve. Pida uno nuevo."))
    return V.publica("Nueva contraseña", _form_restablecer(token))


@router.post("/restablecer/{token}", response_class=HTMLResponse)
def guardar_contrasena(request: Request, token: str, clave: str = Form(""), clave2: str = Form("")):
    t = cuentas.leer_token(token, "reset")
    if not t:
        return sesiones.redirigir("/olvide?ok=" + quote("Ese enlace ya no sirve. Pida uno nuevo."))
    u = cuentas.usuario_por_id(t["usuario_id"])
    error = ("Las contraseñas no coinciden." if clave != clave2 else None) or seguridad.validar_contrasena(clave, u["email"] if u else "")
    if error:
        return V.publica("Nueva contraseña", _form_restablecer(token, error))
    cuentas.restablecer(token, clave)
    return sesiones.redirigir("/login?ok=" + quote("Contraseña cambiada. Ingrese con la nueva."))


# ------------------------------------------------------------- invitacion
def _form_invitacion(token: str, t: dict, error: str | None = None) -> str:
    empresa = cuentas.empresa_por_id(t["empresa_id"]) or {}
    return (f'<div>{BADGE}<h1>Únase a {V.h(empresa.get("nombre", ""))}.</h1>'
            f'<p class="sub">Cree su usuario para <b>{V.h(t["email"])}</b> ({V.h(t["rol"])}).</p></div>{V.mensajes(error=error)}'
            f'<form method="post" action="/invitacion/{V.h(token)}" class="lg-campos">'
            f'{V.campo("nombre", "Su nombre", autocomplete="name")}'
            f'{V.campo("clave", "Contraseña", "password", autocomplete="new-password", ayuda="Mínimo 10 caracteres")}'
            f'<label class="lg-check"><input type="checkbox" name="acepta" value="1" required> Acepto los '
            f'<a href="/terminos" target="_blank">términos</a> y la <a href="/privacidad" target="_blank">política de privacidad</a>.</label>'
            f'<button class="ad-btn ad-btn-shadow" type="submit">Crear mi usuario</button></form>')


@router.get("/invitacion/{token}", response_class=HTMLResponse)
def invitacion(token: str):
    t = cuentas.leer_token(token, "invitacion")
    if not t:
        return sesiones.redirigir("/login?error=" + quote("La invitación no es válida o venció. Pida otra a su administrador."))
    return V.publica("Invitación", _form_invitacion(token, t))


@router.post("/invitacion/{token}", response_class=HTMLResponse)
def aceptar(request: Request, token: str, nombre: str = Form(""), clave: str = Form(""), acepta: str = Form("")):
    t = cuentas.leer_token(token, "invitacion")
    if not t:
        return sesiones.redirigir("/login?error=" + quote("La invitación no es válida o venció."))
    error = (None if acepta == "1" else "Debe aceptar los términos.") \
        or (None if len(nombre.strip()) >= 2 else "Escriba su nombre.") \
        or seguridad.validar_contrasena(clave, t["email"])
    if error:
        return V.publica("Invitación", _form_invitacion(token, t, error))
    usuario = cuentas.aceptar_invitacion(token, nombre.strip()[:120], clave)
    if not usuario:
        # Mismo mensaje que una invitacion vencida: no se revela que el correo ya es cuenta.
        return sesiones.redirigir("/login?error=" + quote("La invitación no es válida o venció. Si ya tiene cuenta, ingrese con ella."))
    sid, _ = sesiones.crear(usuario["id"], request)
    respuesta = sesiones.redirigir("/panel?ok=" + quote("Bienvenido. Ya hace parte del equipo."))
    sesiones.poner_cookie(respuesta, sid, request)
    return respuesta


# ---------------------------------------------------------- legales
TERMINOS = """<!-- REVISAR LEGAL: borrador; debe revisarlo un abogado antes de vender. -->
<p><b>1. Servicio.</b> Pliego ofrece análisis sobre datos públicos del SECOP para apoyar decisiones comerciales de empresas constructoras. Las recomendaciones son estimaciones y no garantizan la adjudicación de ningún proceso.</p>
<p><b>2. Cuenta.</b> La cuenta pertenece a la empresa identificada por su NIT. El administrador responde por los usuarios que invita.</p>
<p><b>3. Uso.</b> No se permite revender el acceso, extraer masivamente los datos ni usar el servicio para fines distintos a la actividad de la empresa.</p>
<p><b>4. Datos.</b> Los datos de procesos y contratos son públicos (SECOP) y se obtienen a través de proveedores de datos. La información que la empresa registra sobre sí misma es suya y puede pedir su eliminación.</p>
<p><b>5. Disponibilidad.</b> El servicio se presta como está; puede haber interrupciones por mantenimiento o por los proveedores de datos.</p>"""

PRIVACIDAD = """<!-- REVISAR LEGAL: borrador; debe adaptarse a la Ley 1581 de 2012 antes de vender. -->
<p><b>Qué guardamos.</b> Nombre, correo, contraseña (solo su hash), NIT y perfil de la empresa, direcciones IP y navegador de las sesiones, y los pliegos que la empresa suba.</p>
<p><b>Para qué.</b> Para prestar el servicio: identificar a la empresa, filtrar procesos según su perfil y enviarle los correos de la cuenta. No se venden ni se ceden a terceros.</p>
<p><b>Proveedores.</b> Los datos del SECOP llegan a través de proveedores de datos; los pliegos se procesan con un modelo de lenguaje para extraer requisitos. Ninguno recibe las credenciales de la empresa.</p>
<p><b>Sus derechos.</b> Puede consultar, corregir o pedir la eliminación de sus datos escribiendo al correo de soporte. Cerrar la cuenta borra usuarios, sesiones y pliegos.</p>"""


@router.get("/terminos", response_class=HTMLResponse)
def terminos():
    return V.publica("Términos", f'<div><h1>Términos del servicio</h1></div><div class="lg-texto">{TERMINOS}</div>', ancha=True)


@router.get("/privacidad", response_class=HTMLResponse)
def privacidad():
    return V.publica("Privacidad", f'<div><h1>Política de privacidad</h1></div><div class="lg-texto">{PRIVACIDAD}</div>', ancha=True)
