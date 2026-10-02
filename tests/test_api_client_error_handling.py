"""
Tests for API client error handling paths.
"""

import pytest
from unittest.mock import AsyncMock, call

from smithsonian_mcp.api_client import SmithsonianAPIClient
from smithsonian_mcp.models import APIError, CollectionSearchFilter, SmithsonianObject

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
async def test_get_object_by_id_partial_id_fallback(monkeypatch):
    """get_object_by_id should try multiple ID formats when partial ID fails."""
    client = SmithsonianAPIClient(api_key="test")

    # The ID as given fails; the EDAN URL form (edanmdm:<record id>) succeeds
    mock_request = AsyncMock()
    mock_request.side_effect = [
        APIError(  # First call with the record ID as given fails
            error="http_error",
            message="not found",
            status_code=404,
            details=None,
        ),
        {"response": {"id": "edanmdm:test_123", "title": "Test Object"}},
    ]

    monkeypatch.setattr(client, "_make_request", mock_request)

    result = await client.get_object_by_id("test_123")

    assert result is not None
    assert result.id == "edanmdm:test_123"
    assert result.title == "Test Object"

    # The ID as given is tried first and the lookup stops on the first success
    assert mock_request.call_args_list == [
        call("/content/test_123"),
        call("/content/edanmdm:test_123"),
    ]


@pytest.mark.asyncio
async def test_get_object_by_id_legacy_dash_id_uses_colon_form(monkeypatch):
    """A legacy edanmdm- ID is retried as an edanmdm: EDAN URL."""
    client = SmithsonianAPIClient(api_key="test")
    not_found = APIError(
        error="not_found", message="not found", status_code=404, details=None
    )
    mock_request = AsyncMock(
        side_effect=[not_found, {"response": {"id": "ld1-1", "title": "Found"}}]
    )
    monkeypatch.setattr(client, "_make_request", mock_request)

    result = await client.get_object_by_id("edanmdm-nmah_1448973")

    assert result is not None and result.title == "Found"
    assert mock_request.call_args_list == [
        call("/content/edanmdm-nmah_1448973"),
        call("/content/edanmdm:nmah_1448973"),
    ]


@pytest.mark.asyncio
async def test_get_object_by_id_search_id_single_request(monkeypatch):
    """Search IDs (ld1-...) and EDAN URLs need no fallback requests."""
    client = SmithsonianAPIClient(api_key="test")
    mock_request = AsyncMock(
        side_effect=APIError(
            error="not_found", message="not found", status_code=404, details=None
        )
    )
    monkeypatch.setattr(client, "_make_request", mock_request)

    assert await client.get_object_by_id("ld1-1643398912743-1643398933001-0") is None
    assert await client.get_object_by_id("edanmdm:nmah_1448973") is None
    assert mock_request.call_count == 2


@pytest.mark.asyncio
async def test_get_object_by_id_full_id_direct_success(monkeypatch):
    """get_object_by_id should work directly with full ID."""
    client = SmithsonianAPIClient(api_key="test")

    mock_request = AsyncMock(
        return_value={"response": {"id": "edanmdm-test_123", "title": "Test Object"}}
    )
    monkeypatch.setattr(client, "_make_request", mock_request)

    result = await client.get_object_by_id("edanmdm-test_123")

    assert result is not None
    assert result.id == "edanmdm-test_123"

    # Should only try the full ID once
    mock_request.assert_called_once_with("/content/edanmdm-test_123")


@pytest.mark.asyncio
async def test_get_object_by_id_all_formats_fail(monkeypatch):
    """get_object_by_id should return None when all ID formats fail."""
    client = SmithsonianAPIClient(api_key="test")

    mock_request = AsyncMock(
        side_effect=APIError(
            error="http_error",
            message="not found",
            status_code=404,
            details=None,
        )
    )
    monkeypatch.setattr(client, "_make_request", mock_request)

    result = await client.get_object_by_id("test_123")

    assert result is None

    # Tried the ID as given and as an EDAN URL
    assert mock_request.call_count == 2
