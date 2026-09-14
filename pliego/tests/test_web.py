"""El shell HTML de los enfoques (pliego/comun/web.py + plantillas): cada
ruta GET responde, las URLs llevan el prefijo cuando la app va montada, el
autoescape corta el XSS y no hay scripts inline (el CSP de la plataforma
solo permite /static)."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pliego.checklist.app import app as checklist
from pliego.filtro import datos as filtro_datos
from pliego.filtro.app import app as filtro
from pliego.generador.app import app as generador
from pliego.radar import datos as radar_datos
from pliego.radar.app import app as radar
from pliego.simulador import datos as simulador_datos
from pliego.simulador.app import app as simulador

RUTAS = {
    "filtro": ["/", "/?recomendacion=presentarse", "/perfil", lambda: "/proceso/" + filtro_datos.evaluaciones()[0]["id_del_proceso"]],
    "checklist": ["/", "/?lote=2", "/carpeta", "/requisito/carta?lote=1"],
    "simulador": ["/backtest", lambda: "/proceso/" + simulador_datos.abiertos()[0]["id_del_proceso"]],
    "radar": ["/", "/entidades", "/competidores", lambda: "/proceso/" + radar_datos.abiertos()[0]["id_del_proceso"],
              lambda: "/entidad/" + radar_datos.entidades_mas_activas(1)[0]["nit"],
              lambda: "/competidor/" + radar_datos.competidores_mas_activos(1)[0]["doc"]],
    "generador": ["/", "/?lote=2", "/perfil", "/documento/formato1?lote=1"],
}
APPS = {"filtro": filtro, "checklist": checklist, "simulador": simulador, "radar": radar, "generador": generador}


def _rutas(nombre):
    return [r() if callable(r) else r for r in RUTAS[nombre]]


@pytest.mark.parametrize("nombre", list(APPS))
def test_cada_pagina_responde_sin_scripts_inline(nombre):
    with TestClient(APPS[nombre]) as c:
        for ruta in _rutas(nombre):
            r = c.get(ruta)
            assert r.status_code == 200, (nombre, ruta, r.status_code)
            assert "<script>" not in r.text and "onsubmit=" not in r.text and "onclick=" not in r.text, (nombre, ruta)
            assert '<link rel="stylesheet" href="/static/base.css">' in r.text


@pytest.mark.parametrize("nombre", list(APPS))
def test_montada_bajo_un_prefijo_las_urls_llevan_el_prefijo(nombre):
    hub = FastAPI()
    hub.mount(f"/app/{nombre}", APPS[nombre])
    with TestClient(hub, follow_redirects=False) as c:
        for ruta in _rutas(nombre):
            r = c.get(f"/app/{nombre}{ruta}")
            assert r.status_code == 200, (nombre, ruta, r.status_code)
            t = r.text
            assert f'href="/app/{nombre}/static/base.css"' in t
            assert f'data-raiz="/app/{nombre}"' in t
            # ningun enlace ni recurso propio se escapa del prefijo
            for pat in ('href="/proceso/', 'href="/static/', 'src="/static/', 'href="/requisito/', 'href="/documento/',
                        'href="/entidad/', 'href="/competidor/', 'href="/perfil"', 'href="/carpeta"', 'href="/backtest"'):
                assert pat not in t, (nombre, ruta, pat)
        if nombre == "simulador":
            assert c.get(f"/app/{nombre}/").headers["location"].startswith(f"/app/{nombre}/proceso/")


def test_el_autoescape_corta_el_xss(monkeypatch):
    malo = [{"doc": "900000001", "nombre": '<script>alert(1)</script><img src=x onerror=alert(2)>', "n": 3}]
    monkeypatch.setattr(radar_datos, "competidores_mas_activos", lambda n=40: malo)
    with TestClient(radar) as c:
        t = c.get("/competidores").text
    assert "<script>alert(1)</script>" not in t and "onerror=" not in t
    assert "&lt;script&gt;" in t
