"""
Tests for get_object_url tool functionality.
"""

import json

import pytest
from unittest.mock import AsyncMock, patch

from smithsonian_mcp.api_client import SmithsonianAPIClient
from smithsonian_mcp.models import SmithsonianObject

pytest.importorskip("pytest_asyncio")


class TestGetObjectUrl:
    """Test get_object_url tool with various identifier formats."""

    @pytest.fixture
    def thunder_god_data(self):
        """Load thunder god test data."""
        with open("tests/thunder_god_response.json", "r") as f:
            return json.load(f)

    @pytest.fixture
    def thunder_god_object(self, thunder_god_data):
        """Create SmithsonianObject from thunder god test data."""
        from smithsonian_mcp.api_client import SmithsonianAPIClient

        client = SmithsonianAPIClient()
        return client._parse_object_data(thunder_god_data["response"])

    @pytest.mark.asyncio
    async def test_get_object_url_accession_number(self, thunder_god_data, thunder_god_object):
        """Test get_object_url with Accession Number (F1900.47)."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        # Mock the API client to return our test object
        mock_client_instance.get_object_by_id.return_value = thunder_god_object

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import tools as tools_module

                # Test with Accession Number
                result = await tools_module.get_object_url.fn(object_identifier="F1900.47")

                # Should return the record_link URL (preferred over url field)
                assert result == "https://asia.si.edu/object/F1900.47/"

                # Verify the API was called (should try Accession Number first)
                mock_client_instance.get_object_by_id.assert_called()

    @pytest.mark.asyncio
    async def test_get_object_url_record_id(self, thunder_god_data, thunder_god_object):
        """Test get_object_url with Record ID (fsg_F1900.47)."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        # Mock the API client to return our test object
        mock_client_instance.get_object_by_id.return_value = thunder_god_object

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import tools as tools_module

                # Test with Record ID
                result = await tools_module.get_object_url.fn(object_identifier="fsg_F1900.47")

                # Should return the constructed URL from record_id
                assert result == "https://asia.si.edu/object/F1900.47"

    @pytest.mark.asyncio
    async def test_get_object_url_internal_id(self, thunder_god_data, thunder_god_object):
        """Test get_object_url with Internal ID (ld1-1643390182193-1643390183699-0)."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        # Mock the API client to return our test object
        mock_client_instance.get_object_by_id.return_value = thunder_god_object

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import tools as tools_module

                # Test with Internal ID
                result = await tools_module.get_object_url.fn(
                    object_identifier="ld1-1643390182193-1643390183699-0"
                )

                # Should return the record_link URL
                assert result == "https://asia.si.edu/object/F1900.47/"

    @pytest.mark.asyncio
    async def test_get_object_url_prefers_record_link(self, thunder_god_object):
        """Test that get_object_url prefers record_link over url field when they differ."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        # Mock the API client to return our test object
        mock_client_instance.get_object_by_id.return_value = thunder_god_object

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import tools as tools_module

                result = await tools_module.get_object_url.fn(object_identifier="F1900.47")

                # Should prefer record_link (https URL) over url field (identifier)
                assert result == "https://asia.si.edu/object/F1900.47/"
                assert result != str(thunder_god_object.url)  # Should not be the identifier

    @pytest.mark.asyncio
    async def test_get_object_url_invalid_identifier(self):
        """Test get_object_url with invalid identifier returns None."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        # Mock the API client to return None (object not found)
        mock_client_instance.get_object_by_id.return_value = None

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import tools as tools_module

                result = await tools_module.get_object_url.fn(object_identifier="invalid-id")

                assert result is None

    @pytest.mark.asyncio
    async def test_get_object_url_empty_identifier_raises_error(self):
        """Test get_object_url with empty identifier raises ValueError."""
        from smithsonian_mcp import tools as tools_module

        with pytest.raises(ValueError, match="object_identifier cannot be empty"):
            await tools_module.get_object_url.fn(object_identifier="")

    @pytest.mark.asyncio
    async def test_get_object_url_no_valid_urls_returns_none(self):
        """Test get_object_url when object has no valid URLs returns None."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        # Create object with invalid URLs
        invalid_object = SmithsonianObject(
            id="test-id",
            record_id="test_record_id",
            title="Test Object",
            url=None,  # No valid URL
            record_link=None,  # No valid record_link
            unit_code="TEST",
            unit_name="Test Unit",
            object_type=None,
            classification=[],
            date=None,
            date_standardized=None,
            maker=[],
            materials=[],
            dimensions=None,
            description=None,
            summary=None,
            notes=None,
            topics=[],
            culture=[],
            place=[],
            images=[],
            credit_line=None,
            rights=None,
            is_cc0=False,
            is_on_view=False,
            exhibition_title=None,
            exhibition_location=None,
            last_modified=None,
        )

        mock_client_instance.get_object_by_id.return_value = invalid_object

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import tools as tools_module

                result = await tools_module.get_object_url.fn(object_identifier="test-id")

                assert result is None
