"""Exporta el warehouse a JSON estatico para el tablero web.

Uso:  python pipeline/export_web.py
Salida: out_web/*.json (en la raiz del repo). plomada/build.py copia ese
directorio a site/datos/ — este script YA NO escribe dentro de site/
directamente: build.py tiene que seguir siendo lo unico que escribe ahi,
porque es lo que le da a plomada/test_privacy.py control sobre TODO el
artefacto publicado (Tanda A, item A4).

Sin API ni build step: el tablero es un solo HTML que lee estos archivos.
Es un prototipo funcional que el equipo puede portar a Next.js despues; la
forma de los JSON es a proposito la misma que tendran los endpoints
(/titulares, /municipios, /departamentos, /red).

`duckdb` se importa DENTRO de main(), a proposito: `sanear_red()` de aqui
abajo es una funcion pura (sin base de datos) y tiene que poder importarse
y probarse (ver tests/test_privacidad_red.py) en un equipo sin duckdb
instalado, sin que el modulo entero truene al importarlo.
"""
from __future__ import annotations

import datetime
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "warehouse", "plomada.duckdb")
OUT = os.path.join(ROOT, "out_web")

TOP_CLUSTERS = 40


def rows(con, sql, params=None):
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _json_default(o):
    if isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat()
    raise TypeError("no serializable: %r" % (o,))


def write(name, obj):
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(",", ":"), default=_json_default)
    print("   %-26s %7.1f KB" % (name, os.path.getsize(path) / 1024))


# --------------------------------------------------------------- privacidad
# plomada/data.py clasifica doc_proveedor como PROHIBIDA_CONDICIONAL (solo se
# publica si el proveedor es persona juridica). El grafo de red no aplicaba
# ese filtro en absoluto: publicaba el 'doc' (NIT o cedula) crudo en cada
# nodo, y doc_a/doc_b crudos en cada arista. Esta funcion cierra esa fuga.
#
# NO se usa un hash del documento. Un NIT o cedula colombiana tiene 9-10
# digitos (baja entropia): un sha256 pelado de eso se revierte por fuerza
# bruta en segundos — es ofuscacion, no anonimizacion. En su lugar, un id
# secuencial asignado EN EL MOMENTO DE EXPORTAR ("n0", "n1", ...): al grafo
# solo le hace falta que la identidad sea consistente DENTRO del cluster que
# se esta exportando (para que una arista apunte al nodo correcto), no que
# sobreviva entre corridas del pipeline. Si algun dia hace falta que el
# mismo proveedor tenga el mismo id entre corridas, la solucion es un HMAC
# con llave guardada FUERA del repo — nunca un hash pelado del documento.
def sanear_red(nodos, aristas):
    """Funcion pura: recibe filas crudas (nodos con 'doc', aristas con
    'doc_a'/'doc_b') y devuelve (nodos_saneados, aristas_saneadas) listas
    para publicar. No toca la base de datos ni el disco -- por eso se puede
    probar con filas fabricadas a mano, sin duckdb ni warehouse.

    nodos_saneados: cada fila pierde 'doc' y gana 'id' ("n0", "n1", ...).
    aristas_saneadas: 'doc_a'/'doc_b' se reemplazan por 'a'/'b' con esos
    mismos ids. Una arista que mencione un doc que no vino en `nodos` se
    descarta (no se le puede asignar un id consistente, y ya se estaba
    filtrando por fuera antes de esta funcion).
    """
    ids: dict = {}
    nodos_saneados = []
    for n in nodos:
        n2 = dict(n)
        doc = n2.pop("doc")
        ids.setdefault(doc, f"n{len(ids)}")
        n2["id"] = ids[doc]
        nodos_saneados.append(n2)

    aristas_saneadas = []
    for a in aristas:
        doc_a, doc_b = a["doc_a"], a["doc_b"]
        if doc_a not in ids or doc_b not in ids:
            continue
        aristas_saneadas.append({
            "a": ids[doc_a], "b": ids[doc_b],
            "peso": a["peso"], "tipos": list(a["tipos"]),
        })
    return nodos_saneados, aristas_saneadas


