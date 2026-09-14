# Plataforma Pliego (cuentas reales + enfoques sobre Croma), puerto 8100.
# Dependencias desde uv.lock (reproducible); el codigo corre desde /app.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
# poppler: pdftotext/pdftoppm para la trazabilidad del pliego (checklist).
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# Solo las dependencias (sin el proyecto), para que la capa se cachee.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --extra plataforma
COPY pliego/ ./pliego/
COPY plataforma/ ./plataforma/
# Usuario sin privilegios: poppler parsea PDFs que sube cualquier usuario
# registrado, y un fallo ahi no debe caer como root sobre el disco de datos.
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/data && chown -R app:app /app
USER app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8100
# --proxy-headers solo para proxies de red privada (el de Render lo es): la
# IP real es la primera publica desde la derecha de X-Forwarded-For.
CMD ["sh", "-c", "python -m plataforma.migrar && python -m uvicorn plataforma.app:app --host 0.0.0.0 --port ${PORT:-8100} --workers 1 --proxy-headers --forwarded-allow-ips='127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16'"]
