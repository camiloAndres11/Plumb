"""Configuracion de la plataforma, en un solo sitio (patron de api/app/config.py).

Todo sale del entorno. En local, del `.env` de la raiz (lo carga
pliego/comun/entorno.py al importar); en Render, de las variables del
servicio. Ver .env.example para la lista y docs/enfoques/plataforma.md para
que hace cada una.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from pliego.comun import entorno  # noqa: F401  (carga .env al importar)

VERSION = "0.1.0"
PUERTO = 8100
RAIZ = Path(__file__).resolve().parents[1]


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

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
    # Raiz de datos en disco: warehouse DuckDB, cache de Croma, PDFs. En
    # Render debe ser el punto de montaje del disco persistente.
    plataforma_datos: str = str(RAIZ / "data")
    # Sesion: dias de inactividad antes de expirar.
    sesion_dias: int = 30
    # Saltos de X-Forwarded-For que se descuentan desde la derecha para hallar
    # la IP real. Por defecto 0: uvicorn ya resuelve la IP con --proxy-headers
    # y una lista de proxies de red privada (ver el Dockerfile), asi que vale
    # la del socket y la cabecera se ignora. Solo para despliegues sin esa
    # capa (p. ej. detras de un proxy con IP publica).
    proxies_confiables: int = 0

    @property
    def dsn(self) -> str:
        """Como api/app/config.py: acepta postgresql+psycopg:// y lo aplana."""
        url = self.database_url.strip()
        if not url:
            return ""
        esquema, _, resto = url.partition("://")
        return "postgresql://" + resto if "+" in esquema else url

    @property
    def admins(self) -> set[str]:
        return {a.strip().lower() for a in self.plataforma_admins.split(",") if a.strip()}

    @property
    def datos(self) -> Path:
        return Path(self.plataforma_datos)

    @property
    def cookies_seguras(self) -> bool:
        return self.base_url.startswith("https://")


config = Config()
