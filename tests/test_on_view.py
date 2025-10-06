"""
Comprehensive tests for on-view functionality.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from smithsonian_mcp.models import (
    CollectionSearchFilter,
    SmithsonianObject,
    SearchResult,
)
from smithsonian_mcp.api_client import SmithsonianAPIClient

pytest.importorskip("pytest_asyncio")


class TestOnViewDataModels:
    """Test on-view related data model functionality."""

    def test_search_filter_with_on_view(self):
        """Test creating search filter with on_view parameter."""
        filter_obj = CollectionSearchFilter(
            query="*",
            on_view=True,
            unit_code=None,
            object_type=None,
            date_start=None,
            date_end=None,
            maker=None,
            material=None,
            topic=None,
            has_images=None,
            has_3d=None,
            is_cc0=None,
        )

        assert filter_obj.on_view is True
        assert filter_obj.query == "*"

    def test_search_filter_on_view_false(self):
        """Test search filter with on_view=False."""
        filter_obj = CollectionSearchFilter(
            query="painting",
            on_view=False,
            unit_code="SAAM",
            object_type=None,
            date_start=None,
            date_end=None,
            maker=None,
            material=None,
            topic=None,
            has_images=None,
            has_3d=None,
            is_cc0=None,
        )

        assert filter_obj.on_view is False
        assert filter_obj.unit_code == "SAAM"

    def test_search_filter_on_view_none(self):
        """Test search filter with on_view=None (no filter)."""
        filter_obj = CollectionSearchFilter(
            query="sculpture",
            on_view=None,
            unit_code=None,
            object_type=None,
            date_start=None,
            date_end=None,
            maker=None,
            material=None,
            topic=None,
            has_images=None,
            has_3d=None,
            is_cc0=None,
        )

        assert filter_obj.on_view is None

    def test_smithsonian_object_on_view_fields(self):
        """Test SmithsonianObject with on-view fields."""
        obj = SmithsonianObject(
            id="test-exhibit-123",
            title="Exhibition Test Object",
            url=None,
            unit_code="NMAH",
            unit_name="National Museum of American History",
            is_on_view=True,
            exhibition_title="American Innovation",
            exhibition_location="Gallery 3",
            object_type=None,
            date=None,
            date_standardized=None,
            dimensions=None,
            description=None,
            summary=None,
            notes=None,
            credit_line=None,
            rights=None,
            record_link=None,
            last_modified=None,
        )

        assert obj.is_on_view is True
        assert obj.exhibition_title == "American Innovation"
        assert obj.exhibition_location == "Gallery 3"

    def test_smithsonian_object_not_on_view(self):
        """Test SmithsonianObject not on view."""
        obj = SmithsonianObject(
            id="test-storage-456",
            title="Storage Test Object",
            url=None,
            unit_code="NMNH",
            is_on_view=False,
            exhibition_title=None,
            exhibition_location=None,
            object_type=None,
            date=None,
            date_standardized=None,
            dimensions=None,
            description=None,
            summary=None,
            notes=None,
            credit_line=None,
            rights=None,
            record_link=None,
            last_modified=None,
            unit_name=None,
        )

        assert obj.is_on_view is False
        assert obj.exhibition_title is None


@pytest.mark.asyncio
class TestOnViewAPIClient:
    """Test API client on-view functionality."""

    def test_build_search_params_on_view_true(self):
        """Test building search params with on_view=True."""
        client = SmithsonianAPIClient(api_key="test_key")

        filters = CollectionSearchFilter(
            query="*",
            on_view=True,
            unit_code=None,
            object_type=None,
            date_start=None,
            date_end=None,
            maker=None,
            material=None,
            topic=None,
            has_images=None,
            has_3d=None,
            is_cc0=None,
        )

        params = client._build_search_params(filters)

        assert "fq" in params
        assert 'onPhysicalExhibit:"Yes"' in params["fq"]

    def test_build_search_params_on_view_false(self):
        """Test building search params with on_view=False."""
        client = SmithsonianAPIClient(api_key="test_key")

        filters = CollectionSearchFilter(
            query="*",
            on_view=False,
            unit_code=None,
            object_type=None,
            date_start=None,
            date_end=None,
            maker=None,
            material=None,
            topic=None,
            has_images=None,
            has_3d=None,
            is_cc0=None,
        )

        params = client._build_search_params(filters)

        assert "fq" in params
        assert 'onPhysicalExhibit:"No"' in params["fq"]

    def test_build_search_params_on_view_with_unit(self):
        """Test building search params with on_view and unit_code."""
        client = SmithsonianAPIClient(api_key="test_key")

        filters = CollectionSearchFilter(
            query="*",
            on_view=True,
            unit_code="NMNH",
            object_type=None,
            date_start=None,
            date_end=None,
            maker=None,
            material=None,
            topic=None,
            has_images=None,
            has_3d=None,
            is_cc0=None,
        )

        params = client._build_search_params(filters)

        assert "fq" in params
        assert 'onPhysicalExhibit:"Yes"' in params["fq"]
        assert 'unit_code:"NMNH"' in params["fq"]
        assert " AND " in params["fq"]

    def test_build_search_params_on_view_none(self):
        """Test building search params with on_view=None (no filter)."""
        client = SmithsonianAPIClient(api_key="test_key")

        filters = CollectionSearchFilter(
            query="test",
            on_view=None,
            unit_code=None,
            object_type=None,
            date_start=None,
            date_end=None,
            maker=None,
            material=None,
            topic=None,
            has_images=None,
            has_3d=None,
            is_cc0=None,
        )

        params = client._build_search_params(filters)

        if "fq" in params:
            assert "onPhysicalExhibit" not in params["fq"]

    def test_parse_object_data_on_view_yes(self):
        """Test parsing object data with onPhysicalExhibit=Yes."""
        client = SmithsonianAPIClient(api_key="test_key")

        raw_data = {
            "id": "test-123",
            "title": "Test Object on View",
            "unitCode": "NMNH",
            "content": {
                "descriptiveNonRepeating": {},
                "freetext": {},
                "indexedStructured": {"onPhysicalExhibit": [{"content": "Yes"}]},
            },
        }

        obj = client._parse_object_data(raw_data)

        assert obj.is_on_view is True
        assert obj.id == "test-123"
        assert obj.title == "Test Object on View"

    def test_parse_object_data_on_view_no(self):
        """Test parsing object data with onPhysicalExhibit=No."""
        client = SmithsonianAPIClient(api_key="test_key")

        raw_data = {
            "id": "test-456",
            "title": "Test Object in Storage",
            "unitCode": "NMAH",
            "content": {
                "descriptiveNonRepeating": {},
                "freetext": {},
                "indexedStructured": {"onPhysicalExhibit": [{"content": "No"}]},
            },
        }

        obj = client._parse_object_data(raw_data)

        assert obj.is_on_view is False

    def test_parse_object_data_on_view_missing(self):
        """Test parsing object data without onPhysicalExhibit field."""
        client = SmithsonianAPIClient(api_key="test_key")

        raw_data = {
            "id": "test-789",
            "title": "Test Object No Status",
            "unitCode": "NPG",
            "content": {
                "descriptiveNonRepeating": {},
                "freetext": {},
                "indexedStructured": {},
            },
        }

        obj = client._parse_object_data(raw_data)

        assert obj.is_on_view is False

    @patch("smithsonian_mcp.api_client.httpx.AsyncClient")
    async def test_search_on_view_objects(self, mock_client_class):
        """Test searching for on-view objects."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": {
                "rows": [
                    {
                        "id": "exhibit-1",
                        "title": "Exhibited Object 1",
                        "unitCode": "NMNH",
                        "content": {
                            "descriptiveNonRepeating": {},
                            "freetext": {},
                            "indexedStructured": {
                                "onPhysicalExhibit": [{"content": "Yes"}]
                            },
                        },
                    }
                ],
                "rowCount": 1,
            }
        }
        mock_response.raise_for_status = MagicMock()

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        mock_client_class.return_value = mock_session

        client = SmithsonianAPIClient(api_key="test_key")
        client.session = mock_session

        filters = CollectionSearchFilter(
            query="*",
            on_view=True,
            unit_code=None,
            object_type=None,
            date_start=None,
            date_end=None,
            maker=None,
            material=None,
            topic=None,
            has_images=None,
            has_3d=None,
            is_cc0=None,
        )

        result = await client.search_collections(filters)

        assert result.total_count == 1
        assert len(result.objects) == 1
        assert result.objects[0].is_on_view is True


