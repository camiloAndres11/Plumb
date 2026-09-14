"""Fase 3: warehouse en disco, descarga por departamento y aislamiento.

El warehouse va a un archivo temporal (PLIEGO_WAREHOUSE) y Croma es la
sesion falsa de pliego/tests/test_croma.py. Lo que toca Postgres
(descargar_departamento anota el estado) se salta sin base.
"""
from __future__ import annotations

import os
from datetime import date

import pytest

from pliego.comun import cache, contexto
from pliego.comun import fuente as F
from pliego.tests import test_croma as T


@pytest.fixture
def wh(tmp_path, monkeypatch):
    from pliego.comun import warehouse as W
    W.cerrar()
    monkeypatch.setenv("PLIEGO_WAREHOUSE", str(tmp_path / "wh.duckdb"))
    monkeypatch.setenv("PLIEGO_FUENTE", "warehouse")
    monkeypatch.setattr(F, "CACHE", tmp_path / "cache")
    yield W
    W.cerrar()


def _lote(n_desde=1, n_hasta=7, nit="890201222", doc="900123456"):
    hoy = date.today()
    adjudicados = [T._adjudicado(i, nit=nit, oferentes=(1 if i % 2 else 4)) for i in range(n_desde, n_hasta)]
    contratos = [T._contrato(i, nit=nit, doc=doc) for i in range(n_desde, n_hasta)]
    abiertos = [T._abierto(100 + n_desde, bid_deadline=hoy.replace(day=28).isoformat()),
                T._abierto(101 + n_desde, invited_providers=8, interested_providers=0, bid_deadline=hoy.isoformat())]
    return contratos, adjudicados, abiertos


def test_dos_empresas_ven_solo_sus_departamentos(wh):
    c1, a1, o1 = _lote(1, 7)
    c2, a2, o2 = _lote(20, 23, nit="800000001", doc="900777777")
    wh.upsert("SANTANDER", c1, a1, o1, as_of="2026-09-14T05:00:00Z")
    wh.upsert("BOYACA", c2, a2, o2, as_of="2026-09-14T06:00:00Z")
    from pliego.filtro import datos as DF
    from pliego.radar import datos as DR
    t = contexto.set(1, {}, ["SANTANDER"])
    try:
        assert F.activa() == "warehouse"
        assert len(DR.contratos()) == 6 and len(DF.procesos()) == 2
        assert F.estado()["n_base"] == 6 and F.estado()["as_of"] == "2026-09-14T05:00:00Z"
    finally:
        contexto.reset(t)
    t = contexto.set(2, {}, ["BOYACA"])
    try:
        assert len(DR.contratos()) == 3 and {c["doc_proveedor"] for c in DR.contratos()} == {"900777777"}
    finally:
        contexto.reset(t)
    t = contexto.set(3, {}, ["BOYACA", "SANTANDER"])
    try:
        assert len(DR.contratos()) == 9
    finally:
        contexto.reset(t)
    # sin contexto, modo warehouse cae a fixtures y ve el snapshot
    assert F.activa() == "fixtures" and len(DF.procesos()) == 565


def test_la_cache_se_invalida_al_escribir(wh):
    from pliego.radar import datos as DR
    c, a, o = _lote(1, 4)
    wh.upsert("SANTANDER", c, a, o)
    t = contexto.set(1, {}, ["SANTANDER"])
    try:
        assert len(DR.contratos()) == 3
        wh.upsert("SANTANDER", *_lote(1, 6))
        assert len(DR.contratos()) == 5      # version nueva, cache nueva
        cache.limpiar_todo()
        assert len(DR.contratos()) == 5
    finally:
        contexto.reset(t)


def test_las_evaluaciones_dependen_de_la_empresa_no_solo_del_ambito(wh):
    import json
    from pliego.filtro import datos as DF
    wh.upsert("SANTANDER", *_lote(1, 7))
    base = json.load(open("pliego/filtro/fixtures/perfil_constructora.json"))
    t = contexto.set(1, {**base, "capacidad_residual": 1e12}, ["SANTANDER"])
    try:
        e1 = [x["evaluacion"]["recomendacion"] for x in DF.evaluaciones()]
    finally:
        contexto.reset(t)
    t = contexto.set(2, {**base, "capacidad_residual": 1}, ["SANTANDER"])
    try:
        e2 = [x["evaluacion"]["recomendacion"] for x in DF.evaluaciones()]
    finally:
        contexto.reset(t)
    assert e1 != e2 and "no_presentarse" in e2


def test_alertas_usan_la_fecha_de_hoy(wh):
    c, a, o = _lote(1, 4)
    wh.upsert("SANTANDER", c, a, o)
    filas = wh.consultar("SELECT id_del_proceso, universo, dias_restantes FROM alertas ORDER BY 1", ("SANTANDER",))
    assert all(f["universo"] == "accionable" and f["dias_restantes"] >= 0 for f in filas)


DSN = os.environ.get("PLATAFORMA_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")


