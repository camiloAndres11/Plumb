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


def _f(d) -> str:
    return d.strftime("%Y-%m-%d %H:%M") if d else "—"


@router.get("/admin", response_class=HTMLResponse)
def admin(request: Request, usuario: dict = Depends(requiere_plataforma_admin)):
    token = sesiones.token_csrf(request)
    empresas = db.todos("""
        SELECT e.id, e.nit, e.nombre, e.departamentos, e.perfil_completo, e.creada,
               count(u.id) AS usuarios, count(u.email_verificado) AS verificados,
               (SELECT count(*) FROM pliego.pliegos p WHERE p.empresa_id = e.id) AS pliegos
        FROM pliego.empresas e LEFT JOIN pliego.usuarios u ON u.empresa_id = e.id
        GROUP BY e.id ORDER BY e.creada DESC""")
    descargas = db.todos("SELECT * FROM pliego.descargas_departamento ORDER BY departamento")
    pliegos = db.todos("SELECT p.id, p.nombre, p.estado, p.paginas, p.costo_usd, p.creado, p.error, e.nombre AS empresa "
                       "FROM pliego.pliegos p JOIN pliego.empresas e ON e.id = p.empresa_id ORDER BY p.creado DESC LIMIT 50")
    en_cola = set(trabajos.en_cola())
    try:
        wh = warehouse.estado()
        meta = {m["departamento"]: m for m in wh["departamentos"]}
    except Exception as e:
        wh, meta = {"as_of": None, "n_base": 0, "n_abiertos": 0}, {}
        meta_error = str(e)
    else:
        meta_error = ""
    f_emp = "".join(
        f'<tr><td>{e["id"]}</td><td>{V.h(e["nombre"])}<br><small class="mute">{V.h(e["nit"])}</small></td>'
        f'<td>{V.h(", ".join(d.title() for d in (e["departamentos"] or [])))}</td><td>{"sí" if e["perfil_completo"] else "no"}</td>'
        f'<td>{e["usuarios"]} ({e["verificados"]} verif.)</td><td>{e["pliegos"]}</td><td>{_f(e["creada"])}</td></tr>' for e in empresas)
    f_desc = ""
    for d in descargas:
        m = meta.get(d["departamento"]) or {}
        boton = (f'<form method="post" action="/admin/descargar" style="display:inline">{V.csrf(token)}'
                 f'<input type="hidden" name="departamento" value="{V.h(d["departamento"])}"><button class="btn" type="submit">Encolar</button></form>'
                 if d["departamento"] not in en_cola and d["estado"] != "descargando" else "en cola")
        f_desc += (f'<tr><td>{V.h(d["departamento"].title())}</td><td><span class="estado {d["estado"]}">{V.h(d["estado"])}</span></td>'
                   f'<td>{V.h(str(d["as_of"] or "")[:16])}</td><td>{_f(d["ultima_ok"])}</td><td>{d["paginas"]}</td>'
                   f'<td>{m.get("n_base", "—")} / {m.get("n_abiertos", "—")}</td>'
                   f'<td style="max-width:260px;font-size:12px;color:#ffb3a3">{V.h((d["error"] or "")[:160])}</td><td>{boton}</td></tr>')
    f_pli = "".join(
        f'<tr><td>{p["id"]}</td><td>{V.h(p["empresa"])}</td><td>{V.h(p["nombre"])}</td><td><span class="estado {p["estado"]}">{p["estado"]}</span></td>'
        f'<td>{p["paginas"] or ""}</td><td>{("$%.3f" % p["costo_usd"]) if p["costo_usd"] is not None else ""}</td><td>{_f(p["creado"])}</td>'
        f'<td style="max-width:220px;font-size:12px;color:#ffb3a3">{V.h((p["error"] or "")[:120])}</td></tr>' for p in pliegos)
    costo_total = sum(float(p["costo_usd"] or 0) for p in pliegos)
    estado = (f'<div class="card"><div class="fila" style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px">'
              f'<div><div class="kicker">Croma</div><b>{"llave configurada" if croma.disponible() else "sin llave"}</b>'
              f'<br><small class="mute">créditos restantes: {trabajos.ultimo_creditos if trabajos.ultimo_creditos is not None else "—"}</small></div>'
              f'<div><div class="kicker">Warehouse</div><b>{wh["n_base"]} contratos · {wh["n_abiertos"]} abiertos</b><br><small class="mute">datos al {V.h(str(wh["as_of"] or "")[:10]) or "—"} · {V.h(meta_error)}</small></div>'
              f'<div><div class="kicker">Cola</div><b>{", ".join(sorted(en_cola)) or "vacía"}</b></div>'
              f'<div><div class="kicker">Pliegos</div><b>{len(pliegos)} · USD {costo_total:.2f}</b></div></div></div>')
    cuerpo = (V.cabecera("Administración", "Plataforma", f"{len(empresas)} empresas · {len(descargas)} departamentos")
              + V.mensajes(ok=request.query_params.get("ok"), error=request.query_params.get("error"), clase="msg") + estado
              + f'<div class="card" style="margin-top:24px"><div class="card-head"><div class="card-title">Empresas</div></div><table class="tabla">'
                f'<tr><th>#</th><th>Empresa</th><th>Departamentos</th><th>Perfil</th><th>Usuarios</th><th>Pliegos</th><th>Creada</th></tr>{f_emp}</table></div>'
              + f'<div class="card" style="margin-top:24px"><div class="card-head"><div class="card-title">Descargas por departamento</div></div><table class="tabla">'
                f'<tr><th>Departamento</th><th>Estado</th><th>as_of</th><th>Última ok</th><th>Consultas</th><th>base / abiertos</th><th></th><th></th></tr>{f_desc}</table></div>'
              + f'<div class="card" style="margin-top:24px"><div class="card-head"><div class="card-title">Pliegos</div></div><table class="tabla">'
                f'<tr><th>#</th><th>Empresa</th><th>Archivo</th><th>Estado</th><th>Pág.</th><th>Costo</th><th>Subido</th><th></th></tr>{f_pli}</table></div>')
    return V.privada("Admin", cuerpo, "/admin", usuario, request.state.empresa, token)


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
