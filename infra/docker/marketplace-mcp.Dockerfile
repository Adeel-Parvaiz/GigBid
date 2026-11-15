FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY pyproject.toml ./
COPY agent ./agent
COPY rag ./rag
COPY dataprep ./dataprep
COPY mcp_servers ./mcp_servers
COPY apps ./apps
COPY worker ./worker
COPY config ./config
COPY data ./data
RUN pip install --upgrade pip && pip install -e ".[postgres]"
RUN useradd -m app && mkdir -p /data && chown -R app /app && chown app:app /data
USER app
CMD ["python","-m","mcp_servers.marketplace.server"]
