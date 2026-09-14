# ADR 0004 · Un `pyproject.toml`, `uv.lock` y Python 3.12 para todo el repo

Fecha: 2026-09-14. Rama: `feature/pyproject-ci`.

## Contexto

Cinco `requirements*.txt` con rangos y sin lock, cinco versiones de Python
declaradas (3.9 en comentarios y en un pin de networkx, 3.11 en CI y Docker,
3.12 en un Dockerfile, "3.12+" en el README, 3.14 en un venv local), cuatro
`sys.path.insert` en tests, y un CI que ejecutaba 88 de 227 tests y pasaba
`ruff` por el 24 % del código.

## Decisión

- Un `pyproject.toml` en la raíz: proyecto `pliego` (paquetes `pliego`,
  `plataforma`, `demo`) con extras `plataforma`, `legacy` (Plomada) y
  `dev`. `uv.lock` deja la instalación reproducible; `uv sync` es la forma
  canónica de instalar y `pip install -e ".[plataforma,dev]"` la alterna.
- Python **3.12** en Dockerfiles, Render y CI. `requires-python = ">=3.12"`.
- `pytest` y `ruff` se configuran ahí: `testpaths` con las cuatro suites,
  `pythonpath` para los imports planos del legado (sin hacks en tests),
  ruff sobre todo el repo con `I`, `UP` y `B` (el legado con el mínimo).
- CI en tres jobs: `pliego` (lint de todo + tests de pliego y plataforma
  con un Postgres de servicio), `legacy` (los pasos de Plomada de siempre)
  y `auditoria` (`pip-audit` sobre el lock, `npm audit`).
- Los Dockerfiles del legado conservan sus `requirements.txt`; el de la
  plataforma instala desde el lock con `uv sync --frozen --no-install-project`.

## Consecuencias

- Toda la suite corre en cada push; ninguna regresión en auth, CSRF o
  multi-tenencia pasa sin ruido.
- Añadir una dependencia es editar `pyproject.toml` y correr `uv lock`.
