"""Configuracion de la plataforma: extiende la de pliego/comun/config.py con
lo suyo (Postgres, secreto, correo, admins, topes) y la registra como LA
configuracion del proceso, asi los enfoques ven la misma instancia.

Todo sale del entorno; en local, del `.env` de la raiz. Ver .env.example
para la lista y docs/enfoques/plataforma.md para que hace cada una.
"""
from __future__ import annotations

from pydantic import Field, field_validator

from pliego.comun import config as base

VERSION = "0.1.0"
PUERTO = 8100
RAIZ = base.RAIZ


class Config(base.Config):
    database_url: str = Field("", description="Postgres con el esquema `pliego` (python -m plataforma.migrar). "
                              "Con docker compose: postgresql://plomada:<POSTGRES_PASSWORD>@127.0.0.1:5432/plomada")
    secret_key: str = Field("", description="Firma de cookies y tokens, >= 32 bytes: python -c \"import secrets; print(secrets.token_urlsafe(48))\". "
                            "Sin ella la app arranca (para /health) pero toda ruta con sesion responde 503")
    base_url: str = Field(f"http://127.0.0.1:{PUERTO}", description="URL publica de ESTE servicio; va en los enlaces de los correos")
    smtp_url: str = Field("", description="smtp://usuario:clave@host:587?tls=1 ; vacio = los correos se imprimen en el log")
    correo_remitente: str = Field("Pliego <no-responder@pliego.co>", description="Remitente de los correos")
    plataforma_admins: str = Field("", description="Emails separados por coma que ven /admin")
    sesion_dias: int = Field(30, description="Sesion: dias de inactividad antes de expirar")
    sesion_max_dias: int = Field(90, description="Sesion: caducidad absoluta desde que se abrio, aunque se siga usando")
    proxies_confiables: int = Field(0, description="Saltos de X-Forwarded-For que se descuentan desde la derecha para hallar la IP real. "
                                    "0 = uvicorn ya la resuelve con --proxy-headers y su lista de proxies privados (ver el Dockerfile)")
    pliego_max_paginas: int = Field(300, description="Paginas maximas por PDF en la extraccion con Claude (se cuentan antes de llamar)")
    pliego_presupuesto_usd_mes: float = Field(25.0, description="Presupuesto en USD de extraccion por empresa y mes calendario")

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
