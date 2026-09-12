"""Pruebas de la verificacion de habilitantes: cada tipo de regla, los
cuatro estados y una de humo sobre el pliego real extraido."""
from datetime import date

import pytest

from pliego.checklist import logica as L

CTX = {"smmlv": 908526, "anticipo_pct": 0.5, "fecha_cierre": date(2021, 7, 6)}
LOTE = {"n": 1, "presupuesto": 737_745_546, "plazo_meses": 4, "actividades": ["edificaciones", "espacio_publico"]}
RUP = {"archivo": "rup.pdf", "fecha_expedicion": "2021-06-18", "vigente": True, "en_firme": True,
       "contratos": [
           {"consecutivo": 1, "actividades": ["edificaciones"], "valor_smmlv": 640, "terminado": True},
           {"consecutivo": 2, "actividades": ["espacio_publico"], "valor_smmlv": 380, "terminado": True},
           {"consecutivo": 3, "actividades": ["edificaciones"], "valor_smmlv": 890, "terminado": False},
           {"consecutivo": 4, "actividades": ["vias"], "valor_smmlv": 1240, "terminado": True},
       ]}
BASE = {"id": "x", "categoria": "juridico", "titulo": "t", "pagina": 1, "seccion": "1", "cita": "c"}


def req(**kw):
    return {**BASE, **kw}


# --------------------------------------------------------------- documento
def test_documento_ausente_es_falta_documento():
    v = L.verificar(req(tipo="documento", documento="garantia"), {}, CTX, LOTE)
    assert v.estado == L.FALTA


def test_documento_presente_cumple():
    v = L.verificar(req(tipo="documento", documento="carta", ), {"carta": {"archivo": "c.pdf", "firmada": True}}, CTX, LOTE)
    assert v.estado == L.CUMPLE


def test_certificado_viejo_no_cumple_y_dice_cuantos_dias():
    r = req(tipo="documento", documento="camara", max_dias_expedicion=30)
    v = L.verificar(r, {"camara": {"fecha_expedicion": "2021-05-20"}}, CTX, LOTE)
    assert v.estado == L.NO_CUMPLE
    assert v.evidencia["dias_antes_del_cierre"] == 47
    v2 = L.verificar(r, {"camara": {"fecha_expedicion": "2021-06-18"}}, CTX, LOTE)
    assert v2.estado == L.CUMPLE and v2.evidencia["dias_antes_del_cierre"] == 18


def test_rup_no_en_firme_no_cumple():
    v = L.verificar(req(tipo="documento", documento="rup", en_firme=True), {"rup": {**RUP, "en_firme": False}}, CTX, LOTE)
    assert v.estado == L.NO_CUMPLE


# --------------------------------------------------------------- indicador
def test_indicador_con_umbral_del_pliego_cumple_o_no():
    r = req(tipo="indicador", documento="ef", campo="liquidez", op=">=", umbral=1.2)
    assert L.verificar(r, {"ef": {"liquidez": 1.8}}, CTX, LOTE).estado == L.CUMPLE
    assert L.verificar(r, {"ef": {"liquidez": 0.9}}, CTX, LOTE).estado == L.NO_CUMPLE
    r2 = req(tipo="indicador", documento="ef", campo="endeudamiento", op="<=", umbral=0.7)
    assert L.verificar(r2, {"ef": {"endeudamiento": 0.75}}, CTX, LOTE).estado == L.NO_CUMPLE


def test_indicador_con_umbral_simulado_es_revisar_aunque_cumpla():
    r = req(tipo="indicador", documento="ef", campo="liquidez", op=">=", umbral=1.2, umbral_simulado=True)
    v = L.verificar(r, {"ef": {"liquidez": 1.8}}, CTX, LOTE)
    assert v.estado == L.REVISAR and v.evidencia["umbral_simulado"] is True


def test_indicador_sin_estados_financieros_es_falta():
    r = req(tipo="indicador", documento="ef", campo="liquidez", op=">=", umbral=1.2)
    assert L.verificar(r, {}, CTX, LOTE).estado == L.FALTA


# --------------------------------------------------------- capital y residual
def test_capital_de_trabajo_contra_el_10_por_ciento_del_lote():
    r = req(tipo="capital_trabajo", documento="ef", pct_po=0.10)
    v = L.verificar(r, {"ef": {"activo_corriente": 3_100e6, "pasivo_corriente": 1_720e6}}, CTX, LOTE)
    assert v.estado == L.CUMPLE
    assert v.evidencia["demandado"] == pytest.approx(73_774_554.6)
    v2 = L.verificar(r, {"ef": {"activo_corriente": 1_000e6, "pasivo_corriente": 950e6}}, CTX, LOTE)
    assert v2.estado == L.NO_CUMPLE


def test_capacidad_residual_resta_el_anticipo():
    r = req(tipo="capacidad_residual", documento="f5")
    v = L.verificar(r, {"f5": {"capacidad_residual": 400e6}}, CTX, LOTE)
    assert v.evidencia["crpc"] == pytest.approx(737_745_546 * 0.5)
    assert v.estado == L.CUMPLE
    assert L.verificar(r, {"f5": {"capacidad_residual": 300e6}}, CTX, LOTE).estado == L.NO_CUMPLE


