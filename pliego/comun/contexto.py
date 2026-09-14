"""La empresa actual, para que los enfoques sepan de quien son los datos.

Los datos.py de los enfoques nacieron con UNA constructora (el perfil
ficticio de los fixtures). La plataforma sirve a muchas: antes de despachar
una peticion fija aqui la empresa (perfil, departamentos, pliego elegido) y
los datos.py preguntan `contexto.get()`; si no hay nada fijado (la demo, las
pruebas, un script), todo sigue leyendo los fixtures como siempre.

ContextVar y no un global: cada peticion de la plataforma corre en su
propio contexto, asi que dos empresas atendidas a la vez no se mezclan.

    from pliego.comun import contexto
    token = contexto.set(empresa_id=3, perfil={...}, departamentos=["SANTANDER"])
    try:
        ...
    finally:
        contexto.reset(token)
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Empresa:
    empresa_id: int
    perfil: dict
    departamentos: tuple[str, ...] = ()
    pliego: dict | None = None          # fase 5: el pliego elegido para checklist/generador
    extra: dict = field(default_factory=dict)

    @property
    def ambito(self) -> tuple[str, ...]:
        """Lo que decide que datos ve: sus departamentos, ordenados. Dos
        empresas con los mismos departamentos comparten cache."""
        return tuple(sorted(self.departamentos))


_actual: ContextVar[Empresa | None] = ContextVar("pliego.empresa", default=None)


def get() -> Empresa | None:
    return _actual.get()


def set(empresa_id: int, perfil: dict, departamentos=(), pliego: dict | None = None, **extra):  # noqa: A001
    return _actual.set(Empresa(empresa_id, perfil, tuple(departamentos), pliego, dict(extra)))


def reset(token) -> None:
    _actual.reset(token)


def pliego() -> dict | None:
    """El pliego elegido de la empresa en contexto (checklist y generador), o None."""
    e = _actual.get()
    return e.pliego if e and e.pliego else None


def ambito() -> tuple[str, ...]:
    """() cuando no hay empresa: el ambito de los fixtures."""
    e = _actual.get()
    return e.ambito if e else ()
