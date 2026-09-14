"""Fase 5: pliegos con extraccion simulada.

Claude se sustituye por un cliente falso que devuelve, como tool_use, la
extraccion manual del fixture SI-LP-004-2021: asi se prueba todo lo demas
(formas, poppler, guardado, contexto, checklist y generador sobre el pliego
subido) sin llave ni costo. La llamada real se prueba a mano.
"""
from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from pliego.comun import entorno  # noqa: F401  (carga .env: DATABASE_URL local)
from plataforma import carpeta as CARPETA
from plataforma import extraccion as X

RAIZ = Path(__file__).resolve().parents[2]
FIX_CHECK = RAIZ / "pliego" / "checklist" / "fixtures"
FIX_GEN = RAIZ / "pliego" / "generador" / "fixtures"
PDF = FIX_CHECK / "pliego_SI-LP-004-2021.pdf"


def _tool_input() -> dict:
    """Lo que Claude devolveria: la extraccion manual, en la forma de la tool."""
    req = json.loads((FIX_CHECK / "requisitos_SI-LP-004-2021.json").read_text(encoding="utf-8"))
    gen = json.loads((FIX_GEN / "pliego_SI-LP-004-2021.json").read_text(encoding="utf-8"))
    proc = {k: v for k, v in req["proceso"].items() if not k.startswith("_") and k not in ("pdf", "paginas")}
    for lote in proc["lotes"]:
        lote.pop("cuantia_smmlv", None)
    return {"proceso": proc, "requisitos": req["requisitos"], "campos": gen["campos"], "formatos": gen["formatos"]}


class ClienteFalso:
    def __init__(self, tool_input):
        self.tool_input = tool_input
        self.messages = SimpleNamespace(create=self._create)
        self.llamadas = []

    def _create(self, **kw):
        self.llamadas.append(kw)
        bloque = SimpleNamespace(type="tool_use", name="registrar_extraccion", input=self.tool_input)
        return SimpleNamespace(content=[bloque], usage=SimpleNamespace(input_tokens=90000, output_tokens=6000))


def test_extraer_produce_las_formas_de_los_fixtures(tmp_path):
    cliente = ClienteFalso(_tool_input())
    r = X.extraer(PDF.read_bytes(), "pliego.pdf", carpeta_paginas=tmp_path / "pags", cliente=cliente)
    kw = cliente.llamadas[0]
    assert kw["model"] == X.MODELO and kw["tool_choice"]["name"] == "registrar_extraccion"
    assert kw["messages"][0]["content"][0]["type"] == "document"
    req, gen = r["requisitos"], r["extraccion"]
    assert set(req) == {"proceso", "requisitos"} and req["proceso"]["pdf"] == "pliego.pdf"
    assert len(req["requisitos"]) == 20 and req["proceso"]["lotes"][0]["cuantia_smmlv"] == pytest.approx(812.02, abs=0.01)
    assert set(gen) >= {"id", "pdf", "paginas", "smmlv", "campos", "lotes", "formatos"}
    assert gen["campos"]["entidad"]["valor"] == "Municipio de Bucaramanga"
    assert r["costo_usd"] == pytest.approx(0.6, abs=0.01)
    if X.poppler_disponible():
        assert r["paginas"] == 66
        assert (tmp_path / "pags" / "p14.png").exists()
        assert r["citas_bbox"]["carta"]["pagina"] == 14 and r["citas_bbox"]["carta"]["cajas"]
    # la extraccion sirve tal cual a la logica del checklist y del generador
    from pliego.checklist import logica as LC
    from pliego.generador import logica as LG
    carpeta_ = json.loads((FIX_CHECK / "documentos_constructora.json").read_text(encoding="utf-8"))
    from datetime import date
    ctx = {"smmlv": req["proceso"]["smmlv"], "anticipo_pct": req["proceso"]["anticipo_pct"], "fecha_cierre": date(2021, 7, 6)}
    vs = LC.verificar_todo(req["requisitos"], carpeta_["documentos"], ctx, req["proceso"]["lotes"][0])
    assert len(vs) == 20
    perfil = json.loads((FIX_GEN / "perfil_constructora.json").read_text(encoding="utf-8"))
    gen["fecha_cierre"] = "2021-07-06"
    docs = LG.generar_todo(gen, perfil, gen["lotes"][0], date(2021, 7, 6))
    assert len(docs) >= 8


