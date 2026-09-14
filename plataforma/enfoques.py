"""Los enfoques dentro de la plataforma: montados bajo /app/<enfoque>.

Cada app de pliego/<enfoque>/app.py se monta tal cual con ConPrefijo (que
reescribe sus URLs y cambia su sidebar por la de la plataforma) y detras
de `Protegido`, un guardia ASGI que exige sesion verificada, perfil
completo y al menos un departamento con datos. Sin eso redirige a donde
toca. El contexto de empresa (pliego/comun/contexto.py) ya lo fijo el
middleware de sesiones, asi que los datos.py sirven lo de la empresa.
"""
from __future__ import annotations

from urllib.parse import quote

from plataforma import vistas as V
from pliego.comun import contexto, warehouse
from pliego.comun.prefijo import ConPrefijo

# Rutas de la plataforma que las apps montadas pueden enlazar tal cual.
RUTAS_HUB = ("/panel", "/login", "/logout", "/empresa", "/cuenta", "/pliegos", "/app/", "/#")
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
        estado = scope.get("state") or {}
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
        return await self.app(scope, receive, send)


def _sidebar(scope: dict) -> str:
    estado = scope.get("state") or {}
    ruta = scope.get("root_path", "") + scope.get("path", "")
    sesion = estado.get("sesion") or {}
    return V.sidebar(ruta, estado.get("usuario"), estado.get("empresa"), sesion.get("csrf", ""))


def montar(app) -> None:
    from pliego.checklist.app import app as checklist_app
    from pliego.filtro.app import app as filtro_app
    from pliego.generador.app import app as generador_app
    from pliego.radar.app import app as radar_app
    from pliego.simulador.app import app as simulador_app
    for nombre, sub in (("filtro", filtro_app), ("simulador", simulador_app), ("radar", radar_app),
                        ("checklist", checklist_app), ("generador", generador_app)):
        prefijo = f"/app/{nombre}"
        app.mount(prefijo, Protegido(ConPrefijo(sub, prefijo, rutas_hub=RUTAS_HUB, sidebar=_sidebar),
                                     requiere_pliego=nombre in CON_PLIEGO))
