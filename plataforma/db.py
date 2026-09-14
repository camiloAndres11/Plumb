"""Acceso a Postgres de la plataforma: el pool de pliego/comun/pg.py con
el DSN y los mensajes de esta app.

    from plataforma import db
    fila = db.uno("SELECT * FROM pliego.usuarios WHERE email = %s", [email])
    filas = db.todos("SELECT ...")
    db.ejecutar("UPDATE ...", [...])
    with db.transaccion() as cur:      # varias sentencias, todo o nada
        cur.execute(...); cur.execute(...)
"""
from __future__ import annotations

from plataforma.config import config
from pliego.comun.pg import NoDisponible as BaseNoDisponible
from pliego.comun.pg import Pg

_pg = Pg(lambda: config.dsn,
         sin_dsn="falta DATABASE_URL en el entorno (ver .env.example)",
         sin_esquema="la base no tiene el esquema `pliego`; corre 'python -m plataforma.migrar'")

pool, cerrar, transaccion, todos, uno, ejecutar = _pg.pool, _pg.cerrar, _pg.transaccion, _pg.todos, _pg.uno, _pg.ejecutar


def disponible() -> tuple[bool, str]:
    """Para /health: (ok, detalle) sin lanzar."""
    try:
        fila = uno("SELECT count(*) AS n FROM pliego.migraciones")
        return True, f"{fila['n']} migraciones"
    except BaseNoDisponible as e:
        return False, str(e)


__all__ = ["BaseNoDisponible", "cerrar", "disponible", "ejecutar", "pool", "todos", "transaccion", "uno"]
