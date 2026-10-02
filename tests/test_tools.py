"""
Offline tests of the MCP tools, run through an in-memory fastmcp Client.

The HTTP transport is replaced by tests.fake_api.FakeAPI, so the tool, client,
query building and parsing code all run without network access or a real key.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List

import httpx
import pytest
from fastmcp import Client

from smithsonian_mcp import __version__
from smithsonian_mcp.app import mcp
from smithsonian_mcp.tools import MAX_IMAGES, MAX_NOTES_CHARS
from tests.fake_api import (
    counting_search,
    html_403,
    key_403,
    make_row,
    search_payload,
)

FIXTURES = Path(__file__).parent
TOOL_NAMES = {
    "search_objects",
    "get_object",
    "list_museums",
    "explore_topic",
    "get_collection_stats",
}
MUPPETS = [
    make_row(
        "ld1-1643398912743-1643398932998-0",
        "Fozzie Bear Puppet",
        record_id="nmah_1448970",
        object_type="Puppets",
        makers=["Henson, Jim"],
        date="1976",
        on_view=True,
        exhibition="Entertainment Nation",
        building="NMAH",
    ),
    make_row(
        "ld1-1643399134763-1643399177676-0",
        "<i>The Muppets</i> Lunch Box",
        record_id="nmah_1310473",
        object_type="Lunch boxes",
        on_view=True,
        exhibition="Taking America To Lunch",
        building="NMAH",
        images=1,
    ),
]


def load_record(name: str) -> Dict[str, Any]:
    """Load a /content record saved from the live API."""
    with open(FIXTURES / name, encoding="utf-8") as handle:
        return json.load(handle)["response"]


async def call(name: str, args: Dict[str, Any] = None) -> Any:
    """Call a tool and return its structured result."""
    async with Client(mcp) as client:
        result = await client.call_tool(name, args or {})
    return result.structured_content


async def call_error(name: str, args: Dict[str, Any] = None) -> str:
    """Call a tool that must fail and return the error text."""
    async with Client(mcp) as client:
        result = await client.call_tool(name, args or {}, raise_on_error=False)
    assert result.is_error, result
    return "".join(getattr(block, "text", "") for block in result.content)


def find_nulls(value: Any, path: str = "") -> List[str]:
    """Paths of null values in a JSON structure, ignoring next_offset."""
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if item is None and key != "next_offset":
                found.append(f"{path}.{key}")
            found += find_nulls(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found += find_nulls(item, f"{path}[{index}]")
    return found


class TestRegistration:
    """The server exposes exactly the new tools, resources and prompts."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("module", ["smithsonian_mcp.app", "smithsonian_mcp"])
    async def test_both_import_paths_expose_everything(self, module):
        server = __import__(module, fromlist=["mcp"]).mcp
        assert server is mcp
        async with Client(server) as client:
            tools = await client.list_tools()
            resources = await client.list_resources()
            templates = await client.list_resource_templates()
            prompts = await client.list_prompts()
        assert {tool.name for tool in tools} == TOOL_NAMES
        assert [str(r.uri) for r in resources] == ["smithsonian://museums"]
        assert [t.uri_template for t in templates] == [
            "smithsonian://objects/{object_id}"
        ]
        assert {p.name for p in prompts} == {
            "collection_research",
            "object_analysis",
            "exhibition_planning",
            "educational_content",
            "museum_on_view",
        }

    @pytest.mark.asyncio
    async def test_server_info_and_instructions(self):
        async with Client(mcp) as client:
            assert client.server_info.version == __version__
            assert client.server_info.name == "Smithsonian Open Access"
            assert "web_url" in client.instructions
            assert "on_view" in client.instructions

    @pytest.mark.asyncio
    async def test_annotations_titles_and_budget(self):
        async with Client(mcp) as client:
            tools = await client.list_tools()
        total = 0
        for tool in tools:
            assert tool.title
            assert tool.annotations.read_only_hint is True
            assert tool.annotations.open_world_hint is True
            assert tool.annotations.idempotent_hint is True
            assert tool.output_schema
            total += len(
                json.dumps(
                    [tool.name, tool.description, tool.input_schema, tool.output_schema]
                )
            )
        assert total / 4 < 6000

    @pytest.mark.asyncio
    async def test_argument_descriptions_are_single_lines(self):
        async with Client(mcp) as client:
            tools = await client.list_tools()
        for tool in tools:
            for name, schema in tool.input_schema["properties"].items():
                description = schema.get("description", "")
                assert description == " ".join(description.split()), (tool.name, name)

    @pytest.mark.asyncio
    async def test_on_view_argument_carries_the_natural_history_caveat(self):
        async with Client(mcp) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
        description = tools["search_objects"].input_schema["properties"]["on_view"][
            "description"
        ]
        assert "Natural History (NMNH) has no exhibit data" in description

    @pytest.mark.asyncio
    async def test_descriptions_are_plain(self):
        async with Client(mcp) as client:
            tools = await client.list_tools()
            prompts = await client.list_prompts()
        text = json.dumps(
            [[t.description, t.input_schema] for t in tools]
            + [p.description for p in prompts]
        )
        assert text.isascii()
        assert not re.search(r"\b(IMPORTANT|CRITICAL|WARNING|NEVER|ALWAYS)\b", text)
        for removed in ("search_collections", "simple_search", "get_object_url"):
            assert removed not in text


