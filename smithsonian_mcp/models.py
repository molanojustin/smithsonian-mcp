"""
Pydantic data models for Smithsonian Open Access data structures.
"""

from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


def _is_empty(value: Any) -> bool:
    """Whether a tool output value carries no information (None or empty)."""
    return value is None or (isinstance(value, (list, dict, str)) and not value)


def _omit_if_empty(description: Optional[str] = None) -> Any:
    """
    Field for an optional tool output value that is left out when empty.

    Tool results are read by language models, so absent values are dropped rather
    than repeated as nulls on every object.

    Args:
        description: Optional field description for the output schema.

    Returns:
        Any: A pydantic Field defaulting to None.
    """
    return Field(None, description=description, exclude_if=_is_empty)


def _list_omit_if_empty(description: Optional[str] = None) -> Any:
    """
    Field for a list tool output value that is left out when empty.

    Args:
        description: Optional field description for the output schema.

    Returns:
        Any: A pydantic Field defaulting to an empty list.
    """
    return Field(default_factory=list, description=description, exclude_if=_is_empty)


class ImageData(BaseModel):
    """Represents image data for a collection object."""

    url: Optional[HttpUrl] = Field(
        None, description="URL of a displayable, screen-sized image"
    )
    download_url: Optional[HttpUrl] = Field(
        None, description="Full-resolution file, a JPEG where one is offered"
    )
    thumbnail_url: Optional[HttpUrl] = Field(
        None, description="URL to thumbnail version"
    )
    iiif_url: Optional[HttpUrl] = Field(
        None, description="IIIF manifest URL if available"
    )
    caption: Optional[str] = Field(None, description="Image caption or description")
    alt_text: Optional[str] = Field(
        None, description="Alternative text for accessibility"
    )
    width: Optional[int] = Field(None, description="Image width in pixels")
    height: Optional[int] = Field(None, description="Image height in pixels")
    format: Optional[str] = Field(None, description="Image format (JPEG, TIFF, etc.)")
    size_bytes: Optional[int] = Field(None, description="File size in bytes")
    is_cc0: bool = Field(default=False, description="Whether image is CC0 licensed")


class SmithsonianUnit(BaseModel):
    """Represents a Smithsonian institution unit/museum."""

    code: str = Field(..., description="Unit code (e.g., NMNH, NPG)")
    name: str = Field(..., description="Full unit name")
    description: Optional[str] = Field(None, description="Unit description")
    website: Optional[HttpUrl] = Field(None, description="Unit website URL")
    location: Optional[str] = Field(None, description="Physical location")
    archival_only: bool = Field(
        default=False,
        description=(
            "True if the unit only publishes archival records, which object "
            "searches do not return"
        ),
    )


class CollectionSearchFilter(BaseModel):
    """
    Search filter parameters for collection queries.

    Every filter becomes a fielded term inside the search ``q`` parameter (the API
    has no separate filter parameter). Text filters match the API vocabularies,
    which are case-sensitive, so common case and singular/plural variants are tried.
    """

    query: Optional[str] = Field(
        None,
        description=(
            "General search query. Supports AND, OR, NOT, quoted phrases, "
            "parentheses and fielded terms; words without an operator must all match"
        ),
    )
    unit_code: Optional[str] = Field(
        None,
        description=(
            "Filter by Smithsonian unit code (e.g. NMAH). NMNH covers every Natural "
            "History department; the legacy code FSG maps to NMAA"
        ),
    )
    object_type: Optional[str] = Field(
        None,
        description="Type of object, matched against object_type (e.g. Paintings)",
    )
    date_start: Optional[str] = Field(
        None,
        description=(
            "Start year (1000-2999) for date filtering. The API indexes dates by "
            "decade, so matching is at decade granularity; other values are "
            "rejected with an error"
        ),
    )
    date_end: Optional[str] = Field(
        None,
        description=(
            "End year (1000-2999) for date filtering, matched at decade "
            "granularity; other values are rejected with an error"
        ),
    )
    maker: Optional[str] = Field(
        None,
        description=(
            "Creator/maker name, matched against the name field "
            '(indexed as "Last, First"; "First Last" is also tried)'
        ),
    )
    material: Optional[str] = Field(
        None,
        description="Material or medium, matched as a phrase in physicalDescription",
    )
    topic: Optional[str] = Field(None, description="Subject topic or theme")
    has_images: Optional[bool] = Field(
        None,
        description="True keeps only objects with images; False or None: no filter",
    )
    is_cc0: Optional[bool] = Field(
        None,
        description="True keeps only objects with CC0 media; False or None: no filter",
    )
    on_view: Optional[bool] = Field(
        None,
        description=(
            "True keeps objects on physical exhibit, False keeps objects not on "
            "exhibit, None applies no filter"
        ),
    )
    limit: int = Field(
        default=20, description="Maximum number of results (clamped to 0-1000)"
    )
    offset: int = Field(default=0, description="Result offset for pagination")
    sort: Optional[Literal["relevancy", "id", "newest", "updated", "random"]] = Field(
        None,
        description=(
            "Row order. None or relevancy is the API default; random returns a "
            "random selection of the matches"
        ),
    )
    row_group: Optional[Literal["objects", "archives"]] = Field(
        None,
        description=(
            "Records to search: objects (the API default) or archives, the "
            "archival collection and item records. The API searches one at a time"
        ),
    )