@pytest.mark.asyncio
class TestOnViewIntegration:
    """Integration tests for on-view functionality."""

    async def test_combined_filters_on_view_and_unit(self):
        """Test combining on_view filter with unit_code."""
        client = SmithsonianAPIClient(api_key="test_key")

        filters = CollectionSearchFilter(
            query="*",
            on_view=True,
            unit_code="NMNH",
            has_images=True,
            object_type=None,
            date_start=None,
            date_end=None,
            maker=None,
            material=None,
            topic=None,
            has_3d=None,
            is_cc0=None,
        )

        params = client._build_search_params(filters)

        assert "fq" in params
        fq_value = params["fq"]
        assert 'onPhysicalExhibit:"Yes"' in fq_value
        assert 'unit_code:"NMNH"' in fq_value
        assert "online_media_type:Images" in fq_value

    async def test_combined_filters_on_view_and_cc0(self):
        """Test combining on_view filter with CC0 license."""
        client = SmithsonianAPIClient(api_key="test_key")

        filters = CollectionSearchFilter(
            query="painting",
            on_view=True,
            is_cc0=True,
            unit_code=None,
            object_type=None,
            date_start=None,
            date_end=None,
            maker=None,
            material=None,
            topic=None,
            has_images=None,
            has_3d=None,
        )

        params = client._build_search_params(filters)

        assert "fq" in params
        fq_value = params["fq"]
        assert 'onPhysicalExhibit:"Yes"' in fq_value
        assert "usage_rights:CC0" in fq_value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
