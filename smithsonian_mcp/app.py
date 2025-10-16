"""
Smithsonian Open Access MCP Application

This module initializes the FastMCP application instance.
"""

from fastmcp import FastMCP
from .config import Config
from .server import server_lifespan

def create_app() -> FastMCP:
    """Create and configure the FastMCP application."""
    return FastMCP(Config.SERVER_NAME, lifespan=server_lifespan)

mcp = create_app()
