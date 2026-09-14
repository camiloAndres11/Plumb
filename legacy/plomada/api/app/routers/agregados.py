"""Agregados: las mismas cifras que muestra el tablero, servidas por HTTP.

Los nombres de campo son identicos a los de web/data/*.json a proposito
(ver el docstring de pipeline/export_web.py): quien ya lee el tablero no
tiene que aprender un segundo vocabulario.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app import consultas
from app.esquemas import (
    Autosupervision,
    Departamento,
    Fuente,
    Indicio,
    Municipio,
    Respuesta,
    TipoObra,
    Titular,
)
from app.routers.comunes import Desplazamiento, Formato, Limite, completo, listar

router = APIRouter(tags=["Agregados"])


@router.get(
    "/titulares",
    response_model=Respuesta[list[Titular]],
    summary="Cifras de encabezado",
    description=(
        "Las cifras que se citan textualmente. OJO: 'adjudicado sin competencia' es mayor "
        "que 'clasificado atipico' y no es una contradiccion -- son dos preguntas distintas "
        "(cuanta plata se adjudico sin competencia vs. cuantos contratos acumulan indicios "
        "suficientes para priorizar investigacion)."
    ),
)
def titulares(formato: Formato = "json"):
    return completo(consultas.titulares(), formato, "titulares", Titular)


@router.get(
    "/indicios",
    response_model=Respuesta[list[Indicio]],
    summary="Plata por categoria de indicio",
    description=(
        "Las filas NO se suman entre si: un contrato puede presentar varios indicios y se "
        "cuenta en cada uno. Cada linea se compara contra el total del universo."
    ),
)
def indicios(formato: Formato = "json"):
    return completo(consultas.indicios(), formato, "indicios", Indicio)


@router.get(
    "/municipios",
    response_model=Respuesta[list[Municipio]],
    summary="Ranking municipal",
    description=(
        "Se devuelven SIEMPRE las dos tasas. La cruda encabeza la lista con municipios de "
        "4 contratos y 2 marcados; la ajustada aplica encogimiento bayesiano empirico y "
        "jala hacia la media nacional a quien no tiene volumen que lo sostenga. "
        "`min_contratos` por defecto es 20 por la misma razon. "
        "El ranking NO esta normalizado por poblacion."
    ),
)
def municipios(
    departamento: Annotated[str | None, Query(description="Coincidencia parcial")] = None,
    min_contratos: Annotated[int, Query(ge=0, description="Piso de volumen para entrar al ranking")] = 20,
    orden: Annotated[str | None, Query(description="Ver /v1 para las llaves validas")] = None,
    limite: Limite = 50,
    desplazamiento: Desplazamiento = 0,
    formato: Formato = "json",
):
    filas, total = consultas.municipios(
        departamento=departamento, min_contratos=min_contratos,
        orden=orden, limite=limite, desplazamiento=desplazamiento,
    )
    return listar(filas, total, limite, desplazamiento, formato, "municipios", Municipio)


@router.get(
    "/departamentos",
    response_model=Respuesta[list[Departamento]],
    summary="Plata y tasas por departamento",
)
def departamentos(formato: Formato = "json"):
    return completo(consultas.departamentos(), formato, "departamentos", Departamento)


@router.get(
    "/tipos-obra",
    response_model=Respuesta[list[TipoObra]],
    summary="Plata por tipo de obra",
    description=(
        "La clasificacion por tipo de obra cubre el 49,3% de los contratos y sirve SOLO "
        "para segmentar, nunca para comparar precios entre obras: el percentil 95 es 59 "
        "veces la mediana en vias, asi que comparar totales mide tamano de proyecto, no "
        "sobreprecio."
    ),
)
def tipos_obra(formato: Formato = "json"):
    return completo(consultas.tipos_obra(), formato, "tipos_obra", TipoObra)


@router.get(
    "/fuentes",
    response_model=Respuesta[list[Fuente]],
    summary="Plata por fuente de recursos",
    description="Regalias, Sistema General de Participaciones y recursos propios territoriales.",
)
def fuentes(formato: Formato = "json"):
    return completo(consultas.fuentes(), formato, "fuentes", Fuente)


@router.get(
    "/autosupervision",
    response_model=Respuesta[list[Autosupervision]],
    summary="Entidades donde autosupervisar es la norma",
    description=(
        "Entidades donde el mismo funcionario ordena el gasto y supervisa en la mayoria de "
        "sus contratos. Se reporta como hallazgo de la ENTIDAD, una sola vez, y no como una "
        "bandera por contrato: marcar 240 contratos de la misma alcaldia infla el conteo y "
        "distorsiona el ranking municipal cuando lo que hay es una costumbre de digitacion."
    ),
)
def autosupervision(formato: Formato = "json"):
    return completo(consultas.autosupervision(), formato, "autosupervision", Autosupervision)
