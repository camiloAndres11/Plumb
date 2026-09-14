# Pliego

<img src="./plataforma/static/logo.png" alt="Pliego" width="120" />

**Herramienta comercial para constructoras que licitan obra pública en Colombia.**
Le dice a una empresa a qué procesos del SECOP presentarse, con qué precio, contra
quién compite, qué le falta para quedar habilitada y le arma la propuesta.

Nació como **Plomada** (Platanus Hack 26, detección de riesgo en contratación de
obra pública) y pivotó a producto en septiembre de 2026. Plomada sigue en producción,
aislada en [`legacy/plomada/`](legacy/plomada/README.md).

> Las recomendaciones son estimaciones sobre datos públicos; no garantizan un
> resultado. Riesgo no es fraude.

---

## Qué hay en el repo

Tres capas, de la más vieja a la más nueva:

| Capa | Carpeta | Qué es | Puerto |
|---|---|---|---|
| **Plomada** (legado) | `legacy/plomada/` | Ingesta de SECOP II a un warehouse DuckDB, banderas de riesgo, API REST + MCP y sitio estático. En producción en Render; no se refactoriza. | `api/` en 8000 (Docker) |
| **Pliego, los enfoques** | `pliego/`, `demo/` | Cinco prototipos de producto y una demo que los integra tras la landing. Perfil de constructora ficticio. | `demo/` en **8000** |
| **Pliego, la plataforma** | `plataforma/` | La versión para empresas reales: cuentas, perfil, datos por departamento, pliegos con Claude, admin. | **8100** |

