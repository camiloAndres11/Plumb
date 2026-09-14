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
    empresa, token, q = request.state.empresa, sesiones.token_csrf(request), request.query_params
    en_cola = set(trabajos.en_cola())
    filas = []
    for p in pliegos.listar(empresa["id"]):
        estado = "en cola" if (p["estado"] == "subido" and f"pliego:{p['id']}" in en_cola) else p["estado"]
        filas.append((p, estado, usuario.get("pliego_actual") == p["id"]))
    return V.privada(request, "pliegos.html", "Pliegos", "/pliegos", usuario, empresa, token, filas=filas,
                     extraccion_disponible=extraccion.disponible(), ok=q.get("ok"), error=q.get("error"))


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
def borrar(request: Request, pliego_id: int, usuario: dict = Depends(sesiones.requiere_admin), _: None = Depends(sesiones.csrf),
           _r: None = Depends(sesiones.reautenticar)):
    pliegos.borrar(request.state.empresa["id"], pliego_id)
    return sesiones.redirigir("/pliegos?ok=" + quote("Pliego borrado."))

