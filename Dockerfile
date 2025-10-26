FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/molanojustin/smithsonian-mcp"
LABEL org.opencontainers.image.description="Smithsonian MCP Server - Model Context Protocol server for Smithsonian Open Access collections"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
COPY smithsonian_mcp/ ./smithsonian_mcp/
COPY README.md ./

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "smithsonian_mcp.server"]
