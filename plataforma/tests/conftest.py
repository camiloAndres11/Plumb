"""Las pruebas de la plataforma nunca tocan la red ni el warehouse real:
sin llave de Croma no arrancan los trabajos, y el warehouse va a un
archivo temporal. Postgres si es real (DATABASE_URL del .env) porque el
esquema es lo que se prueba."""
import pytest


@pytest.fixture(autouse=True)
def _aislado(tmp_path, monkeypatch):
    from pliego.comun import warehouse
    warehouse.cerrar()
    monkeypatch.delenv("CROMA_API_KEY", raising=False)
    monkeypatch.setenv("PLIEGO_WAREHOUSE", str(tmp_path / "wh.duckdb"))
    monkeypatch.setenv("PLATAFORMA_DATOS", str(tmp_path))
    yield
    warehouse.cerrar()
