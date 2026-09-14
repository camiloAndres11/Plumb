"""Alertas pre-adjudicacion: licitaciones que TODAVIA aceptan ofertas.

Todo lo demas en esta API mira contratos ya firmados. Aqui una
observacion al pliego todavia puede cambiar el resultado; despues de
adjudicado ya es tarde.

Los tres endpoints dependen de que alguien haya corrido
pipeline/alertas.py contra un snapshot del dia. Si no, responden 503 con
el comando que falta -- el mismo criterio que el tablero, donde
alertas.json es opcional a proposito.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app import consultas
from app.esquemas import Alerta, Respuesta, ResumenAlertas
from app.formatos import responder
from app.routers.comunes import Desplazamiento, Formato, Limite, listar

router = APIRouter(prefix="/alertas", tags=["Alertas pre-adjudicacion"])

_SIN_DATOS = (
    "no hay un snapshot de licitaciones abiertas cargado; corre "
    "'python pipeline/ingest_abiertos.py && python pipeline/alertas.py' y recarga "
    "con 'python pipeline/load_postgres.py'"
)


def _exigir_datos():
    if not consultas.hay_alertas():
        raise HTTPException(status_code=503, detail=_SIN_DATOS)


@router.get(
    "",
    response_model=Respuesta[list[Alerta]],
    summary="Licitaciones abiertas con banderas",
    description=(
        "Por defecto solo el universo `accionable`. La distincion importa: del snapshot "
        "medido el 2026-08-22, de 31.685 procesos que la plataforma marca como abiertos, "
        "el 85,5% no tiene fecha de cierre publicada y el 12,9% la tiene ya vencida. "
        "Solo el 1,6% admite hoy una observacion con efecto real.\n\n"
        "Ordenadas por numero de banderas y, a igualdad, por lo que cierra antes."
    ),
    responses={503: {"description": "No hay snapshot de alertas cargado"}},
)
def alertas(
    universo: Annotated[str, Query(
        description="accionable (defecto) | zombie_vencido | sin_fecha_cierre")] = "accionable",
    departamento: Annotated[str | None, Query()] = None,
    entidad: Annotated[str | None, Query()] = None,
    min_banderas: Annotated[int | None, Query(ge=0)] = None,
    limite: Limite = 50,
    desplazamiento: Desplazamiento = 0,
    formato: Formato = "json",
):
    _exigir_datos()
    filas, total = consultas.buscar_alertas(
        universo=universo, departamento=departamento, entidad=entidad,
        min_banderas=min_banderas, limite=limite, desplazamiento=desplazamiento,
    )
    return listar(filas, total, limite, desplazamiento, formato, "alertas", Alerta)


@router.get(
    "/resumen",
    response_model=Respuesta[ResumenAlertas],
    summary="Conteo por universo del snapshot",
    description=(
        "Los tres numeros, no solo el bonito: el titular no puede ser '31.685 alertas' "
        "cuando el 98,4% no es accionable ahora mismo."
    ),
    responses={503: {"description": "No hay snapshot de alertas cargado"}},
)
def resumen():
    _exigir_datos()
    return responder(consultas.resumen_alertas())
