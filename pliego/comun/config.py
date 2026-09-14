"""Configuracion de Pliego, en un solo sitio.

Todo sale del entorno y, en local, del `.env` de la raiz del repo (lo lee
pydantic-settings; el entorno manda sobre el archivo). Ningun otro modulo
de pliego/, plataforma/ o demo/ lee os.environ: piden `config.actual()`.

    from pliego.comun import config as CFG
    if CFG.actual().croma_api_key: ...

La plataforma extiende esta clase (plataforma/config.py) y registra su
instancia con `usar()`, asi que hay UNA sola configuracion viva en el
proceso y los enfoques ven lo mismo que la plataforma. En las pruebas se
cambia con monkeypatch.setattr(CFG.actual(), "croma_hilos", 1), nunca con
variables de entorno.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parents[2]


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=RAIZ / ".env", env_file_encoding="utf-8", extra="ignore")

    # Fuente de datos de filtro, radar y simulador: "croma" (la demo con
    # datos de hoy), "warehouse" (la plataforma, por empresa) o vacio =
    # los parquet commiteados en pliego/*/fixtures/.
    pliego_fuente: str = ""

    # Croma (docs/enfoques/croma.md). Sin llave no hay descargas.
    croma_api_key: str = ""
    croma_api_url: str = "https://api.croma.run"
    croma_max_paginas: int = 30          # tope de paginas (de 100) por busqueda: cada una es 1 credito
    croma_desde_anio: int | None = None  # primer anio del historico; por defecto hace 4 anios
    croma_cache_horas: float = 24        # vigencia de la cache en disco por busqueda; 0 la desactiva
    croma_hilos: int = 4                 # busquedas en paralelo

    # Raiz de datos en disco: warehouse DuckDB, cache de Croma, PDFs. En
    # Render, el disco persistente. PLIEGO_WAREHOUSE fuerza la ruta del
    # DuckDB (lo usan las pruebas).
    plataforma_datos: Path = RAIZ / "data"
    pliego_warehouse: Path | None = None

    # Extraccion de pliegos con Claude (plataforma/extraccion.py).
    anthropic_api_key: str = ""

    @field_validator("pliego_fuente", mode="before")
    @classmethod
    def _fuente(cls, v):
        return str(v or "").strip().lower()

    @property
    def datos(self) -> Path:
        return Path(self.plataforma_datos)

    @property
    def warehouse(self) -> Path:
        return Path(self.pliego_warehouse) if self.pliego_warehouse else self.datos / "warehouse" / "pliego.duckdb"

    @property
    def cache_croma(self) -> Path:
        return self.datos / "cache" / "croma"


_actual: Config | None = None


def actual() -> Config:
    """La configuracion viva del proceso (se construye una vez)."""
    global _actual
    if _actual is None:
        _actual = Config()
    return _actual


def usar(config: Config) -> Config:
    """Registra una configuracion (la plataforma registra la suya, que
    extiende esta)."""
    global _actual
    _actual = config
    return config
