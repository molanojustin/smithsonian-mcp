"""
Smithsonian Open Access MCP Tools
"""

import logging
from typing import Optional, List

from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession

from .app import mcp
from .context import ServerContext, get_api_client
from .models import (
    SmithsonianObject,
    SearchResult,
    CollectionSearchFilter,
    SmithsonianUnit,
    CollectionStats,
)
from .constants import MUSEUM_MAP, VALID_MUSEUM_CODES

logger = logging.getLogger(__name__)


@mcp.tool()
async def search_collections(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    query: str = "",
    unit_code: Optional[str] = None,
    object_type: Optional[str] = None,
    maker: Optional[str] = None,
    material: Optional[str] = None,
    topic: Optional[str] = None,
    has_images: Optional[bool] = None,
    has_3d: Optional[bool] = None,
    is_cc0: Optional[bool] = None,
    on_view: Optional[bool] = None,
    limit: int = 500,
    offset: int = 0,
) -> SearchResult:
    """
    Search the Smithsonian Open Access collections.

    This tool allows comprehensive searching across all Smithsonian museums and
    collections with various filters for object type, creator, materials, and more.

    IMPORTANT: This tool returns a maximum of 1000 results per call. If you need to
    search through more results (e.g., to find specific on-view items that may not
    appear in the first 1000 results), use the find_on_view_items tool which
    automatically paginates through up to 10,000 results.

    Args:
        query: General search terms (keywords, titles, descriptions)
        unit_code: Filter by Smithsonian unit (e.g., "NMNH", "NPG", "SAAM")
        object_type: Type of object (e.g., "painting", "sculpture", "photograph")
        maker: Creator or maker name (artist, photographer, etc.)
        material: Materials or medium (e.g., "oil on canvas", "bronze", "silver")
        topic: Subject topic or theme
        has_images: Filter objects that have associated images
        has_3d: Filter objects that have 3D models available
        is_cc0: Filter objects with CC0 (public domain) licensing
        on_view: Filter objects currently on physical exhibit (NOTE: API filter may have
                 data quality issues. For most reliable on-view results, use get_objects_on_view
                 or find_on_view_items tools instead)
        limit: Maximum number of results to return (default: 500, max: 1000)
        offset: Number of results to skip for pagination (default: 0)

    Returns:
        Search results including objects, total count, and pagination info. Use the
        has_more and next_offset fields to determine if there are additional results
        beyond the returned set.
    """
    try:

        # Create search filter
        # pylint: disable=duplicate-code
        filters = CollectionSearchFilter(
            query=query,
            unit_code=unit_code,
            object_type=object_type,
            maker=maker,
            material=material,
            topic=topic,
            has_images=has_images,
            has_3d=has_3d,
            is_cc0=is_cc0,
            on_view=on_view,
            limit=limit,
            offset=offset,
            date_start=None,
            date_end=None,
        )

        # Get API client and perform search
        api_client = await get_api_client(ctx)
        results = await api_client.search_collections(filters)

        if 1000 <= limit < results.total_count:
            logger.warning(
                "Search completed: '%s' returned %d of %d results; only first %d returned.",
                query,
                results.returned_count,
                results.total_count,
                limit,
            )
            logger.warning(
                "Use find_on_view_items for comprehensive on-view searches."
            )
        else:
            logger.info(
                "Search completed: '%s' returned %d of %d results",
                query,
                results.returned_count,
                results.total_count,
            )

        return results

    except Exception as e:
        logger.error("API error during search: %s", e)
        raise RuntimeError(f"Search failed: {e}") from e


