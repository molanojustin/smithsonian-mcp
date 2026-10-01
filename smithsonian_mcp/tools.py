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

import inspect
import logging
import re
import time
from collections import Counter, deque
from typing import (
    Annotated,
    Any,
    Callable,
    Deque,
    Dict,
    List,
    NoReturn,
    Optional,
    Tuple,
)

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from .api_client import MAX_DATE_YEAR, MIN_DATE_YEAR, date_clause
from .constants import (
    ARCHIVAL_UNIT_CODES,
    MUSEUM_MAP,
    NMNH_AGGREGATE_CODE,
    UNIT_INFO,
)
from .context import get_api_client
from .models import (
    APIError,
    CollectionOverview,
    CollectionSearchFilter,
    CollectionStats,
    ImageSummary,
    MuseumCount,
    MuseumInfo,
    MuseumRef,
    ObjectDetails,
    ObjectSearchResults,
    ObjectSummary,
    SearchResult,
    SmithsonianObject,
    TopicExploration,
    TopicFacets,
)
from .utils import (
    normalize_unit_code,
    record_page_url,
    resolve_museum_code,
    validate_url,
)

logger = logging.getLogger(__name__)

SEARCH_DEFAULT_LIMIT = 10
SEARCH_MAX_LIMIT = 50
EXPLORE_DEFAULT_LIMIT = 12
EXPLORE_MAX_LIMIT = 30
# Rows fetched at random for explore_topic; the sample and facets come from it.
EXPLORE_POOL_SIZE = 60
EXPLORE_MAX_TYPE_FACETS = 10

MAX_IMAGES = 10
MAX_SUMMARY_MAKERS = 3
MAX_DETAIL_MAKERS = 10
MAX_LIST_ITEMS = 12
MAX_TITLE_CHARS = 200
MAX_DESCRIPTION_CHARS = 1500
MAX_SUMMARY_CHARS = 800
MAX_NOTES_CHARS = 1000
MAX_SHORT_TEXT_CHARS = 400

# /stats changes monthly; one cached copy serves list_museums and
# get_collection_stats.
STATS_CACHE_SECONDS = 6 * 60 * 60

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True, idempotentHint=True)

DATE_HELP = (
    f"date_from and date_to take four-digit years from {MIN_DATE_YEAR} to "
    f"{MAX_DATE_YEAR}, e.g. 1865. Dates match by decade."
)
UNKNOWN_MUSEUM_HELP = (
    "Use a museum name or unit code such as 'American History' (NMAH), "
    "'Natural History' (NMNH), 'American Art' (SAAM), 'Asian Art' (NMAA), "
    "'Air and Space' (NASM) or 'Portrait Gallery' (NPG); list_museums shows "
    "every unit."
)
NMNH_ON_VIEW_NOTE = (
    "Natural History (NMNH) records carry no on-exhibit data, so on_view=true "
    "never matches them. Search without on_view instead."
)
NO_MATCH_NOTE = (
    "No matches. Every word in query must match: use fewer or broader keywords, "
    "OR between alternatives, maker for names, or drop a filter."
)

# Aliases from MUSEUM_MAP left out of list_museums: misspellings and a wrong
# abbreviation that resolve_museum_code accepts but should not be advertised.
_HIDDEN_ALIASES = frozenset({"ahm", "botony", "sculture garden"})

_stats_cache: Dict[str, Tuple[float, CollectionStats]] = {}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def clear_caches() -> None:
    """Forget cached collection statistics so the next call fetches them."""
    _stats_cache.clear()


def _unit_name(code: Optional[str], fallback: Optional[str] = None) -> Optional[str]:
    """
    Display name of a unit code.

    Args:
        code: Unit code such as ``NMAH``.
        fallback: Name to use for codes without static information.

    Returns:
        Optional[str]: The unit name, the fallback or the code itself.
    """
    if code and code in UNIT_INFO:
        return UNIT_INFO[code]["name"]
    return fallback or code


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
    if museum is None or not museum.strip():
        return None
    code = resolve_museum_code(museum)
    if code is None:
        raise ToolError(f"Unknown museum '{museum.strip()}'. {UNKNOWN_MUSEUM_HELP}")
    return MuseumRef(code=code, name=_unit_name(code) or code)


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
    if exc.error in ("request_error", "stats_failed") or (exc.status_code or 0) >= 500:
        raise ToolError(
            "The Smithsonian API is not responding right now. Try again shortly."
        ) from exc
    raise exc


