"""Recorrido completo de cuentas contra un Postgres real.

Se salta si no hay PLATAFORMA_TEST_DATABASE_URL (o DATABASE_URL) en el
entorno. Usa la base tal cual (esquema `pliego`), con correos y NITs
unicos por corrida, y borra lo que creo al final. Los correos salen por el
backend de consola (correo.enviados), de donde se leen los enlaces.
"""
from __future__ import annotations

import os
import re
import uuid

import pytest

from pliego.comun import entorno  # noqa: F401  (carga .env: DATABASE_URL local)

DSN = os.environ.get("PLATAFORMA_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="sin Postgres de pruebas (PLATAFORMA_TEST_DATABASE_URL)")


@pytest.fixture(scope="module")
def cliente():
    os.environ["DATABASE_URL"] = DSN
    os.environ.setdefault("SECRET_KEY", "clave-de-pruebas-" + "x" * 40)
    os.environ["SMTP_URL"] = ""
    from fastapi.testclient import TestClient

    from plataforma import config as C
    # Se muta el objeto (no se reemplaza): los modulos ya lo importaron.
    C.config.database_url, C.config.smtp_url = DSN, ""
    C.config.secret_key = os.environ["SECRET_KEY"]
    from plataforma import migrar
    migrar.migrar(DSN, salida=open(os.devnull, "w"))
    from plataforma.app import app
    with TestClient(app, base_url="http://127.0.0.1:8100", follow_redirects=False) as c:
        yield c
    from plataforma import db
    db.ejecutar("DELETE FROM pliego.empresas WHERE nit LIKE '9009%%'")
    db.ejecutar("DELETE FROM pliego.intentos")


def _correo_enlace(destinatario: str, ruta: str) -> str:
    from plataforma import correo
    for m in reversed(correo.enviados):
        if m["a"] == destinatario:
            e = re.search(r"https?://\S+" + re.escape(ruta) + r"/\S+", m["texto"])
            if e:
                return e.group(0).replace("http://127.0.0.1:8100", "")
    raise AssertionError(f"sin correo a {destinatario} con {ruta}")


def _csrf(html: str) -> str:
    m = re.search(r'name="csrf" value="([^"]+)"', html)
    assert m, "sin csrf en la pagina"
    return m.group(1)


def _nit():
    # 9009xxxxx con su digito de verificacion real
    from plataforma import seguridad
    base = "9009" + str(uuid.uuid4().int)[:5]
    return f"{base}-{seguridad.digito_verificacion(base)}", base


def test_registro_verificacion_login_equipo_y_reset(cliente):
    from plataforma import correo, db
    correo.enviados.clear()
    sufijo = uuid.uuid4().hex[:8]
    admin = f"admin-{sufijo}@ejemplo.test"
    nit_con_dv, nit = _nit()

    # registro: pantalla y envio
    assert cliente.get("/registro").status_code == 200
    r = cliente.post("/registro", data={"empresa": "Constructora Prueba", "nit": nit_con_dv, "nombre": "Ana",
                                        "email": admin, "clave": "una-clave-larga-1", "acepta": "1"})
    assert r.status_code == 303 and r.headers["location"].startswith("/verificar?enviado=")
    # sin verificar no se entra al panel
    r = cliente.post("/login", data={"email": admin, "clave": "una-clave-larga-1"})
    assert r.status_code == 303 and r.headers["location"] == "/verificar"
    assert cliente.get("/panel").status_code == 303   # redirige a /verificar
    cliente.cookies.clear()
    # el mismo NIT o email no se puede registrar dos veces, y la respuesta es la misma
    r = cliente.post("/registro", data={"empresa": "Otra", "nit": nit_con_dv, "nombre": "Bea", "email": f"otro-{sufijo}@ejemplo.test",
                                        "clave": "una-clave-larga-1", "acepta": "1"})
    assert r.status_code == 303 and r.headers["location"].startswith("/verificar?enviado="), r.text[r.text.find("lg-msg error"):r.text.find("lg-msg error") + 160]
    assert db.uno("SELECT count(*) AS n FROM pliego.empresas WHERE nit = %s", [nit])["n"] == 1

    # verificacion por el enlace del correo -> sesion y wizard
    r = cliente.get(_correo_enlace(admin, "/verificar"))
    assert r.status_code == 303 and r.headers["location"].startswith("/empresa/perfil/1")
    assert "pliego_sesion" in cliente.cookies
    # el enlace no sirve dos veces
    cookies = dict(cliente.cookies)
    cliente.cookies.clear()
    r = cliente.get(_correo_enlace(admin, "/verificar"))
    assert r.headers["location"].startswith("/login?error=")
    cliente.cookies.update(cookies)

    # panel y equipo
    r = cliente.get("/panel")
    assert r.status_code == 200 and "Constructora Prueba" in r.text
    html = cliente.get("/empresa/equipo").text
    assert "Ana (usted)" in html and "Invitar a alguien" in html
    csrf = _csrf(html)
    # sin csrf: 403
    assert cliente.post("/invitar", data={"email": "x@ejemplo.test", "rol": "miembro"}).status_code == 403
    miembro = f"miembro-{sufijo}@ejemplo.test"
    r = cliente.post("/invitar", data={"email": miembro, "rol": "miembro", "csrf": csrf})
    assert r.status_code == 303 and "ok=" in r.headers["location"]
    assert "Invitaciones pendientes" in cliente.get("/empresa/equipo").text

    # el invitado acepta en otro navegador
    cookies_admin = dict(cliente.cookies)
    cliente.cookies.clear()
    enlace = _correo_enlace(miembro, "/invitacion")
    assert cliente.get(enlace).status_code == 200
    r = cliente.post(enlace, data={"nombre": "Beto", "clave": "otra-clave-larga-2", "acepta": "1"})
    assert r.status_code == 303 and r.headers["location"].startswith("/panel")
    html = cliente.get("/empresa/equipo").text
    assert "Beto (usted)" in html and "Invitar a alguien" not in html   # miembro: no invita
    assert cliente.post("/invitar", data={"email": "z@ejemplo.test", "rol": "miembro", "csrf": _csrf(html)}).status_code == 403

    # el admin no puede degradarse si es el unico admin; si puede ascender al miembro
    cliente.cookies.clear()
    cliente.cookies.update(cookies_admin)
    html = cliente.get("/empresa/equipo").text
    csrf = _csrf(html)
    uid_admin = db.uno("SELECT id FROM pliego.usuarios WHERE email = %s", [admin])["id"]
    uid_miembro = db.uno("SELECT id FROM pliego.usuarios WHERE email = %s", [miembro])["id"]
    r = cliente.post("/empresa/equipo/rol", data={"usuario_id": uid_admin, "rol": "miembro", "csrf": csrf})
    assert "error=" in r.headers["location"]
    r = cliente.post("/empresa/equipo/rol", data={"usuario_id": uid_miembro, "rol": "admin", "csrf": csrf})
    assert "ok=" in r.headers["location"]

    # cuenta: cambiar contrasena cierra las otras sesiones
    r = cliente.post("/cuenta/contrasena", data={"actual": "una-clave-larga-1", "nueva": "clave-nueva-larga-3",
                                                 "nueva2": "clave-nueva-larga-3", "csrf": csrf})
    assert "ok=" in r.headers["location"]
    assert cliente.get("/cuenta").status_code == 200

    # logout
    r = cliente.post("/logout", data={"csrf": csrf})
    assert r.status_code == 303 and cliente.get("/panel").status_code == 303

    # reset por correo
    r = cliente.post("/olvide", data={"email": admin})
    assert r.status_code == 303
    enlace = _correo_enlace(admin, "/restablecer")
    r = cliente.post(enlace, data={"clave": "clave-final-larga-4", "clave2": "clave-final-larga-4"})
    assert r.headers["location"].startswith("/login?ok=")
    r = cliente.post("/login", data={"email": admin, "clave": "clave-final-larga-4"})
    assert r.status_code == 303 and r.headers["location"] == "/panel"
    # "olvide" con un correo inexistente responde igual
    r = cliente.post("/olvide", data={"email": f"nadie-{sufijo}@ejemplo.test"})
    assert r.status_code == 303 and "ok=" in r.headers["location"]


def test_login_se_frena_por_fuerza_bruta(cliente):
    from plataforma import db
    db.ejecutar("DELETE FROM pliego.intentos")
    email = f"nadie-{uuid.uuid4().hex[:6]}@ejemplo.test"
    ultimo = ""
    for _ in range(6):
        r = cliente.post("/login", data={"email": email, "clave": "cualquier-cosa-larga"})
        ultimo = r.text
    assert "Demasiados intentos" in ultimo
    db.ejecutar("DELETE FROM pliego.intentos")


def test_siguiente_solo_acepta_rutas_internas(cliente):
    cliente.cookies.clear()
    r = cliente.get("/panel")
    assert r.status_code == 303 and r.headers["location"].startswith("/login?siguiente=%2Fpanel")
    from fastapi import Request

    from plataforma.routers.publico import _siguiente
    req = Request({"type": "http", "query_string": b"", "headers": []})
    assert _siguiente(req, "https://malo.example/x") == "/panel"
    assert _siguiente(req, "//malo.example") == "/panel"
    assert _siguiente(req, "/empresa/equipo") == "/empresa/equipo"
