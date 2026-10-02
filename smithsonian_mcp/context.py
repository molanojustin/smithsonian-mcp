"""
Smithsonian Open Access MCP Context

Holds the single API client shared by every tool, resource and helper. The server
lifespan creates and closes it; ``get_api_client`` creates one lazily when called
outside a lifespan (tests, mcpo, direct library use).

The client's HTTP connections belong to the event loop that created them, so the
shared client is replaced when it is requested from a different event loop (for
example a second ``asyncio.run``).
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Optional

from fastmcp import Context, FastMCP

from .api_client import SmithsonianAPIClient, create_client
from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class ServerContext:
    """Application context with initialized dependencies."""

    api_client: SmithsonianAPIClient


@dataclass
class _SharedClient:
    """The process-wide client and the event loop it was created on, if known."""

    client: Optional[SmithsonianAPIClient] = None
    loop: Optional[asyncio.AbstractEventLoop] = None


_shared = _SharedClient()


def _running_loop() -> Optional[asyncio.AbstractEventLoop]:
    """Return the running event loop, or None outside one."""
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


def _discard_client(
    client: SmithsonianAPIClient, loop: Optional[asyncio.AbstractEventLoop]
) -> None:
    """
    Release a client that belongs to another event loop.

    It is closed on its own loop when that loop is still running (for example in
    another thread). A closed loop has already dropped the client's connections,
    so the client is simply forgotten.

    Args:
        client: The client to release.
        loop: The event loop the client was created on.
    """
    if loop is not None and loop.is_running() and not loop.is_closed():
        asyncio.run_coroutine_threadsafe(client.disconnect(), loop)


async def get_api_client(
    ctx: Optional[Context] = None,  # pylint: disable=unused-argument
) -> SmithsonianAPIClient:
    """
    Return the shared API client, creating it if none is installed.

    A client created on a different event loop is replaced, because its
    connections cannot be used from this one.

    Args:
        ctx: FastMCP context (unused; the client is process-wide).

    Returns:
        SmithsonianAPIClient: The shared client.
    """
    loop = asyncio.get_running_loop()
    if (
        _shared.client is not None
        and _shared.loop is not None
        and _shared.loop is not loop
    ):
        logger.info("Replacing the shared API client created on another event loop")
        _discard_client(_shared.client, _shared.loop)
        _shared.client = None
        _shared.loop = None

    if _shared.client is None:
        client = await create_client()
        if _shared.client is None:
            _shared.client = client
            _shared.loop = loop
            logger.info("Shared API client created outside the server lifespan")
        else:
            # Another task installed a client while this one was connecting
            await client.disconnect()

    return _shared.client


def set_api_client(
    client: Optional[SmithsonianAPIClient],
) -> Optional[SmithsonianAPIClient]:
    """
    Install the shared API client.

    The running event loop, if any, is recorded as the client's loop.

    Args:
        client: Client to share, or None to clear it.

    Returns:
        Optional[SmithsonianAPIClient]: The previously installed client.
    """
    previous = _shared.client
    _shared.client = client
    _shared.loop = _running_loop() if client is not None else None
    return previous


def peek_api_client() -> Optional[SmithsonianAPIClient]:
    """
    Return the installed shared client without creating one.

    Returns:
        Optional[SmithsonianAPIClient]: The shared client, if any.
    """
    return _shared.client


async def close_api_client() -> None:
    """Close and clear the shared API client, if one is installed."""
    client = set_api_client(None)
    if client is not None:
        await client.disconnect()


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
    previous = set_api_client(api_client)
    if previous is not None and previous is not api_client:
        await previous.disconnect()

    try:
        logger.info(
            "Server initialized: %s v%s", Config.SERVER_NAME, Config.SERVER_VERSION
        )
        yield ServerContext(api_client=api_client)
    finally:
        logger.info("Shutting down Smithsonian MCP Server...")
        if peek_api_client() is api_client:
            set_api_client(None)
        await api_client.disconnect()
