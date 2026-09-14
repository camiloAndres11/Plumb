"""Cliente minimo para la API SoDA de datos.gov.co.

Aprendizajes duros medidos contra la API real (no son suposiciones):

  * Las AGREGACIONES grandes ($group/$select=count con filtros compuestos)
    se cuelgan por timeout. Nunca dependemos de ellas en el camino critico.
  * Una pagina de 10.000 filas del dataset de contratos pesa ~37 MB y baja
    en ~30 s. Eso si funciona de forma estable.
  * Conclusion de arquitectura: se traen las filas crudas a disco y TODA la
    analitica se hace en local con DuckDB.

Por eso la paginacion aqui NO usa count(): pagina hasta que llega una
pagina mas corta que el tamano de pagina. Reanudable.
"""
from __future__ import annotations

import json
import os
import sys
import time

import requests

DOMAIN = "https://www.datos.gov.co"
PAGE = 10000
MAX_RETRIES = 5
TIMEOUT = 240


def _get(dataset, params, timeout=TIMEOUT):
    url = "%s/resource/%s.json" % (DOMAIN, dataset)
    delay = 5.0
    last = None
    for attempt in range(1, MAX_RETRIES + 1):
        t0 = time.time()
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            last = "HTTP %s: %s" % (r.status_code, r.text[:200])
        except requests.RequestException as exc:
            last = repr(exc)
        sys.stderr.write(
            "    reintento %d/%d (fallo tras %.0fs: %s)\n"
            % (attempt, MAX_RETRIES, time.time() - t0, last)
        )
        sys.stderr.flush()
        time.sleep(delay)
        delay = min(delay * 2, 60)
    raise RuntimeError("fallo definitivo en %s %s: %s" % (dataset, params, last))


def dump(dataset, out_path, where=None, page=PAGE, label=""):
    """Descarga a JSONL paginando por $offset sobre $order=:id.

    Sin count() previo: para cuando una pagina vuelve incompleta.
    Reanuda si el archivo ya existe (trunca a multiplo de pagina para no
    dejar una pagina a medias).
    """
    done = 0
    if os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8") as fh:
            done = sum(1 for _ in fh)
        keep = (done // page) * page
        if keep != done:
            with open(out_path, "r", encoding="utf-8") as fh:
                lines = [fh.readline() for _ in range(keep)]
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.writelines(lines)
            done = keep
        if done:
            print("  [%s] reanudando en offset %d" % (label or dataset, done), flush=True)

    with open(out_path, "a" if done else "w", encoding="utf-8") as fh:
        offset = done
        while True:
            params = {"$order": ":id", "$limit": page, "$offset": offset}
            if where:
                params["$where"] = where
            t0 = time.time()
            rows = _get(dataset, params)
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            offset += len(rows)
            print(
                "  [%s] +%d -> %d filas (%.0fs)"
                % (label or dataset, len(rows), offset, time.time() - t0),
                flush=True,
            )
            if len(rows) < page:
                break
    return offset