def test_a_formas_limpia_ids_repetidos_e_indicadores_sin_umbral():
    ti = {"proceso": {"id": "X-1", "entidad": "E", "objeto": "O", "modalidad": "M", "smmlv": 1_000_000, "anticipo_pct": 0,
                      "lotes": [{"nombre": "L", "presupuesto": 5e8, "plazo_meses": 3, "actividades": ["vias"], "pagina": 2}]},
          "requisitos": [{"id": "Doc A", "categoria": "juridico", "titulo": "A", "tipo": "documento", "documento": "rup", "pagina": 3, "cita": "x", "vigente": None},
                         {"id": "doc_a", "categoria": "juridico", "titulo": "B", "tipo": "documento", "documento": "rup", "pagina": 3, "cita": "y"},
                         {"id": "liq", "categoria": "financiero", "titulo": "L", "tipo": "indicador", "campo": "liquidez", "op": ">=", "pagina": 4, "cita": "z"}],
          "campos": {"anticipo_pct": {"valor": 0.2, "pagina": 9}}, "formatos": []}
    req, gen = X.a_formas(ti, "p.pdf", 10)
    ids = [r["id"] for r in req["requisitos"]]
    assert ids == ["doc_a", "doc_a_", "liq"] and "vigente" not in req["requisitos"][0]
    assert req["requisitos"][2]["tipo"] == "revisar"          # indicador sin umbral no se verifica solo
    assert req["proceso"]["lotes"][0]["n"] == 1 and req["proceso"]["lotes"][0]["cuantia_smmlv"] == 500
    assert gen["campos"]["entidad"]["valor"] == "E" and gen["campos"]["anticipo_pct"]["valor"] == 0.2
    assert gen["campos"]["proceso"]["valor"] == "X-1"


def test_carpeta_desde_el_perfil():
    perfil = json.loads((RAIZ / "pliego" / "filtro" / "fixtures" / "perfil_constructora.json").read_text(encoding="utf-8"))
    perfil["documentos"] = {"carta_presentacion": {"tiene": True, "archivo": "carta.pdf", "firmada": True},
                            "camara_comercio": {"tiene": False, "archivo": "cc.pdf"}}
    c = CARPETA.carpeta_de(perfil)
    d = c["documentos"]
    assert c["constructora"]["ciudad"] == "Bucaramanga"
    assert d["carta_presentacion"]["firmada"] and "camara_comercio" not in d
    assert d["rup"]["vigente"] and len(d["rup"]["contratos"]) == 6
    assert d["rup"]["contratos"][0]["actividades"] == ["vias"] and d["rup"]["contratos"][3]["actividades"] == ["edificaciones"]
    assert d["estados_financieros"]["liquidez"] == 1.8 and d["estados_financieros"]["activo_corriente"] == 1.9e9
    assert d["formato5_capacidad_residual"]["capacidad_residual"] == 3.8e9


DSN = os.environ.get("PLATAFORMA_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")


