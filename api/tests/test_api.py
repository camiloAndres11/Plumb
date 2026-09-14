"""Pruebas del API que NO necesitan Postgres.

La capa de consulta (`app.consultas`) se sustituye por dobles, asi que
esto verifica lo que es responsabilidad del API y no de los datos: que
las rutas existan, que el sobre de respuesta sea el mismo en todas, que
los parametros fuera de la lista blanca se rechacen ANTES de llegar al
SQL, y que el CSV salga bien.

Las puertas sobre los datos viven en tests/test_calidad.py (Python 3.9,
contra el warehouse DuckDB). Son dos suites porque son dos entornos: el
pipeline esta fijado a 3.9 y el SDK de MCP exige >=3.10.

    python -m pytest api/tests/ -v      # deps: pip install -e ".[legacy,dev]"
"""
from __future__ import annotations

import datetime

import pytest
from app import consultas  # api/ esta en pythonpath (pyproject.toml)
from app.main import app
from fastapi.testclient import TestClient

GLOSARIO = [
    {"bandera": "f_proponente_unico", "peso": 2.0, "grupo": "Competencia", "capa": "contrato",
     "glosa": "Un solo oferente en el proceso", "evidencia": None},
    {"bandera": "f_fraccionamiento", "peso": 3.0, "grupo": "Umbrales", "capa": "contrato",
     "glosa": "Contratos hermanos en 30 dias", "evidencia": "ev_hermanos_30d"},
]

CONTRATO = {
    "id_contrato": "CO1.BDOS.1",
    "entidad": "MUNICIPIO DE PIEDECUESTA",
    "nit_entidad": "890205565",
    "departamento": "SANTANDER",
    "ciudad": "PIEDECUESTA",
    "tipo_contrato": "OBRA",
    "modalidad": "CONTRATACION DIRECTA",
    "tipo_obra": "VIAS Y TRANSPORTE",
    "anio": 2023,
    "fecha_firma": datetime.date(2023, 12, 20),
    "proveedor": "CONSORCIO EJEMPLO",
    "doc_proveedor": "900123456",
    "valor": 1_500_000_000.0,
    "valor_plausible": 1_500_000_000.0,
    "es_atipico": True,
    "puntos_crudos": 8,
    "n_banderas_fuertes": 1,
    "puntos_red": 3,
    "n_banderas_red_fuertes": 1,
    "score": 0.21,
    "banderas": ["f_proponente_unico", "f_fraccionamiento"],
    "urlproceso": "https://community.secop.gov.co/Public/Tendering/x",
}


@pytest.fixture()
def cliente(monkeypatch):
    """TestClient con la capa de datos sustituida. No se abre el lifespan
    (no hay Postgres ni servidor MCP que arrancar en una prueba unitaria)."""
    monkeypatch.setattr(consultas, "glosario", lambda: GLOSARIO)
    monkeypatch.setattr(consultas, "nombres_banderas", lambda: {g["bandera"] for g in GLOSARIO})
    return TestClient(app)


# ---------------------------------------------------------------------
# El sobre y el aviso
# ---------------------------------------------------------------------
def test_toda_respuesta_lleva_el_aviso_de_riesgo_no_es_fraude(cliente):
    """El aviso es la afirmacion central del proyecto. Una respuesta sin el
    invita exactamente a la lectura que el proyecto niega, asi que va en
    el sobre de TODAS, no en la documentacion."""
    r = cliente.get("/v1/banderas")
    assert r.status_code == 200
    assert "no es fraude" in r.json()["meta"]["aviso"].lower()


def test_el_sobre_trae_paginacion_y_datos(cliente):
    cuerpo = cliente.get("/v1/banderas").json()
    assert set(cuerpo) == {"datos", "meta"}
    assert cuerpo["meta"]["paginacion"]["total"] == len(GLOSARIO)
    assert cuerpo["datos"][0]["bandera"] == "f_proponente_unico"


def test_health_responde_sin_base_de_datos(cliente):
    """El health check del hosting no puede depender de que Postgres este
    cargado: un servicio recien desplegado todavia no lo esta."""
    assert cliente.get("/health").json()["ok"] is True


def test_el_indice_lista_los_endpoints(cliente):
    cuerpo = cliente.get("/v1").json()
    assert "GET /v1/contratos/{id_contrato}" in cuerpo["endpoints"]
    assert cuerpo["openapi"] == "/openapi.json"


