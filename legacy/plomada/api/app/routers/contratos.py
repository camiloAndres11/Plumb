"""Contratos: el dato crudo, que es lo que un buscador de filas no da
junto con el porque.

/v1/contratos/{id_contrato} es el endpoint que sostiene la regla del
proyecto: cada bandera encendida sale con su peso, su glosa y el numero
que la disparo. Sin evidencia no se publica.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from app import consultas
from app.esquemas import ContratoDetalle, ContratoResumen, Respuesta
from app.formatos import responder
from app.routers.comunes import Desplazamiento, Formato, Limite, listar

router = APIRouter(prefix="/contratos", tags=["Contratos"])


@router.get(
    "",
    response_model=Respuesta[list[ContratoResumen]],
    summary="Buscar contratos",
    description=(
        "Universo: 77.864 contratos de construccion del SECOP II (obra, interventoria, "
        "consultoria, concesion y APP). Los filtros de texto son coincidencia parcial e "
        "insensible a mayusculas; `nit_entidad`, `doc_proveedor`, `tipo_contrato` y "
        "`tipo_obra` son exactos.\n\n"
        "`bandera` se puede repetir y las condiciones se combinan con AND: "
        "`?bandera=f_proponente_unico&bandera=f_obra_directa` devuelve los contratos que "
        "tienen las dos. Los nombres validos estan en `GET /v1/banderas`.\n\n"
        "Sumas: usa `valor_plausible`, no `valor`. Hay 24 contratos publicados con valores "
        "imposibles (hasta 6x10^18 COP) que concentraban el 98,6% de cualquier total; no se "
        "borran, se aislan con `f_valor_implausible` y quedan con `valor_plausible` nulo."
    ),
)
def buscar(
    entidad: Annotated[str | None, Query(description="Nombre de la entidad, coincidencia parcial")] = None,
    nit_entidad: Annotated[str | None, Query(description="NIT exacto")] = None,
    departamento: Annotated[str | None, Query()] = None,
    ciudad: Annotated[str | None, Query()] = None,
    tipo_contrato: Annotated[str | None, Query(
        description="OBRA | INTERVENTORIA | CONSULTORIA | CONCESION | ASOCIACION PUBLICO PRIVADA")] = None,
    modalidad: Annotated[str | None, Query(description="Coincidencia parcial, p.ej. 'DIRECTA'")] = None,
    tipo_obra: Annotated[str | None, Query(
        description="VIAS Y TRANSPORTE | EDUCATIVO | AGUA Y SANEAMIENTO | SALUD | ...")] = None,
    anio: Annotated[int | None, Query()] = None,
    anio_desde: Annotated[int | None, Query()] = None,
    anio_hasta: Annotated[int | None, Query()] = None,
    proveedor: Annotated[str | None, Query(description="Nombre del proveedor, coincidencia parcial")] = None,
    doc_proveedor: Annotated[str | None, Query(description="NIT o cedula del proveedor, exacto")] = None,
    cluster_id: Annotated[int | None, Query(description="Contratos de un grupo economico")] = None,
    valor_min: Annotated[float | None, Query(description="Piso en COP sobre valor_plausible")] = None,
    valor_max: Annotated[float | None, Query(description="Techo en COP sobre valor_plausible")] = None,
    texto: Annotated[str | None, Query(description="Busca en la descripcion del objeto")] = None,
    bandera: Annotated[list[str] | None, Query(description="Repetible; se combinan con AND")] = None,
    solo_atipicos: Annotated[bool, Query(
        description="Solo los que encienden una bandera fuerte o acumulan 6+ puntos")] = False,
    orden: Annotated[str | None, Query(
        description="-riesgo (defecto) | riesgo | -valor | valor | -fecha | fecha | -score")] = None,
    limite: Limite = 50,
    desplazamiento: Desplazamiento = 0,
    formato: Formato = "json",
):
    filas, total = consultas.buscar_contratos(
        entidad=entidad, nit_entidad=nit_entidad, departamento=departamento,
        ciudad=ciudad, tipo_contrato=tipo_contrato, modalidad=modalidad,
        tipo_obra=tipo_obra, anio=anio, anio_desde=anio_desde, anio_hasta=anio_hasta,
        proveedor=proveedor, doc_proveedor=doc_proveedor, cluster_id=cluster_id,
        valor_min=valor_min, valor_max=valor_max, texto=texto, banderas=bandera,
        solo_atipicos=solo_atipicos, orden=orden,
        limite=limite, desplazamiento=desplazamiento,
    )
    return listar(filas, total, limite, desplazamiento, formato, "contratos", ContratoResumen)


@router.get(
    "/{id_contrato}",
    response_model=Respuesta[ContratoDetalle],
    summary="Ficha completa de un contrato",
    description=(
        "Todo lo que se sabe del contrato, agrupado en dinero, competencia, partes y riesgo, "
        "mas `banderas`: cada bandera encendida con su peso, su glosa y la EVIDENCIA numerica "
        "que la disparo en este contrato concreto (por ejemplo, cuantos proveedores comparten "
        "la cuenta, o cuantos contratos hermanos hubo en 30 dias).\n\n"
        "Un contrato marcado no es un contrato corrupto: es un contrato que amerita mirarse. "
        "`urlproceso` lleva al expediente publico en SECOP II para verificarlo."
    ),
    responses={404: {"description": "No existe un contrato con ese id"}},
)
def ficha(
    id_contrato: Annotated[str, Path(description="id_contrato del SECOP II")],
):
    datos = consultas.contrato(id_contrato)
    if datos is None:
        raise HTTPException(
            status_code=404,
            detail="no existe el contrato '%s' en el universo de obra publica analizado"
                   % id_contrato,
        )
    return responder(datos)
