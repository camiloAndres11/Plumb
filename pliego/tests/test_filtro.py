"""Pruebas de la logica del filtro: habilitantes, senales y puntaje.

Sobre dicts armados a mano (sin fixtures) para que cada regla se pruebe
sola. Al final, una de humo sobre los fixtures reales.
"""
import pytest

from pliego.filtro import logica as L
from pliego.filtro import reglas as R

PERFIL = {
    "unspsc": ["V1.72141000", "V1.72121400"],
    "rup": {"vigente": True},
    "capacidad_residual": 3_800e6,
    "departamentos_interes": ["SANTANDER"],
    "cuantia_objetivo": {"min": 500e6, "max": 3_000e6},
    "experiencia": [
        {"unspsc": "V1.72141000", "valor_smmlv": 1240},
        {"unspsc": "V1.72141100", "valor_smmlv": 610},   # misma familia 7214
        {"unspsc": "V1.72121400", "valor_smmlv": 100},
    ],
    "financiero": {"liquidez": 1.8, "endeudamiento": 0.55, "cobertura_intereses": 3.2},
    "organizacional": {"rentabilidad_patrimonio": 0.12, "rentabilidad_activo": 0.06},
}

PROCESO = {
    "id_del_proceso": "CO1.REQ.1", "unspsc": "V1.72141000", "departamento": "SANTANDER",
    "precio_base": 1_500e6, "modalidad": "LICITACION PUBLICA OBRA PUBLICA",
    "dias_restantes": 10, "dias_ventana": 20,
}

ENTIDAD_ABIERTA = {"n_contratos": 20, "n_proveedores": 15, "share_top1": 0.15,
                   "tasa_proponente_unico": 0.1, "mediana_oferentes": 6, "top1_proveedor": "X", "top1_n": 3}


def razon(ev, codigo):
    for r in ev.razones:
        if r.codigo == codigo:
            return r
    return None


# ------------------------------------------------------------ familia UNSPSC
def test_familia_es_cuatro_digitos_tras_el_prefijo():
    assert L.familia("V1.72141000") == "7214"
    assert L.familia("UNSPECIFIED") is None
    assert L.familia(None) is None


def test_experiencia_suma_toda_la_familia_no_solo_el_codigo_exacto():
    assert L.experiencia_en_familia(PERFIL, "7214") == 1240 + 610
    assert L.experiencia_en_familia(PERFIL, "9999") == 0


# ------------------------------------------------------------ habilitantes
def test_proceso_que_cumple_todo_se_recomienda():
    ev = L.evaluar(PERFIL, PROCESO, ENTIDAD_ABIERTA, None, 500)
    assert ev.recomendacion == L.PRESENTARSE
    assert all(r.cumple for r in ev.razones if r.habilitante)
    assert ev.horas_ahorradas == 0


def test_objeto_fuera_de_las_familias_del_perfil_descarta():
    ev = L.evaluar(PERFIL, {**PROCESO, "unspsc": "V1.81101500"}, ENTIDAD_ABIERTA, None, 500)
    assert ev.recomendacion == L.NO_PRESENTARSE
    assert razon(ev, "objeto").cumple is False
    assert razon(ev, "objeto").evidencia["familia"] == "8110"


def test_capacidad_residual_menor_al_presupuesto_descarta():
    ev = L.evaluar(PERFIL, {**PROCESO, "precio_base": 5_000e6}, ENTIDAD_ABIERTA, None, 500)
    assert ev.recomendacion == L.NO_PRESENTARSE
    r = razon(ev, "capacidad_residual")
    assert r.cumple is False and r.evidencia["cobertura"] == pytest.approx(3.8 / 5)


def test_experiencia_insuficiente_en_la_familia_descarta():
    # 2.500 millones = ~1.428 SMMLV; la familia 7212 solo acredita 100
    ev = L.evaluar(PERFIL, {**PROCESO, "unspsc": "V1.72121400", "precio_base": 2_500e6},
                   ENTIDAD_ABIERTA, None, 500)
    assert ev.recomendacion == L.NO_PRESENTARSE
    r = razon(ev, "experiencia")
    assert r.cumple is False
    assert r.evidencia["requerida_smmlv"] == pytest.approx(2_500e6 / R.SMMLV * R.EXPERIENCIA_FRACCION_MIN)


