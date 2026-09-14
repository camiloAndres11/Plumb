# Plomada (legado). Correr desde legacy/plomada/. Los comandos son one-liners
# a proposito: si no tienes make, copia la linea de la receta.
.PHONY: help ingest build graph test test-api load api up down lint front sitio
help:
	@grep -E '^[a-z-]+:.*?##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/'

ingest:   ## Descarga el universo de obra publica del SECOP II (~4 min)
	python pipeline/ingest.py

build:    ## Warehouse + publica data/exports/base.parquet (~20 s)
	python pipeline/build.py

graph:    ## Solo el grafo (pasos 04-09), sin recalcular el nucleo
	python pipeline/build.py --steps 04 05 --no-export
	python pipeline/grafo.py

all:      ## Todos los pasos SQL en orden
	python pipeline/build.py --all

valores:  ## Tipo de obra + la cifra en pesos (pasos 10-11)
	python pipeline/build.py --steps 10 11 --no-export

abiertos: ## Snapshot de hoy de licitaciones abiertas (~1 min)
	python pipeline/ingest_abiertos.py

alertas:  ## Banderas pre-adjudicacion (requiere build + abiertos)
	python pipeline/alertas.py

web:      ## Exporta los JSON del tablero a out_web/
	python pipeline/export_web.py

test:     ## Puertas de calidad de datos (fallan el PR)
	python -m pytest tests/ -v

lint:
	ruff check .

load:     ## Carga las tablas api_* del warehouse a Postgres
	python pipeline/load_postgres.py

api:      ## Sirve la API publica en http://localhost:8000/docs (necesita DATABASE_URL)
	uvicorn app.main:app --app-dir api --reload

test-api: ## Contrato del API (no necesita Postgres); deps: uv sync --extra legacy --extra dev
	python -m pytest api/tests/ -v

front:    ## Compila las islas de Vue (docs/PLAN_VUE.md). Solo hace falta si tocaste frontend/
	npm --prefix frontend install
	npm --prefix frontend run build

sitio:    ## Compone el CSS y genera plomada/site/ (no hace falta Node: el bundle ya esta commiteado)
	python3 design/construir.py
	python3 plomada/build.py

up:
	cd ../.. && docker compose up --build

down:
	cd ../.. && docker compose down