def test_el_openapi_se_genera(cliente):
    """Si un response_model no casa con lo que devuelve un router, esto
    revienta aqui y no en produccion."""
    esquema = cliente.get("/openapi.json").json()
    assert "/v1/contratos/{id_contrato}" in esquema["paths"]
    assert "/chat" in esquema["paths"]


# ---------------------------------------------------------------------
# Listas blancas: lo que no esta en ellas no llega al SQL
# ---------------------------------------------------------------------
def test_un_orden_inventado_da_400_y_no_toca_la_base(cliente, monkeypatch):
    def explotar(*a, **k):
        raise AssertionError("la consulta no deberia haberse ejecutado")

    monkeypatch.setattr(consultas, "consultar", explotar, raising=False)
    r = cliente.get("/v1/contratos", params={"orden": "valor; DROP TABLE api_contratos"})
    assert r.status_code == 400
    cuerpo = r.json()
    assert cuerpo["error"]["codigo"] == "parametro_invalido"
    assert "no permitido" in cuerpo["error"]["mensaje"]


def test_una_bandera_inventada_da_400(cliente):
    r = cliente.get("/v1/contratos", params={"bandera": "f_lo_que_sea OR 1=1"})
    assert r.status_code == 400
    assert "glosario" in r.json()["error"]["mensaje"]


def test_un_universo_de_alerta_inventado_da_400(cliente, monkeypatch):
    monkeypatch.setattr(consultas, "hay_alertas", lambda: True)
    r = cliente.get("/v1/alertas", params={"universo": "el-que-yo-quiera"})
    assert r.status_code == 400


def test_el_limite_tiene_techo(cliente):
    """Sin techo, un cliente pide limite=100000 y se lleva la tabla entera."""
    r = cliente.get("/v1/contratos", params={"limite": 9999})
    assert r.status_code == 422
    assert r.json()["error"]["codigo"] == "parametro_invalido"


# ---------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------
def test_un_contrato_inexistente_da_404_con_el_formato_de_error(cliente, monkeypatch):
    monkeypatch.setattr(consultas, "contrato", lambda _id: None)
    r = cliente.get("/v1/contratos/NO-EXISTE")
    assert r.status_code == 404
    assert r.json()["error"]["codigo"] == "no_encontrado"


def test_sin_base_cargada_responde_503_con_el_comando_que_falta(cliente, monkeypatch):
    from app.db import DatosNoDisponibles

    def caer():
        raise DatosNoDisponibles("corre 'python pipeline/load_postgres.py'")

    monkeypatch.setattr(consultas, "titulares", caer)
    r = cliente.get("/v1/titulares")
    assert r.status_code == 503
    assert r.json()["error"]["codigo"] == "datos_no_disponibles"
    assert "load_postgres" in r.json()["error"]["mensaje"]


def test_las_alertas_degradan_a_503_si_nadie_corrio_el_snapshot(cliente, monkeypatch):
    monkeypatch.setattr(consultas, "hay_alertas", lambda: False)
    r = cliente.get("/v1/alertas")
    assert r.status_code == 503
    assert "ingest_abiertos" in r.json()["error"]["mensaje"]


# ---------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------
def test_el_csv_sale_con_cabecera_bom_y_descarga(cliente, monkeypatch):
    monkeypatch.setattr(consultas, "buscar_contratos", lambda **k: ([CONTRATO], 1))
    r = cliente.get("/v1/contratos", params={"formato": "csv", "limite": 1})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    texto = r.content.decode("utf-8")
    # BOM: sin el, Excel en Windows rompe las tildes de los nombres de entidad
    assert texto.startswith("﻿")
    assert "id_contrato" in texto.splitlines()[0]
    fila = texto.splitlines()[1]
    assert "CO1.BDOS.1" in fila
    assert "true" in fila                                  # booleanos legibles
    assert "2023-12-20" in fila                            # fechas ISO, no repr
    assert "f_proponente_unico|f_fraccionamiento" in fila   # listas aplanadas


