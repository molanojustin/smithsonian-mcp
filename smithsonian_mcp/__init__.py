"""
Smithsonian Open Access MCP Server

This package provides an MCP (Model Context Protocol) server for accessing
the Smithsonian Institution's Open Access collections through a standardized
interface that AI assistants can use.

Key Features:
- Search across 3+ million Smithsonian collection objects
- Access detailed object metadata and images
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

from warnings import warn
from .app import mcp
from .config import Config
from .models import SmithsonianObject, SearchResult, CollectionSearchFilter
from .api_client import SmithsonianAPIClient, create_client
from . import server, tools, resources, prompts, context, main, utils
try:
    from ._version import __version__
except ModuleNotFoundError:  # pragma: no cover - fallback for missing build artefact
    warn("Version module not found, setting local __version__ to '0.0.0'")
    __version__ = "0.0.0"

__author__ = "Justin Molano"
__email__ = "justinmolano2@gmail.com"

__all__ = [
    "mcp",
    "Config",
    "SmithsonianObject",
    "SearchResult",
    "CollectionSearchFilter",
    "SmithsonianAPIClient",
    "create_client",
    "server",
    "tools",
    "resources",
    "prompts",
    "context",
    "main",
    "utils",
]
