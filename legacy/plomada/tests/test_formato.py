"""Corredor sin pytest (no esta instalado en este equipo) sobre el fixture
compartido tests/formato_casos.json.

Verifica que plomada/data.py — el comportamiento de referencia — sigue
produciendo lo mismo que quedo registrado en el fixture. El otro lado del
mismo fixture es test_formato.mjs, que corre las mismas entradas contra
plomada/static/formato.js. Si un caso falla en uno pero no en el otro, las
dos implementaciones divergieron.

Corre con: python3 tests/test_formato.py
"""
import json
import sys
from pathlib import Path

import data as D  # plomada/ esta en pythonpath (pyproject.toml)

RAIZ = Path(__file__).parent.parent

CASOS = json.loads((RAIZ / "tests" / "formato_casos.json").read_text(encoding="utf-8"))


def main():
    fallos = 0
    for i, c in enumerate(CASOS):
        fn = getattr(D, c["fn"])
        try:
            obtenido = fn(*c["args"])
        except Exception as e:  # una excepcion tambien es un fallo, no un crash del corredor
            obtenido = f"<excepcion: {e!r}>"
        if obtenido != c["esperado"]:
            fallos += 1
            print(f"  FALLO caso {i}: {c['fn']}({c['args']!r}) = {obtenido!r}, "
                  f"esperaba {c['esperado']!r}")
    if fallos:
        print(f"\n{fallos} de {len(CASOS)} casos fallaron")
        sys.exit(1)
    print(f"{len(CASOS)} casos OK (python / data.py)")


if __name__ == "__main__":
    main()
