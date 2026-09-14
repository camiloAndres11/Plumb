"""Prueba de la funcion pura de saneamiento del grafo de red (Tanda A, A3/A5).

`pipeline.export_web.sanear_red()` es la unica pieza que decide que se
publica en datos/red.json. Es una funcion pura (sin duckdb, sin disco) a
proposito para que se pueda probar con filas fabricadas a mano en un equipo
SIN warehouse -- que es exactamente este equipo (ver el reporte de Tanda A:
la corrida de punta a punta de export_web.py sigue sin probarse).

Corre con: python3 tests/test_privacidad_red.py
"""
import json
import re
import sys
from pathlib import Path

import export_web as E  # pipeline/ esta en pythonpath (pyproject.toml); duckdb se importa dentro de main()

RAIZ = Path(__file__).parent.parent

fallos = []


def check(ok, mensaje):
    if not ok:
        fallos.append(mensaje)


# documentos de mentira, pero con la FORMA real de un NIT/cedula colombiana
# (9-10 digitos), que es justo el patron de baja entropia que hace que un
# hash pelado no sirva para anonimizar.
DOC_A, DOC_B, DOC_C = "900412345", "901556677", "800556677"


def fabricar():
    nodos = [
        {"doc": DOC_A, "nombre": "MYG LINARES S.A.S.", "n_obra": 2, "n_interventoria": 0,
         "n_contratos": 2, "valor": 300_000_000, "n_entidades": 1},
        {"doc": DOC_B, "nombre": "MYG PUERRES S.A.S.", "n_obra": 1, "n_interventoria": 1,
         "n_contratos": 2, "valor": 200_000_000, "n_entidades": 1},
    ]
    aristas = [
        {"doc_a": DOC_A, "doc_b": DOC_B, "peso": 2, "tipos": ["cuenta", "replegal"]},
        # arista hacia un documento que NO esta en `nodos`: no deberia colarse.
        {"doc_a": DOC_A, "doc_b": DOC_C, "peso": 1, "tipos": ["cuenta"]},
    ]
    return nodos, aristas


def test_reemplaza_doc_por_id_secuencial():
    nodos, aristas = fabricar()
    nodos_s, _ = E.sanear_red(nodos, aristas)
    check(len(nodos_s) == 2, f"se esperaban 2 nodos saneados, salieron {len(nodos_s)}")
    ids = [n.get("id") for n in nodos_s]
    check(ids == ["n0", "n1"], f"los ids deberian ser secuenciales en orden de entrada: {ids}")
    for n in nodos_s:
        check("doc" not in n, f"'doc' crudo se colo en un nodo saneado: {n}")
    # el resto de los campos del nodo (nombre, cifras) se conservan intactos
    check(nodos_s[0]["nombre"] == "MYG LINARES S.A.S.", "el nombre del proveedor no deberia tocarse")
    check(nodos_s[0]["valor"] == 300_000_000, "las cifras del nodo no deberian tocarse")


def test_aristas_usan_los_mismos_ids_que_los_nodos():
    nodos, aristas = fabricar()
    nodos_s, aristas_s = E.sanear_red(nodos, aristas)
    id_de = {DOC_A: "n0", DOC_B: "n1"}
    # la arista DOC_A<->DOC_B debe sobrevivir, apuntando a los ids correctos
    sobrevive = [a for a in aristas_s if {a["a"], a["b"]} == {id_de[DOC_A], id_de[DOC_B]}]
    check(len(sobrevive) == 1, f"deberia sobrevivir exactamente 1 arista entre n0 y n1: {aristas_s}")
    check(sobrevive and sobrevive[0]["peso"] == 2, "el peso de la arista no deberia tocarse")
    check(sobrevive and sobrevive[0]["tipos"] == ["cuenta", "replegal"], "los tipos no deberian tocarse")
    for a in aristas_s:
        check("doc_a" not in a and "doc_b" not in a, f"doc_a/doc_b crudos se colaron en una arista: {a}")


def test_arista_hacia_nodo_ausente_se_descarta():
    """DOC_C no viene en `nodos`: la arista que lo menciona no puede
    publicarse (no hay a que id mapearlo sin inventar uno para un nodo que
    nunca se publico), y sobre todo, DOC_C no puede colarse crudo."""
    nodos, aristas = fabricar()
    _, aristas_s = E.sanear_red(nodos, aristas)
    check(len(aristas_s) == 1, f"la arista hacia el documento ausente deberia descartarse: {aristas_s}")
    dump = json.dumps(aristas_s)
    check(DOC_C not in dump, f"el documento ausente {DOC_C} se colo en las aristas saneadas: {dump}")