class TestSearchObjects:
    """search_objects builds fielded queries and returns compact summaries."""

    @pytest.mark.asyncio
    async def test_muppets_on_view_at_american_history(self, fake_api):
        fake_api.search = lambda params: search_payload(MUPPETS)
        result = await call(
            "search_objects",
            {"query": "muppet", "museum": "American History", "on_view": True},
        )
        (params,) = fake_api.searches
        assert params["q"] == '(muppet) AND unit_code:NMAH AND onPhysicalExhibit:"Yes"'
        assert params["rows"] == "10" and params["start"] == "0"
        assert result["museum"] == {
            "code": "NMAH",
            "name": "National Museum of American History",
        }
        assert result["total_count"] == 2 and result["returned"] == 2
        assert result["next_offset"] is None
        fozzie, lunch_box = result["objects"]
        assert fozzie == {
            "id": "ld1-1643398912743-1643398932998-0",
            "title": "Fozzie Bear Puppet",
            "maker": ["Henson, Jim"],
            "date": "1976",
            "museum_code": "NMAH",
            "museum_name": "National Museum of American History",
            "object_type": "Puppets",
            "on_view": True,
            "exhibition_title": "Entertainment Nation",
            "exhibition_location": "National Museum of American History, Washington, DC",
            "web_url": "https://americanhistory.si.edu/collections/object/nmah_1448970",
        }
        assert lunch_box["title"] == "The Muppets Lunch Box"
        assert lunch_box["thumbnail_url"].startswith("https://ids.si.edu/")
        assert find_nulls(result) == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "museum, clause",
        [
            ("NMAH", "unit_code:NMAH"),
            ("Smithsonian National Museum of American History", "unit_code:NMAH"),
            ("Asian Art", "unit_code:NMAA"),
            ("FSG", "unit_code:NMAA"),
            ("Natural History", "unit_code:NMNH*"),
            ("nmafa", "unit_code:NMAfA"),
        ],
    )
    async def test_museum_names_and_codes_resolve(self, fake_api, museum, clause):
        result = await call("search_objects", {"museum": museum})
        assert fake_api.searches[0]["q"] == f"* AND {clause}"
        assert result["museum"]["code"] == clause.split(":")[1].rstrip("*")

    @pytest.mark.asyncio
    async def test_filters_become_fielded_clauses(self, fake_api):
        await call(
            "search_objects",
            {
                "query": "lunch box",
                "object_type": "Lunch boxes",
                "maker": "Jim Henson",
                "topic": "Television",
                "material": "metal",
                "date_from": 1965,
                "date_to": 1979,
                "has_images": True,
                "cc0_only": True,
                "on_view": False,
                "limit": 5,
                "offset": 10,
            },
        )
        params = fake_api.searches[0]
        query = params["q"]
        assert query.startswith("(lunch AND box) AND object_type:(")
        assert 'name:"Henson, Jim"' in query
        assert "topic:(" in query
        assert 'physicalDescription:"metal"' in query
        assert 'date:("1960s" OR "1970s")' in query
        assert 'online_media_type:"Images"' in query
        assert 'media_usage:"CC0"' in query
        assert '(* NOT onPhysicalExhibit:"Yes")' in query
        assert params["rows"] == "5" and params["start"] == "10"
        assert "sort" not in params

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "building, room, location",
        [
            (
                "HAZY",
                None,
                "Steven F. Udvar-Hazy Center, National Air and Space Museum, "
                "Chantilly, VA",
            ),
            (
                "Freer",
                "Gallery 19",
                "Freer Gallery of Art, National Museum of Asian Art, Gallery 19, "
                "Washington, DC",
            ),
            (
                "NMAI NY",
                None,
                "National Museum of the American Indian, George Gustav Heye Center, "
                "New York, NY",
            ),
            (
                "HAC",
                None,
                "Smithsonian Gardens, Horticultural Artifacts Collection, "
                "Washington, DC",
            ),
            ("Building 7", "Room 2", "Building 7, Room 2"),
        ],
    )
    async def test_exhibition_buildings_are_named(
        self, fake_api, building, room, location
    ):
        row = make_row(
            "ld1-x", "X", "NASM", on_view=True, exhibition="E", building=building
        )
        if room:
            row["content"]["indexedStructured"]["exhibition"][0]["room"] = room
        fake_api.search = lambda params: search_payload([row])
        result = await call("search_objects", {"query": "x", "on_view": True})
        assert result["objects"][0]["exhibition_location"] == location

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "date_from, decade",
        [("1860s", "1860s"), ("1860's", "1860s"), ("1865", "1860s")],
    )
    async def test_decade_strings_are_accepted(self, fake_api, date_from, decade):
        await call(
            "search_objects",
            {"query": "lincoln", "date_from": date_from, "date_to": date_from},
        )
        assert fake_api.searches[0]["q"] == f'(lincoln) AND date:"{decade}"'

    @pytest.mark.asyncio
    async def test_unparseable_date_text_gets_the_date_help(self, fake_api):
        text = await call_error("search_objects", {"date_from": "the sixties"})
        assert '"1860s"' in text and fake_api.requests == []

    @pytest.mark.asyncio
    async def test_pagination_uses_next_offset(self, fake_api):
        rows = [make_row(f"ld1-{i}", f"Object {i}") for i in range(3)]
        fake_api.search = lambda params: search_payload(rows, total=25)
        result = await call("search_objects", {"query": "object", "limit": 3})
        assert result["next_offset"] == 3 and result["returned"] == 3
        result = await call(
            "search_objects", {"query": "object", "limit": 3, "offset": 24}
        )
        assert result["next_offset"] is None

    @pytest.mark.asyncio
    async def test_unknown_museum_is_a_tool_error(self, fake_api):
        text = await call_error("search_objects", {"museum": "Louvre"})
        assert "Unknown museum 'Louvre'" in text and "list_museums" in text
        assert "Omit museum to search every museum" in text
        assert fake_api.requests == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "museum", ["Smithsonian", "the Smithsonian", "Smithsonian Institution"]
    )
    async def test_the_whole_smithsonian_means_no_museum_filter(self, fake_api, museum):
        fake_api.search = lambda params: search_payload(MUPPETS, total=2)
        result = await call("search_objects", {"query": "quilt", "museum": museum})
        assert fake_api.searches[0]["q"] == "quilt"
        assert "museum" not in result
        assert result["note"].startswith(f"museum='{museum}' means every")

    @pytest.mark.asyncio
    async def test_african_american_museum_is_not_african_art(self, fake_api):
        result = await call(
            "search_objects", {"query": "quilt", "museum": "African American Museum"}
        )
        assert result["museum"]["code"] == "NMAAHC"
        assert fake_api.searches[0]["q"] == "(quilt) AND unit_code:NMAAHC"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("year", [999, 3000, 12])
    async def test_bad_year_is_a_tool_error(self, fake_api, year):
        text = await call_error("search_objects", {"query": "x", "date_from": year})
        assert "four-digit years" in text and "decade" in text
        assert fake_api.requests == []

    @pytest.mark.asyncio
    async def test_limit_is_bounded(self, fake_api):
        text = await call_error("search_objects", {"query": "x", "limit": 51})
        assert "50" in text
        assert fake_api.requests == []

    @pytest.mark.asyncio
    async def test_firewall_rejection_is_a_tool_error(self, fake_api):
        fake_api.search = lambda params: html_403()
        text = await call_error("search_objects", {"query": "' OR 1=1 --"})
        assert "rejected this query text" in text and "plain keywords" in text

    @pytest.mark.asyncio
    async def test_rejected_key_names_the_setting(self, fake_api):
        fake_api.search = lambda params: key_403()
        text = await call_error("search_objects", {"query": "muppet"})
        assert "SMITHSONIAN_API_KEY" in text

    @pytest.mark.asyncio
    async def test_rate_limit_is_a_tool_error(self, fake_api):
        fake_api.search = lambda params: httpx.Response(429, json={})
        text = await call_error("search_objects", {"query": "muppet"})
        assert "rate limit" in text

    @pytest.mark.asyncio
    async def test_unexpected_errors_are_masked(self, fake_api):
        fake_api.search = lambda params: httpx.Response(200, content=b"not json")
        text = await call_error("search_objects", {"query": "muppet"})
        assert text == "Error calling tool 'search_objects'"

    @pytest.mark.asyncio
    async def test_natural_history_on_view_explains_empty_result(self, fake_api):
        result = await call(
            "search_objects",
            {"query": "dinosaur", "museum": "Natural History", "on_view": True},
        )
        assert result["total_count"] == 0 and result["objects"] == []
        assert "NMNH" in result["note"] and "on_view" in result["note"]

    @pytest.mark.asyncio
    async def test_archival_only_museum_with_no_objects_is_a_tool_error(self, fake_api):
        text = await call_error(
            "search_objects", {"query": "letters", "museum": "Archives of American Art"}
        )
        assert "AAA" in text and "record_type='archives'" in text
        assert len(fake_api.searches) == 1  # the search still ran

    @pytest.mark.asyncio
    async def test_archive_records_are_searched_separately(self, fake_api):
        record = load_record("archive_record_response.json")
        fake_api.search = lambda params: search_payload([record], total=1)
        result = await call(
            "search_objects",
            {"query": "warren", "museum": "ACAH", "record_type": "archives"},
        )
        params = fake_api.searches[0]
        assert params["row_group"] == "archives"
        assert params["q"] == "(warren) AND unit_code:ACAH"
        (archive,) = result["objects"]
        assert archive["title"] == "Spring Isn't Everything"
        assert archive["object_type"] == "Archival materials"
        assert archive["collection"] == "Harry Warren Papers"
        assert archive["web_url"].startswith("https://n2t.net/ark:/65665/")

    @pytest.mark.asyncio
    async def test_archive_search_of_a_museum_without_archives_has_a_note(
        self, fake_api
    ):
        result = await call(
            "search_objects", {"museum": "NMAH", "record_type": "archives"}
        )
        assert "record_type='objects'" in result["note"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "query, sentence",
        [
            ("Which Muppets are on display at the American History museum?", True),
            ("public domain images of quilts", True),
            ("muppets?", True),
            ('muppet OR muppets OR henson OR "sesame street"', False),
            ("Winslow Homer paintings", False),
            ("", False),
        ],
    )
    async def test_sentence_queries_get_a_note(self, fake_api, query, sentence):
        fake_api.search = lambda params: search_payload(MUPPETS[:1], total=1)
        result = await call("search_objects", {"query": query})
        assert ("reads like a sentence" in result.get("note", "")) is sentence

    @pytest.mark.asyncio
    async def test_on_view_without_museum_warns_about_natural_history(self, fake_api):
        fake_api.search = lambda params: search_payload(MUPPETS, total=2)
        result = await call("search_objects", {"query": "dinosaur", "on_view": True})
        assert result["returned"] == 2
        assert "Natural History (NMNH) publishes no exhibit data" in result["note"]
        result = await call(
            "search_objects", {"query": "muppet", "museum": "NMAH", "on_view": True}
        )
        assert "note" not in result

    @pytest.mark.asyncio
    @pytest.mark.parametrize("museum", ["Natural History", "NMNHPALEO", "paleobiology"])
    async def test_natural_history_units_on_view_explain_empty_results(
        self, fake_api, museum
    ):
        result = await call(
            "search_objects", {"query": "dinosaur", "museum": museum, "on_view": True}
        )
        assert result["note"].startswith("Natural History (NMNH) records carry no")

    @pytest.mark.asyncio
    async def test_offset_past_the_end_has_a_note(self, fake_api):
        fake_api.search = lambda params: search_payload([], total=12)
        result = await call("search_objects", {"query": "muppet", "offset": 40})
        assert result["note"] == "offset is past the last of 12 results."
        assert result["next_offset"] is None

    @pytest.mark.asyncio
    async def test_no_matches_explains_all_and_matching(self, fake_api):
        result = await call("search_objects", {"query": "which muppets are shown"})
        assert "Every word" in result["note"]


