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
    SimpleSearchResult,
    CollectionSearchFilter,
    SmithsonianUnit,
    CollectionStats,
    MuseumCollectionTypes,
    ObjectTypeAvailability,
    APIError,
)
from .constants import MUSEUM_MAP, VALID_MUSEUM_CODES

logger = logging.getLogger(__name__)


@mcp.tool()
async def search_collections(  # pylint: disable=too-many-arguments, too-many-locals, too-many-positional-arguments
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    query: str = "",
    unit_code: Optional[str] = None,
    museum: Optional[str] = None,
    object_type: Optional[str] = None,
    maker: Optional[str] = None,
    material: Optional[str] = None,
    topic: Optional[str] = None,
    has_images: Optional[bool] = None,
    is_cc0: Optional[bool] = None,
    on_view: Optional[bool] = None,
    limit: int = 500,
    offset: int = 0,
) -> SearchResult:
    """
    Search the Smithsonian Open Access collections.

    This tool allows comprehensive searching across all Smithsonian museums and
    collections with various filters for object type, creator, materials, and more.

     🚨 CRITICAL: NEVER construct URLs from the returned object IDs!
     Always use get_object_url(object_identifier=object_id) to get valid URLs.
     Manual URL construction like "https://collections.si.edu/search/detail/{id}" WILL FAIL.

     IMPORTANT: This tool returns a maximum of 1000 results per call. If you need to
     search through more results (e.g., to find specific on-view items that may not
     appear in the first 1000 results), use the find_on_view_items tool which
     automatically paginates through up to 10,000 results.

     NOTE: When a unit_code is specified, results are automatically prioritized to show
     objects from that museum first (IDs starting with the unit code). If you provide an
     invalid unit_code, this tool will automatically attempt to resolve it as a museum name.
     For best results, use resolve_museum_name() first or provide the museum name directly.

     Args:
         query: General search terms (keywords, titles, descriptions)
         unit_code: Filter by Smithsonian unit code (e.g., "NMNH", "NPG", "SAAM")
         museum: Filter by museum name (e.g., "Smithsonian Asian Art Museum", "Natural History")
         object_type: Type of object (e.g., "painting", "sculpture", "photograph")
        maker: Creator or maker name (artist, photographer, etc.)
        material: Materials or medium (e.g., "oil on canvas", "bronze", "silver")
        topic: Subject topic or theme
        has_images: Filter objects that have associated images
        is_cc0: Filter objects with CC0 (public domain) licensing
        on_view: Filter objects currently on physical exhibit (NOTE: API filter may have
                 data quality issues. For most reliable on-view results, use get_objects_on_view
                 or find_on_view_items tools instead)
        limit: Maximum number of results to return (default: 500, max: 1000)
        offset: Number of results to skip for pagination (default: 0)

    Returns:
        Search results including objects, total count, and pagination info. Each object
        has an 'id' field that can be used with get_object_details. Use the has_more
        and next_offset fields to determine if there are additional results beyond
        the returned set.

    Note:
        **For the absolute simplest experience, use these LLM-optimized tools:**

        **Easiest:** `find_and_describe(query="Alma Thomas Earth Sermon")`
        - Returns complete description with download links in one call!

        **Simple:** `simple_search(query="Alma Thomas")`
        - Returns easy-to-read results with first_object_id ready to use

        **Advanced:** Use search_collections with helper tools (ALWAYS search first, never construct URLs manually):
        - summarize_search_results() - Get readable summary
        - get_first_object_id() - Extract first object ID
        - get_object_url() - Get validated object URL (use IDs from search results only)
        - search_and_get_first_details() - Search and get details

    Examples:
        # Simplest: Get complete description with downloads
        description = find_and_describe(query="Alma Thomas Earth Sermon")

        # Simple: Easy search with readable results
        results = simple_search(query="Alma Thomas Earth Sermon")
        details = get_object_details(object_id=results.first_object_id)

        # Advanced: Full control workflow
        results = search_collections(query="Alma Thomas", object_type="painting")
        summary = summarize_search_results(search_result=results)
        object_id = get_first_object_id(search_result=results)
        url = get_object_url(object_identifier=object_id)  # MANDATORY: Never construct URLs manually
        details = get_object_details(object_id=object_id)
    """
    try:
        # Resolve museum name to unit code if provided
        resolved_unit_code = None

        if museum:
            # If museum name provided, resolve it
            from .utils import resolve_museum_code
            resolved_unit_code = resolve_museum_code(museum)
            if resolved_unit_code:
                logger.info(f"Resolved museum name '{museum}' to unit code '{resolved_unit_code}'")
        elif unit_code:
            # If unit_code provided, validate it
            if unit_code.upper() in VALID_MUSEUM_CODES:
                resolved_unit_code = unit_code.upper()
            else:
                # Try to resolve invalid unit_code as a museum name
                from .utils import resolve_museum_code
                attempted_resolution = resolve_museum_code(unit_code)
                if attempted_resolution:
                    logger.warning(f"Invalid unit_code '{unit_code}' resolved as museum name to '{attempted_resolution}'")
                    resolved_unit_code = attempted_resolution
                else:
                    logger.warning(f"Invalid unit_code '{unit_code}' provided and could not resolve as museum name")
                    resolved_unit_code = unit_code.upper()  # Use as-is but warn

        # Create search filter
        # pylint: disable=duplicate-code
        filters = CollectionSearchFilter(
            query=query,
            unit_code=resolved_unit_code,
            object_type=object_type,
            maker=maker,
            material=material,
            topic=topic,
            has_images=has_images,
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

        # Prioritize objects by unit code if specified
        if resolved_unit_code:
            from .utils import prioritize_objects_by_unit_code
            results.objects = prioritize_objects_by_unit_code(results.objects, resolved_unit_code)
            logger.info(f"Prioritized {len(results.objects)} results for unit_code '{resolved_unit_code}'")

        if 1000 <= limit < results.total_count:
            logger.warning(
                "Search completed: '%s' returned %d of %d results; only first %d returned.",
                query,
                results.returned_count,
                results.total_count,
                limit,
            )
            logger.warning("Use find_on_view_items for comprehensive on-view searches.")
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
async def simple_search(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    query: str = "",
    unit_code: Optional[str] = None,
    museum: Optional[str] = None,
    object_type: Optional[str] = None,
    maker: Optional[str] = None,
    material: Optional[str] = None,
    topic: Optional[str] = None,
    has_images: Optional[bool] = None,
    is_cc0: Optional[bool] = None,
    on_view: Optional[bool] = None,
    limit: int = 10,
) -> SimpleSearchResult:
    """
    Search Smithsonian collections and return results in a simple, easy-to-understand format.

    This tool is optimized for LLMs - it returns a human-readable summary along with
    the key information you need. Use the first_object_id with get_object_details().

    🚨 CRITICAL: NEVER construct URLs from the returned object IDs!
    Always use get_object_url(object_identifier=object_id) to get valid URLs.
    Manual URL construction like "https://collections.si.edu/search/detail/{id}" WILL FAIL.

    NOTE: When a unit_code is specified, results are automatically prioritized to show
    objects from that museum first (IDs starting with the unit code). If you provide an
    invalid unit_code, this tool will automatically attempt to resolve it as a museum name.
    For best results, use resolve_museum_name() first or provide the museum name directly.

    Args:
        query: General search terms (keywords, titles, descriptions)
        unit_code: Filter by Smithsonian unit code (e.g., "NMNH", "NPG", "SAAM")
        museum: Filter by museum name (e.g., "Smithsonian Asian Art Museum", "Natural History")
        object_type: Type of object (e.g., "painting", "sculpture", "photograph")
        maker: Creator or maker name (artist, photographer, etc.)
        material: Materials or medium (e.g., "oil on canvas", "bronze", "silver")
        topic: Subject topic or theme
        has_images: Filter objects that have associated images
        is_cc0: Filter objects with CC0 (public domain) licensing
        on_view: Filter objects currently on physical exhibit
        limit: Number of results to return (default: 10, max: 50)

    Returns:
        Simplified search results with summary, object IDs, and easy-to-use fields

    Example:
        # Search for objects
        results = simple_search(query="Alma Thomas Earth Sermon")

        # ✅ CORRECT: Use get_object_url for URLs
        if results.first_object_id:
            url = get_object_url(object_identifier=results.first_object_id)

        # ❌ WRONG: Don't construct URLs manually
        # url = f"https://collections.si.edu/search/detail/{results.first_object_id}"
    """
    try:
        # Limit to reasonable number for simple format
        limit = max(1, min(limit, 50))

        # Resolve museum name to unit code if provided
        resolved_unit_code = None

        if museum:
            # If museum name provided, resolve it
            from .utils import resolve_museum_code
            resolved_unit_code = resolve_museum_code(museum)
            if resolved_unit_code:
                logger.info(f"Resolved museum name '{museum}' to unit code '{resolved_unit_code}'")
        elif unit_code:
            # If unit_code provided, validate it
            if unit_code.upper() in VALID_MUSEUM_CODES:
                resolved_unit_code = unit_code.upper()
            else:
                # Try to resolve invalid unit_code as a museum name
                from .utils import resolve_museum_code
                attempted_resolution = resolve_museum_code(unit_code)
                if attempted_resolution:
                    logger.warning(f"Invalid unit_code '{unit_code}' resolved as museum name to '{attempted_resolution}'")
                    resolved_unit_code = attempted_resolution
                else:
                    logger.warning(f"Invalid unit_code '{unit_code}' provided and could not resolve as museum name")
                    resolved_unit_code = unit_code.upper()  # Use as-is but warn

        # Create search filter
        filters = CollectionSearchFilter(
            query=query,
            unit_code=resolved_unit_code,
            object_type=object_type,
            maker=maker,
            material=material,
            topic=topic,
            has_images=has_images,
            is_cc0=is_cc0,
            on_view=on_view,
            limit=limit,
            offset=0,
            date_start=None,
            date_end=None,
        )

        # Get API client and perform search
        api_client = await get_api_client(ctx)
        results = await api_client.search_collections(filters)

        # Prioritize objects by unit code if specified
        if resolved_unit_code:
            from .utils import prioritize_objects_by_unit_code
            results.objects = prioritize_objects_by_unit_code(results.objects, resolved_unit_code)
            logger.info(f"Prioritized {len(results.objects)} results for unit_code '{resolved_unit_code}'")

        # Convert to simple format
        simple_results = results.to_simple_result()

        logger.info(
            "Simple search completed: '%s' returned %d of %d results",
            query,
            results.returned_count,
            results.total_count,
        )

        return simple_results

    except Exception as e:
        logger.error("API error during simple search: %s", e)
        raise RuntimeError(f"Simple search failed: {e}") from e


@mcp.tool()
async def simple_explore(  # pylint: disable=too-many-locals, too-many-branches, too-many-statements
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
        museum: Optional museum or museum code to focus on (e.g., "asian art", "SAAM", "Smithsonian Asian Art Museum")
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
            from .utils import resolve_museum_code
            museum_code = resolve_museum_code(museum)

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
                query="*",
                unit_code=museum_code,
                limit=min(max_samples * 2, 400),
                offset=0,
                object_type=None,
                maker=None,
                material=None,
                topic=None,
                has_images=None,
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
                museum_sample.extend(type_objects[:samples_from_type])

            collected_objects.extend(museum_sample)

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
async def continue_explore(  # pylint: disable=too-many-locals, too-many-branches, too-many-statements
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
        museum: Optional museum focus (e.g., "asian art", "SAAM", "Smithsonian Asian Art Museum")
        max_samples: How many new examples to return (default 50, max 200)

    Returns:
        More diverse samples from the same topic, excluding objects you've already seen
    """
    try:  # pylint: disable=too-many-nested-blocks
        # Reuse the same exploration logic but with seen items filtered out
        if not topic or topic.strip() == "":
            raise ValueError("Search topic cannot be empty")
        if previously_seen_ids is None:
            previously_seen_ids = []
        max_samples = min(max(10, max_samples), 200)
        if len(topic.strip()) < 2:
            raise ValueError("Search topic must be at least 2 characters long")

        # Map museum names to codes
        museum_code = None
        if museum:
            from .utils import resolve_museum_code
            museum_code = resolve_museum_code(museum)

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
                        museum_sample.extend(
                            type_objects[
                                : max(1, samples_per_museum // max(len(type_groups), 2))
                            ]
                        )
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
                offset=0,
                unit_code=None,
                object_type=None,
                maker=None,
                material=None,
                topic=None,
                has_images=None,
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
async def summarize_search_results(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    search_result: Optional[SearchResult] = None
) -> Optional[str]:
    """
    Provide a human-readable summary of search results.

    This tool creates a clear, readable summary of what objects were found in a search,
    making it easy to understand the results without parsing complex data structures.

    Args:
        search_result: The result from a search_collections call

    Returns:
        A readable summary of the search results, or None if no results provided

    Example:
        results = search_collections(query="Alma Thomas Earth Sermon")
        summary = summarize_search_results(search_result=results)
        # Returns: "Found 3 objects: 1. 'Earth Sermon—Beauty, Love and Peace' by Alma Thomas (edanmdm-hmsg_80.107), ..."
    """
    if search_result is None or not search_result.objects:
        return "No search results to summarize."

    summary_lines = []
    summary_lines.append(f"Found {search_result.returned_count} objects (out of {search_result.total_count} total matches):")

    for i, obj in enumerate(search_result.objects[:5], 1):  # Show first 5 objects
        title = obj.title or "Untitled"
        maker = obj.maker[0] if obj.maker else "Unknown artist"
        object_id = obj.id
        summary_lines.append(f"{i}. '{title}' by {maker} (ID: {object_id})")

    if search_result.returned_count > 5:
        summary_lines.append(f"... and {search_result.returned_count - 5} more objects")

    if search_result.has_more:
        summary_lines.append(f"More results available (use offset={search_result.next_offset} for next page)")

    return "\n".join(summary_lines)


@mcp.tool()
async def get_object_ids(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    search_result: Optional[SearchResult] = None
) -> Optional[List[str]]:
    """
    Extract object IDs from search results for use with get_object_details.

    This is a helper tool to make it easier to get the correct object IDs
    from search results. Use this if you're having trouble extracting IDs manually.

    Args:
        search_result: The result from a search_collections call

    Returns:
        List of object IDs that can be used with get_object_details, or None if no search_result provided

    Example:
        results = search_collections(query="Alma Thomas")
        ids = get_object_ids(search_result=results)
        # ids[0] can now be used with get_object_details
    """
    if search_result is None:
        return None
    return search_result.object_ids


@mcp.tool()
async def get_first_object_id(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    search_result: Optional[SearchResult] = None
) -> Optional[str]:
    """
    Get the ID of the first object from search results.

    This is the easiest way to get an object ID for get_object_details.
    Use this right after search_collections to get the most relevant result.

    Args:
        search_result: The result from a search_collections call

    Returns:
        The object ID of the first result, or None if no results

    Example:
        results = search_collections(query="Alma Thomas Earth Sermon")
        object_id = get_first_object_id(search_result=results)
        details = get_object_details(object_id=object_id)
    """
    if search_result is None:
        return None
    return search_result.first_object_id


@mcp.tool()
async def validate_object_id(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    object_id: str = ""
) -> bool:
    """
    Check if an object ID exists in the Smithsonian collection.

    Use this to verify an object ID before calling get_object_details.
    This is faster than get_object_details since it doesn't fetch full metadata.

    Args:
        object_id: The object ID to validate

    Returns:
        True if the object exists, False otherwise

    Example:
        if validate_object_id(object_id="edanmdm-hmsg_80.107"):
            details = get_object_details(object_id="edanmdm-hmsg_80.107")
    """
    if not object_id or object_id.strip() == "":
        return False

    try:
        api_client = await get_api_client(ctx)
        result = await api_client.get_object_by_id(object_id.strip())
        return result is not None
    except (APIError, RuntimeError, ValueError):
        return False


@mcp.tool()
async def resolve_museum_name(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    museum_name: str = "",
) -> str:
    """
    🔍 MUSEUM NAME RESOLVER - Use this FIRST when working with Smithsonian museums!

    This essential tool converts natural language museum names into correct Smithsonian unit codes.
    ALWAYS use this tool before calling search functions when you have a museum name instead of a code.

    IMPORTANT: Common mistake - "Smithsonian Asian Art Museum" should be "FSG", not "SAAM"!

    Args:
        museum_name: Museum name in plain English (e.g., "Smithsonian Asian Art Museum",
                    "American Art Museum", "Natural History Museum")

    Returns:
        The resolved unit code (e.g., "NMAH", "SAAM", "FSG"), or error message if not found.

    Examples:
        # CORRECT usage:
        code = resolve_museum_name(museum_name="Smithsonian Asian Art Museum")
        # Returns: "FSG"

        # Then use the resolved code:
        search_collections(query="art", unit_code=code)

        # INCORRECT (common mistake):
        search_collections(query="art", unit_code="SAAM")  # Wrong! This is American Art
    """
    if not museum_name or museum_name.strip() == "":
        return "Error: Museum name cannot be empty"

    from .utils import resolve_museum_code

    unit_code = resolve_museum_code(museum_name.strip())
    if not unit_code:
        return f"Error: Could not resolve museum name '{museum_name}'. Please try a different name or use a known unit code like 'SAAM', 'FSG', 'NMNH', etc."

    # Return just the unit code for clear programmatic use
    return unit_code


@mcp.tool()
async def search_and_get_first_url(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    query: str = "",
    unit_code: Optional[str] = None,
    museum: Optional[str] = None,
    object_type: Optional[str] = None,
    maker: Optional[str] = None,
    material: Optional[str] = None,
    topic: Optional[str] = None,
    has_images: Optional[bool] = None,
    is_cc0: Optional[bool] = None,
    on_view: Optional[bool] = None,
    limit: int = 1,
) -> str:
    """
    Search for Smithsonian objects and get the URL for the first result in one step.

    This is the easiest way to find an object and get its web page URL without manual URL construction.
    It combines searching with URL retrieval to prevent the common mistake of guessing URL formats.

    🚨 This tool exists because manual URL construction ALWAYS fails. Use this instead of:
    ❌ search_collections() + manual URL construction
    ✅ search_collections() + get_object_url()

    NOTE: When a unit_code is specified, results are automatically prioritized to show
    objects from that museum first (IDs starting with the unit code).

    Args:
        query: General search terms (keywords, titles, descriptions)
        unit_code: Filter by Smithsonian unit code (e.g., "NMNH", "NPG", "SAAM")
        museum: Filter by museum name (e.g., "Smithsonian Asian Art Museum", "Natural History")
        object_type: Type of object (e.g., "painting", "sculpture", "photograph")
        maker: Creator or maker name (artist, photographer, etc.)
        material: Materials or medium (e.g., "oil on canvas", "bronze", "silver")
        topic: Subject topic or theme
        has_images: Filter objects that have associated images
        is_cc0: Filter objects with CC0 (public domain) licensing
        on_view: Filter objects currently on physical exhibit
        limit: Number of results to search through (default: 1, max: 10)

    Returns:
        Search summary and validated URL for the first result, or error message if no results

    Example:
        # ✅ CORRECT: One-step search and URL retrieval
        result = search_and_get_first_url(query="Alma Thomas Earth Sermon", unit_code="HMSG")
        # Returns: "Found: Alma Thomas 'Earth Sermon' - https://hirshhorn.si.edu/object/..."

        # ❌ WRONG: Don't do this multi-step manual process
        # results = search_collections(query="Alma Thomas")
        # url = f"https://collections.si.edu/search/detail/{results.first_object_id}"  # FAILS!
    """
    try:
        # Limit to reasonable number for this combined operation
        limit = max(1, min(limit, 10))

        # Resolve museum name to unit code if provided
        resolved_unit_code = None

        if museum:
            # If museum name provided, resolve it
            from .utils import resolve_museum_code
            resolved_unit_code = resolve_museum_code(museum)
            if resolved_unit_code:
                logger.info(f"Resolved museum name '{museum}' to unit code '{resolved_unit_code}'")
        elif unit_code:
            # If unit_code provided, validate it
            if unit_code.upper() in VALID_MUSEUM_CODES:
                resolved_unit_code = unit_code.upper()
            else:
                # Try to resolve invalid unit_code as a museum name
                from .utils import resolve_museum_code
                attempted_resolution = resolve_museum_code(unit_code)
                if attempted_resolution:
                    logger.warning(f"Invalid unit_code '{unit_code}' resolved as museum name to '{attempted_resolution}'")
                    resolved_unit_code = attempted_resolution
                else:
                    logger.warning(f"Invalid unit_code '{unit_code}' provided and could not resolve as museum name")
                    resolved_unit_code = unit_code.upper()  # Use as-is but warn

        # Create search filter
        filters = CollectionSearchFilter(
            query=query,
            unit_code=resolved_unit_code,
            object_type=object_type,
            maker=maker,
            material=material,
            topic=topic,
            has_images=has_images,
            is_cc0=is_cc0,
            on_view=on_view,
            limit=limit,
            offset=0,
            date_start=None,
            date_end=None,
        )

        # Get API client and perform search
        api_client = await get_api_client(ctx)
        results = await api_client.search_collections(filters)

        # Prioritize objects by unit code if specified
        if resolved_unit_code:
            from .utils import prioritize_objects_by_unit_code
            results.objects = prioritize_objects_by_unit_code(results.objects, resolved_unit_code)
            logger.info(f"Prioritized {len(results.objects)} results for unit_code '{resolved_unit_code}'")

        if not results.objects:
            return f"No objects found matching: {query}"

        # Get the first object (now prioritized)
        first_object = results.objects[0]
        object_id = first_object.id

        # Get the URL for the first object using the same logic as get_object_url tool
        from .utils import validate_url

        # Try multiple lookup strategies in order of user-friendliness
        lookup_strategies = [object_id]  # Start with the object_id

        result = None
        successful_lookup = None

        # Try each lookup strategy
        for lookup_id in lookup_strategies:
            try:
                candidate_result = await api_client.get_object_by_id(lookup_id)
                if candidate_result:
                    result = candidate_result
                    successful_lookup = lookup_id
                    break
            except Exception:
                continue

        if not result:
            return f"Found object '{first_object.title or 'Untitled'}' but could not retrieve URL"

        # Validate and select the best URL (same logic as get_object_url)
        valid_url = validate_url(str(result.url) if result.url else None)
        valid_record_link = validate_url(str(result.record_link) if result.record_link else None)

        # Prefer record_link if different and valid
        selected_url = None
        if valid_record_link and valid_record_link != valid_url:
            selected_url = valid_record_link
        elif valid_url:
            selected_url = valid_url

        if not selected_url:
            return f"Found object '{first_object.title or 'Untitled'}' but could not retrieve valid URL"

        url = selected_url

        # Build a nice summary
        title = first_object.title or "Untitled"
        maker_text = f" by {first_object.maker[0]}" if first_object.maker else ""
        museum_text = f" at {first_object.unit_name}" if first_object.unit_name else ""

        return f"Found: {title}{maker_text}{museum_text} - {url}"

    except Exception as e:
        logger.error("Error in search_and_get_first_url: %s", e)
        raise RuntimeError(f"Search and get URL failed: {e}") from e


@mcp.tool()
async def find_and_describe(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    query: str = "",
    unit_code: Optional[str] = None,
    object_type: Optional[str] = None,
    maker: Optional[str] = None,
) -> str:
    """
    Find an object and provide a complete description with download information.

    This is the easiest way to get information about a Smithsonian object from their
    Open Access collections.

    IMPORTANT: The Smithsonian Open Access API primarily contains archival/library
    materials (books, manuscripts, catalogs) and some digitized objects. Most museum
    artwork collections (paintings, sculptures, artifacts) are NOT available through
    this API - they require visiting museum websites directly.

    Use get_museum_collection_types() first to see what's available in each museum,
    or check_museum_has_object_type() to verify if a specific type is available.

    Args:
        query: What you're looking for (e.g., "Alma Thomas Earth Sermon")
        unit_code: Museum code (e.g., "HMSG" for Hirshhorn)
        object_type: Type of object (e.g., "painting")
        maker: Artist or creator name

    Returns:
        Complete description of the object including title, artist, description,
        and download information if available

    Example:
        # First check what's available
        types = get_museum_collection_types(unit_code="HMSG")
        # Then search if appropriate
        description = find_and_describe(query="Alma Thomas Earth Sermon", unit_code="HMSG")
    """
    try:
        # Perform search directly
        filters = CollectionSearchFilter(
            query=query,
            unit_code=unit_code,
            object_type=object_type,
            maker=maker,
            material=None,
            topic=None,
            has_images=None,
            is_cc0=None,
            on_view=None,
            limit=1,
            offset=0,
            date_start=None,
            date_end=None,
        )

        api_client = await get_api_client(ctx)
        search_results = await api_client.search_collections(filters)

        if not search_results.objects:
            return f"No objects found matching: {query}"

        # Get detailed information
        object_id = search_results.first_object_id
        if not object_id:
            return f"Found object but could not determine ID for: {query}"

        details = await api_client.get_object_by_id(object_id)

        if not details:
            return f"Found object but could not retrieve details for: {query}"

        # Build comprehensive description
        description_parts = []

        # Basic info
        title = details.title or "Untitled"
        maker_text = ", ".join(details.maker) if details.maker else "Unknown artist"
        description_parts.append(f"**{title}** by {maker_text}")

        # Date and dimensions
        if details.date:
            description_parts.append(f"**Date:** {details.date}")
        if details.dimensions:
            description_parts.append(f"**Dimensions:** {details.dimensions}")

        # Description
        if details.description:
            description_parts.append(f"**Description:** {details.description}")
        elif details.summary:
            description_parts.append(f"**Summary:** {details.summary}")

        # Materials and type
        if details.materials:
            description_parts.append(f"**Materials:** {', '.join(details.materials)}")
        if details.object_type:
            description_parts.append(f"**Type:** {details.object_type}")

        # Location and exhibition
        if details.is_on_view and details.exhibition_location:
            description_parts.append(f"**Currently on view:** {details.exhibition_location}")
        elif details.unit_name:
            description_parts.append(f"**Collection:** {details.unit_name}")

        # Images and downloads
        if details.images:
            image_count = len(details.images)
            description_parts.append(f"**Images available:** {image_count}")

            # Check for downloadable images
            downloadable = [img for img in details.images if img.url and (img.is_cc0 or img.url)]
            if downloadable:
                description_parts.append("**Download options:**")
                for i, img in enumerate(downloadable[:3], 1):  # Show first 3
                    format_info = f" ({img.format})" if img.format else ""
                    size_info = f" [{img.size_bytes} bytes]" if img.size_bytes else ""
                    description_parts.append(f"  {i}. {img.url}{format_info}{size_info}")
                if len(downloadable) > 3:
                    description_parts.append(f"  ... and {len(downloadable) - 3} more")
            else:
                description_parts.append("**Note:** High-resolution downloads may require special permissions")
        else:
            description_parts.append("**Images:** None available")

        # Rights and usage
        if details.is_cc0:
            description_parts.append("**Usage rights:** CC0 (public domain)")
        elif details.rights:
            description_parts.append(f"**Rights:** {details.rights}")

        # Object ID for reference
        description_parts.append(f"**Object ID:** {details.id}")

        return "\n".join(description_parts)

    except (APIError, RuntimeError, ValueError) as e:
        logger.error("Error in find_and_describe: %s", e)
        return f"Error retrieving information for: {query}. {str(e)}"


@mcp.tool()
async def search_and_get_first_details(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    query: str = "",
    unit_code: Optional[str] = None,
    object_type: Optional[str] = None,
    maker: Optional[str] = None,
    material: Optional[str] = None,
    topic: Optional[str] = None,
    has_images: Optional[bool] = None,
    is_cc0: Optional[bool] = None,
    on_view: Optional[bool] = None,
) -> Optional[SmithsonianObject]:
    """
    Search for objects and automatically get details for the first result.

    This is the simplest way to get detailed information about a specific object.
    It combines searching and detail retrieval in one step, automatically selecting
    the most relevant result.

    Args:
        query: General search terms (keywords, titles, descriptions)
        unit_code: Filter by Smithsonian unit (e.g., "NMNH", "NPG", "SAAM")
        object_type: Type of object (e.g., "painting", "sculpture", "photograph")
        maker: Creator or maker name (artist, photographer, etc.)
        material: Materials or medium (e.g., "oil on canvas", "bronze", "silver")
        topic: Subject topic or theme
        has_images: Filter objects that have associated images
        is_cc0: Filter objects with CC0 (public domain) licensing
        on_view: Filter objects currently on physical exhibit

    Returns:
        Detailed information for the first search result, or None if no results found

    Example:
        # Get details for the most relevant Alma Thomas work
        details = search_and_get_first_details(
            query="Alma Thomas Earth Sermon",
            object_type="painting",
            has_images=True
        )
        # Returns full object details including images, description, etc.
    """
    try:
        # Search with limit 1 to get just the first result
        filters = CollectionSearchFilter(
            query=query,
            unit_code=unit_code,
            object_type=object_type,
            maker=maker,
            material=material,
            topic=topic,
            has_images=has_images,
            is_cc0=is_cc0,
            on_view=on_view,
            limit=1,
            offset=0,
            date_start=None,
            date_end=None,
        )

        # Get API client and perform search
        api_client = await get_api_client(ctx)
        results = await api_client.search_collections(filters)

        if not results.objects:
            logger.info("No results found for query: %s", query)
            return None

        # Get details for the first (and only) result
        first_object_id = results.first_object_id
        if first_object_id:
            logger.info("Found object, getting details for: %s", first_object_id)
            return await api_client.get_object_by_id(first_object_id)
        else:
            logger.warning("Search returned results but no valid object ID found")
            return None

    except Exception as e:
        logger.error("Error in search_and_get_first_details: %s", e)
        raise RuntimeError(f"Search and get details failed: {e}") from e


@mcp.tool()
async def search_and_get_details(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    query: str = "",
    unit_code: Optional[str] = None,
    object_type: Optional[str] = None,
    maker: Optional[str] = None,
    material: Optional[str] = None,
    topic: Optional[str] = None,
    has_images: Optional[bool] = None,
    is_cc0: Optional[bool] = None,
    on_view: Optional[bool] = None,
    limit: int = 1,
) -> Optional[SmithsonianObject]:
    """
    Search for objects and get detailed information for the first result.

    This combines search_collections and get_object_details into one convenient tool.
    Use this when you want details for the most relevant search result.

    Args:
        query: General search terms (keywords, titles, descriptions)
        unit_code: Filter by Smithsonian unit (e.g., "NMNH", "NPG", "SAAM")
        object_type: Type of object (e.g., "painting", "sculpture", "photograph")
        maker: Creator or maker name (artist, photographer, etc.)
        material: Materials or medium (e.g., "oil on canvas", "bronze", "silver")
        topic: Subject topic or theme
        has_images: Filter objects that have associated images
        is_cc0: Filter objects with CC0 (public domain) licensing
        on_view: Filter objects currently on physical exhibit
        limit: Number of results to search through (default: 1, max: 10)

    Returns:
        Detailed information for the first search result, or None if no results found

    Example:
        # Get details for the most relevant Alma Thomas work
        details = search_and_get_details(
            query="Alma Thomas Earth Sermon",
            object_type="painting",
            has_images=True
        )
    """
    try:
        # Limit to reasonable number for this combined operation
        limit = max(1, min(limit, 10))

        # Create search filter
        filters = CollectionSearchFilter(
            query=query,
            unit_code=unit_code,
            object_type=object_type,
            maker=maker,
            material=material,
            topic=topic,
            has_images=has_images,
            is_cc0=is_cc0,
            on_view=on_view,
            limit=limit,
            offset=0,
            date_start=None,
            date_end=None,
        )

        # Get API client and perform search
        api_client = await get_api_client(ctx)
        results = await api_client.search_collections(filters)

        if not results.objects:
            logger.info("No results found for query: %s", query)
            return None

        # Get details for the first result
        first_object_id = results.first_object_id
        if first_object_id:
            logger.info("Found %d results, getting details for first: %s", results.returned_count, first_object_id)
            return await api_client.get_object_by_id(first_object_id)
        else:
            logger.warning("Search returned results but no valid object ID found")
            return None

    except Exception as e:
        logger.error("Error in search_and_get_details: %s", e)
        raise RuntimeError(f"Search and get details failed: {e}") from e


@mcp.tool()
async def get_object_details(
    ctx: Optional[Context[ServerSession, ServerContext]] = None, object_id: str = ""
) -> Optional[SmithsonianObject]:
    """
    Get detailed information about a specific Smithsonian collection object.

    This tool retrieves comprehensive metadata, descriptions, images, and other
    details for a single object using its unique identifier.

    The tool automatically tries multiple ID formats to handle different input styles:
    - Full IDs like "edanmdm-hmsg_80.107"
    - Partial IDs like "hmsg_80.107" (will be prefixed automatically)

    Args:
        object_id: Unique identifier for the object. This should be the 'id' field
                  from a search result. Can be:
                  - Full API ID (e.g., "edanmdm-hmsg_80.107")
                  - Partial ID from object URLs (e.g., "hmsg_80.107")
                  - Any format - the tool will try multiple variations automatically

    Returns:
        Detailed object information, or None if object not found

    Note:
        If the object is not found, the tool tries multiple ID formats automatically.
        For best results, use the 'id' field from search_collections results.
        Use validate_object_id() first to check if an ID exists.
        IMPORTANT: Use get_object_url() if you need the object's web page URL.
        NEVER construct URLs manually - always use search tools first to find the correct ID, then get_object_url().

    Example:
        # First search for objects
        results = search_collections(query="Alma Thomas")

        # Easy way: Use helper to get first ID
        object_id = get_first_object_id(search_result=results)
        if object_id and validate_object_id(object_id=object_id):
            details = get_object_details(object_id=object_id)

        # Alternative: Manual extraction
        if results.objects:
            details = get_object_details(object_id=results.objects[0].id)
    """
    # Input validation
    if not object_id or object_id.strip() == "":
        raise ValueError("object_id cannot be empty")

    object_id = object_id.strip()

    try:
        api_client = await get_api_client(ctx)
        result = await api_client.get_object_by_id(object_id)

        if result:
            logger.info("Retrieved object details: %s", object_id)
        else:
            logger.warning(
                "Object not found: %s. This may indicate the object doesn't exist, "
                "or the ID format needs adjustment. Try using the exact ID from search results.",
                object_id
            )

        return result

    except Exception as e:
        logger.error("API error retrieving object %s: %s", object_id, e)
        raise RuntimeError(
            f"Failed to retrieve object '{object_id}': {e}. "
            "Try using the exact ID from search results (e.g., 'edanmdm-hmsg_80.107')."
        ) from e


@mcp.tool()
async def get_object_url(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    object_identifier: str = ""
) -> Optional[str]:
    """
    🚨 CRITICAL WARNING: NEVER construct Smithsonian URLs manually! 🚨

    Manual URL construction ALWAYS FAILS due to:
    - Case sensitivity issues (F1916.118 vs f1916.118)
    - Changing URL formats over time
    - Different museums using different URL patterns
    - API updates that break old URL structures

    ❌ WRONG - These will FAIL:
    "https://collections.si.edu/search/detail/{id}"
    "https://asia.si.edu/object/{id}"
    "https://americanhistory.si.edu/collections/{id}"

    ✅ CORRECT - Always use this tool:
    url = get_object_url(object_identifier="edanmdm-hmsg_80.107")

    This tool provides the exact, validated URL from Smithsonian's authoritative record_link field.
    It handles all the complexity of URL formatting, case sensitivity, and API changes automatically.

    The tool accepts multiple identifier formats:
    - Accession Number (e.g., "F1900.47")
    - Record ID (e.g., "fsg_F1900.47")
    - Internal ID (e.g., "ld1-1643390182193-1643390183699-0")
    - Full API ID (e.g., "edanmdm-hmsg_80.107")
    - Partial ID from object URLs (e.g., "hmsg_80.107")

    Args:
        object_identifier: Identifier for the object (NEVER a manually constructed URL)

    Returns:
        Validated URL to the object's page, or None if object not found

    IMPORTANT: This tool exists because manual URL construction consistently fails.
    Smithsonian URLs change frequently and have complex formatting rules that only this
    tool knows how to handle correctly.

    Examples:
        # ✅ CORRECT: Use the tool
        url = get_object_url(object_identifier="F1900.47")
        # Returns: "https://asia.si.edu/object/F1900.47/"

        # ❌ WRONG: Manual construction (will fail)
        # url = "https://collections.si.edu/search/detail/edanmdm-hmsg_80.107"  # FAILS!

        # ✅ CORRECT: Use tool with any valid identifier
        url = get_object_url(object_identifier="edanmdm-hmsg_80.107")
    """
    # Input validation
    if not object_identifier or object_identifier.strip() == "":
        raise ValueError("object_identifier cannot be empty")

    object_identifier = object_identifier.strip()

    try:
        from .utils import validate_url

        api_client = await get_api_client(ctx)

        # Try multiple lookup strategies in order of user-friendliness
        lookup_strategies = []

        # Strategy 1: Try as Accession Number (most user-friendly)
        lookup_strategies.append(object_identifier)

        # Strategy 2: Try as Record ID format (museum_code + accession)
        if "_" not in object_identifier and not object_identifier.startswith("ld1-"):
            # Try common museum codes
            common_codes = ["fsg", "saam", "nmnh", "npg", "hmsg", "nasm", "nmah"]
            for code in common_codes:
                lookup_strategies.append(f"{code}_{object_identifier}")

        # Strategy 3: Try as Internal ID format
        if not object_identifier.startswith("ld1-") and len(object_identifier) < 20:
            # Try adding ld1- prefix if it looks like a partial ID
            lookup_strategies.append(f"ld1-{object_identifier}")

        # Strategy 4: Try original API ID variations (existing logic)
        lookup_strategies.extend([
            object_identifier,  # Already included, but keep for completeness
        ])

        # Remove duplicates while preserving order
        seen = set()
        lookup_strategies = [x for x in lookup_strategies if not (x in seen or seen.add(x))]

        result = None
        successful_lookup = None

        # Try each lookup strategy
        for lookup_id in lookup_strategies:
            try:
                logger.debug("Trying object identifier format: %s", lookup_id)
                candidate_result = await api_client.get_object_by_id(lookup_id)
                if candidate_result:
                    result = candidate_result
                    successful_lookup = lookup_id
                    logger.info("Successfully found object using identifier: %s", lookup_id)
                    break
            except Exception as e:
                logger.debug("Failed to find object with identifier %s: %s", lookup_id, e)
                continue

        if not result:
            logger.warning(
                "Object not found with identifier: %s. Tried %d different formats.",
                object_identifier, len(lookup_strategies)
            )
            return None

        # Validate and select the best URL
        valid_url = validate_url(str(result.url) if result.url else None)
        valid_record_link = validate_url(str(result.record_link) if result.record_link else None)

        # Prefer record_link if different and valid (web URL over identifier)
        selected_url = None
        if valid_record_link and valid_record_link != valid_url:
            selected_url = valid_record_link
            logger.info("Using record_link URL: %s", selected_url)
        elif valid_url:
            selected_url = valid_url
            logger.info("Using url field: %s", selected_url)
        else:
            logger.warning(
                "No valid URL found for object %s. url='%s', record_link='%s'",
                successful_lookup, result.url, result.record_link
            )
            return None

        logger.info("Retrieved object URL for %s: %s", object_identifier, selected_url)
        return selected_url

    except Exception as e:
        logger.error("API error retrieving object URL %s: %s", object_identifier, e)
        raise RuntimeError(
            f"Failed to retrieve object URL '{object_identifier}': {e}. "
            "This may be due to an invalid ID format or the object not existing. "
            "Try these solutions: "
            "1. Use search tools (search_collections, simple_explore) first to find the correct object ID "
            "2. Try different identifier formats (Accession Number like 'F1900.47', Record ID like 'nmah_1448973', or full API ID) "
            "3. Verify the museum name and object name are correct "
            "REMEMBER: Never construct URLs manually - always use this tool with IDs from search results."
        ) from e


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
    CC0 licensed materials, and breakdowns by museum/unit and object type.

    IMPORTANT: The Smithsonian Open Access API primarily contains archival/library
    materials (books, manuscripts, catalogs) and some digitized objects. Most museum
    artwork collections (paintings, sculptures, artifacts) are NOT available through
    this API - they require visiting museum websites directly.

    Returns:
        Collection statistics including object type breakdowns
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
    museum: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
) -> SearchResult:
    """
    Get objects that are currently on physical exhibit at Smithsonian museums.

    FOR GENERAL overviews of what's on view at a museum, use this tool.
    This tool finds objects that are verified to be on display for the public,
    which is useful for planning museum visits or finding currently accessible objects.

    This tool searches through the collections and filters locally for objects with
    verified exhibition status, ensuring reliable results.

    Args:
        unit_code: Optional filter by specific Smithsonian unit code (e.g., "NMAH", "FSG", "SAAM")
        museum: Optional filter by museum name (e.g., "Smithsonian Asian Art Museum", "Natural History")
        limit: Maximum number of results to return (default: 500, max: 1000)
        offset: Number of results to skip for pagination (default: 0)

    Returns:
        Search results containing objects actually marked as on physical exhibit

    Examples:
        # General overview of what's on view
        get_objects_on_view(unit_code="FSG")
        get_objects_on_view(museum="Smithsonian Asian Art Museum")
    """
    try:
        # Validate inputs
        limit = max(1, min(limit, 1000))

        # Resolve museum name to unit code if provided
        resolved_unit_code = unit_code
        if museum and not unit_code:
            from .utils import resolve_museum_code
            resolved_unit_code = resolve_museum_code(museum)
        elif unit_code:
            resolved_unit_code = unit_code

        # Try API-level filtering first, fall back to local filtering
        api_client = await get_api_client(ctx)

        # Strategy 1: Use API filter for on-view objects
        filters = CollectionSearchFilter(
            query="*",
            unit_code=resolved_unit_code,
            on_view=True,  # Use API filter
            limit=limit,
            offset=offset,
            object_type=None,
            maker=None,
            material=None,
            topic=None,
            has_images=None,
            is_cc0=None,
            date_start=None,
            date_end=None,
        )

        results = await api_client.search_collections(filters)

        # If API filtering returns no results, try local approach
        if not results.objects:
            local_filters = CollectionSearchFilter(
                query="*",
                unit_code=resolved_unit_code,
                on_view=None,  # No API filter, filter locally
                limit=min(limit * 2, 200),  # Get more to find on-view objects
                offset=0,
                object_type=None,
                maker=None,
                material=None,
                topic=None,
                has_images=None,
                is_cc0=None,
                date_start=None,
                date_end=None,
            )

            local_results = await api_client.search_collections(local_filters)

            # Enhanced on-view detection
            def is_effectively_on_view(obj):
                if obj.is_on_view:
                    return True
                if obj.exhibition_title or obj.exhibition_location:
                    return True
                return False

            on_view_objects = [obj for obj in local_results.objects if is_effectively_on_view(obj)]
            results = SearchResult(
                objects=on_view_objects[:limit],
                total_count=len(on_view_objects),
                returned_count=min(len(on_view_objects), limit),
                offset=0,
                has_more=len(on_view_objects) > limit,
                next_offset=limit if len(on_view_objects) > limit else None,
            )

        logger.info(
            "On-view search completed: %d verified on-view out of %d returned",
            results.returned_count,
            results.total_count,
        )

        return results

    except Exception as e:
        logger.error("Error getting museum highlights: %s", e)
        raise RuntimeError(f"Failed to get museum highlights: {e}") from e


@mcp.tool()
async def get_museum_collection_types(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    unit_code: Optional[str] = None,
    sample_size: int = 100,
    use_cache: bool = True
) -> List[MuseumCollectionTypes]:
    """
    Discover what types of objects are available in Smithsonian museums' Open Access collections.

    This tool returns known object types from cached data when available, or samples
    collections to identify object types available in each museum's Open Access contributions.

    IMPORTANT: The Smithsonian Open Access API primarily contains archival/library
    materials and technical objects. Traditional museum artworks (paintings, sculptures)
    are generally NOT available through this API.

    Args:
        unit_code: Specific museum code (e.g., "SAAM", "NASM"), or None for all museums
        sample_size: Number of objects to sample per museum when not using cache (default: 100, max: 500)
        use_cache: Whether to use cached known object types (default: True)

    Returns:
        List of museums with their available object types in Open Access collections

    Examples:
        # Check what types are available at SAAM (uses cache)
        types = get_museum_collection_types(unit_code="SAAM")

        # Check all museums with fresh sampling
        all_types = get_museum_collection_types(use_cache=False)
    """
    from .museum_data import MUSEUM_OBJECT_TYPES, get_museum_object_types

    try:
        sample_size = max(10, min(sample_size, 500))  # Reasonable bounds
        api_client = await get_api_client(ctx)

        # Get list of units to check
        if unit_code:
            # Validate unit code exists
            all_units = await api_client.get_units()
            unit_codes = [unit_code] if any(u.code == unit_code for u in all_units) else []
            if not unit_codes:
                raise ValueError(f"Unknown museum code: {unit_code}")
        else:
            # Get all unit codes
            all_units = await api_client.get_units()
            unit_codes = [u.code for u in all_units]

        results = []

        for code in unit_codes:
            try:
                # First try to get from cache
                cached_types = get_museum_object_types(code) if use_cache else []

                if cached_types:
                    # Use cached data
                    available_types = cached_types
                    source = "cached"
                    sampled_count = 0
                    search_results = None
                else:
                    # Fall back to API sampling
                    filters = CollectionSearchFilter(
                        query="*",  # Get all objects
                        unit_code=code,
                        limit=sample_size,
                        offset=0,
                        object_type=None,
                        maker=None,
                        material=None,
                        topic=None,
                        has_images=None,
                        is_cc0=None,
                        on_view=None,
                        date_start=None,
                        date_end=None,
                    )

                    search_results = await api_client.search_collections(filters)

                    # Extract unique object types
                    object_types = set()
                    for obj in search_results.objects:
                        if obj.object_type:
                            object_types.add(obj.object_type.lower().strip())

                    # Sort for consistency
                    available_types = sorted(list(object_types))
                    source = "sampled"
                    sampled_count = len(search_results.objects)

                # Get museum name
                museum_name = next((u.name for u in all_units if u.code == code), code)

                # Create notes about scope and source
                notes = None
                if not available_types:
                    notes = "No objects found in Open Access collection"
                elif "painting" not in available_types and "sculpture" not in available_types:
                    notes = "Primarily archival/library materials; traditional artwork may not be available in Open Access"

                if source == "cached":
                    notes = (notes + "; " if notes else "") + "Data from cached known types"
                elif source == "sampled":
                    notes = (notes + "; " if notes else "") + f"Sampled {sampled_count} objects"

                results.append(MuseumCollectionTypes(
                    museum_code=code,
                    museum_name=museum_name,
                    available_object_types=available_types,
                    total_sampled=sampled_count,
                    notes=notes
                ))

                if source == "sampled" and search_results:
                    logger.info(
                        "Sampled %d objects from %s (%s): found types %s",
                        len(search_results.objects), code, museum_name, available_types
                    )

            except Exception as e:
                logger.warning("Failed to sample museum %s: %s", code, e)
                # Add empty result for failed museums
                museum_name = next((u.name for u in all_units if u.code == code), code)
                results.append(MuseumCollectionTypes(
                    museum_code=code,
                    museum_name=museum_name,
                    available_object_types=[],
                    total_sampled=0,
                    notes=f"Failed to sample: {str(e)}"
                ))

        return results

    except Exception as e:
        logger.error("Error getting museum collection types: %s", e)
        raise RuntimeError(f"Failed to get museum collection types: {e}") from e


@mcp.tool()
async def get_museum_highlights_on_view(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    unit_code: Optional[str] = None,
    museum: Optional[str] = None,
    limit: int = 10,
) -> SearchResult:
    """
    Get HIGHLIGHTS of notable objects currently on view at a Smithsonian museum.

    FOR questions like "what are the highlights on view" or "featured exhibits".
    This tool performs comprehensive on-view detection across up to 5000 objects
    and returns ONLY objects that are currently on physical exhibit or have active
    exhibition data. It uses multi-batch searching and local filtering to reliably
    identify on-view objects even when API data is incomplete or sparsely populated.

    Returns an empty result if no on-view objects are found after thorough searching -
    no fallbacks to non-on-view objects.

    Args:
        unit_code: Optional museum code (e.g., "FSG", "SAAM", "NMNH")
        museum: Optional museum name (e.g., "Smithsonian Asian Art Museum")
        limit: Number of highlights to return (default: 10, max: 50)

    Returns:
        Curated selection of verified on-view objects, or empty result if none found

    Examples:
        get_museum_highlights_on_view(unit_code="FSG")
        get_museum_highlights_on_view(museum="Smithsonian Asian Art Museum", limit=10)
    """
    try:
        limit = max(5, min(limit, 50))

        # Resolve museum name to unit code if provided
        resolved_unit_code = unit_code
        if museum and not unit_code:
            from .utils import resolve_museum_code
            resolved_unit_code = resolve_museum_code(museum)
        elif unit_code:
            resolved_unit_code = unit_code

        api_client = await get_api_client(ctx)

        # Reliable on-view detection function
        def is_effectively_on_view(obj):
            if obj.is_on_view:  # Direct API flag
                return True
            if obj.exhibition_title or obj.exhibition_location:  # Exhibition context
                return True
            return False

        # Comprehensive multi-search approach for thorough on-view detection
        all_searched_objects = []
        max_searches = 5  # Search up to 5 batches of 1000 objects each

        for search_batch in range(max_searches):
            batch_filters = CollectionSearchFilter(
                query="*",
                unit_code=resolved_unit_code,
                on_view=None,  # Don't rely on potentially unreliable API filter
                limit=1000,  # Large batch size for comprehensive coverage
                offset=search_batch * 1000,  # Different offset for each batch
                object_type=None,
                maker=None,
                material=None,
                topic=None,
                has_images=None,
                is_cc0=None,
                date_start=None,
                date_end=None,
            )

            batch_results = await api_client.search_collections(batch_filters)

            # Add new objects (avoid duplicates across batches)
            existing_ids = {obj.id for obj in all_searched_objects}
            new_objects = [obj for obj in batch_results.objects if obj.id not in existing_ids]
            all_searched_objects.extend(new_objects)

            # Check if we found any on-view objects in this batch
            batch_on_view = [obj for obj in new_objects if is_effectively_on_view(obj)]
            if batch_on_view:
                # Found on-view objects, no need to search further batches
                break

        # Find ALL objects with on-view indicators from all searched objects
        on_view_candidates = [
            obj for obj in all_searched_objects
            if is_effectively_on_view(obj)
        ]

        candidate_objects = on_view_candidates

        # If no on-view objects found after comprehensive multi-batch search, return empty result
        if len(on_view_candidates) == 0:
            logger.info("No on-view objects found at %s after searching %d objects across %d batches",
                       resolved_unit_code, len(all_searched_objects), max_searches)
            return SearchResult(
                objects=[],
                total_count=0,
                returned_count=0,
                offset=0,
                has_more=False,
                next_offset=None,
            )

        # Apply highlight curation to the verified on-view objects

        # Curate highlights: prioritize objects with images and descriptions
        def highlight_score(obj):
            score = 0
            if obj.is_on_view: score += 5  # Truly on view
            if obj.exhibition_title or obj.exhibition_location: score += 3  # Exhibition data
            if obj.images: score += 3
            if obj.description or obj.summary: score += 2
            if obj.title and len(obj.title) > 10: score += 1
            if obj.maker: score += 1
            return score

        # Sort by highlight score and take top results
        curated_highlights = sorted(candidate_objects, key=highlight_score, reverse=True)[:limit]

        # Add metadata about the curation strategy used
        curation_notes = []
        on_view_count = sum(1 for obj in curated_highlights if obj.is_on_view)
        exhibition_count = sum(1 for obj in curated_highlights if (obj.exhibition_title or obj.exhibition_location) and not obj.is_on_view)

        if on_view_count > 0:
            curation_notes.append(f"{on_view_count} currently on view")
        if exhibition_count > 0:
            curation_notes.append(f"{exhibition_count} with exhibition data")

        notes = f"On-view highlights from {resolved_unit_code or 'all museums'}: {', '.join(curation_notes) if curation_notes else 'no on-view objects found'}"

        logger.info(
            "Found %d on-view highlight objects at %s from %d searched objects (%s)",
            len(curated_highlights),
            resolved_unit_code or "all museums",
            len(all_searched_objects),
            notes
        )

        return SearchResult(
            objects=curated_highlights,
            total_count=len(curated_highlights),
            returned_count=len(curated_highlights),
            offset=0,
            has_more=len(candidate_objects) > limit,
            next_offset=None,
        )

    except Exception as e:
        logger.error("Error getting museum highlights: %s", e)
        raise RuntimeError(f"Failed to get museum highlights: {e}") from e


@mcp.tool()
async def check_museum_has_object_type(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    unit_code: str = "",
    object_type: str = "",
    use_cache: bool = True
) -> ObjectTypeAvailability:
    """
    Check if a Smithsonian museum has objects of a specific type in their Open Access collection.

    This tool uses cached known data when available, or samples the collection to determine
    whether a particular type of object is available in a museum's Open Access contributions.

    IMPORTANT: Most museum artwork collections are NOT available through the Open Access API.
    This API primarily contains archival/library materials and some digitized objects.

    Args:
        unit_code: Museum code (e.g., "SAAM" for American Art Museum, "NASM" for Air & Space)
        object_type: Object type to check (e.g., "painting", "sculpture", "aircraft")
        use_cache: Whether to use cached known data (default: True)

    Returns:
        Availability information with explanation

    Examples:
        # Check if SAAM has paintings (uses cache)
        result = check_museum_has_object_type(unit_code="SAAM", object_type="painting")

        # Check if NASM has aircraft with fresh sampling
        result = check_museum_has_object_type(unit_code="NASM", object_type="aircraft", use_cache=False)
    """
    if not unit_code or not object_type:
        raise ValueError("Both unit_code and object_type are required")

    unit_code = unit_code.strip().upper()
    object_type = object_type.strip().lower()

    try:
        api_client = await get_api_client(ctx)

        # Validate museum exists
        all_units = await api_client.get_units()
        museum_info = next((u for u in all_units if u.code == unit_code), None)
        if not museum_info:
            return ObjectTypeAvailability(
                museum_code=unit_code,
                museum_name=f"Unknown Museum ({unit_code})",
                object_type=object_type,
                available=False,
                count=None,
                sample_ids=None,
                message=f"Unknown museum code: {unit_code}"
            )

        # Check cached data first if enabled
        if use_cache:
            from .museum_data import museum_has_object_type as cached_check
            cached_result = cached_check(unit_code, object_type)

            if cached_result:
                return ObjectTypeAvailability(
                    museum_code=unit_code,
                    museum_name=museum_info.name,
                    object_type=object_type,
                    available=True,
                    count=None,  # We don't cache counts, just presence
                    sample_ids=None,
                    message=f"Yes, {museum_info.name} has {object_type}(s) in their Open Access collection (confirmed by cached data)"
                )

        # Search for objects of this type in the museum
        filters = CollectionSearchFilter(
            query=None,  # No general query, just filter by object_type and unit_code
            unit_code=unit_code,
            object_type=object_type,
            limit=10,  # Just need to check if any exist
            offset=0,
            maker=None,
            material=None,
            topic=None,
            has_images=None,
            is_cc0=None,
            on_view=None,
            date_start=None,
            date_end=None,
        )

        search_results = await api_client.search_collections(filters)

        available = search_results.returned_count > 0
        sample_ids = search_results.object_ids[:3] if available else None  # First 3 examples

        # Craft helpful message
        if available:
            message = f"Yes, {museum_info.name} has {search_results.total_count} {object_type}(s) in their Open Access collection"
            if search_results.total_count > search_results.returned_count:
                message += f" ({search_results.returned_count} shown)"
            if not use_cache:
                message += " (sampled)"
        else:
            # Provide guidance based on object type
            if object_type in ["painting", "sculpture", "artifact", "pottery", "textile"]:
                message = f"No {object_type}s found in {museum_info.name}'s Open Access collection. Most museum artwork requires visiting {museum_info.website or 'the museum website'} directly."
            else:
                message = f"No {object_type}s found in {museum_info.name}'s Open Access collection."
            if not use_cache:
                message += " (sampled)"

        return ObjectTypeAvailability(
            museum_code=unit_code,
            museum_name=museum_info.name,
            object_type=object_type,
            available=available,
            count=search_results.total_count if available else None,
            sample_ids=sample_ids,
            message=message
        )

    except Exception as e:
        logger.error("Error checking object type availability: %s", e)
        return ObjectTypeAvailability(
            museum_code=unit_code,
            museum_name=f"Error checking {unit_code}",
            object_type=object_type,
            available=False,
            count=None,
            sample_ids=None,
            message=f"Error checking availability: {str(e)}"
        )
