"""Pliegos de la empresa: guardar el PDF, extraer en segundo plano, cargar
el elegido al contexto.

Archivos en $PLATAFORMA_DATOS/pliegos/<empresa_id>/<sha256>.pdf y las
paginas renderizadas en .../<sha256>/p<N>.png. La extraccion (Claude +
poppler) corre en el hilo de trabajos de la plataforma; el estado va en
pliego.pliegos (subido -> extrayendo -> listo | error).
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from plataforma import carpeta, db, extraccion
from plataforma.config import config

log = logging.getLogger("pliego.pliegos")
MAX_BYTES = 30 * 1024 * 1024


def carpeta_pliegos(empresa_id: int) -> Path:
    return config.datos / "pliegos" / str(empresa_id)


def listar(empresa_id: int) -> list[dict]:
    return db.todos("SELECT id, nombre, estado, paginas, error, costo_usd, creado, listo, "
                    "extraccion->'id' AS proceso, extraccion->'campos'->'entidad'->'valor' AS entidad "
                    "FROM pliego.pliegos WHERE empresa_id = %s ORDER BY creado DESC", [empresa_id])


def obtener(empresa_id: int, pliego_id: int) -> dict | None:
    return db.uno("SELECT * FROM pliego.pliegos WHERE id = %s AND empresa_id = %s", [pliego_id, empresa_id])


def gasto_mes_usd(empresa_id: int) -> float:
    """Lo que la empresa lleva gastado en extracciones este mes calendario."""
    fila = db.uno("SELECT coalesce(sum(costo_usd), 0) AS usd FROM pliego.pliegos "
                  "WHERE empresa_id = %s AND creado >= date_trunc('month', now())", [empresa_id])
    return float(fila["usd"]) if fila else 0.0


def presupuesto_agotado(empresa_id: int) -> bool:
    return gasto_mes_usd(empresa_id) >= config.pliego_presupuesto_usd_mes


def guardar(empresa_id: int, usuario_id: int, nombre: str, contenido: bytes) -> tuple[dict | None, str | None]:
    """Guarda el PDF y crea la fila `subido`. (fila, error). Rechaza antes
    de escribir lo que no es PDF, lo que pesa de mas y lo que tiene mas
    paginas de las que la extraccion acepta (config.pliego_max_paginas)."""
    if not contenido.startswith(b"%PDF"):
        return None, "El archivo no es un PDF."
    if len(contenido) > MAX_BYTES:
        return None, "El PDF pesa más de 30 MB."
    sha = hashlib.sha256(contenido).hexdigest()
    existente = db.uno("SELECT id, estado FROM pliego.pliegos WHERE empresa_id = %s AND sha256 = %s", [empresa_id, sha])
    if existente:
        return existente, "Ese pliego ya estaba subido."
    carpeta_ = carpeta_pliegos(empresa_id)
    carpeta_.mkdir(parents=True, exist_ok=True)
    ruta = carpeta_ / f"{sha}.pdf"
    ruta.write_bytes(contenido)
    paginas = extraccion.n_paginas(ruta)
    if paginas > config.pliego_max_paginas:
        ruta.unlink(missing_ok=True)
        return None, f"El PDF tiene {paginas} páginas; el máximo es {config.pliego_max_paginas}."
    relativa = str(ruta.relative_to(config.datos))
    fila = db.uno("INSERT INTO pliego.pliegos (empresa_id, nombre, sha256, ruta_pdf, estado, subido_por) "
                  "VALUES (%s, %s, %s, %s, 'subido', %s) RETURNING id, estado", [empresa_id, nombre[:200], sha, relativa, usuario_id])
    return fila, None


def borrar(empresa_id: int, pliego_id: int) -> None:
    fila = obtener(empresa_id, pliego_id)
    if not fila:
        return
    db.ejecutar("DELETE FROM pliego.pliegos WHERE id = %s", [pliego_id])
    ruta = config.datos / fila["ruta_pdf"]
    try:
        ruta.unlink(missing_ok=True)
        for f in (ruta.parent / fila["sha256"]).glob("*.png"):
            f.unlink()
        (ruta.parent / fila["sha256"]).rmdir()
    except OSError:
        pass


def extraer(pliego_id: int, cliente=None) -> None:
    """Corre la extraccion y guarda el resultado; en el hilo de trabajos."""
    fila = db.uno("SELECT * FROM pliego.pliegos WHERE id = %s", [pliego_id])
    if not fila:
        return
    db.ejecutar("UPDATE pliego.pliegos SET estado = 'extrayendo', error = NULL WHERE id = %s", [pliego_id])
    try:
        ruta = config.datos / fila["ruta_pdf"]
        r = extraccion.extraer(ruta.read_bytes(), fila["nombre"], carpeta_paginas=ruta.parent / fila["sha256"], cliente=cliente,
                               max_paginas=config.pliego_max_paginas)
        avisos = extraccion.validar({"proceso": r["requisitos"]["proceso"], "requisitos": r["requisitos"]["requisitos"]})
        db.ejecutar("UPDATE pliego.pliegos SET estado = 'listo', extraccion = %s, requisitos = %s, citas_bbox = %s, paginas = %s, "
                    "costo_usd = %s, error = %s, listo = now() WHERE id = %s",
                    [json.dumps(r["extraccion"]), json.dumps(r["requisitos"]), json.dumps(r["citas_bbox"]), r["paginas"],
                     r["costo_usd"], ("; ".join(avisos) or None), pliego_id])
        log.info("pliego %s extraido: %d requisitos, %d lotes, USD %.3f, avisos %s", pliego_id,
                 len(r["requisitos"]["requisitos"]), len(r["requisitos"]["proceso"]["lotes"]), r["costo_usd"], avisos)
    except Exception as e:
        log.exception("extraccion del pliego %s fallo", pliego_id)
        db.ejecutar("UPDATE pliego.pliegos SET estado = 'error', error = %s WHERE id = %s", [str(e)[:500], pliego_id])
        raise


def para_contexto(fila: dict, perfil: dict) -> dict:
    """La fila `listo` -> lo que pliego/comun/contexto.py lleva en `pliego`."""
    ruta = config.datos / fila["ruta_pdf"]
    return {"id": fila["id"], "nombre": fila["nombre"], "requisitos": fila["requisitos"], "extraccion": fila["extraccion"],
            "citas_bbox": fila["citas_bbox"] or {}, "carpeta": carpeta.carpeta_de(perfil),
            "pdf": str(ruta), "dir": str(ruta.parent / fila["sha256"])}


def elegido_para(usuario: dict, empresa: dict) -> dict | None:
    """El pliego actual del usuario si esta listo; si no, el ultimo listo de
    la empresa; si no hay, None."""
    fila = None
    if usuario.get("pliego_actual"):
        fila = db.uno("SELECT * FROM pliego.pliegos WHERE id = %s AND empresa_id = %s AND estado = 'listo'",
                      [usuario["pliego_actual"], empresa["id"]])
    if not fila:
        fila = db.uno("SELECT * FROM pliego.pliegos WHERE empresa_id = %s AND estado = 'listo' ORDER BY listo DESC LIMIT 1",
                      [empresa["id"]])
    return fila


def pendientes() -> list[int]:
    return [f["id"] for f in db.todos("SELECT id FROM pliego.pliegos WHERE estado IN ('subido', 'extrayendo') ORDER BY creado")]
