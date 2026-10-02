"""
Live tests of the MCP tools against the Smithsonian Open Access API.

Skipped unless SMITHSONIAN_LIVE_TESTS=1 and an API key is configured. Tools run
through an in-memory fastmcp Client; about 15 API requests in total.
"""

import json
from typing import Any, Dict

import httpx
import pytest
from fastmcp import Client

from smithsonian_mcp.api_client import BASE_URL
from smithsonian_mcp.app import mcp
from smithsonian_mcp.config import Config

pytestmark = [pytest.mark.live, pytest.mark.asyncio]

ELMO_ID = "ld1-1643398912743-1643398932982-0"


@pytest.fixture(autouse=True)
def _require_key():
    """Skip when no API key is configured."""
    if not Config.validate_api_key():
        pytest.skip("SMITHSONIAN_API_KEY is not configured")


async def call(name: str, args: Dict[str, Any] = None) -> Any:
    """Call a tool; return (structured result, response size in tokens)."""
    async with Client(mcp) as client:
        result = await client.call_tool(name, args or {})
    text = "".join(getattr(block, "text", "") for block in result.content)
    return result.structured_content, len(text) / 4


async def call_error(name: str, args: Dict[str, Any]) -> str:
    """Call a tool that must fail; return the error text."""
    async with Client(mcp) as client:
        result = await client.call_tool(name, args, raise_on_error=False)
    assert result.is_error
    return "".join(getattr(block, "text", "") for block in result.content)


async def direct_on_view_ids(terms: str) -> Dict[str, str]:
    """Ids and exhibition titles of matching NMAH objects on view, queried directly."""
    query = f'({terms}) AND unit_code:NMAH AND onPhysicalExhibit:"Yes"'
    async with httpx.AsyncClient(
        timeout=60, headers={"X-Api-Key": Config.API_KEY}
    ) as http:
        response = await http.get(BASE_URL + "search", params={"q": query, "rows": 100})
        response.raise_for_status()
        data = response.json()["response"]
    assert data["rowCount"] <= 100
    return {
        row["id"]: (row["content"]["indexedStructured"].get("exhibition") or [{}])[
            0
        ].get("exhibitionTitle")
        for row in data["rows"]
    }


async def test_muppets_on_view_match_the_live_set():
    expected = await direct_on_view_ids("muppet")
    result, _ = await call(
        "search_objects",
        {"query": "muppet", "museum": "American History", "on_view": True, "limit": 50},
    )
    assert result["museum"]["code"] == "NMAH"
    got = {obj["id"]: obj.get("exhibition_title") for obj in result["objects"]}
    assert got == expected
    assert result["total_count"] == len(expected)
    assert all(obj["on_view"] for obj in result["objects"])


async def test_default_search_is_compact():
    result, tokens = await call("search_objects", {"query": "telescope"})
    assert result["returned"] == 10 and result["next_offset"] == 10
    assert tokens < 3000
    assert all(obj["id"] and obj["title"] for obj in result["objects"])


async def test_get_object_for_elmo():
    result, tokens = await call("get_object", {"object_id": ELMO_ID})
    assert result["title"] == "Elmo Puppet"
    assert result["record_id"] == "nmah_1444757"
    assert result["web_url"] == (
        "https://americanhistory.si.edu/collections/object/nmah_1444757"
    )
    assert result["exhibition_title"] == "Entertainment Nation"
    assert result["exhibition_location"] == "National Museum of American History"
    assert tokens < 2500


async def test_explore_topic_applies_the_topic_with_a_museum():
    result, tokens = await call(
        "explore_topic", {"topic": "dinosaurs", "museum": "Natural History"}
    )
    assert result["museum"]["code"] == "NMNH"
    assert result["returned"] == 12
    assert all(obj["museum_code"].startswith("NMNH") for obj in result["objects"])
    assert sum(result["facets"]["museums"].values()) >= result["returned"]
    assert tokens < 3000


async def test_natural_history_on_view_has_a_note():
    result, _ = await call(
        "search_objects",
        {"query": "dinosaur", "museum": "Natural History", "on_view": True},
    )
    assert result["total_count"] == 0
    assert "NMNH" in result["note"]


async def test_archival_only_museum_is_searched_as_archives():
    text = await call_error(
        "search_objects", {"query": "letters", "museum": "Archives of American Art"}
    )
    assert "record_type='archives'" in text
    result, _ = await call(
        "search_objects",
        {
            "query": "letters",
            "museum": "Archives of American Art",
            "record_type": "archives",
            "limit": 3,
        },
    )
    assert result["total_count"] > 1000 and result["returned"] == 3
    assert all(obj["museum_code"] == "AAA" for obj in result["objects"])
    assert all(obj.get("collection") for obj in result["objects"])


async def test_firewall_rejection_is_explained():
    text = await call_error("search_objects", {"query": "<script>alert(1)</script>"})
    assert "rephrase" in text


async def test_counts_agree_with_search_totals():
    museums, museums_tokens = await call("list_museums")
    listed = {museum["code"]: museum for museum in museums["result"]}
    assert "FSG" not in listed
    assert listed["AAA"]["record_types"] == ["archives"]
    assert listed["NASM"]["record_types"] == ["objects"]
    stats, stats_tokens = await call(
        "get_collection_stats", {"museum": "Air and Space"}
    )
    search, _ = await call("search_objects", {"museum": "NASM", "limit": 1})
    assert stats["objects"] == search["total_count"] > 0
    assert stats["objects"] >= stats["objects_with_images"]
    assert json.dumps(museums) and museums_tokens < 2500 and stats_tokens < 200