Los datos de SECOP para los enfoques llegan de **[Croma](https://usecroma.com)**, un
proveedor de datos públicos con SECOP I y II como dataset (`pliego/comun/croma.py`).
Ver [`docs/enfoques/croma.md`](docs/enfoques/croma.md).

## Los cinco enfoques

| Enfoque | Promesa | Datos |
|---|---|---|
| [Filtro de procesos](docs/enfoques/filtro-de-procesos/ENFOQUE.md) | Deje de presentarse a licitaciones que no puede ganar. | procesos abiertos + historial de cada entidad |
| [Checklist del pliego](docs/enfoques/checklist-habilitantes/ENFOQUE.md) | No vuelva a quedar por fuera por un papel. | el pliego (PDF) + la carpeta de la empresa |
| [Simulador de oferta](docs/enfoques/simulador-oferta/ENFOQUE.md) | Oferte al precio que maximiza su puntaje, no al más bajo. | adjudicaciones históricas |
| [Radar de competidores](docs/enfoques/radar-competidores/ENFOQUE.md) | Sepa contra quién compite antes de presentarse. | contratos por proveedor y entidad |
| [Generador de propuesta](docs/enfoques/generador-propuesta/ENFOQUE.md) | Prepare la propuesta en horas, no en días. | el pliego + el perfil |

Cada enfoque es una app FastAPI independiente en `pliego/<enfoque>/` con la misma
estructura: `datos.py` (única capa con IO), `logica.py` (funciones puras),
`app.py` (rutas JSON y HTML), `templates/` (Jinja2 con autoescape) y `fixtures/`. Índice en [`docs/enfoques/README.md`](docs/enfoques/README.md).

## Correr

Requisitos: Python 3.12+, [uv](https://docs.astral.sh/uv/) y `poppler-utils` para el
checklist. `uv sync --extra plataforma --extra dev` instala todo desde `uv.lock`
(sin uv: `pip install -e ".[plataforma,dev]"`). Variables en `.env` (copiar de `.env.example`; nunca se commitea).

**Demo (vitrina, perfil ficticio):**
```bash
uvicorn demo.app:app --port 8000
```
Sin variables corre sobre los fixtures commiteados. Con `PLIEGO_FUENTE=croma` y
`CROMA_API_KEY` corre sobre los datos de hoy (la primera vez tarda minutos y se
cachea en `data/cache/croma/`).

**Plataforma (empresas reales):**
```bash
docker compose up -d db                  # Postgres en 127.0.0.1:5432 (pide POSTGRES_PASSWORD y SECRET_KEY en .env)
python -m plataforma.migrar              # esquema `pliego`
uvicorn plataforma.app:app --port 8100
```
Registro en `http://127.0.0.1:8100/registro`. Sin `SMTP_URL` los correos de
verificación salen por el log. Guía completa en
[`docs/enfoques/plataforma.md`](docs/enfoques/plataforma.md).

**Plomada (legado, pipeline + API):** ver [`legacy/plomada/README.md`](legacy/plomada/README.md),
[`API.md`](legacy/plomada/API.md) y [`MCP.md`](legacy/plomada/MCP.md).

**Pruebas y lint:**
```bash
python -m pytest        # todo (pyproject.toml): enfoques sobre fixtures, plataforma contra Postgres, legado
ruff check .
```

## Variables de entorno

| Variable | Para qué |
|---|---|
| `PLIEGO_FUENTE` | `croma` (demo con datos de hoy) o vacío (fixtures); la plataforma fija `warehouse` |
| `CROMA_API_KEY` | llave de organización de Croma |
| `DATABASE_URL`, `SECRET_KEY`, `BASE_URL`, `SMTP_URL`, `PLATAFORMA_ADMINS`, `PLATAFORMA_DATOS` | la plataforma |
| `ANTHROPIC_API_KEY` | extracción de pliegos con Claude |

Todas documentadas en `.env.example` y definidas en `pliego/comun/config.py` (base) y
`plataforma/config.py` (lo de la plataforma). Se leen una sola vez al arrancar.

## Flujo de trabajo

`main` (producción, no se toca) ← `dev` (integración, solo por PR) ← rama personal
(`rarechimera87`, `andres_nino`, …) ← `feature/<nombre>` (nace y muere en la
personal, merge `--no-ff`). Detalle en [`docs/agents/flujo-ramas.md`](docs/agents/flujo-ramas.md).

Issues en GitHub Issues de `camiloAndres11/Plumb` (ver `docs/agents/`).

## Mapa del repo

```
pyproject.toml  uv.lock   un proyecto (pliego, plataforma, demo); extras plataforma, legacy, dev
pliego/
  comun/     web (Jinja2: plantillas, filtros, base.html), config, fuente (fixtures | croma | warehouse),
             croma, mapeo_croma, warehouse, cache, contexto, pg, panel
  filtro/  checklist/  simulador/  radar/  generador/   los enfoques (app.py + templates/ + datos.py + logica.py)
  static/    base.css, fuentes y el css/js de cada enfoque
  tests/
demo/        la demo integrada (puerto 8000)
plataforma/  cuentas, perfil, trabajos, enfoques montados, pliegos, admin (puerto 8100)
  static/    landing.html, landing.css, fuentes, favicon, logo
deploy/      docker-compose.yml (se usa via compose.yaml de la raiz) y render.yaml
legacy/plomada/   Plomada, el producto anterior, en produccion y sin refactorizar:
             pipeline/ sql/ api/ plomada/ frontend/ design/ tests/ (ver su README.md)
docs/
  enfoques/  ENFOQUE.md por enfoque, croma.md, plataforma.md
  agents/    instrucciones para agentes (issues, etiquetas, dominio, flujo de ramas)
data/        no versionado: warehouse de Pliego, cache de Croma, PDFs
```

## Estado (septiembre de 2026)

- Enfoques y demo: hechos; corren sobre fixtures o sobre Croma.
- Plataforma: seis fases hechas (cuentas, perfil, datos por departamento, enfoques
  con sesión, pliegos con Claude, admin y Render). Pendiente: probar la extracción
  real con `ANTHROPIC_API_KEY`, revisión legal de términos y privacidad, y desplegar.
- Plomada: en producción en Render (`plumb-duy6.onrender.com`), aislada en `legacy/plomada/`.

## Fuentes

- SECOP II – Contratos (`jbjy-vk9h`) y Procesos (`p6dx-8zbt`) en datos.gov.co, para Plomada.
- Croma (`api.croma.run`): SECOP I y II como dataset, para Pliego.

## Licencia

Código y metodología abiertos. Los datos son públicos y de propiedad del Estado
colombiano.

## Equipo — team-15

- Andres Alejandro Niño Araujo ([@anothercoolcoder](https://github.com/anothercoolcoder))
- Santiago Reina Diaz ([@rarechimera87](https://github.com/rarechimera87))
- Jose Luis Salamanca Lopez ([@joseslk](https://github.com/joseslk))
- Camilo Andres Niño Amaya ([@camiloAndres11](https://github.com/camiloAndres11))
- Diego Andrés Combariza Puerto ([@diegocombariza11](https://github.com/diegocombariza11))
