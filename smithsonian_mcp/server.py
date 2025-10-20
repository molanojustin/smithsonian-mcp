"""
Smithsonian Open Access MCP Server

This MCP server provides AI assistants with access to the Smithsonian's
Open Access collections through a standardized interface.
"""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastmcp import FastMCP

from .config import Config
from .api_client import create_client
from .context import ServerContext

logger = logging.getLogger(__name__)


@asynccontextmanager
async def server_lifespan(
    server: FastMCP, # pylint: disable=unused-argument
) -> AsyncIterator[ServerContext]:
    """Manage server lifecycle with API client initialization."""
    global _global_api_client  # pylint: disable=global-variable-undefined
    logger.info("Initializing Smithsonian MCP Server...")

    # Validate configuration
    if not Config.validate_api_key():
        logger.warning( # TODO: Update to raise exception and quit if no API key is provided.
            "No API key configured. "
            "Set SMITHSONIAN_API_KEY environment variable for access."
        )

    # Initialize API client
    api_client = await create_client()
    _global_api_client = api_client  # Set global reference for mcpo compatibility

    try:
        logger.info(
            "Server initialized: %s v%s", Config.SERVER_NAME, Config.SERVER_VERSION
        )
        yield ServerContext(api_client=api_client)
    finally:
        logger.info("Shutting down Smithsonian MCP Server...")
        await api_client.disconnect()
        _global_api_client = None
