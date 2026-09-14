# Pliego

<img src="./project-logo.png" alt="Pliego" width="160" />

**Herramienta comercial para constructoras que licitan obra pública en Colombia.**
Le dice a una empresa a qué procesos del SECOP presentarse, con qué precio, contra
quién compite, qué le falta para quedar habilitada y le arma la propuesta.

Nació como **Plomada** (Platanus Hack 26, detección de riesgo en contratación de
obra pública) y pivotó a producto en septiembre de 2026. La metodología, el pipeline
y la API de Plomada siguen en el repo y documentados en [`docs/PLOMADA.md`](docs/PLOMADA.md).

> Las recomendaciones son estimaciones sobre datos públicos; no garantizan un
> resultado. Riesgo no es fraude.

---

## Qué hay en el repo

Tres capas, de la más vieja a la más nueva:

| Capa | Carpeta | Qué es | Puerto |
|---|---|---|---|
| **Plomada** | `pipeline/`, `sql/`, `api/`, `plomada/` | Ingesta de SECOP II a un warehouse DuckDB, banderas de riesgo, API REST + MCP y sitio estático. En producción en Render/Vercel. | `api/` en 8000 (Docker) |
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
`app.py` (HTML + JSON) y `fixtures/`. Índice en [`docs/enfoques/README.md`](docs/enfoques/README.md).

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
docker compose up -d db                  # Postgres en 127.0.0.1:5432
python -m plataforma.migrar              # esquema `pliego`
uvicorn plataforma.app:app --port 8100
```
Registro en `http://127.0.0.1:8100/registro`. Sin `SMTP_URL` los correos de
verificación salen por el log. Guía completa en
[`docs/enfoques/plataforma.md`](docs/enfoques/plataforma.md).

**Plomada (pipeline + API):** ver [`docs/PLOMADA.md`](docs/PLOMADA.md),
[`API.md`](API.md) y [`MCP.md`](MCP.md).

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

Todas documentadas en `.env.example`.

## Flujo de trabajo

`main` (producción, no se toca) ← `dev` (integración, solo por PR) ← rama personal
(`rarechimera87`, `andres_nino`, …) ← `feature/<nombre>` (nace y muere en la
personal, merge `--no-ff`). Detalle en [`docs/agents/flujo-ramas.md`](docs/agents/flujo-ramas.md).

Issues en GitHub Issues de `camiloAndres11/Plumb` (ver `docs/agents/`).

## Mapa del repo

```
pipeline/  sql/  api/  plomada/   Plomada: ingesta, warehouse, API + MCP, sitio (docs/PLOMADA.md)
pliego/
  comun/     web (shell HTML), fuente (fixtures | croma | warehouse), croma, mapeo_croma,
             warehouse, cache, contexto, prefijo, panel
  filtro/  checklist/  simulador/  radar/  generador/   los enfoques
  tests/
demo/        la demo integrada (puerto 8000)
plataforma/  cuentas, perfil, trabajos, enfoques montados, pliegos, admin (puerto 8100)
docs/
  enfoques/  ENFOQUE.md por enfoque, croma.md, plataforma.md
  agents/    instrucciones para agentes (issues, etiquetas, dominio, flujo de ramas)
  PLOMADA.md el README original: metodología, banderas, decisiones
data/        no versionado: warehouse, caché de Croma, PDFs (data/cache, data/warehouse)
render.yaml  Render: plomada-db, plomada-api, plomada-sitio, pliego-app (con disco)
```

## Estado (septiembre de 2026)

- Enfoques y demo: hechos; corren sobre fixtures o sobre Croma.
- Plataforma: seis fases hechas (cuentas, perfil, datos por departamento, enfoques
  con sesión, pliegos con Claude, admin y Render). Pendiente: probar la extracción
  real con `ANTHROPIC_API_KEY`, revisión legal de términos y privacidad, y desplegar.
- Plomada: en producción (`plumb-duy6.onrender.com`, `plomada-xi.vercel.app`).

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
