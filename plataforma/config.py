"""Configuracion de la plataforma: extiende la de pliego/comun/config.py con
lo suyo (Postgres, secreto, correo, admins, topes) y la registra como LA
configuracion del proceso, asi los enfoques ven la misma instancia.

Todo sale del entorno; en local, del `.env` de la raiz. Ver .env.example
para la lista y docs/enfoques/plataforma.md para que hace cada una.
"""
from __future__ import annotations

from pydantic import field_validator

from pliego.comun import config as base

VERSION = "0.1.0"
PUERTO = 8100
RAIZ = base.RAIZ


class Config(base.Config):
    # Postgres con el esquema `pliego` (python -m plataforma.migrar lo crea).
    database_url: str = ""
    # Firma de cookies y tokens. Sin ella la app arranca (para /health)
    # pero cualquier ruta con sesion responde 503 diciendo que falta.
    secret_key: str = ""
    # URL publica de ESTE servicio: va en los enlaces de los correos.
    base_url: str = f"http://127.0.0.1:{PUERTO}"
    # smtp://usuario:clave@host:587?tls=1 ; vacio = los correos se imprimen
    # en el log (y se devuelven a quien los pidio, para las pruebas).
    smtp_url: str = ""
    correo_remitente: str = "Pliego <no-responder@pliego.co>"
    # Emails (separados por coma) que ven /admin.
    plataforma_admins: str = ""
    # Sesion: dias de inactividad antes de expirar, y caducidad absoluta
    # desde que se abrio, aunque se siga usando.
    sesion_dias: int = 30
    sesion_max_dias: int = 90
    # Saltos de X-Forwarded-For que se descuentan desde la derecha para hallar
    # la IP real. Por defecto 0: uvicorn ya resuelve la IP con --proxy-headers
    # y una lista de proxies de red privada (ver el Dockerfile), asi que vale
    # la del socket y la cabecera se ignora. Solo para despliegues sin esa
    # capa (p. ej. detras de un proxy con IP publica).
    proxies_confiables: int = 0
    # Topes de la extraccion de pliegos con Claude, que paga la plataforma:
    # paginas maximas por PDF (se cuentan ANTES de llamar) y presupuesto en
    # USD por empresa y mes calendario (suma de costo_usd de sus pliegos).
    pliego_max_paginas: int = 300
    pliego_presupuesto_usd_mes: float = 25.0

    @field_validator("pliego_fuente", mode="after")
    @classmethod
    def _siempre_warehouse(cls, v):
        # La plataforma SIEMPRE sirve los enfoques desde el warehouse por
        # empresa (pliego/comun/fuente.py modo warehouse), aunque el .env
        # compartido con la demo pida `croma` o nada.
        return "warehouse"

    @property
    def dsn(self) -> str:
        """Acepta postgresql+psycopg:// (forma de SQLAlchemy) y lo aplana."""
        url = self.database_url.strip()
        if not url:
            return ""
        esquema, _, resto = url.partition("://")
        return "postgresql://" + resto if "+" in esquema else url

    @property
    def admins(self) -> set[str]:
        return {a.strip().lower() for a in self.plataforma_admins.split(",") if a.strip()}

    @property
    def cookies_seguras(self) -> bool:
        return self.base_url.startswith("https://")


config = base.usar(Config())
__all__ = ["PUERTO", "RAIZ", "VERSION", "Config", "config"]
