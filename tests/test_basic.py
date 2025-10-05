"""
Basic tests for Smithsonian MCP Server
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from smithsonian_mcp.models import CollectionSearchFilter, SmithsonianObject
from smithsonian_mcp.config import Config


class TestConfig:
    """Test configuration management."""

    def test_default_values(self):
        """Test default configuration values."""
        assert Config.SERVER_NAME == "Smithsonian Open Access"
        assert Config.SERVER_VERSION == "1.0.0"
        assert Config.DEFAULT_RATE_LIMIT == 60


class TestModels:
    """Test data models."""

    def test_search_filter_creation(self):
        """Test creating search filter."""
        filter_obj = CollectionSearchFilter(query="pottery", unit_code="NMNH", limit=10)

        assert filter_obj.query == "pottery"
        assert filter_obj.unit_code == "NMNH"
        assert filter_obj.limit == 10
        assert filter_obj.offset == 0

    def test_smithsonian_object_creation(self):
        """Test creating Smithsonian object."""
        obj = SmithsonianObject(id="test-123", title="Test Object")

        assert obj.id == "test-123"
        assert obj.title == "Test Object"
        assert obj.images == []
        assert obj.is_cc0 is False


@pytest.mark.asyncio
class TestAPIClient:
    """Test API client functionality."""

    @patch("smithsonian_mcp.api_client.httpx.AsyncClient")
    async def test_client_creation(self, mock_client):
        """Test API client creation."""
        from smithsonian_mcp.api_client import SmithsonianAPIClient

        client = SmithsonianAPIClient(api_key="test_key")
        assert client.api_key == "test_key"

        # Test connection
        await client.connect()
        assert client.session is not None


if __name__ == "__main__":
    pytest.main([__file__])
