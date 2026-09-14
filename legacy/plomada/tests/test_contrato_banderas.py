"""Blindaje F1.2b: que el vocabulario de banderas del fixture no se vuelva a
desincronizar de sql/03_ranking.sql sin que alguien se entere.

sql/03_ranking.sql (tabla `pesos`) es la fuente de verdad de que banderas
existen, con que peso, en que grupo y con que glosa. `plomada/fixtures/
banderas_glosario.csv` es una COPIA sintetica pensada para alimentar la demo
sin pipeline real: tiene que copiar esa tabla, no reinventarla. Si el
pipeline agrega, quita o renombra una bandera en sql/ y nadie actualiza el
fixture ni data.py, este test lo dice antes de que llegue a produccion.

`sql/` no se toca aqui: solo se LEE como texto (no hay duckdb en este
equipo, y no hace falta: la tabla es un INSERT INTO ... VALUES literal).

Corre con: python3 tests/test_contrato_banderas.py
"""
import csv
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
SQL_RANKING = RAIZ / "sql" / "03_ranking.sql"
FIXTURE_GLOSARIO = RAIZ / "plomada" / "fixtures" / "banderas_glosario.csv"

fallos = []


def check(ok, mensaje):
    if not ok:
        fallos.append(mensaje)


def _desescapar(s):
    """SQL escapa una comilla simple duplicandola: 'no''s' -> "no's"."""
    return s.replace("''", "'")


def parsear_pesos_sql(texto):
    """Extrae (bandera, peso, grupo, glosa) del INSERT INTO pesos VALUES ...;
    de sql/03_ranking.sql. Es texto, no SQL de verdad: un regex sobre los
    literales '...' y numeros de cada tupla alcanza porque el archivo no
    tiene nada mas raro alli (sin subconsultas, sin expresiones)."""
    m = re.search(r"INSERT INTO pesos VALUES\s*(.*?);", texto, re.S)
    if not m:
        raise ValueError("no se encontro 'INSERT INTO pesos VALUES ... ;' en sql/03_ranking.sql — "
                          "¿se renombro la tabla o cambio el formato del archivo?")
    bloque = m.group(1)
    fila_re = re.compile(
        r"\(\s*'((?:[^']|'')*)'\s*,\s*([0-9.]+)\s*,\s*'((?:[^']|'')*)'\s*,\s*'((?:[^']|'')*)'\s*\)")
    filas = []
    for bandera, peso, grupo, glosa in fila_re.findall(bloque):
        filas.append((_desescapar(bandera), float(peso), _desescapar(grupo), _desescapar(glosa)))
    return filas


def leer_fixture():
    if not FIXTURE_GLOSARIO.exists():
        raise FileNotFoundError(f"no existe {FIXTURE_GLOSARIO}. Corra primero "
                                 "python3 plomada/gen_synthetic.py")
    with open(FIXTURE_GLOSARIO, newline="", encoding="utf-8") as fh:
        return [(r["bandera"], float(r["peso"]), r["grupo"], r["glosa"])
                for r in csv.DictReader(fh)]


def main():
    sql_texto = SQL_RANKING.read_text(encoding="utf-8")
    canonicas = parsear_pesos_sql(sql_texto)
    check(len(canonicas) > 0, "el parser no encontro ninguna bandera en sql/03_ranking.sql "
                              "(revise el regex, no el SQL: sql/ no se toca)")

    fixture = leer_fixture()

    nombres_sql = {b for b, *_ in canonicas}
    nombres_fixture = {b for b, *_ in fixture}

    faltan_en_fixture = nombres_sql - nombres_fixture
    sobran_en_fixture = nombres_fixture - nombres_sql
    check(not faltan_en_fixture,
          f"sql/03_ranking.sql tiene banderas que el fixture NO conoce: {sorted(faltan_en_fixture)} "
          "— actualice plomada/gen_synthetic.py y plomada/data.py (_ev())")
    check(not sobran_en_fixture,
          f"el fixture tiene banderas que sql/03_ranking.sql YA NO define: {sorted(sobran_en_fixture)} "
          "— borrelas de plomada/gen_synthetic.py y plomada/data.py (_ev())")

    # para las que si coinciden por nombre: peso, grupo y glosa deben ser
    # una copia literal, no una reescritura. "cópialos de ahi, no los
    # reescribas" (encargo F1.2b).
    sql_por_nombre = {b: (peso, grupo, glosa) for b, peso, grupo, glosa in canonicas}
    fix_por_nombre = {b: (peso, grupo, glosa) for b, peso, grupo, glosa in fixture}
    for nombre in sorted(nombres_sql & nombres_fixture):
        peso_sql, grupo_sql, glosa_sql = sql_por_nombre[nombre]
        peso_fix, grupo_fix, glosa_fix = fix_por_nombre[nombre]
        check(peso_sql == peso_fix,
              f"{nombre}: peso {peso_fix} en el fixture, {peso_sql} en sql/03_ranking.sql")
        check(grupo_sql == grupo_fix,
              f"{nombre}: grupo '{grupo_fix}' en el fixture, '{grupo_sql}' en sql/03_ranking.sql")
        check(glosa_sql == glosa_fix,
              f"{nombre}: glosa distinta de sql/03_ranking.sql —\n"
              f"    fixture: {glosa_fix!r}\n"
              f"    sql:     {glosa_sql!r}")

    if fallos:
        print(f"\n  {len(fallos)} FALLO(S):\n")
        for f in fallos:
            print("   ✗", f)
        print()
        sys.exit(1)
    print(f"  OK: las {len(nombres_sql)} banderas de sql/03_ranking.sql y las del fixture "
          "coinciden en nombre, peso, grupo y glosa.")


if __name__ == "__main__":
    main()
