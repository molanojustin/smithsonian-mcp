"""
Tests for collection statistics fallback handling.
"""
# TODO: FIX TEST
import pytest
from unittest.mock import AsyncMock

from smithsonian_mcp.api_client import SmithsonianAPIClient
from smithsonian_mcp.models import SearchResult, SmithsonianUnit, APIError

pytest.importorskip("pytest_asyncio")


@pytest.mark.asyncio
async def test_get_stats_context_handles_stats_endpoint_failure(monkeypatch):
    """Ensure stats context handles fallback data with missing metrics."""
    client = SmithsonianAPIClient(api_key="test-key")

    stats_failure = AsyncMock(
        side_effect=APIError(
            error="http_error",
            message="stats endpoint unavailable",
            status_code=500,
            details=None,
        )
    )
    monkeypatch.setattr(client, "_make_request", stats_failure)

    fallback_search_result = SearchResult(
        objects=[],
        total_count=120,
        returned_count=0,
        offset=0,
        has_more=False,
        next_offset=None,
    )
    monkeypatch.setattr(
        client,
        "search_collections",
        AsyncMock(return_value=fallback_search_result),
    )

    fallback_units = [
        SmithsonianUnit(code="NMAH", name="National Museum of American History"),
        SmithsonianUnit(code="NMNH", name="National Museum of Natural History"),
    ]
    monkeypatch.setattr(client, "get_units", AsyncMock(return_value=fallback_units))

    monkeypatch.setattr(
        "smithsonian_mcp.resources.get_api_client",
        AsyncMock(return_value=client),
    )

    from smithsonian_mcp import resources as resources_module

    result = await resources_module.get_stats_context.fn()

    assert "Total Objects: 120" in result
    assert "Digitized Objects: 120" in result
    assert "CC0 Licensed Objects: 120" in result
    assert "Objects with Images: 120" in result
    assert "Objects with 3D Models: 120" in result
    assert "  NMAH: 120" in result
    assert "  NMNH: 120" in result

    stats_failure.assert_awaited_once()
    assert client.search_collections.call_count == 12
    client.get_units.assert_awaited_once()
