"""Lo puro de seguridad.py: sin base ni red."""
from __future__ import annotations

import pytest

from plataforma import seguridad as S


def test_hash_y_verificacion():
    h = S.hashear("una-clave-larga-1")
    assert h.startswith("$argon2id$")
    assert S.verificar(h, "una-clave-larga-1") and not S.verificar(h, "otra")
    assert not S.verificar("basura", "x")


def test_politica_de_contrasena():
    assert S.validar_contrasena("corta", "a@b.co")
    assert S.validar_contrasena("a@b.co-igual", "a@b.co-igual")
    assert S.validar_contrasena("contraseña1", "a@b.co")
    assert S.validar_contrasena("una-clave-razonable", "a@b.co") is None


def test_nit_con_digito_de_verificacion():
    assert S.digito_verificacion("900195855") == 1     # ejemplo real de la doc de Croma
    assert S.nit_valido("900.195.855-1") == "900195855"
    assert S.nit_valido("900195855") == "900195855"
    assert S.nit_valido("900.195.855-7") is None       # DV equivocado
    assert S.nit_valido("abc") is None and S.nit_valido("") is None


def test_email():
    assert S.email_valido("  Ana@Empresa.CO ") == "ana@empresa.co"
    assert S.email_valido("sin-arroba") is None


def test_firma_exige_secreto(monkeypatch):
    from plataforma import config as C
    monkeypatch.setattr(C.config, "secret_key", "")
    with pytest.raises(S.SinSecreto):
        S.firmar("x")
    monkeypatch.setattr(C.config, "secret_key", "s" * 40)
    firmado = S.firmar("sesion-1")
    assert S.leer_firma(firmado, 60) == "sesion-1"
    assert S.leer_firma(firmado + "x", 60) is None
    assert S.leer_firma(None, 60) is None