class TestGetObject:
    """get_object returns a bounded full record."""

    @pytest.mark.asyncio
    async def test_bert_puppet_details(self, fake_api):
        fake_api.add_record(load_record("bert_puppet_response.json"))
        result = await call("get_object", {"object_id": "nmah_1448973"})
        assert fake_api.paths() == [
            "content/nmah_1448973",
            "content/edanmdm:nmah_1448973",
        ]
        assert result["id"] == "ld1-1643398912743-1643398933001-0"
        assert result["record_id"] == "nmah_1448973"
        # Performers count as creators; the donor label does not
        assert result["maker"] == [
            "Oz, Frank",
            "Jacobson, Eric",
            "Henson, Jim",
            "Sahlin, Don",
        ]
        assert result["exhibition_title"] == "Entertainment Nation"
        assert result["on_view"] is True
        assert result["web_url"] == (
            "https://americanhistory.si.edu/collections/object/nmah_1448973"
        )
        assert "hand-rod puppet" in result["notes"]
        assert "foam (overall material)" in result["materials"]
        assert "Sesame Street" in result["topics"]
        assert find_nulls(result) == []

    @pytest.mark.asyncio
    async def test_record_link_is_preferred_and_images_listed(self, fake_api):
        fake_api.add_record(load_record("thunder_god_response.json"))
        result = await call(
            "get_object", {"object_id": "ld1-1643390182193-1643390183699-0"}
        )
        assert result["web_url"] == "https://asia.si.edu/object/F1900.47/"
        assert 1 <= len(result["images"]) <= MAX_IMAGES
        assert "image_count" not in result
        first = result["images"][0]
        # Displayable delivery URL; the thumbnail is the same URL, so left out
        assert (
            first["url"] == "https://ids.si.edu/ids/deliveryService?id=FS-F1900.47_001"
        )
        assert first["download_url"].endswith("FS-F1900.47_001.jpg")
        assert "thumbnail_url" not in first

    @pytest.mark.asyncio
    async def test_images_and_notes_are_capped(self, fake_api):
        long_note = "word " * 400
        fake_api.add_record(
            make_row(
                "ld1-many",
                "Album",
                images=25,
                notes=[
                    {"label": "Description", "content": long_note},
                    {"label": "Note", "content": long_note},
                    {"label": "Note", "content": "short"},
                ],
            )
        )
        result = await call("get_object", {"object_id": "ld1-many"})
        assert len(result["images"]) == MAX_IMAGES
        assert result["image_count"] == 25
        assert len(result["notes"]) <= MAX_NOTES_CHARS
        assert len(result["description"]) <= 1500
        # The Description note is not repeated in notes
        assert result["notes"].count("word word") < result["description"].count(
            "word word"
        )
        response = json.dumps(result)
        assert len(response) / 4 < 2500

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "unit, record_id, guid, url, expected",
        [
            # SIRIS id of a non-SIA unit: no pattern page, so the guid is used
            (
                "CFCHFOLKLIFE",
                "siris_arc_336210",
                "https://n2t.net/ark:/65665/x1",
                None,
                "https://n2t.net/ark:/65665/x1",
            ),
            # Neither link nor pattern nor guid: the url field
            (
                "SILNMAHTL",
                "SILNMAHTL_45848",
                None,
                "https://library.si.edu/x",
                "https://library.si.edu/x",
            ),
            ("SILNMAHTL", "SILNMAHTL_45848", None, None, None),
            (
                "SIA",
                "siris_arc_367768",
                None,
                None,
                "https://siarchives.si.edu/collections/siris_arc_367768",
            ),
        ],
    )
    async def test_web_url_fallbacks(
        self, fake_api, unit, record_id, guid, url, expected
    ):
        row = make_row("ld1-w", "W", unit, record_id=record_id, guid=guid)
        if url:
            row["url"] = url
        fake_api.add_record(row)
        result = await call("get_object", {"object_id": "ld1-w"})
        assert result.get("web_url") == expected

    @pytest.mark.asyncio
    async def test_unknown_id_is_a_tool_error(self, fake_api):
        text = await call_error("get_object", {"object_id": "ld1-missing"})
        assert "No object with id 'ld1-missing'" in text

    @pytest.mark.asyncio
    async def test_blank_id_is_a_tool_error(self, fake_api):
        text = await call_error("get_object", {"object_id": "  "})
        assert "object_id is required" in text
        assert fake_api.requests == []


