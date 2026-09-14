"""Postgres con psycopg 3, sin ORM: un pool perezoso y cuatro helpers.

    from pliego.comun.pg import Pg
    pg = Pg(lambda: config.dsn, sin_dsn="falta DATABASE_URL", sin_esquema="corre las migraciones")
    fila = pg.uno("SELECT ...", [x]); filas = pg.todos(...); n = pg.ejecutar(...)
    with pg.transaccion() as cur: ...

El servicio arranca y responde /health aunque Postgres no este; la primera
consulta abre el pool. `NoDisponible` es el error de operacion (sin DSN,
sin conexion, sin esquema) que la app traduce a 503 con el mensaje que
toca. Es lo que plataforma/db.py y (en su dia) api/app/db.py duplicaban.
"""
from __future__ import annotations

import atexit
import threading
from collections.abc import Callable
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


class NoDisponible(RuntimeError):
    """Falta el DSN, no se pudo conectar, o no existe el esquema."""


class Pg:
    def __init__(self, dsn: Callable[[], str], sin_dsn: str, sin_esquema: str, sin_conexion: str = "no se pudo conectar a la base de datos",
                 max_size: int = 8):
        self._dsn, self._max = dsn, max_size
        self.mensajes = {"dsn": sin_dsn, "esquema": sin_esquema, "conexion": sin_conexion}
        self._pool: ConnectionPool | None = None
        self._lock = threading.Lock()

    def pool(self) -> ConnectionPool:
        if self._pool is None:
            with self._lock:
                if self._pool is None:
                    dsn = self._dsn()
                    if not dsn:
                        raise NoDisponible(self.mensajes["dsn"])
                    self._pool = ConnectionPool(dsn, min_size=1, max_size=self._max, open=True, timeout=10,
                                                kwargs={"row_factory": dict_row})
                    atexit.register(self.cerrar)
        return self._pool

    def cerrar(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None

    def _traducir(self, e: Exception) -> NoDisponible:
        if isinstance(e, psycopg.errors.UndefinedTable | psycopg.errors.InvalidSchemaName):
            return NoDisponible(self.mensajes["esquema"])
        return NoDisponible(self.mensajes["conexion"])

    @contextmanager
    def transaccion(self):
        """Un cursor dentro de una transaccion: commit al salir, rollback si hay excepcion."""
        try:
            with self.pool().connection() as conn:
                with conn.cursor() as cur:
                    yield cur
        except (psycopg.errors.UndefinedTable, psycopg.errors.InvalidSchemaName, psycopg.OperationalError) as e:
            raise self._traducir(e) from e

    def todos(self, sql: str, params=None) -> list[dict]:
        with self.transaccion() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()

    def uno(self, sql: str, params=None) -> dict | None:
        filas = self.todos(sql, params)
        return filas[0] if filas else None

    def ejecutar(self, sql: str, params=None) -> int:
        """Devuelve las filas afectadas."""
        with self.transaccion() as cur:
            cur.execute(sql, params or ())
            return cur.rowcount
