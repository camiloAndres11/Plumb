"""Indice, metadatos y glosario. Lo que hay que leer antes de consultar
cualquier cifra."""
from __future__ import annotations

from fastapi import APIRouter

from app import consultas
from app.config import AVISO, VERSION_API
from app.esquemas import Bandera, Indice, Meta, Respuesta
from app.formatos import responder
from app.routers.comunes import Formato, completo

router = APIRouter(tags=["Catalogo"])


@router.get(
    "",
    response_model=Indice,
    summary="Indice de la API",
    description="Punto de entrada: version, endpoints disponibles y donde esta la documentacion.",
)
def indice():
    return {
        "nombre": "Plomada",
        "version": VERSION_API,
        "descripcion": (
            "Indicios de riesgo en la contratacion de obra publica de Colombia, "
            "a partir de datos 100% publicos del SECOP II."
        ),
        "documentacion": "https://github.com/JoseSLK/Plumb/blob/main/API.md",
        "openapi": "/openapi.json",
        "licencia": "Datos publicos del Estado colombiano. Codigo y metodologia abiertos.",
        "aviso": AVISO,
        "endpoints": {
            "GET /v1/meta": "Cobertura, cifras de encabezado y limitaciones",
            "GET /v1/banderas": "Glosario de las 26 banderas con sus pesos",
            "GET /v1/titulares": "Cifras de encabezado",
            "GET /v1/indicios": "Plata por categoria de indicio",
            "GET /v1/municipios": "Ranking municipal (tasa cruda y ajustada)",
            "GET /v1/departamentos": "Plata y tasas por departamento",
            "GET /v1/tipos-obra": "Plata por tipo de obra",
            "GET /v1/fuentes": "Plata por fuente de recursos",
            "GET /v1/autosupervision": "Entidades donde autosupervisar es la norma",
            "GET /v1/contratos": "Busqueda de contratos con filtros",
            "GET /v1/contratos/{id_contrato}": "Ficha completa con la evidencia de cada bandera",
            "GET /v1/entidades": "Entidades contratantes",
            "GET /v1/entidades/{nit_entidad}": "Perfil de una entidad",
            "GET /v1/proveedores": "Proveedores",
            "GET /v1/proveedores/{doc}": "Perfil de un proveedor y su red",
            "GET /v1/red/clusters": "Grupos economicos detectados",
            "GET /v1/red/clusters/{cluster_id}": "Subgrafo de un grupo economico",
            "GET /v1/alertas": "Licitaciones abiertas con banderas (pre-adjudicacion)",
            "GET /v1/alertas/resumen": "Conteo por universo del snapshot de alertas",
        },
    }


@router.get(
    "/meta",
    response_model=Respuesta[Meta],
    summary="Cobertura y limitaciones",
    description=(
        "Las limitaciones viajan con los datos a proposito: ninguna cifra de esta API "
        "deberia mostrarse sin su salvedad al lado. Incluye tambien el umbral explicito "
        "de 'atipico', que no esta escondido en ningun modelo."
    ),
)
def meta():
    return responder(consultas.meta())


@router.get(
    "/banderas",
    response_model=Respuesta[list[Bandera]],
    summary="Glosario de banderas",
    description=(
        "Las 26 banderas con su peso (3 = indicio fuerte, 1 = contexto), su grupo y las "
        "columnas de evidencia que la sustentan. Los pesos son explicitos y discutibles: "
        "cualquiera puede recalcular el puntaje con otros."
    ),
)
def banderas(formato: Formato = "json"):
    return completo(consultas.glosario(), formato, "banderas", Bandera)
