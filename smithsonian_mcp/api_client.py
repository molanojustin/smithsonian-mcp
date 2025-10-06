"""
HTTP client for interacting with the Smithsonian Open Access API via api.data.gov.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

import httpx

from .config import Config
from .models import (
    SmithsonianObject,
    SearchResult,
    CollectionSearchFilter,
    ImageData,
    Model3D,
    APIError,
    SmithsonianUnit,
    CollectionStats,
    UnitStats,
)

logger = logging.getLogger(__name__)


class SmithsonianAPIClient:
    """
    Client for interacting with the Smithsonian Open Access API.

    This client handles authentication, rate limiting, and data transformation
    for the Smithsonian collections available through api.data.gov.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the API client.

        Args:
            api_key: Optional API key. If not provided, uses Config.API_KEY
        """
        self.api_key = api_key or Config.API_KEY
        self.base_url = "https://api.si.edu/openaccess/api/v1.0/"
        self.session: Optional[httpx.AsyncClient] = None

        if not self.api_key:
            logger.warning("No API key configured. Rate limits will be lower.")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self):
        """Initialize the HTTP session."""
        if self.session is None:
            headers = {"X-Api-Key": self.api_key} if self.api_key else {}
            self.session = httpx.AsyncClient(
                headers=headers,
                timeout=30.0,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )

    async def disconnect(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.aclose()
            self.session = None

    def _build_search_params(self, filters: CollectionSearchFilter) -> Dict[str, Any]:
        """
        Build query parameters for search requests.

        Args:
            filters: Search filter parameters

        Returns:
            Dictionary of query parameters
        """
        params = {}
        filter_queries = []

        # Basic search query
        if filters.query:
            params["q"] = filters.query

        # Filters - these are added as 'fq' (filter query) parameters
        if filters.unit_code:
            filter_queries.append(f'unit_code:"{filters.unit_code}"')

        if filters.object_type:
            filter_queries.append(f'content_type:"{filters.object_type}"')

        if filters.maker:
            # Assuming maker is part of the indexData
            filter_queries.append(f'indexed_structured_data.name:"{filters.maker}"')

        if filters.topic:
            filter_queries.append(f'topic:"{filters.topic}"')

        # Boolean filters
        if filters.has_images:
            filter_queries.append("online_media_type:Images")

        if filters.has_3d:
            filter_queries.append("online_media_type:3D")

        if filters.is_cc0:
            filter_queries.append("usage_rights:CC0")

        if filters.on_view is not None:
            if filters.on_view:
                filter_queries.append('onPhysicalExhibit:"Yes"')
            else:
                filter_queries.append('onPhysicalExhibit:"No"')

        if filter_queries:
            params["fq"] = " AND ".join(filter_queries)

        # Pagination
        params["start"] = filters.offset
        params["rows"] = filters.limit

        return {k: v for k, v in params.items() if v is not None}

    async def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the API.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            APIError: If the request fails
        """
        if not self.session:
            await self.connect()

        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        try:
            logger.debug(f"Making request to {url} with params: {params}")

            # The Smithsonian API uses api_key in the query string, not headers
            request_params = params.copy() if params else {}
            if self.api_key:
                request_params["api_key"] = self.api_key

            # Double-check session is available
            if self.session is None:
                raise APIError(
                    error="session_error",
                    message="Failed to initialize HTTP session",
                    details=None,
                    status_code=None,
                )

            response = await self.session.get(url, params=request_params)
            response.raise_for_status()

            return response.json()

        except httpx.HTTPStatusError as e:
            # Handle HTTP status errors (like 404) gracefully
            status_code = e.response.status_code
            error_msg = f"HTTP {status_code} error for {url}: {str(e)}"

            if status_code == 404:
                logger.debug(f"Resource not found: {url}")
                raise APIError(
                    error="not_found",
                    message="Resource not found",
                    status_code=status_code,
                    details={"url": url},
                )
            else:
                logger.error(error_msg)
                raise APIError(
                    error="http_error",
                    message=error_msg,
                    status_code=status_code,
                    details={"url": url},
                )
        except Exception as e:
            error_msg = f"Request failed: {str(e)}"
            logger.error(error_msg)

            raise APIError(
                error="request_error",
                message=error_msg,
                status_code=None,
                details={"exception_type": type(e).__name__},
            )

    def _parse_on_view_status(self, indexed_structured: Dict[str, Any]) -> bool:
        """
        Parse the onPhysicalExhibit field which can be a list of strings or dicts.
        """
        on_exhibit = indexed_structured.get("onPhysicalExhibit", [])
        if not on_exhibit:
            return False
        
        first_item = on_exhibit[0]
        if isinstance(first_item, str):
            return first_item == "Yes"
        elif isinstance(first_item, dict):
            return first_item.get("content") == "Yes"
        return False

    def _parse_exhibition_title(self, indexed_structured: Dict[str, Any]) -> Optional[str]:
        """
        Parse exhibition title from the exhibition field.
        """
        exhibitions = indexed_structured.get("exhibition", [])
        if exhibitions and isinstance(exhibitions[0], dict):
            return exhibitions[0].get("exhibitionTitle")
        return None

    def _parse_exhibition_location(self, indexed_structured: Dict[str, Any]) -> Optional[str]:
        """
        Parse exhibition location from the exhibition field.
        """
        exhibitions = indexed_structured.get("exhibition", [])
        if exhibitions and isinstance(exhibitions[0], dict):
            building = exhibitions[0].get("building", "")
            room = exhibitions[0].get("room", "")
            if building and room:
                return f"{building}, {room}"
            elif building:
                return building
            elif room:
                return room
        return None

    def _parse_object_data(self, raw_data: Dict[str, Any]) -> SmithsonianObject:
        """
        Parse raw API response data into a SmithsonianObject.
        """
        # Handle case where raw_data might be a string (JSON string)
        if isinstance(raw_data, str):
            try:
                raw_data = json.loads(raw_data)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse raw_data as JSON: {raw_data}")
                raise ValueError("raw_data is not valid JSON or dict")

        if not isinstance(raw_data, dict):
            logger.error(f"raw_data is not a dict or JSON string: {type(raw_data)}")
            raise ValueError("raw_data must be a dict or JSON string")

        content = raw_data.get("content", {})
        descriptive_non_repeating = content.get("descriptiveNonRepeating", {})
        freetext = content.get("freetext", {})
        indexed_structured = content.get("indexedStructured", {})

        # Extract core fields
        obj_id = raw_data.get("id", "")
        title = raw_data.get("title", "")
        unit_code = raw_data.get("unitCode", "")

        # Parse images
        images = []
        online_media = descriptive_non_repeating.get("online_media", {})
        if "media" in online_media:
            for media_item in online_media["media"]:
                if media_item.get("type") == "Images":
                    images.append(
                        ImageData(
                            url=media_item.get("content"),
                            thumbnail_url=media_item.get("thumbnail"),
                            iiif_url=media_item.get("iiif"),
                            alt_text=media_item.get("caption", ""),
                            width=media_item.get("width"),
                            height=media_item.get("height"),
                            format=media_item.get("format"),
                            size_bytes=media_item.get("size"),
                            caption=media_item.get("caption", ""),
                            is_cc0=media_item.get("usage", {}).get("access") == "CC0",
                        )
                    )

        # Parse 3D models
        models_3d = []
        if "media" in online_media:
            for media_item in online_media["media"]:
                if media_item.get("type") == "3D":
                    models_3d.append(
                        Model3D(
                            url=media_item.get("content"),
                            format=media_item.get("format"),
                            preview_url=media_item.get("thumbnail"),
                            file_size=media_item.get("size"),
                            polygons=media_item.get("polygons"),
                        )
                    )

        return SmithsonianObject(
            id=obj_id,
            title=title,
            url=None,  # raw_data.get("url") is an internal ID, not a URL
            unit_code=unit_code,
            unit_name=(
                indexed_structured.get("unit_name", [{}])[0].get("content")
                if indexed_structured.get("unit_name")
                else None
            ),
            description=next(
                (
                    note.get("content")
                    for note in freetext.get("notes", [])
                    if note.get("label") == "Description"
                ),
                None,
            ),
            images=images,
            models_3d=models_3d,
            raw_metadata=raw_data,
            date=descriptive_non_repeating.get("date", {}).get("content"),
            date_standardized=descriptive_non_repeating.get("date", {}).get(
                "date_standardized"
            ),
            dimensions=(
                descriptive_non_repeating.get("physicalDescription", [{}])[0].get(
                    "content"
                )
                if descriptive_non_repeating.get("physicalDescription")
                else None
            ),
            summary=(
                freetext.get("summary", [{}])[0].get("content")
                if freetext.get("summary")
                else None
            ),
            notes=(
                "\n".join(note.get("content", "") for note in freetext.get("notes", []))
                if freetext.get("notes")
                else None
            ),
            credit_line=descriptive_non_repeating.get("creditLine", ""),
            rights=descriptive_non_repeating.get("rights", ""),
            record_link=descriptive_non_repeating.get("record_link"),
            last_modified=raw_data.get("modified"),
            maker=list(
                filter(
                    None,
                    [
                        maker.get("content")
                        for maker in freetext.get("maker", [])
                        if isinstance(maker, dict)
                    ],
                )
            ),
            object_type=next(
                (t.get("content") for t in freetext.get("objectType", [])), None
            ),
            materials=list(
                filter(
                    None,
                    [
                        m.get("content")
                        for m in freetext.get("physicalDescription", [])
                        if isinstance(m, dict)
                    ],
                )
            ),
            topics=indexed_structured.get("topic", []),
            is_cc0=descriptive_non_repeating.get("metadata_usage", {}).get("access")
            == "CC0",
            is_on_view=self._parse_on_view_status(indexed_structured),
            exhibition_title=self._parse_exhibition_title(indexed_structured),
            exhibition_location=self._parse_exhibition_location(indexed_structured),
        )

    async def search_collections(self, filters: CollectionSearchFilter) -> SearchResult:
        """
        Search the Smithsonian collections.

        Args:
            filters: Search parameters and filters

        Returns:
            Search results with objects and pagination info
        """
        params = self._build_search_params(filters)
        endpoint = "search"

        response_data = await self._make_request(endpoint, params)

        # Parse response
        objects = []
        rows = response_data.get("response", {}).get("rows", [])

        for row in rows:
            try:
                obj = self._parse_object_data(row)
                objects.append(obj)
            except Exception as e:
                logger.warning(
                    f"Failed to parse object data for row {row.get('id')}: {e}"
                )
                # Debug: print the problematic row structure
                logger.debug(f"Row data: {row}")
                continue

        total_count = response_data.get("response", {}).get("rowCount", 0)
        returned_count = len(objects)
        has_more = filters.offset + returned_count < total_count
        next_offset = filters.offset + returned_count if has_more else None

        return SearchResult(
            objects=objects,
            total_count=total_count,
            returned_count=returned_count,
            offset=filters.offset,
            has_more=has_more,
            next_offset=next_offset,
        )

    async def get_object_by_id(self, object_id: str) -> Optional[SmithsonianObject]:
        """
        Get detailed information about a specific object.

        Args:
            object_id: Unique object identifier

        Returns:
            Object details or None if not found
        """
        endpoint = f"/content/{object_id}"

        try:
            response_data = await self._make_request(endpoint)
            # The content endpoint response is nested under 'response'
            if "response" in response_data:
                return self._parse_object_data(response_data["response"])
            else:
                logger.warning(
                    f"Malformed response for object {object_id}: {response_data}"
                )
                return None
        except APIError as e:
            if e.error == "not_found" or e.status_code == 404:
                logger.info(f"Object {object_id} not found in Smithsonian collection")
                return None
            raise

    async def get_units(self) -> List[SmithsonianUnit]:
        """
        Get list of available Smithsonian units/museums.

        Returns:
            List of Smithsonian units
        """
        # The Smithsonian API doesn't have a dedicated endpoint for units.
        # Return a hardcoded list of known units based on documentation
        known_units = [
            SmithsonianUnit(
                code="NMNH",
                name="National Museum of Natural History",
                description="Natural history museum",
                website=None,
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="NPG",
                name="National Portrait Gallery",
                description="Portrait art museum",
                website=None,
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="SAAM",
                name="Smithsonian American Art Museum",
                description="American art museum",
                website=None,
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="HMSG",
                name="Hirshhorn Museum and Sculpture Garden",
                description="Modern and contemporary art",
                website=None,
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="FSG",
                name="Freer and Sackler Galleries",
                description="Asian art museum",
                website=None,
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="NMAfA",
                name="National Museum of African Art",
                description="African art museum",
                website=None,
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="NMAI",
                name="National Museum of the American Indian",
                description="Native American art and culture",
                website=None,
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="NASM",
                name="National Air and Space Museum",
                description="Air and space museum",
                website=None,
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="NMAH",
                name="National Museum of American History",
                description="American history museum",
                website=None,
                location="Washington, DC",
            ),
        ]

        return known_units

    async def get_collection_stats(self) -> CollectionStats:
        """
        Get overall collection statistics.

        Returns:
            Collection statistics
        """

        try:
            # Use the dedicated stats endpoint for accurate data
            response = await self._make_request("stats")
            stats_data = response.get("response", {})

            total_objects = stats_data.get("total_objects", 0)
            metrics = stats_data.get("metrics", {})

            total_cc0 = metrics.get("CC0_records", 0)
            total_with_cc0_media = metrics.get("CC0_records_with_CC0_media", 0)
            total_cc0_media = metrics.get("CC0_media", 0)

            logger.info(
                f"Stats from API - Total: {total_objects:,}, CC0: {total_cc0:,}, CC0 Media: {total_cc0_media:,}"
            )

            # Build unit statistics from the API response
            unit_stats = []
            units_data = stats_data.get("units", [])

            # Get unit names from the units endpoint to match codes with names
            units_info = await self.get_units()
            unit_name_map = {unit.code: unit.name for unit in units_info}

            for unit_data in units_data:
                unit_code = unit_data.get("unit", "")
                unit_name = (
                    unit_name_map.get(unit_code, unit_code)
                    or unit_code
                    or "Unknown Unit"
                )
                unit_total = unit_data.get("total_objects", 0)
                unit_metrics = unit_data.get("metrics", {})

                unit_stats.append(
                    UnitStats(
                        unit_code=unit_code,
                        unit_name=unit_name,
                        total_objects=unit_total,
                        digitized_objects=(
                            unit_total // 2 if unit_total else None
                        ),  # Estimate
                        cc0_objects=unit_metrics.get("CC0_records", 0),
                        objects_with_images=unit_metrics.get(
                            "CC0_records_with_CC0_media", 0
                        ),
                        objects_with_3d=None,  # Not available in stats
                    )
                )

            return CollectionStats(
                total_objects=total_objects,
                total_digitized=(
                    total_objects // 2 if total_objects else None
                ),  # Estimate
                total_cc0=total_cc0,
                total_with_images=total_with_cc0_media,  # CC0 media count
                total_with_3d=None,  # Not available
                units=unit_stats,
                last_updated=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Failed to get collection stats from API: {e}")
            # Fallback to basic search if stats endpoint fails
            try:
                filter_dict = {
                    "query": "*",
                    "limit": 0,
                    "unit_code": None,
                    "object_type": None,
                    "date_start": None,
                    "date_end": None,
                    "maker": None,
                    "material": None,
                    "topic": None,
                    "has_images": None,
                    "has_3d": None,
                    "is_cc0": None,
                    "offset": 0,
                }
                filters = CollectionSearchFilter(**filter_dict)
                search_result = await self.search_collections(filters)
                total_objects = search_result.total_count

                units = await self.get_units()
                num_units = len(units)
                unit_stats = [
                    UnitStats(
                        unit_code=unit.code,
                        unit_name=unit.name,
                        total_objects=total_objects // num_units,
                        digitized_objects=(
                            total_objects // num_units // 2 if total_objects else None
                        ),
                        cc0_objects=None,
                        objects_with_images=None,
                        objects_with_3d=None,
                    )
                    for unit in units
                ]

                return CollectionStats(
                    total_objects=total_objects,
                    total_digitized=total_objects // 2 if total_objects else None,
                    total_cc0=None,
                    total_with_images=None,
                    total_with_3d=None,
                    units=unit_stats,
                    last_updated=datetime.now(),
                )
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
                raise APIError(
                    error="stats_failed",
                    message=f"Failed to retrieve collection statistics: {e}",
                    status_code=None,
                )


# Utility function for creating client instance
async def create_client(api_key: Optional[str] = None) -> SmithsonianAPIClient:
    """
    Create and initialize an API client.

    Args:
        api_key: Optional API key

    Returns:
        Initialized API client
    """
    client = SmithsonianAPIClient(api_key)
    await client.connect()
    return client
