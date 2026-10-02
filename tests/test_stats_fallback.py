"""
Tests for collection statistics: /stats plus one count query, no sampling.
"""

import pytest

from smithsonian_mcp.api_client import SmithsonianAPIClient
from smithsonian_mcp.models import APIError

pytest.importorskip("pytest_asyncio")

STATS_RESPONSE = {
    "response": {
        "time": "2026-09",
        "total_objects": 1000,
        "metrics": {"CC0_records": 600, "CC0_records_with_CC0_media": 200},
        "units": [
            {
                "unit": "NMAH",
                "total_objects": 700,
                "metrics": {"CC0_records": 400, "CC0_records_with_CC0_media": 150},
                "data_source": "National Museum of American History",
            },
            {
                "unit": "NEWUNIT",
                "total_objects": 300,
                "metrics": {"CC0_records": 200, "CC0_records_with_CC0_media": 50},
                "data_source": "A New Unit",
            },
        ],
    }
}


def _fake_requests(stats_ok: bool = True, search_ok: bool = True):
    """Build a _make_request replacement that records calls."""
    calls = []

    async def fake(endpoint, params=None):
        calls.append((endpoint, params))
        if endpoint == "stats":
            if stats_ok:
                return STATS_RESPONSE
            raise APIError(error="http_error", message="stats down", status_code=500)
        if endpoint == "search":
            if not search_ok:
                raise APIError(
                    error="http_error", message="search down", status_code=500
                )
            counts = {"*": 120, 'online_media_type:"Images"': 45}
            return {"response": {"rows": [], "rowCount": counts[params["q"]]}}
        raise AssertionError(f"unexpected endpoint {endpoint}")

    return fake, calls


@pytest.mark.asyncio
async def test_stats_use_stats_endpoint_and_one_count_query(monkeypatch):
    """Totals, units and CC0 come from /stats; images from one rows=0 query."""
    client = SmithsonianAPIClient(api_key="test-key")
    fake, calls = _fake_requests()
    monkeypatch.setattr(client, "_make_request", fake)

    stats = await client.get_collection_stats()

    assert len(calls) == 2
    search_calls = [params for endpoint, params in calls if endpoint == "search"]
    assert search_calls == [{"q": 'online_media_type:"Images"', "start": 0, "rows": 0}]
    assert stats.total_objects == 1000
    assert stats.total_cc0 == 600
    assert stats.total_cc0_objects_with_cc0_media == 200
    assert stats.total_with_images == 45
    assert stats.object_type_breakdown is None
    assert stats.last_updated.year == 2026 and stats.last_updated.month == 9
    assert [u.unit_code for u in stats.units] == ["NMAH", "NEWUNIT"]
    nmah = stats.units[0]
    assert nmah.unit_name == "National Museum of American History"
    assert (nmah.total_objects, nmah.cc0_objects) == (700, 400)
    assert nmah.cc0_objects_with_cc0_media == 150
    assert nmah.objects_with_images is None
    assert stats.units[1].unit_name == "A New Unit"


@pytest.mark.asyncio
async def test_stats_tolerate_failed_image_count(monkeypatch):
    """A failed image count leaves total_with_images unset."""
    client = SmithsonianAPIClient(api_key="test-key")
    fake, _ = _fake_requests(search_ok=False)
    monkeypatch.setattr(client, "_make_request", fake)

    stats = await client.get_collection_stats()

    assert stats.total_objects == 1000
    assert stats.total_with_images is None


@pytest.mark.asyncio
async def test_stats_raise_when_everything_fails(monkeypatch):
    """If /stats and the count queries all fail, an APIError is raised."""
    client = SmithsonianAPIClient(api_key="test-key")
    fake, _ = _fake_requests(stats_ok=False, search_ok=False)
    monkeypatch.setattr(client, "_make_request", fake)

    with pytest.raises(APIError) as excinfo:
        await client.get_collection_stats()
    assert excinfo.value.error == "stats_failed"
