"""
MCP tools for the Smithsonian Open Access collections.

Five read-only tools cover searching, object records, the list of museums, topic
exploration and collection statistics. ``register_tools`` adds them to a FastMCP
server. Guidance shared by every tool lives in the server instructions (app.py),
so the tool descriptions stay short.

Problems the caller can fix (an unknown museum, a bad year, query text rejected
by the API firewall, an unknown object id, a rejected API key) raise ToolError
with a next step. Any other exception is masked by the server.
"""

import asyncio
import inspect
import logging
import re
import time
from typing import (
    Annotated,
    Any,
    Callable,
    Dict,
    List,
    Literal,
    NoReturn,
    Optional,
    Tuple,
    Union,
)

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import FunctionTool
from mcp.types import ToolAnnotations
from pydantic import Field

from .constants import ARCHIVAL_UNIT_CODES, MUSEUM_MAP
from .context import get_api_client
from .formatting import details, summarize, unit_name
from .models import (
    APIError,
    CollectionOverview,
    CollectionSearchFilter,
    MuseumInfo,
    MuseumRef,
    ObjectDetails,
    ObjectSearchResults,
    SearchResult,
    TopicExploration,
)
from .notes import explore_note, search_note, whole_smithsonian_note
from .query import MAX_DATE_YEAR, MIN_DATE_YEAR, build_search_query, date_clause
from .sampling import diverse_sample, facets, rank_pool
from .utils import is_whole_smithsonian, record_types, resolve_museum_code

logger = logging.getLogger(__name__)

SEARCH_DEFAULT_LIMIT = 10
SEARCH_MAX_LIMIT = 50
EXPLORE_DEFAULT_LIMIT = 12
EXPLORE_MAX_LIMIT = 30
# Most relevant matches fetched for explore_topic; the sample and facets come
# from them.
EXPLORE_POOL_SIZE = 100

# Collection counts change slowly; get_collection_stats caches them per museum.
STATS_CACHE_SECONDS = 6 * 60 * 60

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True, idempotentHint=True)

DATE_HELP = (
    f"date_from and date_to take four-digit years from {MIN_DATE_YEAR} to "
    f'{MAX_DATE_YEAR}, such as 1865, or decades such as "1860s". Dates match '
    "by decade."
)
_YEAR_TEXT_RE = re.compile(r"\s*(\d{1,4})\s*'?s?\s*")
UNKNOWN_MUSEUM_HELP = (
    "Use a museum name or unit code such as 'American History' (NMAH), "
    "'Natural History' (NMNH), 'American Art' (SAAM), 'Asian Art' (NMAA), "
    "'Air and Space' (NASM) or 'Portrait Gallery' (NPG); list_museums shows "
    "every unit. Omit museum to search every museum."
)

# Aliases from MUSEUM_MAP left out of list_museums: misspellings and a wrong
# abbreviation that resolve_museum_code accepts but should not be advertised.
_HIDDEN_ALIASES = frozenset({"ahm", "botony", "sculture garden"})

_stats_cache: Dict[str, Tuple[float, CollectionOverview]] = {}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def clear_caches() -> None:
    """Forget cached collection counts so the next call fetches them."""
    _stats_cache.clear()


def _resolve_museum(museum: Optional[str]) -> Optional[MuseumRef]:
    """
    Resolve a museum name or code to a unit.

    Args:
        museum: Name or code supplied by the caller, or None.

    Returns:
        Optional[MuseumRef]: The unit, or None when no museum was given.

    Raises:
        ToolError: If the museum cannot be resolved.
    """
    if museum is None or not museum.strip() or is_whole_smithsonian(museum):
        return None
    code = resolve_museum_code(museum)
    if code is None:
        raise ToolError(f"Unknown museum '{museum.strip()}'. {UNKNOWN_MUSEUM_HELP}")
    return MuseumRef(code=code, name=unit_name(code) or code)


def _raise_for_api_error(exc: APIError) -> NoReturn:
    """
    Turn an API failure into a ToolError when the caller can act on it.

    Args:
        exc: The API error.

    Raises:
        ToolError: For rejected query text, a rejected key, rate limiting or an
            unavailable API.
        APIError: Otherwise, re-raised so the server masks it.
    """
    if exc.error == "query_rejected":
        raise ToolError(
            "The Smithsonian API rejected this query text; rephrase it with plain "
            "keywords."
        ) from exc
    if exc.error == "api_key_rejected":
        raise ToolError(
            "The Smithsonian API rejected the API key. Check SMITHSONIAN_API_KEY in "
            "the server configuration (free keys: https://api.data.gov/signup/)."
        ) from exc
    if exc.error == "rate_limit_exceeded":
        raise ToolError(
            "The Smithsonian API rate limit for this API key was reached. Try "
            "again later."
        ) from exc
    if exc.error == "request_error" or (exc.status_code or 0) >= 500:
        raise ToolError(
            "The Smithsonian API is not responding right now. Try again shortly."
        ) from exc
    raise exc


