# Decisiones de arquitectura (ADR)

Una decisión por archivo, corta: contexto, decisión, consecuencias. Se
escriben cuando algo se decide, no antes. Numeradas en orden; una decisión
que se revierte no se borra: se añade otra que la reemplaza y se enlazan.

| # | Decisión |
|---|---|
| [0001](0001-plomada-como-legado.md) | Plomada queda aislada en `legacy/plomada/` y no se refactoriza |
| [0002](0002-jinja2-y-root-path.md) | HTML con Jinja2 (autoescape) y URLs con `root_path`, sin reescritura |
| [0003](0003-config-unica-pydantic-settings.md) | Una sola configuración viva (pydantic-settings) y cero `os.environ` fuera de ella |
| [0004](0004-uv-y-pyproject.md) | Un `pyproject.toml`, `uv.lock` y Python 3.12 para todo el repo |
