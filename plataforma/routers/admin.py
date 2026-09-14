"""/admin: operacion de la plataforma, solo para PLATAFORMA_ADMINS.

Ver empresas y usuarios, el estado de las descargas por departamento (y
encolar o reintentar), los pliegos y su costo, la cola de trabajos y el
saldo de Croma. Sin edicion de datos de clientes: para eso esta Postgres.
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from plataforma import db, sesiones, trabajos
from plataforma import vistas as V
from plataforma.config import config
from pliego.comun import croma, warehouse

router = APIRouter()


def requiere_plataforma_admin(request: Request) -> dict:
    usuario = sesiones.requiere_sesion(request)
    if usuario["email"].lower() not in config.admins:
        raise sesiones.Prohibido("esta página es solo para los administradores de la plataforma")
    return usuario


@router.get("/admin", response_class=HTMLResponse)
def admin(request: Request, usuario: dict = Depends(requiere_plataforma_admin)):
    token, q = sesiones.token_csrf(request), request.query_params
    empresas = db.todos("""
        SELECT e.id, e.nit, e.nombre, e.departamentos, e.perfil_completo, e.creada,
               count(u.id) AS usuarios, count(u.email_verificado) AS verificados,
               (SELECT count(*) FROM pliego.pliegos p WHERE p.empresa_id = e.id) AS pliegos
        FROM pliego.empresas e LEFT JOIN pliego.usuarios u ON u.empresa_id = e.id
        GROUP BY e.id ORDER BY e.creada DESC""")
    descargas = db.todos("SELECT * FROM pliego.descargas_departamento ORDER BY departamento")
    pliegos = db.todos("SELECT p.id, p.nombre, p.estado, p.paginas, p.costo_usd, p.creado, p.error, e.nombre AS empresa "
                       "FROM pliego.pliegos p JOIN pliego.empresas e ON e.id = p.empresa_id ORDER BY p.creado DESC LIMIT 50")
    try:
        wh = warehouse.estado()
        meta, meta_error = {m["departamento"]: m for m in wh["departamentos"]}, ""
    except Exception as e:
        wh, meta, meta_error = {"as_of": None, "n_base": 0, "n_abiertos": 0}, {}, str(e)
    return V.privada(request, "admin.html", "Admin", "/admin", usuario, request.state.empresa, token, empresas=empresas,
                     descargas=descargas, pliegos=pliegos, en_cola=set(trabajos.en_cola()), wh=wh, meta=meta, meta_error=meta_error,
                     croma_ok=croma.disponible(), creditos=trabajos.ultimo_creditos,
                     costo_total=sum(float(p["costo_usd"] or 0) for p in pliegos), ok=q.get("ok"), error=q.get("error"))


@router.get("/admin/estado")
def estado(request: Request, usuario: dict = Depends(requiere_plataforma_admin)):
    """El estado detallado del servicio (lo que /health ya no cuenta)."""
    from plataforma.app import estado_detallado
    return estado_detallado()


@router.post("/admin/descargar")
def descargar(request: Request, usuario: dict = Depends(requiere_plataforma_admin), _: None = Depends(sesiones.csrf),
              departamento: str = Form(...)):
    if not croma.disponible():
        return sesiones.redirigir("/admin?error=" + quote("Sin CROMA_API_KEY no se puede descargar."))
    db.ejecutar("UPDATE pliego.descargas_departamento SET estado = 'pendiente', error = NULL WHERE departamento = %s AND estado <> 'descargando'",
                [departamento])
    trabajos.encolar(departamento)
    return sesiones.redirigir("/admin?ok=" + quote(f"{departamento.title()} en cola."))
