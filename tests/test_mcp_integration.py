"""
Comprehensive MCP integration tests for the Smithsonian MCP server.

This module tests end-to-end MCP workflows, protocol adherence, and cross-tool dependencies.
"""
# TODO: DEBUG THIS TEST. STILL PASSING, BUT WE NEED TO FIGURE OUT THE 21 ISSUES.
import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from typing import List, Dict, Any, Optional

from smithsonian_mcp.models import (
    SmithsonianObject,
    SearchResult,
    CollectionSearchFilter,
    SmithsonianUnit,
    CollectionStats,
    APIError,
)
from smithsonian_mcp.api_client import SmithsonianAPIClient

pytest.importorskip("pytest_asyncio")


class TestMCPProtocolAdherence:
    """Test MCP protocol adherence and tool interface compliance."""

    @pytest.mark.asyncio
    async def test_tool_signature_compliance(self):
        """Test that MCP tools have proper signatures by checking the server module."""
        from smithsonian_mcp import tools as tools_module
        from smithsonian_mcp import resources as resources_module
        import inspect

        # Get the actual function implementations (the decorated tools are directly callable)
        tools_to_test = [
            ("search_collections", tools_module.search_collections),
            ("simple_explore", tools_module.simple_explore),
            ("continue_explore", tools_module.continue_explore),
            ("get_object_details", tools_module.get_object_details),
            ("get_smithsonian_units", tools_module.get_smithsonian_units),
            ("get_collection_statistics", tools_module.get_collection_statistics),
            ("search_by_unit", tools_module.search_by_unit),
            ("get_objects_on_view", tools_module.get_objects_on_view),
            ("check_object_on_view", tools_module.check_object_on_view),
            ("find_on_view_items", tools_module.find_on_view_items),
            ("get_search_context", resources_module.get_search_context),
            ("get_object_context", resources_module.get_object_context),
            ("get_on_view_context", resources_module.get_on_view_context),
            ("get_units_context", resources_module.get_units_context),
            ("get_stats_context", resources_module.get_stats_context),
        ]

        for tool_name, tool_func in tools_to_test:
            # Get the actual function from the FunctionTool wrapper
            actual_func = tool_func.fn

            # Verify tool has proper signature
            sig = inspect.signature(actual_func)
            assert "ctx" in sig.parameters, f"Tool {tool_name} missing ctx parameter"
            assert (
                sig.parameters["ctx"].default is None
            ), f"Tool {tool_name} ctx parameter should default to None"

    @pytest.mark.asyncio
    async def test_tool_return_types(self):
        """Test that tools return expected types."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import tools as tools_module

                # Test search_collections returns SearchResult
                mock_client_instance.search_collections.return_value = SearchResult(
                    objects=[],
                    total_count=0,
                    returned_count=0,
                    offset=0,
                    has_more=False,
                    next_offset=None,
                )

                result = await tools_module.search_collections.fn(query="test")
                assert isinstance(
                    result, SearchResult
                ), "search_collections should return SearchResult"

                # Test get_smithsonian_units returns list
                mock_client_instance.get_units.return_value = [
                    SmithsonianUnit(code="NMAH", name="American History Museum"),
                    SmithsonianUnit(code="NMNH", name="Natural History Museum"),
                ]
                result = await tools_module.get_smithsonian_units.fn()
                assert isinstance(
                    result, list
                ), "get_smithsonian_units should return list"

                # Test get_collection_statistics returns CollectionStats
                mock_client_instance.get_collection_stats.return_value = (
                    CollectionStats(
                        total_objects=1000,
                        total_digitized=500,
                        total_cc0=200,
                        total_with_images=400,
                        last_updated=datetime(2024, 1, 1),
                        units=[],
                    )
                )
                result = await tools_module.get_collection_statistics.fn()
                assert isinstance(
                    result, CollectionStats
                ), "get_collection_statistics should return CollectionStats"


class TestEndToEndMCPWorkflows:
    """Test complete user interaction patterns and workflows."""

    @pytest.mark.asyncio
    async def test_full_discovery_workflow(self):
        """Test complete discovery workflow: explore -> search -> details -> context."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import (
                    tools as tools_module,
                    resources as resources_module,
                )

                # Step 1: Simple exploration
                mock_client_instance.search_collections.return_value = SearchResult(
                    objects=[
                        SmithsonianObject(
                            id="test-123",
                            title="Test Object",
                            unit_code="NMNH",
                            unit_name="Natural History Museum",
                            is_on_view=True,
                            object_type="fossil",
                        )
                    ],
                    total_count=1,
                    returned_count=1,
                    offset=0,
                    has_more=False,
                    next_offset=None,
                )

                explore_result = await tools_module.simple_explore.fn(topic="dinosaurs")
                assert explore_result.objects
                object_id = explore_result.objects[0].id

                # Step 2: Get detailed object information
                mock_client_instance.get_object_by_id.return_value = SmithsonianObject(
                    id=object_id,
                    title="Detailed Test Object",
                    unit_code="NMNH",
                    description="A detailed description",
                    images=[{"url": "http://example.com/image.jpg"}],
                )

                detail_result = await tools_module.get_object_details.fn(
                    object_id=object_id
                )
                assert detail_result.id == object_id

                # Step 3: Get object context
                context_result = await resources_module.get_object_context.fn(
                    object_id=object_id
                )
                assert "Detailed Test Object" in context_result
                assert "Images: 1 available" in context_result

    @pytest.mark.asyncio
    async def test_exhibition_planning_workflow(self):
        """Test exhibition planning workflow: units -> on-view -> search -> context."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import (
                    tools as tools_module,
                    resources as resources_module,
                )

                # Step 1: Get available museums
                mock_client_instance.get_units.return_value = [
                    SmithsonianUnit(code="NMAH", name="American History Museum"),
                    SmithsonianUnit(code="NMNH", name="Natural History Museum"),
                ]

                units = await tools_module.get_smithsonian_units.fn()
                assert len(units) >= 2

                # Step 2: Find on-view items at specific museum
                mock_client_instance.search_collections.return_value = SearchResult(
                    objects=[
                        SmithsonianObject(
                            id="exhibit-1",
                            title="Exhibition Item 1",
                            unit_code="NMAH",
                            is_on_view=True,
                            exhibition_title="American Innovation",
                        )
                    ],
                    total_count=1,
                    returned_count=1,
                    offset=0,
                    has_more=False,
                    next_offset=None,
                )

                on_view_result = await tools_module.get_objects_on_view.fn(
                    unit_code="NMAH"
                )
                assert on_view_result.objects
                assert all(obj.is_on_view for obj in on_view_result.objects)

                # Step 3: Get on-view context
                context_result = await resources_module.get_on_view_context.fn(
                    unit_code="NMAH"
                )
                assert "Currently on exhibit" in context_result

    @pytest.mark.asyncio
    async def test_research_workflow_with_pagination(self):
        """Test research workflow with pagination: search -> continue -> details."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import tools as tools_module

                # Initial search
                seen_ids = []

                # Mock first batch of results
                mock_client_instance.search_collections.return_value = SearchResult(
                    objects=[
                        SmithsonianObject(
                            id=f"obj-{i}", title=f"Object {i}", unit_code="NMNH"
                        )
                        for i in range(5)
                    ],
                    total_count=20,
                    returned_count=5,
                    offset=0,
                    has_more=True,
                    next_offset=5,
                )

                first_result = await tools_module.simple_explore.fn(
                    topic="fossils", max_samples=5
                )
                assert len(first_result.objects) == 5
                seen_ids.extend([obj.id for obj in first_result.objects])

                # Continue exploration with deduplication
                mock_client_instance.search_collections.return_value = SearchResult(
                    objects=[
                        SmithsonianObject(
                            id=f"obj-{i+10}", title=f"Object {i+10}", unit_code="NMNH"
                        )
                        for i in range(5)
                    ],
                    total_count=20,
                    returned_count=5,
                    offset=5,
                    has_more=True,
                    next_offset=10,
                )

                continue_result = await tools_module.continue_explore.fn(
                    topic="fossils", previously_seen_ids=seen_ids, max_samples=5
                )

                # Verify no duplicates
                new_ids = [obj.id for obj in continue_result.objects]
                assert not any(
                    obj_id in seen_ids for obj_id in new_ids
                ), "Continue explore should not return duplicate objects"


