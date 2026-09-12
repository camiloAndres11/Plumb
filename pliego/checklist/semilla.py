"""Trazabilidad al PDF: localiza cada cita en su pagina y renderiza la pagina.

La extraccion de requisitos es manual (requisitos_*.json). Lo que SI es
automatico es esto: para cada requisito, encontrar las coordenadas del
fragmento citado dentro de la pagina del PDF (para poder resaltarlo) y
renderizar esa pagina a PNG para verla en el navegador sin depender de un
visor de PDF.

Usa poppler (pdftotext -bbox-layout, pdftoppm), que es herramienta del
sistema y no una dependencia de Python. Sus salidas se commitean, asi que
solo hay que correrlo cuando cambian las citas:

    python -m pliego.checklist.semilla

Salidas:
  fixtures/paginas/p<N>.png     paginas citadas, a 72 dpi
  fixtures/citas_bbox.json      {id_requisito: {pagina, ancho, alto, cajas: [[x0,y0,x1,y1], ...]}}
                                cajas en fraccion 0-1 del ancho/alto de la pagina
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REQUISITOS = FIXTURES / "requisitos_SI-LP-004-2021.json"
PAGINAS = FIXTURES / "paginas"
SALIDA = FIXTURES / "citas_bbox.json"
NS = {"x": "http://www.w3.org/1999/xhtml"}


def normalizar(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def palabras_pagina(pdf: Path, n: int) -> tuple[float, float, list[tuple[str, float, float, float, float]]]:
    xml = subprocess.run(["pdftotext", "-bbox-layout", "-f", str(n), "-l", str(n), str(pdf), "-"],
                         check=True, capture_output=True, text=True).stdout
    raiz = ET.fromstring(xml)
    pag = raiz.find(".//x:page", NS)
    w, h = float(pag.get("width")), float(pag.get("height"))
    out = []
    for word in pag.iter("{http://www.w3.org/1999/xhtml}word"):
        out.append((normalizar(word.text or ""), float(word.get("xMin")), float(word.get("yMin")),
                    float(word.get("xMax")), float(word.get("yMax"))))
    return w, h, [p for p in out if p[0]]


def localizar(cita: str, palabras) -> list[tuple[float, float, float, float]]:
    """Ventana deslizante: la secuencia de tokens de la cita contra la de la
    pagina, aceptando >= 80 % de coincidencias. Devuelve las cajas por linea."""
    tokens = [t for t in (normalizar(x) for x in cita.split()) if t]
    n = len(tokens)
    if n == 0 or len(palabras) < n:
        return []
    mejor, mejor_i = 0, None
    for i in range(len(palabras) - n + 1):
        aciertos = sum(1 for j in range(n) if palabras[i + j][0] == tokens[j])
        if aciertos > mejor:
            mejor, mejor_i = aciertos, i
    if mejor_i is None or mejor / n < 0.8:
        return []
    # una caja por linea (agrupar por yMin parecido)
    cajas: list[list[float]] = []
    for _, x0, y0, x1, y1 in palabras[mejor_i:mejor_i + n]:
        if cajas and abs(cajas[-1][1] - y0) < 3:
            cajas[-1][0] = min(cajas[-1][0], x0); cajas[-1][2] = max(cajas[-1][2], x1)
            cajas[-1][1] = min(cajas[-1][1], y0); cajas[-1][3] = max(cajas[-1][3], y1)
        else:
            cajas.append([x0, y0, x1, y1])
    return [tuple(c) for c in cajas]


def main() -> int:
    if not shutil.which("pdftotext") or not shutil.which("pdftoppm"):
        print("falta poppler (pdftotext/pdftoppm); los fixtures commiteados siguen sirviendo")
        return 1
    datos = json.loads(REQUISITOS.read_text(encoding="utf-8"))
    pdf = FIXTURES / datos["proceso"]["pdf"]
    PAGINAS.mkdir(exist_ok=True)
    salida, cache = {}, {}
    paginas = sorted({r["pagina"] for r in datos["requisitos"]} | {l["pagina"] for l in datos["proceso"]["lotes"]})
    for n in paginas:
        cache[n] = palabras_pagina(pdf, n)
        subprocess.run(["pdftoppm", "-r", "72", "-png", "-f", str(n), "-l", str(n), str(pdf),
                        str(PAGINAS / "p")], check=True)
        # pdftoppm nombra p-NN.png con ceros a la izquierda; normalizamos a pN.png
        for f in PAGINAS.glob("p-*.png"):
            f.rename(PAGINAS / f"p{int(f.stem.split('-')[1])}.png")
    sin_caja = []
    for r in datos["requisitos"]:
        w, h, palabras = cache[r["pagina"]]
        cajas = localizar(r["cita"], palabras)
        if not cajas:
            sin_caja.append(r["id"])
        salida[r["id"]] = {"pagina": r["pagina"], "ancho": w, "alto": h,
                           "cajas": [[round(x0 / w, 4), round(y0 / h, 4), round(x1 / w, 4), round(y1 / h, 4)]
                                     for x0, y0, x1, y1 in cajas]}
    SALIDA.write_text(json.dumps(salida, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(salida)} citas, {len(paginas)} paginas renderizadas; sin caja: {sin_caja or 'ninguna'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
