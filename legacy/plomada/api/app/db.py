"""Acceso a Postgres: un pool y tres helpers. Nada mas.

Toda consulta del proyecto pasa por aqui -- el API REST y las tools del
servidor MCP -- para que haya un solo sitio donde mirar cuando algo de
datos se comporta raro.

El pool es perezoso: se abre en la primera consulta, no al importar. Asi
el servicio arranca y responde /health y /docs aunque Postgres todavia no
este cargado, que es exactamente el estado de un deploy nuevo antes de
correr pipeline/load_postgres.py.
"""
from __future__ import annotations

import atexit
import threading

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import config


class DatosNoDisponibles(RuntimeError):
    """Postgres no esta configurado o no tiene la capa de serving cargada.

    Es un error de operacion, no del cliente: el API lo traduce a 503 con
    un mensaje que dice que comando falta correr.
    """


_pool: ConnectionPool | None = None
_lock = threading.Lock()


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                if not config.dsn:
                    raise DatosNoDisponibles(
                        "falta DATABASE_URL en el entorno; apunta a un Postgres "
                        "cargado con 'python pipeline/load_postgres.py'"
                    )
                # min_size=1: Render duerme los servicios del plan gratis y
                # no vale la pena mantener conexiones abiertas de mas.
                _pool = ConnectionPool(
                    config.dsn, min_size=1, max_size=8, open=True, timeout=10,
                    kwargs={"row_factory": dict_row},
                )
                # El lifespan de FastAPI ya cierra el pool, pero el servidor
                # MCP tambien corre como proceso suelto (stdio/--http) y ahi
                # no hay lifespan. Sin esto, el pool se recoge en la
                # finalizacion del interprete y Python >=3.13 escupe un
                # PythonFinalizationError al salir.
                atexit.register(cerrar)
    return _pool


def cerrar() -> None:
    """Cierra el pool al apagar el servicio (lo llama el lifespan)."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def consultar(sql: str, params=None) -> list[dict]:
    """Ejecuta y devuelve todas las filas como dicts."""
    try:
        with pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                return cur.fetchall()
    except psycopg.errors.UndefinedTable as e:
        # Pasa cuando el Postgres existe pero nunca se cargo la capa de
        # serving. Mensaje accionable en vez de un 500 opaco.
        raise DatosNoDisponibles(
            "la base no tiene las tablas del API (%s); corre "
            "'python pipeline/load_postgres.py'" % e.diag.table_name
        ) from e
    except psycopg.OperationalError as e:
        raise DatosNoDisponibles("no se pudo conectar a la base de datos") from e


def consultar_uno(sql: str, params=None) -> dict | None:
    filas = consultar(sql, params)
    return filas[0] if filas else None


def contar(desde: str, where: str = "", params=None) -> int:
    """Total de filas de una consulta, para el bloque de paginacion.

    `desde` y `where` son fragmentos SQL construidos por app.consultas a
    partir de listas blancas; los VALORES siempre van en `params`.
    """
    sql = "SELECT count(*) AS n FROM %s" % desde
    if where:
        sql += " WHERE " + where
    fila = consultar_uno(sql, params)
    return int(fila["n"]) if fila else 0


def existe_tabla(nombre: str) -> bool:
    """Para los endpoints opcionales (alertas), que dependen de que
    alguien haya corrido pipeline/alertas.py."""
    fila = consultar_uno("SELECT to_regclass(%s) AS t", [nombre])
    return bool(fila and fila["t"])