def _archival_only_error(unit: MuseumRef, tool: str = "search_objects") -> ToolError:
    """
    Explain that a museum holds only archive records.

    Args:
        unit: The archival-only unit.
        tool: The tool that was called.

    Returns:
        ToolError: Error with a next step.
    """
    if tool == "explore_topic":
        step = "explore_topic samples objects; use search_objects with "
    else:
        step = "Search again with "
    return ToolError(
        f"{unit.name} ({unit.code}) holds only archive records, which object "
        f"searches do not return. {step}record_type='archives'."
    )


async def _search(filters: CollectionSearchFilter) -> SearchResult:
    """
    Run a search with the shared client, converting API errors.

    Args:
        filters: Search filters.

    Returns:
        SearchResult: The client search result.
    """
    client = await get_api_client()
    try:
        return await client.search_collections(filters)
    except APIError as exc:
        _raise_for_api_error(exc)


async def _count(filters: CollectionSearchFilter) -> int:
    """
    Number of records a search would return, without fetching any.

    Args:
        filters: Search filters, built exactly as search_objects builds them.

    Returns:
        int: The search's total count.
    """
    client = await get_api_client()
    return await client.count_matches(
        build_search_query(filters), row_group=filters.row_group
    )


async def _collection_counts(unit: Optional[MuseumRef]) -> CollectionOverview:
    """
    Searchable record counts, cached for STATS_CACHE_SECONDS.

    Each figure is the total_count of the search_objects call it describes, so
    the numbers always agree with search results.

    Args:
        unit: Museum to count, or None for the whole collection.

    Returns:
        CollectionOverview: The counts.
    """
    key = unit.code if unit else ""
    cached = _stats_cache.get(key)
    if cached and time.monotonic() - cached[0] < STATS_CACHE_SECONDS:
        return cached[1]
    code = unit.code if unit else None
    try:
        objects, archives, with_images, cc0 = await asyncio.gather(
            _count(CollectionSearchFilter(unit_code=code)),
            _count(CollectionSearchFilter(unit_code=code, row_group="archives")),
            _count(CollectionSearchFilter(unit_code=code, has_images=True)),
            _count(CollectionSearchFilter(unit_code=code, is_cc0=True)),
        )
    except APIError as exc:
        _raise_for_api_error(exc)
    overview = CollectionOverview(
        museum=unit,
        objects=objects,
        archive_records=archives,
        objects_with_images=with_images,
        objects_with_cc0_media=cc0,
    )
    _stats_cache[key] = (time.monotonic(), overview)
    return overview


