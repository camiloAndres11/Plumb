"""Lo que se ve sin sesion: landing, login, registro, verificacion, reset.

Fase 0: la landing y las pantallas vacias. Fase 1 les pone la logica.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from plataforma import vistas as V
from plataforma.config import RAIZ

router = APIRouter()
LANDING = RAIZ / "plomada" / "landing.html"


@router.get("/", response_class=HTMLResponse)
def landing():
    html = LANDING.read_text(encoding="utf-8")
    # La landing es la misma de la demo; aqui «Entrar» y «Empezar» llevan
    # al login y al registro reales.
    return (html.replace('href="/tablero/">Entrar', 'href="/login">Entrar')
                .replace('class="ad-nav-cta" href="#precios">Empezar', 'class="ad-nav-cta" href="/registro">Empezar')
                .replace('class="ad-btn" href="#precios">Probar 14 días gratis', 'class="ad-btn" href="/registro">Probar 14 días gratis'))


@router.get("/login", response_class=HTMLResponse)
def login():
    return V.publica("Ingresar", (
        '<div><span class="ad-badge"><span class="ad-dot"></span>Para constructoras que licitan obra pública</span>'
        '<h1>Ingrese a Pliego.</h1><p class="sub">El inicio de sesión llega en la fase 1.</p></div>'
        '<div class="lg-links"><a href="/registro">Crear una cuenta</a><a href="/">Volver</a></div>'))


@router.get("/registro", response_class=HTMLResponse)
def registro():
    return V.publica("Crear cuenta", (
        '<div><span class="ad-badge"><span class="ad-dot"></span>Para constructoras que licitan obra pública</span>'
        '<h1>Cree la cuenta de su empresa.</h1><p class="sub">El registro llega en la fase 1.</p></div>'
        '<div class="lg-links"><a href="/login">Ya tengo cuenta</a><a href="/">Volver</a></div>'))
