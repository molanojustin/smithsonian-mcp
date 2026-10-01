# syntax=docker/dockerfile:1

# Build stage: install the locked runtime dependencies and the package into
# /app/.venv with uv. Nothing from this stage except the virtual environment
# ends up in the final image.
FROM python:3.13.15-slim-trixie@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b AS builder

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
FROM python:3.13.15-slim-trixie@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b

LABEL org.opencontainers.image.source="https://github.com/molanojustin/smithsonian-mcp"
LABEL org.opencontainers.image.description="Smithsonian MCP Server - Model Context Protocol server for Smithsonian Open Access collections"
LABEL org.opencontainers.image.licenses="MIT"

RUN groupadd --system --gid 10001 smithsonian \
    && useradd --system --uid 10001 --gid smithsonian --create-home \
        --home-dir /home/smithsonian --shell /usr/sbin/nologin smithsonian

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
USER smithsonian

# The server speaks MCP over stdio, so run the container with -i:
#   docker run -i --rm -e SMITHSONIAN_API_KEY justinmol/smithsonian-mcp
CMD ["smithsonian-mcp"]
