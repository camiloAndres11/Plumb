"""Modelos de respuesta. Son el contrato publico de la API y lo que
FastAPI usa para generar el OpenAPI de /docs.

Dos reglas que se siguen en todo el archivo:

1. Los nombres de campo son los mismos que ya usan web/data/*.json. Ese
   vocabulario existe desde el primer commit (ver el docstring de
   pipeline/export_web.py) y tener dos nombres para la misma cifra seria
   peor que tenerlos en espanol.
2. Casi todo es opcional. Los datos del SECOP II tienen huecos reales y
   un modelo que exija valores obligatorios convertiria un hueco de
   publicacion de una alcaldia en un 500 de esta API.
"""
from __future__ import annotations

import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.config import AVISO, FUENTE, VERSION_API

T = TypeVar("T")


# ---------------------------------------------------------------------
# Sobre comun
# ---------------------------------------------------------------------
class Paginacion(BaseModel):
    limite: int = Field(description="Filas pedidas por pagina")
    desplazamiento: int = Field(description="Filas saltadas desde el inicio")
    total: int = Field(description="Filas que cumplen el filtro, sin paginar")
    devueltas: int = Field(description="Filas en esta respuesta")


class MetaRespuesta(BaseModel):
    version: str = VERSION_API
    fuente: str = FUENTE
    aviso: str = AVISO
    paginacion: Paginacion | None = None


class Respuesta(BaseModel, Generic[T]):
    """Sobre de toda respuesta con exito.

    Las filas de `datos` conservan exactamente la forma de los JSON del
    tablero; el sobre solo agrega contexto alrededor.
    """
    datos: T
    meta: MetaRespuesta


class DetalleError(BaseModel):
    codigo: str = Field(description="Identificador estable del error, apto para programar contra el")
    mensaje: str
    detalle: object | None = None


class RespuestaError(BaseModel):
    error: DetalleError


# ---------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------
class Bandera(BaseModel):
    bandera: str = Field(description="Nombre de la columna, p.ej. f_proponente_unico")
    peso: float = Field(description="3 = indicio fuerte, 2 = intermedio, 1 = contexto")
    grupo: str = Field(description="Competencia | Red | Dinero | Ejecucion | Umbrales | Opacidad")
    glosa: str = Field(description="Que significa, en una linea")
    capa: str = Field(description="'contrato' (tramite) o 'red' (grafo de proveedores)")
    evidencia: str | None = Field(
        default=None,
        description="Columnas ev_* que sustentan la bandera, separadas por coma",
    )


class Cobertura(BaseModel):
    cedula_ordenador: float | None = None
    cedula_supervisor: float | None = None
    cuenta_bancaria: float | None = None
    unido_a_proceso: float | None = None
    tipo_obra: float | None = None


class Meta(BaseModel):
    contratos: int
    valor_total: float | None = None
    contratos_atipicos: int
    n_clusters: int
    n_proveedores: int
    n_entidades: int
    primer_anio: int | None = None
    ultimo_anio: int | None = None
    cobertura: Cobertura
    limitaciones: list[str] = Field(
        description="Lo que hay que decir en voz alta. Viaja con los datos a proposito: "
                    "ninguna cifra de esta API deberia mostrarse sin su salvedad."
    )
    umbral_atipico: str = Field(
        default="n_banderas_fuertes >= 1 OR puntos_crudos >= 6",
        description="El umbral es explicito y discutible, no un modelo opaco.",
    )
    construido: datetime.date | None = None


# ---------------------------------------------------------------------
# Agregados
# ---------------------------------------------------------------------
class Titular(BaseModel):
    concepto: str
    n_contratos: int
    valor: float


class Indicio(BaseModel):
    indicio: str
    grupo: str
    n_contratos: int
    valor: float


class Municipio(BaseModel):
    ciudad: str
    departamento: str | None = None
    n_contratos: int
    n_atipicos: int
    tasa_cruda: float | None = Field(default=None, description="n_atipicos / n_contratos, sin corregir")
    tasa_ajustada: float | None = Field(
        default=None,
        description="Tasa con encogimiento bayesiano empirico. Se publican SIEMPRE las dos: "
                    "un municipio con 4 contratos y 2 marcados da 50% cruda y no significa nada.",
    )
    valor_total: float
    valor_atipico: float
    share_valor_atipico: float | None = None
    n_proponente_unico: int | None = None
    n_obra_directa: int | None = None
    n_cuenta_compartida: int | None = None
    n_fraccionamiento: int | None = None


class Departamento(BaseModel):
    departamento: str
    n_contratos: int
    total: float
    sin_competencia: float
    en_riesgo: float
    riesgo_red: float
    regalias: float
    tasa_cruda: float | None = None
    tasa_ajustada: float | None = None


class TipoObra(BaseModel):
    tipo_obra: str
    n_contratos: int
    total: float
    en_riesgo: float
    sin_competencia: float