@pytest.mark.skipif(not DSN, reason="sin Postgres de pruebas")
def test_descargar_departamento_escribe_warehouse_y_estado(wh, monkeypatch):
    from plataforma import db, migrar, trabajos
    from plataforma import config as C
    C.config.database_url = DSN
    migrar.migrar(DSN, salida=open(os.devnull, "w"))
    db.ejecutar("DELETE FROM pliego.descargas_departamento WHERE departamento = 'VAUPES'")
    monkeypatch.setenv("CROMA_HILOS", "1")   # la sesion falsa responde en orden
    c, a, o = _lote(1, 5)
    respuestas = []
    for _ in range(3):   # 3 tipos x (contratos, adjudicados, abiertos)
        respuestas += [T.Resp(200, T.pagina(c, as_of="2026-09-14T05:00:00Z"), {"X-RateLimit-Remaining": "4000"}),
                       T.Resp(200, T.pagina(a)), T.Resp(200, T.pagina(o))]
    api, ses = T.cliente(*respuestas)
    r = trabajos.descargar_departamento("VAUPES", api=api)
    assert r["n_base"] == 4 and len(ses.llamadas) == 9
    fila = db.uno("SELECT * FROM pliego.descargas_departamento WHERE departamento = 'VAUPES'")
    assert fila["estado"] == "lista" and fila["paginas"] == 9 and fila["ultima_ok"] is not None
    assert fila["as_of"].isoformat().startswith("2026-09-14")
    # segunda vez: incremental (from_date reciente) y con error -> queda en error
    api2, ses2 = T.cliente(T.Resp(402, {"error": {"code": "billing_error"}}, {"X-RateLimit-Reset": "x"}))
    with pytest.raises(Exception):
        trabajos.descargar_departamento("VAUPES", api=api2)
    fila = db.uno("SELECT * FROM pliego.descargas_departamento WHERE departamento = 'VAUPES'")
    assert fila["estado"] == "error" and "402" in fila["error"]
    assert ses2.llamadas[0][1]["from_date"] >= (date.today().replace(day=1)).isoformat()[:4]
    db.ejecutar("DELETE FROM pliego.descargas_departamento WHERE departamento = 'VAUPES'")


@pytest.mark.skipif(not DSN, reason="sin Postgres de pruebas")
def test_los_enfoques_bajo_app_exigen_sesion_perfil_y_datos(wh, monkeypatch):
    """Fase 4: /app/filtro redirige segun lo que falte y, con todo, sirve la
    lista del filtro con la sidebar de la plataforma y los datos de la empresa."""
    import uuid
    from fastapi.testclient import TestClient

    from plataforma import config as C
    from plataforma import db, migrar
    C.config.database_url, C.config.smtp_url = DSN, ""
    C.config.secret_key = C.config.secret_key or "clave-de-pruebas-" + "x" * 40
    migrar.migrar(DSN, salida=open(os.devnull, "w"))
    from plataforma.app import app
    from plataforma.tests.test_flujo import _correo_enlace, _nit
    with TestClient(app, base_url="http://127.0.0.1:8100", follow_redirects=False) as c:
        # sin sesion
        r = c.get("/app/filtro/")
        assert r.status_code == 303 and r.headers["location"].startswith("/login?siguiente=%2Fapp%2Ffiltro")
        # con sesion pero sin perfil
        sufijo = uuid.uuid4().hex[:8]
        admin = f"enf-{sufijo}@ejemplo.test"
        nit_con_dv, nit = _nit()
        c.post("/registro", data={"empresa": "Enfoques Prueba", "nit": nit_con_dv, "nombre": "Ana", "email": admin,
                                  "clave": "una-clave-larga-1", "acepta": "1"})
        c.get(_correo_enlace(admin, "/verificar"))
        r = c.get("/app/filtro/")
        assert r.status_code == 303 and r.headers["location"].startswith("/empresa/perfil/1")
        # perfil completo (directo en la base) pero sin datos
        import json
        perfil = json.load(open("pliego/filtro/fixtures/perfil_constructora.json"))
        perfil["departamentos_interes"] = ["VICHADA"]
        db.ejecutar("UPDATE pliego.empresas SET perfil = %s, departamentos = %s, perfil_completo = TRUE WHERE nit = %s",
                    [json.dumps(perfil), ["VICHADA"], nit])
        r = c.get("/app/filtro/")
        assert r.status_code == 303 and r.headers["location"].startswith("/empresa/datos")
        assert "Lo que falta" in c.get("/panel").text
        # con datos del departamento
        wh.upsert("VICHADA", *_lote(1, 7), as_of="2026-09-14T05:00:00Z")
        r = c.get("/app/filtro/")
        assert r.status_code == 200
        assert 'href="/panel"' in r.text and "Enfoques Prueba" in r.text          # sidebar de la plataforma
        assert 'href="/app/filtro/static/base.css"' in r.text                    # prefijo reescrito
        assert "datos al 2026-09-14" in r.text
        html = c.get("/panel").text
        assert "pn-card" in html and "Próximamente" in html and 'href="/app/filtro/"' in html
        assert c.get("/app/radar/").status_code == 200
        r = c.get("/app/simulador/")            # el simulador redirige al primer proceso, con prefijo
        assert r.status_code == 307 and r.headers["location"].startswith("/app/simulador/proceso/")
        assert c.get(r.headers["location"]).status_code == 200
        db.ejecutar("DELETE FROM pliego.empresas WHERE nit = %s", [nit])
        db.ejecutar("DELETE FROM pliego.descargas_departamento WHERE departamento = 'VICHADA'")
