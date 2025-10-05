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


async def get_api_client(ctx: Optional[Context[ServerSession, ServerContext]] = None) -> SmithsonianAPIClient:
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
    ctx: Context[ServerSession, ServerContext],
    query: str,
    unit_code: Optional[str] = None,
    object_type: Optional[str] = None,
    maker: Optional[str] = None,
    material: Optional[str] = None,
    topic: Optional[str] = None,
    has_images: Optional[bool] = None,
    has_3d: Optional[bool] = None,
    is_cc0: Optional[bool] = None,
    limit: int = 20,
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
        limit: Maximum number of results to return (default: 20, max: 100)
        offset: Number of results to skip for pagination (default: 0)

    Returns:
        Search results including objects, total count, and pagination info
    """
    try:
        # Validate inputs
        if limit > 100:
            limit = 100
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
async def get_object_details(
    ctx: Context[ServerSession, ServerContext], object_id: str
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
    ctx: Context[ServerSession, ServerContext],
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
    ctx: Context[ServerSession, ServerContext],
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
    ctx: Context[ServerSession, ServerContext],
    unit_code: str,
    query: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> SearchResult:
    """
    Search collections within a specific Smithsonian museum or unit.

    This tool focuses searches on a particular museum's collection, useful when
    you want to explore what's available at a specific institution.

    Args:
        unit_code: Smithsonian unit code (e.g., "NMNH", "NPG", "SAAM", "NASM")
        query: Optional search terms within that unit's collection
        limit: Maximum number of results (default: 20, max: 100)
        offset: Results offset for pagination (default: 0)

    Returns:
        Search results from the specified unit
    """
    try:
        # Validate inputs
        if limit > 100:
            limit = 100
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


# ============================================================================
# RESOURCES - Data sources that provide context to AI assistants
# ============================================================================


@mcp.tool()
async def get_search_context(
    ctx: Context[ServerSession, ServerContext], query: str, limit: int = 10
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
    ctx: Context[ServerSession, ServerContext], object_id: str
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
async def get_units_context(ctx: Context[ServerSession, ServerContext]) -> str:
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
async def get_stats_context(ctx: Context[ServerSession, ServerContext]) -> str:
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