def _year_text(value: Optional[Union[int, str]]) -> Optional[str]:
    """
    Normalize a year argument for the client's date filter.

    Args:
        value: A year (1865), a year string ("1865") or a decade ("1860s").

    Returns:
        Optional[str]: The year as text, or None if no year was given.

    Raises:
        ToolError: If the value is not a year or decade.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise ToolError(DATE_HELP)
    if isinstance(value, int):
        return str(value)
    match = _YEAR_TEXT_RE.fullmatch(value)
    if not match:
        raise ToolError(DATE_HELP)
    return match.group(1)


def _museum_aliases() -> Dict[str, List[str]]:
    """
    Short names that resolve to each unit code, from MUSEUM_MAP.

    Longer variants that contain a shorter alias ("american history museum"
    next to "american history") are left out.

    Returns:
        Dict[str, List[str]]: Aliases by unit code, shortest first.
    """
    by_code: Dict[str, List[str]] = {}
    for alias, code in MUSEUM_MAP.items():
        alias = alias.replace("-", " ")
        if alias in _HIDDEN_ALIASES or alias in by_code.get(code, []):
            continue
        by_code.setdefault(code, []).append(alias)
    compact: Dict[str, List[str]] = {}
    for code, aliases in by_code.items():
        kept: List[str] = []
        for alias in sorted(aliases, key=len):
            if not any(f" {short} " in f" {alias} " for short in kept):
                kept.append(alias)
        compact[code] = kept
    return compact


_ALIASES = _museum_aliases()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


# The parameters are the tool's input schema, so they are not grouped.
async def search_objects(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    query: str = "",
    museum: Optional[str] = None,
    object_type: Optional[str] = None,
    maker: Optional[str] = None,
    topic: Optional[str] = None,
    material: Optional[str] = None,
    date_from: Optional[Union[int, str]] = None,
    date_to: Optional[Union[int, str]] = None,
    has_images: bool = False,
    cc0_only: bool = False,
    on_view: Optional[bool] = None,
    record_type: Literal["objects", "archives"] = "objects",
    limit: Annotated[int, Field(ge=1, le=SEARCH_MAX_LIMIT)] = SEARCH_DEFAULT_LIMIT,
    offset: Annotated[int, Field(ge=0)] = 0,
) -> ObjectSearchResults:
    """
    Search Smithsonian collection objects by keyword and filters.

    Returns compact summaries; pass an id to get_object for the full record.
    For "how many" questions use limit=1 and read total_count.

    Args:
        query: Keywords. Every word must match, so use 1-4 distinctive words, OR
            between alternatives ("muppet OR henson") and quotes for phrases.
            Leave out stop-words and questions. Empty matches everything.
        museum: Museum name or unit code, e.g. "American History", "NMAH",
            "Asian Art", "Natural History".
        object_type: Object type, e.g. "Paintings", "Puppets".
        maker: Creator name, e.g. "Winslow Homer".
        topic: Subject term, e.g. "Civil War".
        material: Material or medium, e.g. "bronze".
        date_from: Earliest year, such as 1860 or "1860s", matched by decade.
            Some records are dated by their subject, so later books about a
            period can match.
        date_to: Latest year, matched by decade.
        has_images: Only objects with images.
        cc0_only: Only objects with CC0 (public domain) media.
        on_view: true for objects on physical exhibit now, false for objects
            not on exhibit. Natural History (NMNH) has no exhibit data, so its
            objects never match true.
        record_type: "objects", or "archives" for archival collections and
            their folders and items (papers, photographs, recordings), which
            the API searches separately from objects.
        limit: Results per page.
        offset: Start position; pass next_offset to get the next page.

    Returns:
        ObjectSearchResults: Total count, pagination and object summaries.
    """
    unit = _resolve_museum(museum)
    date_start = _year_text(date_from)
    date_end = _year_text(date_to)
    try:
        date_clause(date_start, date_end)
    except ValueError as exc:
        raise ToolError(DATE_HELP) from exc

    filters = CollectionSearchFilter(
        query=query or None,
        unit_code=unit.code if unit else None,
        object_type=object_type,
        maker=maker,
        topic=topic,
        material=material,
        date_start=date_start,
        date_end=date_end,
        has_images=True if has_images else None,
        is_cc0=True if cc0_only else None,
        on_view=on_view,
        row_group=record_type,
        limit=limit,
        offset=offset,
    )
    result = await _search(filters)

    if (
        result.total_count == 0
        and unit
        and record_type == "objects"
        and unit.code in ARCHIVAL_UNIT_CODES
    ):
        raise _archival_only_error(unit)

    return ObjectSearchResults(
        total_count=result.total_count,
        returned=len(result.objects),
        offset=result.offset,
        next_offset=result.next_offset,
        museum=unit,
        objects=[summarize(obj) for obj in result.objects],
        note=search_note(filters, result, museum, unit),
    )


async def get_object(object_id: str) -> ObjectDetails:
    """
    Full record of one object: description, notes, materials, topics, rights,
    up to 10 images and the web_url of its page.

    Args:
        object_id: An id from search_objects or explore_topic results. Record
            ids such as "nmah_1448973" also work.

    Returns:
        ObjectDetails: The object record.
    """
    object_id = (object_id or "").strip()
    if not object_id:
        raise ToolError("object_id is required: use an id from search_objects.")
    client = await get_api_client()
    try:
        obj = await client.get_object_by_id(object_id)
    except APIError as exc:
        _raise_for_api_error(exc)
    if obj is None:
        raise ToolError(
            f"No object with id '{object_id}'. Use an id from search_objects results."
        )
    return details(obj)


async def list_museums() -> List[MuseumInfo]:
    """
    Smithsonian units in Open Access: codes, names, the record_type values that
    return their records, and the names the museum argument accepts. For counts
    use get_collection_stats.

    Returns:
        List[MuseumInfo]: One entry per unit code, plus NMNH for all Natural
        History departments.
    """
    client = await get_api_client()
    try:
        units = await client.get_units()
    except APIError as exc:
        _raise_for_api_error(exc)
    return [
        MuseumInfo(
            code=unit.code,
            name=unit.name,
            record_types=record_types(unit.code),
            aliases=[
                alias
                for alias in _ALIASES.get(unit.code, [])
                if alias != unit.name.lower()
            ],
        )
        for unit in units
    ]


async def explore_topic(
    topic: str,
    museum: Optional[str] = None,
    limit: Annotated[int, Field(ge=1, le=EXPLORE_MAX_LIMIT)] = EXPLORE_DEFAULT_LIMIT,
) -> TopicExploration:
    """
    A varied sample of objects about a topic, spread across museums in
    proportion to their matches and across object types, with counts by museum
    and type. Prefers objects with images whose title, type or subject names the
    topic. Use it for open-ended browsing; use search_objects to find specific
    things. Calls can return different samples.

    Args:
        topic: Topic keywords, e.g. "dinosaurs" or "jazz". Every word must match.
        museum: Optional museum name or unit code.
        limit: Number of objects to return.

    Returns:
        TopicExploration: The sample, the match count and facet counts.
    """
    topic = (topic or "").strip()
    if not topic:
        raise ToolError("topic is required, e.g. 'dinosaurs' or 'jazz'.")
    unit = _resolve_museum(museum)

    def filters(has_images: bool) -> CollectionSearchFilter:
        # The topic is always part of the query
        return CollectionSearchFilter(
            query=topic,
            unit_code=unit.code if unit else None,
            has_images=has_images or None,
            limit=EXPLORE_POOL_SIZE,
        )

    result = await _search(filters(True))
    total_count = result.total_count
    matches = "matches with images"
    named, others = rank_pool(result.objects, topic)
    if len(named) + len(others) < limit:
        # Too few with images: add the most relevant without images
        everything = await _search(filters(False))
        seen = {obj.id for obj in named + others}
        extra = rank_pool(
            [obj for obj in everything.objects if obj.id not in seen], topic
        )
        named += extra[0]
        others += extra[1]
        total_count = everything.total_count
        matches = "matches"

    picks = diverse_sample(named, limit)
    picks += diverse_sample(others, limit - len(picks))
    if total_count == 0 and unit and unit.code in ARCHIVAL_UNIT_CODES:
        raise _archival_only_error(unit, "explore_topic")
    note = explore_note(topic, total_count, matches, len(named), len(others))
    if is_whole_smithsonian(museum):
        note = whole_smithsonian_note(museum) + " " + note

    return TopicExploration(
        total_count=total_count,
        returned=len(picks),
        offset=0,
        next_offset=None,
        museum=unit,
        objects=[summarize(obj) for obj in picks],
        note=note,
        facets=facets(named or others),
    )


async def get_collection_stats(museum: Optional[str] = None) -> CollectionOverview:
    """
    Counts of searchable objects, archive records, objects with images and
    objects with CC0 media, for the whole collection or one museum. Each count
    equals the total_count of the matching search_objects call.

    Args:
        museum: Optional museum name or unit code.

    Returns:
        CollectionOverview: The counts.
    """
    return await _collection_counts(_resolve_museum(museum))


TOOLS = (
    (search_objects, "Search Objects"),
    (get_object, "Get Object"),
    (list_museums, "List Museums"),
    (explore_topic, "Explore Topic"),
    (get_collection_stats, "Get Collection Stats"),
)


def summary_of(function: Callable[..., Any]) -> str:
    """
    The text of a docstring before its Args or Returns section, on one line.

    Used as the description that clients show to the model, so developer
    sections and line wrapping do not cost tokens.

    Args:
        function: A documented function.

    Returns:
        str: The summary text.
    """
    text = inspect.getdoc(function) or ""
    text = re.split(r"\n\s*(?:Args|Returns|Raises):", text, maxsplit=1)[0]
    return " ".join(text.split())


def register_tools(server: FastMCP) -> None:
    """
    Register the five read-only tools on a server.

    Args:
        server: The FastMCP server.
    """
    for function, title in TOOLS:
        tool = FunctionTool.from_function(
            function,
            title=title,
            description=summary_of(function),
            annotations=READ_ONLY,
        )
        # Argument descriptions come from wrapped docstring lines
        for schema in tool.parameters.get("properties", {}).values():
            if isinstance(schema.get("description"), str):
                schema["description"] = " ".join(schema["description"].split())
        server.add_tool(tool)
