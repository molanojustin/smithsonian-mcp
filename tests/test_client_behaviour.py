"""
Tests for API client behaviour: row parsing, units, the shared client, logging
setup and the command line entry points.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from smithsonian_mcp import context
from smithsonian_mcp.api_client import SmithsonianAPIClient
from smithsonian_mcp.models import APIError, CollectionSearchFilter

pytest.importorskip("pytest_asyncio")

REPO_ROOT = Path(__file__).resolve().parent.parent

REAL_ROW = {
    "id": "ld1-1643381040022-1643381051917-0",
    "title": "<i>Small</i> Landscape &amp; Trees",
    "unitCode": "SAAM",
    "url": "edanmdm:saam_1956.11.37",
    "lastTimeUpdated": "1757413722",
    "content": {
        "freetext": {
            "date": [{"label": "Date", "content": "ca. 1880-1890"}],
            "name": [
                {"label": "Artist", "content": "J. Francis Murphy, born 1853"},
                {"label": "Sitter", "content": "Somebody Else"},
            ],
            "creditLine": [{"label": "Credit Line", "content": "Bequest of M. L."}],
            "objectType": [{"label": "Type", "content": "Painting"}],
            "objectRights": [{"label": "Restrictions & Rights", "content": "CC0"}],
            "physicalDescription": [
                {"label": "Medium", "content": "oil on canvas"},
                {"label": "Dimensions", "content": "10 x 12 in."},
            ],
            "notes": [{"label": "Description", "content": "A <b>quiet</b> scene"}],
        },
        "indexedStructured": {
            "date": ["1880s"],
            "name": ["Murphy, J. Francis"],
            "topic": ["Trees", "Landscapes"],
            "exhibition": [{"building": "SAAM", "exhibitionTitle": "<i>Gallery</i> 1"}],
            "object_type": ["Paintings"],
            "onPhysicalExhibit": ["Yes"],
            "online_media_type": ["Images"],
        },
        "descriptiveNonRepeating": {
            "guid": "http://n2t.net/ark:/65665/vk796c355a9",
            "record_ID": "saam_1956.11.37",
            "unit_code": "SAAM",
            "data_source": "Smithsonian American Art Museum",
            "record_link": "https://americanart.si.edu/collections/search/artwork/?id=18097",
            "online_media": {
                "media": [
                    {
                        "type": "Images",
                        "usage": {"access": "CC0"},
                        "content": "https://ids.si.edu/ids/deliveryService?id=SAAM-1",
                        "thumbnail": "https://ids.si.edu/ids/deliveryService?id=SAAM-1",
                        "resources": [
                            {
                                "label": "High-resolution TIFF",
                                "url": "https://ids.si.edu/ids/download?id=SAAM-1.tif",
                                "dimensions": "3000x2423",
                            }
                        ],
                    },
                    {"type": "Images", "size": "not a number", "content": 42},
                ],
                "mediaCount": 2,
            },
            "metadata_usage": {"access": "CC0"},
        },
    },
}


def _search_response(rows, row_count):
    return {"response": {"rows": rows, "rowCount": row_count}}


class TestParsing:
    """Parsing of real search rows."""

    def test_real_row_fields(self, caplog):
        caplog.set_level(logging.DEBUG, logger="smithsonian_mcp")
        client = SmithsonianAPIClient(api_key="test")
        obj = client._parse_object_data(REAL_ROW)

        assert obj.title == "Small Landscape & Trees"
        assert obj.unit_code == "SAAM"
        assert obj.unit_name == "Smithsonian American Art Museum"
        assert obj.record_id == "saam_1956.11.37"
        assert obj.guid == "http://n2t.net/ark:/65665/vk796c355a9"
        assert str(obj.record_link).startswith("https://americanart.si.edu/")
        assert obj.url is None  # edanmdm: URLs are not web URLs
        assert obj.maker == ["J. Francis Murphy, born 1853"]
        assert obj.date == "ca. 1880-1890"
        assert obj.date_standardized == "1880s"
        assert obj.object_type == "Painting"
        assert obj.materials == ["oil on canvas"]
        assert obj.dimensions == "10 x 12 in."
        assert obj.credit_line == "Bequest of M. L."
        assert obj.rights == "CC0"
        assert obj.description == "A quiet scene"
        assert obj.topics == ["Trees", "Landscapes"]
        assert obj.is_on_view is True
        assert obj.exhibition_title == "Gallery 1"
        assert obj.exhibition_location == "SAAM"
        assert obj.is_cc0 is True
        assert obj.last_modified is not None and obj.last_modified.year == 2025
        assert len(obj.images) == 2
        assert str(obj.images[0].url).endswith("SAAM-1.tif")
        assert (obj.images[0].width, obj.images[0].height) == (3000, 2423)
        assert obj.images[0].is_cc0 is True
        assert obj.images[1].url is None and obj.images[1].size_bytes is None

        # Every log record must format cleanly (the old image count used %d on a list)
        messages = [record.getMessage() for record in caplog.records]
        assert any("Parsed 2 images" in message for message in messages)

    @pytest.mark.parametrize(
        "unit,names,indexed,expected",
        [
            # Label sets taken from real records of each unit
            (
                "NMAI",
                [
                    ("Culture/People", "Lakota"),
                    ("Seller", "Some Dealer"),
                    ("Previous owner", "A Collector"),
                    ("Collector", "Field Collector"),
                    ("Artist/Maker", "Real Maker"),
                ],
                ["Some Dealer", "A Collector"],
                ["Real Maker"],
            ),
            (
                "NMNHMINSCI",
                [("Site Name", "Synthetic"), ("Taxon", "Cubic zirconia - Primary")],
                [],
                [],
            ),
            (
                "NMNHANTHRO",
                [
                    ("Donor Name", "Donor"),
                    ("Collector", "Collector"),
                    ("Site Name", "X"),
                ],
                [],
                [],
            ),
            (
                "NMAAHC",
                [
                    ("subject of", "Subject Person"),
                    ("photograph by", "Photographer"),
                    ("owned by", "Owner"),
                    ("signed by", "Signer"),
                    ("created by", "Creator"),
                ],
                [],
                ["Photographer", "Creator"],
            ),
            (
                "NPG",
                [("Sitter", "Jack London"), ("Artist", "Finn Frolich")],
                [],
                ["Finn Frolich"],
            ),
            (
                "SAAM",
                [
                    ("Artist", "A"),
                    ("Copy after", "B"),
                    ("Commissioner", "C"),
                    ("Sitter", "D"),
                ],
                [],
                ["A"],
            ),
            (
                "NASM",
                [
                    ("Manufacturer", "Boeing"),
                    ("Manufactured for", "US Navy"),
                    ("Owner", "O"),
                ],
                [],
                ["Boeing"],
            ),
            ("HMSG", [("Artist", "A"), ("Formerly attributed to", "B")], [], ["A"]),
            (
                "CHNDM",
                [("Designer", "D"), ("Print maker", "P"), ("After", "X")],
                [],
                ["D", "P"],
            ),
            # No creator in freetext: indexed names (dealers, collectors) are not used
            ("NMAA", [], ["Kobayashi, Bunshichi", "Freer, Charles Lang"], []),
            # Unlabeled name entries have no known role
            ("NMAH", [(None, "Unknown Role")], [], []),
        ],
    )
    def test_makers_are_creators_only(self, unit, names, indexed, expected):
        client = SmithsonianAPIClient(api_key="test")
        entries = [
            (
                {"content": content}
                if label is None
                else {"label": label, "content": content}
            )
            for label, content in names
        ]
        row = {
            "id": "ld1-x",
            "title": "t",
            "unitCode": unit,
            "content": {
                "freetext": {"name": entries},
                "indexedStructured": {"name": indexed},
            },
        }
        assert client._parse_object_data(row).maker == expected

    @staticmethod
    def _parse(content, **extra):
        client = SmithsonianAPIClient(api_key="test")
        return client._parse_object_data(
            {"id": "ld1-x", "title": "t", "content": content, **extra}
        )

    def test_date_standardized_is_the_earliest_decade(self):
        # HMSG lists later decades first for an object dated 1497-98
        obj = self._parse({"indexedStructured": {"date": ["1520s", "1490s", "1500s"]}})
        assert obj.date_standardized == "1490s"
        obj = self._parse({"indexedStructured": {"date": ["20th century", "1950s"]}})
        assert obj.date_standardized == "1950s"
        obj = self._parse({"indexedStructured": {"date": ["Ming dynasty"]}})
        assert obj.date_standardized == "Ming dynasty"

    def test_rights_keep_every_statement(self):
        rights = [
            {"label": "Restrictions & Rights", "content": "© Bernard J. Kleina"},
            {
                "label": "Restrictions & Rights",
                "content": "Permission required for use.",
            },
        ]
        obj = self._parse({"freetext": {"objectRights": rights}})
        assert obj.rights == "© Bernard J. Kleina; Permission required for use."
        npg = [
            {"label": "Restrictions & Rights", "content": "CC0"},
            {"label": "Copyright", "content": "death date 1923"},
        ]
        assert self._parse({"freetext": {"objectRights": npg}}).rights == "CC0"

    def test_materials_come_from_material_labels(self):
        nmai = [
            {"label": "Object Name", "content": "Jar"},
            {"label": "Media/Materials", "content": "Pottery"},
            {"label": "Techniques", "content": "Painted"},
            {"label": "Dimensions", "content": "10 cm"},
        ]
        obj = self._parse({"freetext": {"physicalDescription": nmai}})
        assert obj.materials == ["Pottery"]
        assert obj.dimensions == "10 cm"
        nmah = [
            {"label": "Physical Description", "content": "vinyl (overall material)"},
            {
                "label": "Physical Description",
                "content": "woven (overall production method/technique)",
            },
            {"label": "Measurements", "content": "overall: 13 in x 8 in"},
        ]
        obj = self._parse({"freetext": {"physicalDescription": nmah}})
        assert obj.materials == ["vinyl (overall material)"]
        assert obj.dimensions == "overall: 13 in x 8 in"
        sil = [{"label": "Physical description", "content": "xii, 300 p. : ill."}]
        assert self._parse({"freetext": {"physicalDescription": sil}}).materials == []

    def test_is_cc0_reflects_media_usage(self):
        # NMAAHC: CC0 metadata, copyrighted object with no CC0 media
        copyrighted = self._parse(
            {"descriptiveNonRepeating": {"metadata_usage": {"access": "CC0"}}}
        )
        assert copyrighted.is_cc0 is False
        assert copyrighted.metadata_is_cc0 is True
        with_media = self._parse(
            {
                "descriptiveNonRepeating": {
                    "metadata_usage": {"access": "CC0"},
                    "online_media": {
                        "media": [{"type": "Images", "usage": {"access": "CC0"}}]
                    },
                }
            }
        )
        assert with_media.is_cc0 is True and with_media.metadata_is_cc0 is True

    def test_maker_block_entries_count_without_label(self):
        client = SmithsonianAPIClient(api_key="test")
        row = {
            "id": "ld1-x",
            "title": "t",
            "content": {"freetext": {"maker": [{"content": "Unlabeled Maker"}]}},
        }
        assert client._parse_object_data(row).maker == ["Unlabeled Maker"]

    def test_exhibition_room_is_optional(self):
        client = SmithsonianAPIClient(api_key="test")
        indexed = {"exhibition": [{"building": "NMAH", "room": "East 1"}]}
        assert client._parse_exhibition_location(indexed) == "NMAH, East 1"
        assert client._parse_exhibition_location({"exhibition": [{}]}) is None
        assert client._parse_exhibition_location({}) is None


class TestSearch:
    """search_collections behaviour."""

    @pytest.mark.asyncio
    async def test_bad_rows_are_skipped(self, monkeypatch, caplog):
        client = SmithsonianAPIClient(api_key="test")
        rows = [
            {"id": "good-1", "title": "Good"},
            "not a row",
            {"id": "bad-1", "title": "Bad", "content": []},
            {"id": "good-2", "title": "Also good"},
        ]
        original = client._parse_object_data

        def parse(row):
            if isinstance(row, dict) and row.get("id") == "bad-1":
                raise ValueError("broken record")
            return original(row)

        monkeypatch.setattr(client, "_parse_object_data", parse)
        monkeypatch.setattr(
            client, "_make_request", AsyncMock(return_value=_search_response(rows, 10))
        )

        result = await client.search_collections(CollectionSearchFilter(limit=4))

        assert [o.id for o in result.objects] == ["good-1", "good-2"]
        assert result.returned_count == 2
        assert result.total_count == 10
        # Pagination follows the rows the API returned, not the parsed count
        assert result.has_more is True and result.next_offset == 4
        assert "bad-1" in caplog.text

    @pytest.mark.asyncio
    async def test_last_page_has_no_more(self, monkeypatch):
        client = SmithsonianAPIClient(api_key="test")
        monkeypatch.setattr(
            client,
            "_make_request",
            AsyncMock(return_value=_search_response([{"id": "x", "title": "x"}], 11)),
        )
        result = await client.search_collections(
            CollectionSearchFilter(limit=10, offset=10)
        )
        assert result.offset == 10
        assert result.has_more is False and result.next_offset is None

    @pytest.mark.asyncio
    async def test_invalid_date_raises_before_any_request(self, monkeypatch):
        client = SmithsonianAPIClient(api_key="test")
        request = AsyncMock()
        monkeypatch.setattr(client, "_make_request", request)
        with pytest.raises(ValueError, match="date_start '19th century'"):
            await client.search_collections(
                CollectionSearchFilter(date_start="19th century")
            )
        request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_count_matches_uses_rows_zero(self, monkeypatch):
        client = SmithsonianAPIClient(api_key="test")
        request = AsyncMock(return_value=_search_response([], 254))
        monkeypatch.setattr(client, "_make_request", request)
        assert await client.count_matches('onPhysicalExhibit:"Yes"') == 254
        request.assert_awaited_once_with(
            "search", {"q": 'onPhysicalExhibit:"Yes"', "start": 0, "rows": 0}
        )


FIREWALL_PAGE = (
    "<html><head><title>Request Rejected</title></head><body>...</body></html>"
)


class TestForbidden:
    """HTTP 403 responses: firewall rejections versus key errors."""

    @staticmethod
    async def _error_for(response: httpx.Response) -> APIError:
        client = SmithsonianAPIClient(
            api_key="test", transport=httpx.MockTransport(lambda request: response)
        )
        try:
            with pytest.raises(APIError) as excinfo:
                await client.search_collections(
                    CollectionSearchFilter(query="x", limit=0)
                )
        finally:
            await client.disconnect()
        return excinfo.value

    @pytest.mark.asyncio
    @pytest.mark.parametrize("content_type", ["text/html; charset=utf-8", "text/html"])
    async def test_html_403_is_a_rejected_query(self, content_type):
        error = await self._error_for(
            httpx.Response(
                403, content=FIREWALL_PAGE, headers={"content-type": content_type}
            )
        )
        assert error.error == "query_rejected"
        assert error.status_code == 403
        assert "rephrase the query" in error.message
        assert "not an API key problem" in error.message

    @pytest.mark.asyncio
    async def test_json_403_is_a_key_error(self):
        body = {
            "error": {
                "code": "API_KEY_INVALID",
                "message": "An invalid api_key was supplied.",
            }
        }
        error = await self._error_for(httpx.Response(403, json=body))
        assert error.error == "api_key_rejected"
        assert "API_KEY_INVALID" in error.message

    @pytest.mark.asyncio
    async def test_other_json_403_stays_an_http_error(self):
        error = await self._error_for(httpx.Response(403, json={"status": 403}))
        assert error.error == "http_error"


class TestUnits:
    """get_units uses /terms/unit_code with a cache and a static fallback."""

    @pytest.mark.asyncio
    async def test_units_from_terms_endpoint(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.url.path)
            terms = ["NMAA", "NMAH", "NMNHBIRDS", "NMNHPALEO", "SAAM", "ZNEW"]
            return httpx.Response(200, json={"response": {"terms": terms}})

        client = SmithsonianAPIClient(
            api_key="test", transport=httpx.MockTransport(handler)
        )
        try:
            units = await client.get_units()
            again = await client.get_units()
        finally:
            await client.disconnect()

        codes = [u.code for u in units]
        assert codes == [
            "NMAA",
            "NMAH",
            "NMNH",
            "NMNHBIRDS",
            "NMNHPALEO",
            "SAAM",
            "ZNEW",
        ]
        assert len(calls) == 1  # cached
        assert [u.code for u in again] == codes
        by_code = {u.code: u for u in units}
        assert by_code["NMAA"].name == "National Museum of Asian Art"
        assert by_code["NMNH"].name == "National Museum of Natural History"
        assert by_code["ZNEW"].name == "ZNEW"

    @pytest.mark.asyncio
    async def test_units_fall_back_to_static_list(self, monkeypatch):
        client = SmithsonianAPIClient(api_key="test")
        monkeypatch.setattr(
            client,
            "_make_request",
            AsyncMock(side_effect=APIError(error="http_error", message="down")),
        )
        units = await client.get_units()
        codes = [u.code for u in units]
        assert len(codes) == len(set(codes)) == 49
        assert "FSG" not in codes and "NMAA" in codes and "NMNH" in codes
        assert codes.count("SAAM") == 1
        aaa = next(u for u in units if u.code == "AAA")
        assert aaa.archival_only is True
        assert "archival" in aaa.description


class TestSharedClient:
    """One API client is shared by the lifespan and the tools."""

    @pytest.mark.asyncio
    async def test_lifespan_client_is_used_and_closed(self, monkeypatch):
        from smithsonian_mcp.server import server_lifespan

        create = AsyncMock(
            side_effect=AssertionError("must not create a second client")
        )
        monkeypatch.setattr(context, "create_client", create)
        context.set_api_client(None)

        async with server_lifespan(None) as server_context:
            client = server_context.api_client
            assert client.session is not None
            assert await context.get_api_client() is client
            assert await context.get_api_client(None) is client

        assert client.session is None  # closed on shutdown
        assert context.peek_api_client() is None
        create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_lazy_client_outside_lifespan(self, monkeypatch):
        created = []

        async def fake_create():
            await asyncio.sleep(0)
            client = SmithsonianAPIClient(api_key="test")
            created.append(client)
            return client

        monkeypatch.setattr(context, "create_client", fake_create)
        context.set_api_client(None)

        first, second = await asyncio.gather(
            context.get_api_client(), context.get_api_client()
        )
        assert first is second
        assert await context.get_api_client() is first
        await context.close_api_client()
        assert context.peek_api_client() is None

    def test_client_is_recreated_on_a_new_event_loop(self, monkeypatch):
        created = []

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_search_response([], 7))

        async def fake_create():
            client = SmithsonianAPIClient(
                api_key="test", transport=httpx.MockTransport(handler)
            )
            await client.connect()
            created.append((client, asyncio.get_running_loop()))
            return client

        monkeypatch.setattr(context, "create_client", fake_create)
        context.set_api_client(None)

        async def use_twice():
            first = await context.get_api_client()
            second = await context.get_api_client()
            assert first is second  # reused within one loop
            return first, await first.count_matches("*")

        client_one, count_one = asyncio.run(use_twice())
        client_two, count_two = asyncio.run(use_twice())

        assert count_one == count_two == 7
        assert client_one is not client_two
        assert len(created) == 2 and created[0][1] is not created[1][1]
        context.set_api_client(None)

    @pytest.mark.live
    def test_shared_client_works_across_asyncio_runs_live(self):
        async def use():
            client = await context.get_api_client()
            return await client.count_matches("muppet")

        context.set_api_client(None)
        try:
            assert asyncio.run(use()) > 0
            assert asyncio.run(use()) > 0  # was "Event loop is closed"
        finally:
            context.set_api_client(None)


def _run_python(code_or_args, env_overrides=None, timeout=60):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SMITHSONIAN")}
    env.update(env_overrides or {})
    args = code_or_args if isinstance(code_or_args, list) else ["-c", code_or_args]
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


class TestLoggingSetup:
    """Logging is configured only by main(), and only to stderr."""

    def test_importing_does_not_configure_logging(self):
        result = _run_python(
            "import logging, smithsonian_mcp, smithsonian_mcp.main, smithsonian_mcp.tools;"
            "print(len(logging.getLogger().handlers), logging.getLogger().level)",
            {"SMITHSONIAN_API_KEY": "placeholder"},
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "0 30"  # no handlers, WARNING default

    def test_configure_logging_targets_stderr_and_quiets_httpx(self):
        result = _run_python(
            "import logging, sys;"
            "from smithsonian_mcp.main import configure_logging;"
            "configure_logging('DEBUG');"
            "root = logging.getLogger();"
            "print(root.level, [h.stream is sys.stderr for h in root.handlers],"
            " logging.getLogger('httpx').level, logging.getLogger('httpcore').level);"
            "logging.getLogger('smithsonian_mcp.test').info('to-stderr')",
            {"SMITHSONIAN_API_KEY": "placeholder"},
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "10 [True] 30 30"
        assert "to-stderr" in result.stderr


class TestEntryPoints:
    """All module invocations reach main() and serve MCP over stdio."""

    @pytest.mark.parametrize(
        "module", ["smithsonian_mcp", "smithsonian_mcp.main", "smithsonian_mcp.server"]
    )
    def test_version_flag(self, module):
        result = _run_python(["-m", module, "--version"], {"SMITHSONIAN_API_KEY": "x"})
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith("smithsonian-mcp ")
        assert "RuntimeWarning" not in result.stderr

    def test_missing_key_exits_with_error(self):
        result = _run_python(
            ["-m", "smithsonian_mcp.server"], {"SMITHSONIAN_API_KEY": ""}, timeout=30
        )
        assert result.returncode == 1
        assert "API key not configured" in result.stderr
        assert result.stdout == ""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "module", ["smithsonian_mcp", "smithsonian_mcp.main", "smithsonian_mcp.server"]
    )
    async def test_module_serves_stdio(self, module):
        from fastmcp import Client
        from fastmcp.client.transports import StdioTransport

        transport = StdioTransport(
            command=sys.executable,
            args=["-m", module],
            env={
                "SMITHSONIAN_API_KEY": "placeholder-key-for-stdio-test",
                "LOG_LEVEL": "DEBUG",
                "PATH": os.environ.get("PATH", ""),
            },
            cwd=str(REPO_ROOT),
        )
        async with Client(transport) as client:
            tools = await client.list_tools()
        names = {tool.name for tool in tools}
        assert {"search_collections", "get_collection_statistics"} <= names


def test_tool_layer_still_imports_constants():
    """Names used by tools.py and resources.py remain available."""
    from smithsonian_mcp import constants, utils

    for name in (
        "MUSEUM_MAP",
        "VALID_MUSEUM_CODES",
        "SIZE_GUIDELINES",
        "MUSEUM_URL_PATTERNS",
    ):
        assert hasattr(constants, name)
    for name in (
        "resolve_museum_code",
        "prioritize_objects_by_unit_code",
        "validate_url",
        "construct_url_from_record_id",
    ):
        assert callable(getattr(utils, name))
    json.dumps(constants.MUSEUM_URL_PATTERNS)
