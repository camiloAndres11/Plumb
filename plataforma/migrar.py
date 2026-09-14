"""Aplica plataforma/sql/*.sql en orden, una sola vez cada uno.

    python -m plataforma.migrar            # aplica lo que falte
    python -m plataforma.migrar --estado   # que hay aplicado y que falta

Cada archivo corre entero dentro de una transaccion y, si termina bien,
queda anotado en pliego.migraciones. Los archivos deben ser idempotentes de
todos modos (IF NOT EXISTS), por si alguien los corre a mano con psql.
"""
from __future__ import annotations

import sys
from pathlib import Path

import psycopg

from plataforma.config import config

SQL = Path(__file__).resolve().parent / "sql"
TABLA = """
CREATE SCHEMA IF NOT EXISTS pliego;
CREATE TABLE IF NOT EXISTS pliego.migraciones (
  nombre TEXT PRIMARY KEY, aplicada TIMESTAMPTZ NOT NULL DEFAULT now());
"""


def archivos() -> list[Path]:
    return sorted(SQL.glob("[0-9][0-9][0-9]_*.sql"))


def aplicadas(conn) -> set[str]:
    conn.execute(TABLA)
    return {r[0] for r in conn.execute("SELECT nombre FROM pliego.migraciones").fetchall()}


def migrar(dsn: str | None = None, salida=sys.stdout) -> list[str]:
    """Devuelve los nombres que aplico en esta corrida."""
    dsn = dsn or config.dsn
    if not dsn:
        raise SystemExit("falta DATABASE_URL (ver .env.example)")
    hechas = []
    with psycopg.connect(dsn) as conn:
        ya = aplicadas(conn)
        for archivo in archivos():
            if archivo.name in ya:
                continue
            with conn.transaction():
                conn.execute(archivo.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO pliego.migraciones (nombre) VALUES (%s)", [archivo.name])
            hechas.append(archivo.name)
            print("aplicada", archivo.name, file=salida)
    if not hechas:
        print("nada que aplicar", file=salida)
    return hechas


def estado(dsn: str | None = None, salida=sys.stdout) -> int:
    dsn = dsn or config.dsn
    if not dsn:
        raise SystemExit("falta DATABASE_URL (ver .env.example)")
    with psycopg.connect(dsn) as conn:
        ya = aplicadas(conn)
    for archivo in archivos():
        print(("  ok    " if archivo.name in ya else "  falta ") + archivo.name, file=salida)
    return 0


if __name__ == "__main__":
    sys.exit(estado() if "--estado" in sys.argv else (0 if migrar() is not None else 1))