def test_capacidad_residual_se_anualiza_si_el_plazo_pasa_de_12_meses():
    r = req(tipo="capacidad_residual", documento="f5")
    lote = {**LOTE, "plazo_meses": 24}
    v = L.verificar(r, {"f5": {"capacidad_residual": 200e6}}, CTX, lote)
    assert v.evidencia["crpc"] == pytest.approx(737_745_546 * 0.5 * 12 / 24)
    assert v.estado == L.CUMPLE


# --------------------------------------------------------------- experiencia
TABLA = [{"contratos_max": 2, "pct": 0.75}, {"contratos_max": 4, "pct": 1.20}, {"contratos_max": 6, "pct": 1.50}]


def test_experiencia_usa_solo_contratos_terminados_de_las_actividades_del_lote():
    r = req(tipo="experiencia", documento="rup", tabla=TABLA)
    v = L.verificar(r, {"rup": RUP}, CTX, LOTE)
    # presupuesto 812,02 SMMLV; con 1 contrato (640) pide 75% = 609 -> cumple con 1
    assert v.estado == L.CUMPLE
    assert v.evidencia["contratos_usados"] == 1 and v.evidencia["acreditado_smmlv"] == 640
    assert 4 not in v.evidencia["contratos_validos"]  # vias no cuenta
    assert 3 not in v.evidencia["contratos_validos"]  # no terminado no cuenta


def test_experiencia_el_porcentaje_sube_con_mas_contratos():
    r = req(tipo="experiencia", documento="rup", tabla=TABLA)
    lote3 = {**LOTE, "presupuesto": 1_614_315_202, "actividades": ["edificaciones"]}
    v = L.verificar(r, {"rup": RUP}, CTX, lote3)
    # 1.776,85 SMMLV; solo 640 y 420? -> en RUP de prueba solo el 1 (640) es edificaciones terminado
    assert v.estado == L.NO_CUMPLE
    assert v.evidencia["pct_requerido"] == 0.75 and v.evidencia["acreditado_smmlv"] == 640


def test_experiencia_actividades_exige_las_dos():
    r = req(tipo="experiencia_actividades", documento="rup")
    assert L.verificar(r, {"rup": RUP}, CTX, LOTE).estado == L.CUMPLE
    solo_edif = {**RUP, "contratos": [c for c in RUP["contratos"] if "espacio_publico" not in c["actividades"]]}
    v = L.verificar(r, {"rup": solo_edif}, CTX, LOTE)
    assert v.estado == L.NO_CUMPLE and "espacio publico" in v.detalle


# ------------------------------------------------------------ otros tipos
def test_duracion_sociedad_plazo_mas_un_ano():
    r = req(tipo="duracion_sociedad", documento="camara")
    assert L.verificar(r, {"camara": {"duracion_hasta": "2035-12-31"}}, CTX, LOTE).estado == L.CUMPLE
    # cierre 2021-07-06 + 4 meses + 1 ano = ~2022-11-03
    assert L.verificar(r, {"camara": {"duracion_hasta": "2022-06-30"}}, CTX, LOTE).estado == L.NO_CUMPLE


def test_garantia_ausente_dice_cuanto_hay_que_asegurar():
    r = req(tipo="garantia", documento="gar", pct_po=0.10, meses_vigencia=3)
    v = L.verificar(r, {}, CTX, LOTE)
    assert v.estado == L.FALTA and v.evidencia["valor_requerido"] == pytest.approx(73_774_554.6)
    assert L.verificar(r, {"gar": {"valor_asegurado": 80e6}}, CTX, LOTE).estado == L.CUMPLE
    assert L.verificar(r, {"gar": {"valor_asegurado": 50e6}}, CTX, LOTE).estado == L.NO_CUMPLE


def test_revisar_es_juicio_humano():
    assert L.verificar(req(tipo="revisar"), {}, CTX, LOTE).estado == L.REVISAR


def test_tipo_desconocido_falla_en_vez_de_callar():
    with pytest.raises(ValueError):
        L.verificar(req(tipo="magia"), {}, CTX, LOTE)


def test_resumen_habil_solo_sin_fallas_ni_faltantes():
    vs = [L.verificar(req(tipo="revisar"), {}, CTX, LOTE), L.verificar(req(tipo="documento", documento="x"), {"x": {}}, CTX, LOTE)]
    assert L.resumen(vs)["habil"] is True
    vs.append(L.verificar(req(tipo="documento", documento="y"), {}, CTX, LOTE))
    assert L.resumen(vs)["habil"] is False


# --------------------------------------------------------------------- humo
def test_pliego_real_extraido_se_verifica_por_lote():
    from pliego.checklist import datos
    for n in (1, 2, 3):
        ck = datos.checklist(n)
        assert ck["resumen"]["total"] == 20
        assert all(r["pagina"] <= ck["proceso"]["paginas"] for r in ck["requisitos"])
        assert all(r["caja"] and r["caja"]["cajas"] for r in ck["requisitos"]), "toda cita tiene su caja en el PDF"
    ck1 = datos.checklist(1)
    estados = {r["id"]: r["estado"] for r in ck1["requisitos"]}
    assert estados["garantia"] == L.FALTA
    assert estados["formato3"] == L.FALTA
    assert estados["camara"] == L.NO_CUMPLE
    assert estados["liquidez"] == L.REVISAR
    assert estados["capacidad_residual"] == L.CUMPLE
    # el lote 3 exige mas experiencia en edificaciones de la que hay terminada
    assert {r["id"]: r["estado"] for r in datos.checklist(3)["requisitos"]}["experiencia"] == L.NO_CUMPLE