def test_el_csv_lleva_el_aviso_en_una_cabecera(cliente, monkeypatch):
    """En CSV el sobre se pierde (una hoja de calculo no abre bien un
    archivo con metadatos arriba), asi que el aviso viaja en la cabecera."""
    monkeypatch.setattr(consultas, "buscar_contratos", lambda **k: ([CONTRATO], 1))
    r = cliente.get("/v1/contratos", params={"formato": "csv"})
    assert "no es fraude" in r.headers["x-plomada-aviso"].lower()


def test_un_formato_inventado_da_422(cliente):
    assert cliente.get("/v1/titulares", params={"formato": "xlsx"}).status_code == 422


# ---------------------------------------------------------------------
# Forma de los datos
# ---------------------------------------------------------------------
def test_la_ficha_de_contrato_trae_la_evidencia_de_cada_bandera(cliente, monkeypatch):
    """Sin evidencia no se publica: es la regla del proyecto y por eso este
    endpoint existe."""
    ficha = {
        "id_contrato": "CO1.BDOS.1", "urlproceso": None, "entidad": "X",
        "dinero": {"valor": 1.0}, "competencia": {}, "partes": {},
        "riesgo": {"es_atipico": True, "puntos_crudos": 8, "n_banderas_fuertes": 1},
        "banderas": [{
            "bandera": "f_fraccionamiento", "peso": 3.0, "grupo": "Umbrales",
            "capa": "contrato", "glosa": "Contratos hermanos en 30 dias",
            "evidencia": {"ev_hermanos_30d": 4},
        }],
    }
    monkeypatch.setattr(consultas, "contrato", lambda _id: ficha)
    datos = cliente.get("/v1/contratos/CO1.BDOS.1").json()["datos"]
    assert datos["banderas"][0]["evidencia"]["ev_hermanos_30d"] == 4
    assert datos["banderas"][0]["glosa"]


def test_los_municipios_llevan_siempre_las_dos_tasas(cliente, monkeypatch):
    """La comparacion cruda vs ajustada ES el argumento metodologico del
    ranking; publicar una sola lo esconde."""
    fila = {"ciudad": "X", "departamento": "Y", "n_contratos": 40, "n_atipicos": 8,
            "tasa_cruda": 0.2, "tasa_ajustada": 0.15, "valor_total": 1.0,
            "valor_atipico": 0.2}
    monkeypatch.setattr(consultas, "municipios", lambda **k: ([fila], 1))
    datos = cliente.get("/v1/municipios").json()["datos"][0]
    assert datos["tasa_cruda"] is not None and datos["tasa_ajustada"] is not None


def test_ninguna_respuesta_expone_la_cuenta_bancaria(cliente, monkeypatch):
    """Invariante del proyecto: la cuenta se usa como llave interna y no
    se publica. La contraparte de esta prueba, del lado de los datos, es
    test_el_snapshot_publico_no_lleva_cuentas en tests/test_calidad.py."""
    contaminado = dict(CONTRATO, cuenta_key="abc123", banco="BANCO X")
    monkeypatch.setattr(consultas, "buscar_contratos", lambda **k: ([contaminado], 1))
    # En JSON lo garantiza el response_model: lo que no esta en el modelo
    # no sale, aunque la consulta lo traiga.
    cuerpo = cliente.get("/v1/contratos").text
    assert "cuenta_key" not in cuerpo and "abc123" not in cuerpo
    # El CSV no pasa por el modelo, asi que tiene su propia lista negra.
    csv = cliente.get("/v1/contratos", params={"formato": "csv"}).text
    assert "cuenta_key" not in csv and "abc123" not in csv


def test_el_csv_neutraliza_las_formulas_de_excel(cliente, monkeypatch):
    """Una celda de texto que empiece por = + - @ la ejecuta Excel como
    formula al abrir el archivo (=WEBSERVICE exfiltra, DDE ejecuta). Los
    valores vienen del SECOP II -- texto escrito por terceros -- y el
    publico objetivo abre estos CSV en Excel: es el vector clasico contra
    periodistas, en el producto hecho para periodistas."""
    envenenado = dict(CONTRATO, entidad="=2+5", proveedor="@SUM(A1)")
    monkeypatch.setattr(consultas, "buscar_contratos", lambda **k: ([envenenado], 1))
    texto = cliente.get("/v1/contratos", params={"formato": "csv"}).text
    fila = texto.splitlines()[1]
    assert "'=2+5" in fila and ",=2+5" not in fila
    assert "'@SUM(A1)" in fila and ",@SUM(A1)" not in fila
    # y los numeros siguen siendo numeros: prefijar un valor numerico
    # negativo lo volveria texto en Excel
    assert "1500000000.0" in fila


