"""La puerta de privacidad, ahora que el sitio es dinamico.

POR QUE ESTE ARCHIVO EXISTE
---------------------------
plomada/test_privacy.py barria los 12.678 HTML de site/ buscando documentos
filtrados, y borraba el build entero si encontraba uno. Ese barrido perdio
casi todo su objeto: las fichas ya no se pre-renderizan, se hidratan en el
navegador desde el API. Sin un reemplazo, el proyecto se queda sin ninguna
garantia automatica sobre los datos personales que llegan al visitante.

Aqui hay dos pruebas distintas, y conviene no confundirlas:

  1. test_cliente_sanea_*  — lo que ESTE repo controla. Verifica que
     plomada/static/api.js::sanear() borre todo campo prohibido antes de que
     ninguna vista lo vea. Si esto falla, Plomada esta publicando documentos:
     es un fallo duro y bloquea.

  2. test_api_no_devuelve_documentos — la puerta del lado del API. Desde
     2026-09 el serializador (api/app/consultas.py::_partes) ya no emite las
     cedulas de ordenador, supervisor ni representante legal: emite su
     presencia (tiene_doc_*) y si dos coinciden. Este test lo verifica contra
     el API desplegado; api/tests/test_api.py lo verifica sin red.
     doc_proveedor se queda: es el NIT del contratista y el identificador del
     recurso /v1/proveedores (sanear() lo sigue borrando en el cliente).
"""
from __future__ import annotations

import json
import os
import subprocess

import pytest
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = os.environ.get("PLOMADA_API_URL", "https://plumb-duy6.onrender.com")

# Espejo de D.PROHIBIDAS | D.PROHIBIDAS_CONDICIONALES (plomada/data.py:48-53).
PROHIBIDOS = ["doc", "doc_a", "doc_b", "doc_proveedor", "doc_ordenador",
              "doc_supervisor", "doc_replegal", "cuenta_bancaria", "cuenta_key"]

TIMEOUT = 60  # Render puede estar dormido


def _claves(obj, encontradas=None):
    """Todas las claves que aparecen en cualquier nivel del objeto."""
    encontradas = encontradas if encontradas is not None else set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            encontradas.add(k)
            _claves(v, encontradas)
    elif isinstance(obj, list):
        for v in obj:
            _claves(v, encontradas)
    return encontradas


@pytest.fixture(scope="module")
def contrato_crudo():
    """Un ContratoDetalle real, tal como el API lo entrega."""
    try:
        r = requests.get(f"{API}/v1/contratos", params={"solo_atipicos": "true", "limite": 1},
                         timeout=TIMEOUT)
        datos = r.json().get("datos")
        if not datos:
            pytest.skip("el API no tiene datos cargados todavia")
        idc = datos[0]["id_contrato"]
        d = requests.get(f"{API}/v1/contratos/{idc}", timeout=TIMEOUT).json()
        if "datos" not in d:
            pytest.skip("el API no devolvio el detalle del contrato")
        return d["datos"]
    except requests.RequestException as e:
        pytest.skip(f"el API no respondio: {e}")


def _sanear_con_node(objeto):
    """Corre plomada/static/api.js::sanear() sobre `objeto` y devuelve el
    resultado. Es el MISMO codigo que corre en el navegador -- no una
    reimplementacion en Python, que podria divergir sin que nadie lo note."""
    script = (
        "import { sanear } from '%s/plomada/static/api.js';\n"
        "let e = ''; process.stdin.on('data', (c) => { e += c; });\n"
        "process.stdin.on('end', () => "
        "  process.stdout.write(JSON.stringify(sanear(JSON.parse(e)))));\n" % ROOT
    )
    ruta = os.path.join(ROOT, "tests", "_sanear_tmp.mjs")
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(script)
    try:
        p = subprocess.run(["node", ruta], input=json.dumps(objeto),
                           capture_output=True, text=True, timeout=30)
        if p.returncode != 0:
            pytest.fail(f"node fallo corriendo sanear(): {p.stderr}")
        return json.loads(p.stdout)
    finally:
        os.unlink(ruta)


# --------------------------------------------------- 1. lo que SI controlamos
def test_cliente_sanea_el_detalle_de_contrato(contrato_crudo):
    """Ningun campo prohibido sobrevive a sanear()."""
    limpio = _sanear_con_node(contrato_crudo)
    fugas = sorted(_claves(limpio) & set(PROHIBIDOS))
    assert not fugas, (
        f"api.js::sanear() dejo pasar {fugas}. Con el sitio dinamico, esta funcion "
        "es lo unico entre el API y lo que ve el visitante.")


def test_cliente_conserva_la_presencia_sin_el_valor(contrato_crudo):
    """f_datos_faltantes y f_ordenador_es_supervisor dependen de si el
    documento existe y de si dos coinciden, nunca de su valor. sanear() tiene
    que dejar esos booleanos derivados -- si los borra de mas, dos banderas
    del sitio dejan de poder explicarse."""
    limpio = _sanear_con_node(contrato_crudo)
    partes = limpio.get("partes") or {}
    assert "_tiene_doc_ordenador" in partes, (
        "sanear() borro la senal de presencia del documento del ordenador: "
        "f_datos_faltantes ya no puede decir que campo falta")
    for k, v in partes.items():
        if k.startswith("_tiene_") or k == "_mismo_ordenador_supervisor":
            assert isinstance(v, bool), f"{k} deberia ser booleano, es {type(v)}"


def test_cliente_sanea_la_red(contrato_crudo):
    """El grafo de proveedores trae 'doc' en cada nodo y 'doc_a'/'doc_b' en
    cada arista. Misma regla."""
    try:
        r = requests.get(f"{API}/v1/red/clusters", params={"limite": 1}, timeout=TIMEOUT)
        clusters = r.json().get("datos")
        if not clusters:
            pytest.skip("el API no devolvio clusters")
        cid = clusters[0]["cluster_id"]
        detalle = requests.get(f"{API}/v1/red/clusters/{cid}", timeout=TIMEOUT).json()["datos"]
    except (requests.RequestException, KeyError) as e:
        pytest.skip(f"el API no respondio: {e}")

    fugas = sorted(_claves(_sanear_con_node(detalle)) & set(PROHIBIDOS))
    assert not fugas, f"api.js::sanear() dejo pasar {fugas} en el grafo de red"


# --------------------------------------------------- 2. la puerta del API
PERSONALES = ["doc_ordenador", "doc_supervisor", "doc_replegal"]


@pytest.mark.xfail(
    strict=False,
    reason="El arreglo (api/app/consultas.py::_partes) esta en la rama y probado sin red "
           "en api/tests/test_api.py; este test golpea el API DESPLEGADO, que sale de main. "
           "Pasara solo cuando main lo tenga. strict=False: no rompe al pasar, y entonces "
           "se borra este marcador.")
def test_api_no_devuelve_documentos(contrato_crudo):
    """Las cedulas de personas naturales no salen del API (Ley 1581 de 2012)."""
    fugas = sorted(_claves(contrato_crudo) & set(PERSONALES))
    assert not fugas, f"el API devuelve documentos de personas naturales: {fugas}"
    partes = contrato_crudo.get("partes") or {}
    assert "tiene_doc_ordenador" in partes, "el API dejo de decir si el documento del ordenador esta"
