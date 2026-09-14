"""Carga a Postgres la capa de serving del API: todas las tablas `api_*`
del warehouse (ver sql/90_serving.sql y sql/91_serving_alertas.sql).

Nada mas viaja a Postgres. Las tablas internas del pipeline (`base`,
`flags`, `red_cuentas`, `cuenta_key`...) se quedan en DuckDB: lo que se
publica es exactamente lo que el paso 90 decidio publicar, y esa
decision esta en un solo archivo y cubierta por la puerta de calidad
test_el_snapshot_publico_no_lleva_cuentas.

Por que DuckDB y no pandas/sqlalchemy: ya es dependencia de pipeline/, y
su extension `postgres` permite copiar tabla a tabla sin pasar los datos
por un DataFrame intermedio.

Requiere:
    python pipeline/build.py --all      (o los pasos 01-06, 10, 11 y 90)
    python pipeline/alertas.py          (opcional: agrega api_alertas)
    DATABASE_URL en el entorno, apuntando al Postgres de destino
    (postgresql://usuario:clave@host:puerto/basededatos)

Uso:
    python pipeline/load_postgres.py
"""
from __future__ import annotations

import os
import sys

import duckdb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "warehouse", "plomada.duckdb").replace("\\", "/")

# Tablas que el API necesita si o si. Si falta una, es que no se corrio
# el paso 90 completo y cargar a medias dejaria endpoints rotos en
# produccion sin aviso: mejor fallar aqui.
OBLIGATORIAS = [
    "api_meta",
    "api_limitaciones",
    "api_banderas",
    "api_contratos",
    "api_entidades",
    "api_proveedores",
    "api_clusters",
    "api_cluster_nodos",
    "api_cluster_aristas",
    "api_titulares",
    "api_indicios",
    "api_municipios",
    "api_departamentos",
    "api_tipos_obra",
    "api_fuentes",
    "api_autosupervision",
]

# Opcionales: dependen de pipeline/alertas.py, que corre por su cuenta
# (snapshot diario). Sin ellas el API responde 503 en /v1/alertas con un
# mensaje claro, igual que el tablero cuando falta alertas.json.
OPCIONALES = ["api_alertas", "api_alertas_resumen"]

# Indices para los filtros que el API expone. Sin esto cada request es un
# seq scan sobre ~78k filas anchas: tolerable, pero innecesario.
INDICES = [
    ("api_contratos", "id_contrato"),
    ("api_contratos", "nit_entidad"),
    ("api_contratos", "departamento"),
    ("api_contratos", "anio"),
    ("api_contratos", "es_atipico"),
    ("api_contratos", "doc_proveedor"),
    ("api_contratos", "cluster_id"),
    ("api_entidades", "nit_entidad"),
    ("api_proveedores", "doc"),
    ("api_proveedores", "cluster_id"),
    ("api_cluster_nodos", "cluster_id"),
    ("api_cluster_aristas", "cluster_id"),
    ("api_alertas", "universo"),
]


def main():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        sys.exit("falta DATABASE_URL en el entorno (postgresql://usuario:clave@host:puerto/db)")
    # `postgresql+psycopg://` es la forma de SQLAlchemy y ni DuckDB ni
    # psycopg la parsean. Se acepta y se reduce, para que la misma cadena
    # sirva en docker-compose, en Render y aqui.
    if "+" in database_url.split("://", 1)[0]:
        database_url = "postgresql://" + database_url.split("://", 1)[1]
    if not os.path.exists(DB):
        sys.exit("no hay warehouse en %s; corre 'python pipeline/build.py --all' primero" % DB)

    con = duckdb.connect(":memory:")
    con.execute("INSTALL postgres")
    con.execute("LOAD postgres")
    con.execute("ATTACH '%s' AS wh (READ_ONLY)" % DB)
    con.execute("ATTACH '%s' AS pg (TYPE POSTGRES)" % database_url)

    presentes = {
        r[0] for r in con.execute(
            "SELECT table_name FROM duckdb_tables() WHERE database_name = 'wh'"
        ).fetchall()
    }
    faltan = [t for t in OBLIGATORIAS if t not in presentes]
    if faltan:
        sys.exit(
            "faltan tablas de serving en el warehouse (%s); corre "
            "'python pipeline/build.py --steps 90 --no-export'" % ", ".join(faltan)
        )

    cargadas = []
    for tabla in OBLIGATORIAS + OPCIONALES:
        if tabla not in presentes:
            print(">> %-22s omitida (corre pipeline/alertas.py para tenerla)" % tabla, flush=True)
            continue
        con.execute("CREATE OR REPLACE TABLE pg.%s AS SELECT * FROM wh.%s" % (tabla, tabla))
        n = con.execute("SELECT count(*) FROM pg.%s" % tabla).fetchone()[0]
        print(">> %-22s %8d filas" % (tabla, n), flush=True)
        cargadas.append(tabla)

    print("\n>> indices", flush=True)
    for tabla, col in INDICES:
        if tabla not in cargadas:
            continue
        # CREATE OR REPLACE TABLE bota el indice con la tabla, asi que se
        # recrean en cada carga. IF NOT EXISTS por si acaso.
        con.execute(
            "CALL postgres_execute('pg', "
            "'CREATE INDEX IF NOT EXISTS ix_%s_%s ON %s (%s)')" % (tabla, col, tabla, col)
        )
        print("   ix_%s_%s" % (tabla, col))

    con.close()
    print("\nCargadas %d tablas en Postgres." % len(cargadas))


if __name__ == "__main__":
    main()
