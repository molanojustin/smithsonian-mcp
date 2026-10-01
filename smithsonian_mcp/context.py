"""
Smithsonian Open Access MCP Context

Holds the single API client shared by every tool, resource and helper. The server
lifespan creates and closes it; ``get_api_client`` creates one lazily when called
outside a lifespan (tests, mcpo, direct library use).
"""

import logging
from dataclasses import dataclass
from typing import Optional

from fastmcp import Context

from .api_client import SmithsonianAPIClient, create_client

logger = logging.getLogger(__name__)

_global_api_client: Optional[SmithsonianAPIClient] = None


@dataclass
class ServerContext:
    """Application context with initialized dependencies."""

    api_client: SmithsonianAPIClient


async def get_api_client(
    ctx: Optional[Context] = None,  # pylint: disable=unused-argument
) -> SmithsonianAPIClient:
    """
    Return the shared API client, creating it if none is installed.

    Args:
        ctx: FastMCP context (unused; the client is process-wide).

    Returns:
        SmithsonianAPIClient: The shared client.
    """
    global _global_api_client  # pylint: disable=global-statement

    if _global_api_client is None:
        client = await create_client()
        if _global_api_client is None:
            _global_api_client = client
            logger.info("Shared API client created outside the server lifespan")
        else:
            # Another task installed a client while this one was connecting
            await client.disconnect()

    return _global_api_client


def set_api_client(
    client: Optional[SmithsonianAPIClient],
) -> Optional[SmithsonianAPIClient]:
    """
    Install the shared API client.

    Args:
        client: Client to share, or None to clear it.

    Returns:
        Optional[SmithsonianAPIClient]: The previously installed client.
    """
    global _global_api_client  # pylint: disable=global-statement

    previous = _global_api_client
    _global_api_client = client
    return previous


def peek_api_client() -> Optional[SmithsonianAPIClient]:
    """
    Return the installed shared client without creating one.

    Returns:
        Optional[SmithsonianAPIClient]: The shared client, if any.
    """
    return _global_api_client


async def close_api_client() -> None:
    """Close and clear the shared API client, if one is installed."""
    client = set_api_client(None)
    if client is not None:
        await client.disconnect()
