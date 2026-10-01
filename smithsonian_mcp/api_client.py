"""
HTTP client for interacting with the Smithsonian Open Access API via api.data.gov.

Search filters are expressed as fielded terms inside the ``q`` parameter because
the API has no separate filter parameter. The API key is sent only in the
``X-Api-Key`` header so it never appears in request URLs or logs.
"""

import asyncio
import json
import logging
import re
import string
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx
from pydantic import HttpUrl, ValidationError

from .config import Config
from .constants import (
    ARCHIVAL_UNIT_CODES,
    KNOWN_UNIT_CODES,
    NMNH_AGGREGATE_CODE,
    UNIT_INFO,
)
from .models import (
    SmithsonianObject,
    SearchResult,
    CollectionSearchFilter,
    ImageData,
    APIError,
    SmithsonianUnit,
    CollectionStats,
    UnitStats,
)
from .utils import (
    clean_text,
    escape_query_phrase,
    escape_query_term,
    mask_api_key,
    unit_code_query_clause,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.si.edu/openaccess/api/v1.0/"

# The API accepts rows in 0..1000; larger values silently return 10 rows.
MAX_ROWS = 1000

DEFAULT_TIMEOUT_SECONDS = 30.0

# Fielded clauses for boolean filters, verified against the live API.
HAS_IMAGES_CLAUSE = 'online_media_type:"Images"'
IS_CC0_CLAUSE = 'media_usage:"CC0"'
ON_VIEW_CLAUSE = 'onPhysicalExhibit:"Yes"'
# "AND NOT onPhysicalExhibit" undercounts on this API; a match-all group does not.
NOT_ON_VIEW_CLAUSE = '(* NOT onPhysicalExhibit:"Yes")'

# freetext.name labels that describe subjects or owners rather than makers.
_NON_MAKER_LABELS = frozenset(
    {
        "sitter",
        "subject",
        "depicted",
        "associated person",
        "associated name",
        "associated institution",
        "owner",
        "previous owner",
        "donor",
    }
)

# ---------------------------------------------------------------------------
# Query building
# ---------------------------------------------------------------------------

_BOOLEAN_OPERATORS = {
    "AND": "AND",
    "&&": "AND",
    "OR": "OR",
    "||": "OR",
    "NOT": "NOT",
    "!": "NOT",
}
_GROUP_PREFIXES = frozenset({"+", "-", "!"})
_RANGE_RE = re.compile(r"^[\[{]\s*\S+\s+TO\s+\S+\s*[\]}]$")
_YEAR_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")
# Letters, digits, spaces and the punctuation found in personal names.
_PERSON_NAME_RE = re.compile(r"^[^\W_][\w .,'’-]*$")
_NAME_SUFFIX_RE = re.compile(r"[,\s]+(?:jr|sr|ii|iii|iv)\.?$", re.IGNORECASE)
# What may follow a vocabulary term in a qualified index term, e.g.
# "Dresses (garments)", "Civil War, 1861-1865", "Camera; Rollfilm", "Cup/Mug".
_QUALIFIER_SEPARATORS = (" (", ",", ";", "/", " /", ":")
# Topics also have narrower terms after a space ("African American women"),
# which covers " (" and " /".
_NARROWER_SEPARATORS = (" ", ",", ";", "/", ":")
# What may follow a name in a longer indexed name: "Lockheed Aircraft
# Corporation", "Homer, Winslow", "Lockheed-Georgia Company", "Gorham/Textron",
# "Colt's Patent Firearms Manufacturing Company".
_NAME_BOUNDARIES = (" ", ",", "-", "/", "'s")


@dataclass
class _QueryNode:
    """Node of a parsed free-text query."""

    kind: str  # "atom", "and", "or", "not" or "group"
    text: str = ""
    children: List["_QueryNode"] = field(default_factory=list)


def _find_closing_quote(text: str, start: int) -> int:
    """Return the index of the closing double quote at or after start, or -1."""
    index = start
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == '"':
            return index
        index += 1
    return -1


def _read_word(text: str, index: int) -> Tuple[str, int]:
    """
    Read one query word starting at index.

    Quoted phrases and ``[a TO b]`` ranges are kept whole. Unmatched quotes are
    dropped, and stray range brackets, ``?`` (a single-character wildcard, which
    makes "Diamond?" match nothing) and ``!`` after the first character are
    escaped.

    Args:
        text: Full query text.
        index: Position of the first character of the word.

    Returns:
        Tuple[str, int]: The word and the position after it.
    """
    parts: List[str] = []
    length = len(text)
    while index < length:
        char = text[index]
        if char == "\\":
            if index + 1 < length:
                parts.append(text[index : index + 2])
            else:
                parts.append("\\\\")
            index += 2
            continue
        if char == '"':
            end = _find_closing_quote(text, index + 1)
            if end < 0:
                index += 1
                continue
            parts.append(text[index : end + 1])
            index = end + 1
            continue
        if char in "[{":
            closer = text.find("]" if char == "[" else "}", index + 1)
            candidate = text[index : closer + 1] if closer >= 0 else ""
            if candidate and _RANGE_RE.match(candidate):
                parts.append(candidate)
                index = closer + 1
                continue
            parts.append("\\" + char)
            index += 1
            continue
        if char in "]}?" or (char == "!" and parts):
            parts.append("\\" + char)
            index += 1
            continue
        if char.isspace() or char in "()":
            break
        parts.append(char)
        index += 1
    return "".join(parts), index


def _is_search_term(word: str) -> bool:
    """
    Whether a word can match anything on its own.

    Words without a letter or digit ("&", an em dash, a lone ":") are dropped from
    the query, as the API's analyzer does for an unparenthesized query; as required
    AND terms they would match nothing. ``*`` and ``*:*`` are kept as match-all.
    """
    return word in ("*", "*:*") or any(char.isalnum() for char in word)


def _tokenize_query(text: str) -> List[Tuple[str, str]]:
    """
    Split a free-text query into ATOM, OP, LPAREN and RPAREN tokens.

    Args:
        text: User query.

    Returns:
        List[Tuple[str, str]]: Tokens as (kind, value) pairs. LPAREN values hold a
        field or +/- prefix written directly before the parenthesis.
    """
    tokens: List[Tuple[str, str]] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if char == "(":
            tokens.append(("LPAREN", ""))
            index += 1
            continue
        if char == ")":
            tokens.append(("RPAREN", ""))
            index += 1
            continue
        word, index = _read_word(text, index)
        if (
            index < length
            and text[index] == "("
            and (word.endswith(":") or word in _GROUP_PREFIXES)
        ):
            tokens.append(("LPAREN", word))
            index += 1
            continue
        if word in _BOOLEAN_OPERATORS:
            tokens.append(("OP", _BOOLEAN_OPERATORS[word]))
            continue
        while word.endswith(":") and not word.endswith("\\:"):
            # "Star Wars: A New Hope" - a colon followed by a space is punctuation
            word = word[:-1]
        if _is_search_term(word):
            tokens.append(("ATOM", word))
    return tokens


def _combine(kind: str, items: List[_QueryNode]) -> Optional[_QueryNode]:
    """Join nodes with an operator, flattening nested nodes of the same kind."""
    flat: List[_QueryNode] = []
    for item in items:
        if item.kind == kind:
            flat.extend(item.children)
        else:
            flat.append(item)
    if not flat:
        return None
    if len(flat) == 1:
        return flat[0]
    return _QueryNode(kind, children=flat)


class _QueryParser:
    """
    Forgiving parser for free-text queries.

    Precedence is NOT, then AND (explicit or implied by whitespace), then OR.
    Unbalanced parentheses and dangling operators are dropped.
    """

    def __init__(self, tokens: List[Tuple[str, str]]):
        self.tokens = tokens
        self.pos = 0

    def _peek(self) -> Optional[Tuple[str, str]]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def parse(self) -> Optional[_QueryNode]:
        """
        Parse all tokens.

        Returns:
            Optional[_QueryNode]: Root node, or None if the query has no terms.
        """
        parts: List[_QueryNode] = []
        while self._peek() is not None:
            start = self.pos
            node = self._parse_or()
            if node is not None:
                parts.append(node)
            if self.pos == start or (
                self._peek() is not None and self._peek()[0] == "RPAREN"
            ):
                self.pos += 1  # skip a stray ")" or anything unparseable
        return _combine("and", parts)

    def _parse_or(self) -> Optional[_QueryNode]:
        items: List[_QueryNode] = []
        node = self._parse_and()
        if node is not None:
            items.append(node)
        while self._peek() == ("OP", "OR"):
            self.pos += 1
            node = self._parse_and()
            if node is not None:
                items.append(node)
        return _combine("or", items)

    def _parse_and(self) -> Optional[_QueryNode]:
        items: List[_QueryNode] = []
        while True:
            token = self._peek()
            if token is None or token[0] == "RPAREN" or token == ("OP", "OR"):
                break
            if token == ("OP", "AND"):
                self.pos += 1
                continue
            node = self._parse_unary()
            if node is not None:
                items.append(node)
        return _combine("and", items)

    def _parse_unary(self) -> Optional[_QueryNode]:
        if self._peek() == ("OP", "NOT"):
            self.pos += 1
            token = self._peek()
            if token is None or token[0] in ("RPAREN", "OP") and token[1] != "NOT":
                return None
            operand = self._parse_unary()
            return _QueryNode("not", children=[operand]) if operand else None
        return self._parse_primary()

    def _parse_primary(self) -> Optional[_QueryNode]:
        kind, value = self.tokens[self.pos]
        self.pos += 1
        if kind == "ATOM":
            return _QueryNode("atom", text=value)
        if kind == "LPAREN":
            inner = self._parse_or()
            if self._peek() is not None and self._peek()[0] == "RPAREN":
                self.pos += 1
            if inner is None:
                return None
            if value:
                return _QueryNode("group", text=value, children=[inner])
            return inner
        return None


def _serialize_query(node: _QueryNode, nested: bool = False) -> str:
    """
    Render a parsed query with explicit operators and grouping.

    Args:
        node: Node to render.
        nested: Whether the node is an operand of another operator.

    Returns:
        str: Query text.
    """
    if node.kind == "atom":
        return node.text
    if node.kind == "group":
        return f"{node.text}({_serialize_query(node.children[0])})"
    if node.kind == "not":
        return f"NOT {_serialize_query(node.children[0], nested=True)}"
    joiner = " AND " if node.kind == "and" else " OR "
    text = joiner.join(_serialize_query(child, nested=True) for child in node.children)
    return f"({text})" if nested else text


def normalize_free_text_query(query: Optional[str]) -> Optional[str]:
    """
    Make the operators of a free-text query explicit.

    The API treats whitespace inside parentheses as OR, so ``(bert puppet)``
    matches either word. Words without an operator are joined with AND, and OR
    operands are grouped so that ``bert puppet OR muppet`` means
    ``(bert AND puppet) OR muppet``.

    Args:
        query: User query, possibly with AND, OR, NOT, phrases and parentheses.

    Returns:
        Optional[str]: Normalized query, or None if it has no search terms.
    """
    tree = _parse_free_text(query)
    return _serialize_query(tree) if tree is not None else None


def _parse_free_text(query: Optional[str]) -> Optional[_QueryNode]:
    """Parse a free-text query, returning None if it has no search terms."""
    if not query or not query.strip():
        return None
    return _QueryParser(_tokenize_query(query)).parse()


def _collapse_whitespace(value: Any) -> str:
    """Return the value as a single-line string with collapsed whitespace."""
    return " ".join(str(value).split())


def _capitalize_first(value: str) -> str:
    """Upper-case the first character and leave the rest unchanged."""
    return value[:1].upper() + value[1:]


def _capitalize_words(value: str) -> str:
    """Upper-case the first character of each space-separated word."""
    return " ".join(_capitalize_first(word) for word in value.split(" "))


def _toggle_plural(value: str) -> Optional[str]:
    """
    Return the singular of a plural English word or the plural of a singular one.

    Only the end of the value is changed, so multi-word values toggle their last
    word. Returns None when the value does not end with a letter.
    """
    if not value or not value[-1].isalpha():
        return None
    lower = value.lower()

    def suffix(text: str) -> str:
        return text.upper() if value.isupper() else text

    if lower.endswith("ies") and len(lower) > 4:
        return value[:-3] + suffix("y")
    if lower.endswith(("sses", "ches", "shes", "xes")):
        return value[:-2]
    if lower.endswith("s") and not lower.endswith("ss"):
        return value[:-1]
    if lower.endswith(("ss", "ch", "sh", "x")):
        return value + suffix("es")
    if lower.endswith("y") and len(lower) > 1 and lower[-2] not in "aeiou":
        return value[:-1] + suffix("ies")
    return value + suffix("s")


def vocabulary_variants(value: str) -> List[str]:
    """
    Case and singular/plural variants of a controlled-vocabulary value.

    Fielded terms such as ``object_type:"Paintings"`` are case-sensitive and the
    vocabularies mix forms ("Paintings", "painting", "Certified Proof").

    Args:
        value: User supplied value, e.g. "painting".

    Returns:
        List[str]: Distinct variants, the original first.
    """
    base = _collapse_whitespace(value)
    if not base:
        return []
    variants: List[str] = []
    for form in (
        base,
        base.lower(),
        _capitalize_first(base.lower()),
        string.capwords(base),
    ):
        for candidate in (form, _toggle_plural(form)):
            if candidate and candidate not in variants:
                variants.append(candidate)
    return variants


def _prefix_wildcard(prefix: str) -> str:
    """
    Escape a prefix, keeping a trailing space, and append the ``*`` wildcard.

    Args:
        prefix: Literal prefix such as "Lockheed " or "Dresses (".

    Returns:
        str: Wildcard term such as ``Lockheed\\ *``.
    """
    trailing_space = prefix.endswith(" ")
    escaped = escape_query_term(prefix)
    return f"{escaped}\\ *" if trailing_space else f"{escaped}*"


def vocabulary_clause(
    field_name: str, value: str, narrower: bool = False
) -> Optional[str]:
    """
    Build the clause for a controlled-vocabulary filter (object_type, topic).

    Index terms are often qualified: "Dresses (garments)", "Coins (money)",
    "Civil War, 1861-1865", "Camera; Rollfilm", "Sculpture/Carving/Figures". The
    clause matches each case and singular/plural variant exactly or followed by
    one of `` (``, ``,``, ``;``, ``/`` or ``:``. A bare prefix is not used because
    it over-matches ("hat" would match "Hatchets", "letter" "Letterpress").

    Args:
        field_name: Indexed field, e.g. ``object_type``.
        value: User supplied value, e.g. "dress".
        narrower: Also match narrower terms that start with the value as typed and a
            space ("African American women" for "African American"); used for
            topics, where such terms are subdivisions rather than other things.

    Returns:
        Optional[str]: Query clause, or None for an empty value.
    """
    variants = vocabulary_variants(value)
    if not variants:
        return None
    typed = variants[0].lower()
    terms = [escape_query_phrase(variant) for variant in variants]
    for variant in variants:
        # Narrower terms only for the value as typed: "Landscapes" covers
        # "Landscapes in art" but not "Landscape architecture"
        if narrower and variant.lower() == typed:
            separators = _NARROWER_SEPARATORS
        else:
            separators = _QUALIFIER_SEPARATORS
        for separator in separators:
            terms.append(_prefix_wildcard(variant + separator))
    return f"{field_name}:({' OR '.join(terms)})"


def _strip_name_suffix(name: str) -> str:
    """Remove a trailing generational suffix such as "Jr." or "III"."""
    return _NAME_SUFFIX_RE.sub("", name).strip()


def maker_clause(maker: str) -> Optional[str]:
    """
    Build the clause for a maker filter.

    Names are indexed as "Last, First" (e.g. "Homer, Winslow"), case-sensitively,
    and organizations under their full names ("Lockheed Aircraft Corporation").
    The clause matches the name as given, with capitalized words, and inverted to
    "Last, First" (after dropping Jr./Sr./II/III/IV), each exactly or followed by
    further words. Prefixes only extend at a word boundary, so "Smith" does not
    match "Smithsonian" and "Colt" does not match "Coltrane".

    Args:
        maker: Maker name, e.g. "Winslow Homer", "Thomas, Alma" or "Lockheed".

    Returns:
        Optional[str]: Query clause, or None for an empty name.
    """
    base = _collapse_whitespace(maker)
    if not base:
        return None
    variants: List[str] = []
    prefixes: List[str] = []

    def add(collection: List[str], value: str) -> None:
        if value and value not in collection:
            collection.append(value)

    add(variants, base)
    add(variants, _capitalize_words(base))
    if _PERSON_NAME_RE.match(base):
        # As given: "Lockheed" -> "Lockheed Aircraft", "Lockheed-Georgia Company"
        add(prefixes, _capitalize_words(base))
        stem = _strip_name_suffix(base)
        words = stem.split(" ")
        if "," not in stem and len(words) >= 2:
            inverted = f"{words[-1]}, {' '.join(words[:-1])}"
            add(variants, _capitalize_words(inverted))
            add(variants, inverted)
            # "King, Martin Luther" -> "King, Martin Luther, Jr."
            add(prefixes, _capitalize_words(inverted))
        elif "," in stem:
            add(prefixes, _capitalize_words(stem))

    terms = [f"name:{escape_query_phrase(value)}" for value in variants]
    for prefix in prefixes:
        boundaries = _NAME_BOUNDARIES if "," not in prefix else (" ", ",")
        for boundary in boundaries:
            terms.append(f"name:{_prefix_wildcard(prefix + boundary)}")
    if len(terms) == 1:
        return terms[0]
    return f"({' OR '.join(terms)})"


def _parse_year(value: Optional[str]) -> Optional[int]:
    """Extract a four-digit year between 1000 and 2999 from a date string."""
    if value is None:
        return None
    match = _YEAR_RE.search(str(value))
    if not match:
        return None
    year = int(match.group(1))
    return year if 1000 <= year <= 2999 else None


def date_clause(date_start: Optional[str], date_end: Optional[str]) -> Optional[str]:
    """
    Build a decade range clause for date filtering.

    The ``date`` field holds decade terms such as "1950s", which sort correctly as
    text for four-digit years, so a range query selects the decades in between.

    Args:
        date_start: Start year or date (e.g. "1943" or "1943-05-01").
        date_end: End year or date.

    Returns:
        Optional[str]: Clause such as ``date:["1940s" TO "1960s"]``, or None.
    """
    start = _parse_year(date_start)
    end = _parse_year(date_end)
    for label, raw, parsed in (
        ("date_start", date_start, start),
        ("date_end", date_end, end),
    ):
        if raw not in (None, "") and parsed is None:
            logger.warning(
                "Ignoring %s %r: only four-digit years 1000-2999 are supported",
                label,
                raw,
            )
    if start is None and end is None:
        return None
    if start is not None and end is not None and start > end:
        start, end = end, start
    lower = f'"{start // 10 * 10}s"' if start is not None else "*"
    upper = f'"{end // 10 * 10}s"' if end is not None else "*"
    return f"date:[{lower} TO {upper}]"


def build_filter_clauses(filters: CollectionSearchFilter) -> List[str]:
    """
    Translate the filters of a CollectionSearchFilter into fielded query clauses.

    Args:
        filters: Search filters.

    Returns:
        List[str]: Clauses to AND with the free-text query.
    """
    clauses: List[str] = []
    unit_clause = unit_code_query_clause(filters.unit_code)
    if unit_clause:
        clauses.append(unit_clause)
    object_type = vocabulary_clause("object_type", filters.object_type or "")
    if object_type:
        clauses.append(object_type)
    if filters.maker and filters.maker.strip():
        clause = maker_clause(filters.maker)
        if clause:
            clauses.append(clause)
    topic = vocabulary_clause("topic", filters.topic or "", narrower=True)
    if topic:
        clauses.append(topic)
    if filters.material and filters.material.strip():
        clauses.append(f"physicalDescription:{escape_query_phrase(filters.material)}")
    dates = date_clause(filters.date_start, filters.date_end)
    if dates:
        clauses.append(dates)
    if filters.has_images:
        clauses.append(HAS_IMAGES_CLAUSE)
    if filters.is_cc0:
        clauses.append(IS_CC0_CLAUSE)
    if filters.on_view is True:
        clauses.append(ON_VIEW_CLAUSE)
    elif filters.on_view is False:
        clauses.append(NOT_ON_VIEW_CLAUSE)
    return clauses


def build_search_query(filters: CollectionSearchFilter) -> str:
    """
    Build the ``q`` parameter for a search.

    The free-text query is normalized and wrapped in parentheses, then each filter
    is appended as a fielded clause joined with AND, e.g.
    ``(muppet OR henson) AND unit_code:NMAH AND onPhysicalExhibit:"Yes"``.
    An empty query becomes ``*``.

    Args:
        filters: Search filters.

    Returns:
        str: Value for the ``q`` parameter.
    """
    tree = _parse_free_text(filters.query)
    if tree is not None and tree.kind == "atom" and tree.text == "*":
        tree = None
    base = _serialize_query(tree) if tree is not None else None
    clauses = build_filter_clauses(filters)
    if not clauses:
        if base is None:
            return "*"
        if tree is not None and tree.kind == "or":
            # The API applies a top-level OR as AND unless it is grouped
            return f"({base}) AND *"
        return base
    head = f"({base})" if base else "*"
    return " AND ".join([head, *clauses])


# ---------------------------------------------------------------------------
# Response parsing helpers
# ---------------------------------------------------------------------------


def _as_dict(value: Any) -> Dict[str, Any]:
    """Return value if it is a dict, else an empty dict."""
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    """Return value as a list (None becomes an empty list)."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _content_of(item: Any) -> Optional[str]:
    """Return the text of a freetext entry ({"label", "content"}) or a string."""
    if isinstance(item, dict):
        content = item.get("content")
        return content if isinstance(content, str) else None
    return item if isinstance(item, str) else None


def _label_of(item: Any) -> str:
    """Return the lowercase label of a freetext entry."""
    if isinstance(item, dict) and isinstance(item.get("label"), str):
        return item["label"].strip().lower()
    return ""


def _first_text(*candidates: Any) -> Optional[str]:
    """Return the first non-empty string content among candidate entry lists."""
    for candidate in candidates:
        for item in _as_list(candidate):
            text = _content_of(item)
            if text and text.strip():
                return text
    return None


def _strings(value: Any) -> List[str]:
    """Return the non-empty strings (or entry contents) of a list."""
    result = []
    for item in _as_list(value):
        text = _content_of(item)
        if text and text.strip():
            result.append(text)
    return result


def _safe_url(value: Any) -> Optional[HttpUrl]:
    """Validate an http(s) URL, returning None for anything else."""
    if not isinstance(value, str) or not value.startswith(("http://", "https://")):
        return None
    try:
        return HttpUrl(value)
    except (ValueError, TypeError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    """Convert to int if possible, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _parse_timestamp(value: Any) -> Optional[datetime]:
    """Parse an epoch-seconds value (int or digit string) to a UTC datetime."""
    seconds = _safe_int(value)
    if seconds is None or seconds <= 0:
        return None
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _parse_stats_time(value: Any) -> Optional[datetime]:
    """Parse the /stats ``time`` value (e.g. "2026-09")."""
    if not isinstance(value, str):
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def _object_id_candidates(object_id: str) -> List[str]:
    """
    ID formats to try with /content, most likely first.

    ``/content`` accepts search IDs (``ld1-...``) and EDAN URLs
    (``edanmdm:nmah_1448973``). Legacy dash IDs and bare record IDs are retried
    as EDAN URLs.
    """
    candidates = [object_id]
    lower = object_id.lower()
    if lower.startswith("edanmdm-"):
        candidates.append(f"edanmdm:{object_id[len('edanmdm-'):]}")
    elif not lower.startswith(("edanmdm:", "ld1-")):
        candidates.append(f"edanmdm:{object_id}")
    return candidates


class SmithsonianAPIClient:
    """
    Client for interacting with the Smithsonian Open Access API.

    This client handles authentication, query building and data transformation
    for the Smithsonian collections available through api.data.gov.
    """

    # Unit codes from /terms/unit_code, shared by all clients in the process.
    _unit_codes_cache: ClassVar[Optional[List[str]]] = None

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        """
        Initialize the API client.

        Args:
            api_key: API key. If not provided, it will be read from `Config.API_KEY`.
            base_url: API base URL.
            timeout: Request timeout in seconds.
            transport: Optional httpx transport, e.g. a mock transport for tests.

        Raises:
            ValueError: If no API key is available.
        """
        key = api_key or Config.API_KEY
        if not key or not key.strip():
            raise ValueError(
                "API key is required. Please provide one or set it in the config."
            )
        self.api_key = key.strip()
        self.base_url = base_url
        self.timeout = timeout
        self._transport = transport
        self.session: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "SmithsonianAPIClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self) -> None:
        """Initialize the HTTP session. The API key is sent only as a header."""
        if self.session is None:
            self.session = httpx.AsyncClient(
                headers={
                    "X-Api-Key": self.api_key,
                    "User-Agent": Config.USER_AGENT,
                    "Accept": "application/json",
                },
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                transport=self._transport,
            )

    async def disconnect(self) -> None:
        """Close the HTTP session."""
        if self.session:
            session, self.session = self.session, None
            await session.aclose()

    def _build_search_params(self, filters: CollectionSearchFilter) -> Dict[str, Any]:
        """
        Build query parameters for search requests.

        Args:
            filters: Search filter parameters

        Returns:
            Dictionary with ``q``, ``start`` and ``rows`` (clamped to 0..1000)
        """
        return {
            "q": build_search_query(filters),
            "start": max(0, int(filters.offset or 0)),
            "rows": max(0, min(int(filters.limit or 0), MAX_ROWS)),
        }

    async def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make a GET request to the API.

        Args:
            endpoint: API endpoint path
            params: Query parameters (an ``api_key`` entry is ignored)

        Returns:
            JSON response data

        Raises:
            APIError: If the request fails
        """
        if not self.session:
            await self.connect()

        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        # The key travels in the X-Api-Key header only, never in the URL.
        request_params = {
            k: v for k, v in mask_api_key(dict(params or {})).items() if k != "api_key"
        }

        try:
            logger.debug("GET %s params=%s", url, request_params)

            if self.session is None:
                raise APIError(
                    error="session_error",
                    message="Failed to initialize HTTP session",
                    details=None,
                    status_code=None,
                )

            response = await self.session.get(url, params=request_params)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise APIError(
                    error="invalid_response",
                    message=f"Unexpected response type from {url}",
                    status_code=response.status_code,
                    details={"url": url},
                )
            return data

        except APIError:
            raise
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code == 404:
                logger.debug("Resource not found: %s", url)
                raise APIError(
                    error="not_found",
                    message="Resource not found",
                    status_code=status_code,
                    details={"url": url},
                ) from e
            if status_code == 429:
                error_msg = f"Rate limit temporarily exceeded for {url}"
                logger.error(error_msg)
                raise APIError(
                    error="rate_limit_exceeded",
                    message=error_msg,
                    status_code=status_code,
                    details={"url": url},
                ) from e
            error_msg = f"HTTP {status_code} error for {url}"
            logger.error(error_msg)
            raise APIError(
                error="http_error",
                message=error_msg,
                status_code=status_code,
                details={"url": url},
            ) from e
        except (json.JSONDecodeError, ValueError) as e:
            error_msg = f"Invalid JSON from {url}"
            logger.error(error_msg)
            raise APIError(
                error="invalid_response",
                message=error_msg,
                status_code=None,
                details={"url": url},
            ) from e
        except Exception as e:  # pylint: disable=broad-exception-caught
            error_msg = f"Request failed: {type(e).__name__}: {e}"
            logger.error(error_msg)
            raise APIError(
                error="request_error",
                message=error_msg,
                status_code=None,
                details={"exception_type": type(e).__name__},
            ) from e

    @staticmethod
    def _parse_on_view_status(indexed_structured: Dict[str, Any]) -> bool:
        """
        Parse the onPhysicalExhibit field, a list of strings (["Yes"]) or dicts.
        """
        for item in _as_list(indexed_structured.get("onPhysicalExhibit")):
            value = item.get("content") if isinstance(item, dict) else item
            if isinstance(value, str) and value.strip().lower() == "yes":
                return True
        return False

    @staticmethod
    def _first_exhibition(indexed_structured: Dict[str, Any]) -> Dict[str, Any]:
        """Return the first exhibition entry as a dict."""
        for item in _as_list(indexed_structured.get("exhibition")):
            if isinstance(item, dict):
                return item
        return {}

    def _parse_exhibition_title(
        self, indexed_structured: Dict[str, Any]
    ) -> Optional[str]:
        """
        Parse exhibition title from the exhibition field.
        """
        title = self._first_exhibition(indexed_structured).get("exhibitionTitle")
        return clean_text(title) if isinstance(title, str) and title.strip() else None

    def _parse_exhibition_location(
        self, indexed_structured: Dict[str, Any]
    ) -> Optional[str]:
        """
        Parse exhibition location (building and, when present, room).
        """
        exhibition = self._first_exhibition(indexed_structured)
        parts = [
            exhibition.get(key)
            for key in ("building", "room")
            if isinstance(exhibition.get(key), str) and exhibition.get(key).strip()
        ]
        return ", ".join(parts) if parts else None

    @staticmethod
    def _parse_images(
        descriptive_non_repeating: Dict[str, Any], obj_id: str
    ) -> List[ImageData]:
        """
        Parse image media from descriptiveNonRepeating.online_media.

        Args:
            descriptive_non_repeating: The descriptiveNonRepeating block.
            obj_id: Object ID for log messages.

        Returns:
            List[ImageData]: Parsed images; malformed media entries are skipped.
        """
        online_media = descriptive_non_repeating.get("online_media")
        if not online_media:
            logger.debug("No online_media found for object %s", obj_id)
            return []

        media_items: List[Any] = []
        if isinstance(online_media, list):
            media_items = online_media
        elif isinstance(online_media, dict):
            if isinstance(online_media.get("media"), list):
                media_items = online_media["media"]
            elif online_media.get("type"):
                media_items = [online_media]

        images: List[ImageData] = []
        for media_item in media_items:
            if not isinstance(media_item, dict) or media_item.get("type") != "Images":
                continue

            media_url = None
            width = _safe_int(media_item.get("width"))
            height = _safe_int(media_item.get("height"))
            # Prefer high-resolution versions listed in resources
            for resource in _as_list(media_item.get("resources")):
                if not isinstance(resource, dict):
                    continue
                label = str(resource.get("label") or "").lower()
                if "high-resolution tiff" in label or "high-resolution jpeg" in label:
                    media_url = _safe_url(resource.get("url"))
                    if media_url is not None:
                        dimensions = resource.get("dimensions")
                        if isinstance(dimensions, str) and "x" in dimensions:
                            w_text, _, h_text = dimensions.partition("x")
                            width = _safe_int(w_text) or width
                            height = _safe_int(h_text) or height
                        break

            if media_url is None:
                for field_name in ("content", "url", "href", "src"):
                    media_url = _safe_url(media_item.get(field_name))
                    if media_url is not None:
                        break

            usage = media_item.get("usage")
            if isinstance(usage, dict):
                is_cc0 = usage.get("access") == "CC0"
            else:
                is_cc0 = usage == "CC0"

            caption = media_item.get("caption")
            caption = caption if isinstance(caption, str) else None
            alt_text = media_item.get("altTextAccessibility")
            alt_text = alt_text if isinstance(alt_text, str) and alt_text else caption
            image_format = media_item.get("format")

            try:
                images.append(
                    ImageData(
                        url=media_url,
                        thumbnail_url=_safe_url(media_item.get("thumbnail")),
                        iiif_url=_safe_url(media_item.get("iiif")),
                        alt_text=alt_text or "",
                        width=width,
                        height=height,
                        format=image_format if isinstance(image_format, str) else None,
                        size_bytes=_safe_int(media_item.get("size")),
                        caption=caption or "",
                        is_cc0=is_cc0,
                    )
                )
            except ValidationError as exc:
                logger.debug("Skipping malformed image for object %s: %s", obj_id, exc)

        logger.debug("Parsed %d images for object %s", len(images), obj_id)
        return images

    @staticmethod
    def _parse_makers(
        freetext: Dict[str, Any], indexed_structured: Dict[str, Any]
    ) -> List[str]:
        """Collect maker names from freetext.maker / freetext.name entries."""
        makers: List[str] = []
        for item in _as_list(freetext.get("maker")) + _as_list(freetext.get("name")):
            if _label_of(item) in _NON_MAKER_LABELS:
                continue
            text = clean_text(_content_of(item))
            if text and text not in makers:
                makers.append(text)
        if not makers:
            makers = [
                clean_text(name) for name in _strings(indexed_structured.get("name"))
            ]
        return makers

    def _parse_object_data(self, raw_data: Dict[str, Any]) -> SmithsonianObject:
        """
        Parse raw API row data into a SmithsonianObject.

        Args:
            raw_data: A search row or /content response (dict or JSON string).

        Returns:
            SmithsonianObject: The parsed object.

        Raises:
            ValueError: If the data is not a dict or JSON object.
        """
        if isinstance(raw_data, str):
            try:
                raw_data = json.loads(raw_data)
            except json.JSONDecodeError as exc:
                raise ValueError("raw_data is not valid JSON or dict") from exc

        if not isinstance(raw_data, dict):
            raise ValueError("raw_data must be a dict or JSON string")

        content = _as_dict(raw_data.get("content"))
        descriptive = _as_dict(content.get("descriptiveNonRepeating"))
        freetext = _as_dict(content.get("freetext"))
        indexed = _as_dict(content.get("indexedStructured"))

        obj_id = str(raw_data.get("id") or "")
        title = clean_text(
            raw_data.get("title")
            if isinstance(raw_data.get("title"), str)
            else _content_of(descriptive.get("title"))
        )
        unit_code = raw_data.get("unitCode") or descriptive.get("unit_code") or None

        notes_list = _as_list(freetext.get("notes"))
        limited_notes = []
        for note in notes_list[:3]:
            text = clean_text(_content_of(note)) or ""
            if len(text) > 500:
                text = text[:497] + "..."
            if text:
                limited_notes.append(text)
        description = next(
            (
                clean_text(_content_of(note))
                for note in notes_list
                if _label_of(note) == "description" and _content_of(note)
            ),
            None,
        )

        physical = _as_list(freetext.get("physicalDescription"))
        dimensions = [
            _content_of(item) for item in physical if "dimension" in _label_of(item)
        ]
        materials = [
            text
            for item in physical
            if "dimension" not in _label_of(item) and (text := _content_of(item))
        ]
        legacy_date = _as_dict(descriptive.get("date"))
        legacy_physical = _as_list(descriptive.get("physicalDescription"))
        unit_name = (
            _first_text(indexed.get("unit_name"))
            or (
                descriptive.get("data_source")
                if isinstance(descriptive.get("data_source"), str)
                else None
            )
            or UNIT_INFO.get(str(unit_code), {}).get("name")
        )

        return SmithsonianObject(
            id=obj_id,
            record_id=(
                descriptive.get("record_ID")
                if isinstance(descriptive.get("record_ID"), str)
                else None
            ),
            guid=(
                descriptive.get("guid")
                if isinstance(descriptive.get("guid"), str)
                else None
            ),
            title=title or "",
            url=_safe_url(raw_data.get("url")),
            unit_code=unit_code if isinstance(unit_code, str) else None,
            unit_name=unit_name,
            description=description,
            images=self._parse_images(descriptive, obj_id),
            date=clean_text(_first_text(freetext.get("date")))
            or (
                legacy_date.get("content")
                if isinstance(legacy_date.get("content"), str)
                else None
            ),
            date_standardized=(
                legacy_date.get("date_standardized")
                if isinstance(legacy_date.get("date_standardized"), str)
                else _first_text(indexed.get("date"))
            ),
            dimensions=(
                "; ".join(d for d in dimensions if d)
                or _first_text(legacy_physical)
                or None
            ),
            summary=clean_text(_first_text(freetext.get("summary"))),
            notes="\n".join(limited_notes) or None,
            credit_line=_first_text(freetext.get("creditLine"))
            or (
                descriptive.get("creditLine")
                if isinstance(descriptive.get("creditLine"), str)
                else None
            ),
            rights=_first_text(freetext.get("objectRights"))
            or (
                descriptive.get("rights")
                if isinstance(descriptive.get("rights"), str)
                else None
            ),
            record_link=_safe_url(descriptive.get("record_link")),
            last_modified=_parse_timestamp(raw_data.get("lastTimeUpdated"))
            or _parse_timestamp(raw_data.get("modified")),
            maker=self._parse_makers(freetext, indexed),
            object_type=_first_text(
                freetext.get("objectType"), indexed.get("object_type")
            ),
            materials=materials,
            topics=_strings(indexed.get("topic")),
            culture=_strings(indexed.get("culture")),
            place=_strings(indexed.get("place")),
            is_cc0=_as_dict(descriptive.get("metadata_usage")).get("access") == "CC0",
            is_on_view=self._parse_on_view_status(indexed),
            exhibition_title=self._parse_exhibition_title(indexed),
            exhibition_location=self._parse_exhibition_location(indexed),
        )

    async def count_matches(self, query: str) -> int:
        """
        Count records matching a raw ``q`` query without fetching rows.

        Args:
            query: Query string in API syntax.

        Returns:
            int: Number of matching records.

        Raises:
            APIError: If the request fails.
        """
        data = await self._make_request("search", {"q": query, "start": 0, "rows": 0})
        return int(_as_dict(data.get("response")).get("rowCount") or 0)

    async def search_collections(self, filters: CollectionSearchFilter) -> SearchResult:
        """
        Search the Smithsonian collections.

        Rows that cannot be parsed are logged and skipped. ``next_offset`` is based
        on the rows the API returned, so skipped rows are not fetched again.

        Args:
            filters: Search parameters and filters

        Returns:
            Search results with objects and pagination info

        Raises:
            APIError: If the request fails.
        """
        params = self._build_search_params(filters)
        response_data = await self._make_request("search", params)
        response = _as_dict(response_data.get("response"))
        rows = _as_list(response.get("rows"))

        objects = []
        for row in rows:
            try:
                objects.append(self._parse_object_data(row))
            except Exception as exc:  # pylint: disable=broad-exception-caught
                row_id = row.get("id") if isinstance(row, dict) else None
                logger.warning(
                    "Skipping search row %s that failed to parse: %s", row_id, exc
                )

        total_count = _safe_int(response.get("rowCount")) or 0
        start = params["start"]
        next_start = start + len(rows)
        has_more = bool(rows) and next_start < total_count

        return SearchResult(
            objects=objects,
            total_count=total_count,
            returned_count=len(objects),
            offset=start,
            has_more=has_more,
            next_offset=next_start if has_more else None,
        )

    async def get_object_by_id(self, object_id: str) -> Optional[SmithsonianObject]:
        """
        Get detailed information about a specific object.

        The ID is tried as given first. Legacy ``edanmdm-`` IDs and bare record
        IDs (``nmah_1448973``) are then retried as EDAN URLs
        (``edanmdm:nmah_1448973``). The first successful lookup is returned.

        Args:
            object_id: Object identifier (search ID, EDAN URL or record ID)

        Returns:
            Object details or None if not found

        Raises:
            ValueError: If object_id is empty.
            APIError: For errors other than not-found.
        """
        if not object_id or not str(object_id).strip():
            raise ValueError("object_id cannot be empty")
        object_id = str(object_id).strip()

        candidates = _object_id_candidates(object_id)
        for attempt_id in candidates:
            endpoint = f"/content/{quote(attempt_id, safe=':-_.~')}"
            try:
                logger.debug("Trying object ID format: %s", attempt_id)
                response_data = await self._make_request(endpoint)
            except APIError as e:
                if e.error == "not_found" or e.status_code == 404:
                    logger.debug("Object not found with ID format %s", attempt_id)
                    continue
                logger.error("API error trying ID format %s: %s", attempt_id, e)
                raise

            record = response_data.get("response")
            if not isinstance(record, dict) or not record:
                logger.warning("Malformed response for object %s", attempt_id)
                continue
            try:
                result = self._parse_object_data(record)
            except (ValueError, ValidationError) as exc:
                raise APIError(
                    error="invalid_response",
                    message=f"Could not parse object {attempt_id}: {exc}",
                    status_code=None,
                    details={"object_id": attempt_id},
                ) from exc
            logger.debug("Retrieved object using ID format: %s", attempt_id)
            return result

        logger.info(
            "Object %s not found (tried %d ID formats)", object_id, len(candidates)
        )
        return None

    async def get_unit_codes(self, refresh: bool = False) -> List[str]:
        """
        Get the unit codes used by the search index.

        Codes come from ``GET /terms/unit_code`` and are cached for the life of the
        process. The built-in list is used if the endpoint fails.

        Args:
            refresh: Fetch again even if cached.

        Returns:
            List[str]: Unit codes such as ``NMAH`` and ``NMNHPALEO``.
        """
        cached = SmithsonianAPIClient._unit_codes_cache
        if cached is not None and not refresh:
            return list(cached)
        try:
            data = await self._make_request("terms/unit_code")
        except APIError as exc:
            logger.warning("Could not fetch unit codes, using built-in list: %s", exc)
            return list(KNOWN_UNIT_CODES)
        terms = [
            term.strip()
            for term in _as_list(_as_dict(data.get("response")).get("terms"))
            if isinstance(term, str) and term.strip()
        ]
        if not terms:
            return list(KNOWN_UNIT_CODES)
        SmithsonianAPIClient._unit_codes_cache = terms
        return list(terms)

    @classmethod
    def clear_unit_code_cache(cls) -> None:
        """Forget cached unit codes so the next call fetches them again."""
        cls._unit_codes_cache = None

    @staticmethod
    def _unit_from_code(code: str) -> SmithsonianUnit:
        """Build a SmithsonianUnit from the static unit information."""
        info = UNIT_INFO.get(code)
        if not info:
            return SmithsonianUnit(
                code=code,
                name=code,
                description="Smithsonian unit",
                website=None,
                location=None,
                archival_only=code in ARCHIVAL_UNIT_CODES,
            )
        description = info.get("description")
        if code in ARCHIVAL_UNIT_CODES:
            description = f"{description} (archival records only; not returned by object searches)"
        return SmithsonianUnit(
            code=code,
            name=info["name"],
            description=description,
            website=info.get("website"),
            location=info.get("location"),
            archival_only=code in ARCHIVAL_UNIT_CODES,
        )

    async def get_units(self) -> List[SmithsonianUnit]:
        """
        Get the Smithsonian units/museums available as search filters.

        Includes every code from ``/terms/unit_code`` plus ``NMNH``, which covers
        all National Museum of Natural History departments.

        Returns:
            List of Smithsonian units
        """
        codes = await self.get_unit_codes()
        units = [self._unit_from_code(code) for code in codes]
        if NMNH_AGGREGATE_CODE not in codes:
            position = next(
                (
                    i
                    for i, code in enumerate(codes)
                    if code.startswith(NMNH_AGGREGATE_CODE)
                ),
                len(units),
            )
            units.insert(position, self._unit_from_code(NMNH_AGGREGATE_CODE))
        return units

    async def get_collection_stats(self) -> CollectionStats:
        """
        Get overall collection statistics.

        Totals, per-unit counts and CC0 counts come from ``/stats``. The number of
        objects with images comes from one ``rows=0`` count query. Both requests
        run concurrently; no objects are sampled.

        Returns:
            CollectionStats: Collection statistics.

        Raises:
            APIError: If neither /stats nor the fallback count query succeeds.
        """
        stats_result, images_result = await asyncio.gather(
            self._make_request("stats"),
            self.count_matches(HAS_IMAGES_CLAUSE),
            return_exceptions=True,
        )
        for result in (stats_result, images_result):
            if isinstance(result, BaseException) and not isinstance(result, APIError):
                raise result

        total_with_images: Optional[int] = None
        if isinstance(images_result, APIError):
            logger.warning("Could not count objects with images: %s", images_result)
        else:
            total_with_images = images_result

        if isinstance(stats_result, APIError):
            logger.warning(
                "Stats endpoint failed, using count queries: %s", stats_result
            )
            return await self._fallback_collection_stats(
                total_with_images, stats_result
            )

        stats = _as_dict(stats_result.get("response"))
        metrics = _as_dict(stats.get("metrics"))
        unit_stats = []
        for unit in _as_list(stats.get("units")):
            if not isinstance(unit, dict) or not isinstance(unit.get("unit"), str):
                continue
            code = unit["unit"]
            unit_metrics = _as_dict(unit.get("metrics"))
            data_source = unit.get("data_source")
            unit_stats.append(
                UnitStats(
                    unit_code=code,
                    unit_name=UNIT_INFO.get(code, {}).get("name")
                    or (data_source if isinstance(data_source, str) else None)
                    or code,
                    total_objects=_safe_int(unit.get("total_objects")) or 0,
                    digitized_objects=None,
                    cc0_objects=_safe_int(unit_metrics.get("CC0_records")),
                    objects_with_images=None,
                    cc0_objects_with_cc0_media=_safe_int(
                        unit_metrics.get("CC0_records_with_CC0_media")
                    ),
                    object_types=None,
                )
            )

        return CollectionStats(
            total_objects=_safe_int(stats.get("total_objects")) or 0,
            total_digitized=total_with_images,
            total_cc0=_safe_int(metrics.get("CC0_records")),
            total_with_images=total_with_images,
            total_cc0_objects_with_cc0_media=_safe_int(
                metrics.get("CC0_records_with_CC0_media")
            ),
            object_type_breakdown=None,
            units=unit_stats,
            last_updated=_parse_stats_time(stats.get("time")) or datetime.now(),
            notes=(
                "Totals, per-unit totals and CC0 counts are from the API /stats "
                "endpoint and include archival records. total_with_images (also "
                "used for total_digitized) counts searchable object records with "
                "online images. The API does not provide per-unit image counts or "
                "object type breakdowns."
            ),
        )

    async def _fallback_collection_stats(
        self, total_with_images: Optional[int], cause: APIError
    ) -> CollectionStats:
        """
        Build minimal statistics from a count query when /stats is unavailable.

        Args:
            total_with_images: Count of objects with images, if known.
            cause: The error from /stats.

        Returns:
            CollectionStats: Totals without per-unit data.

        Raises:
            APIError: If the count query fails too.
        """
        try:
            total_objects = await self.count_matches("*")
        except APIError as fallback_error:
            logger.error("Fallback count query also failed: %s", fallback_error)
            raise APIError(
                error="stats_failed",
                message=f"Failed to retrieve collection statistics: {cause}",
                status_code=None,
            ) from fallback_error

        return CollectionStats(
            total_objects=total_objects,
            total_digitized=total_with_images,
            total_cc0=None,
            total_with_images=total_with_images,
            object_type_breakdown=None,
            units=[],
            last_updated=datetime.now(),
            notes=(
                "The /stats endpoint was unavailable; total_objects counts "
                "searchable object records. CC0 and per-unit figures are missing."
            ),
        )


# Utility function for creating client instance
async def create_client(api_key: Optional[str] = None) -> SmithsonianAPIClient:
    """
    Create and initialize an API client.

    Args:
        api_key: Optional API key. If not provided, it will be read from `Config.API_KEY`.

    Returns:
        Initialized API client
    """
    client = SmithsonianAPIClient(api_key)
    await client.connect()
    return client
