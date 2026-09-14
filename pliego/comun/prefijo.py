"""Montar las apps de los enfoques bajo un prefijo sin tocarlas.

Cada app de pliego/<enfoque>/app.py nacio para correr sola en su puerto y
enlaza con rutas absolutas (/proceso/..., /static/...). Cuando un
concentrador (la demo en /filtro, la plataforma en /app/filtro) la monta
bajo un prefijo, `ConPrefijo` reescribe esas URLs en el HTML que devuelve y
en las redirecciones. Truco de integracion, no de produccion: si algun dia
las apps reciben `root_path`, esto sobra.

Ademas puede cambiar la sidebar de la app por la del concentrador
(`sidebar=` una funcion scope -> html), para que dentro de la plataforma
cada enfoque muestre el menu de la plataforma y no el suyo.
"""
from __future__ import annotations

import re
from collections.abc import Callable

from pliego.comun import web as W

# Rutas del concentrador que las apps montadas pueden enlazar sin que se
# les anteponga el prefijo.
RUTAS_HUB_DEMO = ("/panel", "/login", "/salir", "/#")
_ASIDE = re.compile(r'<aside class="side">.*?</aside>', re.S)


class ConPrefijo:
    _ATTR = re.compile(r'((?:href|src|action)=")/(?!/)')
    _JS = re.compile(r"""((?:fetch|open)\(\s*['"])/(?!/)""")
    _JS_STR = re.compile(r"""(['"])/(proceso|documento|requisito|entidad|competidor|api|pliego\.pdf|paquete\.zip)""")

    def __init__(self, app, prefijo: str, rutas_hub: tuple[str, ...] = RUTAS_HUB_DEMO,
                 sidebar: Callable[[dict], str] | None = None):
        self.app, self.prefijo, self.rutas_hub, self.sidebar = app, prefijo, rutas_hub, sidebar

    def _reescribir(self, html: str, scope: dict) -> str:
        def attr(m):
            resto = html_resto = m.string[m.end() - 1:m.end() + 8]
            return m.group(0) if resto.startswith(self.rutas_hub) or html_resto.startswith(self.prefijo + "/") else m.group(1) + self.prefijo + "/"
        if self.sidebar is not None:
            # La sidebar del concentrador ya trae rutas absolutas suyas:
            # se pone DESPUES de reescribir para que no le anteponga el prefijo.
            html = _ASIDE.sub("__SIDEBAR__", html, count=1)
        html = self._ATTR.sub(attr, html)
        html = self._JS.sub(lambda m: m.group(1) + self.prefijo + "/", html)
        html = self._JS_STR.sub(lambda m: m.group(1) + self.prefijo + "/" + m.group(2), html)
        if self.sidebar is not None:
            html = html.replace("__SIDEBAR__", self.sidebar(scope), 1)
        return html

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        partes: list[bytes] = []
        cabecera = {}

        async def send_(msg):
            if msg["type"] == "http.response.start":
                # Redirecciones absolutas (p. ej. / -> /proceso/x) tambien llevan prefijo.
                headers = []
                for k, v in msg.get("headers", []):
                    if k == b"location" and v.startswith(b"/") and not v.startswith(b"//") \
                            and not v.decode().startswith(self.rutas_hub) and not v.startswith(self.prefijo.encode() + b"/"):
                        v = self.prefijo.encode() + v
                    headers.append((k, v))
                msg = {**msg, "headers": headers}
                cabecera.update(msg)
                ct = dict(headers).get(b"content-type", b"")
                cabecera["html"] = b"text/html" in ct
                if not cabecera["html"]:
                    await send(msg)
                return
            if msg["type"] == "http.response.body":
                if not cabecera.get("html"):
                    await send(msg)
                    return
                partes.append(msg.get("body", b""))
                if msg.get("more_body"):
                    return
                cuerpo = self._reescribir(b"".join(partes).decode("utf-8", "replace"), scope).encode("utf-8")
                headers = [(k, v) for k, v in cabecera["headers"] if k != b"content-length"]
                headers.append((b"content-length", str(len(cuerpo)).encode()))
                await send({**cabecera, "headers": headers, "type": "http.response.start"})
                await send({"type": "http.response.body", "body": cuerpo})
                return
            await send(msg)

        await self.app(scope, receive, send_)


def sidebar_con_hub(hub: str = "/panel") -> None:
    """Parche global para la demo: a la sidebar de cada app le agrega un
    enlace al panel del concentrador, justo despues del logo. La plataforma
    no lo usa: reemplaza la sidebar entera con ConPrefijo(sidebar=...)."""
    if getattr(W.sidebar, "_con_hub", False):
        return
    original = W.sidebar

    def sidebar(items, actual, pie=""):
        html = original(items, actual, pie)
        volver = (f'<a class="side-item" href="{hub}" style="margin-bottom:6px;color:var(--ad-ink-55)">'
                  '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M19 12H5M12 19l-7-7 7-7"></path></svg>Panel</a>')
        return html.replace("</a>", "</a>" + volver, 1)
    sidebar._con_hub = True
    W.sidebar = sidebar