class TestCrossToolDependencies:
    """Test interactions and dependencies between different MCP tools."""

    @pytest.mark.asyncio
    async def test_search_to_details_dependency(self):
        """Test that search results can be used with get_object_details."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import tools as tools_module

                # Search returns objects
                mock_client_instance.search_collections.return_value = SearchResult(
                    objects=[
                        SmithsonianObject(
                            id="interconnected-123",
                            title="Search Result Object",
                            unit_code="NMAH",
                        )
                    ],
                    total_count=1,
                    returned_count=1,
                    offset=0,
                    has_more=False,
                    next_offset=None,
                )

                search_result = await tools_module.search_collections.fn(
                    query="technology"
                )
                assert search_result.objects

                # Get details for search result object
                mock_client_instance.get_object_by_id.return_value = SmithsonianObject(
                    id="interconnected-123",
                    title="Detailed Search Result Object",
                    unit_code="NMAH",
                    description="A detailed description",
                    images=[{"url": "http://example.com/image.jpg"}],
                )

                detail_result = await tools_module.get_object_details.fn(
                    object_id="interconnected-123"
                )
                assert detail_result.id == "interconnected-123"
                assert "detailed description" in detail_result.description

    @pytest.mark.asyncio
    async def test_unit_search_integration(self):
        """Test integration between get_smithsonian_units and search_by_unit."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import tools as tools_module

                # Get units first
                mock_client_instance.get_units.return_value = [
                    SmithsonianUnit(
                        code="SAAM", name="Smithsonian American Art Museum"
                    ),
                    SmithsonianUnit(code="NPG", name="National Portrait Gallery"),
                ]

                units = await tools_module.get_smithsonian_units.fn()
                saam_unit = next(unit for unit in units if unit.code == "SAAM")

                # Use unit code for targeted search
                mock_client_instance.search_collections.return_value = SearchResult(
                    objects=[
                        SmithsonianObject(
                            id="art-123",
                            title="American Art Piece",
                            unit_code="SAAM",
                            unit_name=saam_unit.name,
                        )
                    ],
                    total_count=1,
                    returned_count=1,
                    offset=0,
                    has_more=False,
                    next_offset=None,
                )

                unit_search_result = await tools_module.search_by_unit.fn(
                    unit_code="SAAM", query="painting"
                )
                assert unit_search_result.objects
                assert all(
                    obj.unit_code == "SAAM" for obj in unit_search_result.objects
                )

    @pytest.mark.asyncio
    async def test_on_view_search_reliability(self):
        """Test that find_on_view_items provides more reliable results than basic on_view filter."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import tools as tools_module

                # Mock reliable local filtering results
                mock_reliable_objects = [
                    SmithsonianObject(
                        id="reliable-1", title="Reliable On-View Item", is_on_view=True
                    ),
                    SmithsonianObject(
                        id="reliable-2", title="Another On-View Item", is_on_view=True
                    ),
                ]

                mock_client_instance.search_collections.return_value = SearchResult(
                    objects=mock_reliable_objects,
                    total_count=2,
                    returned_count=2,
                    offset=0,
                    has_more=False,
                    next_offset=None,
                )

                # Test find_on_view_items (reliable approach)
                reliable_result = await tools_module.find_on_view_items.fn(
                    query="exhibition"
                )
                assert all(obj.is_on_view for obj in reliable_result.objects)
                assert len(reliable_result.objects) == 2


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases in MCP workflows."""

    @pytest.mark.asyncio
    async def test_empty_search_results_handling(self):
        """Test handling of empty search results across tools."""
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

                # Test various tools with empty results
                search_result = await tools_module.search_collections.fn(
                    query="nonexistenttopic12345"
                )
                assert search_result.objects == []
                assert search_result.total_count == 0

                explore_result = await tools_module.simple_explore.fn(
                    topic="nonexistenttopic12345"
                )
                assert explore_result.objects == []

                on_view_result = await tools_module.get_objects_on_view.fn()
                assert on_view_result.objects == []

    @pytest.mark.asyncio
    async def test_invalid_object_id_handling(self):
        """Test handling of invalid object IDs."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import (
                    tools as tools_module,
                    resources as resources_module,
                )

                # Mock not found result
                mock_client_instance.get_object_by_id.return_value = None

                result = await tools_module.get_object_details.fn(
                    object_id="invalid-id-12345"
                )
                assert result is None

                context_result = await resources_module.get_object_context.fn(
                    object_id="invalid-id-12345"
                )
                assert "not found" in context_result.lower()

    @pytest.mark.asyncio
    async def test_rate_limiting_simulation(self):
        """Test behavior under simulated rate limiting conditions."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import tools as tools_module

                # Simulate rate limit error
                mock_client_instance.search_collections.side_effect = Exception(
                    "Rate limit exceeded"
                )

                with pytest.raises(Exception) as exc_info:
                    await tools_module.search_collections.fn(query="test")
                assert "Rate limit exceeded" in str(exc_info.value)


