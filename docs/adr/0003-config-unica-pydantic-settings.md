# ADR 0003 · Una sola configuración viva y cero `os.environ` fuera de ella

Fecha: 2026-09-14. Rama: `feature/config-unica`.

## Contexto

Había 24 lecturas sueltas de `os.environ` fuera de un `config.py`; nueve
variables de `pliego/comun` no tenían configuración; `plataforma/app.py`
**escribía** `os.environ["PLIEGO_FUENTE"]` al importarse; y
`pliego/comun/entorno.py` cargaba el `.env` como efecto secundario de un
import. Las pruebas cambiaban variables de entorno y dependían del orden.

## Decisión

- `pliego/comun/config.py`: un `BaseSettings` (pydantic-settings) con todo
  lo de pliego, que lee el `.env` de la raíz. `actual()` devuelve la
  instancia viva; `usar()` registra otra.
- `plataforma/config.py` **hereda** de esa clase, añade lo suyo y registra
  su instancia: en un proceso de la plataforma hay **una** configuración y
  los enfoques ven la misma. Fuerza `pliego_fuente = "warehouse"` con un
  validador, no escribiendo el entorno.
- Cada campo lleva `Field(description=...)`; `.env.example` se genera con
  `python -m pliego.comun.config --ejemplo` y no se edita a mano.
- Ningún módulo de `pliego/`, `plataforma/` o `demo/` lee `os.environ`
  salvo `config.py`; un test lo verifica. Las pruebas ajustan la
  configuración con `monkeypatch.setattr(config, ...)`.
- `pliego/comun/pg.py` es el único pool de Postgres; `plataforma/db.py` solo
  aporta DSN y mensajes.

## Consecuencias

- La configuración se lee una vez al arrancar: cambiar el `.env` exige
  reiniciar el proceso.
- `api/` (legado) conserva su propia `Config` y su `db.py`: no se toca.
