"""Configuracion del servicio, en un solo sitio.

Todo sale del entorno. En Render son variables del servicio; en local,
docker-compose.yml o el shell. No hay archivo de secretos y no hay
ANTHROPIC_API_KEY: /chat es BYOK, cada usuario manda la suya en el
header de cada request (ver MCP.md).
"""
from __future__ import annotations

from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict

VERSION_API = "1.0.0"

# El aviso viaja con cada respuesta. No es decoracion legal: es la
# afirmacion central del proyecto, y una respuesta de la API sin ella
# invita exactamente a la lectura que el proyecto niega.
AVISO = (
    "Riesgo no es fraude. Estas cifras son indicios para priorizar investigacion "
    "periodistica y control social; ninguna prueba un delito."
)

FUENTE = "SECOP II - datos.gov.co (jbjy-vk9h contratos, p6dx-8zbt procesos)"


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    # Postgres cargado por pipeline/load_postgres.py. Sin esto la API
    # arranca igual (para que /health y /docs respondan) pero cada
    # endpoint de datos devuelve 503 con un mensaje que dice que hacer.
    database_url: str = ""

    # URL publica de ESTE servicio. Claude la usa para alcanzar /mcp desde
    # la nube de Anthropic, y de ella sale el allowlist de Host del
    # transporte MCP.
    self_url: str = "http://127.0.0.1:8000"

    # CORS. Vacio = abierto: los datos son publicos y la API no usa
    # cookies ni credenciales de servidor, asi que restringir origenes no
    # protege nada y solo estorba a quien la integre.
    cors_origins: str = ""

    # Techos de paginacion. El de REST es mas alto que el del MCP porque
    # una respuesta de 200 filas a un cliente HTTP es normal, y 200 filas
    # en el contexto de un modelo no lo es.
    limite_default: int = 50
    limite_max: int = 200
    limite_max_mcp: int = 50

    # Techos del asistente /chat. BYOK protege la plata (cada usuario paga
    # con su propia key) pero NO protege el servicio: cada stream abierto
    # es una conexion viva con Anthropic durante minutos, y sin techo unas
    # decenas de conexiones lentas acaparan el proceso entero -- incluida
    # la API de datos, que comparte el mismo servidor. Ademas, sin limite
    # por IP el proxy sirve de relay anonimo para probar keys ajenas.
    # Saltos de X-Forwarded-For que se descuentan desde la derecha para hallar
    # la IP real. Por defecto 0: uvicorn ya resuelve la IP con --proxy-headers
    # y una lista de proxies de red privada (ver el Dockerfile), asi que vale
    # la del socket y la cabecera se ignora. Solo para despliegues sin esa
    # capa (p. ej. detras de un proxy con IP publica).
    proxies_confiables: int = 0
    chat_max_concurrentes: int = 8
    chat_max_por_ip: int = 6      # peticiones por IP por ventana
    chat_ventana_seg: int = 60

    @property
    def dsn(self) -> str:
        """DSN normalizado. Acepta la forma de SQLAlchemy
        (`postgresql+psycopg://`) porque es la que suele quedar en los
        compose y en los paneles de hosting, pero psycopg no la parsea."""
        url = self.database_url.strip()
        if not url:
            return ""
        esquema, _, resto = url.partition("://")
        if "+" in esquema:
            return "postgresql://" + resto
        return url

    @property
    def self_host(self) -> str:
        return urlparse(self.self_url).netloc

    @property
    def origenes(self) -> list[str]:
        lista = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return lista or ["*"]


config = Config()
