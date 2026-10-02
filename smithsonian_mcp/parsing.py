"""
Parsing of Smithsonian Open Access records into SmithsonianObject models.

Search rows and /content records share one layout: ``content`` holds the
``descriptiveNonRepeating``, ``freetext`` and ``indexedStructured`` blocks.
Values are checked before use, so malformed or missing data leaves a field empty
instead of failing the record.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import HttpUrl, ValidationError

from .constants import UNIT_INFO
from .models import ImageData, SmithsonianObject
from .utils import clean_text

logger = logging.getLogger(__name__)

# freetext.name labels that name the creator of an object. The other labels in
# that block name subjects, sitters, owners, sellers, donors, collectors,
# cultures, places, vessels or taxa. Derived from label frequencies in random
# samples of 26 units.
_MAKER_LABELS = frozenset(
    {
        "artist",
        "artist/maker",
        "maker",
        "creator",
        "created by",
        "made by",
        "manufacturer",
        "manufactured by",
        "author",
        "written by",
        "writer",
        "photographer",
        "photograph by",
        "photographed by",
        "designer",
        "designed by",
        "engraver",
        "engraved by",
        "printer",
        "printed by",
        "print maker",
        "printmaker",
        "lithographer",
        "publisher",
        "published by",
        "sculptor",
        "architect",
        "illustrator",
        "illustrated by",
        "calligrapher",
        "embroiderer",
        "model maker",
        "attributed to",
        "attribution",
        "possibly",
        "studio",
        "mint",
        "founder",
        "assembler",
        "contractor",
        "inventor",
        "collaborator",
        "composer",
        "performer",
        "recording artist",
        "producer",
        "produced by",
        "editor",
        "edited by",
    }
)
# Label fragments of further creator roles ("Artist (attributed)", "Silversmith").
_MAKER_LABEL_FRAGMENTS = (
    "artist",
    "maker",
    "manufactur",
    "photograph",
    "designer",
    "engraver",
    "sculpt",
    "illustrat",
    "lithograph",
    "painter",
    "potter",
    "weaver",
    "smith",
    "carver",
)
# physicalDescription labels that hold materials, and prefixes of labels that
# hold dimensions.
_MATERIAL_LABELS = frozenset({"medium", "materials", "material", "media/materials"})
_DIMENSION_LABELS = ("dimension", "measurement")
_DECADE_RE = re.compile(r"^(\d{3,4})s$")
# Labels that mention a creator but describe someone else's role.
_NOT_MAKER_LABEL_PREFIXES = ("formerly", "copy after", "after", "possible owner")
# freetext.objectType labels that hold something other than a type: Paleobiology
# records put the literature citation of a type specimen there.
_NOT_OBJECT_TYPE_LABELS = frozenset({"type citation"})
# Labels of full-resolution image downloads, in order of preference.
_DOWNLOAD_KINDS = ("high-resolution jpeg", "high-resolution tiff")


def as_dict(value: Any) -> Dict[str, Any]:
    """Return value if it is a dict, else an empty dict."""
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> List[Any]:
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


def _is_maker_label(label: str) -> bool:
    """Whether a freetext.name label is a creator role."""
    # "manufactured for", "printed for" name the client, not the maker
    if (
        not label
        or label.startswith(_NOT_MAKER_LABEL_PREFIXES)
        or label.endswith(" for")
    ):
        return False
    return label in _MAKER_LABELS or any(
        fragment in label for fragment in _MAKER_LABEL_FRAGMENTS
    )


def _material_of(item: Any) -> Optional[str]:
    """
    Return the text of a physicalDescription entry that describes materials.

    Entries labelled Medium, Materials or Media/Materials qualify. "Physical
    description" entries qualify only when they name a material ("vinyl (overall
    material)" at NMAH); elsewhere that label holds extents such as "3 p.". Other
    labels (Dimensions, Object Name, Techniques, Contents, Preparation, ...) do
    not describe materials.
    """
    text = _content_of(item)
    if not text or not text.strip():
        return None
    label = _label_of(item)
    if label in _MATERIAL_LABELS:
        return text
    if label == "physical description" and "material" in text.lower():
        return text
    return None


def _earliest_decade(values: List[str]) -> Optional[str]:
    """
    Return the earliest decade term (e.g. "1490s" from ["1520s", "1490s"]).

    Values that are not decades are ignored unless nothing else is present, in
    which case the first value is returned.
    """
    decades = []
    for value in values:
        match = _DECADE_RE.match(value.strip())
        if match:
            decades.append((int(match.group(1)), value.strip()))
    if decades:
        return min(decades)[1]
    return values[0] if values else None


def _rights_statement(entries: Any) -> Optional[str]:
    """
    Join the rights statements of a record.

    Records can carry several, e.g. "© Bernard J. Kleina" and "Permission required
    for use". Entries labelled "Restrictions & Rights" are used when present;
    other labels (NPG "Copyright" holds internal notes) only when they are not.
    """
    items = as_list(entries)
    preferred = [item for item in items if _label_of(item) == "restrictions & rights"]
    statements: List[str] = []
    for item in preferred or items:
        text = clean_text(_content_of(item))
        if text and text not in statements:
            statements.append(text)
    return "; ".join(statements) or None


def _has_cc0_media(descriptive: Dict[str, Any]) -> bool:
    """Whether any online media item of the record is CC0."""
    online_media = descriptive.get("online_media")
    if isinstance(online_media, dict):
        media = online_media.get("media")
        items = media if isinstance(media, list) else [online_media]
    else:
        items = as_list(online_media)
    return any(
        isinstance(item, dict) and _usage_is_cc0(item.get("usage")) for item in items
    )


def _first_text(*candidates: Any) -> Optional[str]:
    """Return the first non-empty string content among candidate entry lists."""
    for candidate in candidates:
        for item in as_list(candidate):
            text = _content_of(item)
            if text and text.strip():
                return text
    return None


def _collection_title(contained_in: Any) -> Optional[str]:
    """Title of the archival collection that contains an archive record."""
    parents = [item for item in as_list(contained_in) if isinstance(item, dict)]
    for parent in parents:
        if parent.get("type") == "Collection":
            return clean_text(_first_string(parent.get("unittitle")))
    return clean_text(_first_string(*(p.get("unittitle") for p in parents[:1])))


def _first_string(*values: Any) -> Optional[str]:
    """Return the first non-empty string among the values."""
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
    return None


def _strings(value: Any) -> List[str]:
    """Return the non-empty strings (or entry contents) of a list."""
    result = []
    for item in as_list(value):
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


def safe_int(value: Any) -> Optional[int]:
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
    seconds = safe_int(value)
    if seconds is None or seconds <= 0:
        return None
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _parse_on_view_status(indexed: Dict[str, Any]) -> bool:
    """Parse the onPhysicalExhibit field, a list of strings (["Yes"]) or dicts."""
    for item in as_list(indexed.get("onPhysicalExhibit")):
        value = item.get("content") if isinstance(item, dict) else item
        if isinstance(value, str) and value.strip().lower() == "yes":
            return True
    return False


def _first_exhibition(indexed: Dict[str, Any]) -> Dict[str, Any]:
    """Return the first exhibition entry as a dict."""
    for item in as_list(indexed.get("exhibition")):
        if isinstance(item, dict):
            return item
    return {}


def _parse_exhibition_title(indexed: Dict[str, Any]) -> Optional[str]:
    """
    Parse the exhibition title from the exhibition field.

    A location that repeats the room before the title is dropped, as in NMAA's
    "West Building (Freer Gallery of Art), Gallery 06: Japanese Art from the
    Collection", since the location is reported separately.

    Args:
        indexed: The indexedStructured block of a record.

    Returns:
        Optional[str]: The title, e.g. "Japanese Art from the Collection".
    """
    exhibition = _first_exhibition(indexed)
    title = exhibition.get("exhibitionTitle")
    if not isinstance(title, str) or not title.strip():
        return None
    title = clean_text(title)
    room = exhibition.get("room")
    if isinstance(room, str) and room.strip():
        location, separator, name = title.partition(f"{room.strip()}: ")
        if separator and name and (not location or location.endswith(", ")):
            return name
    return title


def parse_exhibition_location(indexed: Dict[str, Any]) -> Optional[str]:
    """
    Parse the exhibition location: the building code and, when present, the room.

    Args:
        indexed: The indexedStructured block of a record.

    Returns:
        Optional[str]: Location such as "NMAH, East 1", or None.
    """
    exhibition = _first_exhibition(indexed)
    parts = [
        exhibition.get(key)
        for key in ("building", "room")
        if isinstance(exhibition.get(key), str) and exhibition.get(key).strip()
    ]
    return ", ".join(parts) if parts else None


def _media_items(online_media: Any) -> List[Any]:
    """Return the media entries of an online_media value (a list or a dict)."""
    if isinstance(online_media, list):
        return online_media
    if isinstance(online_media, dict):
        if isinstance(online_media.get("media"), list):
            return online_media["media"]
        if online_media.get("type"):
            return [online_media]
    return []


def _usage_is_cc0(usage: Any) -> bool:
    """Whether a media usage value ("CC0" or {"access": "CC0"}) is CC0."""
    access = usage.get("access") if isinstance(usage, dict) else usage
    return access == "CC0"


def _full_resolution(media_item: Dict[str, Any]) -> Tuple[Optional[HttpUrl], Any]:
    """
    Find the full-resolution download of an image, a JPEG where one is offered.

    TIFF files cannot be displayed in a browser, so they are used only when no
    JPEG is offered.

    Args:
        media_item: One online_media entry.

    Returns:
        Tuple: The download URL and the resource's ``dimensions`` value, or
        (None, None) when the image has no download.
    """
    downloads: Dict[str, Tuple[HttpUrl, Dict[str, Any]]] = {}
    for resource in as_list(media_item.get("resources")):
        if not isinstance(resource, dict):
            continue
        label = str(resource.get("label") or "").lower()
        resource_url = _safe_url(resource.get("url"))
        for kind in _DOWNLOAD_KINDS:
            if kind in label and resource_url is not None:
                downloads.setdefault(kind, (resource_url, resource))
    for kind in _DOWNLOAD_KINDS:
        if kind in downloads:
            download_url, resource = downloads[kind]
            return download_url, resource.get("dimensions")
    return None, None


def _parse_image(media_item: Dict[str, Any]) -> ImageData:
    """
    Parse one image entry of online_media.

    Args:
        media_item: An online_media entry of type "Images".

    Returns:
        ImageData: The image.

    Raises:
        ValidationError: If the entry does not form a valid image.
    """
    width = safe_int(media_item.get("width"))
    height = safe_int(media_item.get("height"))
    download_url, dimensions = _full_resolution(media_item)
    if isinstance(dimensions, str) and "x" in dimensions:
        w_text, _, h_text = dimensions.partition("x")
        width = safe_int(w_text) or width
        height = safe_int(h_text) or height

    # The delivery URL serves a displayable, screen-sized image
    media_url = None
    for field_name in ("content", "url", "href", "src"):
        media_url = _safe_url(media_item.get(field_name))
        if media_url is not None:
            break

    caption = media_item.get("caption")
    caption = caption if isinstance(caption, str) else None
    alt_text = media_item.get("altTextAccessibility")
    alt_text = alt_text if isinstance(alt_text, str) and alt_text else caption
    image_format = media_item.get("format")
    return ImageData(
        url=media_url or download_url,
        download_url=download_url,
        thumbnail_url=_safe_url(media_item.get("thumbnail")),
        iiif_url=_safe_url(media_item.get("iiif")),
        alt_text=alt_text or "",
        width=width,
        height=height,
        format=image_format if isinstance(image_format, str) else None,
        size_bytes=safe_int(media_item.get("size")),
        caption=caption or "",
        is_cc0=_usage_is_cc0(media_item.get("usage")),
    )


def parse_images(descriptive: Dict[str, Any], obj_id: str) -> List[ImageData]:
    """
    Parse image media from descriptiveNonRepeating.online_media.

    Args:
        descriptive: The descriptiveNonRepeating block.
        obj_id: Object ID for log messages.

    Returns:
        List[ImageData]: Parsed images; malformed media entries are skipped.
    """
    online_media = descriptive.get("online_media")
    if not online_media:
        logger.debug("No online_media found for object %s", obj_id)
        return []

    images: List[ImageData] = []
    for media_item in _media_items(online_media):
        if not isinstance(media_item, dict) or media_item.get("type") != "Images":
            continue
        try:
            images.append(_parse_image(media_item))
        except ValidationError as exc:
            logger.debug("Skipping malformed image for object %s: %s", obj_id, exc)

    logger.debug("Parsed %d images for object %s", len(images), obj_id)
    return images


def parse_makers(freetext: Dict[str, Any]) -> List[str]:
    """
    Collect creator names from the freetext block.

    Entries under ``freetext.name`` count only when their label is a creator
    role (artist, manufacturer, author, photograph by, ...); unlabeled entries
    have no known role and are skipped. Entries under ``freetext.maker`` count
    unless their label names another role. indexedStructured.name is not used:
    it mixes makers with dealers, collectors and subjects.

    Args:
        freetext: The freetext block of a record.

    Returns:
        List[str]: Distinct maker names in record order.
    """
    makers: List[str] = []
    candidates = [(item, True) for item in as_list(freetext.get("maker"))]
    candidates += [(item, False) for item in as_list(freetext.get("name"))]
    for item, from_maker_block in candidates:
        label = _label_of(item)
        if not (_is_maker_label(label) or (from_maker_block and not label)):
            continue
        text = clean_text(_content_of(item))
        if text and text not in makers:
            makers.append(text)
    return makers


def _string_value(block: Dict[str, Any], key: str) -> Optional[str]:
    """Return block[key] if it is a string, else None."""
    value = block.get(key)
    return value if isinstance(value, str) else None


def _notes(notes: List[Any]) -> Optional[str]:
    """Join the first three notes, each cut to 500 characters, with newlines."""
    limited = []
    for note in notes[:3]:
        text = clean_text(_content_of(note)) or ""
        if len(text) > 500:
            text = text[:497] + "..."
        if text:
            limited.append(text)
    return "\n".join(limited) or None


def _description(notes: List[Any]) -> Optional[str]:
    """Return the text of the first note labelled Description."""
    return next(
        (
            clean_text(_content_of(note))
            for note in notes
            if _label_of(note) == "description" and _content_of(note)
        ),
        None,
    )


def _dimensions(physical: List[Any], descriptive: Dict[str, Any]) -> Optional[str]:
    """Join the dimension entries of physicalDescription."""
    dimensions = [
        _content_of(item)
        for item in physical
        if _label_of(item).startswith(_DIMENSION_LABELS)
    ]
    return (
        "; ".join(d for d in dimensions if d)
        or _first_text(as_list(descriptive.get("physicalDescription")))
        or None
    )


def _unit_name(
    indexed: Dict[str, Any], descriptive: Dict[str, Any], unit_code: Any
) -> Optional[str]:
    """Name of the record's unit: indexed, then data_source, then static."""
    return (
        _first_text(indexed.get("unit_name"))
        or _string_value(descriptive, "data_source")
        or UNIT_INFO.get(str(unit_code), {}).get("name")
    )


