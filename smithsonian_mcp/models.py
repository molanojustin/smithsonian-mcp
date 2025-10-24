"""
Pydantic data models for Smithsonian Open Access data structures.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


class ImageData(BaseModel):
    """Represents image data for a collection object."""

    url: Optional[HttpUrl] = Field(None, description="URL to the image file")
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


class CollectionSearchFilter(BaseModel):
    """Search filter parameters for collection queries."""

    query: Optional[str] = Field(None, description="General search query")
    unit_code: Optional[str] = Field(None, description="Filter by Smithsonian unit")
    object_type: Optional[str] = Field(
        None, description="Type of object (painting, sculpture, etc.)"
    )
    date_start: Optional[str] = Field(
        None, description="Start date for date range filtering"
    )
    date_end: Optional[str] = Field(
        None, description="End date for date range filtering"
    )
    maker: Optional[str] = Field(None, description="Creator/maker name")
    material: Optional[str] = Field(None, description="Material or medium")
    topic: Optional[str] = Field(None, description="Subject topic or theme")
    has_images: Optional[bool] = Field(None, description="Filter objects with images")
    is_cc0: Optional[bool] = Field(None, description="Filter CC0 licensed objects")
    on_view: Optional[bool] = Field(
        None, description="Filter objects currently on physical exhibit"
    )
    limit: int = Field(default=20, description="Maximum number of results")
    offset: int = Field(default=0, description="Result offset for pagination")


class SmithsonianObject(BaseModel):
    """Main data model for Smithsonian collection objects."""

    # Core identification
    id: str = Field(..., description="Unique object identifier")
    record_id: Optional[str] = Field(None, description="Official record identifier (e.g., nmah_1448973)")
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
    is_cc0: bool = Field(default=False, description="CC0 license status")

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

    # Administrative
    record_link: Optional[HttpUrl] = Field(None, description="Link to full record")
    last_modified: Optional[datetime] = Field(
        None, description="Last modification date"
    )

    # Raw metadata (removed to prevent context bloat - not used in codebase)
    raw_metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Original API response (not populated to reduce context size)"
    )


class SimpleSearchResult(BaseModel):
    """Simplified search results optimized for LLM parsing."""

    summary: str = Field(..., description="Human-readable summary of results")
    object_count: int = Field(..., description="Number of objects found")
    total_available: int = Field(..., description="Total matching objects in database")
    object_ids: List[str] = Field(..., description="List of object IDs for get_object_details")
    first_object_id: Optional[str] = Field(None, description="ID of first result (easiest to use)")
    has_more: bool = Field(..., description="Whether more results are available")
    next_offset: Optional[int] = Field(None, description="Offset for next page if has_more is true")

    @classmethod
    def from_search_result(cls, search_result: "SearchResult") -> "SimpleSearchResult":
        """Convert a SearchResult to a SimpleSearchResult."""
        summary_lines = []
        summary_lines.append(f"Found {search_result.returned_count} objects")

        if search_result.total_count > search_result.returned_count:
            summary_lines[0] += f" (out of {search_result.total_count} total matches)"

        summary_lines[0] += ":"

        for i, obj in enumerate(search_result.objects[:5], 1):  # Show first 5
            title = obj.title or "Untitled"
            maker = obj.maker[0] if obj.maker else "Unknown artist"
            summary_lines.append(f"{i}. '{title}' by {maker}")

        if search_result.returned_count > 5:
            summary_lines.append(f"... and {search_result.returned_count - 5} more objects")

        if search_result.has_more:
            summary_lines.append(f"More results available (use offset={search_result.next_offset})")

        return cls(
            summary="\n".join(summary_lines),
            object_count=search_result.returned_count,
            total_available=search_result.total_count,
            object_ids=search_result.object_ids,
            first_object_id=search_result.first_object_id,
            has_more=search_result.has_more,
            next_offset=search_result.next_offset
        )


class SearchResult(BaseModel):
    """Represents search results with pagination info."""

    objects: List[SmithsonianObject] = Field(..., description="Found objects")
    total_count: int = Field(..., description="Total number of results")
    returned_count: int = Field(..., description="Number of results returned")
    offset: int = Field(default=0, description="Result offset")
    has_more: bool = Field(..., description="Whether more results are available")
    next_offset: Optional[int] = Field(None, description="Offset for next page")

    @property
    def object_ids(self) -> List[str]:
        """List of object IDs for easy access. Use these with get_object_details."""
        return [obj.id for obj in self.objects]

    @property
    def first_object_id(self) -> Optional[str]:
        """The ID of the first object, or None if no results. Use with get_object_details."""
        return self.object_ids[0] if self.objects else None

    def to_simple_result(self) -> SimpleSearchResult:
        """Convert to a simplified, LLM-friendly format."""
        return SimpleSearchResult.from_search_result(self)


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
    object_types: Optional[List[str]] = Field(
        None, description="Available object types in this museum's Open Access collection"
    )



class CollectionStats(BaseModel):
    """Overall collection statistics."""

    total_objects: int = Field(..., description="Total objects across all units")
    total_digitized: Optional[int] = Field(None, description="Total digitized objects")
    total_cc0: Optional[int] = Field(None, description="Total CC0 licensed objects")
    total_with_images: Optional[int] = Field(None, description="Objects with images")

    object_type_breakdown: Optional[Dict[str, int]] = Field(
        None, description="Count of objects by type across all collections"
    )

    units: List[UnitStats] = Field(..., description="Per-unit statistics")
    last_updated: datetime = Field(..., description="Statistics last updated")


class MuseumCollectionTypes(BaseModel):
    """Information about what types of objects are available in museum collections."""

    museum_code: str = Field(..., description="Museum unit code")
    museum_name: str = Field(..., description="Full museum name")
    available_object_types: List[str] = Field(..., description="Object types available in Open Access")
    total_sampled: int = Field(..., description="Number of objects sampled")
    notes: Optional[str] = Field(None, description="Additional notes about collection scope")


class ObjectTypeAvailability(BaseModel):
    """Result of checking if a museum has objects of a specific type."""

    museum_code: str = Field(..., description="Museum unit code")
    museum_name: str = Field(..., description="Full museum name")
    object_type: str = Field(..., description="Object type being checked")
    available: bool = Field(..., description="Whether this object type is available")
    count: Optional[int] = Field(None, description="Number of objects of this type")
    sample_ids: Optional[List[str]] = Field(None, description="Sample object IDs")
    message: str = Field(..., description="Human-readable explanation")


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