def test_indicador_financiero_por_debajo_del_umbral_descarta():
    perfil = {**PERFIL, "financiero": {**PERFIL["financiero"], "liquidez": 0.9}}
    ev = L.evaluar(perfil, PROCESO, ENTIDAD_ABIERTA, None, 500)
    assert ev.recomendacion == L.NO_PRESENTARSE
    assert razon(ev, "financiero").evidencia["fallan"] == ["liquidez"]


def test_rup_vencido_descarta():
    ev = L.evaluar({**PERFIL, "rup": {"vigente": False}}, PROCESO, ENTIDAD_ABIERTA, None, 500)
    assert ev.recomendacion == L.NO_PRESENTARSE


def test_sin_codigo_unspsc_es_revisar_no_descartar():
    ev = L.evaluar(PERFIL, {**PROCESO, "unspsc": "UNSPECIFIED"}, ENTIDAD_ABIERTA, None, 0)
    assert ev.recomendacion == L.REVISAR
    assert razon(ev, "objeto").cumple is None


def test_no_presentarse_reporta_horas_de_su_modalidad():
    ev = L.evaluar({**PERFIL, "rup": {"vigente": False}}, PROCESO, ENTIDAD_ABIERTA, None, 500)
    assert ev.horas_ahorradas == R.HORAS_POR_MODALIDAD["LICITACION PUBLICA OBRA PUBLICA"]
    ev2 = L.evaluar({**PERFIL, "rup": {"vigente": False}}, {**PROCESO, "modalidad": "RARA"},
                    ENTIDAD_ABIERTA, None, 500)
    assert ev2.horas_ahorradas == R.HORAS_DEFECTO


# ------------------------------------------------------------------ senales
def test_ganador_recurrente_resta_y_cita_al_ganador():
    hist = {**ENTIDAD_ABIERTA, "share_top1": 0.6, "top1_proveedor": "CONSORCIO Z", "top1_n": 12}
    ev = L.evaluar(PERFIL, PROCESO, hist, None, 500)
    r = razon(ev, "ganador_recurrente")
    assert r is not None and r.peso == R.PESOS["ganador_recurrente"]
    assert "CONSORCIO Z" in r.texto and "12 de 20" in r.texto
    assert razon(ev, "entidad_competitiva") is None


def test_ganador_recurrente_no_se_evalua_con_poca_muestra():
    hist = {**ENTIDAD_ABIERTA, "n_contratos": 3, "share_top1": 1.0}
    ev = L.evaluar(PERFIL, PROCESO, hist, None, 500)
    assert razon(ev, "ganador_recurrente") is None


def test_ganador_recurrente_en_la_familia_aunque_la_entidad_sea_abierta():
    fam = {"n_contratos": 8, "share_top1": 0.75, "top1_proveedor": "VIAS SAS", "familia": "7214"}
    ev = L.evaluar(PERFIL, PROCESO, ENTIDAD_ABIERTA, fam, 500)
    r = razon(ev, "ganador_recurrente")
    assert r is not None and "VIAS SAS" in r.texto and r.evidencia["familia"] == "7214"


def test_entidad_cerrada_por_proponente_unico():
    hist = {**ENTIDAD_ABIERTA, "tasa_proponente_unico": 0.85}
    ev = L.evaluar(PERFIL, PROCESO, hist, None, 500)
    assert razon(ev, "entidad_cerrada") is not None
    assert ev.puntaje < L.evaluar(PERFIL, PROCESO, ENTIDAD_ABIERTA, None, 500).puntaje


def test_codigo_raro_solo_bajo_el_umbral():
    assert razon(L.evaluar(PERFIL, PROCESO, None, None, 5), "codigo_raro") is not None
    assert razon(L.evaluar(PERFIL, PROCESO, None, None, R.CODIGO_RARO_N), "codigo_raro") is None


