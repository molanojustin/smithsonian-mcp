"""
Utility functions for the Smithsonian MCP server.
"""

import html
import logging
import re
from typing import Any, Dict, List, Optional

from pydantic import HttpUrl

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"</?[A-Za-z][^<>]*>")
_WHITESPACE_RE = re.compile(r"\s+")
_PLAIN_CODE_RE = re.compile(r"^[A-Za-z0-9]+$")
_WILDCARD_CODE_RE = re.compile(r"^[A-Za-z0-9_\-]+\*$")
_LUCENE_SPECIAL_RE = re.compile(r'([+\-&|!(){}\[\]^"~*?:\\/,\s])')

# Words that carry no information when matching museum names.
_NAME_STOP_WORDS = frozenset(
    {
        "the",
        "smithsonian",
        "museum",
        "museums",
        "national",
        "of",
        "and",
        "gallery",
        "galleries",
        "art",
        "arts",
        "history",
        "american",
        "center",
        "institution",
        "collection",
        "collections",
    }
)
_NAME_PREFIXES = (
    "the ",
    "smithsonian ",
    "national museum of the ",
    "national museum of ",
    "museum of the ",
    "museum of ",
)
_NAME_SUFFIXES = (" museum", " gallery", " galleries")


def mask_api_key(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Masks the API key in a dictionary of parameters.

    Args:
        params: A dictionary of parameters.

    Returns:
        A new dictionary with the API key masked.
    """
    if "api_key" in params:
        masked_params = params.copy()
        masked_params["api_key"] = "****"
        return masked_params
    return params


def clean_text(value: Optional[str]) -> Optional[str]:
    """
    Strip HTML tags, unescape entities and collapse whitespace for display.

    Titles from the API can contain markup such as ``<i>The Muppets</i> Lunch Box``.

    Args:
        value: Raw text from the API.

    Returns:
        Optional[str]: Cleaned text, or the input unchanged if it is not a string.
    """
    if not isinstance(value, str):
        return value
    text = html.unescape(_TAG_RE.sub("", value))
    return _WHITESPACE_RE.sub(" ", text).strip()


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


def normalize_unit_code(code: Optional[str]) -> Optional[str]:
    """
    Normalize a unit code to the spelling used by the search index.

    Legacy codes are mapped (``FSG`` to ``NMAA``) and known codes are matched
    case-insensitively (``nmafa`` to ``NMAfA``). Unknown codes are returned stripped.

    Args:
        code: Unit code as supplied by a caller.

    Returns:
        Optional[str]: Canonical unit code, or None for empty input.
    """
    if not code or not code.strip():
        return None

    # Import here to avoid circular imports
    from .constants import (  # pylint: disable=import-outside-toplevel
        UNIT_CODE_ALIASES,
        VALID_MUSEUM_CODES,
    )

    raw = code.strip()
    upper = raw.upper()
    if upper in UNIT_CODE_ALIASES:
        return UNIT_CODE_ALIASES[upper]
    for known in VALID_MUSEUM_CODES:
        if known.upper() == upper:
            return known
    return raw


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
    from .constants import (  # pylint: disable=import-outside-toplevel
        NMNH_AGGREGATE_CODE,
    )

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


def unit_code_matches(
    object_unit_code: Optional[str], filter_code: Optional[str]
) -> bool:
    """
    Check whether an object's unit code falls under a filter unit code.

    Args:
        object_unit_code: Unit code of a returned object (e.g. ``NMNHPALEO``).
        filter_code: Unit code used as a filter (e.g. ``NMNH`` or ``FSG``).

    Returns:
        bool: True if the object belongs to the filtered unit.
    """
    from .constants import (  # pylint: disable=import-outside-toplevel
        NMNH_AGGREGATE_CODE,
    )

    canonical = normalize_unit_code(filter_code)
    if not object_unit_code or not canonical:
        return False
    if canonical == NMNH_AGGREGATE_CODE:
        return object_unit_code.upper().startswith(NMNH_AGGREGATE_CODE)
    if canonical.endswith("*"):
        return object_unit_code.upper().startswith(canonical[:-1].upper())
    return object_unit_code.upper() == canonical.upper()


def _normalize_museum_name(text: str) -> str:
    """Lowercase a museum name and reduce punctuation to single spaces."""
    text = text.lower().replace("&", " and ")
    text = re.sub(r"['’`]s\b", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _strip_name_affixes(text: str) -> str:
    """Remove prefixes such as 'smithsonian' and suffixes such as 'museum'."""
    changed = True
    while changed:
        changed = False
        for prefix in _NAME_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix) :].strip()
                changed = True
        for suffix in _NAME_SUFFIXES:
            if text.endswith(suffix) and len(text) > len(suffix):
                text = text[: -len(suffix)].strip()
                changed = True
    return text


def _normalized_museum_map() -> Dict[str, str]:
    """Return MUSEUM_MAP with keys normalized like user input."""
    from .constants import MUSEUM_MAP  # pylint: disable=import-outside-toplevel

    return {_normalize_museum_name(key): code for key, code in MUSEUM_MAP.items()}


def resolve_museum_code(museum_name: str) -> Optional[str]:
    """
    Resolve a museum name or code to the correct Smithsonian unit code.

    This function provides flexible matching for museum names, handling common
    variations and partial matches. It supports:
    - Exact matches: "asian art" -> "NMAA"
    - Partial matches: "Smithsonian Asian Art Museum" -> "NMAA"
    - Direct codes, case-insensitive: "SAAM" -> "SAAM", "nmafa" -> "NMAfA"
    - Legacy codes: "FSG" -> "NMAA"
    - Natural History: "natural history" and "NMNH" -> "NMNH", which searches
      expand to every NMNH department (unit_code:NMNH*)

    Args:
        museum_name: Museum name or code to resolve

    Returns:
        The corresponding museum code (e.g., "NMAA", "SAAM"), or None if not found

    Examples:
        resolve_museum_code("Smithsonian Asian Art Museum")  # -> "NMAA"
        resolve_museum_code("Asian Art")                      # -> "NMAA"
        resolve_museum_code("SAAM")                           # -> "SAAM"
        resolve_museum_code("Natural History Museum")         # -> "NMNH"
    """
    if not museum_name or not museum_name.strip():
        return None

    from .constants import (  # pylint: disable=import-outside-toplevel
        UNIT_CODE_ALIASES,
        VALID_MUSEUM_CODES,
    )

    raw = museum_name.strip()
    upper = raw.upper()
    if upper in UNIT_CODE_ALIASES or any(
        upper == c.upper() for c in VALID_MUSEUM_CODES
    ):
        return normalize_unit_code(raw)

    museum_map = _normalized_museum_map()
    normalized = _normalize_museum_name(raw)
    if not normalized:
        return None
    if normalized in museum_map:
        return museum_map[normalized]

    cleaned = _strip_name_affixes(normalized)
    if cleaned in museum_map:
        return museum_map[cleaned]

    # Longest map key contained in the input as whole words
    padded = f" {normalized} "
    contained = [key for key in museum_map if f" {key} " in padded]
    if contained:
        return museum_map[max(contained, key=len)]

    # Input contained in a map key, ignoring generic words such as "museum"
    informative = [w for w in cleaned.split() if w not in _NAME_STOP_WORDS]
    if informative:
        phrase = f" {' '.join(informative)} "
        containing = [key for key in museum_map if phrase in f" {key} "]
        if containing:
            return museum_map[min(containing, key=len)]

    # Word overlap on informative words
    input_words = set(informative)
    best_code: Optional[str] = None
    best_score = 0.0
    for key, code in museum_map.items():
        key_words = set(key.split()) - _NAME_STOP_WORDS
        if not key_words or not input_words:
            continue
        score = len(input_words & key_words) / len(key_words)
        if score > 0.5 and score > best_score:
            best_code, best_score = code, score

    return best_code


def validate_url(url_str: Optional[str]) -> Optional[str]:
    """
    Validate and normalize a URL string.

    This function checks if a URL string is a valid HTTP or HTTPS URL.
    It handles edge cases like malformed URLs and non-HTTP protocols.

    Args:
        url_str: The URL string to validate

    Returns:
        The validated URL string if valid, None otherwise

    Examples:
        validate_url("https://example.com")  # -> "https://example.com"
        validate_url("http://example.com")   # -> "http://example.com"
        validate_url("ftp://example.com")    # -> None
        validate_url("not-a-url")            # -> None
        validate_url(None)                   # -> None
    """
    if not url_str:
        return None

    try:
        parsed = HttpUrl(url_str)
        if parsed.scheme in ("http", "https"):
            return str(parsed)
    except (ValueError, TypeError):
        pass

    return None


def prioritize_objects_by_unit_code(objects: List, unit_code: Optional[str]) -> List:
    """
    Reorder search results so objects from the requested unit come first.

    An object matches when its ``unit_code`` falls under the filter code (``NMNH``
    covers every NMNH department, ``FSG`` means ``NMAA``) or, for objects without a
    unit code, when its ID starts with the lowercase code and an underscore.

    Args:
        objects: List of SmithsonianObject instances from search results
        unit_code: The unit code used in the search (e.g., "NMAH", "NMNH")

    Returns:
        Reordered list with museum-specific objects first, relative order kept
    """
    if not unit_code or not objects:
        return objects

    unit_prefix = f"{unit_code.lower()}_"

    prioritized = []
    others = []

    for obj in objects:
        object_code = getattr(obj, "unit_code", None)
        if object_code:
            matched = unit_code_matches(object_code, unit_code)
        else:
            matched = bool(obj.id and obj.id.lower().startswith(unit_prefix))
        if matched:
            prioritized.append(obj)
        else:
            others.append(obj)

    return prioritized + others


def _normalize_museum_code(record_id_prefix: str) -> str:
    """Normalize record_id prefix to museum code key used in MUSEUM_URL_PATTERNS."""
    prefix = record_id_prefix.lower()

    # Handle NMNH sub-museums with long prefixes
    if prefix.startswith("nmnh"):
        if "invertebratezoology" in prefix:
            return "NMNHINV"
        if "anthropology" in prefix:
            return "NMNHANTHRO"
        if "education" in prefix:
            return "NMNHEDUCATION"
        if "mineralsciences" in prefix:
            return "NMNHMINSCI"
        if "paleobiology" in prefix:
            return "NMNHPALEO"
        return prefix.upper()  # fallback

    return prefix.upper()


async def construct_url_from_record_id(record_id: Optional[str]) -> Optional[str]:
    """
    Construct a URL from a record_id using museum-specific URL patterns.

    This function uses predefined URL construction patterns for each Smithsonian museum
    to generate accurate object URLs. Different museums have different URL formats and
    identifier requirements. Museums whose URLs need record data are looked up through
    the shared API client.

    Args:
        record_id: The record identifier (e.g., "nmah_1448973", "fsg_F1900.47")

    Returns:
        Constructed URL string, or None if museum not found or record_id malformed

    Examples:
        construct_url_from_record_id("nmah_1448973")
        # Returns: "https://americanhistory.si.edu/collections/object/nmah_1448973"

        construct_url_from_record_id("fsg_F1900.47")
        # Returns: "https://asia.si.edu/object/F1900.47"

        construct_url_from_record_id("nmnhinvertebratezoology_14688577")
        # Returns: "https://naturalhistory.si.edu/object/nmnhinvertebratezoology_14688577"
    """
    if not record_id or "_" not in record_id:
        return None

    # Extract components from record_id
    parts = record_id.split("_", 1)
    if len(parts) != 2:
        return None

    record_id_prefix = parts[0]
    accession = parts[1]

    # Normalize to museum code. Smithsonian Institution Archives records use
    # SIRIS archive IDs such as "siris_arc_403511".
    if record_id_prefix.lower() == "siris" and accession.lower().startswith("arc_"):
        museum_code = "SIA"
    else:
        museum_code = _normalize_museum_code(record_id_prefix)

    from .constants import (  # pylint: disable=import-outside-toplevel
        MUSEUM_URL_PATTERNS,
    )

    pattern = MUSEUM_URL_PATTERNS.get(museum_code)
    if not pattern:
        # Unknown museum, fall back to API lookup
        return await _get_url_from_api_record_id(record_id)

    # Handle different identifier types
    identifier_type = pattern["identifier"]
    base_url = pattern["base_url"]
    path_template = pattern["path_template"]

    if identifier_type not in ("record_ID", "accession"):
        # record_link, guid, url and idsId all need record data from the API
        return await _get_url_from_api_record_id(record_id)

    # Handle template variables in base_url
    if "{record_link}" in base_url or "{guid}" in base_url:
        return await _get_url_from_api_record_id(record_id)

    # Construct the URL
    try:
        url = base_url.rstrip("/")
        if path_template:
            formatted_path = path_template.format(
                record_ID=record_id,
                accession=accession,
                url=record_id,  # fallback
                idsId=record_id,  # fallback
                guid=record_id,  # fallback
            )
            url += formatted_path
        return url
    except (KeyError, ValueError):
        # Template formatting failed, fall back to API
        return await _get_url_from_api_record_id(record_id)


async def _get_url_from_api_record_id(record_id: str) -> Optional[str]:
    """
    Look up an object's web URL through the shared API client.

    Used when pattern-based construction fails or when the URL needs record data
    (record_link or guid). The record is fetched directly by its EDAN URL
    (``edanmdm:<record_id>``), which is a single request.

    Args:
        record_id: Record identifier such as ``saam_1956.11.37``.

    Returns:
        Optional[str]: The record_link or guid URL, or None if unavailable.
    """
    # Imported here to avoid circular imports (api_client imports this module)
    from .context import get_api_client  # pylint: disable=import-outside-toplevel
    from .models import APIError  # pylint: disable=import-outside-toplevel

    try:
        client = await get_api_client()
        obj = await client.get_object_by_id(f"edanmdm:{record_id}")
    except (APIError, ValueError) as exc:
        logger.debug("URL lookup failed for record_id %s: %s", record_id, exc)
        return None

    if obj is None:
        return None
    for candidate in (obj.record_link, getattr(obj, "guid", None)):
        valid = validate_url(str(candidate)) if candidate else None
        if valid:
            return valid
    return None
