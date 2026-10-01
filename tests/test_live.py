"""
Live tests against the Smithsonian Open Access API.

Skipped unless SMITHSONIAN_LIVE_TESTS=1 and an API key is configured (environment
or .env). Each test compares the client with a direct API query where possible.
"""

import time
from typing import Dict, Set

import httpx
import pytest
import pytest_asyncio

from smithsonian_mcp.api_client import (
    BASE_URL,
    SmithsonianAPIClient,
    build_search_query,
)
from smithsonian_mcp.config import Config
from smithsonian_mcp.models import CollectionSearchFilter
from smithsonian_mcp.utils import resolve_museum_code

pytest.importorskip("pytest_asyncio")

pytestmark = [pytest.mark.live, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def client():
    """A connected client using the configured API key."""
    if not Config.validate_api_key():
        pytest.skip("SMITHSONIAN_API_KEY is not configured")
    api_client = SmithsonianAPIClient()
    await api_client.connect()
    yield api_client
    await api_client.disconnect()


async def _direct_ids(query: str) -> Dict[str, str]:
    """Run a raw query against the API, paging through all rows."""
    found: Dict[str, str] = {}
    async with httpx.AsyncClient(
        timeout=60, headers={"X-Api-Key": Config.API_KEY}
    ) as http:
        start = 0
        while True:
            response = await http.get(
                BASE_URL + "search", params={"q": query, "start": start, "rows": 100}
            )
            response.raise_for_status()
            data = response.json()["response"]
            for row in data["rows"]:
                found[row["id"]] = row["title"]
            start += 100
            if start >= data["rowCount"]:
                return found


async def _direct_count(query: str) -> int:
    async with httpx.AsyncClient(
        timeout=60, headers={"X-Api-Key": Config.API_KEY}
    ) as http:
        response = await http.get(BASE_URL + "search", params={"q": query, "rows": 0})
        response.raise_for_status()
        return response.json()["response"]["rowCount"]


async def _direct_rows(query: str, rows: int = 100) -> list:
    async with httpx.AsyncClient(
        timeout=60, headers={"X-Api-Key": Config.API_KEY}
    ) as http:
        response = await http.get(
            BASE_URL + "search", params={"q": query, "rows": rows}
        )
        response.raise_for_status()
        return response.json()["response"]["rows"]


async def _client_ids(client, **filters) -> Set[str]:
    result = await client.search_collections(
        CollectionSearchFilter(limit=1000, **filters)
    )
    assert not result.has_more, "test expects a single page"
    return {obj.id for obj in result.objects}


async def test_muppets_on_view_at_nmah_match_direct_query(client):
    """The NMAH on-view Muppet search returns exactly the live API result set."""
    expected = await _direct_ids(
        '(muppet) AND unit_code:NMAH AND onPhysicalExhibit:"Yes"'
    )
    result = await client.search_collections(
        CollectionSearchFilter(query="muppet", unit_code="NMAH", on_view=True, limit=50)
    )

    assert expected, "expected some Muppet objects on view at NMAH"
    assert {obj.id for obj in result.objects} == set(expected)
    assert result.total_count == len(expected)
    assert all(obj.is_on_view and obj.unit_code == "NMAH" for obj in result.objects)


async def test_boolean_query_with_filters_matches_direct_query(client):
    terms = 'muppet OR muppets OR henson OR "sesame street"'
    expected = await _direct_ids(
        f'({terms}) AND unit_code:NMAH AND onPhysicalExhibit:"Yes"'
    )
    got = await _client_ids(client, query=terms, unit_code="NMAH", on_view=True)
    assert got == set(expected)


async def test_museum_name_resolves_to_nmah(client):
    code = resolve_museum_code("American History")
    assert code == "NMAH"
    got = await _client_ids(client, query="muppet", unit_code=code, on_view=True)
    expected = await _direct_ids(
        '(muppet) AND unit_code:NMAH AND onPhysicalExhibit:"Yes"'
    )
    assert got == set(expected)


@pytest.mark.parametrize(
    "query,reference",
    [
        ("Lewis & Clark", "Lewis & Clark"),
        ("rock & roll", "rock & roll"),
        ("Procter & Gamble", "Procter & Gamble"),
        ("Kermit — Muppets", "Kermit — Muppets"),
        ("Star Wars : A New Hope", "Star AND Wars AND A AND New AND Hope"),
        ("What is the Hope Diamond?", "What AND is AND the AND Hope AND Diamond"),
        (
            "Who made the Star Spangled Banner?",
            "Who AND made AND the AND Star AND Spangled AND Banner",
        ),
    ],
)
async def test_punctuation_in_queries_is_ignored(client, query, reference):
    result = await client.search_collections(
        CollectionSearchFilter(query=query, limit=0)
    )
    assert result.total_count > 0
    assert result.total_count == await _direct_count(reference)


async def test_multi_word_query_requires_all_words(client):
    got = await client.search_collections(
        CollectionSearchFilter(query="bert puppet", unit_code="NMAH", limit=0)
    )
    assert got.total_count == await _direct_count("bert AND puppet AND unit_code:NMAH")
    assert got.total_count < await _direct_count("(bert OR puppet) AND unit_code:NMAH")


@pytest.mark.parametrize(
    "filters,direct",
    [
        ({"has_images": True}, '(landscape) AND online_media_type:"Images"'),
        ({"is_cc0": True}, '(landscape) AND media_usage:"CC0"'),
        ({"on_view": True}, '(landscape) AND onPhysicalExhibit:"Yes"'),
        ({"unit_code": "SAAM"}, "(landscape) AND unit_code:SAAM"),
    ],
)
async def test_filters_narrow_results_like_direct_queries(client, filters, direct):
    result = await client.search_collections(
        CollectionSearchFilter(query="landscape", limit=0, **filters)
    )
    total = await _direct_count("landscape")
    assert result.total_count == await _direct_count(direct)
    assert 0 < result.total_count < total


@pytest.mark.parametrize(
    "filters,direct",
    [
        ({"object_type": "Paintings"}, '(landscape) AND object_type:"Paintings"'),
        ({"object_type": "painting"}, '(landscape) AND object_type:"Paintings"'),
        ({"topic": "Landscapes"}, '(landscape) AND topic:"Landscapes"'),
    ],
)
async def test_vocabulary_filters_contain_exact_matches(client, filters, direct):
    """Vocabulary filters add qualified terms to the exact match, never lose it."""
    query = build_search_query(CollectionSearchFilter(query="landscape", **filters))
    result = await client.search_collections(
        CollectionSearchFilter(query="landscape", limit=0, **filters)
    )
    exact = await _direct_count(direct)
    assert exact <= result.total_count < await _direct_count("landscape")
    assert await _direct_count(f"{query} AND {direct}") == exact


@pytest.mark.parametrize(
    "field,value,reference",
    [
        # Qualified index terms the exact value alone does not match
        ("object_type", "dress", 'object_type:"Dresses (garments)"'),
        ("object_type", "coin", 'object_type:"Coins (money)"'),
        ("object_type", "camera", 'object_type:"Cameras (photographic equipment)"'),
        ("topic", "civil war", 'topic:"Civil War, 1861-1865"'),
        ("topic", "African American", 'topic:"African American women"'),
        ("maker", "Martin Luther King Jr.", 'name:"King, Martin Luther"'),
        ("maker", "Lockheed", 'name:"Lockheed Aircraft Corporation"'),
        ("maker", "Wright Brothers", 'name:"Wright Brothers Quartet"'),
        # Cases that already worked keep every record they matched
        ("object_type", "painting", 'object_type:"Paintings"'),
        ("object_type", "PAINTINGS", 'object_type:"Paintings"'),
        ("topic", "Dinosaurs", 'topic:"Dinosaurs"'),
        ("maker", "alma thomas", 'name:"Thomas, Alma"'),
        ("maker", "Jim Henson", 'name:"Henson, Jim"'),
    ],
)
async def test_vocabulary_filters_include_qualified_terms(
    client, field, value, reference
):
    query = build_search_query(CollectionSearchFilter(**{field: value}))
    expected = await _direct_count(f"* AND {reference}")
    result = await client.search_collections(
        CollectionSearchFilter(limit=0, **{field: value})
    )
    assert expected > 0
    assert result.total_count >= expected
    assert await _direct_count(f"{query} AND {reference}") == expected


async def test_vocabulary_filters_do_not_use_bare_prefixes(client):
    hats = await client.search_collections(
        CollectionSearchFilter(object_type="hat", limit=0)
    )
    bare = await _direct_count("* AND object_type:(Hat* OR hat*)")
    assert 0 < hats.total_count < bare  # "Hatchets", "Hatpins" are excluded
    smith = await client.search_collections(
        CollectionSearchFilter(maker="Smith", limit=0)
    )
    assert smith.total_count < await _direct_count("* AND name:Smith*")


async def test_not_on_view_is_complement_of_on_view(client):
    total = await _direct_count("landscape")
    on_view = await _direct_count('(landscape) AND onPhysicalExhibit:"Yes"')
    result = await client.search_collections(
        CollectionSearchFilter(query="landscape", on_view=False, limit=0)
    )
    assert result.total_count == total - on_view


async def test_maker_material_and_date_filters(client):
    homer = await client.search_collections(
        CollectionSearchFilter(maker="Winslow Homer", limit=20)
    )
    assert homer.total_count > 100
    assert any("Homer" in " ".join(obj.maker) for obj in homer.objects)

    oil = await client.search_collections(
        CollectionSearchFilter(
            query="landscape", unit_code="SAAM", material="oil on canvas", limit=0
        )
    )
    assert 0 < oil.total_count < await _direct_count("(landscape) AND unit_code:SAAM")

    dated = await client.search_collections(
        CollectionSearchFilter(
            query="landscape", date_start="1950", date_end="1969", limit=0
        )
    )
    assert dated.total_count == await _direct_count(
        '(landscape) AND (date:"1950s" OR date:"1960s")'
    )


async def test_asian_art_and_natural_history_units(client):
    asian = await client.search_collections(
        CollectionSearchFilter(unit_code=resolve_museum_code("Asian Art"), limit=20)
    )
    assert asian.total_count > 1000
    assert {obj.unit_code for obj in asian.objects} == {"NMAA"}

    dinos = await client.search_collections(
        CollectionSearchFilter(
            query="dinosaur",
            unit_code=resolve_museum_code("Natural History"),
            limit=100,
        )
    )
    assert dinos.total_count == await _direct_count("(dinosaur) AND unit_code:NMNH*")
    assert dinos.objects
    assert all(obj.unit_code.startswith("NMNH") for obj in dinos.objects)

    legacy = await client.search_collections(
        CollectionSearchFilter(unit_code="FSG", limit=0)
    )
    assert legacy.total_count == asian.total_count


async def test_date_filters_use_whole_decades(client):
    closed = await client.search_collections(
        CollectionSearchFilter(date_start="1940", date_end="1960", limit=0)
    )
    assert closed.total_count == await _direct_count(
        '* AND (date:"1940s" OR date:"1950s" OR date:"1960s")'
    )
    # An open start must not reach three-digit decades or text values
    query = build_search_query(CollectionSearchFilter(date_start="1863"))
    assert await _direct_count(f'{query} AND date:"900s"') <= await _direct_count(
        '* AND date:"900s" AND date:("1860s" OR "1870s" OR "1880s" OR "1890s" OR '
        '"1900s" OR "1910s" OR "1920s" OR "1930s" OR "1940s" OR "1950s" OR "1960s" '
        'OR "1970s" OR "1980s" OR "1990s" OR "2000s" OR "2010s" OR "2020s")'
    )
    open_start = await client.search_collections(
        CollectionSearchFilter(date_start="1863", limit=0)
    )
    assert open_start.total_count < await _direct_count('* AND date:["1860s" TO *]')


async def test_firewall_rejection_is_reported_as_query_problem(client):
    from smithsonian_mcp.models import APIError

    for query in ["<script>alert(1)</script>", "../../etc/passwd"]:
        with pytest.raises(APIError) as excinfo:
            await client.search_collections(
                CollectionSearchFilter(query=query, limit=0)
            )
        assert excinfo.value.error == "query_rejected"
    bad_key = SmithsonianAPIClient(api_key="INVALID-KEY-FOR-TEST")
    try:
        with pytest.raises(APIError) as excinfo:
            await bad_key.search_collections(CollectionSearchFilter(query="x", limit=0))
    finally:
        await bad_key.disconnect()
    assert excinfo.value.error == "api_key_rejected"


async def test_invalid_date_is_rejected(client):
    with pytest.raises(ValueError):
        await client.search_collections(CollectionSearchFilter(date_start="500"))


async def test_rows_above_limit_are_clamped(client):
    result = await client.search_collections(
        CollectionSearchFilter(query="art", limit=1500)
    )
    assert result.returned_count == 1000


async def test_collection_stats_are_fast(client):
    start = time.monotonic()
    stats = await client.get_collection_stats()
    elapsed = time.monotonic() - start
    assert elapsed < 2.0, f"stats took {elapsed:.2f}s"
    assert stats.total_objects > 1_000_000
    assert stats.total_cc0 and stats.total_with_images
    assert any(unit.unit_code == "NMAH" for unit in stats.units)


async def test_units_come_from_terms_endpoint(client):
    SmithsonianAPIClient.clear_unit_code_cache()
    units = await client.get_units()
    codes = {unit.code for unit in units}
    assert {"NMAA", "NMAH", "NMNH", "NMNHPALEO", "SAAM"} <= codes
    assert "FSG" not in codes


async def test_get_object_by_id_formats(client):
    result = await client.search_collections(
        CollectionSearchFilter(query="muppet", unit_code="NMAH", on_view=True, limit=1)
    )
    first = result.objects[0]
    by_search_id = await client.get_object_by_id(first.id)
    assert by_search_id is not None and by_search_id.id == first.id
    assert by_search_id.record_id
    by_record_id = await client.get_object_by_id(by_search_id.record_id)
    assert by_record_id is not None and by_record_id.id == first.id
    assert await client.get_object_by_id("ld1-does-not-exist") is None


async def test_titles_are_plain_text(client):
    # The API title of nmah_1182905 is "<i>The Muppets</i> Lunch Box"
    result = await client.search_collections(
        CollectionSearchFilter(query="muppets lunch box", unit_code="NMAH", limit=20)
    )
    titles = [obj.title for obj in result.objects]
    assert "The Muppets Lunch Box" in titles
    assert all("<" not in title for title in titles)


NON_CREATOR_LABELS = {
    "sitter",
    "seller",
    "culture/people",
    "previous owner",
    "collector",
    "donor name",
    "subject of",
    "owned by",
    "taxon",
    "site name",
}


@pytest.mark.parametrize(
    "unit",
    ["SAAM", "NPG", "NMAH", "NASM", "NMAA", "NMAI", "CHNDM", "NMAAHC", "NMNHMINSCI"],
)
async def test_makers_exclude_non_creators(client, unit):
    rows = await _direct_rows(f"unit_code:{unit}", rows=100)
    assert rows
    for row in rows:
        obj = client._parse_object_data(row)
        entries = row["content"].get("freetext", {}).get("name") or []
        creators = {
            entry.get("content")
            for entry in entries
            if (entry.get("label") or "").lower() not in NON_CREATOR_LABELS
        }
        for entry in entries:
            if (entry.get("label") or "").lower() in NON_CREATOR_LABELS:
                content = entry.get("content")
                assert content in creators or content not in obj.maker, row["id"]


async def test_hope_diamond_replica_has_no_maker(client):
    result = await client.search_collections(
        CollectionSearchFilter(
            query="Hope Diamond Replica", unit_code="NMNHMINSCI", limit=5
        )
    )
    assert result.objects
    assert all(obj.maker == [] for obj in result.objects)