def _archival_only_error(unit: MuseumRef) -> ToolError:
    """
    Explain that a museum holds only archive records.

    Args:
        unit: The archival-only unit.

    Returns:
        ToolError: Error with a next step.
    """
    return ToolError(
        f"{unit.name} ({unit.code}) publishes only archival records, which object "
        "searches do not return. Search without museum, or pick a museum from "
        "list_museums that is not archival_only."
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


async def _collection_stats() -> CollectionStats:
    """
    Collection statistics from /stats, cached for STATS_CACHE_SECONDS.

    Returns:
        CollectionStats: Statistics with per-unit counts when /stats answered.
    """
    cached = _stats_cache.get("stats")
    if cached and time.monotonic() - cached[0] < STATS_CACHE_SECONDS:
        return cached[1]
    client = await get_api_client()
    try:
        stats = await client.get_collection_stats()
    except APIError as exc:
        _raise_for_api_error(exc)
    if stats.units:
        # Fallback figures without per-unit counts are not kept
        _stats_cache["stats"] = (time.monotonic(), stats)
    return stats


def _museum_counts(stats: CollectionStats) -> List[MuseumCount]:
    """
    Per-unit record counts from /stats, under the codes searches use.

    /stats still reports the legacy FSG (Freer|Sackler) unit next to NMAA; its
    records are searched as NMAA, so its counts are added to NMAA.

    Args:
        stats: Collection statistics.

    Returns:
        List[MuseumCount]: One entry per unit code, in /stats order.
    """
    merged: Dict[str, MuseumCount] = {}
    for unit in stats.units:
        code = normalize_unit_code(unit.unit_code) or unit.unit_code
        entry = merged.get(code)
        if entry is None:
            merged[code] = MuseumCount(
                code=code,
                name=_unit_name(code, unit.unit_name) or code,
                object_count=unit.total_objects,
                cc0=unit.cc0_objects,
            )
            continue
        entry.object_count += unit.total_objects
        if unit.cc0_objects is not None:
            entry.cc0 = (entry.cc0 or 0) + unit.cc0_objects
    return list(merged.values())


def _trim(text: Optional[str], limit: int) -> Optional[str]:
    """
    Shorten text to at most ``limit`` characters at a word boundary.

    Args:
        text: Text to shorten.
        limit: Maximum length, including the trailing ellipsis.

    Returns:
        Optional[str]: The text, shortened with "..." if it was too long.
    """
    if not text:
        return None
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 3]
    if " " in cut[limit // 2 :]:
        cut = cut[: cut.rindex(" ")]
    return cut.rstrip(" ,;:") + "..."


def _location_name(location: Optional[str]) -> Optional[str]:
    """
    Readable exhibition location.

    Exhibition blocks name the building by unit code ("NMAH"), optionally
    followed by a room; the code is replaced with the museum name.

    Args:
        location: Location as parsed by the client ("NMAH" or "NMAH, Gallery 3").

    Returns:
        Optional[str]: The location with a known building code spelled out.
    """
    if not location:
        return None
    building, _, rest = location.partition(", ")
    if building in UNIT_INFO:
        building = UNIT_INFO[building]["name"]
    return f"{building}, {rest}" if rest else building


def _web_url(obj: SmithsonianObject) -> Optional[str]:
    """
    Best human-readable page for an object.

    Order: the record_link, then the URL pattern for the record_id's museum,
    then the persistent guid (an ark link that resolves to the page), then the
    url field.

    Args:
        obj: Parsed object.

    Returns:
        Optional[str]: A validated http(s) URL, or None.
    """
    candidates = (obj.record_link, record_page_url(obj.record_id), obj.guid, obj.url)
    for candidate in candidates:
        url = validate_url(str(candidate)) if candidate else None
        if url:
            return url
    return None


def _thumbnail(obj: SmithsonianObject) -> Optional[str]:
    """
    First thumbnail (or image) URL of an object.

    Args:
        obj: Parsed object.

    Returns:
        Optional[str]: The URL, or None for objects without images.
    """
    for image in obj.images or []:
        url = image.thumbnail_url or image.url
        if url:
            return str(url)
    return None


def _summary_fields(obj: SmithsonianObject, max_makers: int) -> Dict[str, Any]:
    """
    Fields shared by ObjectSummary and ObjectDetails.

    Args:
        obj: Parsed object.
        max_makers: Maximum number of makers to list.

    Returns:
        Dict[str, Any]: Keyword arguments for the output models.
    """
    return {
        "id": obj.id,
        "title": _trim(obj.title, MAX_TITLE_CHARS) or "Untitled",
        "maker": list(obj.maker or [])[:max_makers],
        "date": obj.date,
        "museum_code": obj.unit_code,
        "museum_name": _unit_name(obj.unit_code, obj.unit_name),
        "object_type": obj.object_type,
        "on_view": obj.is_on_view,
        "exhibition_title": obj.exhibition_title,
        "exhibition_location": _location_name(obj.exhibition_location),
        "thumbnail_url": _thumbnail(obj),
        "web_url": _web_url(obj),
    }


def _summarize(obj: SmithsonianObject) -> ObjectSummary:
    """
    Compact summary of an object for result lists.

    Args:
        obj: Parsed object.

    Returns:
        ObjectSummary: The summary.
    """
    return ObjectSummary(**_summary_fields(obj, MAX_SUMMARY_MAKERS))


def _notes_without(notes: Optional[str], description: Optional[str]) -> Optional[str]:
    """
    Drop notes that repeat the description.

    The client joins up to three notes with newlines, cutting each at 500
    characters with "...", and also returns the note labelled Description.

    Args:
        notes: Newline-separated notes.
        description: The description, if any.

    Returns:
        Optional[str]: The remaining notes.
    """
    if not notes:
        return None
    kept = []
    for note in notes.split("\n"):
        if description and (
            note == description
            or (note.endswith("...") and description.startswith(note[:-3]))
        ):
            continue
        kept.append(note)
    return "\n".join(kept) or None


def _details(obj: SmithsonianObject) -> ObjectDetails:
    """
    Full but bounded record of an object.

    Args:
        obj: Parsed object.

    Returns:
        ObjectDetails: The record with trimmed text and at most MAX_IMAGES images.
    """
    images = list(obj.images or [])
    description = _trim(obj.description, MAX_DESCRIPTION_CHARS)
    return ObjectDetails(
        **_summary_fields(obj, MAX_DETAIL_MAKERS),
        record_id=obj.record_id,
        description=description,
        summary=_trim(obj.summary, MAX_SUMMARY_CHARS),
        notes=_trim(_notes_without(obj.notes, obj.description), MAX_NOTES_CHARS),
        dimensions=_trim(obj.dimensions, MAX_SHORT_TEXT_CHARS),
        materials=list(obj.materials or [])[:MAX_LIST_ITEMS],
        topics=list(obj.topics or [])[:MAX_LIST_ITEMS],
        place=list(obj.place or [])[:MAX_LIST_ITEMS],
        credit_line=_trim(obj.credit_line, MAX_SHORT_TEXT_CHARS),
        rights=_trim(obj.rights, MAX_SHORT_TEXT_CHARS),
        is_cc0=obj.is_cc0,
        images=[
            ImageSummary(
                url=str(image.url) if image.url else None,
                thumbnail_url=str(image.thumbnail_url) if image.thumbnail_url else None,
                iiif_url=str(image.iiif_url) if image.iiif_url else None,
                caption=_trim(image.caption, MAX_SHORT_TEXT_CHARS),
                is_cc0=image.is_cc0,
            )
            for image in images[:MAX_IMAGES]
        ],
        image_count=len(images) if len(images) > MAX_IMAGES else None,
    )


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


async def search_objects(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    query: str = "",
    museum: Optional[str] = None,
    object_type: Optional[str] = None,
    maker: Optional[str] = None,
    topic: Optional[str] = None,
    material: Optional[str] = None,
    date_from: Optional[int] = None,
    date_to: Optional[int] = None,
    has_images: bool = False,
    cc0_only: bool = False,
    on_view: Optional[bool] = None,
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
        date_from: Earliest year, matched with decade precision.
        date_to: Latest year, matched with decade precision.
        has_images: Only objects with images.
        cc0_only: Only objects with CC0 (public domain) media.
        on_view: true for objects on physical exhibit now, false for objects
            not on exhibit.
        limit: Results per page.
        offset: Start position; pass next_offset to get the next page.

    Returns:
        ObjectSearchResults: Total count, pagination and object summaries.
    """
    unit = _resolve_museum(museum)
    date_start = str(date_from) if date_from is not None else None
    date_end = str(date_to) if date_to is not None else None
    try:
        date_clause(date_start, date_end)
    except ValueError as exc:
        raise ToolError(DATE_HELP) from exc

    result = await _search(
        CollectionSearchFilter(
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
            limit=limit,
            offset=offset,
        )
    )

    note = None
    if result.total_count == 0:
        if unit and unit.code in ARCHIVAL_UNIT_CODES:
            raise _archival_only_error(unit)
        if unit and unit.code.startswith(NMNH_AGGREGATE_CODE) and on_view:
            note = NMNH_ON_VIEW_NOTE
        else:
            note = NO_MATCH_NOTE
    elif not result.objects and offset >= result.total_count:
        note = f"offset is past the last of {result.total_count} results."

    return ObjectSearchResults(
        total_count=result.total_count,
        returned=len(result.objects),
        offset=result.offset,
        next_offset=result.next_offset,
        museum=unit,
        objects=[_summarize(obj) for obj in result.objects],
        note=note,
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
    return _details(obj)


async def list_museums() -> List[MuseumInfo]:
    """
    Smithsonian units in Open Access with their codes, object counts and the
    names the museum argument accepts. archival_only units hold archive records,
    which object searches do not return.

    Returns:
        List[MuseumInfo]: One entry per unit code, plus NMNH for all Natural
        History departments.
    """
    client = await get_api_client()
    units = await client.get_units()
    counts: Dict[str, int] = {}
    try:
        stats = await _collection_stats()
        counts = {museum.code: museum.object_count for museum in _museum_counts(stats)}
    except (ToolError, APIError) as exc:
        cause = exc if isinstance(exc, APIError) else exc.__cause__
        if isinstance(cause, APIError) and cause.error == "api_key_rejected":
            raise
        logger.warning("Listing museums without counts: %s", exc)
    if counts:
        counts[NMNH_AGGREGATE_CODE] = sum(
            count
            for code, count in counts.items()
            if code.startswith(NMNH_AGGREGATE_CODE)
        )

    return [
        MuseumInfo(
            code=unit.code,
            name=unit.name,
            object_count=counts.get(unit.code),
            archival_only=True if unit.archival_only else None,
            aliases=_ALIASES.get(unit.code, []),
        )
        for unit in units
    ]


def _type_key(obj: SmithsonianObject) -> str:
    """Case-insensitive object type of an object, for grouping."""
    return (obj.object_type or "").strip().lower()


def _interleave_types(objects: List[SmithsonianObject]) -> Deque[SmithsonianObject]:
    """
    Order objects so that consecutive picks differ in object type.

    Args:
        objects: Objects of one museum, in pool order.

    Returns:
        Deque[SmithsonianObject]: Round-robin order across object types.
    """
    buckets: Dict[str, Deque[SmithsonianObject]] = {}
    for obj in objects:
        buckets.setdefault(_type_key(obj), deque()).append(obj)
    ordered: Deque[SmithsonianObject] = deque()
    while buckets:
        for key in list(buckets):
            ordered.append(buckets[key].popleft())
            if not buckets[key]:
                del buckets[key]
    return ordered


def _diverse_sample(
    pool: List[SmithsonianObject], limit: int
) -> List[SmithsonianObject]:
    """
    Pick objects round-robin across museums, and across types within a museum.

    Args:
        pool: Candidate objects, preferred ones first.
        limit: Number of objects to pick.

    Returns:
        List[SmithsonianObject]: The sample.
    """
    groups: Dict[str, List[SmithsonianObject]] = {}
    for obj in pool:
        groups.setdefault(obj.unit_code or "", []).append(obj)
    queues = [_interleave_types(group) for group in groups.values()]
    picks: List[SmithsonianObject] = []
    while len(picks) < limit and any(queues):
        for queue in queues:
            if queue and len(picks) < limit:
                picks.append(queue.popleft())
    return picks


def _facets(pool: List[SmithsonianObject]) -> TopicFacets:
    """
    Counts by museum and by object type over the sampled pool.

    Args:
        pool: The sampled objects.

    Returns:
        TopicFacets: Museum counts by unit code and the most common types.
    """
    museums = Counter(obj.unit_code for obj in pool if obj.unit_code)
    labels: Dict[str, str] = {}
    types: Counter = Counter()
    for obj in pool:
        key = _type_key(obj)
        if key:
            labels.setdefault(key, obj.object_type.strip()[:1].upper() + key[1:])
            types[key] += 1
    return TopicFacets(
        museums=dict(museums.most_common()),
        object_types={
            labels[key]: count
            for key, count in types.most_common(EXPLORE_MAX_TYPE_FACETS)
        },
    )


async def explore_topic(
    topic: str,
    museum: Optional[str] = None,
    limit: Annotated[int, Field(ge=1, le=EXPLORE_MAX_LIMIT)] = EXPLORE_DEFAULT_LIMIT,
) -> TopicExploration:
    """
    A varied random sample of objects about a topic, spread across museums and
    object types, with counts by museum and type. Use it for open-ended
    browsing; use search_objects to find specific things. Each call returns a
    different sample.

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
    unit_code = unit.code if unit else None

    # Objects with images first; the topic is always part of the query
    with_images = await _search(
        CollectionSearchFilter(
            query=topic,
            unit_code=unit_code,
            has_images=True,
            sort="random",
            limit=EXPLORE_POOL_SIZE,
        )
    )
    pool = list(with_images.objects)
    total_count = with_images.total_count
    matches = "matches with images"
    picks = _diverse_sample(pool, limit)
    if len(picks) < limit:
        # Too few with images: fill up with objects without images
        everything = await _search(
            CollectionSearchFilter(
                query=topic, unit_code=unit_code, sort="random", limit=EXPLORE_POOL_SIZE
            )
        )
        seen = {obj.id for obj in pool}
        rest = [obj for obj in everything.objects if obj.id not in seen]
        picks += _diverse_sample(rest, limit - len(picks))
        pool += rest
        total_count = everything.total_count
        matches = "matches"

    if total_count == 0:
        if unit and unit.code in ARCHIVAL_UNIT_CODES:
            raise _archival_only_error(unit)
        note = f"No objects match '{topic}'. Try a broader or different keyword."
    else:
        note = (
            f"Random sample; facets count a pool of {len(pool)} of the "
            f"{total_count} {matches}. Call again for a different sample."
        )

    return TopicExploration(
        total_count=total_count,
        returned=len(picks),
        offset=0,
        next_offset=None,
        museum=unit,
        objects=[_summarize(obj) for obj in picks],
        note=note,
        facets=_facets(pool),
    )


async def get_collection_stats() -> CollectionOverview:
    """
    Collection totals (all records, CC0 records, objects with images) and
    record counts per museum.

    Returns:
        CollectionOverview: Totals and per-museum counts, largest first.
    """
    stats = await _collection_stats()
    museums = sorted(
        _museum_counts(stats), key=lambda museum: museum.object_count, reverse=True
    )
    if stats.units:
        as_of = stats.last_updated.strftime("%Y-%m")
        note = (
            "Counts are from the API /stats endpoint and include archival records; "
            "with_images counts searchable objects that have images."
        )
    else:
        as_of = None
        note = stats.notes
    return CollectionOverview(
        total_objects=stats.total_objects,
        cc0=stats.total_cc0,
        with_images=stats.total_with_images,
        as_of=as_of,
        museums=museums,
        note=note,
    )


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
        server.tool(
            function,
            title=title,
            description=summary_of(function),
            annotations=READ_ONLY,
        )
