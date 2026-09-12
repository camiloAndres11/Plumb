"""Pruebas del simulador: cada formula contra ejemplos calculados a mano,
la configuracion por version, la simulacion y el backtest."""
import random

import pytest

from pliego.simulador import logica as L
from pliego.simulador import metodos as M

V = M.VERSIONES["bucaramanga_2021"]
MAX = 60


# ---------------------------------------------------------------- formulas
def test_mediana_impar_maximo_en_la_mediana():
    vals = [90, 95, 100]
    assert M.mediana_valor_absoluto(vals, 95, MAX) == MAX
    assert M.mediana_valor_absoluto(vals, 90, MAX) == pytest.approx((1 - 5 / 95) * MAX)
    assert M.mediana_valor_absoluto(vals, 100, MAX) == pytest.approx((1 - 5 / 95) * MAX)


def test_mediana_par_maximo_a_la_inmediatamente_por_debajo():
    vals = [90, 94, 96, 100]     # mediana 95; por debajo: 94
    assert M.mediana_valor_absoluto(vals, 94, MAX) == MAX
    assert M.mediana_valor_absoluto(vals, 96, MAX) == pytest.approx((1 - 2 / 94) * MAX)


def test_media_geometrica_maximo_a_la_mas_cercana():
    vals = [90, 95, 100]
    mg = (90 * 95 * 100) ** (1 / 3)   # ~94.9
    assert M.media_geometrica(vals, 95, MAX) == MAX
    assert M.media_geometrica(vals, 90, MAX) == pytest.approx(MAX * (1 - abs(mg - 90) / mg))


def test_media_aritmetica_baja():
    vals = [90, 95, 100]
    # XB = (90 + 95) / 2 = 92,5
    assert M.media_aritmetica_baja(vals, 92.5, MAX) == MAX
    assert M.media_aritmetica_baja(vals, 100, MAX) == pytest.approx(MAX * (1 - 7.5 / 92.5))


def test_menor_valor():
    vals = [90, 95, 100]
    assert M.menor_valor(vals, 90, MAX) == MAX
    assert M.menor_valor(vals, 100, MAX) == pytest.approx(54)


def test_puntaje_negativo_se_vuelve_cero():
    assert M.mediana_valor_absoluto([10, 100, 1000], 1000, MAX) == 0
    assert M.media_geometrica([10, 100, 1000], 1000, MAX) == 0


def test_formulas_son_homogeneas_en_pesos_o_en_fraccion():
    vals = [0.90, 0.95, 1.00]
    pesos = [x * 737_745_546 for x in vals]
    for f in (M.mediana_valor_absoluto, M.media_geometrica, M.media_aritmetica_baja, M.menor_valor):
        assert f(vals, 0.90, MAX) == pytest.approx(f(pesos, 0.90 * 737_745_546, MAX))


# ------------------------------------------------------------ configuracion
def test_la_trm_elige_el_metodo_por_rangos_de_centavos():
    assert V.por_centavos(0).clave == "mediana" and V.por_centavos(24).clave == "mediana"
    assert V.por_centavos(25).clave == "geometrica" and V.por_centavos(49).clave == "geometrica"
    assert V.por_centavos(50).clave == "aritmetica_baja" and V.por_centavos(74).clave == "aritmetica_baja"
    assert V.por_centavos(75).clave == "menor_valor" and V.por_centavos(99).clave == "menor_valor"
    with pytest.raises(ValueError):
        V.por_centavos(100)


def test_las_probabilidades_de_los_metodos_suman_uno():
    assert sum(m.probabilidad for m in V.metodos) == pytest.approx(1.0)


def test_una_version_nueva_cambia_el_resultado_sin_tocar_la_logica():
    solo_menor = M.Version("x", "x", "x", 100, (M.Metodo("menor_valor", "Menor valor", M.menor_valor, 0, 99),))
    pool = L.Pool("nacional", "", [0.95, 0.96, 0.97, 0.98, 0.99, 1.0], [4, 5, 6])
    rec = L.recomendar(pool, solo_menor, n_sim=60, rng=random.Random(1), malla=[0.85, 0.9, 0.95, 1.0])
    assert rec.ratio == 0.85          # con menor valor siempre gana el mas bajo
    assert rec.esperado == pytest.approx(100, abs=1e-6)