class Fuente(BaseModel):
    fuente: str
    total: float
    en_riesgo: float


class Autosupervision(BaseModel):
    nit_entidad: str | None = None
    entidad: str | None = None
    departamento: str | None = None
    ciudad: str | None = None
    n_auto: int
    n_con_ambos: int
    tasa: float
    valor_auto: float


# ---------------------------------------------------------------------
# Contratos
# ---------------------------------------------------------------------
class ContratoResumen(BaseModel):
    """Fila de /v1/contratos. Lo justo para decidir cual abrir."""
    id_contrato: str
    entidad: str | None = None
    nit_entidad: str | None = None
    departamento: str | None = None
    ciudad: str | None = None
    tipo_contrato: str | None = None
    modalidad: str | None = None
    tipo_obra: str | None = None
    anio: int | None = None
    fecha_firma: datetime.date | None = None
    proveedor: str | None = None
    doc_proveedor: str | None = None
    valor: float | None = None
    valor_plausible: float | None = Field(
        default=None,
        description="NULL en los 24 contratos con valor imposible. Esta es la columna "
                    "que se suma; `valor` es lo publicado tal cual.",
    )
    es_atipico: bool
    puntos_crudos: int
    n_banderas_fuertes: int
    puntos_red: int | None = None
    n_banderas_red_fuertes: int | None = None
    score: float | None = None
    banderas: list[str] = Field(description="Nombres de las banderas encendidas")
    urlproceso: str | None = None


class BanderaEncendida(BaseModel):
    """Una bandera con su evidencia. Sin evidencia no se publica: esa
    regla del proyecto es el motivo de que este modelo exista."""
    bandera: str
    peso: float
    grupo: str
    capa: str
    glosa: str
    evidencia: dict[str, object] = Field(
        default_factory=dict,
        description="Los numeros ev_* que dispararon la bandera en ESTE contrato",
    )


class Dinero(BaseModel):
    valor: float | None = None
    valor_plausible: float | None = None
    valor_pagado: float | None = None
    valor_pend_ejecucion: float | None = None
    valor_anticipo: float | None = None
    precio_base: float | None = None
    rec_regalias: float | None = None
    rec_sgp: float | None = None
    rec_propios_terr: float | None = None


class Competencia(BaseModel):
    n_oferentes_unicos: int | None = None
    n_invitados: int | None = None
    dias_ventana: int | None = None
    dias_originales: int | None = None
    dias_adicionados: int | None = None


class Partes(BaseModel):
    """Quien firma. Los documentos de identidad de personas naturales
    (ordenador del gasto, supervisor, representante legal) NO se publican:
    son dato personal (Ley 1581 de 2012). Lo unico que el sitio necesita de
    ellos es si estan y si dos coinciden, y eso sale como booleanos."""
    proveedor: str | None = None
    doc_proveedor: str | None = Field(default=None, description="NIT del contratista; identificador del recurso /v1/proveedores")
    ordenador: str | None = None
    supervisor: str | None = None
    tiene_doc_ordenador: bool = False
    tiene_doc_supervisor: bool = False
    tiene_doc_replegal: bool = False
    mismo_ordenador_supervisor: bool = Field(default=False, description="El ordenador del gasto y el supervisor son la misma persona")


class Riesgo(BaseModel):
    es_atipico: bool
    puntos_crudos: int
    score: float | None = None
    n_banderas_fuertes: int
    puntos_red: int | None = None
    n_banderas_red_fuertes: int | None = None
    cluster_id: int | None = None
    tamano_cluster: int | None = None


class ContratoDetalle(BaseModel):
    """Ficha completa de /v1/contratos/{id_contrato}."""
    id_contrato: str
    urlproceso: str | None = Field(default=None, description="Enlace al proceso en SECOP II")
    entidad: str | None = None
    nit_entidad: str | None = None
    departamento: str | None = None
    ciudad: str | None = None
    orden: str | None = None
    tipo_contrato: str | None = None
    modalidad: str | None = None
    estado: str | None = None
    unspsc: str | None = None
    tipo_obra: str | None = None
    descripcion: str | None = None
    dir_ejecucion: str | None = None
    fecha_firma: datetime.date | None = None
    anio: int | None = None
    periodo_gobierno: str | None = None
    dinero: Dinero
    competencia: Competencia
    partes: Partes
    riesgo: Riesgo
    banderas: list[BanderaEncendida]


# ---------------------------------------------------------------------
# Actores
# ---------------------------------------------------------------------
class Entidad(BaseModel):
    nit_entidad: str
    entidad: str | None = None
    departamento: str | None = None
    ciudad: str | None = None
    orden: str | None = None
    n_contratos: int
    valor_total: float | None = None
    n_atipicos: int
    valor_atipico: float | None = None
    tasa_atipicos: float | None = None
    n_riesgo_red: int | None = None
    n_proveedores: int | None = None
    primer_anio: int | None = None
    ultimo_anio: int | None = None


