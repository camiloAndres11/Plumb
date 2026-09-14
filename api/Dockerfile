FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY api/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt
COPY api/app/ ./app/
# Usuario sin privilegios (mismo criterio que plataforma/Dockerfile).
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app && chown -R app:app /app
USER app
EXPOSE 8000
# Render inyecta $PORT; en local cae a 8000
# --proxy-headers/--forwarded-allow-ips: Render termina TLS en su proxy y
# reenvia por HTTP plano con X-Forwarded-Proto: https. Sin esto, uvicorn no
# sabe que la conexion original fue HTTPS y genera redirects (ej. /mcp ->
# /mcp/) con esquema http://, que el cliente MCP no puede seguir bien.
# Solo se confia en proxies de red privada (el de Render lo es): uvicorn
# recorre X-Forwarded-For de derecha a izquierda saltando esos y se queda
# con la primera IP publica, asi que lo que el cliente ponga a la izquierda
# no cuenta. Con '*' cualquiera se inventaba la IP y saltaba el rate limit.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16'"]
