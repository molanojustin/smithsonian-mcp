"""
Tests for API client error handling paths.
"""

import pytest
from unittest.mock import AsyncMock

from smithsonian_mcp.api_client import SmithsonianAPIClient
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