class TestListMuseums:
    """list_museums lists units, their record types and aliases, without counts."""

    @pytest.mark.asyncio
    async def test_units_record_types_and_aliases(self, fake_api):
        result = (await call("list_museums"))["result"]
        assert fake_api.paths() == ["terms/unit_code"]
        by_code = {museum["code"]: museum for museum in result}
        assert by_code["NMAH"]["record_types"] == ["objects"]
        assert by_code["AAA"]["record_types"] == ["archives"]
        assert by_code["NPG"]["record_types"] == ["objects", "archives"]
        assert by_code["NMNH"]["record_types"] == ["objects"]
        assert "american history" in by_code["NMAH"]["aliases"]
        assert "ahm" not in by_code["NMAH"]["aliases"]
        assert "natural history" in by_code["NMNH"]["aliases"]
        assert set(by_code["NMAA"]["aliases"]) >= {"asian art", "freer", "sackler"}
        assert all("object_count" not in museum for museum in result)

    @pytest.mark.asyncio
    async def test_terms_outage_falls_back_to_the_built_in_list(self, fake_api):
        fake_api.unit_codes = httpx.Response(503, json={})
        result = (await call("list_museums"))["result"]
        assert len(result) == 49
        assert {"FSG"}.isdisjoint(museum["code"] for museum in result)

    @pytest.mark.asyncio
    async def test_rejected_key_is_reported(self, fake_api):
        fake_api.unit_codes = key_403()
        text = await call_error("list_museums")
        assert "SMITHSONIAN_API_KEY" in text


