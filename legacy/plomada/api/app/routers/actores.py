"""Entidades contratantes y proveedores.

Es la vista que un buscador de filas no da: no "estos contratos", sino
"esta entidad" y "este proveedor", con su acumulado y su red.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from app import consultas
from app.esquemas import Entidad, EntidadDetalle, Proveedor, ProveedorDetalle, Respuesta
from app.formatos import responder
from app.routers.comunes import Desplazamiento, Formato, Limite, listar

router = APIRouter(tags=["Actores"])


@router.get(
    "/entidades",
    response_model=Respuesta[list[Entidad]],
    summary="Buscar entidades contratantes",
)
def entidades(
    q: Annotated[str | None, Query(description="Nombre parcial o NIT exacto")] = None,
    departamento: Annotated[str | None, Query()] = None,
    min_contratos: Annotated[int | None, Query(ge=0)] = None,
    orden: Annotated[str | None, Query(description="-valor (defecto) | -contratos | -atipicos | -tasa")] = None,
    limite: Limite = 50,
    desplazamiento: Desplazamiento = 0,
    formato: Formato = "json",
):
    filas, total = consultas.buscar_entidades(
        texto=q, departamento=departamento, min_contratos=min_contratos,
        orden=orden, limite=limite, desplazamiento=desplazamiento,
    )
    return listar(filas, total, limite, desplazamiento, formato, "entidades", Entidad)


@router.get(
    "/entidades/{nit_entidad}",
    response_model=Respuesta[EntidadDetalle],
    summary="Perfil de una entidad",
    description=(
        "Acumulado de la entidad, sus diez banderas mas frecuentes y sus diez proveedores "
        "con mas plata adjudicada. Ordenar por `-tasa` en el listado sin filtrar por "
        "`min_contratos` sube entidades con dos o tres contratos: usa las dos cosas juntas."
    ),
    responses={404: {"description": "Ninguna entidad con ese NIT"}},
)
def entidad(nit_entidad: Annotated[str, Path(description="NIT exacto, solo digitos")]):
    datos = consultas.entidad(nit_entidad)
    if datos is None:
        raise HTTPException(
            status_code=404, detail="ninguna entidad con NIT '%s'" % nit_entidad
        )
    return responder(datos)


@router.get(
    "/proveedores",
    response_model=Respuesta[list[Proveedor]],
    summary="Buscar proveedores",
    description=(
        "`hace_ambos=true` filtra los 766 proveedores que hacen obra E interventoria: que "
        "el que vigila la obra pertenezca a la misma red que la construye es el mecanismo "
        "central del fraude en obra publica, y solo se ve teniendo los dos lados."
    ),
)
def proveedores(
    q: Annotated[str | None, Query(description="Nombre parcial o documento exacto")] = None,
    hace_ambos: Annotated[bool | None, Query(description="Hace obra e interventoria")] = None,
    cluster_id: Annotated[int | None, Query(description="Miembros de un grupo economico")] = None,
    min_contratos: Annotated[int | None, Query(ge=0)] = None,
    orden: Annotated[str | None, Query(description="-valor (defecto) | -contratos | -entidades")] = None,
    limite: Limite = 50,
    desplazamiento: Desplazamiento = 0,
    formato: Formato = "json",
):
    filas, total = consultas.buscar_proveedores(
        texto=q, hace_ambos=hace_ambos, cluster_id=cluster_id,
        min_contratos=min_contratos, orden=orden,
        limite=limite, desplazamiento=desplazamiento,
    )
    return listar(filas, total, limite, desplazamiento, formato, "proveedores", Proveedor)


@router.get(
    "/proveedores/{doc}",
    response_model=Respuesta[ProveedorDetalle],
    summary="Perfil de un proveedor y su red",
    description=(
        "Incluye `contrapartes`: otros proveedores unidos a este por llaves que deberian "
        "ser unicas (cuenta bancaria, representante legal, domicilio). `n_tipos` dice por "
        "cuantas llaves distintas estan unidos -- dos o mas es el indicio fuerte. "
        "La cuenta bancaria nunca se publica: solo el hecho de que se comparte."
    ),
    responses={404: {"description": "Ningun proveedor con ese documento"}},
)
def proveedor(doc: Annotated[str, Path(description="NIT o cedula del proveedor")]):
    datos = consultas.proveedor(doc)
    if datos is None:
        raise HTTPException(
            status_code=404, detail="ningun proveedor con documento '%s'" % doc
        )
    return responder(datos)