class ConteoBandera(BaseModel):
    bandera: str
    glosa: str
    peso: float
    n_contratos: int


class EntidadDetalle(Entidad):
    banderas_frecuentes: list[ConteoBandera]
    top_proveedores: list["ProveedorEnEntidad"]


class ProveedorEnEntidad(BaseModel):
    doc_proveedor: str | None = None
    proveedor: str | None = None
    n_contratos: int
    valor_total: float | None = None
    n_atipicos: int


class Proveedor(BaseModel):
    doc: str
    nombre: str | None = None
    n_contratos: int
    valor_total: float | None = None
    n_entidades: int | None = None
    n_obra: int | None = None
    n_interventoria: int | None = None
    hace_ambos: bool | None = Field(
        default=None,
        description="Hace obra E interventoria. Que el que vigila y el que construye "
                    "sean el mismo es el mecanismo central del fraude en obra publica.",
    )
    es_entidad_publica: bool | None = None
    primer_anio: int | None = None
    ultimo_anio: int | None = None
    cluster_id: int | None = None
    tamano_cluster: int | None = None


class Contraparte(BaseModel):
    doc: str
    nombre: str | None = None
    peso: float
    n_tipos: int = Field(description="Cuantas llaves distintas los unen (cuenta, replegal, domicilio)")
    tipos: list[str]


class ProveedorDetalle(Proveedor):
    contrapartes: list[Contraparte] = Field(
        description="Proveedores unidos a este por llaves que deberian ser unicas"
    )
    entidades: list[str] = Field(description="Entidades a las que le ha contratado")


# ---------------------------------------------------------------------
# Red
# ---------------------------------------------------------------------
class Cluster(BaseModel):
    cluster_id: int
    n_proveedores: int
    n_contratos: int | None = None
    valor_total: float | None = None
    n_obra: int | None = None
    n_interventoria: int | None = None
    vigila_y_construye: bool | None = None
    tiene_entidad_publica: bool | None = None


class NodoRed(BaseModel):
    doc: str
    nombre: str | None = None
    n_obra: int | None = None
    n_interventoria: int | None = None
    n_contratos: int
    valor_total: float
    n_entidades: int | None = None
    es_entidad_publica: bool | None = None


class AristaRed(BaseModel):
    doc_a: str
    doc_b: str
    peso: float
    n_tipos: int
    tipos: list[str]


class ClusterDetalle(Cluster):
    nodos: list[NodoRed]
    aristas: list[AristaRed]


# ---------------------------------------------------------------------
# Alertas pre-adjudicacion
# ---------------------------------------------------------------------
class Alerta(BaseModel):
    id_del_proceso: str
    urlproceso: str | None = None
    entidad: str | None = None
    nit_entidad: str | None = None
    departamento: str | None = None
    ciudad: str | None = None
    tipo_contrato: str | None = None
    modalidad: str | None = None
    unspsc: str | None = None
    descripcion: str | None = None
    precio_base: float
    fecha_publicacion: datetime.date | None = None
    fecha_cierre: datetime.date | None = None
    dias_ventana: int | None = None
    dias_restantes: int | None = None
    n_invitados: int | None = None
    n_manifestaron: int | None = None
    n_respuestas: int | None = None
    universo: str = Field(
        description="accionable | zombie_vencido | sin_fecha_cierre. Solo 'accionable' "
                    "es un proceso donde hoy se puede radicar una observacion con efecto."
    )
    n_banderas: int
    f_ventana_corta: bool | None = None
    f_al_tope_minima: bool | None = None
    f_historial_proponente_unico: bool | None = None
    f_sin_interes_a_tiempo: bool | None = None
    f_cierre_movido: bool | None = Field(
        default=None,
        description="NULL significa 'no hay snapshot de ayer con que comparar', "
                    "no 'se comparo y no cambio'.",
    )
    # Las dos siguientes son opacidad de publicacion, no riesgo de fraude:
    # no suman a n_banderas, pero explican por que un proceso cayo en el
    # universo 'zombie_vencido' o 'sin_fecha_cierre'.
    f_cierre_vencido: bool | None = None
    f_sin_fechas: bool | None = None
    ev_ventana_p10_modalidad: float | None = None
    ev_tasa_historica_entidad: float | None = None
    ev_n_historico_entidad: int | None = None


class ResumenUniverso(BaseModel):
    universo: str
    n_procesos: int
    n_con_alerta: int
    precio_base_total: float | None = None


class ResumenAlertas(BaseModel):
    construido: datetime.date | None = None
    por_universo: list[ResumenUniverso]
    nota: str


# ---------------------------------------------------------------------
# Indice
# ---------------------------------------------------------------------
class Indice(BaseModel):
    nombre: str
    version: str
    descripcion: str
    documentacion: str
    openapi: str
    licencia: str
    aviso: str
    endpoints: dict[str, str]


EntidadDetalle.model_rebuild()