class TestExploreTopic:
    """explore_topic samples relevant matches that name the topic, spread out."""

    @staticmethod
    def pool() -> List[Dict[str, Any]]:
        rows = [
            # Matches the text search but does not name the topic
            make_row("ld1-lichen", "Psora tuckermanii", "NMNHBOTANY", images=1),
        ]
        for i in range(6):
            rows.append(
                make_row(
                    f"ld1-paleo-{i}",
                    f"Sauropod Dinosaur {i}",
                    "NMNHPALEO",
                    images=1,
                    object_type="Fossils" if i % 2 else "Casts",
                )
            )
        rows.append(
            make_row("ld1-nmah-0", "Dinosaur toy", "NMAH", images=1, object_type="Toys")
        )
        rows.append(
            make_row(
                "ld1-saam-0", "Untitled", "SAAM", images=1, object_type="Dinosaurs"
            )
        )
        return rows

    @pytest.mark.asyncio
    async def test_topic_is_applied_with_a_museum(self, fake_api):
        fake_api.search = lambda params: search_payload(self.pool(), total=354)
        await call(
            "explore_topic",
            {"topic": "dinosaurs", "museum": "Natural History", "limit": 5},
        )
        (params,) = fake_api.searches
        assert params["q"] == (
            '(dinosaurs) AND unit_code:NMNH* AND online_media_type:"Images"'
        )
        assert params["rows"] == "100" and params["start"] == "0"
        assert "sort" not in params  # relevance order

    @pytest.mark.asyncio
    async def test_sample_prefers_objects_naming_the_topic(self, fake_api):
        fake_api.search = lambda params: search_payload(self.pool(), total=354)
        result = await call("explore_topic", {"topic": "dinosaurs", "limit": 4})
        ids = [obj["id"] for obj in result["objects"]]
        assert "ld1-lichen" not in ids
        codes = [obj["museum_code"] for obj in result["objects"]]
        # Proportional with at least one each: 6 Paleobiology, 1 NMAH, 1 SAAM
        assert sorted(codes) == ["NMAH", "NMNHPALEO", "NMNHPALEO", "SAAM"]
        paleo_types = [
            obj["object_type"]
            for obj in result["objects"]
            if obj["museum_code"] == "NMNHPALEO"
        ]
        assert len(set(paleo_types)) == 2
        assert result["facets"]["museums"] == {"NMNHPALEO": 6, "NMAH": 1, "SAAM": 1}
        assert result["total_count"] == 354 and result["next_offset"] is None
        assert result["note"].startswith("8 of the 9 most relevant of 354")

    @pytest.mark.asyncio
    async def test_other_matches_fill_the_sample_last(self, fake_api):
        fake_api.search = lambda params: search_payload(self.pool(), total=9)
        result = await call("explore_topic", {"topic": "dinosaurs", "limit": 9})
        assert result["objects"][-1]["id"] == "ld1-lichen"

    @pytest.mark.asyncio
    async def test_fills_up_without_images_when_needed(self, fake_api):
        with_images = [make_row("ld1-a", "Jazz A", images=1)]
        without = [make_row(f"ld1-b{i}", f"Jazz B{i}", "SAAM") for i in range(5)]

        def search(params):
            if "online_media_type" in params["q"]:
                return search_payload(with_images, total=1)
            return search_payload(with_images + without, total=6)

        fake_api.search = search
        result = await call("explore_topic", {"topic": "jazz", "limit": 4})
        assert len(fake_api.searches) == 2
        assert fake_api.searches[1]["q"] == "jazz"
        assert "ld1-a" in [obj["id"] for obj in result["objects"]]
        assert result["returned"] == 4 and result["total_count"] == 6
        assert "6 most relevant of 6 matches" in result["note"]

    @pytest.mark.asyncio
    async def test_no_matches_has_a_note(self, fake_api):
        result = await call("explore_topic", {"topic": "zzzz"})
        assert result["objects"] == [] and "No objects match" in result["note"]

    @pytest.mark.asyncio
    async def test_archival_only_museum_points_to_archive_search(self, fake_api):
        text = await call_error("explore_topic", {"topic": "letters", "museum": "AAA"})
        assert "search_objects" in text and "record_type='archives'" in text

    def test_allocation_is_proportional_with_one_each(self):
        from smithsonian_mcp.tools import _allocate

        groups = {"A": [None] * 6, "B": [None] * 3, "C": [None] * 1}
        assert _allocate(groups, 5) == {"A": 3, "B": 1, "C": 1}
        assert _allocate(groups, 2) == {"A": 1, "B": 1, "C": 0}
        assert _allocate(groups, 20) == {"A": 6, "B": 3, "C": 1}

    def test_topic_stems(self):
        from smithsonian_mcp.tools import _topic_stems

        assert _topic_stems("Space exploration") == ["space", "exploration"]
        assert _topic_stems("dinosaurs OR fossils") == ["dinosaur", "fossil"]
        assert _topic_stems("the art of jazz") == ["art", "jazz"]


