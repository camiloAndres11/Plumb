"""La red de proveedores.

Los contratos no son filas: son aristas de una red de personas. Estos
endpoints exponen los grupos economicos detectados por deteccion de
comunidades sobre llaves que deberian ser unicas (cuenta bancaria,
representante legal, domicilio del representante).

Lo que NO se publica: la cuenta bancaria. Se usa como llave interna y
solo sale el hecho de que dos proveedores la comparten.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from app import consultas
from app.esquemas import Cluster, ClusterDetalle, Respuesta
from app.formatos import responder
from app.routers.comunes import Desplazamiento, Formato, Limite, listar

router = APIRouter(prefix="/red", tags=["Red"])


@router.get(
    "/clusters",
    response_model=Respuesta[list[Cluster]],
    summary="Grupos economicos detectados",
    description=(
        "Comunidades de proveedores unidos por llaves compartidas. `vigila_y_construye` "
        "marca los grupos que concentran a la vez la obra y su interventoria -- se excluyen "
        "de esa marca los grupos que contienen una entidad publica, porque ahi la "
        "concentracion es legal (convenios interadministrativos).\n\n"
        "Solo se publican los grupos de mas de un proveedor: un proveedor solo no es una red."
    ),
)
def clusters(
    vigila_y_construye: Annotated[bool | None, Query(
        description="Solo los grupos que hacen obra e interventoria a la vez")] = None,
    min_proveedores: Annotated[int | None, Query(ge=2)] = None,
    limite: Limite = 50,
    desplazamiento: Desplazamiento = 0,
    formato: Formato = "json",
):
    filas, total = consultas.buscar_clusters(
        vigila_y_construye=vigila_y_construye, min_proveedores=min_proveedores,
        limite=limite, desplazamiento=desplazamiento,
    )
    return listar(filas, total, limite, desplazamiento, formato, "clusters", Cluster)


@router.get(
    "/clusters/{cluster_id}",
    response_model=Respuesta[ClusterDetalle],
    summary="Subgrafo de un grupo economico",
    description=(
        "Nodos (proveedores) y aristas (llaves compartidas) del grupo, listo para dibujar. "
        "`tipos` dice por que estan unidos: comparte_cuenta, comparte_replegal, "
        "comparte_domicilio. Una arista con dos o mas tipos es el indicio fuerte."
    ),
    responses={404: {"description": "No existe ese grupo economico"}},
)
def cluster(cluster_id: Annotated[int, Path(description="Identificador del grupo")]):
    datos = consultas.cluster(cluster_id)
    if datos is None:
        raise HTTPException(
            status_code=404, detail="no existe el grupo economico %s" % cluster_id
        )
    return responder(datos)
