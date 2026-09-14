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
    # Checklist y generador: calculados del pliego en contexto (o del fixture
    # en la demo). Antes eran cifras fijas de Bucaramanga para cualquiera.
    if "checklist" in activos:
        from pliego.checklist import datos as checklist_datos
        try:
            ck = checklist_datos.checklist(1)
            c = ck["resumen"]["conteo"]
            faltan = c["no_cumple"] + c["falta_documento"]
            ciudad = corto(((ck["proceso"].get("entidad") or "").replace("MUNICIPIO DE ", "").replace("ALCALDIA DE ", "")) or "el pliego")
            salida["checklist"] = ((f"{faltan} cosa{'s' if faltan != 1 else ''}", f"falta{'n' if faltan != 1 else ''} para quedar habilitado en {ciudad}")
                                   if faltan else ("Habilitado", f"{c['revisar']} punto{'s' if c['revisar'] != 1 else ''} por revisar en {ciudad}"))
        except Exception:   # sin pliego legible: la tarjeta no tumba el panel
            salida["checklist"] = ("—", "sin pliego legible")
    else:
        salida["checklist"] = ("Próximamente", "suba un pliego para revisar sus requisitos")
    if "generador" in activos:
        from pliego.generador import datos as generador_datos
        from pliego.generador import logica as LG
        try:
            r = generador_datos.paquete(1)["resumen"]
            aplican = r["total"] - r["conteo"][LG.NO_APLICA]
            pct = round(100 * r["conteo"][LG.LISTO] / aplican) if aplican else 0
            nc = r["faltantes_criticos"]
            salida["generador"] = (f"{pct} %", "de la propuesta lista · " + ("nada la rechaza" if nc == 0 else f"falta{'n' if nc != 1 else ''} {nc} cosa{'s' if nc != 1 else ''} que la rechaza{'n' if nc != 1 else ''}"))
        except Exception:
            salida["generador"] = ("—", "sin pliego legible")
    else:
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
