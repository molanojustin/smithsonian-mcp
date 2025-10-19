"""
Smithsonian Open Access MCP Context
"""

import logging
from typing import Optional
from dataclasses import dataclass

from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession

from .api_client import SmithsonianAPIClient, create_client

logger = logging.getLogger(__name__)

_global_api_client: Optional[SmithsonianAPIClient] = None


@dataclass
class ServerContext:
    """Application context with initialized dependencies."""

    api_client: SmithsonianAPIClient


async def get_api_client(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,  # pylint: disable=unused-argument
) -> SmithsonianAPIClient:
    """Get API client from global instance for mcpo compatibility."""
    global _global_api_client # pylint: disable=global-statement

    # Always use global client to avoid context access issues
    # This works for both normal MCP and mcpo scenarios
    if _global_api_client is None:
        _global_api_client = await create_client()
        logger.info("Global API client initialized")

    return _global_api_client
