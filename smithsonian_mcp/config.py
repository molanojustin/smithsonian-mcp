"""
Configuration management for Smithsonian MCP Server.

Settings are read from environment variables, or from a ``.env`` file found by
python-decouple, when this module is first imported.
"""

from typing import Optional

from decouple import config

from . import __version__


# A namespace of settings read once at import, not an object with behaviour.
class Config:  # pylint: disable=too-few-public-methods
    """Configuration settings for the Smithsonian MCP server."""

    # API key from https://api.data.gov/signup/. Sent only in the X-Api-Key header.
    API_KEY: Optional[str] = config("SMITHSONIAN_API_KEY", default=None)  # type: ignore

    # Server identity
    SERVER_NAME: str = config(
        "SERVER_NAME", default="Smithsonian Open Access"
    )  # type: ignore
    SERVER_VERSION: str = __version__

    # Logging level used by the command line entry point (DEBUG, INFO, ...)
    LOG_LEVEL: str = config("LOG_LEVEL", default="INFO")  # type: ignore

    # Transport of the command line entry point: stdio, or http for streamable
    # HTTP on MCP_HOST:MCP_PORT. The --transport, --host and --port options take
    # precedence; the values are validated when the server starts.
    MCP_TRANSPORT: str = config("MCP_TRANSPORT", default="stdio")  # type: ignore
    MCP_HOST: str = config("MCP_HOST", default="127.0.0.1")  # type: ignore
    MCP_PORT: str = config("MCP_PORT", default="8000")  # type: ignore

    # Value of the User-Agent header sent with every API request
    USER_AGENT: str = (
        f"smithsonian-mcp/{__version__} "
        "(+https://github.com/molanojustin/smithsonian-mcp)"
    )

    @classmethod
    def validate_api_key(cls) -> bool:
        """
        Check if an API key is configured.

        Returns:
            bool: True if a non-empty API key is configured.
        """
        return cls.API_KEY is not None and len(cls.API_KEY.strip()) > 0
