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


def tarjetas(base: str = "/", activos: set[str] | None = None) -> list[dict]:
    """Las cinco tarjetas, para _tarjetas.html. `base` es el prefijo de las
    rutas ("/" en la demo: /filtro/; "/app/" en la plataforma: /app/filtro/)."""
    activos = activos if activos is not None else {r for r, *_ in ENFOQUES}
    valores = cifras(activos)
    return [{"href": f"{base}{ruta}/", "nombre": nombre, "promesa": promesa, "icono": icono, "hot": i == 0,
             "activo": ruta in activos, "cifra": valores[ruta][0], "sub": valores[ruta][1]}
            for i, (ruta, nombre, promesa, icono) in enumerate(ENFOQUES)]


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_larga(d) -> str:
    return f"{d.day} de {MESES[d.month - 1]}"