def test_plazo_corto_y_ventana_corta_restan():
    p = {**PROCESO, "dias_restantes": 2, "f_ventana_corta": True}
    ev = L.evaluar(PERFIL, p, ENTIDAD_ABIERTA, None, 500)
    assert razon(ev, "plazo_corto") is not None and razon(ev, "ventana_corta") is not None


def test_fuera_de_region_y_fuera_de_rango_restan():
    p = {**PROCESO, "departamento": "AMAZONAS", "precio_base": 200e6}
    ev = L.evaluar(PERFIL, p, ENTIDAD_ABIERTA, None, 500)
    assert razon(ev, "fuera_de_region") and razon(ev, "cuantia_fuera_rango")
    assert razon(ev, "departamento_interes") is None


def test_senales_sin_veredicto_no_mueven_el_puntaje():
    base = L.evaluar(PERFIL, PROCESO, ENTIDAD_ABIERTA, None, 500).puntaje
    con = L.evaluar(PERFIL, {**PROCESO, "f_cierre_movido": True, "f_sin_interes_a_tiempo": True},
                    ENTIDAD_ABIERTA, None, 500)
    assert con.puntaje == base
    assert razon(con, "cierre_movido").cumple is None


# ------------------------------------------------------------------ puntaje
def test_puntaje_acotado_entre_0_y_100():
    malo = {**PROCESO, "departamento": "AMAZONAS", "precio_base": 100e6, "dias_restantes": 1,
            "f_ventana_corta": True}
    cerrada = {**ENTIDAD_ABIERTA, "share_top1": 0.9, "tasa_proponente_unico": 0.95, "mediana_oferentes": 1}
    ev = L.evaluar(PERFIL, malo, cerrada, None, 1)
    assert 0 <= ev.puntaje <= 100
    assert ev.puntaje == 0


def test_umbrales_de_recomendacion_con_habilitantes_ok():
    # Sin senales de entidad: region, cuantia y las dos holguras a favor
    # (1.850 SMMLV acreditados > 2 x 857 requeridos; 3.800 > 1,5 x 1.500)
    ev = L.evaluar(PERFIL, PROCESO, None, None, 500)
    assert ev.puntaje == 50 + R.PESOS["departamento_interes"] + R.PESOS["cuantia_objetivo"] \
        + R.PESOS["capacidad_holgada"] + R.PESOS["experiencia_holgada"]
    assert ev.recomendacion == L.PRESENTARSE
    # Fuera de region y de rango, sin holguras: 50-12-8 = 30 -> no presentarse
    # aunque cumpla todos los habilitantes (justo: 3.600 > 3.500; 2.100 SMMLV > 1.999)
    justo = {**PERFIL, "capacidad_residual": 3_600e6,
             "experiencia": [{"unspsc": "V1.72141000", "valor_smmlv": 2100}]}
    ev2 = L.evaluar(justo, {**PROCESO, "departamento": "AMAZONAS", "precio_base": 3_500e6}, None, None, 500)
    assert ev2.puntaje == 30
    assert ev2.recomendacion == L.NO_PRESENTARSE
    assert all(r.cumple for r in ev2.razones if r.habilitante)
    assert ev2.horas_ahorradas > 0


def test_toda_razon_lleva_evidencia_o_texto_verificable():
    ev = L.evaluar(PERFIL, PROCESO, ENTIDAD_ABIERTA, None, 500)
    for r in ev.razones:
        assert r.texto and r.codigo


# --------------------------------------------------------------------- humo
def test_fixtures_reales_evaluan_todos_los_procesos():
    from pliego.filtro import datos
    evs = datos.evaluaciones()
    assert len(evs) == len(datos.procesos()) > 0
    recs = {x["evaluacion"]["recomendacion"] for x in evs}
    assert recs <= {L.PRESENTARSE, L.REVISAR, L.NO_PRESENTARSE}
    assert datos.resumen()["horas_ahorradas"] > 0
    # ordenados: los "presentarse" van primero
    orden = [x["evaluacion"]["recomendacion"] for x in evs]
    assert orden == sorted(orden, key={L.PRESENTARSE: 0, L.REVISAR: 1, L.NO_PRESENTARSE: 2}.get)