class TestCollectionStats:
    """get_collection_stats counts exactly what search_objects returns."""

    COUNTS = {
        ("*", None): 1000,
        ("*", "archives"): 300,
        ('* AND online_media_type:"Images"', None): 400,
        ('* AND media_usage:"CC0"', None): 250,
        ("* AND unit_code:NASM", None): 1012,
        ('* AND unit_code:NASM AND online_media_type:"Images"', None): 900,
        ('* AND unit_code:NASM AND media_usage:"CC0"', None): 5,
        ("* AND unit_code:AAA", "archives"): 492052,
    }

    @pytest.mark.asyncio
    async def test_whole_collection(self, fake_api):
        fake_api.search = counting_search(self.COUNTS)
        result = await call("get_collection_stats")
        assert result == {
            "objects": 1000,
            "archive_records": 300,
            "objects_with_images": 400,
            "objects_with_cc0_media": 250,
        }
        assert all(params["rows"] == "0" for params in fake_api.searches)
        assert len(fake_api.searches) == 4

    @pytest.mark.asyncio
    @pytest.mark.parametrize("museum", ["Air and Space", "AAA"])
    async def test_counts_equal_search_totals(self, fake_api, museum):
        fake_api.search = counting_search(self.COUNTS)
        stats = await call("get_collection_stats", {"museum": museum})
        searches = {
            "objects": {},
            "archive_records": {"record_type": "archives"},
            "objects_with_images": {"has_images": True},
            "objects_with_cc0_media": {"cc0_only": True},
        }
        for field, args in searches.items():
            text_or_result = None
            async with Client(mcp) as client:
                text_or_result = await client.call_tool(
                    "search_objects",
                    {"museum": museum, "limit": 1, **args},
                    raise_on_error=False,
                )
            if text_or_result.is_error:  # archival-only museum, objects search
                assert stats[field] == 0 and "record_type='archives'" in (
                    text_or_result.content[0].text
                )
            else:
                assert stats[field] == text_or_result.structured_content["total_count"]
        assert stats["museum"]["code"] in ("NASM", "AAA")

    @pytest.mark.asyncio
    async def test_counts_are_cached_until_they_expire(self, fake_api, monkeypatch):
        from smithsonian_mcp import tools

        clock = [1000.0]
        monkeypatch.setattr(tools.time, "monotonic", lambda: clock[0])
        fake_api.search = counting_search(self.COUNTS)
        await call("get_collection_stats")
        await call("get_collection_stats")
        assert len(fake_api.searches) == 4
        clock[0] += tools.STATS_CACHE_SECONDS + 1
        await call("get_collection_stats")
        assert len(fake_api.searches) == 8

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "response, message",
        [
            (key_403, "SMITHSONIAN_API_KEY"),
            (lambda: httpx.Response(429, json={}), "rate limit"),
            (lambda: httpx.Response(503, json={}), "not responding"),
        ],
    )
    async def test_errors_are_reported_and_not_cached(
        self, fake_api, response, message
    ):
        fake_api.search = lambda params: response()
        assert message in await call_error("get_collection_stats")
        fake_api.search = counting_search(self.COUNTS)
        assert (await call("get_collection_stats"))["objects"] == 1000


