# Plumb

## Agent skills

### Issue tracker

Issues en GitHub Issues de `camiloAndres11/Plumb`, via el CLI `gh`.
See `docs/agents/issue-tracker.md`.

### Triage labels

Las cinco etiquetas canonicas, sin renombrar. See `docs/agents/triage-labels.md`.

### Domain docs

Contexto unico: `CONTEXT.md` (glosario) y `docs/adr/` (decisiones: legado, Jinja2, configuracion, uv) en la raiz. See `docs/agents/domain.md`.

### Flujo de ramas

`main` intocable <- `dev` <- rama personal (`rarechimera87`) <- `feature/*`. See `docs/agents/flujo-ramas.md`.

### Plataforma

Pliego para empresas reales (cuentas, perfil, datos por empresa) en `plataforma/`, puerto 8100; la demo sigue en 8000. See `docs/enfoques/plataforma.md`.

### Legado

Plomada (producto anterior, en produccion) vive intacta en `legacy/plomada/` y no se refactoriza: solo arreglos de seguridad (ADR 0001). Su CI es el job `legacy`. Despliegue en `deploy/` (`compose.yaml` en la raiz lo incluye).

### Reglas del codigo

Configuracion solo en `pliego/comun/config.py` y `plataforma/config.py` (nada de `os.environ` fuera; `.env.example` se genera con `python -m pliego.comun.config --ejemplo`). HTML solo en `templates/` (Jinja2, autoescape) y JS solo en `/static` (CSP sin inline). `uv sync --extra plataforma --extra dev`, `python -m pytest`, `ruff check .`.
