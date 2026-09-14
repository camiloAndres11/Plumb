"""Pruebas del adaptador de Croma: cliente, mapeo y armado de tablas.

Sin red ni llave: el cliente recibe una sesion falsa que devuelve lo que
cada prueba le programa, y el armado de tablas se alimenta con dicts que
imitan los registros de Croma tal como los describe su documentacion.
La prueba de humo final comprueba que las SQL de las semillas corren sobre
esas tablas y devuelven las columnas que cada datos.py espera.
"""
from __future__ import annotations

from datetime import date

import pytest

from pliego.comun import croma as C
from pliego.comun import fuente as F
from pliego.comun import mapeo_croma as M


# ------------------------------------------------------------- sesion falsa
class Resp:
    def __init__(self, estado=200, cuerpo=None, cabeceras=None):
        self.status_code = estado
        self._cuerpo = cuerpo
        self.headers = cabeceras or {}

    def json(self):
        if self._cuerpo is None:
            raise ValueError("sin json")
        return self._cuerpo


class Sesion:
    """Devuelve las respuestas en orden y guarda lo que se le pidio."""

    def __init__(self, *respuestas):
        import threading
        self.respuestas = list(respuestas)
        self.llamadas = []
        self._candado = threading.Lock()

    def post(self, url, json=None, headers=None, timeout=None):
        with self._candado:   # fuente._traer llama desde varios hilos
            self.llamadas.append((url, json, headers))
            return self.respuestas.pop(0)


def cliente(*respuestas, esperas=None):
    ses = Sesion(*respuestas)
    api = C.CromaCliente(llave_api="croma_test_x", base_url="https://api.test",
                         session=ses, dormir=(esperas.append if esperas is not None else lambda s: None))
    return api, ses


def pagina(filas, total_paginas=1, as_of="2026-09-12T05:00:00Z"):
    return {"data": {"as_of": as_of, "total_pages": total_paginas, "results": filas}}


# ------------------------------------------------------------------ cliente
def test_sin_llave_no_arranca(monkeypatch):
    monkeypatch.delenv("CROMA_API_KEY", raising=False)
    assert not C.disponible()
    with pytest.raises(C.ClaveInvalida):
        C.CromaCliente()


def test_llamar_manda_bearer_y_devuelve_data():
    api, ses = cliente(Resp(200, pagina([{"id": "x"}]), {"X-RateLimit-Remaining": "4990"}))
    data = api.llamar("/co/secop/processes-search/v1", {"query": "obra"})
    url, cuerpo, cab = ses.llamadas[0]
    assert url == "https://api.test/co/secop/processes-search/v1"
    assert cab["Authorization"] == "Bearer croma_test_x"
    assert cuerpo == {"query": "obra"}
    assert data["results"] == [{"id": "x"}]
    assert api.creditos_restantes == 4990


def test_429_espera_retry_after_y_reintenta():
    esperas = []
    api, ses = cliente(Resp(429, {"error": {"code": "rate_limited"}}, {"Retry-After": "7"}),
                       Resp(200, pagina([])), esperas=esperas)
    api.llamar("/x")
    assert esperas == [7.0]
    assert len(ses.llamadas) == 2


def test_402_es_sin_creditos_y_no_reintenta():
    api, ses = cliente(Resp(402, {"error": {"code": "billing_error", "message": "sin saldo"}},
                            {"X-RateLimit-Reset": "2026-10-01T00:00:00Z"}))
    with pytest.raises(C.SinCreditos) as e:
        api.llamar("/x")
    assert e.value.reinicio == "2026-10-01T00:00:00Z"
    assert len(ses.llamadas) == 1


def test_401_es_clave_invalida():
    api, _ = cliente(Resp(401, {"error": {"code": "invalid_api_key"}}))
    with pytest.raises(C.ClaveInvalida):
        api.llamar("/x")


def test_paginar_recorre_hasta_total_pages_y_marca_as_of():
    api, ses = cliente(Resp(200, pagina([{"id": 1}, {"id": 2}], total_paginas=2, as_of="A")),
                       Resp(200, pagina([{"id": 3}], total_paginas=2, as_of="B")))
    filas = list(api.paginar("/x", {"q": 1}, max_paginas=10))
    assert [f["id"] for f in filas] == [1, 2, 3]
    assert [f["_as_of"] for f in filas] == ["A", "A", "B"]
    assert ses.llamadas[0][1] == {"q": 1, "page": 1, "per_page": 100}
    assert ses.llamadas[1][1]["page"] == 2


