"""
Smithsonian Open Access MCP Server

This package provides an MCP (Model Context Protocol) server for accessing
the Smithsonian Institution's Open Access collections through a standardized
interface that AI assistants can use.

Key Features:
- Search across 3+ million Smithsonian collection objects
- Access detailed object metadata, images, and 3D models
- Filter by museum/unit, object type, creator, materials, and more
- Educational and research-oriented prompt templates
- Full support for CC0 licensed content

Usage:
    from smithsonian_mcp import mcp

    # Run the server
    mcp.run()

API Key Setup:
    Get your free API key from https://api.data.gov/signup/
    Set environment variable: SMITHSONIAN_API_KEY=your_key_here
"""

from .server import mcp
from .config import Config
from .models import SmithsonianObject, SearchResult, CollectionSearchFilter
from .api_client import SmithsonianAPIClient, create_client

__version__ = "0.1.0"
__author__ = "Justin Molano"
__email__ = "160653314+molanojustin@users.noreply.github.com"

__all__ = [
    "mcp",
    "Config",
    "SmithsonianObject",
    "SearchResult",
    "CollectionSearchFilter",
    "SmithsonianAPIClient",
    "create_client",
]
