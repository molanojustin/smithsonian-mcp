"""
HTTP client for interacting with the Smithsonian Open Access API via api.data.gov.
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode

import httpx
from pydantic import HttpUrl

from .config import Config
from .models import (
    SmithsonianObject,
    SearchResult,
    CollectionSearchFilter,
    ImageData,
    APIError,
    SmithsonianUnit,
    CollectionStats,
    UnitStats,
)

from .utils import mask_api_key

logger = logging.getLogger(__name__)

BASE_URL = "https://api.si.edu/openaccess/api/v1.0/"


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
            api_key: API key. If not provided, it will be read from `Config.API_KEY`.
        """
        self.api_key = api_key or Config.API_KEY
        self.base_url = BASE_URL
        self.session: Optional[httpx.AsyncClient] = None

        if not self.api_key:
            raise ValueError("API key is required. Please provide one or set it in the config.")

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
            filter_queries.append(f'unitCode:{filters.unit_code}')

        if filters.object_type:
            filter_queries.append(f'content_type:"{filters.object_type}"')

        if filters.maker:
            # Makers are indexed under indexedStructured.name in the public API
            filter_queries.append(f'indexedStructured.name:"{filters.maker}"')

        if filters.topic:
            filter_queries.append(f'topic:"{filters.topic}"')

        # Boolean filters
        if filters.has_images:
            filter_queries.append("online_media_type:Images")

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

        # Prepare request parameters and logging URL
        request_params = params.copy() if params else {}
        if self.api_key:
            request_params["api_key"] = self.api_key
            log_params = mask_api_key(request_params)  # Remove API key from being logged
        else:
            log_params = request_params

        # Create masked URL for logging
        log_url = f"{url}?{urlencode(log_params)}" if log_params else url

        try:

            logger.debug(
                "Making request to %s", log_url
            )

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
            error_msg = f"HTTP {status_code} error for {log_url}"

            if status_code == 404:
                logger.debug("Resource not found: %s", url)
                raise APIError(
                    error="not_found",
                    message="Resource not found",
                    status_code=status_code,
                    details={"url": url},
                ) from e
            if status_code == 429:
                error_msg = f"Rate limit temporarilyexceeded for {url}"
                logger.error(error_msg)
                raise APIError(
                    error="rate_limit_exceeded",
                    message=error_msg,
                    status_code=status_code,
                    details={"url": url},
                ) from e
            logger.error(error_msg)
            raise APIError(
                error="http_error",
                message=error_msg,
                status_code=status_code,
                details={"url": url},
            ) from e
        except Exception as e:
            error_msg = f"Request failed: {str(e)}"
            logger.error(error_msg)

            raise APIError(
                error="request_error",
                message=error_msg,
                status_code=None,
                details={"exception_type": type(e).__name__},
            ) from e

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
        if isinstance(first_item, dict):
            return first_item.get("content") == "Yes"
        return False

    def _parse_exhibition_title(
        self, indexed_structured: Dict[str, Any]
    ) -> Optional[str]:
        """
        Parse exhibition title from the exhibition field.
        """
        exhibitions = indexed_structured.get("exhibition", [])
        if exhibitions and isinstance(exhibitions[0], dict):
            return exhibitions[0].get("exhibitionTitle")
        return None

    def _parse_exhibition_location(
        self, indexed_structured: Dict[str, Any]
    ) -> Optional[str]:
        """
        Parse exhibition location from the exhibition field.
        """
        exhibitions = indexed_structured.get("exhibition", [])
        if exhibitions and isinstance(exhibitions[0], dict):
            building = exhibitions[0].get("building", "")
            room = exhibitions[0].get("room", "")
            if building and room:
                return f"{building}, {room}"
            if building:
                return building
            if room:
                return room
        return None

    async def _sample_objects_for_stats(
        self, sample_size: int = 1000
    ) -> tuple[int, int]:
        """
        Sample objects and count how many have images.

        Args:
            sample_size: Number of objects to sample

        Returns:
            Tuple of (total_sampled, count_with_images)
        """
        # Search for sample objects
        # Note: unit filtering doesn't work in the API
        filters = CollectionSearchFilter(
            query="*",  # Required for API
            limit=sample_size,
            offset=0,
            unit_code=None,  # Filtering doesn't work
            object_type=None,
            date_start=None,
            date_end=None,
            maker=None,
            material=None,
            topic=None,
            has_images=None,
            is_cc0=None,
            on_view=None,
        )

        try:
            results = await self.search_collections(filters)
            objects = results.objects

            count_with_images = sum(1 for obj in objects if obj.images)

            return len(objects), count_with_images

        except APIError as e:
            logger.warning("Failed to sample objects for stats: %s", e)
            return 0, 0

    def _parse_object_data(self, raw_data: Dict[str, Any]) -> SmithsonianObject:
        """
        Parse raw API response data into a SmithsonianObject.
        """
        # Handle case where raw_data might be a string (JSON string)
        if isinstance(raw_data, str):
            try:
                raw_data = json.loads(raw_data)
            except json.JSONDecodeError as exc:
                logger.error("Failed to parse raw_data as JSON: %s", raw_data)
                raise ValueError("raw_data is not valid JSON or dict") from exc

        if not isinstance(raw_data, dict):
            logger.error("raw_data is not a dict or JSON string: %s", type(raw_data))
            raise ValueError("raw_data must be a dict or JSON string")

        content = raw_data.get("content", {})
        descriptive_non_repeating = content.get("descriptiveNonRepeating", {})
        freetext = content.get("freetext", {})
        indexed_structured = content.get("indexedStructured", {})

        # Extract core fields
        obj_id = raw_data.get("id", "")
        title = raw_data.get("title", "")
        unit_code = raw_data.get("unitCode", "")

        # Parse images with robust structure handling
        images = []
        online_media = descriptive_non_repeating.get("online_media", {})

        # Log when online_media is missing (API may have changed)
        if not online_media:
            logger.debug("No online_media found for object %s", obj_id)

        # Handle different possible structures for online_media
        media_items = []
        if isinstance(online_media, list):
            # online_media is a direct array of media items
            media_items = online_media
        elif isinstance(online_media, dict):
            if "media" in online_media and isinstance(online_media["media"], list):
                # online_media has a "media" key containing array
                media_items = online_media["media"]
            elif online_media.get("type"):
                # online_media itself is a single media item
                media_items = [online_media]

        # Process each media item
        for media_item in media_items:
            if not isinstance(media_item, dict):
                continue



            if media_item.get("type") == "Images":
                # Extract media URL - prioritize high-resolution versions from resources
                media_url = None

                # First, check resources array for high-resolution versions
                resources = media_item.get("resources", [])
                if isinstance(resources, list):
                    # Prioritize high-res TIFF, then JPEG, then any download URL
                    for resource in resources:
                        if isinstance(resource, dict):
                            label = resource.get("label", "").lower()
                            url = resource.get("url")
                            if (url and isinstance(url, str) and
                                (url.startswith("http://") or url.startswith("https://"))):
                                if ("high-resolution tiff" in label or
                                    "high-resolution jpeg" in label):
                                    try:
                                        media_url = HttpUrl(url)  # type: ignore
                                        # Extract dimensions if available
                                        dimensions = resource.get("dimensions")
                                        if dimensions and isinstance(dimensions, str):
                                            try:
                                                width, height = dimensions.split("x")
                                                media_item["width"] = int(width)
                                                media_item["height"] = int(height)
                                            except (ValueError, IndexError):
                                                pass
                                        break  # Found high-res, use it
                                    except (ValueError, TypeError):
                                        pass

                # If no high-res found in resources, fall back to direct fields
                if media_url is None:
                    for field_name in ["content", "url", "href", "src"]:
                        candidate_url = media_item.get(field_name)
                        if (candidate_url and isinstance(candidate_url, str) and
                            (candidate_url.startswith("http://") or
                             candidate_url.startswith("https://"))):
                            try:
                                media_url = HttpUrl(candidate_url)  # type: ignore
                            except (ValueError, TypeError):
                                # If URL validation fails, keep as None
                                pass
                            break

                # Extract thumbnail URL
                thumbnail_url = None
                thumbnail_str = media_item.get("thumbnail")
                if thumbnail_str and isinstance(thumbnail_str, str):
                    try:
                        thumbnail_url = HttpUrl(thumbnail_str)  # type: ignore
                    except (ValueError, TypeError):
                        pass

                # Extract IIIF URL
                iiif_url = None
                iiif_str = media_item.get("iiif")
                if iiif_str and isinstance(iiif_str, str):
                    try:
                        iiif_url = HttpUrl(iiif_str)  # type: ignore
                    except (ValueError, TypeError):
                        pass

                # Parse usage rights
                is_cc0 = False
                usage = media_item.get("usage", {})
                if isinstance(usage, dict):
                    access = usage.get("access")
                    is_cc0 = access == "CC0"
                elif isinstance(usage, str):
                    is_cc0 = usage == "CC0"

                images.append(
                    ImageData(
                        url=media_url,
                        thumbnail_url=thumbnail_url,
                        iiif_url=iiif_url,
                        alt_text=media_item.get("caption", ""),
                        width=media_item.get("width"),
                        height=media_item.get("height"),
                        format=media_item.get("format"),
                        size_bytes=media_item.get("size"),
                        caption=media_item.get("caption", ""),
                        is_cc0=is_cc0,
                    )
                )

        logger.debug("Parsed %d images for object %s", images, obj_id)



        return SmithsonianObject(
            id=obj_id,
            title=title,
            url=descriptive_non_repeating.get("record_link"),
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
            except APIError as e:
                logger.warning(
                    "Failed to parse object data for row %s: %s", row.get("id"), e
                )
                # Debug: print the problematic row structure
                logger.debug("Row data: %s", row)
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
            logger.warning(
                "Malformed response for object %s: %s", object_id, response_data
            )
            return None
        except APIError as e:
            if e.error == "not_found" or e.status_code == 404:
                logger.info("Object %s not found in Smithsonian collection", object_id)
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
                website=HttpUrl("https://naturalhistory.si.edu/"),
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="NPG",
                name="National Portrait Gallery",
                description="Portrait art museum",
                website=HttpUrl("https://npg.si.edu/"),
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="SAAM",
                name="Smithsonian American Art Museum",
                description="American art museum",
                website=HttpUrl("https://americanart.si.edu/"),
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="HMSG",
                name="Hirshhorn Museum and Sculpture Garden",
                description="Modern and contemporary art",
                website=HttpUrl("https://hirshhorn.si.edu/"),
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="FSG",
                name="Freer and Sackler Galleries",
                description="Asian art museum",
                website=HttpUrl("https://www.asia.si.edu/"),
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="NMAfA",
                name="National Museum of African Art",
                description="African art museum",
                website=HttpUrl("https://africa.si.edu/"),
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="NMAI",
                name="National Museum of the American Indian",
                description="Native American art and culture",
                website=HttpUrl("https://americanindian.si.edu/"),
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="NASM",
                name="National Air and Space Museum",
                description="Air and space museum",
                website=HttpUrl("https://airandspace.si.edu/"),
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="NMAH",
                name="National Museum of American History",
                description="American history museum",
                website=HttpUrl("https://americanhistory.si.edu/"),
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="SAAM",
                name="Smithsonian American Art Museum",
                description="American art museum",
                website=HttpUrl("https://americanart.si.edu/"),
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="CHNDM",
                name="Cooper Hewitt, Smithsonian Design Museum",
                description="Design museum",
                website=HttpUrl("https://cooperhewitt.org/"),
                location="New York, NY",
            ),
            SmithsonianUnit(
                code="NMAAHC",
                name="National Museum of African American History and Culture",
                description="African American history and culture museum",
                website=HttpUrl("https://nmaahc.si.edu/"),
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="SIA",
                name="Smithsonian Institution Archives",
                description="Archives of the Smithsonian Institution",
                website=HttpUrl("https://siarchives.si.edu/"),
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="NPM",
                name="National Postal Museum",
                description="Postal history museum",
                website=HttpUrl("https://postalmuseum.si.edu/"),
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="NZP",
                name="National Zoo and Conservation Biology Institute",
                description="National Zoo",
                website=HttpUrl("https://nationalzoo.si.edu/"),
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="AAA",
                name="Archives of American Art",
                description="Archives of American Art",
                website=HttpUrl("https://aaa.si.edu/"),
                location="Washington, DC",
            ),
            SmithsonianUnit(
                code="ACM",
                name="Anacostia Community Museum",
                description="Anacostia",
                website=HttpUrl("https://anacostia.si.edu/"),
                location="Washington, DC",
            ),
        ]

        return known_units

    async def get_collection_stats(self) -> CollectionStats: # pylint: disable=too-many-locals
        """
        Get overall collection statistics.

        Note: The Smithsonian API stats endpoint only provides CC0 object counts.
        Image statistics are estimated via sampling since the API doesn't provide
        per-media-type metrics. Additionally, the current API version does not
        include online_media data in detailed content responses, so actual image
        availability cannot be verified. Per-museum image counts are approximations
        based on overall collection proportions and may not reflect actual
        museum-specific digitization patterns.
        """
        try:
            # Get base stats (total objects, CC0 metrics) from the stats endpoint
            stats_response = await self._make_request("stats")
            stats_data = stats_response.get("response", {})
            total_objects = stats_data.get("total_objects", 0)
            metrics = stats_data.get("metrics", {})
            total_cc0 = metrics.get("CC0_records", 0)

            # Get estimates via sampling (API doesn't support accurate filtered counts)
            sample_size, sample_with_images = await self._sample_objects_for_stats(
                sample_size=1000
            )
            if sample_size > 0:
                total_with_images = int((sample_with_images / sample_size) * total_objects)
            else:
                total_with_images = 0

            # Build unit statistics
            unit_stats = []
            units_data = stats_data.get("units", [])
            unit_name_map = {unit.code: unit.name for unit in await self.get_units()}

            # Note: Smithsonian API doesn't provide per-unit image statistics.
            # We use overall collection proportions as estimates for each unit.
            # This is a limitation of the API - different museum types should have
            # different image percentages, but we can't determine this accurately.
            overall_sample_size, overall_with_images = await self._sample_objects_for_stats(
                sample_size=1000
            )
            if overall_sample_size > 0:
                overall_images_ratio = overall_with_images / overall_sample_size
            else:
                overall_images_ratio = 0

            for unit_data in units_data:
                unit_code = unit_data.get("unit", "")
                unit_metrics = unit_data.get("metrics", {})
                unit_total = unit_data.get("total_objects", 0)

                # Use overall proportions as estimates (API limitation)
                unit_with_images = int(overall_images_ratio * unit_total)

                unit_stats.append(
                    UnitStats(
                        unit_code=unit_code,
                        unit_name=unit_name_map.get(unit_code, unit_code)
                        or "Unknown Unit",
                        total_objects=unit_total,
                        digitized_objects=unit_with_images,
                        cc0_objects=unit_metrics.get("CC0_records", 0),
                        objects_with_images=unit_with_images,
                    )
                )

            return CollectionStats(
                total_objects=total_objects,
                total_digitized=total_with_images,
                total_cc0=total_cc0,
                total_with_images=total_with_images,
                units=unit_stats,
                last_updated=datetime.now(),
            )

        except APIError as e:
            logger.error("Failed to get collection stats from API: %s", e)
            # Fallback to basic search if stats endpoint fails
            try:
                total_objects = (
                    await self.search_collections(
                        CollectionSearchFilter(
                            query="*",
                            limit=0,
                            offset=0,
                            unit_code=None,
                            object_type=None,
                            date_start=None,
                            date_end=None,
                            maker=None,
                            material=None,
                            topic=None,
                            has_images=None,
                            is_cc0=None,
                            on_view=None,
                        )
                    )
                ).total_count

                # Get estimates via sampling
                sample_size, sample_with_images = await self._sample_objects_for_stats(
                    sample_size=1000
                )
                if sample_size > 0:
                    total_with_images = int((sample_with_images / sample_size) * total_objects)
                else:
                    total_with_images = 0

                total_cc0 = (
                    await self.search_collections(
                        CollectionSearchFilter(
                            query="*",
                            limit=0,
                            offset=0,
                            unit_code=None,
                            object_type=None,
                            date_start=None,
                            date_end=None,
                            maker=None,
                            material=None,
                            topic=None,
                            has_images=None,
                            is_cc0=True,
                            on_view=None,
                        )
                    )
                ).total_count

                units = await self.get_units()

                # Get overall proportions for fallback
                overall_sample_size, overall_with_images = await self._sample_objects_for_stats(
                    sample_size=1000
                )
                if overall_sample_size > 0:
                    overall_images_ratio = overall_with_images / overall_sample_size
                else:
                    overall_images_ratio = 0

                unit_stats = []
                for unit in units:
                    unit_total = (
                        await self.search_collections(
                            CollectionSearchFilter(
                                query="*",
                                limit=0,
                                offset=0,
                                unit_code=unit.code,
                                object_type=None,
                                date_start=None,
                                date_end=None,
                                maker=None,
                                material=None,
                                topic=None,
                                has_images=None,
                                is_cc0=None,
                                on_view=None,
                            )
                        )
                    ).total_count

                    # Use overall proportions since per-unit filtering doesn't work
                    unit_images = int(overall_images_ratio * unit_total)

                    unit_cc0 = (
                        await self.search_collections(
                            CollectionSearchFilter(
                                query="*",
                                limit=0,
                                offset=0,
                                unit_code=unit.code,
                                object_type=None,
                                date_start=None,
                                date_end=None,
                                maker=None,
                                material=None,
                                topic=None,
                                has_images=None,
                                is_cc0=True,
                                on_view=None,
                            )
                        )
                    ).total_count

                    unit_stats.append(
                        UnitStats(
                            unit_code=unit.code,
                            unit_name=unit.name,
                            total_objects=unit_total,
                            digitized_objects=unit_images,
                            cc0_objects=unit_cc0,
                            objects_with_images=unit_images,
                        )
                    )

                return CollectionStats(
                    total_objects=total_objects,
                    total_digitized=total_with_images,
                    total_cc0=total_cc0,
                    total_with_images=total_with_images,
                    units=unit_stats,
                    last_updated=datetime.now(),
                )
            except Exception as fallback_error:
                logger.error("Fallback also failed: %s", fallback_error)
                raise APIError(
                    error="stats_failed",
                    message=f"Failed to retrieve collection statistics: {e}",
                    status_code=None,
                ) from fallback_error


# Utility function for creating client instance
async def create_client(api_key: Optional[str] = None) -> SmithsonianAPIClient:
    """
    Create and initialize an API client.

    Args:
        api_key: Optional API key. If not provided, it will be read from `Config.API_KEY`.

    Returns:
        Initialized API client
    """
    client = SmithsonianAPIClient(api_key)
    await client.connect()
    return client