class SmithsonianObject(BaseModel):
    """Main data model for Smithsonian collection objects."""

    # Core identification
    id: str = Field(..., description="Unique object identifier")
    record_id: Optional[str] = Field(
        None, description="Official record identifier (e.g., nmah_1448973)"
    )
    guid: Optional[str] = Field(
        None, description="Persistent identifier URL (ark), when published"
    )
    title: str = Field(..., description="Object title")
    url: Optional[HttpUrl] = Field(None, description="URL to object page")

    # Classification
    unit_code: Optional[str] = Field(None, description="Owning Smithsonian unit code")
    unit_name: Optional[str] = Field(None, description="Owning Smithsonian unit name")
    object_type: Optional[str] = Field(None, description="Type classification")
    classification: Optional[List[str]] = Field(
        default_factory=list, description="Classification terms"
    )

    # Creation info
    date: Optional[str] = Field(None, description="Creation date or date range")
    date_standardized: Optional[str] = Field(
        None, description="Standardized date format"
    )
    maker: Optional[List[str]] = Field(
        default_factory=list, description="Creator(s) or maker(s)"
    )

    # Physical properties
    materials: Optional[List[str]] = Field(
        default_factory=list, description="Materials and techniques"
    )
    dimensions: Optional[str] = Field(None, description="Physical dimensions")

    # Content description
    description: Optional[str] = Field(None, description="Object description")
    summary: Optional[str] = Field(None, description="Brief summary")
    notes: Optional[str] = Field(None, description="Additional notes")

    # Subject information
    topics: Optional[List[str]] = Field(
        default_factory=list, description="Subject topics"
    )
    culture: Optional[List[str]] = Field(
        default_factory=list, description="Cultural associations"
    )
    place: Optional[List[str]] = Field(
        default_factory=list, description="Geographic associations"
    )

    # Digital assets
    images: Optional[List[ImageData]] = Field(
        default_factory=list, description="Associated images"
    )

    # Rights and access
    credit_line: Optional[str] = Field(None, description="Credit line")
    rights: Optional[str] = Field(None, description="Rights statement")
    is_cc0: bool = Field(
        default=False,
        description="Whether the object has CC0 (public domain) media to reuse",
    )
    metadata_is_cc0: bool = Field(
        default=False,
        description="Whether the record's descriptive text is CC0",
    )

    # Exhibition information
    is_on_view: bool = Field(
        default=False, description="Whether object is currently on physical exhibit"
    )
    exhibition_title: Optional[str] = Field(
        None, description="Current exhibition title"
    )
    exhibition_location: Optional[str] = Field(
        None, description="Exhibition location/room"
    )
    collection: Optional[str] = Field(
        None, description="Archival collection that holds an archive record"
    )

    # Administrative
    record_link: Optional[HttpUrl] = Field(None, description="Link to full record")
    last_modified: Optional[datetime] = Field(
        None, description="Last modification date"
    )

    # Raw metadata (removed to prevent context bloat - not used in codebase)
    raw_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Original API response (not populated to reduce context size)",
    )


class SearchResult(BaseModel):
    """Represents search results with pagination info."""

    objects: List[SmithsonianObject] = Field(..., description="Found objects")
    total_count: int = Field(..., description="Total number of results")
    returned_count: int = Field(..., description="Number of results returned")
    offset: int = Field(default=0, description="Result offset")
    has_more: bool = Field(..., description="Whether more results are available")
    next_offset: Optional[int] = Field(None, description="Offset for next page")


class UnitStats(BaseModel):
    """Statistics for a Smithsonian unit."""

    unit_code: str = Field(..., description="Unit identifier")
    unit_name: str = Field(..., description="Unit name")
    total_objects: int = Field(..., description="Total objects in collection")
    digitized_objects: Optional[int] = Field(
        None, description="Digitized objects count"
    )
    cc0_objects: Optional[int] = Field(None, description="CC0 licensed objects count")
    objects_with_images: Optional[int] = Field(
        None, description="Objects with images count"
    )
    cc0_objects_with_cc0_media: Optional[int] = Field(
        None, description="CC0 records that also have CC0 media (from /stats)"
    )
    object_types: Optional[List[str]] = Field(
        None,
        description="Available object types in this museum's Open Access collection",
    )