# ---------------------------------------------------------------- pool
HIST = (
    [{"id_contrato": f"e{i}", "nit_entidad": "1", "departamento": "SANTANDER", "familia": "7214",
      "modalidad": "L", "ratio": 0.95, "n_oferentes_unicos": 5, "entidad": "E1", "precio_base": 1e9, "fecha_firma": "2025-01-01"} for i in range(12)]
    + [{"id_contrato": f"d{i}", "nit_entidad": "2", "departamento": "SANTANDER", "familia": "7214",
        "modalidad": "L", "ratio": 0.90, "n_oferentes_unicos": 8, "entidad": "E2", "precio_base": 1e9, "fecha_firma": "2025-02-01"} for i in range(12)]
    + [{"id_contrato": f"s{i}", "nit_entidad": "3", "departamento": "BOYACA", "familia": "7214",
        "modalidad": "L", "ratio": 1.0, "n_oferentes_unicos": 1, "entidad": "E3", "precio_base": 1e9, "fecha_firma": "2025-03-01"} for i in range(12)]
)


def test_pool_usa_el_nivel_mas_especifico_con_muestra():
    p = L.armar_pool(HIST, {"nit_entidad": "1", "departamento": "SANTANDER", "familia": "7214", "modalidad": "L"})
    assert p.nivel == "entidad" and p.n == 12 and set(p.ratios) == {0.95}
    p2 = L.armar_pool(HIST, {"nit_entidad": "9", "departamento": "SANTANDER", "familia": "7214", "modalidad": "L"})
    assert p2.nivel == "departamento_familia" and p2.n == 24
    p3 = L.armar_pool(HIST, {"nit_entidad": "9", "departamento": "AMAZONAS", "familia": "7214", "modalidad": "L"})
    assert p3.nivel == "familia"


def test_pool_excluye_procesos_sin_competencia_y_el_propio():
    p = L.armar_pool(HIST, {"nit_entidad": "3", "departamento": "BOYACA", "familia": "7214", "modalidad": "L"})
    assert 1.0 not in p.ratios          # los de un solo oferente no ensenan nada del precio
    p2 = L.armar_pool(HIST, {"nit_entidad": "1", "departamento": "SANTANDER", "familia": "7214", "modalidad": "L"}, excluir_id="e0")
    assert p2.n == 11


# ------------------------------------------------------------- simulacion
def test_recomendacion_reproducible_y_dentro_de_la_malla():
    pool = L.Pool("nacional", "", [0.93, 0.95, 0.96, 0.97, 0.99], [5, 8, 12])
    a = L.recomendar(pool, V, n_sim=100, rng=random.Random(3))
    b = L.recomendar(pool, V, n_sim=100, rng=random.Random(3))
    assert a.ratio == b.ratio and a.esperado == b.esperado
    assert 0.85 <= a.ratio <= 1.0
    assert a.rango[0] <= a.ratio <= a.rango[1]
    assert all(0 <= p.esperado <= 60 for p in a.malla)
    assert all(0 <= p.prob_primero <= 1 for p in a.malla)


def test_el_precio_recomendado_esta_cerca_del_centro_del_pool_no_del_piso():
    # Con tres metodos de cuatro premiando el centro, ofertar al 85 % pierde
    pool = L.Pool("nacional", "", [0.94, 0.95, 0.96, 0.97, 0.98], [10, 12, 15])
    rec = L.recomendar(pool, V, n_sim=150, rng=random.Random(5))
    assert 0.92 <= rec.ratio <= 0.98
    peor = next(p for p in rec.malla if p.ratio == 0.85)
    assert peor.esperado < rec.esperado


def test_puntaje_por_metodo_cuadra_con_el_esperado():
    pool = L.Pool("nacional", "", [0.95, 0.96, 0.97], [4])
    rec = L.recomendar(pool, V, n_sim=30, rng=random.Random(2), malla=[0.95])
    p = rec.malla[0]
    assert p.esperado == pytest.approx(sum(m.probabilidad * p.por_metodo[m.clave] for m in V.metodos))


# ---------------------------------------------------------------- backtest
def test_backtest_excluye_el_proceso_evaluado_y_reporta_fracciones():
    res = L.backtest(HIST, V, n_procesos=5, n_sim=20, rng=random.Random(4), min_oferentes=3)
    assert res["n"] == 5
    assert 0 <= res["pct_primero"] <= 1 and 0 <= res["pct_gana_al_ganador"] <= 1
    for r in res["resultados"]:
        assert r["n_oferentes"] >= 3 and 0.85 <= r["ratio_recomendado"] <= 1.0


# --------------------------------------------------------------------- humo
def test_fixtures_reales():
    from pliego.simulador import datos
    hist = datos.historico()
    assert len(hist) > 10_000
    ab = datos.abiertos()
    assert ab and all(a["precio_base"] > 0 for a in ab)
    rec = datos.recomendar_para(ab[0]["id_del_proceso"], n_sim=40)
    assert 0.85 <= rec["ratio"] <= 1.0 and rec["pool"]["n"] >= L.PISO_MUESTRA
