"""Trabajos en segundo plano: descargar departamentos de Croma al warehouse
y extraer pliegos con Claude.

Un solo hilo trabajador con una cola (la API de Croma es lenta y solo hay
tope mensual de creditos: no hay razon para mas), y un hilo reloj que a las
05:00 de Colombia encola el refresco de todo lo que ya esta `lista`. Al
arrancar se retoma lo `pendiente` o en `error` y lo `lista` con mas de 24 h,
y los pliegos que quedaron `subido` o `extrayendo`.

Cada trabajo es ("departamento", nombre) o ("pliego", id).

Estado en pliego.descargas_departamento (Postgres): pendiente -> descargando
-> lista | error, con as_of, paginas y el error si lo hubo. /empresa/datos
lo muestra y el admin puede reintentar.

Descarga:
  - primera vez: todo el historico desde CROMA_DESDE_ANIO (completa)
  - despues: desde ultima_ok - 2 dias, incremental (INSERT OR REPLACE por
    id; los abiertos se reemplazan enteros, que son pocos)
  - la cache en disco de fuente._paginas evita repetir paginas del dia
Nunca en el hilo de una peticion: una descarga son minutos.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from datetime import UTC, datetime, timedelta, timezone

from plataforma import db, extraccion, pliegos
from pliego.comun import cache, croma, fuente, warehouse

log = logging.getLogger("pliego.trabajos")
COLOMBIA = timezone(timedelta(hours=-5))
HORA_REFRESCO = 5          # 05:00 America/Bogota
REFRESCO_CADA_H = 24
_cola: queue.Queue = queue.Queue()
_en_cola: set[tuple] = set()
_candado = threading.Lock()
_hilos: list[threading.Thread] = []
_parar = threading.Event()
ultimo_creditos: int | None = None   # lo que Croma reporto en la ultima descarga (para /admin)


def _encolar(trabajo: tuple) -> bool:
    """True si se encolo; False si ya estaba en cola o en curso."""
    with _candado:
        if trabajo in _en_cola:
            return False
        _en_cola.add(trabajo)
    _cola.put(trabajo)
    return True


def encolar(departamento: str) -> bool:
    return _encolar(("departamento", departamento))


def encolar_pliego(pliego_id: int) -> bool:
    return _encolar(("pliego", int(pliego_id)))


def en_cola() -> list[str]:
    with _candado:
        return sorted(f"{t}:{v}" if t == "pliego" else v for t, v in _en_cola)


# ------------------------------------------------------------ una descarga
def descargar_departamento(departamento: str, api=None) -> dict:
    """Descarga (completa o incremental) y escribe el warehouse. Devuelve
    lo que escribio; anota el estado en Postgres en cada paso."""
    fila = db.uno("SELECT * FROM pliego.descargas_departamento WHERE departamento = %s", [departamento])
    ultima_ok = fila["ultima_ok"] if fila else None
    db.ejecutar("INSERT INTO pliego.descargas_departamento (departamento, estado, actualizado) VALUES (%s, 'descargando', now()) "
                "ON CONFLICT (departamento) DO UPDATE SET estado = 'descargando', error = NULL, actualizado = now()", [departamento])
    try:
        api = api or croma.CromaCliente()
        incremental = ultima_ok is not None
        desde = (ultima_ok - timedelta(days=2)).date().isoformat() if incremental else None
        consultas = fuente.consultas_para([departamento], desde=desde)
        contratos, adjudicados, abiertos, errores = fuente.traer(api, consultas)
        if errores:
            # Nada a medias en el warehouse: con una busqueda fallida el
            # departamento queda en error y se reintenta; las busquedas que
            # si salieron quedan en la cache de disco y no se repiten.
            raise croma.CromaError("; ".join(e["error"] for e in errores)[:500])
        as_of = max((r.get("_as_of") or "" for r in adjudicados + abiertos + contratos), default=None) or None
        resultado = warehouse.upsert(departamento, contratos, adjudicados, abiertos, as_of=as_of, incremental=incremental)
        cache.limpiar_todo()
        global ultimo_creditos
        if api.creditos_restantes is not None:
            ultimo_creditos = api.creditos_restantes
        db.ejecutar("UPDATE pliego.descargas_departamento SET estado = 'lista', as_of = %s, ultima_ok = now(), paginas = %s, "
                    "error = NULL, actualizado = now() WHERE departamento = %s", [as_of, api.llamadas, departamento])
        log.info("descarga %s: %s (llamadas %s, creditos %s)", departamento, resultado, api.llamadas, api.creditos_restantes)
        return resultado
    except Exception as e:   # cualquier cosa: queda en error, visible en /empresa/datos
        log.exception("descarga %s fallo", departamento)
        db.ejecutar("UPDATE pliego.descargas_departamento SET estado = 'error', error = %s, actualizado = now() WHERE departamento = %s",
                    [str(e)[:500], departamento])
        raise


# ------------------------------------------------------------------ hilos
def _trabajador():
    while not _parar.is_set():
        try:
            trabajo = _cola.get(timeout=1)
        except queue.Empty:
            continue
        tipo, valor = trabajo
        try:
            if tipo == "departamento":
                descargar_departamento(valor)
            else:
                pliegos.extraer(valor)
        except Exception:
            pass   # ya quedo anotado en Postgres
        finally:
            with _candado:
                _en_cola.discard(trabajo)
            _cola.task_done()


def _reloj():
    """Cada minuto mira si toca el refresco diario."""
    ultimo_dia = None
    while not _parar.wait(60):
        ahora = datetime.now(COLOMBIA)
        if ahora.hour == HORA_REFRESCO and ultimo_dia != ahora.date():
            ultimo_dia = ahora.date()
            try:
                refrescar_todo()
            except Exception:
                log.exception("refresco diario fallo")


def refrescar_todo() -> int:
    """Encola todo lo `lista`. Devuelve cuantos encolo."""
    n = 0
    for f in db.todos("SELECT departamento FROM pliego.descargas_departamento WHERE estado = 'lista'"):
        n += encolar(f["departamento"])
    return n


def retomar_pendientes() -> int:
    """Al arrancar: lo pendiente, lo que quedo en error o a medias, lo listo
    con mas de REFRESCO_CADA_H horas, y los pliegos sin extraer."""
    limite = datetime.now(UTC) - timedelta(hours=REFRESCO_CADA_H)
    n = 0
    if croma.disponible():
        for f in db.todos("SELECT departamento FROM pliego.descargas_departamento WHERE estado IN ('pendiente', 'error', 'descargando') "
                          "OR (estado = 'lista' AND coalesce(ultima_ok, to_timestamp(0)) < %s) ORDER BY actualizado", [limite]):
            n += encolar(f["departamento"])
    if extraccion.disponible():
        for pid in pliegos.pendientes():
            n += encolar_pliego(pid)
    return n


def arrancar() -> None:
    """Lanza los hilos una sola vez por proceso. Sin CROMA_API_KEY no se
    descargan departamentos (se sirve lo que tenga el warehouse); sin
    ANTHROPIC_API_KEY no se extraen pliegos."""
    if _hilos:
        return
    if not croma.disponible():
        log.warning("sin CROMA_API_KEY: no se descargan departamentos; el warehouse se sirve como este")
    if not extraccion.disponible():
        log.warning("sin ANTHROPIC_API_KEY: los pliegos subidos no se extraen")
    if not croma.disponible() and not extraccion.disponible():
        return
    _parar.clear()
    for objetivo, nombre in ((_trabajador, "pliego-descargas"), (_reloj, "pliego-reloj")):
        h = threading.Thread(target=objetivo, name=nombre, daemon=True)
        h.start()
        _hilos.append(h)
    try:
        n = retomar_pendientes()
        if n:
            log.warning("retomando %d departamento(s) pendientes", n)
    except db.BaseNoDisponible as e:
        log.warning("no se pudo leer pendientes: %s", e)


def parar() -> None:
    _parar.set()
    for h in _hilos:
        h.join(timeout=2)
    _hilos.clear()


def esperar_cola(timeout: float = 600) -> None:
    """Para pruebas y scripts: bloquea hasta vaciar la cola."""
    fin = time.time() + timeout
    while time.time() < fin and (en_cola() or not _cola.empty()):
        time.sleep(0.2)
