"""Comunidades del grafo de proveedores.  Owner: B  (Pilar 1, paso A3)

Requiere: python pipeline/build.py --steps 04 05 --no-export

Que hace
--------
Proyeccion proveedor--proveedor sobre las llaves que deberian ser unicas
(cuenta bancaria, representante legal, domicilio) -> componentes conexas ->
Louvain dentro de las componentes grandes -> `cluster_id` por proveedor.

El grafo es chico (28.811 proveedores, ~13k aristas): networkx en memoria
le sobra. Nada de Neo4j ni kuzu.

PRUEBA DE HUMO OBLIGATORIA
--------------------------
Si algun cluster supera MAX_CLUSTER proveedores, una llave placeholder se
filtro a las aristas y el resultado no significa nada. El script FALLA en
vez de escribir basura. `domicilio_replegal` es 63% 'NO DEFINIDO' y liga
19.403 proveedores: sin la lista negra de 04, ese solo valor produce un
cluster que se traga el grafo entero.
"""
from __future__ import annotations

import os
import sys

import duckdb
import networkx as nx
from networkx.algorithms.community import louvain_communities

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "warehouse", "plomada.duckdb")

MAX_CLUSTER = 200      # techo de la prueba de humo
SUBDIVIDIR = 50        # componentes mayores a esto se parten con Louvain
SEED = 20260822        # Louvain es estocastico: semilla fija = resultado reproducible


def construir(con):
    aristas = con.execute(
        "SELECT doc_a, doc_b, peso, n_tipos FROM aristas_prov_1x"
    ).fetchall()
    g = nx.Graph()
    for a, b, peso, n_tipos in aristas:
        g.add_edge(a, b, weight=float(peso), n_tipos=int(n_tipos))
    print("grafo: %d nodos, %d aristas" % (g.number_of_nodes(), g.number_of_edges()))
    return g


def comunidades(g):
    """Componentes conexas; las grandes se subdividen con Louvain.

    Una componente conexa puede unir dos redes distintas por una sola
    arista debil. Louvain dentro de la componente separa esos nucleos.
    """
    out = []
    for comp in nx.connected_components(g):
        if len(comp) <= SUBDIVIDIR:
            out.append(comp)
            continue
        sub = g.subgraph(comp)
        partes = louvain_communities(sub, weight="weight", seed=SEED)
        print("   componente de %d -> %d comunidades" % (len(comp), len(partes)))
        out.extend(partes)
    return sorted(out, key=len, reverse=True)


def main():
    if not os.path.exists(DB):
        sys.exit("no hay warehouse; corre 'python pipeline/build.py'")
    con = duckdb.connect(DB)

    g = construir(con)
    if g.number_of_nodes() == 0:
        sys.exit("grafo vacio; corre 'python pipeline/build.py --steps 04 05'")

    print("\ndetectando comunidades...")
    grupos = comunidades(g)

    mayor = len(grupos[0]) if grupos else 0
    print("\ncomunidades: %d   mayor: %d proveedores" % (len(grupos), mayor))

    # ---- PRUEBA DE HUMO: no escribir nada si el grafo esta contaminado ----
    if mayor > MAX_CLUSTER:
        muestra = sorted(grupos[0])[:5]
        sys.exit(
            "\nFALLA: el cluster mas grande tiene %d proveedores (techo %d).\n"
            "Una llave placeholder se filtro a las aristas. Revisa:\n"
            "  SELECT * FROM llaves_basura ORDER BY n_proveedores DESC;\n"
            "  SELECT tipo, count(*) FROM aristas_prov GROUP BY 1;\n"
            "Proveedores de muestra en el cluster: %s\n"
            "No se escribio nada al warehouse." % (mayor, MAX_CLUSTER, muestra)
        )

    filas = []
    for cid, grupo in enumerate(grupos):
        for doc in grupo:
            filas.append((cid, doc, len(grupo)))

    con.execute("CREATE OR REPLACE TABLE clusters (cluster_id INTEGER, doc_proveedor VARCHAR, tamano INTEGER)")
    con.executemany("INSERT INTO clusters VALUES (?, ?, ?)", filas)

    # ---- perfil de cada cluster ----
    con.execute(
        """
        CREATE OR REPLACE TABLE clusters_perfil AS
        SELECT
          c.cluster_id,
          c.tamano,
          count(DISTINCT p.doc)                              AS n_proveedores,
          sum(p.valor_total)                                 AS valor_total,
          sum(p.n_contratos)                                 AS n_contratos,
          sum(p.n_obra)                                      AS n_obra,
          sum(p.n_interventoria)                             AS n_interventoria,
          -- LA SENAL QUE IMPORTA: el cluster contiene a la vez quien
          -- construye y quien vigila. A4 lo confirma emparejando contratos.
          (sum(p.n_obra) > 0 AND sum(p.n_interventoria) > 0)  AS obra_e_interventoria,
          bool_or(p.es_entidad_publica)                       AS tiene_entidad_publica,
          list(p.nombre)                                      AS miembros
        FROM clusters c
        JOIN nodos_proveedor p ON p.doc = c.doc_proveedor
        GROUP BY c.cluster_id, c.tamano
        """
    )

    n_cl = con.execute("SELECT count(*) FROM clusters_perfil").fetchone()[0]
    print("\nescrito: clusters (%d proveedores) y clusters_perfil (%d clusteres)"
          % (len(filas), n_cl))

    print("\n=== CLUSTERES CON OBRA E INTERVENTORIA (leads para A4) ===")
    rows = con.execute(
        """SELECT cluster_id, n_proveedores, n_obra, n_interventoria,
                  round(valor_total/1e9, 1) AS mm, miembros
           FROM clusters_perfil
           WHERE obra_e_interventoria AND n_proveedores > 1
             AND NOT tiene_entidad_publica
           ORDER BY valor_total DESC LIMIT 12"""
    ).fetchall()
    for cid, n, no, ni, mm, miembros in rows:
        nombres = ", ".join(str(x) for x in miembros if x)[:96]
        print("   #%-5d %d provs  obra=%-4d interv=%-4d $%8.1f mm  %s"
              % (cid, n, no, ni, mm, nombres))
    if not rows:
        print("   (ninguno)")

    con.close()


if __name__ == "__main__":
    main()
