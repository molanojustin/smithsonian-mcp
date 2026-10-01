"""
Smithsonian Open Access MCP Server

This MCP server provides AI assistants with access to the Smithsonian's
Open Access collections through a standardized interface.

Running ``python -m smithsonian_mcp.server`` is kept for backward compatibility
and starts the same entry point as ``python -m smithsonian_mcp``.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from . import context
from .api_client import create_client
from .config import Config
from .context import ServerContext

logger = logging.getLogger(__name__)


@asynccontextmanager
async def server_lifespan(
    server: FastMCP,  # pylint: disable=unused-argument
) -> AsyncIterator[ServerContext]:
    """
    Create the shared API client for the server's lifetime and close it on exit.

    Args:
        server: The FastMCP server.

    Yields:
        ServerContext: Context holding the shared API client.

    Raises:
        ValueError: If no API key is configured.
    """
    logger.info("Initializing Smithsonian MCP Server...")

    if not Config.validate_api_key():
        raise ValueError(
            "No API key configured. "
            "Set SMITHSONIAN_API_KEY environment variable for access."
        )

    api_client = await create_client()
    previous = context.set_api_client(api_client)
    if previous is not None and previous is not api_client:
        await previous.disconnect()

    try:
        logger.info(
            "Server initialized: %s v%s", Config.SERVER_NAME, Config.SERVER_VERSION
        )
        yield ServerContext(api_client=api_client)
    finally:
        logger.info("Shutting down Smithsonian MCP Server...")
        if context.peek_api_client() is api_client:
            context.set_api_client(None)
        await api_client.disconnect()


if __name__ == "__main__":
    from .main import main

    main()
