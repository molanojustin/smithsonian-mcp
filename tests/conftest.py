"""
Shared pytest configuration.

Tests marked ``live`` call the real Smithsonian Open Access API and only run when
``SMITHSONIAN_LIVE_TESTS=1``. Every other test runs offline: outgoing HTTP is
blocked and a placeholder API key replaces any real one.
"""

import os

import httpx
import pytest

LIVE_TESTS_ENABLED = os.environ.get("SMITHSONIAN_LIVE_TESTS") == "1"

if not LIVE_TESTS_ENABLED:
    # Set before smithsonian_mcp.config is imported; environment variables take
    # precedence over the .env file.
    os.environ["SMITHSONIAN_API_KEY"] = "unit-test-placeholder-key"


def pytest_configure(config: pytest.Config) -> None:
    """Register the live marker."""
    config.addinivalue_line(
        "markers",
        "live: calls the live Smithsonian API; run with SMITHSONIAN_LIVE_TESTS=1",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list  # pylint: disable=unused-argument
) -> None:
    """Skip live tests unless SMITHSONIAN_LIVE_TESTS=1."""
    if LIVE_TESTS_ENABLED:
        return
    skip_live = pytest.mark.skip(
        reason="live API test; set SMITHSONIAN_LIVE_TESTS=1 to run"
    )
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture(autouse=True)
def _isolate_client_state(request: pytest.FixtureRequest, monkeypatch):
    """
    Block real network access in offline tests and reset shared client state.
    """
    from smithsonian_mcp import context
    from smithsonian_mcp.api_client import SmithsonianAPIClient

    if "live" not in request.keywords:

        async def _blocked(self, http_request):  # pylint: disable=unused-argument
            raise httpx.ConnectError(
                "Network access is disabled in offline tests", request=http_request
            )

        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _blocked)

    from smithsonian_mcp import tools

    SmithsonianAPIClient.clear_unit_code_cache()
    tools.clear_caches()
    previous_client = context.peek_api_client()
    yield
    context.set_api_client(previous_client)
    SmithsonianAPIClient.clear_unit_code_cache()
    tools.clear_caches()


@pytest.fixture
def fake_api(monkeypatch):
    """
    Answer the client's HTTP requests from a FakeAPI instead of the network.

    The real tool, client and parsing code all run; only the transport is faked.
    """
    from tests.fake_api import FakeAPI

    api = FakeAPI()

    async def _handle(self, http_request):  # pylint: disable=unused-argument
        return await api.handle(http_request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _handle)
    return api
