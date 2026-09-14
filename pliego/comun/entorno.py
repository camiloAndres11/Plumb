"""Carga `.env` de la raiz del repo en os.environ, sin pisar lo que ya este.

Sin dependencia de python-dotenv: solo lineas CLAVE=valor, comentarios con #
y lineas vacias. Lo importa pliego/comun/fuente.py, asi que basta con
`uvicorn demo.app:app` para que PLIEGO_FUENTE y CROMA_API_KEY salgan del
archivo. Las variables ya presentes en el entorno mandan sobre el archivo,
para poder cambiar una cosa puntual desde la linea de comandos.
"""
from __future__ import annotations

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ARCHIVO = RAIZ / ".env"


def cargar(archivo: Path = ARCHIVO) -> dict[str, str]:
    """Devuelve lo que cargo (solo lo que no existia ya en el entorno)."""
    cargado = {}
    if not archivo.exists():
        return cargado
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave, valor = clave.strip(), valor.strip().strip("'\"")
        if clave and valor and clave not in os.environ:
            os.environ[clave] = valor
            cargado[clave] = valor
    return cargado


cargar()
