"""Metodos de ponderacion de la oferta economica, configurables por version
de los documentos tipo.

Las formulas cambian con cada version de los documentos tipo de Colombia
Compra Eficiente, y cada pliego puede ajustar rangos de TRM y puntaje
maximo. Por eso hay un registro VERSIONES: cada entrada dice que metodos
existen, con que formula, que rango de centavos de la TRM los activa y
cuanto vale el maximo. La logica de simulacion no sabe nada de formulas:
recibe una Version y la usa.

La version `bucaramanga_2021` esta transcrita del pliego real SI-LP-004-2021
(Municipio de Bucaramanga, seccion 4.1.4, paginas 46-49), el mismo que usa
la rama feature/checklist-habilitantes.
"""
from __future__ import annotations

import math
import statistics
from collections.abc import Callable
from dataclasses import dataclass

# Cada formula recibe (valores de todas las ofertas habiles, valor de la
# oferta que se califica, puntaje maximo) y devuelve el puntaje. Trabajan
# con valores en cualquier unidad (pesos o fraccion del presupuesto): son
# homogeneas de grado 0.
Formula = Callable[[list[float], float, float], float]


def _clip(x: float) -> float:
    return max(0.0, x)


def mediana_valor_absoluto(vals: list[float], v: float, maximo: float) -> float:
    """Impar: maximo a la oferta en la mediana, las demas 1 - |Me - Vi|/Me.
    Par: maximo a la inmediatamente por debajo de la mediana (VMe), las
    demas contra VMe. (SI-LP-004-2021, p. 47-48)"""
    orden = sorted(vals)
    n = len(orden)
    if n % 2 == 1:
        ref = orden[n // 2]
    else:
        # "inmediatamente por debajo de la mediana": el mayor de los dos centrales? No:
        # la mediana es el promedio de los centrales; el valor por debajo es orden[n//2 - 1].
        ref = orden[n // 2 - 1]
    if math.isclose(v, ref, rel_tol=1e-9):
        return maximo
    return _clip((1 - abs(ref - v) / ref) * maximo)


def media_geometrica(vals: list[float], v: float, maximo: float) -> float:
    """Maximo a la mas cercana a la media geometrica; las demas
    maximo * (1 - |MG - Vi|/MG). (p. 48)"""
    mg = statistics.geometric_mean(vals)
    mas_cerca = min(vals, key=lambda x: abs(x - mg))
    if math.isclose(v, mas_cerca, rel_tol=1e-9):
        return maximo
    return _clip(maximo * (1 - abs(mg - v) / mg))


def media_aritmetica_baja(vals: list[float], v: float, maximo: float) -> float:
    """XB = (Vmin + promedio) / 2; puntaje = maximo * (1 - |XB - Vi|/XB). (p. 48-49)
    En este pliego las dos ramas (<= XB y > XB) tienen la misma formula; otras
    versiones castigan mas a un lado: por eso es una formula aparte."""
    xb = (min(vals) + statistics.fmean(vals)) / 2
    return _clip(maximo * (1 - abs(xb - v) / xb))


def menor_valor(vals: list[float], v: float, maximo: float) -> float:
    """maximo * Vmin / Vi. (p. 49)"""
    return _clip(maximo * min(vals) / v)


@dataclass(frozen=True)
class Metodo:
    clave: str
    nombre: str
    formula: Formula
    centavos_desde: int   # rango inclusive de los centavos de la TRM (0-99)
    centavos_hasta: int

    @property
    def probabilidad(self) -> float:
        """Los centavos de la TRM son, a efectos practicos, uniformes: la
        probabilidad de cada metodo es el ancho de su rango sobre 100."""
        return (self.centavos_hasta - self.centavos_desde + 1) / 100


@dataclass(frozen=True)
class Version:
    clave: str
    nombre: str
    fuente: str
    puntaje_maximo: float
    metodos: tuple[Metodo, ...]
    # Algunas versiones meten el presupuesto oficial como una oferta mas al
    # calcular la media geometrica; esta no. Se deja como bandera por version.
    incluye_presupuesto_en_media: bool = False

    def por_centavos(self, centavos: int) -> Metodo:
        for m in self.metodos:
            if m.centavos_desde <= centavos <= m.centavos_hasta:
                return m
        raise ValueError("centavos fuera de rango: %s" % centavos)

    def puntaje(self, metodo: Metodo, vals: list[float], v: float) -> float:
        return metodo.formula(vals, v, self.puntaje_maximo)


VERSIONES: dict[str, Version] = {
    "bucaramanga_2021": Version(
        clave="bucaramanga_2021",
        nombre="Documentos tipo obra pública · pliego SI-LP-004-2021",
        fuente="Municipio de Bucaramanga, SI-LP-004-2021, sección 4.1.4 (p. 46-49)",
        puntaje_maximo=60,
        metodos=(
            Metodo("mediana", "Mediana con valor absoluto", mediana_valor_absoluto, 0, 24),
            Metodo("geometrica", "Media geométrica", media_geometrica, 25, 49),
            Metodo("aritmetica_baja", "Media aritmética baja", media_aritmetica_baja, 50, 74),
            Metodo("menor_valor", "Menor valor", menor_valor, 75, 99),
        ),
    ),
}
VERSION_DEFECTO = "bucaramanga_2021"
