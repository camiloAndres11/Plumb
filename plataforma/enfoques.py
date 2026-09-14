"""Los enfoques dentro de la plataforma: montados bajo /app/<enfoque>.

Cada app de pliego/<enfoque>/app.py se monta tal cual con app.mount (sus
plantillas arman las URLs con el root_path, asi que no hay que reescribir
HTML) detras de `Protegido`, un guardia ASGI que exige sesion verificada,
perfil completo y al menos un departamento con datos. Sin eso redirige a
donde toca. El guardia deja ademas en request.state.hub la sidebar de la
plataforma, que base.html pinta en vez de la de la app. El contexto de
empresa (pliego/comun/contexto.py) ya lo fijo el middleware de sesiones,
asi que los datos.py sirven lo de la empresa.
"""
from __future__ import annotations

from urllib.parse import quote

from plataforma import vistas as V
from pliego.comun import contexto, warehouse

ACTIVOS = ("filtro", "simulador", "radar")           # siempre, con datos del departamento
CON_PLIEGO = ("checklist", "generador")              # solo con un pliego extraido


def datos_listos(ambito: tuple[str, ...]) -> bool:
    try:
        return bool(warehouse.estado(ambito)["departamentos"])
    except Exception:
        return False


def _redirigir(send, url: str):
    async def _():
        await send({"type": "http.response.start", "status": 303,
                    "headers": [(b"location", url.encode()), (b"content-length", b"0")]})
        await send({"type": "http.response.body", "body": b""})
    return _()


class Protegido:
    def __init__(self, app, requiere_pliego: bool = False):
        self.app, self.requiere_pliego = app, requiere_pliego

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        estado = scope.setdefault("state", {})
        usuario, empresa = estado.get("usuario"), estado.get("empresa")
        ruta = scope.get("root_path", "") + scope.get("path", "")
        if not usuario:
            return await _redirigir(send, "/login?siguiente=" + quote(ruta, safe=""))
        if not usuario.get("email_verificado"):
            return await _redirigir(send, "/verificar")
        if not empresa or not empresa.get("perfil_completo"):
            return await _redirigir(send, "/empresa/perfil/1?error=" + quote("Complete el perfil de la empresa para usar los enfoques."))
        if self.requiere_pliego:
            e = contexto.get()
            if not (e and e.pliego):
                return await _redirigir(send, "/pliegos?error=" + quote("Suba un pliego y espere a que esté listo para usar este enfoque."))
        elif not datos_listos(contexto.ambito()):
            return await _redirigir(send, "/empresa/datos?error=" + quote("Los datos de sus departamentos todavía se están preparando."))
        sesion = estado.get("sesion") or {}
        estado["hub"] = V.hub(ruta, usuario, empresa, sesion.get("csrf", ""))
        return await self.app(scope, receive, send)


def montar(app) -> None:
    from pliego.checklist.app import app as checklist_app
    from pliego.filtro.app import app as filtro_app
    from pliego.generador.app import app as generador_app
    from pliego.radar.app import app as radar_app
    from pliego.simulador.app import app as simulador_app
    for nombre, sub in (("filtro", filtro_app), ("simulador", simulador_app), ("radar", radar_app),
                        ("checklist", checklist_app), ("generador", generador_app)):
        app.mount(f"/app/{nombre}", Protegido(sub, requiere_pliego=nombre in CON_PLIEGO))