class CollectionStats(BaseModel):
    """Overall collection statistics."""

    total_objects: int = Field(..., description="Total objects across all units")
    total_digitized: Optional[int] = Field(None, description="Total digitized objects")
    total_cc0: Optional[int] = Field(None, description="Total CC0 licensed objects")
    total_with_images: Optional[int] = Field(None, description="Objects with images")
    total_cc0_objects_with_cc0_media: Optional[int] = Field(
        None, description="CC0 records that also have CC0 media"
    )

    object_type_breakdown: Optional[Dict[str, int]] = Field(
        None, description="Count of objects by type across all collections"
    )

    units: List[UnitStats] = Field(..., description="Per-unit statistics")
    last_updated: datetime = Field(..., description="Statistics last updated")
    notes: Optional[str] = Field(
        None, description="How the figures were obtained and their limitations"
    )


# ---------------------------------------------------------------------------
# Tool outputs
#
# Compact shapes returned by the MCP tools and resources. Empty optional values
# are omitted, raw API blocks are never included and long text is trimmed.
# ---------------------------------------------------------------------------


class MuseumRef(BaseModel):
    """A Smithsonian unit identified by code and name."""

    code: str
    name: str


class ObjectSummary(BaseModel):
    """One collection object in a result list."""

    id: str = Field(..., description="Pass to get_object for the full record")
    title: str
    maker: List[str] = _list_omit_if_empty()
    date: Optional[str] = _omit_if_empty()
    museum_code: Optional[str] = _omit_if_empty()
    museum_name: Optional[str] = _omit_if_empty()
    object_type: Optional[str] = _omit_if_empty()
    on_view: bool = Field(False, description="On physical exhibit now")
    exhibition_title: Optional[str] = _omit_if_empty()
    exhibition_location: Optional[str] = _omit_if_empty()
    collection: Optional[str] = _omit_if_empty(
        "Archival collection of an archive record"
    )
    thumbnail_url: Optional[str] = _omit_if_empty()
    web_url: Optional[str] = _omit_if_empty("Object page; use as given")


class ObjectSearchResults(BaseModel):
    """A page of search results."""

    total_count: int = Field(..., description="All matches, not just this page")
    returned: int
    offset: int = 0
    next_offset: Optional[int] = Field(
        None, description="Offset of the next page; null when there are no more"
    )
    museum: Optional[MuseumRef] = _omit_if_empty("Museum filter that was applied")
    objects: List[ObjectSummary] = Field(default_factory=list)
    note: Optional[str] = _omit_if_empty()


class TopicFacets(BaseModel):
    """Counts over the sampled pool of a topic exploration."""

    museums: Dict[str, int] = Field(default_factory=dict, description="By unit code")
    object_types: Dict[str, int] = Field(default_factory=dict)


class TopicExploration(ObjectSearchResults):
    """A varied random sample of objects about a topic."""

    facets: TopicFacets = Field(default_factory=TopicFacets)


class ImageSummary(BaseModel):
    """One image of an object."""

    url: Optional[str] = _omit_if_empty("Displayable image")
    download_url: Optional[str] = _omit_if_empty("Full-resolution file")
    thumbnail_url: Optional[str] = _omit_if_empty()
    iiif_url: Optional[str] = _omit_if_empty()
    caption: Optional[str] = _omit_if_empty()
    is_cc0: bool = False


class ObjectDetails(ObjectSummary):
    """The full record of one object."""

    record_id: Optional[str] = _omit_if_empty()
    description: Optional[str] = _omit_if_empty()
    summary: Optional[str] = _omit_if_empty()
    notes: Optional[str] = _omit_if_empty()
    dimensions: Optional[str] = _omit_if_empty()
    materials: List[str] = _list_omit_if_empty()
    topics: List[str] = _list_omit_if_empty()
    place: List[str] = _list_omit_if_empty()
    credit_line: Optional[str] = _omit_if_empty()
    rights: Optional[str] = _omit_if_empty()
    is_cc0: bool = Field(False, description="Has CC0 (public domain) media")
    images: List[ImageSummary] = _list_omit_if_empty()
    image_count: Optional[int] = _omit_if_empty(
        "Total images, given when more exist than are listed"
    )


class MuseumInfo(BaseModel):
    """A Smithsonian unit that contributes to Open Access."""

    code: str
    name: str
    record_types: List[str] = Field(
        default_factory=list,
        description="search_objects record_type values that return its records",
    )
    aliases: List[str] = _list_omit_if_empty("Names the museum argument accepts")


class CollectionOverview(BaseModel):
    """Searchable record counts for the whole collection or one museum."""

    museum: Optional[MuseumRef] = _omit_if_empty()
    objects: int = Field(..., description="search_objects total_count with no filters")
    archive_records: int = Field(..., description="Same, with record_type='archives'")
    objects_with_images: int = Field(..., description="Same, with has_images=true")
    objects_with_cc0_media: int = Field(..., description="Same, with cc0_only=true")


class APIError(Exception):
    """API error response structure."""

    def __init__(
        self,
        error: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None,
    ):
        self.error = error
        self.message = message
        self.details = details
        self.status_code = status_code
        super().__init__(f"{error}: {message}")

    def __str__(self):
        return f"{self.error}: {self.message}"