def test_paginar_respeta_el_tope_de_paginas():
    api, ses = cliente(Resp(200, pagina([{"id": 1}], total_paginas=50)),
                       Resp(200, pagina([{"id": 2}], total_paginas=50)))
    assert len(list(api.paginar("/x", {}, max_paginas=2))) == 2
    assert len(ses.llamadas) == 2


def test_paginar_para_en_pagina_vacia():
    api, ses = cliente(Resp(200, pagina([], total_paginas=None)))
    assert list(api.paginar("/x", {}, max_paginas=5)) == []
    assert len(ses.llamadas) == 1


# -------------------------------------------------------------------- mapeo
def test_norm_txt_como_el_warehouse():
    assert M.norm_txt("  Selección   Abreviada de Menor Cuantía ") == "SELECCION ABREVIADA DE MENOR CUANTIA"
    assert M.norm_txt("Bogotá D.C.") == "BOGOTA D.C."
    assert M.norm_txt("") is None and M.norm_txt(None) is None


def test_norm_doc_quita_puntos_y_digito_de_verificacion():
    assert M.norm_doc("900.195.855-1") == "900195855"
    assert M.norm_doc("900195855") == "900195855"
    assert M.norm_doc(" 12.345.678 ") == "12345678"


def test_notice_uid_lo_saca_de_una_url_o_de_un_id():
    assert M.notice_uid("https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUID=CO1.NTC.82911") == "CO1.NTC.82911"
    assert M.notice_uid(None, "secop_ii:CO1.NTC.5", ) == "CO1.NTC.5"
    assert M.notice_uid("CO1.REQ.1", "nada") is None


PROCESO_CROMA = {
    "id": "secop_ii:CO1.REQ.10811072", "notice_uid": "CO1.NTC.82911",
    "url": "https://community.secop.gov.co/...noticeUID=CO1.NTC.82911",
    "entity": "Alcaldía de Bucaramanga", "entity_nit": "890.201.222-0",
    "entity_department": "Santander", "entity_city": "Bucaramanga",
    "contract_type": "Obra", "modality": "Licitación pública Obra Pública",
    "unspsc_code": "V1.72141000", "description": "Pavimentación vía rural",
    "base_price": 1500000000, "awarded": "yes", "awarded_value": 1450000000,
    "invited_providers": 12, "interested_providers": 4, "responses": 3,
    "unique_responding_providers": 3,
    "published_date": "2026-08-01", "bid_deadline": "2026-08-21", "award_date": "2026-09-01",
}


def test_proceso_a_fila_tiene_el_esquema_de_alertas():
    f = M.proceso_a_fila(PROCESO_CROMA, hoy=date(2026, 8, 10))
    assert f["id_del_proceso"] == "CO1.REQ.10811072"
    assert f["notice_uid"] == "CO1.NTC.82911"
    assert f["nit_entidad"] == "890201222"
    assert f["entidad"] == "ALCALDIA DE BUCARAMANGA"
    assert f["departamento"] == "SANTANDER" and f["ciudad"] == "BUCARAMANGA"
    assert f["tipo_contrato"] == "OBRA" and f["modalidad"] == "LICITACION PUBLICA OBRA PUBLICA"
    assert f["precio_base"] == 1.5e9 and f["valor_adjudicado"] == 1.45e9 and f["adjudicado"] is True
    assert (f["n_invitados"], f["n_manifestaron"], f["n_respuestas"], f["n_oferentes_unicos"]) == (12, 4, 3, 3)
    assert f["dias_ventana"] == 20 and f["dias_restantes"] == 11


CONTRATO_CROMA = {
    "id": "secop_ii:CO1.PCCNTR.5201", "contract_id": "CO1.PCCNTR.5201",
    "process_id": "CO1.REQ.10811072",
    "entity": "Alcaldía de Bucaramanga", "entity_nit": "890201222",
    "entity_department": "Santander", "entity_city": "Bucaramanga", "entity_order": "Territorial",
    "provider": "Constructora Andina S.A.S.", "provider_document": "900.123.456-7",
    "is_group": False, "status": "En ejecución", "contract_type": "Obra",
    "modality": "Licitación pública Obra Pública", "unspsc_code": "V1.72141000",
    "object": "Pavimentación vía rural " + "x" * 200,
    "value": 1450000000, "paid_value": 500000000, "pending_execution_value": 950000000,
    "sign_date": "2026-09-05", "start_date": "2026-09-10", "end_date": "2027-03-10",
}


