"""Ingesta diaria de licitaciones de obra publica que SIGUEN ABIERTAS.

A diferencia de ingest.py (que trae contratos YA ADJUDICADOS para el
analisis retrospectivo), este script trae procesos que TODAVIA ACEPTAN
OFERTAS. El objetivo es alertar mientras la licitacion se puede observar,
no despues de que se firmo.

"Abierto" se definio MIDIENDO la plataforma en vivo el 2026-08-22, no por
suposicion:

    estado_del_procedimiento in ('Publicado','Abierto') AND adjudicado='No'

En el universo de construccion eso dio 557 procesos ese dia (381 obra +
96 interventoria + 73 consultoria + 7 concesion). El filtro NO exige que
la fecha de cierre siga vigente: los que ya vencieron (1.369 en el
universo total sin filtrar por tipo) son procesos "zombie" que la entidad
no actualizo, y esa opacidad es en si misma una senal que se conserva, no
se descarta (ver f_cierre_vencido en 30_procesos_abiertos.sql).

El dataset PUBLICA VARIAS FILAS IDENTICAS por proceso incluso en este
universo chico -- un proceso trajo 21 copias exactas en la prueba real.
Se colapsa en el paso SQL siguiente, igual que en 01_stage.sql.

Guarda un snapshot fechado en data/raw/abiertos/YYYY-MM-DD.jsonl y NUNCA
lo borra: pipeline/alertas.py compara el snapshot de hoy contra el de
ayer para detectar addendas que mueven la fecha de cierre. En la primera
corrida no hay snapshot anterior, asi que esa bandera especifica queda en
NULL (no en falso) hasta el segundo dia.
"""
from __future__ import annotations

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import soda

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "abiertos")

PROCESOS = "p6dx-8zbt"  # SECOP II - Procesos de Contratacion

TIPOS = [
    "Obra",
    "Interventoría",
    "Consultoría",
    "Concesión",
    "Asociación Público Privada",
]


def where_abiertos() -> str:
    vals = ",".join("'" + t.replace("'", "''") + "'" for t in TIPOS)
    return (
        "tipo_de_contrato in(%s) AND adjudicado='No' "
        "AND estado_del_procedimiento in('Publicado','Abierto')" % vals
    )


def main():
    os.makedirs(RAW, exist_ok=True)
    hoy = datetime.date.today().isoformat()
    path = os.path.join(RAW, hoy + ".jsonl")
    w = where_abiertos()
    print("snapshot %s" % hoy, flush=True)
    print("filtro: %s" % w, flush=True)
    n = soda.dump(PROCESOS, path, where=w, label="abiertos/%s" % hoy)
    print("guardado: %d filas -> %s" % (n, path), flush=True)


if __name__ == "__main__":
    main()