def test_documento_no_sobrevive_en_ningun_lado_del_payload():
    """La comprobacion mas directa: serializa TODO lo que sanear_red()
    devuelve y confirma que ninguno de los documentos de entrada aparece,
    ni como valor ni como substring."""
    nodos, aristas = fabricar()
    nodos_s, aristas_s = E.sanear_red(nodos, aristas)
    dump = json.dumps({"nodos": nodos_s, "aristas": aristas_s}, ensure_ascii=False)
    for doc in (DOC_A, DOC_B, DOC_C):
        check(doc not in dump, f"FUGA: el documento '{doc}' aparece en el payload saneado: {dump}")


def test_no_es_un_hash():
    """NO se usa un hash del documento (ver docstring de sanear_red en
    export_web.py): los ids deben tener forma 'n<numero>', nunca la forma de
    un hash (hexadecimal largo) ni la de un documento (6-12 digitos)."""
    nodos, aristas = fabricar()
    nodos_s, aristas_s = E.sanear_red(nodos, aristas)
    forma_id = re.compile(r"^n\d+$")
    forma_documento = re.compile(r"^\d{6,12}$")
    forma_hash_hex = re.compile(r"^[0-9a-f]{32,}$")
    for n in nodos_s:
        idv = str(n["id"])
        check(forma_id.match(idv), f"el id '{idv}' no tiene forma 'n<numero>'")
        check(not forma_documento.match(idv), f"el id '{idv}' tiene forma de documento crudo")
        check(not forma_hash_hex.match(idv), f"el id '{idv}' tiene forma de hash — no se pidio un hash, se pidio un id secuencial")
    for a in aristas_s:
        for k in ("a", "b"):
            v = str(a[k])
            check(forma_id.match(v), f"el extremo '{k}'='{v}' no tiene forma 'n<numero>'")


def test_pura_sin_estado_compartido_entre_llamadas():
    """Cada llamada (cada cluster, en export_web.construir_red()) tiene que
    empezar su numeracion en n0 otra vez: si el conteo se filtrara entre
    llamadas, dos clusters distintos podrian mezclar identidades por
    accidente. sanear_red() no debe guardar estado global."""
    nodos1 = [{"doc": "111111111", "nombre": "A"}]
    nodos2 = [{"doc": "222222222", "nombre": "B"}]
    s1, _ = E.sanear_red(nodos1, [])
    s2, _ = E.sanear_red(nodos2, [])
    check(s1[0]["id"] == "n0", f"primera llamada deberia arrancar en n0: {s1}")
    check(s2[0]["id"] == "n0", f"segunda llamada deberia arrancar en n0 otra vez (sin estado compartido): {s2}")


def test_mismo_documento_dos_veces_reusa_el_mismo_id():
    """Si el mismo doc aparece en mas de una fila de nodos (no deberia pasar
    con datos reales, pero la funcion no debe asumirlo), tiene que quedarse
    con un solo id, no dos."""
    nodos = [
        {"doc": DOC_A, "nombre": "MYG LINARES S.A.S. (fila 1)"},
        {"doc": DOC_A, "nombre": "MYG LINARES S.A.S. (fila 2, duplicada)"},
        {"doc": DOC_B, "nombre": "MYG PUERRES S.A.S."},
    ]
    nodos_s, _ = E.sanear_red(nodos, [])
    ids = {n["id"] for n in nodos_s}
    check(nodos_s[0]["id"] == nodos_s[1]["id"] == "n0",
          f"el mismo documento repetido deberia reusar el id: {[n['id'] for n in nodos_s]}")
    check(nodos_s[2]["id"] == "n1", f"el siguiente documento distinto deberia avanzar a n1: {nodos_s[2]}")
    check(len(ids) == 2, f"deberian quedar solo 2 ids distintos: {ids}")


def main():
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith("test_"):
            fn()
    if fallos:
        print(f"\n  {len(fallos)} FALLO(S):\n")
        for f in fallos:
            print("   ✗", f)
        print()
        sys.exit(1)
    n_pruebas = sum(1 for k in globals() if k.startswith("test_"))
    print(f"  OK: {n_pruebas} pruebas de sanear_red() sobre filas fabricadas a mano "
          "(sin duckdb, sin warehouse) — ningun documento crudo se cuela al payload.")


if __name__ == "__main__":
    main()