def test_contrato_a_fila_toma_del_proceso_lo_que_el_contrato_no_trae():
    p = M.proceso_a_fila(PROCESO_CROMA, hoy=date(2026, 9, 10))
    f = M.contrato_a_fila(CONTRATO_CROMA, p)
    assert f["id_contrato"] == "CO1.PCCNTR.5201"
    assert f["doc_proveedor"] == "9001234567"[:9] or f["doc_proveedor"] == "900123456"
    assert f["proveedor"] == "CONSTRUCTORA ANDINA S.A.S."
    assert f["es_grupo"] == "NO" and f["orden"] == "TERRITORIAL" and f["estado"] == "EN EJECUCION"
    assert f["valor_adjudicado"] == f["valor_plausible"] == 1.45e9
    assert f["precio_base"] == 1.5e9                # del proceso
    assert f["n_oferentes_unicos"] == 3 and f["n_respuestas"] == 3   # del proceso
    assert f["fecha_cierre_ofertas"] == "2026-08-21"  # del proceso
    assert f["notice_uid"] == "CO1.NTC.82911"
    assert f["anio"] == 2026 and len(f["descripcion"]) == 120


def test_contrato_sin_proceso_deja_nulos_no_inventa():
    f = M.contrato_a_fila(CONTRATO_CROMA, None)
    assert f["precio_base"] is None and f["n_oferentes_unicos"] is None
    assert f["valor_adjudicado"] == 1.45e9


def test_valor_implausible_no_pasa_al_warehouse():
    f = M.contrato_a_fila({**CONTRATO_CROMA, "value": 5e13}, None)
    assert f["valor_adjudicado"] == 5e13 and f["valor_plausible"] is None


# ----------------------------------------------------------- armado + SQL
def _abierto(i, **extra):
    return {**PROCESO_CROMA, "id": f"secop_ii:CO1.REQ.{i}", "notice_uid": f"CO1.NTC.{i}",
            "url": f"...noticeUID=CO1.NTC.{i}", "awarded": "no", "awarded_value": None,
            "published_date": "2026-09-01", "bid_deadline": "2026-09-20", **extra}


def _adjudicado(i, nit="890201222", oferentes=3, ventana=20):
    return {**PROCESO_CROMA, "id": f"secop_ii:CO1.REQ.{i}", "notice_uid": f"CO1.NTC.{i}",
            "url": f"...noticeUID=CO1.NTC.{i}", "entity_nit": nit,
            "unique_responding_providers": oferentes, "responses": oferentes,
            "published_date": "2026-01-01", "bid_deadline": f"2026-01-{1 + ventana:02d}"}


def _contrato(i, nit="890201222", doc="900123456", valor=1.45e9):
    return {**CONTRATO_CROMA, "id": f"secop_ii:CO1.PCCNTR.{i}", "contract_id": f"CO1.PCCNTR.{i}",
            "process_id": f"CO1.REQ.{i}", "entity_nit": nit, "provider_document": doc, "value": valor,
            "sign_date": "2026-02-01"}


def _tablas():
    hoy = date(2026, 9, 10)
    # 6 contratos de la entidad A (3 con proponente unico) y 2 de la B, con sus procesos
    adjudicados = [_adjudicado(i, oferentes=(1 if i % 2 else 4)) for i in range(1, 7)]
    adjudicados += [_adjudicado(i, nit="800000001", oferentes=6) for i in range(7, 9)]
    contratos = [_contrato(i, doc=("900123456" if i <= 4 else "900999999")) for i in range(1, 7)]
    contratos += [_contrato(i, nit="800000001", doc="900777777") for i in range(7, 9)]
    abiertos = [_abierto(101), _abierto(102, invited_providers=8, interested_providers=0,
                                        bid_deadline="2026-09-15"), _abierto(103, bid_deadline="2026-08-01")]
    return F._armar(contratos, adjudicados, abiertos, hoy, meta={"as_of": "T"})


def test_armar_enlaza_contrato_con_proceso_y_calcula_banderas():
    con, meta = _tablas()
    assert meta == {"as_of": "T"}
    base = con.execute("SELECT count(*), count(precio_base), count(n_oferentes_unicos) FROM base").fetchone()
    assert base == (8, 8, 8)      # todos los contratos encontraron su proceso
    filas = {r[0]: r for r in con.execute(
        "SELECT id_del_proceso, universo, f_sin_interes_a_tiempo, f_historial_proponente_unico, "
        "f_al_tope_minima, f_cierre_movido, n_banderas, dias_restantes FROM alertas").fetchall()}
    assert filas["CO1.REQ.101"][1] == "accionable" and filas["CO1.REQ.103"][1] == "cierre_vencido"
    # 8 invitados, 0 manifestaron, cierra en 5 dias -> sin interes a tiempo
    assert filas["CO1.REQ.102"][2] is True and filas["CO1.REQ.101"][2] is False
    # la entidad A adjudico 3 de 6 con proponente unico: tasa 0.5, no llega a 0.8
    assert filas["CO1.REQ.101"][3] is False
    # lo que Croma no deja calcular queda en NULL, no en False
    assert filas["CO1.REQ.101"][4] is None and filas["CO1.REQ.101"][5] is None
    # 102 ademas tiene ventana de 14 dias contra un p10 de 20 -> 2 banderas
    assert filas["CO1.REQ.102"][6] == 2 and filas["CO1.REQ.101"][7] == 10


