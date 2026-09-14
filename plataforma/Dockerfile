# Plataforma Pliego (cuentas reales + enfoques sobre Croma), puerto 8100.
# Copia de api/Dockerfile: mismas notas sobre --proxy-headers en Render.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
# poppler: pdftotext/pdftoppm para la trazabilidad del pliego (checklist).
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY plataforma/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt
COPY pliego/ ./pliego/
COPY plomada/landing.html plomada/static/ ./plomada/
COPY plataforma/ ./plataforma/
# Usuario sin privilegios: poppler parsea PDFs que sube cualquier usuario
# registrado, y un fallo ahi no debe caer como root sobre el disco de datos.
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/data && chown -R app:app /app
USER app
EXPOSE 8100
CMD ["sh", "-c", "python -m plataforma.migrar && uvicorn plataforma.app:app --host 0.0.0.0 --port ${PORT:-8100} --workers 1 --proxy-headers --forwarded-allow-ips='127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16'"]
