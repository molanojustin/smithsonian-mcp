"""
Compact tool output built from parsed objects.

Search results list short summaries and get_object returns a bounded record:
long text is trimmed at a word boundary, lists and images are capped, building
codes become names, and every object gets the best web page link available.
"""

from typing import Any, Dict, Optional

from .constants import EXHIBITION_BUILDINGS, UNIT_INFO
from .models import ImageSummary, ObjectDetails, ObjectSummary, SmithsonianObject
from .query import maker_matches
from .utils import record_page_url, validate_url

MAX_IMAGES = 10
MAX_SUMMARY_MAKERS = 3
MAX_DETAIL_MAKERS = 10
MAX_LIST_ITEMS = 12
MAX_TITLE_CHARS = 200
MAX_DESCRIPTION_CHARS = 1500
MAX_SUMMARY_CHARS = 800
MAX_NOTES_CHARS = 1000
MAX_SHORT_TEXT_CHARS = 400


def unit_name(code: Optional[str], fallback: Optional[str] = None) -> Optional[str]:
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


def trim(text: Optional[str], limit: int) -> Optional[str]:
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


def location_name(location: Optional[str]) -> Optional[str]:
    """
    Readable exhibition location.

    Exhibition blocks name the building by a code ("NMAH", "HAZY", "NMAI NY"),
    optionally followed by a room. Known codes become the building's name and
    place, with the room in between.

    Args:
        location: Location as parsed by the client ("NMAH" or "Freer, Gallery 19").

    Returns:
        Optional[str]: The location, e.g. "Steven F. Udvar-Hazy Center, National
        Air and Space Museum, Chantilly, VA".
    """
    if not location:
        return None
    building, _, room = location.partition(", ")
    if building in EXHIBITION_BUILDINGS:
        name, place = EXHIBITION_BUILDINGS[building]
    elif building in UNIT_INFO:
        name, place = UNIT_INFO[building]["name"], UNIT_INFO[building]["location"]
    else:
        return location
    return ", ".join(part for part in (name, room, place) if part)


def web_url(obj: SmithsonianObject) -> Optional[str]:
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
    candidates = (
        obj.record_link,
        record_page_url(obj.record_id, obj.unit_code),
        obj.guid,
        obj.url,
    )
    for candidate in candidates:
        url = validate_url(str(candidate)) if candidate else None
        if url:
            return url
    return None


def thumbnail(obj: SmithsonianObject) -> Optional[str]:
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
        "title": trim(obj.title, MAX_TITLE_CHARS) or "Untitled",
        "maker": list(obj.maker or [])[:max_makers],
        "date": obj.date,
        "museum_code": obj.unit_code,
        "museum_name": unit_name(obj.unit_code, obj.unit_name),
        "object_type": obj.object_type,
        "on_view": obj.is_on_view,
        "exhibition_title": obj.exhibition_title,
        "exhibition_location": location_name(obj.exhibition_location),
        "collection": obj.collection,
        "thumbnail_url": thumbnail(obj),
        "web_url": web_url(obj),
    }


def summarize(obj: SmithsonianObject, maker: Optional[str] = None) -> ObjectSummary:
    """
    Compact summary of an object for result lists.

    Args:
        obj: Parsed object.
        maker: The search's maker filter, if any; the summary then says whether
            one of the object's creators matches it.

    Returns:
        ObjectSummary: The summary.
    """
    match = maker_matches(maker, obj.maker or []) if maker and maker.strip() else None
    return ObjectSummary(**_summary_fields(obj, MAX_SUMMARY_MAKERS), maker_match=match)


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


def details(obj: SmithsonianObject) -> ObjectDetails:
    """
    Full but bounded record of an object.

    Args:
        obj: Parsed object.

    Returns:
        ObjectDetails: The record with trimmed text and at most MAX_IMAGES images.
    """
    images = list(obj.images or [])
    description = trim(obj.description, MAX_DESCRIPTION_CHARS)
    return ObjectDetails(
        **_summary_fields(obj, MAX_DETAIL_MAKERS),
        record_id=obj.record_id,
        description=description,
        summary=trim(obj.summary, MAX_SUMMARY_CHARS),
        notes=trim(_notes_without(obj.notes, obj.description), MAX_NOTES_CHARS),
        dimensions=trim(obj.dimensions, MAX_SHORT_TEXT_CHARS),
        materials=list(obj.materials or [])[:MAX_LIST_ITEMS],
        topics=list(obj.topics or [])[:MAX_LIST_ITEMS],
        place=list(obj.place or [])[:MAX_LIST_ITEMS],
        credit_line=trim(obj.credit_line, MAX_SHORT_TEXT_CHARS),
        rights=trim(obj.rights, MAX_SHORT_TEXT_CHARS),
        is_cc0=obj.is_cc0,
        images=[
            ImageSummary(
                url=str(image.url) if image.url else None,
                download_url=str(image.download_url) if image.download_url else None,
                # Often the same delivery URL as url
                thumbnail_url=(
                    str(image.thumbnail_url)
                    if image.thumbnail_url and image.thumbnail_url != image.url
                    else None
                ),
                iiif_url=str(image.iiif_url) if image.iiif_url else None,
                caption=trim(image.caption, MAX_SHORT_TEXT_CHARS),
                is_cc0=image.is_cc0,
            )
            for image in images[:MAX_IMAGES]
        ],
        image_count=len(images) if len(images) > MAX_IMAGES else None,
    )
