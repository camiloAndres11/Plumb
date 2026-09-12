"""Pruebas del radar: agregaciones por entidad y competidor, saturacion y
competidores probables, sobre un historico chico armado a mano."""
from datetime import date

import pytest

from pliego.radar import logica as L

HOY = date(2026, 8, 22)


def c(id_, nit, prov, nombre="P", ratio=0.95, ofer=5, anio=2025, dep="SANTANDER", fam="7214",
      modalidad="LICITACION PUBLICA OBRA PUBLICA", estado="TERMINADO", fin="2025-12-31", pend=0, valor=1000e6, tipo="OBRA"):
    return {"id_contrato": id_, "nit_entidad": nit, "entidad": "E" + nit, "departamento": dep, "familia": fam,
            "modalidad": modalidad, "precio_base": valor, "valor_adjudicado": valor * ratio, "ratio": ratio,
            "n_oferentes_unicos": ofer, "anio": anio, "fecha_firma": f"{anio}-03-01", "fecha_fin": fin, "estado": estado,
            "doc_proveedor": prov, "proveedor": nombre, "valor_plausible": valor, "valor_pend_ejecucion": pend,
            "tipo_contrato": tipo, "es_grupo": "NO"}


HIST = (
    [c(f"a{i}", "1", "A", "ALFA SAS", ratio=0.96, ofer=8) for i in range(6)]          # A domina la entidad 1
    + [c(f"b{i}", "1", "B", "BETA SAS", ratio=0.93, ofer=8) for i in range(2)]
    + [c("d1", "1", "D", "DIRECTA", modalidad="CONTRATACION DIRECTA (CON OFERTAS)")]  # no cuenta
    + [c(f"c{i}", "2", f"P{i}", f"PROV {i}", ratio=0.94, ofer=12) for i in range(10)]  # entidad 2 abierta
    + [c(f"u{i}", "3", "U", "UNICO SAS", ratio=1.0, ofer=1) for i in range(5)]          # entidad 3 proponente unico
    + [c("e1", "4", "B", "BETA SAS", fam="7214", dep="SANTANDER", estado="EN EJECUCION", fin="2027-06-30", pend=2500e6, valor=3000e6, anio=2026)]
    + [c("e2", "5", "B", "BETA SAS", fam="7214", dep="BOYACA", estado="EN EJECUCION", fin="2027-01-31", pend=1500e6, valor=2000e6, anio=2026)]
    + [c("v1", "6", "A", "ALFA SAS", estado="MODIFICADO", fin="2024-01-01", pend=100e6, anio=2022)]      # vencido: no cuenta
)


# ------------------------------------------------------------ entidad
def test_entidad_predecible_por_ganador_recurrente():
    p = L.perfil_entidad(HIST, "1", HOY)
    assert p["n_competitivos"] == 8                    # la directa no cuenta
    assert p["ganadores"][0]["doc"] == "A" and p["ganadores"][0]["n"] == 6
    assert p["share_top1"] == pytest.approx(0.75)
    assert p["etiqueta"] == "predecible" and "ALFA SAS" in p["razon"]
    assert p["margen_mediano"] == pytest.approx(1 - 0.96)


def test_entidad_abierta():
    p = L.perfil_entidad(HIST, "2", HOY)
    assert p["n_proveedores"] == 10 and p["share_top1"] == pytest.approx(0.1)
    assert p["etiqueta"] == "abierta" and p["mediana_oferentes"] == 12


def test_entidad_predecible_por_proponente_unico():
    p = L.perfil_entidad(HIST, "3", HOY)
    assert p["tasa_proponente_unico"] == 1.0 and p["etiqueta"] == "predecible"


def test_entidad_sin_muestra_o_inexistente():
    assert L.perfil_entidad(HIST, "4", HOY)["etiqueta"] == "sin_muestra"
    assert L.perfil_entidad(HIST, "999", HOY) is None


def test_el_tipo_de_contrato_separa_quien_gana():
    mezcla = HIST + [c(f"i{i}", "1", "I", "INTER SAS", tipo="INTERVENTORIA", ofer=6) for i in range(9)]
    todo = L.perfil_entidad(mezcla, "1", HOY)
    obra = L.perfil_entidad(mezcla, "1", HOY, tipo="OBRA")
    assert todo["ganadores"][0]["doc"] == "I" and obra["ganadores"][0]["doc"] == "A"
    top = L.competidores_probables(mezcla, {"nit_entidad": "1", "departamento": "SANTANDER", "familia": "7214", "tipo_contrato": "OBRA"}, HOY)
    assert "I" not in {x["doc"] for x in top}


