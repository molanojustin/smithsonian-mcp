"""
Configuration management for Smithsonian MCP Server.
"""

from typing import Optional
from decouple import config


class Config:
    """Configuration settings for the Smithsonian MCP server."""

    # API Configuration
    # TODO: Align with actual base URL if different.
    API_DATA_GOV_BASE_URL: str = config(
        "API_DATA_GOV_BASE_URL", default="https://api.data.gov"
    )  # type: ignore

    API_KEY: Optional[str] = config("SMITHSONIAN_API_KEY", default=None)  # type: ignore

    # Smithsonian specific endpoints
    EDAN_API_PATH: str = "/edan"

    # Rate limiting
    DEFAULT_RATE_LIMIT: int = config("DEFAULT_RATE_LIMIT", default=60, cast=int)

    # Server configuration
    # TODO: Remove from environment variables in future releases.
    SERVER_NAME: str = config("SERVER_NAME", default="Smithsonian Open Access")  # type: ignore
    SERVER_VERSION: str = config("SERVER_VERSION", default="1.0.0")  # type: ignore

    # Logging
    LOG_LEVEL: str = config("LOG_LEVEL", default="INFO")  # type: ignore

    # Cache settings
    ENABLE_CACHE: bool = config("ENABLE_CACHE", default=True, cast=bool)
    CACHE_TTL_SECONDS: int = config("CACHE_TTL_SECONDS", default=3600, cast=int)

    # Image handling
    MAX_IMAGE_SIZE_MB: int = config("MAX_IMAGE_SIZE_MB", default=50, cast=int)

    @classmethod
    def validate_api_key(cls) -> bool:
        """Check if API key is configured."""
        return cls.API_KEY is not None and len(cls.API_KEY) > 0

    @classmethod
    def get_headers(cls) -> dict:
        """Get standard headers for API requests."""
        headers = {
            "User-Agent": f"smithsonian-mcp-server/{cls.SERVER_VERSION}",
            "Accept": "application/json",
        }

        if cls.API_KEY:
            headers["X-Api-Key"] = cls.API_KEY

        return headers
