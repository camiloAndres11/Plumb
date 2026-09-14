"""Servidor de desarrollo para plomada/site/.

    python3 plomada/servir.py            # http://localhost:8765

Existe porque `python -m http.server` NO sirve el sitio dinamico: las fichas
y los municipios son rutas que no tienen un archivo detras
(/contrato/co1-pccntr-8462295/ se resuelve contra contrato/index.html, que
luego se hidrata del API). En produccion eso lo hace el host con las reglas
de site/_redirects; aqui se emulan para poder probar las URLs de verdad.

Si abres el sitio con un http.server pelado, la portada y el tablero
funcionan pero toda ficha da 404. No es un bug del build.
"""
from __future__ import annotations

import argparse
import http.server
import os
from pathlib import Path

SITE = Path(__file__).parent / "site"

# Mismas rutas que build.py escribe en site/_redirects. Si se agrega una
# vista dinamica alla, agregarla aqui tambien.
DINAMICAS = ("/contrato/", "/municipio/")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(SITE), **k)

    def translate_path(self, path):
        destino = super().translate_path(path)
        falta = not os.path.exists(destino) or (
            os.path.isdir(destino) and not os.path.exists(os.path.join(destino, "index.html")))
        if falta:
            for prefijo in DINAMICAS:
                if path.startswith(prefijo):
                    return str(SITE / prefijo.strip("/") / "index.html")
        return destino

    def log_message(self, formato, *args):
        print("  %s" % (formato % args))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-p", "--puerto", type=int, default=8765)
    args = ap.parse_args()

    if not SITE.exists():
        raise SystemExit("No hay plomada/site/. Corre antes: python3 plomada/build.py")

    print(f"Plomada en http://localhost:{args.puerto}")
    print("  reescribiendo %s como en produccion (site/_redirects)" % ", ".join(DINAMICAS))
    try:
        http.server.HTTPServer(("127.0.0.1", args.puerto), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nlisto")


if __name__ == "__main__":
    main()