def construir_red(con):
    """Un subgrafo por cluster, solo los mas relevantes, ya saneado con
    sanear_red(). Separado de main() para que la consulta y el saneamiento
    queden en un solo lugar, en orden."""
    ids_clusters = [r["cluster_id"] for r in rows(con, """
        SELECT cluster_id FROM clusters_perfil
        WHERE n_proveedores > 1 AND NOT tiene_entidad_publica
        ORDER BY (obra_e_interventoria::INT) DESC, valor_total DESC
        LIMIT %d""" % TOP_CLUSTERS)]

    red = []
    for cid in ids_clusters:
        nodos_crudos = rows(con, """
            SELECT p.doc, p.nombre, p.n_obra, p.n_interventoria, p.n_contratos,
                   coalesce(p.valor_total, 0) AS valor, p.n_entidades
            FROM clusters c JOIN nodos_proveedor p ON p.doc = c.doc_proveedor
            WHERE c.cluster_id = ?
            ORDER BY p.valor_total DESC""", [cid])
        docs = {n["doc"] for n in nodos_crudos}
        aristas_crudas = [
            a for a in rows(con, """
                SELECT doc_a, doc_b, peso, tipos FROM aristas_prov_1x
                WHERE doc_a IN (SELECT doc_proveedor FROM clusters WHERE cluster_id = ?)
                  AND doc_b IN (SELECT doc_proveedor FROM clusters WHERE cluster_id = ?)""",
                [cid, cid])
            if a["doc_a"] in docs and a["doc_b"] in docs
        ]
        nodos, aristas = sanear_red(nodos_crudos, aristas_crudas)
        perfil = rows(con, "SELECT * FROM clusters_perfil WHERE cluster_id = ?", [cid])[0]
        red.append({
            "id": cid,
            "n_obra": perfil["n_obra"],
            "n_interventoria": perfil["n_interventoria"],
            "valor": perfil["valor_total"] or 0,
            "vigila_y_construye": bool(perfil["obra_e_interventoria"]),
            "nodos": nodos,
            "aristas": aristas,
        })
    return red


def tablas(con):
    return {r[0] for r in con.execute("SELECT table_name FROM duckdb_tables()").fetchall()}


