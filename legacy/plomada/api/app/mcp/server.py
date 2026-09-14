"""Servidor MCP de Plomada: tools de solo lectura para que Claude (u otra
IA con soporte de MCP) responda preguntas conversacionales sobre los
datos. Ver MCP.md en la raiz del repo para el plan completo.

No tiene SQL propio. Todas las tools llaman a `app.consultas`, la misma
capa que usa la API REST (`app/routers/*`), que lee las tablas `api_*` de
Postgres cargadas por `pipeline/load_postgres.py`. Antes este archivo
tenia sus propias consultas y su propia copia del umbral de "atipico":
dos definiciones de la misma cifra es exactamente el bug que este
proyecto se pasa el README evitando.

Diferencia con el REST: aqui el techo de filas es mas bajo
(`config.limite_max_mcp`, 50). Una respuesta de 200 filas es normal para
un cliente HTTP y no lo es para el contexto de un modelo.

Requiere Python >=3.10 (el SDK oficial de `mcp` lo exige). El resto del
pipeline esta fijado a Python 3.9 en el entorno local, por eso este
servidor vive con su propio entorno (ver api/requirements.txt).

Correr en local (stdio, para probar con un cliente MCP o el inspector):
    DATABASE_URL=postgresql://plomada:plomada@localhost:5432/plomada python -m app.mcp.server

Correr como servidor HTTP (lo que necesita el connector remoto de Claude):
    python -m app.mcp.server --http --port 8765
"""
from __future__ import annotations

import sys

from mcp.server import MCPServer

from app import consultas
from app.config import config

# Ninguna tool devuelve mas filas que esto, sin importar lo que pida el
# modelo: volcar una tabla al contexto no ayuda a responder.
LIMITE = config.limite_max_mcp

mcp = MCPServer(
    name="plomada",
    title="Plomada: riesgo en contratacion de obra publica (SECOP II)",
    instructions=(
        "Datos publicos de contratacion de obra publica en Colombia (SECOP II). "
        "'Riesgo' aqui significa indicio para priorizar investigacion periodistica "
        "y control social, NUNCA prueba de fraude. No afirmes que un contrato "
        "marcado es corrupto: di que presenta indicios y cuales son. "
        "Los mismos datos estan disponibles como API REST publica en /v1 "
        "(documentada en API.md) si el usuario prefiere consultarlos el mismo."
    ),
)


def _tope(limite):
    return max(1, min(int(limite or 20), LIMITE))


@mcp.tool()
def resumen_indicios() -> dict:
    """Cifras titulares del proyecto: contratos analizados, plata en riesgo
    por categoria de indicio, y las limitaciones que hay que decir en voz
    alta (cobertura de datos, que NO se puede afirmar). Usa esto primero
    para dar contexto antes de responder preguntas puntuales."""
    meta = consultas.meta()
    return {
        "titulares": consultas.titulares(),
        "indicios": consultas.indicios(),
        "cobertura": meta["cobertura"],
        "limitaciones": meta["limitaciones"],
        "umbral_atipico": "una bandera fuerte (peso 3) o 6 puntos acumulados",
    }


@mcp.tool()
def buscar_contratos_atipicos(
    entidad: str | None = None,
    departamento: str | None = None,
    tipo_contrato: str | None = None,
    valor_minimo: float | None = None,
    bandera: str | None = None,
    limite: int = 20,
) -> list[dict]:
    """Busca contratos marcados como atipicos (indicio fuerte, o 6+ puntos
    acumulados de banderas mas debiles). Filtros opcionales por entidad
    (coincidencia parcial), departamento, tipo_contrato (OBRA/INTERVENTORIA/
    CONSULTORIA/CONCESION/ASOCIACION PUBLICO PRIVADA), valor minimo en COP y
    una bandera concreta (usa `glosario_banderas` para ver los nombres).
    Devuelve como maximo 50 filas aunque se pida mas."""
    filas, _ = consultas.buscar_contratos(
        entidad=entidad,
        departamento=departamento,
        tipo_contrato=tipo_contrato,
        valor_min=valor_minimo,
        banderas=[bandera] if bandera else None,
        solo_atipicos=True,
        limite=_tope(limite),
    )
    return filas


