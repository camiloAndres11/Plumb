"""Cache en memoria por ambito de datos, en lugar de lru_cache.

Los datos.py de los enfoques cacheaban con `@lru_cache(maxsize=1)`: valia
mientras habia UNA constructora y UN conjunto de datos. En la plataforma
hay muchas empresas y el warehouse cambia con cada descarga, asi que la
llave incluye:

  - el ambito (los departamentos de la empresa en contexto; () con fixtures)
  - la version del warehouse (sube con cada escritura)
  - la empresa, solo si `por_empresa=True` (lo que depende del perfil, como
    las evaluaciones del filtro; lo que solo depende de los datos, como
    los contratos cargados, se comparte entre empresas del mismo ambito)
  - los argumentos de la llamada

Sin contexto ni warehouse (la demo, las pruebas) la llave es constante y
esto se comporta exactamente como el lru_cache de antes.

    @cache.por_ambito()                  # datos: se comparten por ambito
    def contratos(): ...
    @cache.por_ambito(por_empresa=True)  # depende del perfil
    def evaluaciones(): ...
    @cache.por_ambito(maxsize=512)       # con argumentos, como lru_cache
    def competidor(doc): ...
"""
from __future__ import annotations

import functools
import threading
from collections import OrderedDict

from pliego.comun import contexto

_TODAS: list = []


def _version() -> int:
    try:
        from pliego.comun import warehouse
        return warehouse.version()
    except Exception:
        return 0


def por_ambito(maxsize: int = 8, por_empresa: bool = False):
    def decorador(fn):
        guardado: OrderedDict = OrderedDict()
        candado = threading.Lock()

        @functools.wraps(fn)
        def envoltura(*args, **kwargs):
            e = contexto.get()
            llave = (contexto.ambito(), _version(), (e.empresa_id if (por_empresa and e) else None),
                     args, tuple(sorted(kwargs.items())))
            with candado:
                if llave in guardado:
                    guardado.move_to_end(llave)
                    return guardado[llave]
            valor = fn(*args, **kwargs)
            with candado:
                guardado[llave] = valor
                while len(guardado) > maxsize:
                    guardado.popitem(last=False)
            return valor

        def cache_clear():
            with candado:
                guardado.clear()

        envoltura.cache_clear = cache_clear
        _TODAS.append(envoltura)
        return envoltura
    return decorador


def limpiar_todo() -> None:
    """Vacia todas las caches (p. ej. tras una descarga del warehouse; la
    version ya las invalida, esto solo libera memoria)."""
    for f in _TODAS:
        f.cache_clear()
