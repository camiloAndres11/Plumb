"""Pliegos de la empresa: subir un PDF, ver su estado, elegir con cual
trabajan checklist y generador, borrar."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import HTMLResponse

from plataforma import db, extraccion, pliegos, seguridad, sesiones, trabajos
from plataforma import vistas as V

router = APIRouter()


@router.get("/pliegos", response_class=HTMLResponse)
def lista(request: Request, usuario: dict = Depends(sesiones.requiere_sesion)):
    empresa, token = request.state.empresa, sesiones.token_csrf(request)
    en_cola = set(trabajos.en_cola())
    filas = ""
    for p in pliegos.listar(empresa["id"]):
        actual = usuario.get("pliego_actual") == p["id"]
        estado = "en cola" if (p["estado"] == "subido" and f"pliego:{p['id']}" in en_cola) else p["estado"]
        acciones = ""
        if p["estado"] == "listo":
            acciones += (f'<form method="post" action="/pliegos/{p["id"]}/usar" style="display:inline">{V.csrf(token)}'
                         f'<button class="btn{" hot" if not actual else ""}" type="submit">{"En uso" if actual else "Usar"}</button></form> '
                         f'<a class="btn" href="/app/checklist/">Checklist</a> <a class="btn" href="/app/generador/">Propuesta</a> ')
        if p["estado"] == "error" and usuario["rol"] == "admin":
            acciones += (f'<form method="post" action="/pliegos/{p["id"]}/reintentar" style="display:inline">{V.csrf(token)}'
                         f'<button class="btn" type="submit">Reintentar</button></form> ')
        if usuario["rol"] == "admin":
            acciones += (f'<form method="post" action="/pliegos/{p["id"]}/borrar" style="display:inline" onsubmit="return confirm(\'¿Borrar este pliego?\')">{V.csrf(token)}'
                         f'<button class="btn peligro" type="submit">Borrar</button></form>')
        filas += (f'<tr><td>{V.h(p["nombre"])}<br><small class="mute">{V.h(p.get("proceso") or "")} · {V.h(p.get("entidad") or "")}</small></td>'
                  f'<td><span class="estado {p["estado"]}">{V.h(estado)}</span></td><td>{p["paginas"] or ""}</td>'
                  f'<td>{p["creado"].strftime("%Y-%m-%d")}</td><td style="max-width:260px;font-size:12px;color:#ffb3a3">{V.h((p.get("error") or "")[:140])}</td>'
                  f'<td style="white-space:nowrap">{acciones}</td></tr>')
    aviso = "" if extraccion.disponible() else V.mensajes(error="La extracción con Claude no está configurada (ANTHROPIC_API_KEY): los pliegos quedarán en 'subido' hasta que lo esté.", clase="msg")
    subir = (f'<div class="card" style="margin-top:24px"><div class="card-head"><div class="card-title">Subir un pliego</div></div>'
             f'<form method="post" action="/pliegos" enctype="multipart/form-data" class="form">{V.csrf(token)}'
             f'<label class="campo">PDF del pliego de condiciones (máximo 30 MB)<input type="file" name="archivo" accept="application/pdf" required></label>'
             f'<div><button class="btn hot" type="submit">Subir y extraer</button></div>'
             f'<p class="mute" style="font-size:13px;margin:0">Claude lee el pliego y saca los requisitos habilitantes, los lotes y los formatos. Tarda uno o dos minutos. '
             f'Cada dato cita la página del PDF de donde salió.</p></form></div>')
    cuerpo = (V.cabecera("Pliegos", "Pliegos de la empresa", "Con un pliego listo se activan el checklist y el generador de propuesta.")
              + V.mensajes(ok=request.query_params.get("ok"), error=request.query_params.get("error"), clase="msg") + aviso
              + (f'<div class="card"><table class="tabla"><tr><th>Pliego</th><th>Estado</th><th>Páginas</th><th>Subido</th><th></th><th></th></tr>{filas}</table></div>'
                 if filas else '<div class="card"><p class="mute" style="margin:0">Todavía no hay pliegos.</p></div>')
              + subir)
    return V.privada("Pliegos", cuerpo, "/pliegos", usuario, empresa, token)


async def _leer_con_tope(archivo: UploadFile, maximo: int) -> bytes | None:
    """Lee el upload por trozos y corta en cuanto pasa del tope, en vez de
    cargar en memoria lo que mande el cliente."""
    partes, total = [], 0
    while True:
        trozo = await archivo.read(1024 * 1024)
        if not trozo:
            break
        total += len(trozo)
        if total > maximo:
            return None
        partes.append(trozo)
    return b"".join(partes)


@router.post("/pliegos")
async def subir(request: Request, usuario: dict = Depends(sesiones.requiere_sesion), _: None = Depends(sesiones.csrf),
                archivo: UploadFile | None = None):
    empresa = request.state.empresa
    if archivo is None or not archivo.filename:
        return sesiones.redirigir("/pliegos?error=" + quote("Elija un PDF."))
    if not seguridad.permitir("pliegos:" + str(empresa["id"]), 20, 86400):
        return sesiones.redirigir("/pliegos?error=" + quote("Ya se subieron muchos pliegos hoy; intente mañana."))
    if pliegos.presupuesto_agotado(empresa["id"]):
        return sesiones.redirigir("/pliegos?error=" + quote("Se agotó el presupuesto de extracción de este mes; contacte a soporte."))
    contenido = await _leer_con_tope(archivo, pliegos.MAX_BYTES)
    if contenido is None:
        return sesiones.redirigir("/pliegos?error=" + quote("El PDF pesa más de 30 MB."))
    fila, error = pliegos.guardar(empresa["id"], usuario["id"], archivo.filename, contenido)
    if error and not fila:
        return sesiones.redirigir("/pliegos?error=" + quote(error))
    if fila["estado"] in ("subido", "error") and extraccion.disponible():
        trabajos.encolar_pliego(fila["id"])
        return sesiones.redirigir("/pliegos?ok=" + quote(error or "Pliego subido; la extracción empezó."))
    return sesiones.redirigir("/pliegos?ok=" + quote(error or "Pliego subido. Se extraerá cuando la extracción esté configurada."))


@router.post("/pliegos/{pliego_id}/usar")
def usar(request: Request, pliego_id: int, usuario: dict = Depends(sesiones.requiere_sesion), _: None = Depends(sesiones.csrf)):
    if not pliegos.obtener(request.state.empresa["id"], pliego_id):
        return sesiones.redirigir("/pliegos?error=" + quote("Ese pliego no es de su empresa."))
    db.ejecutar("UPDATE pliego.usuarios SET pliego_actual = %s WHERE id = %s", [pliego_id, usuario["id"]])
    return sesiones.redirigir("/app/checklist/")


@router.post("/pliegos/{pliego_id}/reintentar")
def reintentar(request: Request, pliego_id: int, usuario: dict = Depends(sesiones.requiere_admin), _: None = Depends(sesiones.csrf)):
    fila = pliegos.obtener(request.state.empresa["id"], pliego_id)
    if not fila or fila["estado"] == "extrayendo":
        return sesiones.redirigir("/pliegos")
    if pliegos.presupuesto_agotado(request.state.empresa["id"]):
        return sesiones.redirigir("/pliegos?error=" + quote("Se agotó el presupuesto de extracción de este mes; contacte a soporte."))
    db.ejecutar("UPDATE pliego.pliegos SET estado = 'subido', error = NULL WHERE id = %s", [pliego_id])
    if not extraccion.disponible():
        return sesiones.redirigir("/pliegos?error=" + quote("La extracción no está configurada (ANTHROPIC_API_KEY)."))
    trabajos.encolar_pliego(pliego_id)
    return sesiones.redirigir("/pliegos?ok=" + quote("Extracción en cola."))


@router.post("/pliegos/{pliego_id}/borrar")
def borrar(request: Request, pliego_id: int, usuario: dict = Depends(sesiones.requiere_admin), _: None = Depends(sesiones.csrf)):
    pliegos.borrar(request.state.empresa["id"], pliego_id)
    return sesiones.redirigir("/pliegos?ok=" + quote("Pliego borrado."))

