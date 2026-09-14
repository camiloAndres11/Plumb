"""HTML de la plataforma: dos layouts y los helpers de formulario.

Render del lado del servidor con f-strings, como pliego/comun/web.py y
demo/app.py (sin motor de plantillas). Dos layouts:

  publica(titulo, tarjeta)   la landing.css y la tarjeta centrada del login
                             de la demo, para todo lo que pasa antes de
                             entrar (login, registro, verificar, olvide...)
  privada(titulo, cuerpo, actual, usuario, ...)
                             el shell sidebar + panel de pliego/comun/web.py,
                             con las rutas de la plataforma en la sidebar

Los mensajes flash viajan en la query (?ok=...&error=...) para no depender
de sesion en las pantallas publicas; en las privadas se usa igual por
uniformidad.
"""
from __future__ import annotations

from pliego.comun import panel as _panel  # noqa: F401  (registra los iconos check/radar)
from pliego.comun import web as W

h = W.h

# La tarjeta del login de la demo (demo/app.py LOGIN_CSS), mas lo que las
# pantallas de registro y perfil necesitan (selects, textarea, mensajes).
CSS_PUBLICA = """
.lg { position: relative; min-height: 100vh; overflow: hidden; display: grid; grid-template-rows: auto 1fr auto; }
.lg-nav { position: relative; z-index: 2; display: flex; align-items: center; justify-content: space-between; max-width: var(--ad-max); width: 100%; margin: 0 auto; padding: 22px var(--ad-gutter); }
.lg-nav a:last-child { font-size: 15px; color: var(--ad-ink-80); }
.lg-centro { position: relative; z-index: 2; display: grid; place-items: center; padding: 24px var(--ad-gutter); }
.lg-card { width: min(480px, 100%); padding: 36px; border-radius: 22px; background: var(--ad-glass); border: 1px solid var(--ad-line); box-shadow: var(--ad-shadow); display: flex; flex-direction: column; gap: 22px; animation: adRise .9s var(--ad-ease) both; }
.lg-card.ancha { width: min(720px, 100%); }
.lg-card h1 { font-size: 30px; line-height: 1.1; letter-spacing: -.03em; font-weight: 500; margin-top: 18px; }
.lg-card .sub { font-size: 15px; color: var(--ad-ink-60); margin-top: 8px; }
.lg-campos { display: flex; flex-direction: column; gap: 14px; }
.lg-fila { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 560px) { .lg-fila { grid-template-columns: 1fr; } }
.lg-campo { display: flex; flex-direction: column; gap: 8px; font-size: 13px; color: var(--ad-ink-60); }
.lg-campo input, .lg-campo select, .lg-campo textarea { padding: 14px 16px; border-radius: 12px; background: var(--ad-fill-3); border: 1px solid var(--ad-line); font: inherit; font-size: 15px; color: var(--ad-ink); outline: 0; }
.lg-campo input:focus, .lg-campo select:focus, .lg-campo textarea:focus { border-color: var(--ad-line-3); }
.lg-campo small { color: var(--ad-ink-35); }
.lg-check { display: flex; gap: 10px; align-items: flex-start; font-size: 13px; color: var(--ad-ink-60); }
.lg-check input { margin-top: 3px; }
.lg-links { display: flex; justify-content: space-between; font-size: 13px; }
.lg-links a { color: var(--ad-ink-70); }
.lg-pie { position: relative; z-index: 2; text-align: center; font-size: 12px; color: var(--ad-ink-35); padding: 24px; }
.lg-msg { padding: 12px 16px; border-radius: 12px; font-size: 14px; border: 1px solid var(--ad-line); }
.lg-msg.ok { background: rgba(80, 200, 120, .12); color: #9fe3b5; }
.lg-msg.error { background: rgba(255, 90, 60, .12); color: #ffb3a3; }
.lg-texto p { font-size: 14px; color: var(--ad-ink-70); line-height: 1.6; margin: 0 0 12px; }
"""

# Anadidos al shell privado (base.css de pliego/static): formularios,
# tablas y mensajes con el mismo lenguaje visual que los enfoques.
CSS_PRIVADA = """
.form { display: flex; flex-direction: column; gap: 16px; max-width: 720px; }
.form .fila { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 720px) { .form .fila { grid-template-columns: 1fr; } }
.campo { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--ink-60, #9a9aa3); }
.campo input, .campo select, .campo textarea { padding: 12px 14px; border-radius: 10px; background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.1); font: inherit; font-size: 14px; color: inherit; outline: 0; }
.campo input:focus, .campo select:focus, .campo textarea:focus { border-color: rgba(255,255,255,.3); }
.campo small { color: rgba(255,255,255,.35); }
.msg { padding: 12px 16px; border-radius: 12px; font-size: 14px; border: 1px solid rgba(255,255,255,.1); margin-bottom: 16px; }
.msg.ok { background: rgba(80, 200, 120, .12); color: #9fe3b5; }
.msg.error { background: rgba(255, 90, 60, .12); color: #ffb3a3; }
.btn { display: inline-flex; align-items: center; gap: 8px; padding: 12px 18px; border-radius: 12px; border: 1px solid rgba(255,255,255,.14); background: rgba(255,255,255,.08); color: inherit; font: inherit; font-size: 14px; cursor: pointer; text-decoration: none; }
.btn.hot { background: var(--acento, #ff6a3d); border-color: transparent; color: #fff; }
.btn.peligro { color: #ffb3a3; }
.tabla { width: 100%; border-collapse: collapse; font-size: 14px; }
.tabla th, .tabla td { text-align: left; padding: 10px 12px; border-bottom: 1px solid rgba(255,255,255,.08); vertical-align: top; }
.tabla th { font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: rgba(255,255,255,.45); font-weight: 500; }
.pasos { display: flex; gap: 10px; font-size: 13px; color: rgba(255,255,255,.45); margin-bottom: 18px; }
.pasos .on { color: inherit; font-weight: 500; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { display: inline-flex; align-items: center; gap: 6px; padding: 6px 10px; border-radius: 999px; background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.1); font-size: 13px; }
.chip button { background: none; border: 0; color: inherit; cursor: pointer; font-size: 14px; line-height: 1; padding: 0; }
.estado { display: inline-block; padding: 3px 9px; border-radius: 999px; font-size: 12px; background: rgba(255,255,255,.08); }
.estado.lista { background: rgba(80,200,120,.15); color: #9fe3b5; }
.estado.error { background: rgba(255,90,60,.15); color: #ffb3a3; }
.estado.descargando, .estado.pendiente { background: rgba(255,190,60,.15); color: #ffd58a; }
"""

