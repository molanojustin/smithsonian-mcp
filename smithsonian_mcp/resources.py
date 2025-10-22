"Smithsonian Open Access MCP Resources"

import logging
from typing import Optional

from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession

from .app import mcp
from .context import ServerContext, get_api_client
from .models import CollectionSearchFilter, APIError
from .constants import MUSEUM_MAP, VALID_MUSEUM_CODES

logger = logging.getLogger(__name__)


def _format_optional_number(value: Optional[int]) -> str:
    """Format optional integer values for human-readable stats output."""
    return f"{value:,}" if value is not None else "Unavailable"

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
        # pylint: disable=duplicate-code
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

    except (APIError, ValueError) as e:
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

        return "\n".join(output)

    except (APIError, ValueError) as e:
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
        unit_code: Optional filter by Smithsonian unit code (e.g., "NMAH", "HMSG") or museum name
            (e.g., "hirshhorn", "natural history")
        limit: Maximum number of results to return (default: 10)
    """
    try:
        # Map museum names to codes
        museum_code = None
        if unit_code:
            unit_code_lower = unit_code.lower().strip()
            if unit_code_lower in MUSEUM_MAP:
                museum_code = MUSEUM_MAP[unit_code_lower]
            elif unit_code_upper := unit_code.upper():
                if unit_code_upper in VALID_MUSEUM_CODES:
                    museum_code = unit_code_upper

        # Use reliable approach: search broadly then filter locally
        # pylint: disable=duplicate-code
        filters = CollectionSearchFilter(
            query="*",
            limit=min(
                limit * 5, 1000
            ),  # Search more broadly to get verified on-view items
            unit_code=museum_code,
            on_view=None,  # Don't use unreliable API filter
            object_type=None,
            date_start=None,
            date_end=None,
            maker=None,
            material=None,
            topic=None,
            has_images=None,
            is_cc0=None,
        )
        api_client = await get_api_client(ctx)
        results = await api_client.search_collections(filters)

        # Filter for verified on-view objects
        verified_on_view = [obj for obj in results.objects if obj.is_on_view][:limit]

        if unit_code:
            output = [f"Objects Currently On View at {unit_code}:\n"]
        else:
            output = ["Objects Currently On View:\n"]

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
            output.append("  Status: Currently on exhibit ✓")
            output.append("")

        return "\n".join(output)

    except (APIError, ValueError) as e:
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

    except (APIError, ValueError) as e:
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
            f"Digitized Objects: {_format_optional_number(stats.total_digitized)}",
            f"CC0 Licensed Objects: {_format_optional_number(stats.total_cc0)}",
            f"Objects with Images (est.): {_format_optional_number(stats.total_with_images)}",

            f"\nLast Updated: {stats.last_updated}\n",
            "By Museum (estimates using overall collection proportions):",
            "Note: Smithsonian API doesn't provide per-museum image statistics.",
            "All museums show the same percentage due to API limitations.",
        ]

        for unit in stats.units:
            output.append(
                f"  {unit.unit_code}: {_format_optional_number(unit.total_objects)} total, "
                f"{_format_optional_number(unit.objects_with_images)} with images (est.)"
            )

        return "\n".join(output)

    except (APIError, ValueError) as e:
        return f"Error retrieving collection statistics: {str(e)}"