def test_las_sql_de_las_semillas_corren_sobre_las_tablas_de_croma(monkeypatch):
    con, meta = _tablas()
    monkeypatch.setattr(F, "_db", lambda: (con, meta))
    esperado = {
        ("filtro", "procesos_abiertos"): {"id_del_proceso", "precio_base", "dias_restantes", "f_ventana_corta"},
        ("filtro", "entidades_historial"): {"nit_entidad", "share_top1", "tasa_proponente_unico", "mediana_oferentes"},
        ("filtro", "entidad_familia"): {"nit_entidad", "familia", "share_top1"},
        ("filtro", "unspsc_frecuencia"): {"unspsc", "n"},
        ("radar", "contratos"): {"id_contrato", "doc_proveedor", "ratio", "familia", "valor_pend_ejecucion"},
        ("radar", "abiertos"): {"id_del_proceso", "familia", "dias_restantes"},
        ("simulador", "historico"): {"id_contrato", "notice_uid", "ratio", "n_oferentes_unicos"},
        ("simulador", "abiertos"): {"id_del_proceso", "precio_base", "n_respuestas"},
    }
    for clave, columnas in esperado.items():
        filas = F._consultar(F._SEMILLAS[clave]())
        assert filas, clave
        assert columnas <= set(filas[0]), clave
    hist = {f["nit_entidad"]: f for f in F._consultar(F._SEMILLAS[("filtro", "entidades_historial")]())}
    a = hist["890201222"]
    assert a["n_contratos"] == 6 and a["n_proveedores"] == 2
    assert a["top1_doc"] == "900123456" and abs(a["share_top1"] - 4 / 6) < 1e-9
    assert abs(a["tasa_proponente_unico"] - 0.5) < 1e-9
    # las fechas salen como ISO, igual que del parquet
    assert isinstance(F._consultar(F._SEMILLAS[("radar", "contratos")]())[0]["fecha_firma"], str)


# --------------------------------------------------------------- conmutador
def test_sin_pedirlo_la_fuente_son_los_fixtures(monkeypatch):
    monkeypatch.delenv("PLIEGO_FUENTE", raising=False)
    monkeypatch.setenv("CROMA_API_KEY", "croma_test_x")
    assert F.activa() == "fixtures" and F.hoy() == F.FECHA_SNAPSHOT


def test_pedirlo_sin_llave_cae_a_fixtures(monkeypatch):
    monkeypatch.setenv("PLIEGO_FUENTE", "croma")
    monkeypatch.delenv("CROMA_API_KEY", raising=False)
    assert F.activa() == "fixtures"


def test_con_llave_y_pedido_es_croma(monkeypatch):
    monkeypatch.setenv("PLIEGO_FUENTE", "croma")
    monkeypatch.setenv("CROMA_API_KEY", "croma_test_x")
    assert F.activa() == "croma" and F.hoy() == date.today()


def test_departamentos_como_los_escribe_secop():
    assert F._depto_secop("SANTANDER") == "Santander"
    assert F._depto_secop("NORTE DE SANTANDER") == "Norte de Santander"
    assert F._depto_secop("BOGOTA D.C.") == "Bogotá D.C."
    assert F._depto_secop("Valle del Cauca") == "Valle del Cauca"


def test_traer_consulta_por_departamento_y_tipo_con_los_filtros_correctos(monkeypatch, tmp_path):
    monkeypatch.setattr(F, "CACHE", tmp_path)
    monkeypatch.setenv("PLIEGO_FUENTE", "croma")
    monkeypatch.setenv("CROMA_API_KEY", "croma_test_x")
    monkeypatch.setenv("CROMA_DESDE_ANIO", "2023")
    respuestas = [Resp(200, pagina([])) for _ in range(2 * 3 * 3)]
    api, ses = cliente(*respuestas)
    *_, errores = F._traer(api, {"departamentos_interes": ["SANTANDER", "BOYACA"]})
    assert errores == [] and len(ses.llamadas) == 18
    rutas = {u.rsplit("/", 2)[-2] for u, _, _ in ses.llamadas}
    assert rutas == {"contracts-search", "processes-search"}
    cuerpos = [c for _, c, _ in ses.llamadas]
    assert {c["department"] for c in cuerpos} == {"Santander", "Boyacá"}
    assert {c["contract_type"] for c in cuerpos} == set(F.TIPOS_CONSTRUCCION)
    assert all(c["platform"] == "secop_ii" for c in cuerpos)
    assert {c.get("awarded") for c in cuerpos} == {None, "yes", "no"}
    assert any(c.get("from_date") == "2023-01-01" for c in cuerpos)


