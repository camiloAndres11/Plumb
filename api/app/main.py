"""Servicio HTTP de Plomada. Un solo proceso sirve tres cosas en el mismo
puerto (necesario en Render, que solo expone un puerto por servicio):

  - `/v1/*`  la API REST publica de datos. Es la via de acceso para
             cualquiera: periodistas, otras herramientas, otros tableros.
             Documentada en API.md y en /docs.
  - `/mcp`   el servidor MCP (streamable-http), llamado por la API de
             Claude para responder preguntas conversacionales.
  - `/chat`  el proxy que el front consume, que le pasa a Claude la URL
             publica de este mismo servicio para que use `/mcp`.

Las tres comparten la misma capa de consulta (`app.consultas`) sobre las
tablas `api_*` de Postgres, que carga `pipeline/load_postgres.py`. No hay
SQL en ningun otro sitio del servicio.

BYOK (bring your own key): `/chat` exige que cada usuario provea SU
PROPIA API key de Anthropic en el header `X-Anthropic-Api-Key`. Este
servicio nunca la guarda -- se usa en memoria para esa sola llamada y se
descarta. No existe una API key "del equipo" en Render: el uso lo paga
cada usuario, no Plomada. Ver MCP.md para el contrato exacto.
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict, deque
from contextlib import AsyncExitStack, asynccontextmanager

import anthropic
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel

from app import db
from app.config import AVISO, VERSION_API, config
from app.formatos import error
from app.mcp.server import mcp
from app.routers import actores, agregados, alertas, catalogo, contratos, red

log = logging.getLogger("plomada")

MODEL = "claude-opus-5"
MCP_BETA = "mcp-client-2025-11-20"
MCP_SERVER_NAME = "plomada"

# URL publica de ESTE MISMO servicio + la ruta del MCP montado abajo.
# Claude llama a esta URL desde la nube de Anthropic: en local, sin tunel
# (ngrok/Cloudflare Tunnel), Claude no puede alcanzarla -- ver MCP.md.
MCP_SERVER_URL = config.self_url.rstrip("/") + "/mcp"

SYSTEM_PROMPT = (
    "Respondes preguntas sobre datos publicos de contratacion de obra publica "
    "en Colombia (SECOP II) usando las tools de Plomada disponibles. "
    "'Riesgo' aqui es un indicio para priorizar investigacion periodistica y "
    "control social, NUNCA prueba de un delito: no afirmes que un contrato "
    "marcado es fraude, di que presenta indicios y cuales. Si una tool no "
    "encuentra nada, dilo -- no inventes cifras ni nombres."
)

DESCRIPCION = """
Indicios de riesgo en la **contratacion de obra publica de Colombia**, a partir de
datos 100% publicos del SECOP II.

**Riesgo no es fraude.** Esta API produce indicios para priorizar investigacion
periodistica y control social. Ninguna cifra de aqui prueba un delito, y el
proyecto no afirma que lo pruebe. Cada respuesta lleva ese aviso en `meta.aviso`;
en CSV va en la cabecera `X-Plomada-Aviso`.

Antes de citar cualquier cifra, lee `GET /v1/meta`: trae la cobertura real de cada
campo y la lista de limitaciones que hay que decir en voz alta.

Universo: **77.864 contratos** de construccion (obra, interventoria, consultoria,
concesion y APP), **$209 billones COP**. Interventoria y consultoria se incluyen a
proposito: que el que vigila la obra pertenezca a la misma red que el que la
construye es el mecanismo central del fraude en obra publica, y solo se ve
teniendo los dos lados.

Todos los endpoints de datos son **de solo lectura**, publicos y sin autenticacion.
Los de listado aceptan `?formato=csv`.

