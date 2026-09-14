"""Shell HTML de los prototipos: sidebar + panel, con la hoja base.

Render del lado del servidor con f-strings, sin plantillas ni bundler
(F4 lo pasa a Jinja2). Cada enfoque arma su cuerpo y lo pasa a pagina().
"""
from __future__ import annotations

import html
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "static"

ICONOS = {
    "hoy": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="4" width="18" height="18" rx="2"></rect><path d="M16 2v4M8 2v4M3 10h18"></path></svg>',
    "filtro": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M7 12h10M10 18h4"></path></svg>',
    "perfil": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle></svg>',
    "lista": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 4h16v16H4z"></path><path d="M8 12h8M8 8h8M8 16h5"></path></svg>',
    "grafico": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 3v18h18"></path><path d="m7 15 4-6 4 4 5-8"></path></svg>',
    "gente": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"></path></svg>',
    "doc": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><path d="M14 2v6h6M8 13h8M8 17h6"></path></svg>',
    "check": '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"><path d="M20 6 9 17l-5-5"></path></svg>',
}

LOGO = ('<a class="logo" href="/"><span class="logo-mark" aria-hidden="true">'
        '<span></span><span></span><span></span></span>Pliego.</a>')


_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\ufffd]")


def h(x) -> str:
    """Escapa y limpia: el SECOP trae caracteres de control sueltos en
    algunos nombres de entidad, que el navegador pinta como un rombo."""
    return html.escape(_CONTROL.sub(" ", str(x if x is not None else "")), quote=True)


def url_segura(u: str | None) -> str:
    """Para un href que viene de los datos (SECOP, Croma): solo http(s). Un
    `javascript:` en la fuente no debe convertirse en un enlace ejecutable."""
    u = (u or "").strip()
    return h(u) if u.lower().startswith(("http://", "https://")) else "#"


def frase(s: str | None) -> str:
    """Descripciones del SECOP, que suelen venir EN MAYUSCULAS: si mas del
    60 % de las letras son mayusculas se pasa a tipo oracion. Si no, se deja."""
    if not s:
        return ""
    letras = [c for c in s if c.isalpha()]
    if letras and sum(c.isupper() for c in letras) / len(letras) > 0.6:
        s = s.lower()
        return s[0].upper() + s[1:]
    return s


def mill(x) -> str:
    """$2.140 mill. / $1,2 mil mill., con separador de miles colombiano."""
    if x is None:
        return "sin dato"
    if abs(x) >= 1e9:
        return "$" + f"{x / 1e9:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + " mil mill."
    return "$" + f"{x / 1e6:,.0f}".replace(",", ".") + " mill."


def entero(x) -> str:
    return "sin dato" if x is None else f"{int(round(x)):,}".replace(",", ".")


def pct(x, dec=0) -> str:
    return "sin dato" if x is None else (f"{100 * x:.{dec}f}".replace(".", ",") + " %")


def titulo_caso(s: str | None) -> str:
    """'MUNICIPIO DE SAN VICENTE DE CHUCURI' -> 'Municipio de San Vicente de Chucurí'
    (sin tildes: no las tiene la fuente). Solo para leer mejor."""
    if not s:
        return ""
    chicas = {"de", "del", "la", "las", "los", "el", "y", "e", "en", "para", "por", "a", "al"}
    out = []
    for i, w in enumerate(s.lower().split()):
        siglas = {"sena", "esp", "e.s.p.", "e.s.p", "i.e.", "i.e", "i.e.m.", "sas", "s.a.s.", "s.a.s", "s.a.", "s.a", "sa",
                  "ltda", "ltda.", "bic", "e.s.e", "e.s.e.", "ese", "cvc", "eici", "cenac", "invias", "ani", "idu", "ut", "u.t."}
        out.append(w if (w in chicas and i) else (w.upper() if w in siglas else w.capitalize()))
    return " ".join(out)


def sidebar(items: list[tuple[str, str, str]], actual: str, pie: str = "") -> str:
    """items: (ruta, icono, texto)."""
    lis = "".join(
        f'<a class="side-item{" on" if actual == ruta else ""}" href="{h(ruta)}">{ICONOS[ic]}{h(t)}</a>'
        for ruta, ic, t in items)
    return f'<aside class="side">{LOGO}{lis}{pie}</aside>'


def pagina(titulo: str, cuerpo: str, side: str, extra_head: str = "", js: str = "") -> str:
    return f"""<!doctype html>
<html lang="es">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{h(titulo)} — Pliego</title>
<meta name="theme-color" content="#0b0b0d">
<link rel="stylesheet" href="/static/base.css">
{extra_head}
<body>
<div class="app">
{side}
<main class="main">
{cuerpo}
</main>
</div>
{js}
"""
