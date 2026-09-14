# Pipeline analitico. Python 3.12, el mismo de todo el repo (pyproject.toml).
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

FROM base AS deps
COPY pipeline/requirements.txt ./pipeline/requirements.txt
RUN pip install -r pipeline/requirements.txt

FROM deps AS final
COPY pipeline/ ./pipeline/
COPY sql/ ./sql/
COPY tests/ ./tests/
# data/ se monta como volumen: los JSONL crudos pesan ~740 MB y no van en la imagen
VOLUME ["/app/data"]
CMD ["python", "pipeline/build.py"]