@pytest.mark.skipif(not DSN, reason="sin Postgres de pruebas")
def test_subir_extraer_y_usar_en_checklist_y_generador(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from plataforma import config as C
    from plataforma import db, migrar, pliegos
    from plataforma.tests.test_flujo import _correo_enlace, _csrf, _nit
    C.config.database_url, C.config.smtp_url, C.config.plataforma_datos = DSN, "", str(tmp_path)
    C.config.secret_key = C.config.secret_key or "clave-de-pruebas-" + "x" * 40
    migrar.migrar(DSN, salida=open(os.devnull, "w"))
    from plataforma.app import app
    from pliego.comun import warehouse
    with TestClient(app, base_url="http://127.0.0.1:8100", follow_redirects=False) as c:
        sufijo = uuid.uuid4().hex[:8]
        admin = f"pli-{sufijo}@ejemplo.test"
        nit_con_dv, nit = _nit()
        c.post("/registro", data={"empresa": "Pliegos Prueba", "nit": nit_con_dv, "nombre": "Ana", "email": admin,
                                  "clave": "una-clave-larga-1", "acepta": "1"})
        c.get(_correo_enlace(admin, "/verificar"))
        perfil = json.loads((RAIZ / "pliego" / "filtro" / "fixtures" / "perfil_constructora.json").read_text(encoding="utf-8"))
        perfil["departamentos_interes"] = ["VICHADA"]
        db.ejecutar("UPDATE pliego.empresas SET perfil = %s, departamentos = %s, perfil_completo = TRUE WHERE nit = %s",
                    [json.dumps(perfil), ["VICHADA"], nit])
        from plataforma.tests.test_datos import _lote
        warehouse.upsert("VICHADA", *_lote(1, 4))
        # sin pliego: el checklist redirige a /pliegos y el panel lo marca "Proximamente"
        r = c.get("/app/checklist/")
        assert r.status_code == 303 and r.headers["location"].startswith("/pliegos")
        assert "Próximamente" in c.get("/panel").text
        html = c.get("/pliegos").text
        assert "Todavía no hay pliegos" in html
        csrf = _csrf(html)
        # subir: no PDF -> error; PDF -> fila `subido` (sin llave no se extrae)
        r = c.post("/pliegos", data={"csrf": csrf}, files={"archivo": ("x.pdf", b"hola", "application/pdf")})
        assert "error=" in r.headers["location"]
        r = c.post("/pliegos", data={"csrf": csrf}, files={"archivo": ("pliego.pdf", PDF.read_bytes(), "application/pdf")})
        assert "ok=" in r.headers["location"]
        fila = db.uno("SELECT * FROM pliego.pliegos WHERE nombre = 'pliego.pdf' ORDER BY id DESC LIMIT 1")
        assert fila["estado"] == "subido" and (tmp_path / fila["ruta_pdf"]).exists()
        # repetido: misma respuesta, sin fila nueva
        r = c.post("/pliegos", data={"csrf": csrf}, files={"archivo": ("otro.pdf", PDF.read_bytes(), "application/pdf")})
        assert "ya%20estaba" in r.headers["location"]
        # extraer con el cliente falso (lo que haria el hilo de trabajos)
        pliegos.extraer(fila["id"], cliente=ClienteFalso(_tool_input()))
        fila = db.uno("SELECT * FROM pliego.pliegos WHERE id = %s", [fila["id"]])
        assert fila["estado"] == "listo" and len(fila["requisitos"]["requisitos"]) == 20 and fila["paginas"] in (66, 0)
        # ahora checklist y generador sirven sobre el pliego de la empresa
        html = c.get("/pliegos").text
        assert "SI-LP-004-2021" in html and "Usar" in html
        r = c.post(f"/pliegos/{fila['id']}/usar", data={"csrf": csrf})
        assert r.headers["location"] == "/app/checklist/"
        r = c.get("/app/checklist/")
        assert r.status_code == 200 and "SI-LP-004-2021" in r.text and 'href="/panel"' in r.text
        assert "Constructora Andina" in r.text or "Pliegos Prueba" in r.text
        r = c.get("/app/checklist/requisito/carta?lote=1")
        assert r.status_code == 200
        if X.poppler_disponible():
            assert c.get("/app/checklist/paginas/p14.png").status_code == 200
        assert c.get("/app/checklist/pliego.pdf").status_code == 200
        r = c.get("/app/generador/")
        assert r.status_code in (200, 307)
        if r.status_code == 307:
            r = c.get(r.headers["location"])
        assert r.status_code == 200 and "SI-LP-004-2021" in r.text
        assert "Próximamente" not in c.get("/panel").text
        # documentos de la empresa: marcar la carta cambia el checklist
        html = c.get("/empresa/documentos").text
        assert "Carta de presentación" in html
        r = c.post("/empresa/documentos", data={"csrf": csrf, "carta_presentacion__tiene": "1", "carta_presentacion__archivo": "carta.pdf",
                                                "carta_presentacion__firmada": "1", "p__representante_legal.nombre": "Ana Ruiz"})
        assert "ok=" in r.headers["location"]
        emp = db.uno("SELECT perfil FROM pliego.empresas WHERE nit = %s", [nit])
        assert emp["perfil"]["documentos"]["carta_presentacion"]["firmada"] and emp["perfil"]["representante_legal"]["nombre"] == "Ana Ruiz"
        # borrar
        r = c.post(f"/pliegos/{fila['id']}/borrar", data={"csrf": csrf})
        assert "ok=" in r.headers["location"] and not (tmp_path / fila["ruta_pdf"]).exists()
        db.ejecutar("DELETE FROM pliego.empresas WHERE nit = %s", [nit])
    shutil.rmtree(tmp_path / "pliegos", ignore_errors=True)


def test_extraer_rechaza_por_paginas_antes_de_llamar_a_claude(tmp_path):
    """El tope de paginas se aplica ANTES de la llamada: un PDF enorme no
    gasta ni un token."""
    if not shutil.which("pdfinfo"):
        pytest.skip("sin poppler no se cuentan paginas")
    cliente = ClienteFalso(_tool_input())
    with pytest.raises(X.DemasiadasPaginas):
        X.extraer(PDF.read_bytes(), PDF.name, cliente=cliente, max_paginas=10)
    assert cliente.llamadas == []
    # Con tope holgado si llama.
    X.extraer(PDF.read_bytes(), PDF.name, cliente=cliente, max_paginas=500)
    assert len(cliente.llamadas) == 1


def test_el_cliente_de_anthropic_se_puede_construir(monkeypatch):
    """La dependencia esta en plataforma/requirements.txt: sin ella, en el
    contenedor la extraccion moria con ImportError al poner la llave."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-prueba")
    assert X._cliente() is not None
