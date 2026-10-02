"""
Search query building for the Smithsonian Open Access API.

The API has no separate filter parameter, so every filter becomes a fielded
clause inside the ``q`` parameter, ANDed with the free-text query. Free text is
parsed by a forgiving parser and written back with explicit operators, because
the API treats whitespace inside parentheses as OR.
"""

import re
import string
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

from .constants import NMNH_AGGREGATE_CODE
from .models import CollectionSearchFilter
from .utils import normalize_unit_code

_WHITESPACE_RE = re.compile(r"\s+")
_PLAIN_CODE_RE = re.compile(r"^[A-Za-z0-9]+$")
_WILDCARD_CODE_RE = re.compile(r"^[A-Za-z0-9_\-]+\*$")
_LUCENE_SPECIAL_RE = re.compile(r'([+\-&|!(){}\[\]^"~*?:\\/,\s])')

# Fielded clauses for boolean filters, verified against the live API.
HAS_IMAGES_CLAUSE = 'online_media_type:"Images"'
IS_CC0_CLAUSE = 'media_usage:"CC0"'
ON_VIEW_CLAUSE = 'onPhysicalExhibit:"Yes"'
# "AND NOT onPhysicalExhibit" undercounts on this API; a match-all group does not.
NOT_ON_VIEW_CLAUSE = '(* NOT onPhysicalExhibit:"Yes")'

_BOOLEAN_OPERATORS = {
    "AND": "AND",
    "&&": "AND",
    "OR": "OR",
    "||": "OR",
    "NOT": "NOT",
    "!": "NOT",
}
# Lowercase words used as operators when they stand between two terms.
_LOWERCASE_OPERATORS = {"or": "OR", "and": "AND"}
_GROUP_PREFIXES = frozenset({"+", "-", "!"})
_RANGE_RE = re.compile(r"^[\[{]\s*\S+\s+TO\s+\S+\s*[\]}]$")
_YEAR_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")
# Years accepted by date_start/date_end; decades are matched as "1950s" terms.
MIN_DATE_YEAR = 1000
MAX_DATE_YEAR = 2999
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


def escape_query_phrase(value: str) -> str:
    """
    Quote a value as a phrase for the search ``q`` parameter.

    Backslashes and double quotes are escaped so user input cannot end the phrase
    and inject query syntax.

    Args:
        value: Raw filter value.

    Returns:
        str: The value wrapped in double quotes.
    """
    text = _WHITESPACE_RE.sub(" ", str(value)).strip()
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def escape_query_term(value: str) -> str:
    """
    Escape a value for use as a single unquoted query term (e.g. before a wildcard).

    Args:
        value: Raw term.

    Returns:
        str: The term with query syntax characters and whitespace escaped.
    """
    text = _WHITESPACE_RE.sub(" ", str(value)).strip()
    return _LUCENE_SPECIAL_RE.sub(r"\\\1", text)


def unit_code_query_clause(code: Optional[str]) -> Optional[str]:
    """
    Build the fielded ``unit_code`` clause for a unit code or alias.

    ``NMNH`` expands to the wildcard ``unit_code:NMNH*`` because Natural History
    records are indexed under department codes such as ``NMNHPALEO``.

    Args:
        code: Unit code, legacy code or aggregate code.

    Returns:
        Optional[str]: Query clause such as ``unit_code:NMAH``, or None for empty input.
    """
    canonical = normalize_unit_code(code)
    if not canonical:
        return None
    if canonical == NMNH_AGGREGATE_CODE:
        return f"unit_code:{NMNH_AGGREGATE_CODE}*"
    if _PLAIN_CODE_RE.match(canonical):
        return f"unit_code:{canonical}"
    if _WILDCARD_CODE_RE.match(canonical):
        return f"unit_code:{escape_query_term(canonical[:-1])}*"
    return f"unit_code:{escape_query_phrase(canonical)}"


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
    return _lowercase_operators(tokens)