LOGO_PUBLICO = ('<a class="ad-logo" href="/"><span class="ad-logo-mark" aria-hidden="true">'
                '<span></span><span></span><span></span></span>Pliego.</a>')


def mensajes(ok: str | None = None, error: str | None = None, clase: str = "lg-msg") -> str:
    out = ""
    if ok:
        out += f'<div class="{clase} ok">{h(ok)}</div>'
    if error:
        out += f'<div class="{clase} error">{h(error)}</div>'
    return out


def campo(nombre: str, etiqueta: str, tipo: str = "text", valor="", *, requerido: bool = True,
          placeholder: str = "", ayuda: str = "", autocomplete: str = "", extra: str = "",
          clase: str = "lg-campo") -> str:
    ayuda_html = f"<small>{h(ayuda)}</small>" if ayuda else ""
    ac = f' autocomplete="{h(autocomplete)}"' if autocomplete else ""
    return (f'<label class="{clase}">{h(etiqueta)}<input type="{tipo}" name="{h(nombre)}" value="{h(valor)}" '
            f'placeholder="{h(placeholder)}"{" required" if requerido else ""}{ac} {extra}>{ayuda_html}</label>')


def csrf(token: str) -> str:
    return f'<input type="hidden" name="csrf" value="{h(token)}">'


def publica(titulo: str, tarjeta: str, pie: str = "", ancha: bool = False, volver: str = "/",
            volver_texto: str = "← Volver a la landing") -> str:
    return f"""<!doctype html>
<html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{h(titulo)} — Pliego</title><meta name="theme-color" content="#0b0b0d">
<link rel="icon" type="image/png" href="/static/favicon-32.png" sizes="32x32">
<link rel="stylesheet" href="/static/landing.css">
<style>{CSS_PUBLICA}</style>
<body>
<div class="lg">
  <div class="ad-hero-bg" aria-hidden="true"></div><div class="ad-glow-a" aria-hidden="true"></div><div class="ad-glow-b" aria-hidden="true"></div>
  <header class="lg-nav">{LOGO_PUBLICO}<a href="{h(volver)}">{h(volver_texto)}</a></header>
  <main class="lg-centro"><div class="lg-card{' ancha' if ancha else ''}">{tarjeta}</div></main>
  <p class="lg-pie">{pie or 'Pliego · datos públicos del SECOP II. Las recomendaciones son estimaciones; no garantizan un resultado.'}</p>
</div>
"""


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


def sidebar(actual: str, usuario: dict | None, empresa: dict | None, csrf_token: str = "") -> str:
    lis = "".join(
        f'<a class="side-item{" on" if actual.startswith(ruta.rstrip("/")) and ruta != "/" else ""}" href="{h(ruta)}">'
        f'{W.ICONOS.get(ic, "")}{h(t)}</a>' for ruta, ic, t in ITEMS_SIDEBAR)
    from plataforma.config import config
    if usuario and usuario.get("email", "").lower() in config.admins:
        lis += f'<a class="side-item{" on" if actual.startswith("/admin") else ""}" href="/admin">{W.ICONOS.get("lista", "")}Admin</a>'
    pie = ""
    if usuario:
        pie = (f'<div class="side-foot"><div class="kicker">Sesión</div><b>{h((empresa or {}).get("nombre", ""))}</b>'
               f'<small>{h(usuario.get("email", ""))}</small>'
               f'<div style="display:flex;gap:12px;margin-top:10px;font-size:12px">'
               f'<a href="/cuenta" style="color:var(--ad-ink-70)">Cuenta</a>'
               f'<form method="post" action="/logout" style="display:inline">{csrf(csrf_token)}'
               f'<button type="submit" style="background:none;border:0;color:var(--ad-ink-70);cursor:pointer;font:inherit;font-size:12px;padding:0">Salir →</button></form>'
               f'</div></div>')
    return f'<aside class="side">{W.LOGO}{lis}{pie}</aside>'


def privada(titulo: str, cuerpo: str, actual: str, usuario: dict | None, empresa: dict | None,
            csrf_token: str = "", js: str = "", extra_head: str = "") -> str:
    return W.pagina(titulo, cuerpo, sidebar(actual, usuario, empresa, csrf_token),
                    extra_head=f"<style>{CSS_PRIVADA}</style>{extra_head}", js=js)


def cabecera(kicker: str, titulo: str, sub: str = "", derecha: str = "") -> str:
    sub_html = f'<p class="mute" style="font-size:14px;margin-top:6px">{h(sub)}</p>' if sub else ""
    return (f'<div class="cab"><div><div class="kicker">{h(kicker)}</div><h1 class="titulo">{h(titulo)}</h1>{sub_html}</div>'
            f'{derecha}</div>')