@mcp.tool()
def detalle_contrato(id_contrato: str) -> dict:
    """Ficha completa de un contrato, con cada bandera encendida y la
    EVIDENCIA numerica que la disparo (cuantos proveedores comparten la
    cuenta, cuantos contratos hermanos hubo en 30 dias, etc.). Usa esto
    cuando tengas que explicar POR QUE un contrato esta marcado: sin la
    evidencia, no lo afirmes."""
    datos = consultas.contrato(id_contrato)
    if datos is None:
        return {"encontrado": False, "mensaje": "No existe el contrato '%s'" % id_contrato}
    return {"encontrado": True, "contrato": datos}


@mcp.tool()
def perfil_entidad(nombre_o_nit: str) -> dict:
    """Resumen de una entidad contratante: cuantos contratos tiene, cuanto
    ha adjudicado, cuantos de sus contratos estan marcados como atipicos,
    sus banderas mas frecuentes y sus principales proveedores. Recibe el
    nombre (coincidencia parcial) o el NIT exacto."""
    # NIT exacto primero: si acierta, se devuelve el perfil completo.
    detalle = consultas.entidad(nombre_o_nit)
    if detalle:
        return {"encontrado": True, "coincidencias": [detalle]}
    filas, _ = consultas.buscar_entidades(texto=nombre_o_nit, limite=5)
    if not filas:
        return {"encontrado": False, "mensaje": "Ninguna entidad coincide con '%s'" % nombre_o_nit}
    return {"encontrado": True, "coincidencias": filas}


@mcp.tool()
def buscar_proveedor(nombre_o_documento: str) -> dict:
    """Perfil de un proveedor y su red: cuantas obras e interventorias
    hace, a cuantas entidades le contrata, y con que otros proveedores
    esta unido por llaves que deberian ser unicas (cuenta bancaria,
    representante legal, domicilio). Que un proveedor haga obra E
    interventoria, o este unido a otro por dos o mas llaves, es el indicio
    fuerte. La cuenta bancaria nunca se publica: solo el hecho de que se
    comparte."""
    detalle = consultas.proveedor(nombre_o_documento)
    if detalle:
        return {"encontrado": True, "coincidencias": [detalle]}
    filas, _ = consultas.buscar_proveedores(texto=nombre_o_documento, limite=5)
    if not filas:
        return {"encontrado": False, "mensaje": "Ningun proveedor coincide con '%s'" % nombre_o_documento}
    return {"encontrado": True, "coincidencias": filas}


@mcp.tool()
def alertas_preadjudicacion(
    departamento: str | None = None,
    entidad: str | None = None,
    limite: int = 20,
) -> dict:
    """Licitaciones de obra publica que TODAVIA aceptan ofertas y presentan
    banderas. A diferencia del resto de las tools, esto no mira contratos
    firmados: mientras el proceso sigue abierto, una observacion al pliego
    puede cambiar el resultado. Aclara siempre que solo el universo
    'accionable' admite una observacion con efecto hoy."""
    if not consultas.hay_alertas():
        return {
            "disponible": False,
            "mensaje": (
                "No hay un snapshot de licitaciones abiertas cargado en la base. "
                "Dilo tal cual: no inventes procesos abiertos."
            ),
        }
    filas, total = consultas.buscar_alertas(
        universo="accionable", departamento=departamento,
        entidad=entidad, min_banderas=1, limite=_tope(limite),
    )
    return {
        "disponible": True,
        "resumen": consultas.resumen_alertas(),
        "accionables_con_alerta": total,
        "procesos": filas,
    }


@mcp.tool()
def glosario_banderas() -> list[dict]:
    """Las 26 banderas con su peso (3 = indicio fuerte, 1 = contexto), su
    grupo y que significa cada una. Usa esto para explicar en palabras que
    quiere decir una bandera que aparece en un contrato, en vez de citar
    el nombre de la columna."""
    return consultas.glosario()


def main():
    if "--http" in sys.argv:
        port = 8765
        if "--port" in sys.argv:
            port = int(sys.argv[sys.argv.index("--port") + 1])
        mcp.run(transport="streamable-http", port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