# ---------------------------------------------------------- campos reales
def test_unspsc_al_formato_del_warehouse():
    assert M.unspsc("V1.72141001") == "V1.72141001"
    assert M.unspsc("721410") == "V1.72141000"        # SECOP I: 6 digitos
    assert M.unspsc("UNSPECIFIED") is None and M.unspsc(None) is None


def test_contrato_real_de_croma_enlaza_por_la_url_y_lee_provider_is_group():
    # Forma real de un contrato SECOP II en Croma (sonda 2026-09-13): sin
    # process_id, con el noticeUID dentro de `url` y `provider_is_group`.
    r = {"id": "secop_ii:CO1.PCCNTR.9930859", "contract_id": "CO1.PCCNTR.9930859",
         "entity": "ALCALDIA CIMITARRA", "entity_nit": "890208363", "entity_department": "Santander",
         "provider": "Empresa de Desarrollo", "provider_document": "901956792", "provider_is_group": True,
         "unspsc_code": "V1.72141001", "contract_type": "Obra", "modality": "Contratación directa",
         "status": "En ejecución", "value": 1583841849, "sign_date": "2026-09-10",
         "url": "https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUID=CO1.NTC.10875302&isFromPublicArea=True"}
    f = M.contrato_a_fila(r, None)
    assert f["notice_uid"] == "CO1.NTC.10875302" and f["es_grupo"] == "SI"
    assert f["unspsc"] == "V1.72141001" and f["modalidad"] == "CONTRATACION DIRECTA"


def test_paginas_usa_el_cache_del_dia(tmp_path, monkeypatch):
    monkeypatch.setattr(F, "CACHE", tmp_path)
    monkeypatch.setenv("CROMA_CACHE_HORAS", "24")
    api, ses = cliente(Resp(200, pagina([{"id": 1}])), Resp(200, pagina([{"id": 2}])))
    assert [f["id"] for f in F._paginas(api, "/x/v1", {"a": 1})] == [1]
    assert [f["id"] for f in F._paginas(api, "/x/v1", {"a": 1})] == [1]   # del disco, sin llamar
    assert len(ses.llamadas) == 1
    assert [f["id"] for f in F._paginas(api, "/x/v1", {"a": 2})] == [2]   # otra consulta, otra llave
    assert len(list(tmp_path.glob("*.json"))) == 2


def test_cache_desactivado_con_cero_horas(tmp_path, monkeypatch):
    monkeypatch.setattr(F, "CACHE", tmp_path)
    monkeypatch.setenv("CROMA_CACHE_HORAS", "0")
    api, ses = cliente(Resp(200, pagina([{"id": 1}])), Resp(200, pagina([{"id": 1}])))
    F._paginas(api, "/x/v1", {})
    F._paginas(api, "/x/v1", {})
    assert len(ses.llamadas) == 2


def test_timeout_de_una_pagina_se_reintenta():
    import requests

    class SesionLenta(Sesion):
        def post(self, *a, **k):
            if len(self.llamadas) == 0:
                self.llamadas.append(("timeout", None, None))
                raise requests.Timeout("lenta")
            return super().post(*a, **k)

    ses = SesionLenta(Resp(200, pagina([{"id": 1}])))
    api = C.CromaCliente(llave_api="k", base_url="https://api.test", session=ses, dormir=lambda s: None)
    assert api.llamar("/x")["results"] == [{"id": 1}]
    assert len(ses.llamadas) == 2


def test_una_busqueda_fallida_no_tumba_el_arranque(monkeypatch, tmp_path):
    monkeypatch.setattr(F, "CACHE", tmp_path)
    monkeypatch.setenv("CROMA_HILOS", "1")
    respuestas = [Resp(402, {"error": {"code": "billing_error"}})] + [Resp(200, pagina([{"id": i}])) for i in range(8)]
    api, ses = cliente(*respuestas)
    contratos, adjudicados, abiertos, errores = F._traer(api, {"departamentos_interes": ["SANTANDER"]})
    assert len(errores) == 1 and "402" in errores[0]["error"]
    assert len(contratos) + len(adjudicados) + len(abiertos) == 8
