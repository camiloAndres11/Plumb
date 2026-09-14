"""Acceso a Postgres de la plataforma: un pool y cuatro helpers.

Mismo patron que api/app/db.py (psycopg 3, sin ORM, pool perezoso): el
servicio arranca y responde /health aunque Postgres no este, y la primera
consulta abre el pool. Todo lo que toca la base pasa por aqui.

    from plataforma import db
    fila = db.uno("SELECT * FROM pliego.usuarios WHERE email = %s", [email])
    filas = db.todos("SELECT ...")
    db.ejecutar("UPDATE ...", [...])
    with db.transaccion() as cur:      # varias sentencias, todo o nada
        cur.execute(...); cur.execute(...)
"""
from __future__ import annotations

import atexit
import threading
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from plataforma.config import config


class BaseNoDisponible(RuntimeError):
    """Falta DATABASE_URL, no se pudo conectar, o no se corrio la migracion.
    Es un error de operacion: la app lo traduce a 503 con el comando que falta."""


_pool: ConnectionPool | None = None
_lock = threading.Lock()


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                if not config.dsn:
                    raise BaseNoDisponible("falta DATABASE_URL en el entorno (ver .env.example)")
                _pool = ConnectionPool(config.dsn, min_size=1, max_size=8, open=True, timeout=10,
                                       kwargs={"row_factory": dict_row})
                atexit.register(cerrar)
    return _pool


def cerrar() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def _traducir(e: Exception) -> BaseNoDisponible:
    if isinstance(e, psycopg.errors.UndefinedTable | psycopg.errors.InvalidSchemaName):
        return BaseNoDisponible("la base no tiene el esquema `pliego`; corre 'python -m plataforma.migrar'")
    return BaseNoDisponible("no se pudo conectar a la base de datos")


@contextmanager
def transaccion():
    """Un cursor dentro de una transaccion: commit al salir, rollback si hay excepcion."""
    try:
        with pool().connection() as conn:
            with conn.cursor() as cur:
                yield cur
    except (psycopg.errors.UndefinedTable, psycopg.errors.InvalidSchemaName, psycopg.OperationalError) as e:
        raise _traducir(e) from e


def todos(sql: str, params=None) -> list[dict]:
    with transaccion() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def uno(sql: str, params=None) -> dict | None:
    filas = todos(sql, params)
    return filas[0] if filas else None


def ejecutar(sql: str, params=None) -> int:
    """Devuelve las filas afectadas."""
    with transaccion() as cur:
        cur.execute(sql, params or ())
        return cur.rowcount


def disponible() -> tuple[bool, str]:
    """Para /health: (ok, detalle) sin lanzar."""
    try:
        fila = uno("SELECT count(*) AS n FROM pliego.migraciones")
        return True, f"{fila['n']} migraciones"
    except BaseNoDisponible as e:
        return False, str(e)
