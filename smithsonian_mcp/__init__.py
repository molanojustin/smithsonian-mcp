"""
Smithsonian Open Access MCP Server

This package provides an MCP (Model Context Protocol) server for accessing
the Smithsonian Institution's Open Access collections through a standardized
interface that AI assistants can use.

Key Features:
- Search across millions of Smithsonian collection objects
- Access detailed object metadata and images
- Filter by museum/unit, object type, creator, materials, and more
- Educational and research-oriented prompt templates
- Full support for CC0 licensed content

Usage:
    from smithsonian_mcp import mcp

    # Run the server
    mcp.run()

    # Or use the command line entry point
    # python -m smithsonian_mcp

API Key Setup:
    Get your free API key from https://api.data.gov/signup/
    Set environment variable: SMITHSONIAN_API_KEY=your_key_here

Submodules and the public names below are loaded lazily, so importing the
package (or a lightweight submodule such as ``smithsonian_mcp.config``) does not
start the FastMCP application, register tools, or configure logging.
"""

import importlib
from typing import Any, Dict, List, Tuple


def _resolve_version() -> str:
    """
    Resolve the package version.

    The generated ``_version.py`` module is preferred, then installed package
    metadata, then a ``0.0.0`` placeholder.

    Returns:
        str: The package version string.
    """
    try:
        from ._version import (  # pylint: disable=import-outside-toplevel
            __version__ as generated_version,
        )

        return generated_version
    except ImportError:
        pass

    try:
        from importlib.metadata import (  # pylint: disable=import-outside-toplevel
            PackageNotFoundError,
            version,
        )

        return version("smithsonian-mcp")
    except PackageNotFoundError:
        return "0.0.0"


# Defined before any submodule import so that submodules can rely on it.
__version__: str = _resolve_version()
__author__ = "Justin Molano"
__email__ = "justinmolano2@gmail.com"

# Public attribute name -> (submodule, attribute). The app module registers the
# tools, resources and prompts when it creates ``mcp``.
_LAZY_ATTRIBUTES: Dict[str, Tuple[str, str]] = {
    "mcp": ("app", "mcp"),
    "Config": ("config", "Config"),
    "SmithsonianObject": ("models", "SmithsonianObject"),
    "SearchResult": ("models", "SearchResult"),
    "CollectionSearchFilter": ("models", "CollectionSearchFilter"),
    "SmithsonianAPIClient": ("api_client", "SmithsonianAPIClient"),
    "create_client": ("api_client", "create_client"),
}

_LAZY_SUBMODULES = frozenset(
    {
        "api_client",
        "app",
        "config",
        "constants",
        "context",
        "main",
        "models",
        "parsing",
        "prompts",
        "query",
        "resources",
        "server",
        "tools",
        "utils",
    }
)

# Names below are loaded lazily by __getattr__
# pylint: disable=undefined-all-variable
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


def __getattr__(name: str) -> Any:
    """
    Load public attributes and submodules on first access.

    Args:
        name: Attribute name requested from the package.

    Returns:
        Any: The requested attribute or submodule.

    Raises:
        AttributeError: If the name is not a known attribute or submodule.
    """
    if name in _LAZY_ATTRIBUTES:
        module_name, attribute = _LAZY_ATTRIBUTES[name]
        module = importlib.import_module(f".{module_name}", __name__)
        value = getattr(module, attribute)
        globals()[name] = value
        return value
    if name in _LAZY_SUBMODULES:
        return importlib.import_module(f".{name}", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> List[str]:
    """
    List the package attributes, including lazily loaded ones.

    Returns:
        List[str]: Sorted attribute names.
    """
    return sorted(set(globals()) | set(_LAZY_ATTRIBUTES) | _LAZY_SUBMODULES)
