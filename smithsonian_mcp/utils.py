"""
Utility functions for the Smithsonian MCP server.
"""

from typing import Dict, Any, Optional

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


def resolve_museum_code(museum_name: str) -> Optional[str]:
    """
    Resolve a museum name or code to the correct Smithsonian unit code.

    This function provides flexible matching for museum names, handling common
    variations and partial matches. It supports:
    - Exact matches: "asian art" -> "FSG"
    - Partial matches: "Smithsonian Asian Art Museum" -> "FSG"
    - Direct codes: "SAAM" -> "SAAM"
    - Case-insensitive matching

    Args:
        museum_name: Museum name or code to resolve

    Returns:
        The corresponding museum code (e.g., "FSG", "SAAM"), or None if not found

    Examples:
        resolve_museum_code("Smithsonian Asian Art Museum")  # -> "FSG"
        resolve_museum_code("Asian Art")                      # -> "FSG"
        resolve_museum_code("SAAM")                          # -> "SAAM"
        resolve_museum_code("Natural History Museum")        # -> "NMNH"
    """
    if not museum_name or not museum_name.strip():
        return None

    # Import here to avoid circular imports
    from .constants import MUSEUM_MAP, VALID_MUSEUM_CODES

    # Normalize input
    normalized = museum_name.lower().strip()

    # Try exact match on original first
    if normalized in MUSEUM_MAP:
        return MUSEUM_MAP[normalized]

    # Remove common prefixes that don't help with matching
    cleaned = normalized
    prefixes_to_remove = ["smithsonian", "national museum of", "museum of"]
    for prefix in prefixes_to_remove:
        if cleaned.startswith(prefix + " "):
            cleaned = cleaned[len(prefix) + 1:].strip()

    # Try exact match on cleaned version
    if cleaned in MUSEUM_MAP:
        return MUSEUM_MAP[cleaned]

    # Try direct code match
    if normalized.upper() in VALID_MUSEUM_CODES:
        return normalized.upper()

    # Try partial matches - check if normalized contains any map key
    for map_key in MUSEUM_MAP:
        if map_key in normalized or normalized in map_key:
            return MUSEUM_MAP[map_key]

    # Try word-based matching for multi-word museum names
    normalized_words = set(normalized.split())
    for map_key, code in MUSEUM_MAP.items():
        map_words = set(map_key.split())
        # If there's significant overlap (more than 50% of words match)
        if len(normalized_words & map_words) / len(map_words) > 0.5:
            return code

    # No match found
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
        from pydantic import HttpUrl
        parsed = HttpUrl(url_str)
        if parsed.scheme in ('http', 'https'):
            return str(parsed)
    except (ValueError, TypeError):
        pass

    return None
