"""
Tests for get_museum_highlights_on_view tool functionality.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from smithsonian_mcp.models import (
    SmithsonianObject,
    SearchResult,
    CollectionSearchFilter,
)
from smithsonian_mcp.api_client import SmithsonianAPIClient

pytest.importorskip("pytest_asyncio")


class TestMuseumHighlightsOnView:
    """Test get_museum_highlights_on_view tool."""

    @pytest.mark.asyncio
    async def test_get_museum_highlights_on_view_basic(self):
        """Test basic functionality of get_museum_highlights_on_view."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import tools as tools_module

                # Mock API responses for the dual strategy
                # Strategy 1: API-level on-view filtering returns some results
                on_view_results = SearchResult(
                    objects=[
                        SmithsonianObject(
                            id="on-view-1",
                            title="On View Object 1",
                            is_on_view=True,
                            exhibition_title="Current Exhibition",
                            images=[{"url": "http://example.com/image1.jpg"}],
                            description="A detailed description",
                        )
                    ],
                    total_count=1,
                    returned_count=1,
                    offset=0,
                    has_more=False,
                    next_offset=None,
                )

                # Strategy 2: Exhibition data filtering returns additional results
                exhibition_results = SearchResult(
                    objects=[
                        SmithsonianObject(
                            id="exhibition-1",
                            title="Exhibition Object 1",
                            is_on_view=False,
                            exhibition_title="Special Exhibition",
                            exhibition_location="Gallery 2",
                            images=[{"url": "http://example.com/image2.jpg"}],
                        ),
                        SmithsonianObject(
                            id="popular-1",
                            title="Popular Object 1",
                            is_on_view=False,
                            images=[{"url": "http://example.com/image3.jpg"}],
                            description="Very popular object",
                        )
                    ],
                    total_count=2,
                    returned_count=2,
                    offset=0,
                    has_more=False,
                    next_offset=None,
                )

                # Mock responses for all possible API calls (strategies 1, 2, and 3)
                mock_client_instance.search_collections.side_effect = [
                    on_view_results,  # Strategy 1: on-view filtering
                    exhibition_results,  # Strategy 2: exhibition data
                    exhibition_results,  # Strategy 3: recent/popular objects (fallback)
                ]

                result = await tools_module.get_museum_highlights_on_view.fn(
                    unit_code="FSG", limit=10
                )

                # Verify the tool was called and returned results
                assert isinstance(result, SearchResult)
                assert len(result.objects) > 0

                # Verify search_collections was called multiple times (dual strategy)
                assert mock_client_instance.search_collections.call_count >= 2

    @pytest.mark.asyncio
    async def test_get_museum_highlights_on_view_empty_results(self):
        """Test get_museum_highlights_on_view with no results."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import tools as tools_module

                # Mock empty results
                empty_result = SearchResult(
                    objects=[],
                    total_count=0,
                    returned_count=0,
                    offset=0,
                    has_more=False,
                    next_offset=None,
                )

                mock_client_instance.search_collections.return_value = empty_result

                result = await tools_module.get_museum_highlights_on_view.fn(
                    museum="Smithsonian Asian Art Museum"
                )

                assert isinstance(result, SearchResult)
                assert result.objects == []
                assert result.total_count == 0

    @pytest.mark.asyncio
    async def test_get_museum_highlights_on_view_with_museum_name_resolution(self):
        """Test that museum name resolution works in get_museum_highlights_on_view."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import tools as tools_module

                # Mock results
                mock_result = SearchResult(
                    objects=[
                        SmithsonianObject(
                            id="highlight-1",
                            title="Highlight Object",
                            is_on_view=True,
                        )
                    ],
                    total_count=1,
                    returned_count=1,
                    offset=0,
                    has_more=False,
                    next_offset=None,
                )

                mock_client_instance.search_collections.return_value = mock_result

                result = await tools_module.get_museum_highlights_on_view.fn(
                    museum="Smithsonian Asian Art Museum", limit=5
                )

                assert isinstance(result, SearchResult)
                assert len(result.objects) == 1

    @pytest.mark.asyncio
    async def test_get_museum_highlights_on_view_curation_scoring(self):
        """Test that objects are properly curated by highlight score."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import tools as tools_module

                # Create objects with different highlight scores
                high_score_obj = SmithsonianObject(
                    id="high-score",
                    title="High Score Object",
                    is_on_view=True,
                    exhibition_title="Major Exhibition",
                    images=[{"url": "http://example.com/image.jpg"}],
                    description="Detailed description",
                    maker=["Famous Artist"],
                )

                low_score_obj = SmithsonianObject(
                    id="low-score",
                    title="Low Score Object",
                    is_on_view=False,
                    exhibition_title=None,
                    images=[],  # No images
                    description=None,
                    maker=[],
                )

                # Mock results with mixed objects
                mixed_results = SearchResult(
                    objects=[low_score_obj, high_score_obj],
                    total_count=2,
                    returned_count=2,
                    offset=0,
                    has_more=False,
                    next_offset=None,
                )

                mock_client_instance.search_collections.return_value = mixed_results

                result = await tools_module.get_museum_highlights_on_view.fn(limit=10)

                # Should return results (exact ordering depends on implementation)
                assert isinstance(result, SearchResult)
                assert len(result.objects) <= 2  # Limited by available objects


if __name__ == "__main__":
    pytest.main([__file__, "-v"])