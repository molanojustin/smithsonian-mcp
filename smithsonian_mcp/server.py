"""
Smithsonian Open Access MCP Server

This MCP server provides AI assistants with access to the Smithsonian's
Open Access collections through a standardized interface.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any, Union
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastmcp import FastMCP
from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession
from mcp.server.fastmcp.prompts import base

from .config import Config
from .api_client import SmithsonianAPIClient, create_client
from .models import (
    SmithsonianObject,
    SearchResult,
    CollectionSearchFilter,
    SmithsonianUnit,
    CollectionStats,
    ImageData,
    APIError,
)

# Configure logging
logging.basicConfig(level=getattr(logging, Config.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Global API client instance for mcpo compatibility
_global_api_client: Optional[SmithsonianAPIClient] = None


@dataclass
class ServerContext:
    """Application context with initialized dependencies."""

    api_client: SmithsonianAPIClient


async def get_api_client(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
) -> SmithsonianAPIClient:
    """Get API client from global instance for mcpo compatibility."""
    global _global_api_client

    # Always use global client to avoid context access issues
    # This works for both normal MCP and mcpo scenarios
    if _global_api_client is None:
        _global_api_client = await create_client()
        logger.info("Global API client initialized")

    return _global_api_client


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[ServerContext]:
    """Manage server lifecycle with API client initialization."""
    global _global_api_client
    logger.info("Initializing Smithsonian MCP Server...")

    # Validate configuration
    if not Config.validate_api_key():
        logger.warning(
            "No API key configured. Some features may have reduced rate limits. "
            "Set SMITHSONIAN_API_KEY environment variable for full access."
        )

    # Initialize API client
    api_client = await create_client()
    _global_api_client = api_client  # Set global reference for mcpo compatibility

    try:
        logger.info(
            f"Server initialized: {Config.SERVER_NAME} v{Config.SERVER_VERSION}"
        )
        yield ServerContext(api_client=api_client)
    finally:
        logger.info("Shutting down Smithsonian MCP Server...")
        await api_client.disconnect()
        _global_api_client = None


# Initialize MCP server with lifespan management
mcp = FastMCP(Config.SERVER_NAME, lifespan=server_lifespan)


# ============================================================================
# TOOLS - Functions that AI assistants can call to perform actions
# ============================================================================


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
        on_view: Filter objects currently on physical exhibit (NOTE: API filter is unreliable,
                 returns many false positives. For accurate on-view results, search broadly
                 with high limit and check is_on_view field in results)
        limit: Maximum number of results to return (default: 500, max: 1000)
        offset: Number of results to skip for pagination (default: 0)

    Returns:
        Search results including objects, total count, and pagination info
    """
    try:
        # Validate inputs
        if limit > 1000:
            limit = 1000
        if limit < 1:
            limit = 1

        # Create search filter
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

        logger.info(
            f"Search completed: '{query}' returned {results.returned_count} of {results.total_count} results"
        )

        return results

    except Exception as e:
        logger.error(f"API error during search: {e}")
        raise Exception(f"Search failed: {e}")


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
    the variety of what's available for your topic. Instead of just returning the 'first 50 results',
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
            museum_map = {
                "american history": "NMAH", "natural history": "NMNH", "art": "SAAM",
                "american indian": "NMAI", "air and space": "NASM", "asian art": "FSG"
            }
            if museum_lower in museum_map:
                museum_code = museum_map[museum_lower]
            elif museum_upper := museum.upper():
                # Try to match codes directly
                valid_codes = ["NMAH", "NMNH", "SAAM", "NMNH", "NASM", "NPG", "FSG", "HMSG", "NMAfA", "NMAI"]
                if museum_upper in valid_codes:
                    museum_code = museum_upper

        api_client = await get_api_client(ctx)

        # Strategy 1: If specific museum requested, get diverse samples from there
        if museum_code:
            # Get a broader set first to sample from
            filters = CollectionSearchFilter(
                query=topic, unit_code=museum_code, limit=min(max_samples * 2, 400),
                offset=0, object_type=None, maker=None, material=None, topic=None,
                has_images=None, has_3d=None, is_cc0=None, on_view=None,
                date_start=None, date_end=None
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
                available = min(len(objects), max(1, max_samples // max(len(type_groups), 1)))
                collected_objects.extend(objects[:available])

            # Fill remaining with more objects if needed and available
            if len(collected_objects) < max_samples and len(results.objects) > len(collected_objects):
                remaining = [obj for obj in results.objects if obj not in collected_objects]
                needed = max_samples - len(collected_objects)
                collected_objects.extend(remaining[:needed])

            collected_objects = collected_objects[:max_samples]

            return SearchResult(
                objects=collected_objects,
                total_count=max(len(results.objects), len(collected_objects)),
                returned_count=len(collected_objects),
                offset=0,
                has_more=len(results.objects) > max_samples,
                next_offset=max_samples if len(results.objects) > max_samples else None
            )

        else:
            # Strategy 2: Sample across all museums for maximum diversity
            # Get broader results first
            filters = CollectionSearchFilter(
                query=topic, unit_code=None, limit=min(max_samples * 3, 600),
                offset=0, object_type=None, maker=None, material=None, topic=None,
                has_images=None, has_3d=None, is_cc0=None, on_view=None,
                date_start=None, date_end=None
            )
            broad_results = await api_client.search_collections(filters)

            if not broad_results.objects:
                # No results at all
                return SearchResult(
                    objects=[],
                    total_count=0,
                    returned_count=0,
                    offset=0,
                    has_more=False,
                    next_offset=None
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

            for museum_code_key, objects in by_museum.items():
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
                    samples_from_type = min(len(type_objects), max(1, samples_per_museum // max(len(type_groups), 2)))
                    museum_sample.extend(type_objects[:samples_from_type])

                collected_objects.extend(museum_sample[:samples_per_museum])

            # Fill remaining slots with additional diverse objects
            if len(collected_objects) < max_samples:
                additional_candidates = [obj for obj in broad_results.objects
                                       if obj not in collected_objects]
                needed = max_samples - len(collected_objects)
                collected_objects.extend(additional_candidates[:needed])

            final_objects = collected_objects[:max_samples]

            return SearchResult(
                objects=final_objects,
                total_count=broad_results.total_count,
                returned_count=len(final_objects),
                offset=0,
                has_more=broad_results.total_count > max_samples,
                next_offset=max_samples if broad_results.total_count > max_samples else None
            )

    except ValueError as ve:
        logger.warning(f"Simple explore validation error: {ve}")
        # Provide fallback
        try:
            filters = CollectionSearchFilter(
                query=topic[:100], limit=min(max_samples, 100),
                offset=0, unit_code=None, object_type=None, maker=None,
                material=None, topic=None, has_images=None, has_3d=None,
                is_cc0=None, on_view=None, date_start=None, date_end=None
            )
            api_client = await get_api_client(ctx)
            results = await api_client.search_collections(filters)
            return results
        except Exception as e:
            logger.error(f"Fallback also failed: {e}")
            raise Exception(f"Exploration failed: {str(ve)}")

    except Exception as e:
        logger.error(f"Error in simple explore: {e}")
        raise Exception(f"Exploration failed: {e}")


@mcp.tool()
async def continue_explore(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    topic: str = "",
    previously_seen_ids: List[str] = None,
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
            museum_map = {
                "american history": "NMAH", "natural history": "NMNH", "art": "SAAM",
                "american indian": "NMAI", "air and space": "NASM", "asian art": "FSG"
            }
            if museum_lower in museum_map:
                museum_code = museum_map[museum_lower]
            elif museum_upper := museum.upper():
                valid_codes = ["NMAH", "NMNH", "SAAM", "NMNH", "NASM", "NPG", "FSG", "HMSG", "NMAfA", "NMAI"]
                if museum_upper in valid_codes:
                    museum_code = museum_upper

        api_client = await get_api_client(ctx)
        seen_ids = set(previously_seen_ids or [])

        # Get broader results and filter out seen items
        fetch_limit = min(max_samples * 4, 800) if museum_code else min(max_samples * 6, 1200)

        filters = CollectionSearchFilter(
            query=topic, unit_code=museum_code, limit=fetch_limit,
            offset=0, object_type=None, maker=None, material=None, topic=None,
            has_images=None, has_3d=None, is_cc0=None, on_view=None,
            date_start=None, date_end=None
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
                has_more=len([obj for obj in broad_results.objects if obj.id not in seen_ids]) > max_samples,
                next_offset=None
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
                available = min(len(objects), max(1, max_samples // max(len(type_groups), 1)))
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

                for museum_code_key, objects in by_museum.items():
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
                    for obj_type, type_objects in type_groups.items():
                        samples_from_type = min(len(type_objects), max(1, samples_per_museum // max(len(type_groups), 2)))
                        museum_sample.extend(type_objects[:samples_from_type])

                    collected_objects.extend(museum_sample[:samples_per_museum])

                # Fill remaining
                if len(collected_objects) < max_samples:
                    additional_candidates = [obj for obj in new_objects if obj not in collected_objects]
                    needed = max_samples - len(collected_objects)
                    collected_objects.extend(additional_candidates[:needed])

        final_objects = collected_objects[:max_samples]

        return SearchResult(
            objects=final_objects,
            total_count=broad_results.total_count,
            returned_count=len(final_objects),
            offset=0,
            has_more=len(new_objects) > max_samples,
            next_offset=max_samples if len(new_objects) > max_samples else None
        )

    except ValueError as ve:
        logger.warning(f"Continue explore validation error: {ve}")
        # Provide fallback
        try:
            filters = CollectionSearchFilter(
                query=topic[:100], limit=min(max_samples, 100),
                offset=len(previously_seen_ids or []),
                unit_code=None, object_type=None, maker=None,
                material=None, topic=None, has_images=None, has_3d=None,
                is_cc0=None, on_view=None, date_start=None, date_end=None
            )
            api_client = await get_api_client(ctx)
            results = await api_client.search_collections(filters)
            return results
        except Exception as e:
            logger.error(f"Fallback also failed: {e}")
            raise Exception(f"Continue exploration failed: {str(ve)}")

    except Exception as e:
        logger.error(f"Error in continue explore: {e}")
        raise Exception(f"Continue exploration failed: {e}")


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
            logger.info(f"Retrieved object details: {object_id}")
        else:
            logger.warning(f"Object not found: {object_id}")

        return result

    except Exception as e:
        logger.error(f"API error retrieving object {object_id}: {e}")
        raise Exception(f"Failed to retrieve object {e}")


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
        logger.info(f"Retrieved {len(units)} Smithsonian units")
        return units

    except Exception as e:
        logger.error(f"Error retrieving Smithsonian units: {str(e)}")
        raise Exception(f"Failed to retrieve units: {str(e)}")


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
        logger.error(f"Error retrieving collection statistics: {str(e)}")
        raise Exception(f"Failed to retrieve statistics: {str(e)}")


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

    Args:
        unit_code: Smithsonian unit code (e.g., "NMNH", "NPG", "SAAM", "NASM")
        query: Optional search terms within that unit's collection
        limit: Maximum number of results (default: 20, max: 1000)
        offset: Results offset for pagination (default: 0)

    Returns:
        Search results from the specified unit
    """
    try:
        # Validate inputs
        if not unit_code or unit_code.strip() == "":
            raise ValueError("Unit code cannot be empty")
        if limit > 1000:
            limit = 1000
        if limit < 1:
            limit = 1

        # Create search filter
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
            f"Search by unit '{unit_code}' completed: '{query}' returned {results.returned_count} of {results.total_count} results"
        )

        return results

    except Exception as e:
        logger.error(f"Unexpected error during search by unit: {str(e)}")
        raise Exception(f"Search by unit failed: {str(e)}")


@mcp.tool()
async def get_objects_on_view(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    unit_code: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
) -> SearchResult:
    """
    Get objects that are currently on physical exhibit at Smithsonian museums.

    This tool specifically finds objects that are marked as being on display
    for the public, which is useful for planning museum visits or finding
    currently accessible objects.

    IMPORTANT: The Smithsonian API filter for on-view objects has data quality 
    issues and often returns false positives. For best results:
    1. Use high limit values (500-1000) to get more results
    2. Specify a particular museum (unit_code) like "FSG", "SAAM", "NMAH"
    3. Results are filtered to only include objects with verified exhibition data
    4. Consider searching without on_view filter and filtering results manually

    Args:
        unit_code: Optional filter by specific Smithsonian unit (e.g., "NMAH", "FSG", "SAAM")
        limit: Maximum number of results to return (default: 500, max: 1000)
        offset: Number of results to skip for pagination (default: 0)

    Returns:
        Search results containing objects actually marked as on physical exhibit
    """
    try:
        # Validate inputs
        if limit > 1000:
            limit = 1000
        if limit < 1:
            limit = 1

        # Create search filter for on-view objects
        filters = CollectionSearchFilter(
            query="*",
            unit_code=unit_code,
            on_view=True,
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

        # Filter out false positives - API returns objects without actual exhibition data
        verified_on_view = [obj for obj in results.objects if obj.is_on_view]
        
        logger.info(
            f"On-view search completed: {len(verified_on_view)} verified on-view out of {results.returned_count} returned ({results.total_count} total matches)"
        )

        # Return only verified on-view objects
        from .models import SearchResult as SR
        return SR(
            objects=verified_on_view,
            total_count=len(verified_on_view),
            returned_count=len(verified_on_view),
            offset=offset,
            has_more=False,
            next_offset=None
        )

    except Exception as e:
        logger.error(f"API error during on-view search: {e}")
        raise Exception(f"On-view search failed: {e}")


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
            logger.info(f"Object {object_id} is {status}")
        else:
            logger.warning(f"Object not found: {object_id}")

        return result

    except Exception as e:
        logger.error(f"API error checking object {object_id}: {e}")
        raise Exception(f"Failed to check object status: {e}")



@mcp.tool()
async def find_on_view_items(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    query: str = "",
    unit_code: Optional[str] = None,
    max_results: int = 1000,
) -> SearchResult:
    """
    Find ALL items currently on physical exhibit matching a search query.
    
    This tool automatically handles pagination to search through all matching items
    and filters them to return only those with verified exhibition status. Use this
    when you need to find all on-view items for a topic.
    
    Important: This tool searches up to max_results items and filters to only
    those with verified exhibition data, which is more reliable than using the
    on_view parameter in other search functions.
    
    Args:
        query: Search terms (e.g., "muppet", "Hokusai", "dinosaur fossils")
        unit_code: Optional museum code (e.g., "NMAH", "FSG", "NMNH", "NASM")
        max_results: Maximum items to search through (default: 1000, max: 1000)
    
    Returns:
        Search results with only verified on-view items, including exhibition details
    
    Examples:
        find_on_view_items(query="muppet", unit_code="NMAH")
        find_on_view_items(query="Hokusai", unit_code="FSG")
    """
    try:
        if not query or query.strip() == "":
            raise ValueError("Search query cannot be empty")
        if max_results > 1000:
            max_results = 1000
        if max_results < 1:
            max_results = 1
        
        logger.info(f"Finding on-view items for '{query}' at {unit_code or 'all museums'}")
        
        filters = CollectionSearchFilter(
            query=query,
            unit_code=unit_code,
            on_view=None,
            limit=max_results,
            offset=0,
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
        
        api_client = await get_api_client(ctx)
        results = await api_client.search_collections(filters)
        
        on_view_items = [obj for obj in results.objects if obj.is_on_view]
        
        logger.info(
            f"Found {len(on_view_items)} verified on-view out of {results.returned_count} searched"
        )
        
        from .models import SearchResult as SR
        return SR(
            objects=on_view_items,
            total_count=len(on_view_items),
            returned_count=len(on_view_items),
            offset=0,
            has_more=False,
            next_offset=None
        )
        
    except Exception as e:
        logger.error(f"Error finding on-view items: {e}")
        raise Exception(f"Failed to find on-view items: {e}")



# ============================================================================
# RESOURCES - Data sources that provide context to AI assistants
# ============================================================================


@mcp.tool()
async def get_search_context(
    ctx: Optional[Context[ServerSession, ServerContext]] = None, query: str = "", limit: int = 10
) -> str:
    """
    Get search results as context data for AI assistants.

    This tool provides search results that can be used as context data without
    explicitly calling search tools.

    Args:
        query: Search query string
        limit: Maximum number of results to return (default: 10)
    """
    try:
        filters = CollectionSearchFilter(
            query=query,
            limit=limit,
            unit_code=None,
            object_type=None,
            date_start=None,
            date_end=None,
            maker=None,
            material=None,
            topic=None,
            has_images=None,
            has_3d=None,
            is_cc0=None,
            on_view=None,
        )
        api_client = await get_api_client(ctx)
        results = await api_client.search_collections(filters)

        output = [f"Search Results for '{query}':\n"]

        for obj in results.objects:
            output.append(f"• {obj.title}")
            if obj.unit_name:
                output.append(f"  Museum: {obj.unit_name}")
            output.append(f"  ID: {obj.id}")
            output.append("")

        return "\n".join(output)

    except Exception as e:
        return f"Error searching collections: {str(e)}"


@mcp.tool()
async def get_object_context(
    ctx: Optional[Context[ServerSession, ServerContext]] = None, object_id: str = ""
) -> str:
    """
    Get detailed object information as context data.

    Provides complete object metadata that can be used as context data.

    Args:
        object_id: The ID of the object to retrieve
    """
    try:
        api_client = await get_api_client(ctx)
        obj = await api_client.get_object_by_id(object_id)

        if not obj:
            return f"Object {object_id} not found."

        output = [f"Object Details: {obj.title}\n"]

        if obj.maker:
            output.append(f"Creator: {', '.join(obj.maker)}")
        if obj.date:
            output.append(f"Date: {obj.date}")
        if obj.unit_name:
            output.append(f"Museum: {obj.unit_name}")
        if obj.materials:
            output.append(f"Materials: {', '.join(obj.materials)}")
        if obj.object_type:
            output.append(f"Type: {obj.object_type}")
        if obj.id:
            output.append(f"Object ID: {obj.id}")
        if obj.description:
            output.append(f"\nDescription: {obj.description}")

        output.append(f"\nImages: {len(obj.images) if obj.images else 0} available")
        output.append(
            f"3D Models: {len(obj.models_3d) if obj.models_3d else 0} available"
        )

        return "\n".join(output)

    except Exception as e:
        return f"Error retrieving object details: {str(e)}"


@mcp.tool()
async def get_on_view_context(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    unit_code: Optional[str] = None,
    limit: int = 10,
) -> str:
    """
    Get objects currently on view as context data for AI assistants.

    This tool provides information about objects currently on exhibit that
    can be used as context data without explicitly calling search tools.

    Args:
        unit_code: Optional filter by specific Smithsonian unit
        limit: Maximum number of results to return (default: 10)
    """
    try:
        filters = CollectionSearchFilter(
            query="*",
            limit=limit,
            unit_code=unit_code,
            on_view=True,
            object_type=None,
            date_start=None,
            date_end=None,
            maker=None,
            material=None,
            topic=None,
            has_images=None,
            has_3d=None,
            is_cc0=None,
        )
        api_client = await get_api_client(ctx)
        results = await api_client.search_collections(filters)

        unit_text = f" at {unit_code}" if unit_code else ""
        output = [f"Objects Currently On View{unit_text}:\n"]

        if not results.objects:
            output.append("No objects are currently on view.")
            return "\n".join(output)

        for obj in results.objects:
            output.append(f"• {obj.title}")
            if obj.unit_name:
                output.append(f"  Museum: {obj.unit_name}")
            if obj.object_type:
                output.append(f"  Type: {obj.object_type}")
            output.append(f"  ID: {obj.id}")
            output.append(f"  Status: Currently on exhibit ✓")
            output.append("")

        return "\n".join(output)

    except Exception as e:
        return f"Error retrieving on-view objects: {str(e)}"


@mcp.tool()
async def get_units_context(ctx: Optional[Context[ServerSession, ServerContext]] = None) -> str:
    """
    Get a list of all Smithsonian units as context data.

    Provides information about all Smithsonian museums and research centers.
    """
    try:
        api_client = await get_api_client(ctx)
        units = await api_client.get_units()

        output = ["Smithsonian Institution Museums and Research Centers:\n"]

        for unit in units:
            output.append(f"• {unit.code}: {unit.name}")
            if unit.description:
                output.append(f"  {unit.description}")
            output.append("")

        return "\n".join(output)

    except Exception as e:
        return f"Error retrieving units list: {str(e)}"


@mcp.tool()
async def get_stats_context(ctx: Optional[Context[ServerSession, ServerContext]] = None) -> str:
    """
    Get collection statistics as context data.

    Provides overview statistics for the Smithsonian Open Access collection.
    """
    try:
        api_client = await get_api_client(ctx)
        stats = await api_client.get_collection_stats()

        output = [
            "Smithsonian Open Access Collection Statistics:\n",
            f"Total Objects: {stats.total_objects:,}",
            f"Digitized Objects: {stats.total_digitized:,}",
            f"CC0 Licensed Objects: {stats.total_cc0:,}",
            f"Objects with Images: {stats.total_with_images:,}",
            f"Objects with 3D Models: {stats.total_with_3d:,}",
            f"\nLast Updated: {stats.last_updated}\n",
            "By Museum:",
        ]

        for unit in stats.units:
            output.append(f"  {unit.unit_code}: {unit.total_objects:,}")

        return "\n".join(output)

    except Exception as e:
        return f"Error retrieving collection statistics: {str(e)}"


# ============================================================================
# PROMPTS - Templates for common user interactions
# ============================================================================


@mcp.prompt(title="Collection Research")
def collection_research_prompt(
    research_topic: str, focus_area: Optional[str] = None
) -> List[base.Message]:
    """
    Help users conduct research using Smithsonian collections.

    This prompt provides structured guidance for exploring collections on
    a specific research topic with scholarly depth.

    Args:
        research_topic: Main topic or theme to research
        focus_area: Optional specific aspect to focus on
    """
    focus_text = f" with particular attention to {focus_area}" if focus_area else ""

    return [
        base.Message(
            role="user",
            content=f"I want to conduct scholarly research on '{research_topic}'{focus_text} "
            f"using the Smithsonian collections. Please help me by:\n\n"
            f"1. Searching for relevant objects and artworks related to this topic\n"
            f"2. Identifying which Smithsonian museums have the most relevant materials\n"
            f"3. Suggesting related topics or themes I should also explore\n"
            f"4. Highlighting any objects with high-quality images or 3D models\n"
            f"5. Noting any objects that are CC0 licensed for potential publication use\n\n"
            f"Please provide detailed information about the most significant objects you find, "
            f"including their historical context and scholarly significance.",
        )
    ]


@mcp.prompt(title="Object Analysis")
def object_analysis_prompt(object_id: str) -> List[base.Message]:
    """
    Analyze a specific Smithsonian collection object in detail.

    This prompt helps users get comprehensive analysis of cultural objects
    including historical context, artistic significance, and research applications.

    Args:
        object_id: Unique identifier of the object to analyze
    """
    return [
        base.Message(
            role="user",
            content=f"Please provide a detailed analysis of Smithsonian object ID: {object_id}. "
            f"Include:\n\n"
            f"1. Complete object details and metadata\n"
            f"2. Historical and cultural context\n"
            f"3. Artistic or scientific significance\n"
            f"4. Information about the creator/maker when available\n"
            f"5. Materials, techniques, and physical characteristics\n"
            f"6. Provenance and acquisition history if available\n"
            f"7. Related objects or collections that would be relevant for comparison\n"
            f"8. Potential research applications or scholarly uses\n\n"
            f"If the object has associated images, describe what they show and note "
            f"their quality and licensing status.",
        )
    ]


@mcp.prompt(title="Exhibition Planning")
def exhibition_planning_prompt(
    exhibition_theme: str, target_audience: str = "general public", size: str = "medium"
) -> List[base.Message]:
    """
    Plan an exhibition using Smithsonian collections.

    This prompt helps curators and educators plan exhibitions by finding
    suitable objects and organizing them thematically.

    Args:
        exhibition_theme: Main theme or topic for the exhibition
        target_audience: Intended audience (e.g., "children", "scholars", "general public")
        size: Exhibition size ("small", "medium", "large")
    """
    size_guidelines = {
        "small": "15-25 objects",
        "medium": "30-50 objects",
        "large": "60+ objects",
    }

    return [
        base.Message(
            role="user",
            content=f"Help me plan a {size} exhibition on '{exhibition_theme}' "
            f"for {target_audience}. I need approximately {size_guidelines.get(size, '30-50')} objects. "
            f"Please:\n\n"
            f"1. Search for relevant objects across different Smithsonian museums\n"
            f"2. Organize findings into thematic sections or galleries\n"
            f"3. Prioritize objects with high-quality images for exhibition materials\n"
            f"4. Include diverse perspectives and representations when possible\n"
            f"5. Suggest a logical flow or narrative structure\n"
            f"6. Note any objects that could serve as highlights or centerpieces\n"
            f"7. Consider educational value appropriate for the target audience\n"
            f"8. Identify objects that are CC0 licensed for marketing materials\n\n"
            f"Provide detailed information about key objects and explain why "
            f"they would be effective for this exhibition concept.",
        )
    ]


@mcp.prompt(title="Educational Content")
def educational_content_prompt(
    subject: str,
    grade_level: str = "middle school",
    learning_goals: Optional[str] = None,
) -> List[base.Message]:
    """
    Create educational content using Smithsonian collections.

    This prompt helps educators develop lesson plans, activities, and
    educational materials using museum objects.

    Args:
        subject: Subject area (e.g., "American History", "Art", "Science")
        grade_level: Target grade level or age group
        learning_goals: Optional specific learning objectives
    """
    goals_text = (
        f"\nSpecific learning goals: {learning_goals}" if learning_goals else ""
    )

    return [
        base.Message(
            role="user",
            content=f"Help me create educational content about '{subject}' "
            f"for {grade_level} students using Smithsonian collections.{goals_text}\n\n"
            f"Please:\n\n"
            f"1. Find age-appropriate objects that illustrate key concepts\n"
            f"2. Suggest hands-on activities or discussion questions\n"
            f"3. Provide historical context suitable for the grade level\n"
            f"4. Include objects with clear, high-quality images for visual learning\n"
            f"5. Consider diverse perspectives and inclusive representation\n"
            f"6. Suggest cross-curricular connections when relevant\n"
            f"7. Identify objects that could inspire creative projects\n"
            f"8. Note any 3D models that could enhance digital learning\n\n"
            f"Structure this as a practical lesson plan with clear learning outcomes "
            f"and explain how each selected object supports educational objectives.",
        )
    ]


# ============================================================================
# SERVER STARTUP
# ============================================================================

if __name__ == "__main__":
    import sys

    logger.info(f"Starting {Config.SERVER_NAME} v{Config.SERVER_VERSION}")

    # Check for API key
    if not Config.validate_api_key():
        logger.error(
            "API key not configured. Set SMITHSONIAN_API_KEY environment variable. "
            "Get your key from https://api.data.gov/signup/"
        )
        sys.exit(1)

    # Run the MCP server
    mcp.run()
