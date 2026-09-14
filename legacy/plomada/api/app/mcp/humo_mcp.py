"""Prueba de humo manual del servidor MCP -- no es parte de la suite de
pytest del pipeline (ese vive en Python 3.9; esto exige >=3.10) ni de la
de api/tests (esa no toca la base).

Necesita un Postgres cargado:
    docker compose up -d db
    export DATABASE_URL=postgresql://plomada:plomada@localhost:5432/plomada
    python pipeline/load_postgres.py

    python -m venv .venv-mcp && .venv-mcp/bin/pip install -r api/requirements.txt
    .venv-mcp/bin/python api/app/mcp/humo_mcp.py           # via stdio
    .venv-mcp/bin/python -m app.mcp.server --http &          # via http (desde api/)
    .venv-mcp/bin/python api/app/mcp/humo_mcp.py --http
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

# .../api  -- el servidor se importa como `app.mcp.server` porque comparte
# app.consultas con el API REST, asi que su raiz de import es api/, no
# el directorio del archivo.
API = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ESPERADAS = {
    "resumen_indicios",
    "buscar_contratos_atipicos",
    "detalle_contrato",
    "perfil_entidad",
    "buscar_proveedor",
    "alertas_preadjudicacion",
    "glosario_banderas",
}


def _json(resultado):
    """Payload de una tool que devuelve UN objeto."""
    return json.loads(resultado.content[0].text)


def _filas(resultado):
    """Payload de una tool que devuelve una LISTA. El SDK manda una fila por
    bloque de contenido, no un bloque con la lista entera."""
    return [json.loads(c.text) for c in resultado.content]


async def probar(session):
    info = await session.initialize()
    print("conectado a:", info.server_info.name)

    tools = await session.list_tools()
    nombres = {t.name for t in tools.tools}
    print("tools:", sorted(nombres))
    assert ESPERADAS <= nombres, "faltan tools: %s" % sorted(ESPERADAS - nombres)

    data = _json(await session.call_tool("resumen_indicios", {}))
    assert data["titulares"], "resumen_indicios no trajo titulares"
    assert data["limitaciones"], "resumen_indicios no trajo limitaciones"
    print("resumen_indicios: OK (%d titulares, %d limitaciones)"
          % (len(data["titulares"]), len(data["limitaciones"])))

    glosario = _filas(await session.call_tool("glosario_banderas", {}))
    assert len(glosario) == 26, "el glosario deberia tener 26 banderas, trajo %d" % len(glosario)
    assert all(g["glosa"] and g["peso"] in (1, 2, 3) for g in glosario)
    print("glosario_banderas: OK (26 banderas con peso y glosa)")

    r = await session.call_tool(
        "buscar_contratos_atipicos", {"departamento": "CUNDINAMARCA", "limite": 3}
    )
    assert len(r.content) == 3
    print("buscar_contratos_atipicos: OK (%d filas)" % len(r.content))

    # La ficha completa tiene que traer la evidencia de cada bandera: es la
    # regla del proyecto (sin evidencia no se publica) y el motivo de que
    # este tool exista.
    primero = json.loads(r.content[0].text)
    data = _json(await session.call_tool("detalle_contrato", {"id_contrato": primero["id_contrato"]}))
    assert data["encontrado"], "detalle_contrato no encontro un contrato que acaba de listar"
    assert data["contrato"]["banderas"], "un contrato atipico sin banderas encendidas"
    print("detalle_contrato: OK (%d banderas con glosa y evidencia)"
          % len(data["contrato"]["banderas"]))

    data = _json(await session.call_tool("perfil_entidad", {"nombre_o_nit": "bogota"}))
    assert data["encontrado"]
    print("perfil_entidad('bogota'): OK (%d coincidencias)" % len(data["coincidencias"]))

    data = _json(await session.call_tool("perfil_entidad", {"nombre_o_nit": "esto-no-existe-en-secop"}))
    assert not data["encontrado"]
    print("perfil_entidad(inexistente): OK (reporta no encontrado, no inventa datos)")

    data = _json(await session.call_tool("buscar_proveedor", {"nombre_o_documento": "consorcio"}))
    assert data["encontrado"], "no encontro ningun proveedor que contenga 'consorcio'"
    print("buscar_proveedor('consorcio'): OK (%d coincidencias)" % len(data["coincidencias"]))

    # Opcional a proposito: si nadie corrio pipeline/alertas.py, la tool
    # tiene que decirlo en vez de inventarse procesos abiertos.
    data = _json(await session.call_tool("alertas_preadjudicacion", {"limite": 3}))
    if data["disponible"]:
        print("alertas_preadjudicacion: OK (%d accionables con alerta)"
              % data["accionables_con_alerta"])
    else:
        print("alertas_preadjudicacion: OK (reporta que no hay snapshot cargado)")


async def main():
    if "--http" in sys.argv:
        async with streamable_http_client("http://127.0.0.1:8765/mcp") as (read, write):
            async with ClientSession(read, write) as session:
                await probar(session)
    else:
        entorno = dict(os.environ)
        entorno["PYTHONPATH"] = API + os.pathsep + entorno.get("PYTHONPATH", "")
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "app.mcp.server"], cwd=API, env=entorno,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await probar(session)
    print("\nTODO OK")


if __name__ == "__main__":
    asyncio.run(main())
