"""
Utility functions for the Smithsonian MCP server.
"""

from typing import Dict, Any, Optional, List

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


def prioritize_objects_by_unit_code(objects: List, unit_code: Optional[str]) -> List:
    """
    Reorder search results to prioritize objects whose IDs start with the unit code.

    This ensures that when searching with a specific unit_code (e.g., "NMAH"),
    objects from that museum appear first, even if the API ordered them differently.

    Args:
        objects: List of SmithsonianObject instances from search results
        unit_code: The unit code used in the search (e.g., "NMAH", "FSG")

    Returns:
        Reordered list with museum-specific objects first
    """
    if not unit_code or not objects:
        return objects

    # Convert unit_code to lowercase for case-insensitive matching
    unit_prefix = f"{unit_code.lower()}_"

    # Separate objects into prioritized and others
    prioritized = []
    others = []

    for obj in objects:
        if obj.id and obj.id.lower().startswith(unit_prefix):
            prioritized.append(obj)
        else:
            others.append(obj)

    # Return prioritized objects first, then others (maintaining their relative order)
    return prioritized + others


async def construct_url_from_record_id(record_id: Optional[str]) -> Optional[str]:
    """
    Construct a URL from a record_id using the museum's official website.

    This function extracts the museum code from the record_id (e.g., "nmah" from "nmah_1448973"),
    looks up the museum's website, and constructs the URL using the format:
    website + "/collections/object/" + record_id

    Args:
        record_id: The record identifier (e.g., "nmah_1448973")

    Returns:
        Constructed URL string, or None if museum not found or record_id malformed

    Examples:
        construct_url_from_record_id("nmah_1448973")
        # Returns: "https://americanhistory.si.edu/collections/object/nmah_1448973"
    """
    if not record_id or "_" not in record_id:
        return None

    # Extract museum code (part before first underscore)
    museum_code = record_id.split("_", 1)[0].upper()

    # Import here to avoid circular imports
    from .api_client import SmithsonianAPIClient

    client = SmithsonianAPIClient()
    try:
        await client.connect()
        units = await client.get_units()
        museum = next((u for u in units if u.code == museum_code), None)
        website = str(museum.website) if museum and museum.website else None
    finally:
        await client.disconnect()

    if website:
        # Remove trailing slash from website if present
        website = website.rstrip("/")
        return f"{website}/collections/object/{record_id}"

    return None
