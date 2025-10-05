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


class Model3D(BaseModel):
    """Represents 3D model data for collection objects."""

    url: Optional[HttpUrl] = Field(None, description="URL to the 3D model file")
    format: Optional[str] = Field(None, description="3D model format (gltf, obj, etc.)")
    preview_url: Optional[HttpUrl] = Field(
        None, description="URL to 3D model preview image"
    )
    file_size: Optional[int] = Field(None, description="Model file size in bytes")
    polygons: Optional[int] = Field(None, description="Number of polygons in the model")
    textures: Optional[List[str]] = Field(
        default_factory=list, description="Available texture maps"
    )


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
    has_3d: Optional[bool] = Field(None, description="Filter objects with 3D models")
    is_cc0: Optional[bool] = Field(None, description="Filter CC0 licensed objects")
    limit: int = Field(default=20, description="Maximum number of results")
    offset: int = Field(default=0, description="Result offset for pagination")


class SmithsonianObject(BaseModel):
    """Main data model for Smithsonian collection objects."""

    # Core identification
    id: str = Field(..., description="Unique object identifier")
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
    models_3d: Optional[List[Model3D]] = Field(
        default_factory=list, description="Associated 3D models"
    )

    # Rights and access
    credit_line: Optional[str] = Field(None, description="Credit line")
    rights: Optional[str] = Field(None, description="Rights statement")
    is_cc0: bool = Field(default=False, description="CC0 license status")

    # Administrative
    record_link: Optional[HttpUrl] = Field(None, description="Link to full record")
    last_modified: Optional[datetime] = Field(
        None, description="Last modification date"
    )

    # Raw metadata
    raw_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Original API response"
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
    digitized_objects: int = Field(..., description="Digitized objects count")
    cc0_objects: int = Field(..., description="CC0 licensed objects count")
    objects_with_images: int = Field(..., description="Objects with images count")
    objects_with_3d: int = Field(..., description="Objects with 3D models count")


class CollectionStats(BaseModel):
    """Overall collection statistics."""

    total_objects: int = Field(..., description="Total objects across all units")
    total_digitized: int = Field(..., description="Total digitized objects")
    total_cc0: int = Field(..., description="Total CC0 licensed objects")
    total_with_images: int = Field(..., description="Objects with images")
    total_with_3d: int = Field(..., description="Objects with 3D models")
    units: List[UnitStats] = Field(..., description="Per-unit statistics")
    last_updated: datetime = Field(..., description="Statistics last updated")


class APIError(Exception):
    """API error response structure."""

    def __init__(self, error: str, message: str, details: Optional[Dict[str, Any]] = None, status_code: Optional[int] = None):
        self.error = error
        self.message = message
        self.details = details
        self.status_code = status_code
        super().__init__(f"{error}: {message}")
    
    def __str__(self):
        return f"{self.error}: {self.message}"