class TestMCPContextTools:
    """Test context-specific tools that provide formatted data."""

    @pytest.mark.asyncio
    async def test_context_tools_formatting(self):
        """Test that context tools return properly formatted strings."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import resources as resources_module

                # Mock search context data
                mock_search_result = SearchResult(
                    objects=[
                        SmithsonianObject(
                            id="ctx-123",
                            title="Context Test Object",
                            unit_name="Test Museum",
                            unit_code="TEST",
                        )
                    ],
                    total_count=1,
                    returned_count=1,
                    offset=0,
                    has_more=False,
                    next_offset=None,
                )
                mock_client_instance.search_collections.return_value = (
                    mock_search_result
                )

                # Test search context formatting
                search_context = await resources_module.get_search_context.fn(
                    query="test"
                )
                assert "Search Results for 'test'" in search_context
                assert "Context Test Object" in search_context
                assert "Test Museum" in search_context

                # Test units context formatting
                mock_units = [
                    SmithsonianUnit(
                        code="TEST", name="Test Museum", description="A test museum"
                    ),
                ]
                mock_client_instance.get_units.return_value = mock_units

                units_context = await resources_module.get_units_context.fn()
                assert "Smithsonian Institution Museums" in units_context

    @pytest.mark.asyncio
    async def test_on_view_context_filtering(self):
        """Test that on_view_context properly filters and formats on-view objects."""
        mock_client_instance = AsyncMock(spec=SmithsonianAPIClient)

        with patch("smithsonian_mcp.context._global_api_client", None):
            with patch("smithsonian_mcp.context.create_client") as mock_create_client:
                mock_create_client.return_value = mock_client_instance

                from smithsonian_mcp import resources as resources_module

                # Mix of on-view and not-on-view objects
                mock_mixed_objects = [
                    SmithsonianObject(
                        id="on-view-1",
                        title="On View Object",
                        unit_name="Test Museum",
                        is_on_view=True,
                        object_type="Painting",
                    ),
                    SmithsonianObject(
                        id="storage-1",
                        title="In Storage Object",
                        unit_name="Test Museum",
                        is_on_view=False,
                    ),
                ]

                mock_result = SearchResult(
                    objects=mock_mixed_objects,
                    total_count=2,
                    returned_count=2,
                    offset=0,
                    has_more=False,
                    next_offset=None,
                )
                mock_client_instance.search_collections.return_value = mock_result

                on_view_context = await resources_module.get_on_view_context.fn()

                # Should only include on-view objects
                assert "On View Object" in on_view_context
                assert "In Storage Object" not in on_view_context
                assert "Currently on exhibit" in on_view_context
                assert "Type: Painting" in on_view_context


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
