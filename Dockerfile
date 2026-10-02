# syntax=docker/dockerfile:1

# Build stage: install the locked runtime dependencies and the package into
# /app/.venv with uv. Nothing from this stage except the virtual environment
# ends up in the final image.
FROM python:3.14.8-slim-trixie@sha256:89fb7d3da20043c370643435258bdd7ab755d326d359001d02988ed15ae5219e AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first, so this layer stays cached until uv.lock changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Then the package itself, installed as a regular (non-editable) wheel.
COPY README.md LICENSE.md ./
COPY smithsonian_mcp/ ./smithsonian_mcp/
RUN uv sync --frozen --no-dev --no-editable


# Runtime stage
FROM python:3.14.8-slim-trixie@sha256:89fb7d3da20043c370643435258bdd7ab755d326d359001d02988ed15ae5219e

LABEL org.opencontainers.image.source="https://github.com/molanojustin/smithsonian-mcp"
LABEL org.opencontainers.image.description="Smithsonian MCP Server - Model Context Protocol server for Smithsonian Open Access collections"
LABEL org.opencontainers.image.licenses="MIT"

RUN groupadd --system --gid 10001 smithsonian \
    && useradd --system --uid 10001 --gid smithsonian --create-home \
        --home-dir /home/smithsonian --shell /usr/sbin/nologin smithsonian

COPY --from=builder /app/.venv /app/.venv

# MCP_HOST and MCP_ALLOWED_HOSTS only apply in HTTP mode. Inside the container
# the server must listen on all interfaces for a published port to reach it, so
# requests are told apart by their Host header instead: only the names in
# MCP_ALLOWED_HOSTS are accepted, which blocks DNS rebinding from web pages.
# Add the names clients use to reach the container, comma-separated.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MCP_HOST=0.0.0.0 \
    MCP_ALLOWED_HOSTS=localhost,127.0.0.1,::1

WORKDIR /app
USER smithsonian

# By default the server speaks MCP over stdio, so run the container with -i:
#   docker run -i --rm -e SMITHSONIAN_API_KEY justinmol/smithsonian-mcp
# For streamable HTTP at http://127.0.0.1:8000/mcp on this machine only (the
# endpoint has no authentication, and anyone who can reach the port spends your
# API key's quota):
#   docker run --rm -e SMITHSONIAN_API_KEY -e MCP_TRANSPORT=http \
#       -p 127.0.0.1:8000:8000 justinmol/smithsonian-mcp
EXPOSE 8000
CMD ["smithsonian-mcp"]
