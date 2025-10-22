"""
Tests for API client error handling paths.
"""

import pytest
from unittest.mock import AsyncMock, call

from smithsonian_mcp.api_client import SmithsonianAPIClient, CollectionSearchFilter
from smithsonian_mcp.models import APIError, SmithsonianObject

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
    """get_object_by_id should try prefixed ID when partial ID fails."""
    client = SmithsonianAPIClient(api_key="test")

    # Mock _make_request to fail on partial ID but succeed on full ID
    mock_request = AsyncMock()
    mock_request.side_effect = [
        APIError(  # First call with partial ID fails
            error="http_error",
            message="not found",
            status_code=404,
            details=None,
        ),
        {"response": {"id": "edanmdm-test_123", "title": "Test Object"}}  # Second call with full ID succeeds
    ]

    monkeypatch.setattr(client, "_make_request", mock_request)

    result = await client.get_object_by_id("test_123")

    assert result is not None
    assert result.id == "edanmdm-test_123"
    assert result.title == "Test Object"

    # Verify both ID formats were tried
    expected_calls = [
        call("/content/test_123"),
        call("/content/edanmdm-test_123")
    ]
    mock_request.assert_has_calls(expected_calls)


@pytest.mark.asyncio
async def test_get_object_by_id_full_id_direct_success(monkeypatch):
    """get_object_by_id should work directly with full ID."""
    client = SmithsonianAPIClient(api_key="test")

    mock_request = AsyncMock(return_value={"response": {"id": "edanmdm-test_123", "title": "Test Object"}})
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

    # Should have tried both formats
    assert mock_request.call_count == 2