# ---------------------------------------------------------------------
# Techos de /chat: BYOK cuida la plata del lector, esto cuida el servicio
# ---------------------------------------------------------------------
def test_el_chat_limita_las_peticiones_por_ip(cliente):
    from app import main
    from app.config import config

    ip = "203.0.113.7"   # rango reservado para documentacion, no colisiona
    for _ in range(config.chat_max_por_ip):
        assert main._dentro_del_limite(ip)
    assert not main._dentro_del_limite(ip)
    # otra IP no paga el techo de la primera
    assert main._dentro_del_limite("203.0.113.8")


def test_el_chat_saturado_avisa_sin_tocar_a_anthropic(cliente, monkeypatch):
    """Con el cupo de streams lleno, /chat responde un evento de error SSE
    y termina: no crea cliente de Anthropic ni gasta la key de nadie."""
    from app import main

    monkeypatch.setattr(main, "_chat_activos", main.config.chat_max_concurrentes)
    monkeypatch.setattr(
        main.anthropic, "AsyncAnthropic",
        lambda **k: (_ for _ in ()).throw(AssertionError("no debio crearse un cliente")),
    )
    r = cliente.post(
        "/chat",
        json={"mensaje": "hola"},
        headers={"X-Anthropic-Api-Key": "sk-ant-falsa"},
    )
    assert r.status_code == 200
    assert "conversaciones abiertas" in r.text


def test_el_exceso_por_ip_da_429_con_el_formato_de_error(cliente, monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_dentro_del_limite", lambda ip: False)
    r = cliente.post(
        "/chat",
        json={"mensaje": "hola"},
        headers={"X-Anthropic-Api-Key": "sk-ant-falsa"},
    )
    assert r.status_code == 429
    assert r.json()["error"]["codigo"] == "limite_alcanzado"


# ---------------------------------------------------------------------
# JSON y CSV son el MISMO contrato
# ---------------------------------------------------------------------
def test_el_csv_publica_las_mismas_columnas_que_el_json(cliente, monkeypatch):
    """El JSON lo filtra el `response_model` y el CSV la lista de columnas de
    ese mismo modelo. Si un endpoint deja de pasar el modelo, el CSV vuelve a
    sacar lo que la consulta traiga y las dos salidas divergen en silencio:
    se documenta un contrato y se sirve otro."""
    from app.esquemas import ContratoResumen

    sobrante = dict(CONTRATO, columna_que_nadie_documento=1, otra_mas="x")
    monkeypatch.setattr(consultas, "buscar_contratos", lambda **k: ([sobrante], 1))

    json_cols = set(cliente.get("/v1/contratos").json()["datos"][0])
    csv_cols = set(
        cliente.get("/v1/contratos", params={"formato": "csv"})
        .text.lstrip("﻿").splitlines()[0].split(",")
    )
    assert json_cols == csv_cols == set(ContratoResumen.model_fields)


def test_la_ficha_no_expone_cedulas_de_personas_naturales(cliente, monkeypatch):
    """Las cedulas del ordenador, el supervisor y el representante legal son
    dato personal: la ficha dice si estan y si dos coinciden, nunca el numero."""
    fila = {**CONTRATO, "doc_ordenador": "1098765432", "doc_supervisor": "1098765432",
            "doc_replegal": "79123456", "ordenador": "PEPE", "supervisor": "PEPE"}
    monkeypatch.setattr(consultas, "consultar_uno", lambda *a, **k: fila)
    monkeypatch.setattr(consultas, "_detalle_banderas", lambda f: [])
    cuerpo = cliente.get("/v1/contratos/CO1.BDOS.1").text
    for cedula in ("1098765432", "79123456"):
        assert cedula not in cuerpo
    partes = cliente.get("/v1/contratos/CO1.BDOS.1").json()["datos"]["partes"]
    assert partes["tiene_doc_ordenador"] and partes["tiene_doc_replegal"]
    assert partes["mismo_ordenador_supervisor"] is True
    assert "doc_ordenador" not in partes and "doc_supervisor" not in partes and "doc_replegal" not in partes
