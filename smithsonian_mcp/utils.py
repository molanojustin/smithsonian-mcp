"""
Utility functions for the Smithsonian MCP server.
"""

import html
import re
from typing import Any, Dict, Optional

from pydantic import HttpUrl

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
    variations and partial matches. Every informative word of the input (not
    "museum", "smithsonian", "american" and the like) must appear in the
    matched name, so "African American Museum" is not taken for African Art.
    It supports:
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

    # Input contained in a map key: the whole name first ("african american"
    # in "african american history"), as long as it has an informative word
    informative = [w for w in cleaned.split() if w not in _NAME_STOP_WORDS]
    if informative:
        phrase = f" {cleaned} "
        containing = [key for key in museum_map if phrase in f" {key} "]
        if containing:
            return museum_map[min(containing, key=len)]

        # Every informative word in one map key, in any order
        wanted = set(informative)
        containing = [key for key in museum_map if wanted <= set(key.split())]
        if containing:
            return museum_map[min(containing, key=len)]

    return None


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


def record_page_url(
    record_id: Optional[str], unit_code: Optional[str] = None
) -> Optional[str]:
    """
    Build an object page URL from a record_id alone, without any request.

    Only museums whose URL pattern needs nothing but the record_id or accession
    number are handled (NMAH, NMAA, NMAAHC, NPG, NPM, SIA, several NMNH
    departments). Each was checked against live pages in October 2026. Museums
    whose pages need record data (record_link, guid, EDAN URL or IDS id) return
    None.

    Args:
        record_id: Record identifier such as ``nmah_1448973`` or ``fsg_F1900.47``.
        unit_code: Unit of the record, if known. SIRIS archive ids
            (``siris_arc_...``) are shared by several units, but only the
            Smithsonian Institution Archives (SIA) has pages for them.

    Returns:
        Optional[str]: The page URL, or None if it cannot be built from the id.
    """
    if not record_id or "_" not in record_id:
        return None
    record_id_prefix, accession = record_id.split("_", 1)

    # Smithsonian Institution Archives records use SIRIS ids ("siris_arc_403511")
    if record_id_prefix.lower() == "siris" and accession.lower().startswith("arc_"):
        if unit_code not in (None, "SIA"):
            return None
        museum_code = "SIA"
    else:
        museum_code = _normalize_museum_code(record_id_prefix)

    from .constants import (  # pylint: disable=import-outside-toplevel
        MUSEUM_URL_PATTERNS,
    )

    pattern = MUSEUM_URL_PATTERNS.get(museum_code)
    if not pattern or pattern["identifier"] not in ("record_ID", "accession"):
        return None
    base_url = pattern["base_url"]
    if "{" in base_url:
        return None
    try:
        path = pattern["path_template"].format(record_ID=record_id, accession=accession)
    except (KeyError, ValueError):
        return None
    return base_url.rstrip("/") + path
