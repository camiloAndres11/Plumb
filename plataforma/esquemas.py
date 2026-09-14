"""El perfil de la empresa, validado: exactamente las claves de
pliego/filtro/fixtures/perfil_constructora.json, porque es lo que consumen
filtro/logica.py, checklist y generador.

El wizard llena el perfil en tres pasos y cada paso valida solo su parte
(PasoSede, PasoCapacidad, PasoExperiencia); `PerfilEmpresa` valida el todo y
`perfil_completo()` dice si los tres pasos ya estan.
"""
from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel, Field, field_validator

from plataforma.catalogos import DEPARTAMENTOS
from pliego.comun.mapeo_croma import norm_txt

_UNSPSC = re.compile(r"^V1\.\d{8}$")


def unspsc_normalizado(v: str) -> str:
    s = (v or "").strip().upper()
    if s.isdigit() and 4 <= len(s) <= 8:
        s = "V1." + s.ljust(8, "0")
    if not _UNSPSC.match(s):
        raise ValueError(f"código UNSPSC inválido: {v!r} (forma V1.72141000)")
    return s


class Sede(BaseModel):
    ciudad: str = Field(min_length=2, max_length=80)
    departamento: str

    @field_validator("ciudad", "departamento", mode="before")
    @classmethod
    def _norm(cls, v):
        return norm_txt(v) or ""

    @field_validator("departamento")
    @classmethod
    def _depto(cls, v):
        if v not in DEPARTAMENTOS:
            raise ValueError(f"departamento desconocido: {v}")
        return v


class Rup(BaseModel):
    vigente: bool = False
    renovado: str | None = None     # yyyy-mm-dd

    @field_validator("renovado", mode="before")
    @classmethod
    def _fecha(cls, v):
        if v in (None, ""):
            return None
        date.fromisoformat(str(v)[:10])
        return str(v)[:10]


class Experiencia(BaseModel):
    objeto: str = Field(min_length=3, max_length=300)
    entidad: str = Field(min_length=2, max_length=200)
    unspsc: str
    valor_smmlv: float = Field(gt=0, le=10_000_000)
    anio: int = Field(ge=1990, le=2100)
    liquidado: bool = True

    @field_validator("unspsc")
    @classmethod
    def _u(cls, v):
        return unspsc_normalizado(v)

    @field_validator("entidad", mode="before")
    @classmethod
    def _norm(cls, v):
        return norm_txt(v) or ""


class Financiero(BaseModel):
    liquidez: float = Field(ge=0, le=1000)
    endeudamiento: float = Field(ge=0, le=1)
    cobertura_intereses: float = Field(ge=0, le=100_000)
    patrimonio: float = Field(ge=0)
    capital_trabajo: float = Field(ge=-1e15)


class Organizacional(BaseModel):
    rentabilidad_patrimonio: float = Field(ge=-1, le=10)
    rentabilidad_activo: float = Field(ge=-1, le=10)


class Cuantia(BaseModel):
    min: float = Field(ge=0)
    max: float = Field(gt=0)

    @field_validator("max")
    @classmethod
    def _orden(cls, v, info):
        if "min" in info.data and v < info.data["min"]:
            raise ValueError("la cuantía máxima debe ser mayor que la mínima")
        return v


# ----------------------------------------------------------------- pasos
class PasoSede(BaseModel):
    """Paso 1: donde esta, donde licita, que construye."""
    sede: Sede
    departamentos_interes: list[str] = Field(min_length=1, max_length=10)
    unspsc: list[str] = Field(min_length=1, max_length=40)

    @field_validator("departamentos_interes", mode="before")
    @classmethod
    def _deptos(cls, v):
        out = []
        for d in v or []:
            n = norm_txt(d)
            if n and n in DEPARTAMENTOS and n not in out:
                out.append(n)
        return out

    @field_validator("unspsc", mode="before")
    @classmethod
    def _codigos(cls, v):
        out = []
        for c in v or []:
            n = unspsc_normalizado(c)
            if n not in out:
                out.append(n)
        return out


class PasoCapacidad(BaseModel):
    """Paso 2: RUP, indicadores y con cuanto puede comprometerse."""
    rup: Rup
    financiero: Financiero
    organizacional: Organizacional
    capacidad_residual: float = Field(ge=0)
    contratos_en_ejecucion: int = Field(ge=0, le=1000)
    cuantia_objetivo: Cuantia


class PasoExperiencia(BaseModel):
    """Paso 3: contratos que acreditan experiencia."""
    experiencia: list[Experiencia] = Field(max_length=200)


class PerfilEmpresa(PasoSede, PasoCapacidad, PasoExperiencia):
    """El perfil entero, con la forma del JSON de los fixtures."""
    nombre: str
    nit: str

    def como_dict(self) -> dict:
        return self.model_dump()


PASOS = {1: PasoSede, 2: PasoCapacidad, 3: PasoExperiencia}


def perfil_completo(perfil: dict) -> bool:
    """Los tres pasos guardados y coherentes entre si."""
    try:
        PasoSede.model_validate(perfil)
        PasoCapacidad.model_validate(perfil)
        PasoExperiencia.model_validate(perfil)
    except Exception:
        return False
    return True
