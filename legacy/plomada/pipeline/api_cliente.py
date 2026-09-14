"""Cliente del API real de Plomada (https://plumb-duy6.onrender.com).

Un solo lugar que habla HTTP con el API, para que el saneamiento de datos
prohibidos (ver pipeline/export_web.py::sanear_red) no se pueda saltar por
descuido en otro modulo que tambien quisiera consumir el API.

Uso basico:
    from pipeline.api_cliente import ApiCliente, ApiError, SinDatos

    api = ApiCliente()
    meta = api.obtener("/v1/meta")                 # dict
    todos = api.listar("/v1/municipios", limite=60) # list, pagina sola si hace falta

Contrato del API (ver openapi.json del servicio):
    - Toda respuesta exitosa envuelve el resultado en {"datos": ..., "meta": {...}}.
    - Toda respuesta de error trae {"error": {"codigo": ..., "mensaje": ..., "detalle": ...}}.
    - Los endpoints de listado paginan con `limite` (tope 200) y `desplazamiento`,
      y devuelven `meta.paginacion.total` con el total real.
    - El servicio corre en Render (plan gratuito): si lleva un rato sin trafico,
      la primera llamada puede tardar 30-60s en "despertar". El timeout de la
      primera llamada es deliberadamente generoso; los reintentos usan backoff.

SIN_DATOS: mientras la base de Postgres del API no tenga las tablas cargadas
(`pipeline/load_postgres.py` no se ha corrido contra produccion), TODOS los
endpoints de datos devuelven el codigo "datos_no_disponibles". Este cliente
distingue ese caso (SinDatos) de una falla real de red (ApiError), porque
build.py necesita reaccionar distinto: "el API esta vivo pero vacio todavia"
no es lo mismo que "el API no respondio". En ambos casos el sitio se
construye igual, mostrando "sin datos disponibles" -- nunca una cifra
inventada (ver plomada/CONTEXT.md / restriccion del plan sobre no rellenar
con el ultimo valor conocido).
"""
from __future__ import annotations

import os
import time

import requests

BASE_URL_DEFAULT = "https://plumb-duy6.onrender.com"
LIMITE_MAX = 200
TIMEOUT_PRIMERA_LLAMADA = 60  # Render free tier: cold start
TIMEOUT_NORMAL = 15
REINTENTOS = 3
BACKOFF_BASE = 2  # segundos: 2, 4, 8...


class ApiError(Exception):
    """El API respondio pero con un error explicito, o la llamada fallo
    despues de agotar los reintentos (red caida, 5xx persistente, timeout)."""

    def __init__(self, mensaje, codigo=None):
        super().__init__(mensaje)
        self.codigo = codigo


class SinDatos(ApiError):
    """El API esta vivo y respondio, pero su base no tiene datos todavia
    (codigo 'datos_no_disponibles': falta correr pipeline/load_postgres.py
    contra la base de produccion). Se distingue de ApiError porque quien
    consume el cliente puede querer degradar distinto ("el servicio esta
    arriba, solo que vacio") de una falla de red."""


class ApiCliente:
    def __init__(self, base_url=None, session=None):
        self.base_url = (base_url or os.environ.get("PLOMADA_API_URL")
                          or BASE_URL_DEFAULT).rstrip("/")
        self.session = session or requests.Session()
        self._primera_llamada = True

    def _url(self, ruta):
        return self.base_url + ("/" + ruta.lstrip("/") if not ruta.startswith("/") else ruta) \
            if not ruta.startswith(self.base_url) else ruta

    def _get(self, ruta, params=None):
        url = self._url(ruta)
        timeout = TIMEOUT_PRIMERA_LLAMADA if self._primera_llamada else TIMEOUT_NORMAL
        ultimo_error = None
        for intento in range(REINTENTOS):
            try:
                r = self.session.get(url, params=params, timeout=timeout)
                self._primera_llamada = False
                if r.status_code >= 500:
                    ultimo_error = ApiError(f"{url}: HTTP {r.status_code}")
                elif r.status_code == 503:
                    ultimo_error = ApiError(f"{url}: HTTP 503 (servicio no disponible)")
                else:
                    return r
            except requests.exceptions.RequestException as e:
                ultimo_error = ApiError(f"{url}: {e}")
            if intento < REINTENTOS - 1:
                time.sleep(BACKOFF_BASE * (2 ** intento))
        raise ultimo_error

    def obtener(self, ruta, params=None):
        """GET que desenvuelve {datos, meta} -> datos. Lanza SinDatos si el
        API responde con 'datos_no_disponibles', ApiError para cualquier
        otro error (incluida una respuesta que no es JSON valido)."""
        r = self._get(ruta, params)
        try:
            cuerpo = r.json()
        except ValueError:
            raise ApiError(f"{ruta}: respuesta no es JSON valido (HTTP {r.status_code})")
        if "error" in cuerpo:
            err = cuerpo["error"] or {}
            codigo = err.get("codigo")
            mensaje = err.get("mensaje") or str(err)
            if codigo == "datos_no_disponibles":
                raise SinDatos(mensaje, codigo=codigo)
            raise ApiError(f"{ruta}: {mensaje}", codigo=codigo)
        if not r.ok:
            raise ApiError(f"{ruta}: HTTP {r.status_code}")
        if "datos" not in cuerpo:
            raise ApiError(f"{ruta}: respuesta sin 'datos' ni 'error' -- contrato inesperado")
        return cuerpo["datos"], cuerpo.get("meta") or {}

    def listar(self, ruta, params=None, limite=LIMITE_MAX):
        """Pagina un endpoint de listado hasta traer todas las filas,
        respetando el tope de LIMITE_MAX por pagina. Se guia por
        meta.paginacion.total, no por 'hasta que venga vacio': el contrato
        del API garantiza ese numero."""
        limite = min(limite, LIMITE_MAX)
        params = dict(params or {})
        desplazamiento = 0
        filas = []
        total = None
        while total is None or desplazamiento < total:
            params["limite"] = limite
            params["desplazamiento"] = desplazamiento
            datos, meta = self.obtener(ruta, params)
            filas.extend(datos)
            paginacion = meta.get("paginacion") or {}
            total = paginacion.get("total", len(filas))
            devueltas = paginacion.get("devueltas", len(datos))
            if devueltas == 0:
                break
            desplazamiento += devueltas
        return filas