def main():
    import duckdb  # perezoso a proposito, ver docstring del modulo

    os.makedirs(OUT, exist_ok=True)
    con = duckdb.connect(DB, read_only=True)
    print("exportando a out_web/")

    write("titulares.json", rows(con, """
        SELECT concepto, n_contratos, coalesce(valor, 0) AS valor FROM titulares"""))

    write("indicios.json", rows(con, """
        SELECT indicio, grupo, n_contratos, coalesce(valor, 0) AS valor
        FROM plata_por_indicio ORDER BY valor DESC"""))

    # Municipios: se llevan las DOS tasas para poder mostrar el efecto del
    # encogimiento bayesiano en un dumbbell. Esa comparacion es el argumento
    # metodologico y no se puede esconder.
    write("municipios.json", rows(con, """
        SELECT ciudad, departamento, n_contratos, n_atipicos,
               tasa_cruda, tasa_ajustada,
               coalesce(valor_total, 0) AS valor_total,
               coalesce(valor_atipico, 0) AS valor_atipico,
               n_proponente_unico, n_obra_directa, n_fraccionamiento
        FROM ranking_municipios
        WHERE n_contratos >= 20
        ORDER BY tasa_ajustada DESC LIMIT 60"""))

    write("departamentos.json", rows(con, """
        SELECT d.departamento, d.n_contratos,
               coalesce(d.total, 0) AS total,
               coalesce(d.sin_competencia, 0) AS sin_competencia,
               coalesce(d.en_riesgo, 0) AS en_riesgo,
               coalesce(d.regalias, 0) AS regalias,
               r.tasa_ajustada
        FROM plata_por_departamento d
        LEFT JOIN ranking_departamentos r USING (departamento)
        ORDER BY d.total DESC"""))

    write("tipo_obra.json", rows(con, """
        SELECT tipo_obra, n_contratos, coalesce(total,0) AS total,
               coalesce(en_riesgo,0) AS en_riesgo,
               coalesce(sin_competencia,0) AS sin_competencia
        FROM plata_por_tipo_obra ORDER BY total DESC"""))

    write("fuentes.json", rows(con, """
        SELECT fuente, total, en_riesgo FROM plata_por_fuente ORDER BY total DESC"""))

    write("autosupervision.json", rows(con, """
        SELECT entidad, departamento, ciudad, n_auto, n_con_ambos, tasa,
               coalesce(valor_auto, 0) AS valor_auto
        FROM entidades_autosupervision ORDER BY valor_auto DESC"""))

    write("red.json", construir_red(con))

    # ---- Alertas pre-adjudicacion (Pilar 4), si ya se corrieron ----
    if "alertas" in tablas(con):
        resumen_universo = rows(con, """
            SELECT universo, count(*) AS n FROM alertas GROUP BY 1""")
        accionables = rows(con, """
            SELECT id_del_proceso, entidad, departamento, ciudad, tipo_contrato,
                   modalidad, coalesce(precio_base,0) AS precio_base,
                   fecha_publicacion, fecha_cierre, dias_ventana, dias_restantes,
                   n_invitados, n_manifestaron, ev_ventana_p10_modalidad,
                   ev_tasa_historica_entidad, ev_n_historico_entidad,
                   f_ventana_corta, f_al_tope_minima, f_historial_proponente_unico,
                   f_sin_interes_a_tiempo, f_cierre_movido, n_banderas, urlproceso
            FROM alertas
            WHERE universo = 'accionable'
            ORDER BY n_banderas DESC, dias_restantes ASC""")
        write("alertas.json", {
            "generado": datetime.date.today(),
            "resumen_universo": resumen_universo,
            "accionables": accionables,
        })
    else:
        print("   (alertas.json omitido: corre pipeline/alertas.py primero)")

    # Metadatos: cobertura y limitaciones viajan CON los datos, para que el
    # tablero no pueda mostrar una cifra sin su salvedad al lado.
    cov = con.execute("""
        SELECT count(*), sum(valor_plausible),
               count(*) FILTER (WHERE doc_ordenador IS NOT NULL),
               count(*) FILTER (WHERE doc_supervisor IS NOT NULL),
               count(*) FILTER (WHERE cuenta_key IS NOT NULL),
               count(*) FILTER (WHERE precio_base IS NOT NULL)
        FROM base""").fetchone()
    write("meta.json", {
        "contratos": cov[0],
        "valor_total": cov[1],
        "cobertura": {
            "cedula_ordenador": cov[2] / cov[0],
            "cedula_supervisor": cov[3] / cov[0],
            # NUNCA "cuenta_bancaria": ese nombre literal esta en D.PROHIBIDAS
            # (plomada/data.py) y test_privacy.py barre TODOS los artefactos
            # buscando ese substring, sin importar si es un valor o (como aqui)
            # solo el nombre de una metrica de cobertura. Encontrado probando
            # copiar_datos_tablero() con un out_web/meta.json fabricado a mano
            # (Tanda B): con este nombre, el build se borraba SIEMPRE que
            # existiera un warehouse real, sin ninguna fuga de verdad.
            "pct_con_cuenta": cov[4] / cov[0],
            "unido_a_proceso": cov[5] / cov[0],
        },
        "n_clusters": con.execute("SELECT count(*) FROM clusters_perfil").fetchone()[0],
        "limitaciones": [
            "Un indicio no es una acusacion: son senales para priorizar investigacion.",
            "Solo SECOP II. No incluye SECOP I ni entidades que publican mal.",
            "La cedula del ordenador del gasto esta en el 64,5% de los contratos y la del supervisor en el 54,3%: el analisis de red cubre esa fraccion.",
            "La cuenta bancaria esta en el 23,7%: las redes detectadas son un piso, no un censo.",
            "No hay datos de oferentes perdedores, solo el numero de ofertas y el ganador.",
            "El sobrecosto por unidad fisica no es calculable: solo el 0,9% de las descripciones declara una cantidad con unidad.",
            "El ranking municipal no esta normalizado por poblacion.",
            "De los procesos que la plataforma marca como abiertos, el 85,5% no tiene fecha de cierre publicada y el 12,9% tiene la fecha ya vencida: solo el 1,6% es realmente accionable hoy.",
        ],
    })
    con.close()


if __name__ == "__main__":
    main()