class TestResources:
    """Resources return the tool data as JSON."""

    @pytest.mark.asyncio
    async def test_museums_resource(self, fake_api):
        async with Client(mcp) as client:
            contents = await client.read_resource("smithsonian://museums")
        museums = json.loads(contents[0].text)
        assert {"code": "NMAH", "record_types": ["objects"]}.items() <= next(
            m for m in museums if m["code"] == "NMAH"
        ).items()

    @pytest.mark.asyncio
    async def test_object_resource(self, fake_api):
        fake_api.add_record(load_record("bert_puppet_response.json"))
        async with Client(mcp) as client:
            contents = await client.read_resource(
                "smithsonian://objects/edanmdm:nmah_1448973"
            )
        record = json.loads(contents[0].text)
        assert record["title"] == "Bert Puppet" and "description" not in record

    @pytest.mark.asyncio
    async def test_object_resource_not_found(self, fake_api):
        async with Client(mcp) as client:
            with pytest.raises(Exception, match="No object with id"):
                await client.read_resource("smithsonian://objects/ld1-missing")


class TestPrompts:
    """Prompts point at the current tools."""

    @pytest.mark.asyncio
    async def test_museum_on_view_prompt(self):
        async with Client(mcp) as client:
            result = await client.get_prompt(
                "museum_on_view", {"museum": "American History", "topic": "muppet"}
            )
        text = result.messages[0].content.text
        assert "search_objects" in text and "on_view=true" in text
        assert "query='muppet'" in text and "exhibition_title" in text

    @pytest.mark.asyncio
    async def test_exhibition_size_is_constrained(self):
        async with Client(mcp) as client:
            result = await client.get_prompt(
                "exhibition_planning", {"exhibition_theme": "flight", "size": "small"}
            )
            assert "about 15-25 objects" in result.messages[0].content.text
            with pytest.raises(Exception, match="size"):
                await client.get_prompt(
                    "exhibition_planning",
                    {"exhibition_theme": "flight", "size": "huge"},
                )

    @pytest.mark.asyncio
    async def test_prompts_only_name_existing_tools(self):
        args = {
            "collection_research": {"research_topic": "jazz"},
            "object_analysis": {"object_id": "ld1-1"},
            "exhibition_planning": {"exhibition_theme": "flight"},
            "educational_content": {"subject": "Space"},
            "museum_on_view": {"museum": "NMAH"},
        }
        async with Client(mcp) as client:
            for name, arguments in args.items():
                result = await client.get_prompt(name, arguments)
                text = result.messages[0].content.text
                named = set(re.findall(r"\b[a-z]+_[a-z_]+\b", text))
                tools_named = {
                    n
                    for n in named
                    if n.split("_")[0]
                    in (
                        "search",
                        "get",
                        "list",
                        "explore",
                        "find",
                        "simple",
                        "resolve",
                        "continue",
                        "validate",
                        "summarize",
                        "check",
                    )
                }
                assert tools_named <= TOOL_NAMES, (name, tools_named)
                assert "FSG" not in text
