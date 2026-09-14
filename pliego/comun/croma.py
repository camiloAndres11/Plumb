"""Cliente de la API de Croma (https://api.croma.run), la fuente de SECOP.

Un solo lugar que habla HTTP con Croma, como pipeline/api_cliente.py lo es
para el API de Plomada. Ver docs/enfoques/croma.md para el mapa completo.

Uso:
    from pliego.comun.croma import CromaCliente, disponible

    if disponible():                      # hay CROMA_API_KEY en el entorno
        api = CromaCliente()
        r = api.llamar("/co/secop/processes-search/v1", {"query": "obra", "per_page": 5})
        for fila in api.paginar("/co/secop/contracts-search/v1", {"department": "Santander"}):
            ...

Contrato de la API (medido contra la doc oficial, docs.usecroma.com):
    - Todo endpoint es POST con cuerpo JSON y `Authorization: Bearer <llave>`.
    - Las busquedas a dataset paginan con `page` (desde 1) y `per_page` (tope
      100), y devuelven `total`, `total_pages`, `as_of` y `results[]`.
    - 401 -> llave ausente o invalida (no se reintenta).
    - 402 -> creditos del mes agotados (no se reintenta: no se cobra fuera
      del plan, simplemente deja de responder hasta el reinicio mensual).
    - 429 -> tope por hora; trae `Retry-After` en segundos. Se espera y se
      reintenta. Cada intento que llega al servidor cuenta, asi que no se
      reintenta antes de tiempo.
    - Una consulta a dataset cuesta 1 credito; una en vivo, 10. El saldo
      viene en `X-RateLimit-Remaining` de cada respuesta y el cliente lo
      recuerda en `.creditos_restantes` para que quien lo use lo muestre.

Medido el 2026-09-13 con llave real (no es lo que dice la doc):
    - Las busquedas SECOP a dataset tardan entre 1,5 s y 30 s por pagina,
      no milisegundos; la primera de cada tipo es la lenta. Por eso el
      timeout es de 120 s y fuente.py cachea en disco y descarga en paralelo.
    - Una llamada que el cliente abandona por timeout SI se cobra si el
      servidor la termino despues (se vio en el saldo). Abandonar pronto no
      ahorra creditos.
    - `as_of` de SECOP fue el mismo dia a las 10:11 UTC: se refresca a diario.
    - El catalogo (/catalog) anuncia "100 requests / 24h" por endpoint, pero
      la respuesta real solo trae la politica mensual de creditos
      (`ratelimit-policy: "credits";q=5000;w=2592000`). La cabecera manda.

Sonda:
    python -m pliego.comun.croma

    Gasta 4 creditos (una consulta de 2 filas a cada busqueda que usa
    Pliego) e imprime los campos reales de cada registro. Es la manera de
    confirmar lo que la doc no fija: el enlace contrato -> proceso y si el
    contrato trae los conteos de oferentes. Correrla antes de fiarse del
    mapeo (pliego/comun/mapeo_croma.py).
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Iterator

import requests

BASE_URL_DEFAULT = "https://api.croma.run"
POR_PAGINA_MAX = 100
TIMEOUT = 120
REINTENTOS_429 = 3
REINTENTOS_TIMEOUT = 2   # una pagina SECOP a veces pasa de 120 s; la siguiente suele salir
ESPERA_429_DEFECTO = 5  # segundos, si el 429 no trae Retry-After


class CromaError(Exception):
    """Croma respondio con un error explicito, o la llamada fallo despues de
    agotar los reintentos."""

    def __init__(self, mensaje, codigo=None, estado=None):
        super().__init__(mensaje)
        self.codigo = codigo
        self.estado = estado


class ClaveInvalida(CromaError):
    """401: no hay llave, esta mal formada o fue revocada."""


class SinCreditos(CromaError):
    """402: los creditos del mes se agotaron. No tiene sentido reintentar
    hasta `reinicio` (ISO, de X-RateLimit-Reset)."""

    def __init__(self, mensaje, reinicio=None):
        super().__init__(mensaje, codigo="billing_error", estado=402)
        self.reinicio = reinicio


def llave() -> str | None:
    return os.environ.get("CROMA_API_KEY") or None


def disponible() -> bool:
    """Hay llave en el entorno. No prueba la red: para eso esta la sonda."""
    return llave() is not None


class CromaCliente:
    def __init__(self, llave_api: str | None = None, base_url: str | None = None, session=None,
                 dormir=time.sleep):
        self.llave = llave_api or llave()
        if not self.llave:
            raise ClaveInvalida("falta CROMA_API_KEY (llave de organizacion croma_live_...)")
        self.base_url = (base_url or os.environ.get("CROMA_API_URL") or BASE_URL_DEFAULT).rstrip("/")
        self.session = session or requests.Session()
        self._dormir = dormir
        self.creditos_restantes: int | None = None
        self.llamadas = 0

    # ------------------------------------------------------------ una llamada
    def llamar(self, ruta: str, cuerpo: dict | None = None) -> dict:
        """POST a `ruta` con `cuerpo`; devuelve `data` de la respuesta (donde
        vienen `as_of` y `results`), o el JSON entero si no hay envoltura."""
        url = self.base_url + "/" + ruta.lstrip("/")
        cabeceras = {"Authorization": "Bearer " + self.llave, "Content-Type": "application/json"}
        timeouts = 0
        for intento in range(REINTENTOS_429 + REINTENTOS_TIMEOUT + 1):
            try:
                r = self.session.post(url, json=cuerpo or {}, headers=cabeceras, timeout=TIMEOUT)
            except requests.Timeout as e:
                timeouts += 1
                if timeouts > REINTENTOS_TIMEOUT:
                    raise CromaError("timeout persistente en %s: %s" % (ruta, e), codigo="timeout") from e
                continue
            except requests.RequestException as e:
                raise CromaError("no se pudo llamar a %s: %s" % (ruta, e)) from e
            self.llamadas += 1
            self._anotar_saldo(r)
            if r.status_code == 429 and intento < REINTENTOS_429:
                self._dormir(_retry_after(r))
                continue
            if r.status_code >= 400:
                raise _error_de(r, ruta)
            try:
                doc = r.json()
            except ValueError as e:
                raise CromaError("respuesta no JSON de %s" % ruta, estado=r.status_code) from e
            return doc.get("data", doc) if isinstance(doc, dict) else doc
        raise CromaError("429 persistente en %s" % ruta, codigo="rate_limited", estado=429)

    def _anotar_saldo(self, r):
        v = r.headers.get("X-RateLimit-Remaining")
        if v is not None and str(v).isdigit():
            self.creditos_restantes = int(v)

    # -------------------------------------------------------------- paginar
    def paginar(self, ruta: str, cuerpo: dict, max_paginas: int | None = None,
                por_pagina: int = POR_PAGINA_MAX) -> Iterator[dict]:
        """Recorre `results` de una busqueda a dataset pagina por pagina.

        Para cuando `total_pages` se alcanza, cuando una pagina viene vacia o
        cuando se llega a `max_paginas` (cada pagina es 1 credito: el tope
        es el freno de mano, no un detalle). Cada fila sale con `_as_of`,
        el de su pagina, para saber de cuando es lo que se muestra."""
        max_paginas = max_paginas or int(os.environ.get("CROMA_MAX_PAGINAS", "30"))
        pagina = 1
        while pagina <= max_paginas:
            data = self.llamar(ruta, {**cuerpo, "page": pagina, "per_page": por_pagina})
            filas = data.get("results") or []
            for fila in filas:
                if isinstance(fila, dict):
                    fila.setdefault("_as_of", data.get("as_of"))
                yield fila
            total_paginas = data.get("total_pages")
            if not filas or (total_paginas is not None and pagina >= int(total_paginas)):
                return
            pagina += 1


def _retry_after(r) -> float:
    v = r.headers.get("Retry-After")
    try:
        return max(0.0, float(v)) if v is not None else ESPERA_429_DEFECTO
    except ValueError:
        return ESPERA_429_DEFECTO


def _error_de(r, ruta) -> CromaError:
    codigo = mensaje = None
    try:
        err = r.json().get("error") or {}
        codigo, mensaje = err.get("code") or err.get("codigo"), err.get("message") or err.get("mensaje")
    except ValueError:
        pass
    mensaje = "%s -> HTTP %s%s" % (ruta, r.status_code, (": " + mensaje) if mensaje else "")
    if r.status_code == 401:
        return ClaveInvalida(mensaje, codigo=codigo, estado=401)
    if r.status_code == 402:
        return SinCreditos(mensaje, reinicio=r.headers.get("X-RateLimit-Reset"))
    return CromaError(mensaje, codigo=codigo, estado=r.status_code)


# ------------------------------------------------------------------- sonda
SONDA = [
    ("/co/secop/processes-search/v1", {"contract_type": "Obra", "awarded": "yes", "per_page": 2}),
    ("/co/secop/processes-search/v1", {"contract_type": "Obra", "awarded": "no", "per_page": 2}),
    ("/co/secop/contracts-search/v1", {"contract_type": "Obra", "per_page": 2}),
    ("/co/secop/awards-search/v1", {"per_page": 2}),
]


def sondear(salida=sys.stdout) -> int:
    if not disponible():
        print("falta CROMA_API_KEY; crea una llave de organizacion en https://platform.usecroma.com",
              file=salida)
        return 1
    api = CromaCliente()
    for ruta, cuerpo in SONDA:
        try:
            data = api.llamar(ruta, cuerpo)
        except CromaError as e:
            print("%s\n  ERROR %s" % (ruta, e), file=salida)
            continue
        filas = data.get("results") or []
        print("%s  %s\n  as_of=%s total=%s creditos_restantes=%s"
              % (ruta, json.dumps(cuerpo, ensure_ascii=False), data.get("as_of"), data.get("total"),
                 api.creditos_restantes), file=salida)
        if filas:
            print("  campos: " + ", ".join(sorted(filas[0].keys())), file=salida)
            print("  primera fila: " + json.dumps(filas[0], ensure_ascii=False)[:600], file=salida)
    return 0


if __name__ == "__main__":
    sys.exit(sondear())
