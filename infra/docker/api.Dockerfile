FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
ARG TARGETARCH
COPY pyproject.toml ./
COPY scripts ./scripts
COPY agent ./agent
COPY rag ./rag
COPY dataprep ./dataprep
COPY mcp_servers ./mcp_servers
COPY apps ./apps
COPY worker ./worker
COPY data ./data
RUN pip install --upgrade pip && pip install -e ".[postgres]"
RUN python -m scripts.install_github_mcp --architecture "$TARGETARCH" \
    --destination /usr/local/bin/github-mcp-server \
    --metadata /usr/local/share/github-mcp/runtime.json
ENV GITHUB_MCP_BINARY=/usr/local/bin/github-mcp-server
RUN useradd -m app && mkdir -p /data && chown -R app /app && chown app:app /data
USER app
CMD ["uvicorn","apps.api.main:create_app","--factory","--host","0.0.0.0","--port","8000"]