Documentacion narrada: [API.md](https://github.com/JoseSLK/Plumb/blob/main/API.md)
"""

ETIQUETAS = [
    {"name": "Catalogo", "description": "Indice, metadatos, cobertura y glosario de banderas."},
    {"name": "Agregados", "description": "Las mismas cifras del tablero, por HTTP."},
    {"name": "Contratos", "description": "Busqueda y ficha completa con la evidencia de cada bandera."},
    {"name": "Actores", "description": "Entidades contratantes y proveedores."},
    {"name": "Red", "description": "Grupos economicos de proveedores unidos por llaves compartidas."},
    {"name": "Alertas pre-adjudicacion",
     "description": "Licitaciones que todavia aceptan ofertas, donde una observacion aun sirve."},
    {"name": "Asistente", "description": "Chat conversacional (BYOK) y servidor MCP."},
    {"name": "Servicio", "description": "Salud del servicio."},
]

# Proteccion anti DNS-rebinding del transporte MCP: por defecto rechaza
# cualquier Host que no este en la lista blanca (vacia por defecto), con
# 421 "Invalid Host header" -- probado contra el deploy real en Render antes
# de agregar esto. SELF_HOST cubre tanto el host publico (Render) como
# localhost:8000 en desarrollo, segun de donde salga SELF_URL.
mcp_app = mcp.streamable_http_app(
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(allowed_hosts=[config.self_host]),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.database_url:
        log.warning(
            "DATABASE_URL no esta definida: /v1/* respondera 503. "
            "Carga la base con 'python pipeline/load_postgres.py'."
        )
    if "SELF_URL" not in os.environ:
        # En produccion esto no es cosmetico: SELF_URL alimenta el
        # allowlist de Host del transporte MCP y la URL que Claude usa
        # para alcanzarlo. Con el valor por defecto, /mcp responde 421 a
        # todo el mundo y /chat no puede funcionar.
        log.warning(
            "SELF_URL no esta definida; usando %s. En un deploy real ponla en la "
            "URL publica del servicio o /mcp respondera 421.", config.self_url
        )
    async with AsyncExitStack() as stack:
        # sin esto el servidor MCP monta las rutas pero nunca arranca su
        # session manager -- Starlette no propaga el lifespan de un sub-app
        # montado automaticamente, hay que entrarlo a mano. Verificado con
        # una prueba de humo antes de dejarlo asi.
        await stack.enter_async_context(mcp_app.router.lifespan_context(mcp_app))
        try:
            yield
        finally:
            db.cerrar()


app = FastAPI(
    title="Plomada API",
    version=VERSION_API,
    summary="Indicios de riesgo en contratacion de obra publica de Colombia (SECOP II)",
    description=DESCRIPCION,
    openapi_tags=ETIQUETAS,
    license_info={"name": "Datos publicos del Estado colombiano"},
    lifespan=lifespan,
)

# Los datos son publicos y la API no usa cookies ni credenciales de
# servidor, asi que restringir origenes no protegeria nada: por defecto
# se abre. CORS_ORIGINS permite cerrarla si algun dia hace falta.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.origenes,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Plomada-Aviso", "Content-Disposition"],
)


# ---------------------------------------------------------------------
# Errores: un solo formato, para que un cliente pueda programar contra el
# ---------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def _http(request: Request, exc: HTTPException):
    codigos = {400: "parametro_invalido", 404: "no_encontrado",
               429: "limite_alcanzado", 503: "datos_no_disponibles"}
    return error(codigos.get(exc.status_code, "error"), str(exc.detail), exc.status_code)


@app.exception_handler(RequestValidationError)
async def _validacion(request: Request, exc: RequestValidationError):
    return error(
        "parametro_invalido",
        "uno o mas parametros de la consulta no son validos",
        422,
        exc.errors(),
    )


@app.exception_handler(ValueError)
async def _valor(request: Request, exc: ValueError):
    """app.consultas levanta ValueError cuando un `orden`, una `bandera` o
    un `universo` no estan en la lista blanca. Es culpa del cliente (400),
    no del servidor, y el mensaje dice cuales son los validos."""
    return error("parametro_invalido", str(exc), 400)


@app.exception_handler(db.DatosNoDisponibles)
async def _sin_datos(request: Request, exc: db.DatosNoDisponibles):
    return error("datos_no_disponibles", str(exc), 503)


# ---------------------------------------------------------------------
# API publica de datos
# ---------------------------------------------------------------------
for r in (catalogo.router, agregados.router, contratos.router,
          actores.router, red.router, alertas.router):
    app.include_router(r, prefix="/v1")


@app.get("/health", tags=["Servicio"], summary="Salud del servicio")
def health():
    """Responde aunque la base no este cargada: sirve para el health check
    del hosting, no para saber si hay datos (para eso, GET /v1/meta)."""
    return {"ok": True, "version": VERSION_API, "aviso": AVISO}


# ---------------------------------------------------------------------
# Asistente conversacional (BYOK)
# ---------------------------------------------------------------------
class Turno(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    mensaje: str
    historial: list[Turno] = []


# ---------------------------------------------------------------------
# Techos de /chat. BYOK cuida la plata del lector; esto cuida el
# SERVICIO. Contadores en memoria del proceso: Render corre una sola
# instancia y no vale la pena un Redis para esto. Si algun dia hay
# varias instancias, cada una aplica su techo por separado -- degrada a
# un limite mas laxo, no a ninguno.
# ---------------------------------------------------------------------
_chat_activos = 0                                  # streams vivos ahora mismo
_chat_golpes: dict[str, deque] = defaultdict(deque)  # ip -> tiempos recientes


def _ip_cliente(request: Request) -> str:
    # La IP del socket, que uvicorn ya corrigio con --proxy-headers y la
    # lista de proxies privados del Dockerfile. Tomar el primer valor de
    # X-Forwarded-For dejaba que el cliente se inventara la IP y saltara el
    # techo. config.proxies_confiables es la salida para despliegues sin
    # esa capa: descuenta N saltos desde la derecha.
    socket = request.client.host if request.client else "?"
    n = config.proxies_confiables
    if n <= 0:
        return socket
    saltos = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    return saltos[-n] if len(saltos) >= n else socket


def _dentro_del_limite(ip: str) -> bool:
    """Ventana deslizante por IP: config.chat_max_por_ip peticiones por
    config.chat_ventana_seg segundos. Devuelve False sin registrar el
    golpe cuando la IP ya agoto su cupo."""
    ahora = time.monotonic()
    corte = ahora - config.chat_ventana_seg
    golpes = _chat_golpes[ip]
    while golpes and golpes[0] < corte:
        golpes.popleft()
    if len(golpes) >= config.chat_max_por_ip:
        return False
    golpes.append(ahora)
    # Que el dict no crezca sin limite con IPs que pasaron una vez.
    if len(_chat_golpes) > 10_000:
        for vieja in [k for k, v in _chat_golpes.items() if not v or v[-1] < corte]:
            del _chat_golpes[vieja]
    return True


@app.post(
    "/chat",
    tags=["Asistente"],
    summary="Chat con los datos (requiere tu propia API key de Anthropic)",
)
async def chat(
    req: ChatRequest,
    request: Request,
    x_anthropic_api_key: str = Header(alias="X-Anthropic-Api-Key"),
):
    # async de punta a punta a proposito: la version sincrona ocupaba un
    # hilo del threadpool de Starlette (~40 en total, compartidos con TODA
    # la API de datos) durante los minutos que dura un stream. Con ~40
    # conversaciones abiertas, /v1/* entero dejaba de responder.
    if not _dentro_del_limite(_ip_cliente(request)):
        raise HTTPException(
            status_code=429,
            detail="demasiadas consultas seguidas desde esta direccion; espera un minuto",
        )

    messages = [{"role": t.role, "content": t.content} for t in req.historial]
    messages.append({"role": "user", "content": req.mensaje})

    async def generar():
        # El front debe poder mostrar "el asistente no esta disponible" en
        # vez de que se le caiga la conexion -- mismo criterio que el
        # tablero con alertas.json opcional (ver MCP.md).
        global _chat_activos
        # El cupo se toma y se suelta DENTRO del generador (sin await entre
        # ver y contar: el event loop lo hace atomico). Tomarlo en el
        # endpoint dejaria un cupo colgado si el cliente corta antes de que
        # el stream arranque.
        if _chat_activos >= config.chat_max_concurrentes:
            yield "data: %s\n\n" % json.dumps(
                {"error": "Hay muchas conversaciones abiertas en este momento, "
                          "intenta de nuevo en unos segundos"}, ensure_ascii=False)
            return
        _chat_activos += 1
        # Cliente nuevo por request, con la key que mando el usuario --
        # nunca un cliente compartido con una key del servidor (no existe
        # tal cosa aqui). Se crea con el cupo ya tomado y se cierra al final.
        client = anthropic.AsyncAnthropic(api_key=x_anthropic_api_key)
        try:
            async with client.beta.messages.stream(
                model=MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                betas=[MCP_BETA],
                mcp_servers=[{"type": "url", "url": MCP_SERVER_URL, "name": MCP_SERVER_NAME}],
                tools=[{"type": "mcp_toolset", "mcp_server_name": MCP_SERVER_NAME}],
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield "data: %s\n\n" % json.dumps({"delta": text}, ensure_ascii=False)
            yield "data: %s\n\n" % json.dumps({"done": True})
        except anthropic.AuthenticationError:
            yield "data: %s\n\n" % json.dumps({"error": "Tu API key de Anthropic no es valida"})
        except anthropic.RateLimitError:
            yield "data: %s\n\n" % json.dumps({"error": "Limite de uso alcanzado, intenta mas tarde"})
        except anthropic.APIStatusError as e:
            yield "data: %s\n\n" % json.dumps({"error": "Error de la API (%s)" % e.status_code})
        except anthropic.APIConnectionError:
            yield "data: %s\n\n" % json.dumps({"error": "No se pudo conectar con el asistente"})
        except Exception:
            yield "data: %s\n\n" % json.dumps({"error": "El asistente no esta disponible ahora"})
        finally:
            _chat_activos -= 1
            await client.close()

    return StreamingResponse(
        generar(),
        media_type="text/event-stream",
        # Sin esto algunos proxies (nginx y afines) acumulan el stream y lo
        # entregan por bloques en vez de dejarlo fluir delta a delta.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


app.mount("/mcp", mcp_app)
