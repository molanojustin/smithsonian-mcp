"""
Tests for API client error handling paths.
"""

import pytest
from unittest.mock import AsyncMock

from smithsonian_mcp.api_client import SmithsonianAPIClient, CollectionSearchFilter
from smithsonian_mcp.models import APIError

pytest.importorskip("pytest_asyncio")


@pytest.mark.asyncio
async def test_get_object_by_id_returns_none_on_404(monkeypatch):
    """get_object_by_id should swallow 404s and return None."""
    client = SmithsonianAPIClient(api_key="test")

    monkeypatch.setattr(
        client,
        "_make_request",
        AsyncMock(
            side_effect=APIError(
                error="http_error",
                message="not found",
                status_code=404,
                details=None,
            )
        ),
    )

    result = await client.get_object_by_id("missing-id")

    assert result is None


@pytest.mark.asyncio
async def test_search_collections_with_3d_filter(monkeypatch):
    """
    Verify that the 3D filter uses the correct '3D Models' term.
    """
    client = SmithsonianAPIClient(api_key="test")
    mock_make_request = AsyncMock(return_value={'response': {'rows': [], 'rowCount': 0}})
    monkeypatch.setattr(client, "_make_request", mock_make_request)

    filters = CollectionSearchFilter(has_3d=True)
    await client.search_collections(filters)

    mock_make_request.assert_called_once()
    call_args = mock_make_request.call_args
    assert len(call_args.args) == 2
    params = call_args.args[1]
    assert 'fq' in params
    assert 'online_media_type:"3D Models"' in params['fq']