@mcp.tool()
async def simple_explore(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    topic: str = "",
    museum: Optional[str] = None,
    max_samples: int = 50,
) -> SearchResult:
    """
    Explore Smithsonian collections with diverse, representative results.

    This provides a smarter search that samples across museums and object types to show you
    the variety of what's available for your topic. Instead of just returning the
    'first 50 results',
    it tries to show representative examples from different museums.

    Note: This will return up to max_samples objects, but there may be many more available.
    Use 'search_collections' with pagination if you need systematic access to all results.

    Args:
        topic: What you want to explore (e.g., "dinosaurs", "computers", "space exploration")
        museum: Optional museum or museum code to focus on
        max_samples: How many diverse examples to return (default 50, max 200)

    Returns:
        A diverse sample of objects showing the range available for your topic
    """
    try:
        # Validate inputs
        if not topic or topic.strip() == "":
            raise ValueError("Search topic cannot be empty")
        max_samples = min(max(10, max_samples), 200)
        if len(topic.strip()) < 2:
            raise ValueError("Search topic must be at least 2 characters long")

        # Map museum names to codes
        museum_code = None
        if museum:
            museum_lower = museum.lower().strip()
            if museum_lower in MUSEUM_MAP:
                museum_code = MUSEUM_MAP[museum_lower]
            elif museum_upper := museum.upper():
                # Try to match codes directly
                if museum_upper in VALID_MUSEUM_CODES:
                    museum_code = museum_upper

        # pylint: disable=duplicate-code
        filters = CollectionSearchFilter(
            query=topic,
            unit_code=museum_code,
            limit=min(max_samples * 2, 400),
            offset=0,
            object_type=None,
            maker=None,
            material=None,
            topic=None,
            has_images=None,
            has_3d=None,
            is_cc0=None,
            on_view=None,
            date_start=None,
            date_end=None,
        )

        api_client = await get_api_client(ctx)

        # Strategy 1: If specific museum requested, get diverse samples from there
        if museum_code:
            # Get a broader set first to sample from
            # pylint: disable=duplicate-code
            filters = CollectionSearchFilter(
                query=topic,
                unit_code=museum_code,
                limit=min(max_samples * 2, 400),
                offset=0,
                object_type=None,
                maker=None,
                material=None,
                topic=None,
                has_images=None,
                has_3d=None,
                is_cc0=None,
                on_view=None,
                date_start=None,
                date_end=None,
            )
            results = await api_client.search_collections(filters)

            # Sample for diversity in object types
            collected_objects = []
            type_groups = {}
            for obj in results.objects:
                obj_type = obj.object_type or "unknown"
                if obj_type not in type_groups:
                    type_groups[obj_type] = []
                type_groups[obj_type].append(obj)

            # Distribute samples across types to show variety
            for obj_type, objects in type_groups.items():
                if len(collected_objects) >= max_samples:
                    break
                available = min(
                    len(objects), max(1, max_samples // max(len(type_groups), 1))
                )
                collected_objects.extend(objects[:available])

            # Fill remaining with more objects if needed and available
            if len(collected_objects) < max_samples and len(results.objects) > len(
                collected_objects
            ):
                remaining = [
                    obj for obj in results.objects if obj not in collected_objects
                ]
                needed = max_samples - len(collected_objects)
                collected_objects.extend(remaining[:needed])

            collected_objects = collected_objects[:max_samples]

            return SearchResult(
                objects=collected_objects,
                total_count=max(results.total_count, len(collected_objects)),
                returned_count=len(collected_objects),
                offset=0,
                has_more=len(results.objects) > max_samples,
                next_offset=max_samples if len(results.objects) > max_samples else None,
            )

        # Strategy 2: Sample across all museums for maximum diversity
        # Get broader results first
        broad_results = await api_client.search_collections(filters)

        if not broad_results.objects:
            # No results at all
            return SearchResult(
                objects=[],
                total_count=0,
                returned_count=0,
                offset=0,
                has_more=False,
                next_offset=None,
            )

        # Group by museum
        by_museum = {}
        for obj in broad_results.objects:
            museum_key = obj.unit_code or "unknown"
            if museum_key not in by_museum:
                by_museum[museum_key] = []
            by_museum[museum_key].append(obj)

        # Sample from each museum to show variety
        collected_objects = []
        samples_per_museum = max(1, max_samples // max(len(by_museum), 1))

        for _, objects in by_museum.items():
            if len(collected_objects) >= max_samples:
                break

            # Within each museum, try to get variety in object types
            type_groups = {}
            for obj in objects[:50]:  # Limit per museum for processing
                obj_type = obj.object_type or "unknown"
                if obj_type not in type_groups:
                    type_groups[obj_type] = []
                type_groups[obj_type].append(obj)

            # Take 1-2 samples from each type in this museum
            museum_sample = []
            for obj_type, type_objects in type_groups.items():
                samples_from_type = min(
                    len(type_objects),
                    max(1, samples_per_museum // max(len(type_groups), 2)),
                )
                collected_objects.extend(museum_sample[:samples_per_museum])

        # Fill remaining slots with additional diverse objects
        if len(collected_objects) < max_samples:
            additional_candidates = [
                obj for obj in broad_results.objects if obj not in collected_objects
            ]
            needed = max_samples - len(collected_objects)
            collected_objects.extend(additional_candidates[:needed])

        final_objects = collected_objects[:max_samples]

        return SearchResult(
            objects=final_objects,
            total_count=broad_results.total_count,
            returned_count=len(final_objects),
            offset=0,
            has_more=broad_results.total_count > max_samples,
            next_offset=(
                max_samples if broad_results.total_count > max_samples else None
            ),
        )

    except ValueError as ve:
        logger.warning("Simple explore validation error: %s", ve)
        # Provide fallback
        try:
            filters = CollectionSearchFilter(
                query=topic[:100],
                limit=min(max_samples, 100),
                offset=0,
                unit_code=None,
                object_type=None,
                maker=None,
                material=None,
                topic=None,
                has_images=None,
                has_3d=None,
                is_cc0=None,
                on_view=None,
                date_start=None,
                date_end=None,
            )
            api_client = await get_api_client(ctx)
            results = await api_client.search_collections(filters)
            return results
        except Exception as e:
            logger.error("Fallback also failed: %s", e)
            raise RuntimeError(f"Exploration failed: {str(ve)}") from e

    except Exception as e:
        logger.error("Error in simple explore: %s", e)
        raise RuntimeError(f"Exploration failed: {e}") from e


@mcp.tool()
async def continue_explore(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    topic: str = "",
    previously_seen_ids: Optional[List[str]] = None,
    museum: Optional[str] = None,
    max_samples: int = 50,
) -> SearchResult:
    """
    Continue exploring a topic, avoiding objects you've already seen.

    Use this when you want more results about the same topic but haven't seen everything yet.
    This tool will try to find different objects than the ones you've already encountered.

    Args:
        topic: The same topic you explored before
        previously_seen_ids: List of object IDs you've already seen (from previous results)
        museum: Optional museum focus (same as before)
        max_samples: How many new examples to return (default 50, max 200)

    Returns:
        More diverse samples from the same topic, excluding objects you've already seen
    """
    try:
        # Reuse the same exploration logic but with seen items filtered out
        if not topic or topic.strip() == "":
            raise ValueError("Search topic cannot be empty")
        if previously_seen_ids is None:
            previously_seen_ids = []
        max_samples = min(max(10, max_samples), 200)
        if len(topic.strip()) < 2:
            raise ValueError("Search topic must be at least 2 characters long")

        # Map museum names to codes (same logic as simple_explore)
        museum_code = None
        if museum:
            museum_lower = museum.lower().strip()
            if museum_lower in MUSEUM_MAP:
                museum_code = MUSEUM_MAP[museum_lower]
            elif museum_upper := museum.upper():
                if museum_upper in VALID_MUSEUM_CODES:
                    museum_code = museum_upper

        api_client = await get_api_client(ctx)
        seen_ids = set(previously_seen_ids or [])

        # Get broader results and filter out seen items
        fetch_limit = (
            min(max_samples * 4, 800) if museum_code else min(max_samples * 6, 1200)
        )

        # pylint: disable=duplicate-code
        filters = CollectionSearchFilter(
            query=topic,
            unit_code=museum_code,
            limit=fetch_limit,
            offset=0,
            object_type=None,
            maker=None,
            material=None,
            topic=None,
            has_images=None,
            has_3d=None,
            is_cc0=None,
            on_view=None,
            date_start=None,
            date_end=None,
        )
        broad_results = await api_client.search_collections(filters)

        # Filter out previously seen objects
        new_objects = [obj for obj in broad_results.objects if obj.id not in seen_ids]

        if not new_objects:
            # No new objects found
            return SearchResult(
                objects=[],
                total_count=broad_results.total_count,
                returned_count=0,
                offset=0,
                has_more=len(
                    [obj for obj in broad_results.objects if obj.id not in seen_ids]
                )
                > max_samples,
                next_offset=None,
            )

        # Apply the same diversity sampling logic as simple_explore
        collected_objects = []

        if museum_code:
            # Same museum - sample for type diversity
            type_groups = {}
            for obj in new_objects:
                obj_type = obj.object_type or "unknown"
                if obj_type not in type_groups:
                    type_groups[obj_type] = []
                type_groups[obj_type].append(obj)

            for obj_type, objects in type_groups.items():
                if len(collected_objects) >= max_samples:
                    break
                available = min(
                    len(objects), max(1, max_samples // max(len(type_groups), 1))
                )
                collected_objects.extend(objects[:available])

            # Fill remaining
            if len(collected_objects) < max_samples:
                remaining = [obj for obj in new_objects if obj not in collected_objects]
                needed = max_samples - len(collected_objects)
                collected_objects.extend(remaining[:needed])
        else:
            # Cross-museum diversity sampling
            by_museum = {}
            for obj in new_objects:
                museum_key = obj.unit_code or "unknown"
                if museum_key not in by_museum:
                    by_museum[museum_key] = []
                by_museum[museum_key].append(obj)

            if by_museum:
                samples_per_museum = max(1, max_samples // max(len(by_museum), 1))

                for _, objects in by_museum.items():
                    if len(collected_objects) >= max_samples:
                        break

                    # Sample variety within museum
                    type_groups = {}
                    for obj in objects[:50]:
                        obj_type = obj.object_type or "unknown"
                        if obj_type not in type_groups:
                            type_groups[obj_type] = []
                        type_groups[obj_type].append(obj)

                    museum_sample = []
                    for _, type_objects in type_groups.items():
                        museum_sample.extend(type_objects[:max(1, samples_per_museum // max(len(type_groups), 2))])
                    collected_objects.extend(museum_sample[:samples_per_museum])

                # Fill remaining
                if len(collected_objects) < max_samples:
                    additional_candidates = [
                        obj for obj in new_objects if obj not in collected_objects
                    ]
                    needed = max_samples - len(collected_objects)
                    collected_objects.extend(additional_candidates[:needed])

        final_objects = collected_objects[:max_samples]

        return SearchResult(
            objects=final_objects,
            total_count=broad_results.total_count,
            returned_count=len(final_objects),
            offset=0,
            has_more=len(new_objects) > max_samples,
            next_offset=max_samples if len(new_objects) > max_samples else None,
        )

    except ValueError as ve:
        logger.warning("Continue explore validation error: %s", ve)
        # Provide fallback
        try:
            filters = CollectionSearchFilter(
                query=topic[:100],
                limit=min(max_samples, 100),
                offset=len(previously_seen_ids or []),
                unit_code=None,
                object_type=None,
                maker=None,
                material=None,
                topic=None,
                has_images=None,
                has_3d=None,
                is_cc0=None,
                on_view=None,
                date_start=None,
                date_end=None,
            )
            api_client = await get_api_client(ctx)
            results = await api_client.search_collections(filters)
            return results
        except Exception as e:
            logger.error("Fallback also failed: %s", e)
            raise RuntimeError(f"Continue exploration failed: {str(ve)}") from e

    except Exception as e:
        logger.error("Error in continue explore: %s", e)
        raise RuntimeError(f"Continue exploration failed: {e}") from e


@mcp.tool()
async def get_object_details(
    ctx: Optional[Context[ServerSession, ServerContext]] = None, object_id: str = ""
) -> Optional[SmithsonianObject]:
    """
    Get detailed information about a specific Smithsonian collection object.

    This tool retrieves comprehensive metadata, descriptions, images, and other
    details for a single object using its unique identifier.

    Args:
        object_id: Unique identifier for the object (found in search results)

    Returns:
        Detailed object information, or None if object not found
    """
    try:
        api_client = await get_api_client(ctx)
        result = await api_client.get_object_by_id(object_id)

        if result:
            logger.info("Retrieved object details: %s", object_id)
        else:
            logger.warning("Object not found: %s", object_id)

        return result

    except Exception as e:
        logger.error("API error retrieving object %s: %s", object_id, e)
        raise RuntimeError(f"Failed to retrieve object: {e}") from e


@mcp.tool()
async def get_smithsonian_units(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
) -> List[SmithsonianUnit]:
    """
    Get a list of all Smithsonian Institution museums and research centers.

    This tool provides information about all the different Smithsonian units,
    including their codes, names, and descriptions. Useful for understanding
    the scope of collections and for filtering searches.

    Returns:
        List of Smithsonian units with their codes and descriptions
    """
    try:
        api_client = await get_api_client(ctx)
        units = await api_client.get_units()
        logger.info("Retrieved %d Smithsonian units", len(units))
        return units

    except Exception as e:
        logger.error("Error retrieving Smithsonian units: %s", str(e))
        raise RuntimeError(f"Failed to retrieve units: {str(e)}") from e


@mcp.tool()
async def get_collection_statistics(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
) -> CollectionStats:
    """
    Get comprehensive statistics about the Smithsonian Open Access collections.

    This tool provides overview statistics including total objects, digitized items,
    CC0 licensed materials, and breakdowns by museum/unit.

    Returns:
        Collection statistics and metrics
    """
    try:
        api_client = await get_api_client(ctx)
        stats = await api_client.get_collection_stats()
        logger.info("Retrieved collection statistics")
        return stats

    except Exception as e:
        logger.error("Error retrieving collection statistics: %s", str(e))
        raise RuntimeError(f"Failed to retrieve statistics: {str(e)}") from e


@mcp.tool()
async def search_by_unit(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    unit_code: str = "",
    query: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
) -> SearchResult:
    """
    Search collections within a specific Smithsonian museum or unit.

    This tool focuses searches on a particular museum's collection, useful when
    you want to explore what's available at a specific institution.

    IMPORTANT: This tool returns a maximum of 1000 results per call. For comprehensive
    on-view searches that may require checking beyond 1000 results, use find_on_view_items.

    Args:
        unit_code: Smithsonian unit code (e.g., "NMNH", "NPG", "SAAM", "NASM")
        query: Optional search terms within that unit's collection
        limit: Maximum number of results (default: 500, max: 1000)
        offset: Results offset for pagination (default: 0)

    Returns:
        Search results from the specified unit
    """
    try:
        # Validate inputs
        limit = max(1, min(limit, 1000))

        # Create search filter
        # pylint: disable=duplicate-code
        filters = CollectionSearchFilter(
            query=query or "*",
            unit_code=unit_code,
            limit=limit,
            offset=offset,
            object_type=None,
            maker=None,
            material=None,
            topic=None,
            has_images=None,
            has_3d=None,
            is_cc0=None,
            on_view=None,
            date_start=None,
            date_end=None,
        )

        # Get API client and perform search
        api_client = await get_api_client(ctx)
        results = await api_client.search_collections(filters)

        logger.info(
            "Search by unit '%s' completed: '%s' returned %d of %d results",
            unit_code,
            query,
            results.returned_count,
            results.total_count,
        )

        return results

    except Exception as e:
        logger.error("Unexpected error during search by unit: %s", str(e))
        raise RuntimeError(f"Search by unit failed: {str(e)}") from e


@mcp.tool()
async def get_objects_on_view(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    unit_code: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
) -> SearchResult:
    """
    Get objects that are currently on physical exhibit at Smithsonian museums.

    This tool finds objects that are verified to be on display for the public,
    which is useful for planning museum visits or finding currently accessible objects.

    This tool searches through the collections and filters locally for objects with
    verified exhibition status, ensuring reliable results.

    Args:
        unit_code: Optional filter by specific Smithsonian unit (e.g., "NMAH", "FSG", "SAAM")
        limit: Maximum number of results to return (default: 500, max: 1000)
        offset: Number of results to skip for pagination (default: 0)

    Returns:
        Search results containing objects actually marked as on physical exhibit
    """
    try:
        # Validate inputs
        limit = max(1, min(limit, 1000))

        # Use the same reliable approach as find_on_view_items: search broadly then filter locally
        # pylint: disable=duplicate-code
        filters = CollectionSearchFilter(
            query="*",
            unit_code=unit_code,
            on_view=None,  # Don't use unreliable API filter
            limit=limit,
            offset=offset,
            object_type=None,
            maker=None,
            material=None,
            topic=None,
            has_images=None,
            has_3d=None,
            is_cc0=None,
            date_start=None,
            date_end=None,
        )

        # Get API client and perform search
        api_client = await get_api_client(ctx)
        results = await api_client.search_collections(filters)

        # Filter for verified on-view objects
        verified_on_view = [obj for obj in results.objects if obj.is_on_view]

        logger.info(
            "On-view search completed: %d verified on-view out of %d returned",
            len(verified_on_view),
            results.returned_count,
        )

        # Return verified on-view objects
        return SearchResult(
            objects=verified_on_view,
            total_count=len(verified_on_view),
            returned_count=len(verified_on_view),
            offset=offset,
            has_more=False,
            next_offset=None,
        )

    except Exception as e:
        logger.error("API error during on-view search: %s", e)
        raise RuntimeError(f"On-view search failed: {e}") from e


@mcp.tool()
async def check_object_on_view(
    ctx: Optional[Context[ServerSession, ServerContext]] = None, object_id: str = ""
) -> Optional[SmithsonianObject]:
    """
    Check if a specific object is currently on physical exhibit.

    This tool retrieves detailed information about an object including
    its current exhibition status.

    Args:
        object_id: Unique identifier for the object

    Returns:
        Object details including on-view status, or None if object not found
    """
    try:
        api_client = await get_api_client(ctx)
        result = await api_client.get_object_by_id(object_id)

        if result:
            status = "on view" if result.is_on_view else "not on view"
            logger.info("Object %s is %s", object_id, status)
        else:
            logger.warning("Object not found: %s", object_id)

        return result

    except Exception as e:
        logger.error("API error checking object %s: %s", object_id, e)
        raise RuntimeError(f"Failed to check object status: {e}") from e


@mcp.tool()
async def find_on_view_items(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    query: str = "",
    unit_code: Optional[str] = None,
    max_results: int = 5000,
) -> SearchResult:
    """
    Find ALL items currently on physical exhibit matching a search query.

    This tool automatically handles pagination to search through large result sets
    and filters them to return only those with verified exhibition status. Unlike
    other search tools limited to 1000 results, this tool will paginate through
    multiple API calls to search up to max_results items.

    Important: This tool searches up to max_results items across multiple API calls
    and filters to only those with verified exhibition data, which is more reliable
    than using the on_view parameter in other search functions. This ensures items
    like "Bert and Ernie" are found even if they appear beyond the first 1000 results.

    Args:
        query: Search terms (e.g., "muppet", "Hokusai", "dinosaur fossils")
        unit_code: Optional museum code (e.g., "NMAH", "FSG", "NMNH", "NASM")
        max_results: Maximum items to search through (default: 5000, max: 10000)

    Returns:
        Search results with only verified on-view items, including exhibition details.
        The total_count reflects how many on-view items were found, not the total
        matching items in the database.

    Examples:
        find_on_view_items(query="muppet", unit_code="NMAH")
        find_on_view_items(query="Hokusai", unit_code="FSG", max_results=10000)
    """
    try:
        if not query or query.strip() == "":
            raise ValueError("Search query cannot be empty")
        max_results = max(1, min(max_results, 10000))

        logger.info(
            "Finding on-view items for '%s' at %s (searching up to %d items)",
            query,
            unit_code or "all museums",
            max_results,
        )

        api_client = await get_api_client(ctx)

        batch_size = 1000
        all_objects = []
        offset = 0
        total_available = None

        while offset < max_results:
            current_batch_size = min(batch_size, max_results - offset)

            # pylint: disable=duplicate-code
            filters = CollectionSearchFilter(
                query=query,
                unit_code=unit_code,
                on_view=None,
                limit=current_batch_size,
                offset=offset,
                object_type=None,
                maker=None,
                material=None,
                topic=None,
                has_images=None,
                has_3d=None,
                is_cc0=None,
                date_start=None,
                date_end=None,
            )

            batch_results = await api_client.search_collections(filters)
            all_objects.extend(batch_results.objects)

            if total_available is None:
                total_available = batch_results.total_count

            logger.info(
                "Fetched batch at offset %d: %d items (total searched so far: %d/%s)",
                offset,
                len(batch_results.objects),
                len(all_objects),
                str(total_available),
            )

            if not batch_results.has_more:
                logger.info("Reached end of available results at offset %d", offset)
                break

            offset += current_batch_size

        on_view_items = [obj for obj in all_objects if obj.is_on_view]

        logger.info(
            "Found %d verified on-view items out of %d total items searched",
            len(on_view_items),
            len(all_objects),
        )
        logger.info(
            "%s items available in database for this query",
            str(total_available),
        )

        return SearchResult(
            objects=on_view_items,
            total_count=len(on_view_items),
            returned_count=len(on_view_items),
            offset=0,
            has_more=False,
            next_offset=None,
        )

    except Exception as e:
        logger.error("Error finding on-view items: %s", e)
        raise RuntimeError(f"Failed to find on-view items: {e}") from e