def test_hhi_cuadra_con_las_shares():
    p = L.perfil_entidad(HIST, "1", HOY)
    assert p["hhi"] == pytest.approx(0.75 ** 2 + 0.25 ** 2)


# --------------------------------------------------------- competidor
def test_competidor_saturado_por_saldo_pendiente():
    p = L.perfil_competidor(HIST, "B", HOY)
    assert p["n_en_ejecucion"] == 2 and p["saldo_pendiente"] == 4000e6
    assert p["nivel_saturacion"] in ("cargado", "saturado")
    assert p["mediana_ratio"] == pytest.approx(0.94)   # [0.93, 0.93, 0.95, 0.95] -> 0.94

def test_competidor_con_capacidad_y_contrato_vencido_no_cuenta():
    p = L.perfil_competidor(HIST, "A", HOY)
    assert p["n_en_ejecucion"] == 0                # v1 tiene fecha_fin vencida
    assert p["nivel_saturacion"] == "con_capacidad"
    assert p["n_contratos"] == 7 and p["entidades"][0]["nit"] == "1"


def test_en_ejecucion_usa_estado_si_no_hay_fecha():
    assert L.en_ejecucion({"estado": "EN EJECUCION", "fecha_fin": None}, HOY)
    assert not L.en_ejecucion({"estado": "TERMINADO", "fecha_fin": "2030-01-01"}, HOY)
    assert L.en_ejecucion({"estado": "MODIFICADO", "fecha_fin": "2027-01-01"}, HOY)


# ------------------------------------------- competidores probables
def test_competidores_probables_prioriza_la_entidad_y_castiga_saturacion():
    proceso = {"nit_entidad": "1", "departamento": "SANTANDER", "familia": "7214"}
    top = L.competidores_probables(HIST, proceso, HOY, n=5)
    assert top[0]["doc"] == "A" and top[0]["razones"]["entidad"] == 6
    b = next(x for x in top if x["doc"] == "B")
    assert b["razones"]["entidad"] == 2 and b["razones"]["departamento_familia"] == 1
    assert b["puntos"] < b["puntos_brutos"]           # saturacion resta
    assert sum(x["peso"] for x in top) == pytest.approx(1.0)
    assert "D" not in {x["doc"] for x in top}         # la directa no cuenta


def test_competidores_probables_en_entidad_nueva_usa_departamento_y_familia():
    proceso = {"nit_entidad": "nueva", "departamento": "SANTANDER", "familia": "7214"}
    top = L.competidores_probables(HIST, proceso, HOY, n=3)
    assert top and all(x["razones"].get("entidad") is None for x in top)
    assert top[0]["doc"] == "A"


def test_contratos_viejos_pesan_la_mitad():
    viejo = [c("o1", "9", "V", "VIEJO", anio=2018), c("o2", "9", "N", "NUEVO", anio=2026)]
    top = L.competidores_probables(viejo, {"nit_entidad": "9", "departamento": "X", "familia": "7214"}, HOY)
    pv = next(x for x in top if x["doc"] == "V")["puntos_brutos"]
    pn = next(x for x in top if x["doc"] == "N")["puntos_brutos"]
    assert pn == 2 * pv


def test_sin_historico_devuelve_vacio():
    assert L.competidores_probables(HIST, {"nit_entidad": "z", "departamento": "z", "familia": "0000"}, HOY) == []


# ------------------------------------------------------------ humo
def test_fixtures_reales():
    from pliego.radar import datos
    top = datos.entidades_mas_activas(5)
    assert len(top) == 5
    p = datos.entidad(top[0]["nit"])
    assert p and p["etiqueta"] in ("predecible", "abierta", "intermedia", "sin_muestra")
    ab = datos.abiertos()[0]
    comp = datos.competidores_de(ab["id_del_proceso"])
    assert isinstance(comp, list)
    if comp:
        assert datos.competidor(comp[0]["doc"])["n_contratos"] >= 1
