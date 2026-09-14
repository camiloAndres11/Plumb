"""PerfilEmpresa: la misma forma que el JSON de los fixtures."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from plataforma import esquemas as E

FIXTURE = Path(__file__).resolve().parents[2] / "pliego" / "filtro" / "fixtures" / "perfil_constructora.json"


def test_el_perfil_ficticio_valida_entero():
    perfil = json.loads(FIXTURE.read_text(encoding="utf-8"))
    p = E.PerfilEmpresa.model_validate(perfil)
    assert E.perfil_completo(perfil)
    assert set(p.como_dict()) == set(perfil) - {"_nota"}


def test_paso_sede_normaliza_y_deduplica():
    p = E.PasoSede.model_validate({"sede": {"ciudad": "Bucaramanga", "departamento": "Santander"},
                                   "departamentos_interes": ["Boyacá", "boyaca", "SANTANDER"],
                                   "unspsc": ["721410", "V1.72141000", "72151100"]})
    assert p.sede.departamento == "SANTANDER" and p.sede.ciudad == "BUCARAMANGA"
    assert p.departamentos_interes == ["BOYACA", "SANTANDER"]
    assert p.unspsc == ["V1.72141000", "V1.72151100"]


def test_departamento_desconocido_y_unspsc_malo_fallan():
    with pytest.raises(ValidationError):
        E.PasoSede.model_validate({"sede": {"ciudad": "X", "departamento": "MARTE"}, "departamentos_interes": ["SANTANDER"], "unspsc": ["V1.72141000"]})
    with pytest.raises(ValidationError):
        E.PasoSede.model_validate({"sede": {"ciudad": "Xy", "departamento": "SANTANDER"}, "departamentos_interes": ["SANTANDER"], "unspsc": ["abc"]})


def test_cuantia_y_experiencia():
    with pytest.raises(ValidationError):
        E.Cuantia.model_validate({"min": 10, "max": 5})
    e = E.Experiencia.model_validate({"objeto": "Pavimento", "entidad": "Alcaldía de Girón", "unspsc": "72141000",
                                      "valor_smmlv": "1240", "anio": "2024", "liquidado": True})
    assert e.entidad == "ALCALDIA DE GIRON" and e.unspsc == "V1.72141000" and e.valor_smmlv == 1240


def test_perfil_incompleto_no_es_completo():
    assert not E.perfil_completo({"sede": {"ciudad": "Xy", "departamento": "SANTANDER"}})