def _lowercase_operators(tokens: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """
    Treat lowercase "or" and "and" between two terms as operators.

    People type "muppet or henson" meaning OR; as a required word "or" matches
    almost nothing. A lowercase "not" stays a word, because "not" inside a
    title is far more common than a lowercase NOT meant as an operator.

    Args:
        tokens: Tokens from _tokenize_query.

    Returns:
        List[Tuple[str, str]]: The tokens with those words made operators.
    """
    result = list(tokens)
    for index, (kind, value) in enumerate(tokens):
        if kind != "ATOM" or value not in _LOWERCASE_OPERATORS:
            continue
        before = tokens[index - 1][0] if index > 0 else None
        after = tokens[index + 1][0] if index + 1 < len(tokens) else None
        if before in ("ATOM", "RPAREN") and after in ("ATOM", "LPAREN"):
            result[index] = ("OP", _LOWERCASE_OPERATORS[value])
    return result


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


# A recursive-descent parser: parse() is its only entry point.
class _QueryParser:  # pylint: disable=too-few-public-methods
    """
    Forgiving parser for free-text queries.

    Precedence is NOT, then AND (explicit or implied by whitespace), then OR.
    Unbalanced parentheses and dangling operators are dropped.
    """

    def __init__(self, tokens: List[Tuple[str, str]]) -> None:
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
    singular = _singular(value)
    return singular if singular is not None else _plural(value)


def _suffix(value: str, suffix: str) -> str:
    """Return the suffix in upper case when the value is upper case."""
    return suffix.upper() if value.isupper() else suffix


def _singular(value: str) -> Optional[str]:
    """Return the singular of a plural word, or None if it is not plural."""
    lower = value.lower()
    if lower.endswith("ies") and len(lower) > 4:
        return value[:-3] + _suffix(value, "y")
    if lower.endswith(("sses", "ches", "shes", "xes")):
        return value[:-2]
    if lower.endswith("s") and not lower.endswith("ss"):
        return value[:-1]
    return None


def _plural(value: str) -> str:
    """Return the plural of a singular word."""
    lower = value.lower()
    if lower.endswith(("ss", "ch", "sh", "x")):
        return value + _suffix(value, "es")
    if lower.endswith("y") and len(lower) > 1 and lower[-2] not in "aeiou":
        return value[:-1] + _suffix(value, "ies")
    return value + _suffix(value, "s")


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


def _parse_year(name: str, value: Optional[str]) -> Optional[int]:
    """
    Extract a four-digit year between 1000 and 2999 from a date string.

    Args:
        name: Filter name for the error message (``date_start`` or ``date_end``).
        value: Year or date such as "1943" or "1943-05-01"; None or blank for none.

    Returns:
        Optional[int]: The year, or None if no value was given.

    Raises:
        ValueError: If a value was given but has no supported year.
    """
    if value is None or not str(value).strip():
        return None
    match = _YEAR_RE.search(str(value))
    year = int(match.group(1)) if match else None
    if year is None or not MIN_DATE_YEAR <= year <= MAX_DATE_YEAR:
        raise ValueError(
            f"{name} {value!r} is not supported: use a four-digit year between "
            f"{MIN_DATE_YEAR} and {MAX_DATE_YEAR}, e.g. '1865' or '1865-04-14'"
        )
    return year


def date_clause(date_start: Optional[str], date_end: Optional[str]) -> Optional[str]:
    """
    Build a decade clause for date filtering.

    The ``date`` field holds normalized terms, mostly decades such as "1950s",
    alongside centuries, three-digit decades and free text. Range queries on it
    compare text, so the decades in the range are listed explicitly. An open
    start begins at the 1000s and an open end stops at the current decade.

    Args:
        date_start: Start year or date (e.g. "1943" or "1943-05-01").
        date_end: End year or date.

    Returns:
        Optional[str]: Clause such as ``date:("1940s" OR "1950s" OR "1960s")``,
        or None when neither bound is given.

    Raises:
        ValueError: If a bound is given but is not a year from 1000 to 2999.
    """
    start = _parse_year("date_start", date_start)
    end = _parse_year("date_end", date_end)
    if start is None and end is None:
        return None
    if start is not None and end is not None and start > end:
        start, end = end, start
    first = (start if start is not None else MIN_DATE_YEAR) // 10 * 10
    current_decade = datetime.now(timezone.utc).year // 10 * 10
    last = (end if end is not None else max(current_decade, first)) // 10 * 10
    decades = [f'"{decade}s"' for decade in range(first, last + 1, 10)]
    if len(decades) == 1:
        return f"date:{decades[0]}"
    return f"date:({' OR '.join(decades)})"


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