def _object_type(indexed: Dict[str, Any], freetext: Dict[str, Any]) -> Optional[str]:
    """The indexed object type, which the object_type filter matches, else a label."""
    return _first_text(
        indexed.get("object_type"),
        [
            item
            for item in as_list(freetext.get("objectType"))
            if _label_of(item) not in _NOT_OBJECT_TYPE_LABELS
        ],
    )


def parse_object_data(raw_data: Any) -> SmithsonianObject:
    """
    Parse a search row or /content record into a SmithsonianObject.

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

    content = as_dict(raw_data.get("content"))
    descriptive = as_dict(content.get("descriptiveNonRepeating"))
    freetext = as_dict(content.get("freetext"))
    indexed = as_dict(content.get("indexedStructured"))

    obj_id = str(raw_data.get("id") or "")
    title = clean_text(
        raw_data.get("title")
        if isinstance(raw_data.get("title"), str)
        else _content_of(descriptive.get("title"))
    )
    unit_code = raw_data.get("unitCode") or descriptive.get("unit_code") or None
    notes = as_list(freetext.get("notes"))
    physical = as_list(freetext.get("physicalDescription"))
    legacy_date = as_dict(descriptive.get("date"))

    return SmithsonianObject(
        id=obj_id,
        # Archive records keep these at the top of content
        record_id=_first_string(descriptive.get("record_ID"), content.get("record_id")),
        guid=_first_string(descriptive.get("guid"), content.get("guid")),
        title=title or "",
        url=_safe_url(raw_data.get("url")),
        unit_code=unit_code if isinstance(unit_code, str) else None,
        unit_name=_unit_name(indexed, descriptive, unit_code),
        description=_description(notes),
        images=parse_images(descriptive, obj_id),
        date=clean_text(_first_text(freetext.get("date")))
        or _string_value(legacy_date, "content"),
        date_standardized=(
            legacy_date["date_standardized"]
            if isinstance(legacy_date.get("date_standardized"), str)
            else _earliest_decade(_strings(indexed.get("date")))
        ),
        dimensions=_dimensions(physical, descriptive),
        summary=clean_text(_first_text(freetext.get("summary"))),
        notes=_notes(notes),
        credit_line=_first_text(freetext.get("creditLine"))
        or _string_value(descriptive, "creditLine"),
        rights=_rights_statement(freetext.get("objectRights"))
        or _string_value(descriptive, "rights"),
        record_link=_safe_url(descriptive.get("record_link")),
        last_modified=_parse_timestamp(raw_data.get("lastTimeUpdated"))
        or _parse_timestamp(raw_data.get("modified")),
        maker=parse_makers(freetext),
        object_type=_object_type(indexed, freetext),
        materials=[
            text for item in physical if (text := _material_of(item)) is not None
        ],
        topics=_strings(indexed.get("topic")),
        culture=_strings(indexed.get("culture")),
        place=_strings(indexed.get("place")),
        is_cc0=_has_cc0_media(descriptive),
        metadata_is_cc0=as_dict(descriptive.get("metadata_usage")).get("access")
        == "CC0",
        is_on_view=_parse_on_view_status(indexed),
        exhibition_title=_parse_exhibition_title(indexed),
        exhibition_location=parse_exhibition_location(indexed),
        collection=_collection_title(content.get("containedIn")),
    )
