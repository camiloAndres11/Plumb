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


def test_los_tokens_y_sesiones_van_hasheados():
    assert S.huella("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert S.huella("abc") != "abc" and len(S.huella(S.nuevo_token())) == 64


def test_protegido_redirige_segun_lo_que_falta():
    """El guardia ASGI de /app/*: sin sesion -> login; sin verificar ->
    /verificar; sin perfil -> wizard; sin datos -> /empresa/datos; sin pliego
    (checklist, generador) -> /pliegos; con todo, pasa y deja el hub."""
    import asyncio

    from plataforma import enfoques as E
    from pliego.comun import contexto

    async def app_final(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    def correr(estado, requiere_pliego=False, datos=True, pliego=None):
        enviados = []

        async def send(m):
            enviados.append(m)

        async def receive():
            return {"type": "http.request"}

        scope = {"type": "http", "root_path": "/app/filtro", "path": "/", "state": dict(estado)}
        token = contexto.set(1, {}, ["SANTANDER"], pliego=pliego) if estado.get("empresa") else None
        try:
            with pytest.MonkeyPatch.context() as mp:
                mp.setattr(E, "datos_listos", lambda ambito: datos)
                asyncio.run(E.Protegido(app_final, requiere_pliego)(scope, receive, send))
        finally:
            if token is not None:
                contexto.reset(token)
        inicio = enviados[0]
        loc = dict(inicio.get("headers", [])).get(b"location", b"").decode()
        return inicio["status"], loc, scope["state"].get("hub")

    verificado = {"id": 1, "email": "a@b.co", "email_verificado": True}
    empresa = {"id": 1, "perfil_completo": True}
    assert correr({})[:2] == (303, "/login?siguiente=%2Fapp%2Ffiltro%2F")
    assert correr({"usuario": {"id": 1, "email_verificado": None}})[:2] == (303, "/verificar")
    assert correr({"usuario": verificado, "empresa": {"id": 1, "perfil_completo": False}})[1].startswith("/empresa/perfil/1?error=")
    assert correr({"usuario": verificado, "empresa": empresa}, datos=False)[1].startswith("/empresa/datos?error=")
    assert correr({"usuario": verificado, "empresa": empresa}, requiere_pliego=True)[1].startswith("/pliegos?error=")
    estado, loc, hub = correr({"usuario": verificado, "empresa": empresa, "sesion": {"csrf": "t"}})
    assert estado == 200 and loc == "" and hub and hub["items"] and "Salir" in str(hub["pie"])
    assert correr({"usuario": verificado, "empresa": empresa}, requiere_pliego=True, pliego={"id": 9})[0] == 200


def test_la_cola_no_repite_trabajos_y_separa_descargas_de_pliegos(monkeypatch):
    from plataforma import trabajos as T
    monkeypatch.setattr(T, "_en_cola", set())
    import queue
    monkeypatch.setattr(T, "_colas", {"departamento": queue.Queue(), "pliego": queue.Queue()})
    assert T.encolar("SANTANDER") and not T.encolar("SANTANDER")
    assert T.encolar_pliego(7) and not T.encolar_pliego("7")
    assert T.en_cola() == ["SANTANDER", "pliego:7"]
    assert T._colas["departamento"].qsize() == 1 and T._colas["pliego"].qsize() == 1
    # retomar_pendientes y refrescar_todo encolan lo que la base diga, una vez
    monkeypatch.setattr(T.croma, "disponible", lambda: True)
    monkeypatch.setattr(T.extraccion, "disponible", lambda: True)
    monkeypatch.setattr(T.db, "todos", lambda sql, params=None: [{"departamento": "BOYACA"}, {"departamento": "SANTANDER"}])
    monkeypatch.setattr(T.pliegos, "pendientes", lambda: [7, 8])
    assert T.retomar_pendientes() == 2        # BOYACA y el pliego 8; SANTANDER y 7 ya estaban
    assert T.refrescar_todo() == 0
    assert T.en_cola() == ["BOYACA", "SANTANDER", "pliego:7", "pliego:8"]
