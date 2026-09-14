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


class _Peticion:
    def __init__(self, socket="9.9.9.9", xff=None):
        self.client = type("C", (), {"host": socket})()
        self.headers = {"x-forwarded-for": xff} if xff else {}


def test_ip_cliente_ignora_la_cabecera_sin_proxies_de_confianza():
    # Lo que el cliente ponga en X-Forwarded-For no cuenta: vale el socket
    # (que uvicorn ya corrigio con su propia lista de proxies privados).
    assert S.ip_cliente(_Peticion("9.9.9.9", "1.2.3.4"), proxies=0) == "9.9.9.9"


def test_ip_cliente_toma_el_salto_del_proxy_no_el_del_cliente():
    # Con un proxy de confianza, la IP real es el ULTIMO salto (lo que el
    # proxy anadio), no el primero (lo que el cliente mando).
    assert S.ip_cliente(_Peticion("10.0.0.5", "1.2.3.4, 200.1.1.1"), proxies=1) == "200.1.1.1"
    assert S.ip_cliente(_Peticion("10.0.0.5", "1.2.3.4, 200.1.1.1, 10.0.0.9"), proxies=2) == "200.1.1.1"
    # Cabecera corta o ausente: socket.
    assert S.ip_cliente(_Peticion("10.0.0.5", None), proxies=1) == "10.0.0.5"
    assert S.ip_cliente(_Peticion("10.0.0.5", "200.1.1.1"), proxies=2) == "10.0.0.5"


def test_el_log_de_acceso_no_lleva_tokens():
    from plataforma.app import ruta_para_log
    assert ruta_para_log("/restablecer/AbC-123_xyz") == "/restablecer/<token>"
    assert ruta_para_log("/verificar/t0k3n") == "/verificar/<token>"
    assert ruta_para_log("/invitacion/t0k3n") == "/invitacion/<token>"
    assert ruta_para_log("/verificar") == "/verificar"
    assert ruta_para_log("/verificar/reenviar") == "/verificar/<token>"   # ruta fija, pero mejor de mas que de menos
    assert ruta_para_log("/pliegos/12/usar") == "/pliegos/12/usar"


def test_cabeceras_de_seguridad_y_cookie_de_login():
    from fastapi.testclient import TestClient

    from plataforma.app import app
    with TestClient(app, follow_redirects=False) as c:
        r = c.get("/terminos")
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
        assert r.headers["x-frame-options"] == "DENY" and r.headers["x-content-type-options"] == "nosniff"
        r = c.get("/login")
        assert "pliego_login" in r.cookies and 'name="csrf"' in r.text
        # Un POST sin el token de doble envio no pasa (login CSRF).
        c.cookies.clear()
        r = c.post("/login", data={"email": "a@b.co", "clave": "x" * 12})
        assert r.status_code == 403


def test_los_correos_escapan_lo_que_escribe_el_usuario(monkeypatch):
    from plataforma import correo
    correo.enviados.clear()
    correo.invitacion("x@ejemplo.test", 'Constructora <a href="https://phishing">Verificar</a>', "Ana\r\nBcc: otro", "https://pliego.test/invitacion/t")
    m = correo.enviados[-1]
    assert "<a href=\"https://phishing\">" not in m["html"] and "&lt;a href=" in m["html"]
    assert "\r" not in m["asunto"] and "\n" not in m["asunto"]
    correo.enviados.clear()


def test_solo_config_lee_el_entorno():
    """Un solo punto de configuracion: ningun modulo de pliego/, plataforma/
    o demo/ lee os.environ salvo pliego/comun/config.py (y las pruebas)."""
    import re
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[2]
    culpables = []
    for paquete in ("pliego", "plataforma", "demo"):
        for f in (raiz / paquete).rglob("*.py"):
            if "tests" in f.parts or f.name == "config.py":
                continue
            if re.search(r"os\.(environ|getenv)\b", f.read_text(encoding="utf-8")):
                culpables.append(str(f.relative_to(raiz)))
    assert culpables == [], culpables
