FROM python:alpine

LABEL org.opencontainers.image.source="https://github.com/molanojustin/smithsonian-mcp"
LABEL org.opencontainers.image.description="Smithsonian MCP Server - Model Context Protocol server for Smithsonian Open Access collections"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

RUN apk add --no-cache ca-certificates

COPY pyproject.toml uv.lock README.md ./
COPY smithsonian_mcp/ ./smithsonian_mcp/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "smithsonian_mcp.server"]
