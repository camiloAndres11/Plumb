"""Pruebas del mapeo de campos: de donde sale cada dato, que se calcula
como, que falta y en que orden, y que cada borrador dice lo que dicen sus
campos."""
from datetime import date

import pytest

from pliego.generador import logica as L
from pliego.generador import datos

HOY = date(2021, 7, 6)


@pytest.fixture
def ctx():
    return datos.pliego(), datos.perfil(), datos.lote(1)


def campo(doc, clave):
    return next(c for c in doc.campos if c.clave == clave)


# ---------------------------------------------------------- trazabilidad
def test_cada_campo_del_pliego_trae_su_pagina(ctx):
    pl, pf, lo = ctx
    for d in L.generar_todo(pl, pf, lo, HOY):
        for c in d.campos:
            if c.origen == L.PLIEGO:
                assert c.pagina and 1 <= c.pagina <= pl["paginas"], (d.id, c.clave)
                assert c.fuente.startswith("pliego.")
            if c.origen == L.PERFIL:
                assert c.fuente.startswith("perfil.")
            if c.origen == L.CALCULADO:
                assert c.fuente, (d.id, c.clave)   # la formula


def test_carta_mezcla_pliego_y_perfil(ctx):
    d = L.formato1(*ctx, HOY)
    assert campo(d, "entidad").origen == L.PLIEGO and campo(d, "entidad").pagina == 1
    assert campo(d, "rl_nombre").origen == L.PERFIL and campo(d, "rl_nombre").fuente == "perfil.representante_legal.nombre"
    assert campo(d, "lote.presupuesto").valor == 737_745_546 and campo(d, "lote.presupuesto").pagina == 5
    assert "Laura Milena Rueda Gómez" in d.texto and "SI-LP-004-2021" in d.texto and "Grupo 1" in d.texto
    assert d.estado == L.LISTO


def test_carta_no_pide_aval_si_el_rl_es_ingeniero_y_si_no_lo_es_lo_marca_faltante(ctx):
    pl, pf, lo = ctx
    d = L.formato1(pl, pf, lo, HOY)
    assert campo(d, "aval").origen == L.CALCULADO and "No requiere aval" in campo(d, "aval").valor
    pf2 = {**pf, "representante_legal": {**pf["representante_legal"], "profesion": "Administradora"}, "avalador": None}
    d2 = L.formato1(pl, pf2, lo, HOY)
    assert campo(d2, "avalador").origen == L.FALTANTE and campo(d2, "avalador").critico
    assert d2.estado == L.CON_FALTANTES


def test_dato_de_perfil_ausente_queda_faltante_y_el_borrador_deja_el_hueco(ctx):
    pl, pf, lo = ctx
    pf2 = {**pf, "correo": None}
    d = L.formato1(pl, pf2, lo, HOY)
    assert campo(d, "correo").origen == L.FALTANTE
    assert "[CORREO]" in d.texto


# ------------------------------------------------------------ calculos
def test_garantia_calcula_valor_y_vigencia_desde_el_pliego(ctx):
    d = L.garantia(*ctx, HOY)
    assert campo(d, "valor_asegurado").valor == pytest.approx(0.10 * 737_745_546)
    assert campo(d, "valor_asegurado").origen == L.CALCULADO and campo(d, "valor_asegurado").critico
    assert campo(d, "garantia_beneficiario").pagina == 59
    assert campo(d, "poliza").origen == L.FALTANTE     # siempre: la expide un tercero
    assert d.estado == L.CON_FALTANTES


def test_experiencia_elige_contratos_terminados_de_las_actividades_hasta_cumplir(ctx):
    pl, pf, lo = ctx
    d = L.formato3(pl, pf, lo, HOY)
    assert campo(d, "elegidos").valor == [9]           # 640 SMMLV ≥ 75 % de 812
    assert campo(d, "requerido_smmlv").valor == pytest.approx(0.75 * 737_745_546 / 908_526, rel=1e-3)
    assert d.estado == L.LISTO and "| 9 |" in d.texto
    d3 = L.formato3(pl, pf, datos.lote(3), HOY)         # 1.776 SMMLV solo edificaciones: no alcanza
    assert campo(d3, "brecha").origen == L.FALTANTE and d3.estado == L.CON_FALTANTES
    assert 12 not in campo(d3, "elegidos").valor         # vias no cuenta


def test_capacidad_residual_resta_anticipo_y_calcula_sce_lineal(ctx):
    d = L.formato5(*ctx, HOY)
    assert campo(d, "crpc").valor == pytest.approx(737_745_546 * 0.5)
    # los dias pendientes se acotan al plazo: el SCE nunca supera el valor del contrato
    assert campo(d, "sce").origen == L.CALCULADO
    assert campo(d, "sce").valor <= 1_558e6 + 980e6
    assert campo(d, "sce").valor == pytest.approx(1_558e6 + 980e6)   # al cierre (2021) ninguno ha arrancado
    assert campo(d, "habil").valor is True and d.estado == L.LISTO


def test_formato4_calcula_los_indicadores_desde_los_estados(ctx):
    d = L.formato4(*ctx, HOY)
    assert campo(d, "liquidez").valor == pytest.approx(3100 / 1720, abs=0.01)
    assert campo(d, "endeudamiento").valor == pytest.approx(3900 / 7100, abs=0.001)
    assert campo(d, "ctd").valor == pytest.approx(73_774_554.6)
    assert campo(d, "ac").origen == L.PERFIL


# ------------------------------------------------------- estados y faltas
def test_formato2_no_aplica_a_proponente_individual(ctx):
    d = L.formato2(*ctx, HOY)
    assert d.estado == L.NO_APLICA and "individual" in d.texto


def test_formatos_de_puntaje_marcan_lo_que_el_generador_no_puede_redactar(ctx):
    d7 = L.formato7(*ctx, HOY)
    d8 = L.formato8(*ctx, HOY)
    assert campo(d7, "plan").origen == L.FALTANTE and not campo(d7, "plan").critico
    assert campo(d8, "certificado").origen == L.FALTANTE and d8.estado == L.CON_FALTANTES


def test_lo_que_falta_va_ordenado_criticos_primero(ctx):
    docs = L.generar_todo(*ctx, HOY)
    falta = L.lo_que_falta(docs)
    assert falta and falta[0]["critico"] is True
    criticos = [f["critico"] for f in falta]
    assert criticos == sorted(criticos, reverse=True)
    assert any(f["campo"] == "poliza" for f in falta)


def test_resumen_cuenta_estados_y_origenes(ctx):
    docs = L.generar_todo(*ctx, HOY)
    r = L.resumen(docs)
    assert r["total"] == 11 and sum(r["conteo"].values()) == 11
    assert r["origenes"][L.PLIEGO] > 0 and r["origenes"][L.PERFIL] > 0 and r["origenes"][L.CALCULADO] > 0
    assert r["conteo"][L.NO_APLICA] == 1


def test_paquete_por_lote_desde_fixtures():
    p = datos.paquete(2)
    assert p["lote"]["n"] == 2 and len(p["documentos"]) == 11
    g = next(d for d in p["documentos"] if d["id"] == "garantia")
    assert next(c for c in g["campos"] if c["clave"] == "valor_asegurado")["valor"] == pytest.approx(0.10 * 929_890_150)
    with pytest.raises(KeyError):
        datos.documentos(9)
