"""
Notes attached to tool results.

A note explains an empty or doubtful result and says what to change: a query
that reads like a sentence, filters that match nothing together, an on-view
search that cannot include Natural History, a maker matched by keyword, an
offset past the end, or a museum name that means every museum.
"""

import re
from typing import List, Optional

from .constants import NMNH_AGGREGATE_CODE, UNITS_WITHOUT_INDEXED_MAKERS
from .models import CollectionSearchFilter, MuseumRef, SearchResult
from .utils import is_whole_smithsonian, record_types

WHOLE_SMITHSONIAN_NOTE = (
    "museum='{museum}' means every Smithsonian museum, so no museum filter was "
    "applied."
)
NMNH_ON_VIEW_NOTE = (
    "Natural History (NMNH) records carry no on-exhibit data, so on_view=true "
    "never matches them. Search without on_view instead."
)
NO_MATCH_NOTE = (
    "No matches. Every word in query must match: use fewer or broader keywords, "
    "OR between alternatives, maker for names, or drop a filter."
)
NO_FILTER_MATCH_NOTE = (
    "No objects match {filters} together. Drop a filter or use a broader value."
)
MAKER_HINT = (
    " maker matches a full name or surname, such as 'Winslow Homer' or 'Homer'."
)
MAKER_KEYWORDS_NOTE = (
    "{name} ({code}) does not index creator names, so maker was matched as "
    "keywords and total_count can include works that only mention the name; "
    "their maker_match is false."
)
ON_VIEW_WITHOUT_MUSEUM_NOTE = (
    "Natural History (NMNH) publishes no exhibit data, so its objects never "
    "match on_view=true, even when on display."
)
SENTENCE_NOTE = (
    "query reads like a sentence, but every word must match, so these results "
    "can miss what was asked. Use 1-4 keywords and put the rest in filters "
    "(museum, on_view, maker, object_type, date_from, cc0_only)."
)
# Free-text queries with this many terms (a quoted phrase counts once) are
# treated as sentences.
SENTENCE_TERMS = 5
_QUERY_OPERATORS = frozenset({"AND", "OR", "NOT"})


def reads_like_a_sentence(query: Optional[str]) -> bool:
    """
    Whether a free-text query looks like a question or sentence.

    Args:
        query: The query.

    Returns:
        bool: True if it contains "?" or SENTENCE_TERMS or more terms, where a
        quoted phrase counts once and AND, OR and NOT are not counted.
    """
    if not query:
        return False
    if "?" in query:
        return True
    unquoted = re.sub(r'"[^"]*"', " PHRASE ", query)
    terms = [
        word
        for word in re.findall(r"[\w'-]+", unquoted)
        if word.upper() not in _QUERY_OPERATORS
    ]
    return len(terms) >= SENTENCE_TERMS


def whole_smithsonian_note(museum: str) -> str:
    """
    Say that a museum name meaning every museum applied no filter.

    Args:
        museum: The museum argument, such as "Smithsonian".

    Returns:
        str: The note.
    """
    return WHOLE_SMITHSONIAN_NOTE.format(museum=museum.strip())


def _applied_filters(
    filters: CollectionSearchFilter, unit: Optional[MuseumRef]
) -> List[str]:
    """
    The filters of a search, written as search_objects arguments.

    Args:
        filters: The search filters.
        unit: The museum filter, if any.

    Returns:
        List[str]: Entries such as "maker='Hokusai'" and "on_view=true".
    """
    applied = [f"museum={unit.code}"] if unit else []
    for argument, value in (
        ("object_type", filters.object_type),
        ("maker", filters.maker),
        ("topic", filters.topic),
        ("material", filters.material),
        ("date_from", filters.date_start),
        ("date_to", filters.date_end),
    ):
        if value and value.strip():
            applied.append(f"{argument}={' '.join(value.split())!r}")
    for argument, flag in (
        ("has_images", filters.has_images),
        ("cc0_only", filters.is_cc0),
        ("on_view", filters.on_view),
    ):
        if flag is not None:
            applied.append(f"{argument}={str(flag).lower()}")
    return applied


def _empty_result_note(
    filters: CollectionSearchFilter, unit: Optional[MuseumRef], sentence: bool
) -> Optional[str]:
    """
    Explain a search with no matches.

    Args:
        filters: The search filters.
        unit: The museum filter, if any.
        sentence: Whether the query reads like a sentence, which has its own note.

    Returns:
        Optional[str]: The note, or None when the sentence note covers it.
    """
    if (
        unit
        and filters.row_group == "archives"
        and "archives" not in record_types(unit.code)
    ):
        return f"{unit.name} has no archive records; use record_type='objects'."
    if unit and unit.code.startswith(NMNH_AGGREGATE_CODE) and filters.on_view:
        return NMNH_ON_VIEW_NOTE
    if sentence:
        return None
    applied = _applied_filters(filters, unit)
    if (filters.query or "").strip() in ("", "*") and applied:
        note = NO_FILTER_MATCH_NOTE.format(filters=", ".join(applied))
        if filters.maker and filters.maker.strip():
            note += MAKER_HINT
        return note
    return NO_MATCH_NOTE


def search_note(
    filters: CollectionSearchFilter,
    result: SearchResult,
    museum: Optional[str],
    unit: Optional[MuseumRef],
) -> Optional[str]:
    """
    Explain an empty or doubtful search_objects result.

    Args:
        filters: The search filters.
        result: The search result.
        museum: The museum argument as given.
        unit: The museum it resolved to, if any.

    Returns:
        Optional[str]: The notes that apply, joined, or None.
    """
    notes: List[str] = []
    sentence = reads_like_a_sentence(filters.query)
    if result.total_count == 0:
        empty = _empty_result_note(filters, unit, sentence)
        if empty:
            notes.append(empty)
    elif not result.objects and filters.offset >= result.total_count:
        notes.append(f"offset is past the last of {result.total_count} results.")
    if (
        result.total_count
        and filters.maker
        and filters.maker.strip()
        and unit
        and unit.code in UNITS_WITHOUT_INDEXED_MAKERS
    ):
        notes.append(MAKER_KEYWORDS_NOTE.format(name=unit.name, code=unit.code))
    if is_whole_smithsonian(museum):
        notes.append(whole_smithsonian_note(museum))
    if filters.on_view and unit is None:
        notes.append(ON_VIEW_WITHOUT_MUSEUM_NOTE)
    if sentence:
        notes.append(SENTENCE_NOTE)
    return " ".join(notes) or None


def explore_note(
    topic: str, total_count: int, matches: str, named: int, others: int
) -> str:
    """
    Describe an explore_topic sample.

    Args:
        topic: The topic.
        total_count: Matches of the search the pool came from.
        matches: What was matched, "matches" or "matches with images".
        named: Pooled objects that name the topic.
        others: Other pooled objects.

    Returns:
        str: The note.
    """
    if total_count == 0:
        return f"No objects match '{topic}'. Try a broader or different keyword."
    if named:
        return (
            f"{named} of the {named + others} most relevant of {total_count} "
            f"{matches} name the topic in their title, type or subjects; the "
            "sample and facets favor them. Call again for a different sample."
        )
    return (
        f"Sample of the {others} most relevant of {total_count} {matches}; none "
        "names the topic in its title, type or subjects, so check that the "
        "results fit."
    )
