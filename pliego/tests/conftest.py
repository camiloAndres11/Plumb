"""Las pruebas corren SIEMPRE sobre los fixtures, aunque el .env de la raiz
pida Croma: sin red, sin creditos, sin depender de que la API responda.
Las pruebas que quieren el modo Croma lo activan ellas con monkeypatch."""
import pytest


@pytest.fixture(autouse=True)
def _sin_croma(monkeypatch):
    monkeypatch.delenv("PLIEGO_FUENTE", raising=False)
    monkeypatch.delenv("CROMA_API_KEY", raising=False)
