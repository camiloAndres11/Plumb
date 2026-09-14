"""Las pruebas de la plataforma nunca tocan la red ni el warehouse real:
sin llave de Croma no arrancan los trabajos, y el warehouse va a un
archivo temporal. Postgres si es real (DATABASE_URL del .env) porque el
esquema es lo que se prueba. Todo se ajusta sobre la configuracion viva,
no sobre el entorno."""
import pytest

from plataforma.config import config


@pytest.fixture(autouse=True)
def _aislado(tmp_path, monkeypatch):
    from pliego.comun import warehouse
    warehouse.cerrar()
    monkeypatch.setattr(config, "croma_api_key", "")
    monkeypatch.setattr(config, "pliego_warehouse", tmp_path / "wh.duckdb")
    monkeypatch.setattr(config, "plataforma_datos", tmp_path)
    yield
    warehouse.cerrar()
