"""Ingesta del universo de CONSTRUCCION del SECOP II a disco local.

De los 5.975.627 contratos del SECOP II, 5.123.891 son prestacion de
servicios (nomina paralela), no obra publica. El universo relevante aqui
son ~78k contratos:

    Obra                          52.355
    Interventoria                 13.074
    Consultoria                   11.482
    Asociacion Publico Privada       715
    Concesion                        238

Interventoria y consultoria van incluidas A PROPOSITO: la captura de la
interventoria (que el que vigila la obra pertenezca a la misma red que el
que la construye) es el mecanismo central del fraude en obra publica, y
solo se ve si tienes ambos lados.

Se descarga un archivo por tipo para que cada uno sea reanudable por
separado. Salida: data/raw/{contratos,procesos}/<tipo>.jsonl
"""
from __future__ import annotations

import os
import sys
import time
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import soda

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")

TIPOS = [
    "Obra",
    "Interventoría",
    "Consultoría",
    "Concesión",
    "Asociación Público Privada",
]

DATASETS = [
    ("contratos", "jbjy-vk9h"),  # SECOP II - Contratos Electronicos
    ("procesos", "p6dx-8zbt"),   # SECOP II - Procesos de Contratacion
]


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return "".join(c if c.isalnum() else "_" for c in s.lower()).strip("_")


def main():
    t_start = time.time()
    for folder, dataset in DATASETS:
        out_dir = os.path.join(RAW, folder)
        os.makedirs(out_dir, exist_ok=True)
        print("\n%s== %s (%s) ==" % ("", folder.upper(), dataset), flush=True)
        for tipo in TIPOS:
            # Filtro por igualdad simple: el in() compuesto tumba la API.
            where = "tipo_de_contrato='%s'" % tipo.replace("'", "''")
            path = os.path.join(out_dir, slug(tipo) + ".jsonl")
            n = soda.dump(dataset, path, where=where, label="%s/%s" % (folder, slug(tipo)))
            print("  -> %s: %d filas" % (tipo, n), flush=True)
    print("\nTOTAL %.1f min" % ((time.time() - t_start) / 60.0), flush=True)


if __name__ == "__main__":
    main()
