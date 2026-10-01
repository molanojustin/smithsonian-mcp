"""
Tests that the API key never reaches request URLs or log output.
"""

import logging

import httpx
import pytest

from smithsonian_mcp.api_client import SmithsonianAPIClient
from smithsonian_mcp.models import APIError, CollectionSearchFilter

pytest.importorskip("pytest_asyncio")

SECRET = "SECRET-test-key-0123456789"


def _handler(request: httpx.Request) -> httpx.Response:
    """Serve canned responses for the endpoints the client uses."""
    path = request.url.path
    if path.endswith("/search"):
        return httpx.Response(200, json={"response": {"rows": [], "rowCount": 0}})
    if path.endswith("/stats"):
        return httpx.Response(500, json={"error": "boom"})
    if "/content/" in path:
        return httpx.Response(404, json={"response": {"error": "not found"}})
    if path.endswith("/terms/unit_code"):
        return httpx.Response(200, json={"response": {"terms": ["NMAH"]}})
    return httpx.Response(429, json={})


@pytest.mark.asyncio
async def test_api_key_only_in_header_and_never_logged(caplog):
    """Exercise every request path at DEBUG and check URLs and logs for the key."""
    requests = []

    def recording_handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _handler(request)

    caplog.set_level(logging.DEBUG)
    for name in ("httpx", "httpcore", "smithsonian_mcp"):
        logging.getLogger(name).setLevel(logging.DEBUG)

    client = SmithsonianAPIClient(
        api_key=SECRET, transport=httpx.MockTransport(recording_handler)
    )
    try:
        await client.search_collections(
            CollectionSearchFilter(query="muppet", unit_code="NMAH", on_view=True)
        )
        await client.get_object_by_id("nmah_1448973")
        await client.get_units()
        with pytest.raises(APIError):
            await client._make_request("stats")
        with pytest.raises(APIError):
            await client._make_request("other", {"api_key": SECRET, "q": "x"})
    finally:
        await client.disconnect()
        logging.getLogger("httpx").setLevel(logging.NOTSET)
        logging.getLogger("httpcore").setLevel(logging.NOTSET)
        logging.getLogger("smithsonian_mcp").setLevel(logging.NOTSET)

    assert len(requests) >= 5
    for request in requests:
        assert SECRET not in str(request.url)
        assert "api_key" not in str(request.url)
        assert request.headers["X-Api-Key"] == SECRET
        assert request.headers["User-Agent"].startswith("smithsonian-mcp/")

    # httpx logs each request URL; the key must not appear anywhere
    assert any("HTTP Request" in r.getMessage() for r in caplog.records)
    assert SECRET not in caplog.text
    for record in caplog.records:
        assert SECRET not in record.getMessage()


@pytest.mark.asyncio
async def test_api_key_not_in_error_messages():
    """Transport errors are wrapped without exposing the key."""

    def failing_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = SmithsonianAPIClient(
        api_key=SECRET, transport=httpx.MockTransport(failing_handler)
    )
    try:
        with pytest.raises(APIError) as excinfo:
            await client._make_request("search", {"q": "test"})
    finally:
        await client.disconnect()

    assert excinfo.value.error == "request_error"
    assert SECRET not in str(excinfo.value)
    assert SECRET not in repr(excinfo.value.details)
