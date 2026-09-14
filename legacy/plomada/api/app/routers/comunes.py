"""Parametros y tipos que comparten los routers.

Definidos una vez para que la paginacion y el `?formato=` se comporten
igual en todos los endpoints y se documenten igual en /docs.
"""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import Query

from app.config import config
from app.formatos import meta_respuesta, paginacion, responder

Formato = Annotated[
    Literal["json", "csv"],
    Query(description="`csv` devuelve las filas planas con cabecera, para abrir en Excel."),
]

Limite = Annotated[
    int,
    Query(ge=1, le=config.limite_max, description="Filas por pagina (maximo %d)." % config.limite_max),
]

Desplazamiento = Annotated[
    int,
    Query(ge=0, description="Filas a saltar desde el inicio del resultado ordenado."),
]


def listar(filas, total, limite, desplazamiento, formato, nombre, modelo):
    """Respuesta estandar de un endpoint de listado.

    `modelo` es el mismo que el `response_model` de la ruta: en JSON lo
    aplica FastAPI y en CSV lo aplica `formatos.responder`, para que las dos
    salidas publiquen las mismas columnas y no diverjan en silencio.
    """
    return responder(
        filas,
        meta_respuesta(paginacion(limite, desplazamiento, total, len(filas))),
        formato,
        nombre,
        modelo,
    )


def completo(filas, formato, nombre, modelo):
    """Respuesta de un agregado que se devuelve entero (tablas chicas)."""
    return responder(
        filas,
        meta_respuesta(paginacion(len(filas), 0, len(filas), len(filas))),
        formato,
        nombre,
        modelo,
    )
