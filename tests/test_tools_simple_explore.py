"""
Targeted tests for simple_explore tool behaviour.
"""

import pytest
from unittest.mock import AsyncMock

from smithsonian_mcp.models import SmithsonianObject, SearchResult

pytest.importorskip("pytest_asyncio")


def _make_object(
    obj_id: str,
    title: str,
    unit_code: str | None,
    object_type: str | None = None,
) -> SmithsonianObject:
    """Create SmithsonianObject test fixtures with explicit optional fields."""
    return SmithsonianObject(
        id=obj_id,
        title=title,
        url=None,
        unit_code=unit_code,
        unit_name=None,
        object_type=object_type,
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
        models_3d=[],
        credit_line=None,
        rights=None,
        is_cc0=False,
        is_on_view=False,
        exhibition_title=None,
        exhibition_location=None,
        record_link=None,
        last_modified=None,
        raw_metadata={},
    )


@pytest.mark.asyncio
async def test_simple_explore_with_museum_branch(monkeypatch):
    """Ensure museum-specific sampling branch returns diverse but limited results."""
    from smithsonian_mcp import tools as tools_module

    museum_code = "NMNH"
    objects = [
        _make_object("obj-1", "Fossil A", museum_code, "Fossil"),
        _make_object("obj-2", "Fossil B", museum_code, "Fossil"),
        _make_object("obj-3", "Dinosaur Skeleton", museum_code, "Sculpture"),
        _make_object("obj-4", "Mineral Exhibit", museum_code, "Mineral"),
    ]
    mock_client = AsyncMock()
    mock_client.search_collections.return_value = SearchResult(
        objects=objects,
        total_count=len(objects),
        returned_count=len(objects),
        offset=0,
        has_more=False,
        next_offset=None,
    )

    monkeypatch.setattr(
        "smithsonian_mcp.tools.get_api_client",
        AsyncMock(return_value=mock_client),
    )

    result = await tools_module.simple_explore.fn(
        topic="dinosaurs",
        museum="National Museum of Natural History",
        max_samples=3,
    )

    assert len(result.objects) <= 10
    assert {obj.unit_code for obj in result.objects} == {museum_code}
    assert len({obj.object_type for obj in result.objects}) == 3
    mock_client.search_collections.assert_awaited()


@pytest.mark.asyncio
async def test_simple_explore_validation_fallback(monkeypatch):
    """Verify fallback path runs when validation raises ValueError."""
    from smithsonian_mcp import tools as tools_module

    fallback_objects = [
        _make_object("obj-5", "Fallback Result", None, None)
    ]
    mock_client = AsyncMock()
    mock_client.search_collections.return_value = SearchResult(
        objects=fallback_objects,
        total_count=1,
        returned_count=1,
        offset=0,
        has_more=False,
        next_offset=None,
    )

    monkeypatch.setattr(
        "smithsonian_mcp.tools.get_api_client",
        AsyncMock(return_value=mock_client),
    )

    result = await tools_module.simple_explore.fn(topic="a", max_samples=10)

    assert result.objects == fallback_objects
    mock_client.search_collections.assert_awaited_once()
