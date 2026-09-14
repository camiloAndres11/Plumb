"""Plantillas de la plataforma (Jinja2, autoescape), sobre el shell de los
enfoques (pliego/comun/web.py). Dos layouts:

  publica.html   la landing.css y la tarjeta centrada del login, para todo lo
                 que pasa antes de entrar (login, registro, verificar, olvide...)
  privada.html   el base.html de los enfoques con la sidebar de la plataforma

    return V.publica(request, "publico/login.html", "Ingresar", ...)
    return V.privada(request, "pliegos.html", "Pliegos", "/pliegos", usuario, empresa, token, ...)

Los mensajes flash viajan en la query (?ok=...&error=...) para no depender
de sesion en las pantallas publicas; en las privadas se usa igual por
uniformidad. `hub()` arma lo que los enfoques montados bajo /app/* usan
para mostrar la sidebar de la plataforma en vez de la suya.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Request
from markupsafe import Markup

from pliego.comun import web as W

h = W.h
templates = W.plantillas(Path(__file__).parent / "templates")

ITEMS_SIDEBAR = [
    ("/panel", "hoy", "Panel"),
    ("/app/filtro/", "filtro", "Filtro de procesos"),
    ("/app/simulador/", "grafico", "Simulador de oferta"),
    ("/app/radar/", "radar", "Radar de competidores"),
    ("/app/checklist/", "check", "Checklist del pliego"),
    ("/app/generador/", "doc", "Generador de propuesta"),
    ("/pliegos", "lista", "Pliegos"),
    ("/empresa/perfil/1", "perfil", "Empresa"),
    ("/empresa/documentos", "doc", "Documentos"),
]


def sidebar_items(actual: str, usuario: dict | None) -> list[dict]:
    from plataforma.config import config
    items = [{"href": ruta, "icono": ic, "texto": t, "on": actual.startswith(ruta.rstrip("/")) and ruta != "/"}
             for ruta, ic, t in ITEMS_SIDEBAR]
    if usuario and usuario.get("email", "").lower() in config.admins:
        items.append({"href": "/admin", "icono": "lista", "texto": "Admin", "on": actual.startswith("/admin")})
    return items


def publica(request: Request, plantilla: str, titulo: str, **ctx):
    return W.render(templates, request, plantilla, titulo=titulo, **ctx)


def privada(request: Request, plantilla: str, titulo: str, actual: str, usuario: dict | None, empresa: dict | None,
            csrf_token: str = "", **ctx):
    return W.render(templates, request, plantilla, titulo=titulo, actual=actual, usuario=usuario, empresa=empresa,
                    csrf_token=csrf_token, sidebar_items=sidebar_items(actual, usuario), **ctx)


def hub(ruta: str, usuario: dict | None, empresa: dict | None, csrf_token: str = "") -> dict:
    """Lo que base.html usa para pintar la sidebar de la plataforma dentro de
    un enfoque montado bajo /app/*."""
    pie = templates.env.get_template("_pie_sesion.html").render(usuario=usuario, empresa=empresa, csrf_token=csrf_token)
    return {"items": sidebar_items(ruta, usuario), "pie": Markup(pie)}
