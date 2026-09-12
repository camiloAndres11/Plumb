#!/usr/bin/env python3
"""Compone la hoja de estilos servida (plomada/static/estilo.css) a partir de
las piezas de diseno del proyecto. Ver design/VENDOR.md.

Por que existe: design/modernist/ es una copia FIEL del sistema Modernist
bajado de claude.ai/design y NO se edita a mano (VENDOR.md lo prohibe). Pero
esa copia trae un @import a fonts.googleapis.com, y este sitio no puede
depender de un CDN externo en tiempo de carga (test_privacy.py y el criterio
del proyecto). La solucion no es parchear modernist/styles.css: es generar,
en un paso de build separado, el artefacto que de verdad se sirve, cosiendo:

  1. design/plomada/fuentes.css   - @font-face de Archivo, auto-hospedada
  2. design/modernist/styles.css  - SIN su linea de @import (se filtra aqui)
  3. design/plomada/dataviz.css   - extension de color/graficos del proyecto
  4. design/plomada/sitio.css     - layout y componentes de pagina del proyecto
  5. design/plomada/tema.css      - delta de tokens de la banda oscura

Y, aparte, plomada/static/landing.css para la landing comercial de la raiz
(/), que tiene su propio shell y NO carga Modernist ni sitio.css:

  1. design/plomada/fuentes.css   - la misma Archivo auto-hospedada
  2. design/plomada/landing.css   - la hoja de la landing (ver su cabecera)

Asi modernist/ se puede volver a bajar completo el dia que el sistema cambie
(paso 1 de VENDOR.md) sin que el sitio vuelva a pedirle nada a Google, y sin
tocar un solo caracter dentro de modernist/.

Uso:  python3 design/construir.py
Salida: plomada/static/estilo.css y plomada/static/landing.css (se
sobreescriben siempre; no se editan a mano — cualquier cambio de estilo entra
por una de las piezas de arriba).
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
DESIGN = RAIZ / "design"
FUENTES = DESIGN / "plomada" / "fuentes.css"
MODERNIST = DESIGN / "modernist" / "styles.css"
DATAVIZ = DESIGN / "plomada" / "dataviz.css"
SITIO = DESIGN / "plomada" / "sitio.css"
# tema.css va de ULTIMO: declara el delta de tokens de la banda oscura y tiene
# que ganarle a Modernist y a sitio.css sin depender de especificidad
# accidental (docs/PLAN_TEMA_API_MCP.md §4.1).
TEMA = DESIGN / "plomada" / "tema.css"
SALIDA = RAIZ / "plomada" / "static" / "estilo.css"
# La landing comercial (/) no comparte shell con el resto del sitio: solo
# lleva la fuente y su propia hoja.
LANDING = DESIGN / "plomada" / "landing.css"
SALIDA_LANDING = RAIZ / "plomada" / "static" / "landing.css"

# Cualquier @import (a una URL) se filtra: es exactamente lo que hay que
# quitarle al vendor sin tocar el archivo vendorizado. Si algun dia
# modernist/styles.css agrega OTRO @import externo, este build lo atrapa
# tambien en vez de dejarlo pasar en silencio.
_IMPORT_URL = re.compile(r"^\s*@import\s+url\(['\"]?https?://.*$", re.MULTILINE)

CABECERA = """/* GENERADO por design/construir.py — NO EDITAR A MANO.
 * Cambios de estilo entran por una de estas cinco piezas, nunca aqui:
 *   1. design/plomada/fuentes.css   (Archivo auto-hospedada)
 *   2. design/modernist/styles.css  (vendor, ver design/VENDOR.md — no se parchea)
 *   3. design/plomada/dataviz.css   (extension de color/graficos del proyecto)
 *   4. design/plomada/sitio.css     (layout y componentes de pagina del proyecto)
 *   5. design/plomada/tema.css      (delta de tokens de la banda oscura)
 * Para regenerar: python3 design/construir.py
 */
"""

CABECERA_LANDING = """/* GENERADO por design/construir.py — NO EDITAR A MANO.
 * Hoja de la landing comercial de Pliego (/). Dos piezas, nada mas:
 *   1. design/plomada/fuentes.css   (Archivo auto-hospedada)
 *   2. design/plomada/landing.css   (la landing: tokens --ad-*, layout, movimiento)
 * No carga Modernist ni sitio.css: la landing tiene su propio shell.
 * Para regenerar: python3 design/construir.py
 */
"""


def leer(ruta):
    if not ruta.exists():
        sys.exit(f"falta {ruta.relative_to(RAIZ)} — no se puede componer estilo.css")
    return ruta.read_text(encoding="utf-8")


def main():
    fuentes = leer(FUENTES)
    modernist = leer(MODERNIST)
    dataviz = leer(DATAVIZ)
    sitio = leer(SITIO)
    tema = leer(TEMA)

    filtrado, n = _IMPORT_URL.subn("", modernist)
    if n == 0:
        print("AVISO: modernist/styles.css no traia ningun @import a una URL externa "
              "(¿ya se quito upstream? revisa si este filtro sigue haciendo falta)",
              file=sys.stderr)
    else:
        print(f"quitadas {n} linea(s) de @import externo de modernist/styles.css", file=sys.stderr)
    # el @import, si existia, tenia que ir de primero en el archivo (regla
    # CSS): confirmamos que no quedo ningun otro rastro de CDN de fuentes.
    if "fonts.googleapis.com" in filtrado or "fonts.gstatic.com" in filtrado:
        sys.exit("modernist/styles.css sigue mencionando un CDN de fuentes despues del filtro — revisa a mano")

    piezas = [CABECERA, fuentes.strip(), filtrado.strip(), dataviz.strip(),
              sitio.strip(), tema.strip(), ""]
    salida = "\n\n".join(piezas)

    if "https://" in salida or "http://" in salida:
        sys.exit("el estilo.css compuesto todavia contiene una URL externa — no se escribe")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(salida, encoding="utf-8")
    print(f"escrito {SALIDA.relative_to(RAIZ)} ({len(salida)} bytes, sin URLs externas)")

    landing = "\n\n".join([CABECERA_LANDING, fuentes.strip(), leer(LANDING).strip(), ""])
    if "https://" in landing or "http://" in landing:
        sys.exit("el landing.css compuesto contiene una URL externa — no se escribe")
    SALIDA_LANDING.write_text(landing, encoding="utf-8")
    print(f"escrito {SALIDA_LANDING.relative_to(RAIZ)} ({len(landing)} bytes, sin URLs externas)")


if __name__ == "__main__":
    main()
