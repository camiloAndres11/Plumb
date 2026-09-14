"""El panel: una tarjeta por enfoque con una cifra calculada de los datos.

Lo comparten la demo (demo/app.py) y la plataforma (plataforma/routers/
panel.py). La cifra sale de los datos que se estan sirviendo (fixtures,
Croma o el warehouse de la empresa en contexto), asi que con el perfil
ficticio da lo de siempre y con una empresa real da lo de hoy.
"""
from __future__ import annotations

from pliego.comun import web as W

# (ruta relativa, nombre, promesa, icono)
ENFOQUES = [
    ("filtro", "Filtro de procesos", "Deje de presentarse a licitaciones que no puede ganar.", "filtro"),
    ("checklist", "Checklist del pliego", "No vuelva a quedar por fuera por un papel.", "check"),
    ("simulador", "Simulador de oferta", "Oferte al precio que maximiza su puntaje, no al más bajo.", "grafico"),
    ("radar", "Radar de competidores", "Sepa contra quién compite antes de presentarse.", "radar"),
    ("generador", "Generador de propuesta", "Prepare la propuesta en horas, no en días.", "doc"),
]

W.ICONOS.setdefault("check", '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 11l3 3L22 4"></path><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>')
W.ICONOS.setdefault("radar", '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"></circle><circle cx="12" cy="12" r="4"></circle><path d="M12 3v3M12 18v3M3 12h3M18 12h3"></path></svg>')

CSS = """<style>
.pn-grid { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 14px; }
.pn-card { display: flex; flex-direction: column; justify-content: space-between; gap: 22px; padding: 26px 28px; border-radius: 18px; background: var(--ad-glass); border: 1px solid var(--ad-line); min-height: 250px; transition: border-color .3s, transform .3s var(--ad-ease); }
.pn-card:hover { border-color: var(--ad-line-3); transform: translateY(-2px); }
.pn-card.hot { border-color: rgba(255,255,255,.18); }
.pn-card.apagada { opacity: .55; pointer-events: none; }
.pn-top { display: flex; align-items: center; justify-content: space-between; }
.pn-ico { display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 12px; background: var(--ad-fill); color: var(--ad-ink-85); }
.pn-card.hot .pn-ico { color: var(--ad-accent-2); }
.pn-ico svg { width: 20px; height: 20px; }
.pn-nombre { font-size: 20px; font-weight: 600; letter-spacing: -.02em; margin-top: 18px; }
.pn-promesa { font-size: 14px; color: var(--ad-ink-60); margin-top: 6px; line-height: 1.5; }
.pn-cifra { font-size: 28px; font-weight: 600; letter-spacing: -.03em; }
.pn-sub { font-size: 12px; color: var(--ad-ink-50); margin-top: 2px; }
.pn-abrir { display: flex; justify-content: space-between; margin-top: 16px; font-size: 14px; color: var(--ad-ink-85); }
.pn-nota { display: flex; flex-direction: column; justify-content: center; gap: 10px; padding: 26px 28px; border-radius: 18px; border: 1px dashed var(--ad-line-3); color: var(--ad-ink-55); font-size: 14px; line-height: 1.5; }
.pn-nota code { font-size: 12px; color: var(--ad-ink-75); }
@media (max-width: 1100px) { .pn-grid { grid-template-columns: repeat(2, minmax(0,1fr)); } }
</style>"""


def corto(nombre: str | None, n: int = 26) -> str:
    """Nombre de entidad para un pie de tarjeta: en tipo oracion y recortado."""
    s = W.frase(nombre) if nombre else ""
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def cifras(activos: set[str] | None = None) -> dict[str, tuple[str, str]]:
    """La cifra grande y su pie por enfoque, calculadas de los datos que se
    sirven. `activos` limita que enfoques se calculan (los demas quedan con
    su texto fijo): en la plataforma checklist y generador no estan hasta
    que haya un pliego subido."""
    from pliego.filtro import datos as filtro_datos
    from pliego.radar import datos as radar_datos
    from pliego.simulador import datos as simulador_datos
    from pliego.simulador.metodos import VERSION_DEFECTO, VERSIONES
    activos = activos if activos is not None else {r for r, *_ in ENFOQUES}
    salida = {
        "filtro": ("—", "sin procesos abiertos"),
        "checklist": ("3 cosas", "faltan para quedar habilitado en Bucaramanga"),
        "generador": ("60 %", "de la propuesta lista · falta 1 cosa que la rechaza"),
        "simulador": ("—", "sin procesos de obra abiertos"),
        "radar": ("—", "sin procesos abiertos"),
    }
    if "filtro" in activos:
        res = filtro_datos.resumen()
        salida["filtro"] = (f"{res['conteo']['presentarse']} de {res['total']}", "procesos abiertos valen su tiempo")
    if "simulador" in activos:
        abiertos = simulador_datos.abiertos()
        if abiertos:
            p = abiertos[0]
            r = simulador_datos.recomendar_para(p["id_del_proceso"])
            maximo = int(VERSIONES[VERSION_DEFECTO].puntaje_maximo)
            ciudad = p.get("ciudad") if p.get("ciudad") not in (None, "", "NO DEFINIDO") else p.get("entidad")
            salida["simulador"] = (f"{100 * r['ratio']:.1f} %".replace(".", ","),
                                   f"precio recomendado para {corto(ciudad)} · {r['esperado']:.1f} de {maximo}".replace(".", ","))
    if "radar" in activos:
        abiertos = radar_datos.abiertos()
        if abiertos:
            p = abiertos[0]
            n = len(radar_datos.competidores_de(p["id_del_proceso"]))
            salida["radar"] = (str(n), f"competidores probables en {corto(p.get('entidad'))}")
    if "checklist" not in activos:
        salida["checklist"] = ("Próximamente", "suba un pliego para revisar sus requisitos")
    if "generador" not in activos:
        salida["generador"] = ("Próximamente", "suba un pliego para armar la propuesta")
    return salida


def tarjetas(base: str = "/", activos: set[str] | None = None) -> str:
    """El HTML de las cinco tarjetas. `base` es el prefijo de las rutas
    ("/" en la demo: /filtro/; "/app/" en la plataforma: /app/filtro/)."""
    activos = activos if activos is not None else {r for r, *_ in ENFOQUES}
    valores = cifras(activos)
    html = ""
    for i, (ruta, nombre, promesa, icono) in enumerate(ENFOQUES):
        cifra, sub = valores[ruta]
        hot, activo = i == 0, ruta in activos
        html += (f'<a class="pn-card{" hot" if hot else ""}{"" if activo else " apagada"}" href="{base}{ruta}/">'
                 f'<div><div class="pn-top"><span class="pn-ico">{W.ICONOS[icono]}</span>'
                 f'<span class="tag{"" if hot else " tag-neutro"}">Enfoque {i + 1}</span></div>'
                 f'<div class="pn-nombre">{W.h(nombre)}</div><div class="pn-promesa">{W.h(promesa)}</div></div>'
                 f'<div><div class="pn-cifra num{" hot" if hot else ""}">{W.h(cifra)}</div><div class="pn-sub">{W.h(sub)}</div>'
                 f'<div class="pn-abrir"><span>{"Abrir" if activo else "Pronto"}</span><span>→</span></div></div></a>')
    return html


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_larga(d) -> str:
    return f"{d.day} de {MESES[d.month - 1]}"
