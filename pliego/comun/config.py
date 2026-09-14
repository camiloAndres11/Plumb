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

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parents[2]


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=RAIZ / ".env", env_file_encoding="utf-8", extra="ignore")

    pliego_fuente: str = Field("", description="Fuente de datos de filtro, radar y simulador: `croma` (la demo con datos de hoy), "
                               "`warehouse` (la plataforma, por empresa; la fija sola) o vacio = los parquet de pliego/*/fixtures/")
    # Croma (docs/enfoques/croma.md). Sin llave no hay descargas.
    croma_api_key: str = Field("", description="Llave de organizacion de Croma (platform.usecroma.com > API keys), croma_live_...")
    croma_api_url: str = Field("https://api.croma.run", description="Base de la API de Croma")
    croma_max_paginas: int = Field(30, description="Tope de paginas (de 100) por busqueda; cada una es 1 credito")
    croma_desde_anio: int | None = Field(None, description="Primer anio del historico a traer; por defecto hace 4 anios")
    croma_cache_horas: float = Field(24, description="Vigencia en horas de la cache en disco por busqueda; 0 la desactiva")
    croma_hilos: int = Field(4, description="Busquedas a Croma en paralelo")
    plataforma_datos: Path = Field(RAIZ / "data", description="Raiz de datos en disco: warehouse DuckDB, cache de Croma, PDFs. "
                                   "En Render, el disco persistente")
    pliego_warehouse: Path | None = Field(None, description="Ruta del DuckDB del warehouse; por defecto $PLATAFORMA_DATOS/warehouse/pliego.duckdb")
    anthropic_api_key: str = Field("", description="Llave de Anthropic de la plataforma para extraer pliegos con Claude; "
                                   "vacia = los pliegos quedan en 'subido'")

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


SECRETOS = {"croma_api_key", "anthropic_api_key", "database_url", "secret_key", "smtp_url"}


def ejemplo_env(cls: type[Config]) -> str:
    """El contenido de .env.example, generado de los campos (una sola fuente)."""
    lineas = ["# Copia este archivo a .env (que esta en .gitignore) y pon los valores reales.",
              "# Generado con `python -m pliego.comun.config --ejemplo` desde pliego/comun/config.py",
              "# y plataforma/config.py: cada variable esta descrita y tiene su valor por defecto ahi.", ""]
    for nombre, campo in cls.model_fields.items():
        if campo.description:
            lineas.append(f"# {campo.description}")
        defecto = campo.default
        if nombre in SECRETOS or defecto in (None, ""):
            valor = ""
        elif isinstance(defecto, Path):
            valor = str(defecto.relative_to(RAIZ)) if defecto.is_relative_to(RAIZ) else str(defecto)
        else:
            valor = str(defecto)
        lineas.append(f"{nombre.upper()}={valor}")
        lineas.append("")
    lineas += ["# ---- Solo para docker compose (deploy/docker-compose.yml), no la lee la app ----",
               "# Clave del Postgres del contenedor; sin ella compose no arranca. DATABASE_URL debe llevar la misma.",
               "POSTGRES_PASSWORD="]
    return "\n".join(lineas).rstrip() + "\n"


if __name__ == "__main__":
    import sys
    if "--ejemplo" in sys.argv:
        import plataforma.config as PC  # la configuracion completa (base + plataforma)
        print(ejemplo_env(PC.Config), end="")
