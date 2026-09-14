"""Shell HTML de los enfoques: plantillas Jinja2 con autoescape.

    templates = W.plantillas(Path(__file__).parent / "templates")
    return W.render(templates, request, "filtro/lista.html", titulo="...", items=ITEMS, actual="/", ...)

Cada enfoque tiene sus plantillas en pliego/<enfoque>/templates/ y extiende
`base.html` (aqui, en pliego/comun/templates/): sidebar + main, la hoja
base y las de cada enfoque. Las URLs se arman con `raiz` (el root_path de
la peticion), asi la misma app sirve suelta en su puerto, montada en la
demo (/filtro) o en la plataforma (/app/filtro) sin reescribir HTML.

Un concentrador (demo, plataforma) puede poner en request.state.hub un
dict con `volver` (ruta, texto), `items` (lista de dicts href/icono/texto/on)
y/o `pie` (Markup): base.html lo usa para cambiar la sidebar de la app por
la suya.

Los filtros (mill, entero, pct, frase, titulo_caso, url_segura) son las
funciones de formato de siempre; `h()` sigue existiendo para los pocos
sitios que arman HTML fuera de plantillas.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from fastapi import Request
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup
from starlette.templating import Jinja2Templates

STATIC = Path(__file__).resolve().parents[1] / "static"
TEMPLATES = Path(__file__).resolve().parent / "templates"

ICONOS = {
    "hoy": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="4" width="18" height="18" rx="2"></rect><path d="M16 2v4M8 2v4M3 10h18"></path></svg>',
    "filtro": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M7 12h10M10 18h4"></path></svg>',
    "perfil": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle></svg>',
    "lista": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 4h16v16H4z"></path><path d="M8 12h8M8 8h8M8 16h5"></path></svg>',
    "grafico": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 3v18h18"></path><path d="m7 15 4-6 4 4 5-8"></path></svg>',
    "gente": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"></path></svg>',
    "doc": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><path d="M14 2v6h6M8 13h8M8 17h6"></path></svg>',
    "check": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 11l3 3L22 4"></path><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>',
    "radar": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"></circle><circle cx="12" cy="12" r="4"></circle><path d="M12 3v3M12 18v3M3 12h3M18 12h3"></path></svg>',
    "entidad": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 21h18M5 21V7l7-4 7 4v14M9 21v-6h6v6"></path></svg>',
    "volver": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M19 12H5M12 19l-7-7 7-7"></path></svg>',
    "no": '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#ff8a72" stroke-width="3" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"></path></svg>',
    "lupa": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.3-4.3"></path></svg>',
}
ICONOS = {k: Markup(v) for k, v in ICONOS.items()}

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


def num1(x) -> str:
    """Un decimal con coma: 57,3."""
    return f"{x:.1f}".replace(".", ",")


def coma(x) -> str:
    """Un numero tal cual pero con coma decimal: 1.8 -> 1,8."""
    return str(x).replace(".", ",")


# ------------------------------------------------------------- plantillas
FILTROS = {"mill": mill, "entero": entero, "pct": pct, "frase": frase, "titulo_caso": titulo_caso,
           "url_segura": url_segura, "num1": num1, "coma": coma}


def _contexto(request: Request) -> dict:
    return {"raiz": request.scope.get("root_path", ""), "hub": getattr(request.state, "hub", None)}


def plantillas(*carpetas: Path) -> Jinja2Templates:
    """Un entorno Jinja2 con autoescape para `carpetas` mas las comunes."""
    env = Environment(loader=FileSystemLoader([str(c) for c in carpetas] + [str(TEMPLATES)]),
                      autoescape=True, trim_blocks=True, lstrip_blocks=True)
    env.filters.update(FILTROS)
    env.globals.update(iconos=ICONOS, LOGO=Markup(LOGO))
    return Jinja2Templates(env=env, context_processors=[_contexto])


def render(templates: Jinja2Templates, request: Request, plantilla: str, **contexto):
    return templates.TemplateResponse(request, plantilla, contexto)


class Estaticos(StaticFiles):
    """/static desde varias carpetas (la primera gana). La plataforma y la
    demo sirven su landing y el shell de los enfoques por la misma ruta."""

    def __init__(self, *carpetas: Path):
        self._carpetas = [str(c) for c in carpetas]
        super().__init__(directory=self._carpetas[0])

    def get_directories(self, directory=None, packages=None):
        return list(self._carpetas)
