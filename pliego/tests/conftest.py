"""Las pruebas corren SIEMPRE sobre los fixtures, aunque el .env de la raiz
pida Croma: sin red, sin creditos, sin depender de que la API responda.
Las pruebas que quieren el modo Croma lo activan ellas con monkeypatch
sobre la configuracion (nunca sobre el entorno: config se lee una vez)."""
import pytest

from pliego.comun import config as CFG


@pytest.fixture(autouse=True)
def _sin_croma(monkeypatch, tmp_path):
    monkeypatch.setattr(CFG.actual(), "pliego_fuente", "")
    monkeypatch.setattr(CFG.actual(), "croma_api_key", "")
    monkeypatch.setattr(CFG.actual(), "plataforma_datos", tmp_path)   # la cache de Croma, fuera del repo
