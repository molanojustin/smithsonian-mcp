"Smithsonian Open Access MCP Resources"

import logging
from typing import Optional

from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession

from .app import mcp
from .context import ServerContext, get_api_client
from .models import CollectionSearchFilter

logger = logging.getLogger(__name__)


@mcp.tool()
async def get_search_context(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
    query: str = "",
    limit: int = 10,
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
                output.append(f"  Museum: %s" % obj.unit_name)
            output.append(f"  ID: %s" % obj.id)
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
    The results are filtered to include only verified on-view objects.

    Args:
        unit_code: Optional filter by specific Smithsonian unit
        limit: Maximum number of results to return (default: 10)
    """
    try:
        # Use reliable approach: search broadly then filter locally
        filters = CollectionSearchFilter(
            query="*",
            limit=min(
                limit * 5,
                1000
            ),  # Search more broadly to get verified on-view items
            unit_code=unit_code,
            on_view=None,  # Don't use unreliable API filter
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

        # Filter for verified on-view objects
        verified_on_view = [obj for obj in results.objects if obj.is_on_view][:limit]

        unit_text = f" at {unit_code}" if unit_code else ""
        output = [f"Objects Currently On View{unit_text}:\n"]

        if not verified_on_view:
            output.append("No objects are currently on view.")
            return "\n".join(output)

        for obj in verified_on_view:
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
async def get_units_context(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
) -> str:
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
async def get_stats_context(
    ctx: Optional[Context[ServerSession, ServerContext]] = None,
) -> str:
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
