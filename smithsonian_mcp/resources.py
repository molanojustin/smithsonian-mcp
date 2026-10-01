"""
MCP resources for the Smithsonian Open Access collections.

Resources return the same data as the list_museums and get_object tools, as JSON,
for clients that attach context through resources rather than tool calls.
"""

import json

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError, ToolError

from . import tools
from .tools import summary_of


async def museums_resource() -> str:
    """
    Smithsonian units with codes, object counts and accepted name aliases.

    Returns:
        str: JSON array, the same data as the list_museums tool.
    """
    try:
        museums = await tools.list_museums()
    except ToolError as exc:
        raise ResourceError(str(exc)) from exc
    return json.dumps([museum.model_dump(mode="json") for museum in museums])


async def object_resource(object_id: str) -> str:
    """
    Full record of one collection object.

    Args:
        object_id: Object id from search results, or a record id.

    Returns:
        str: JSON object, the same data as the get_object tool.
    """
    try:
        details = await tools.get_object(object_id)
    except ToolError as exc:
        raise ResourceError(str(exc)) from exc
    return details.model_dump_json()


def register_resources(server: FastMCP) -> None:
    """
    Register the museum list and object record resources on a server.

    Args:
        server: The FastMCP server.
    """
    server.resource(
        "smithsonian://museums",
        name="museums",
        title="Smithsonian Museums",
        description=summary_of(museums_resource),
        mime_type="application/json",
    )(museums_resource)
    server.resource(
        "smithsonian://objects/{object_id}",
        name="object",
        title="Smithsonian Object",
        description=summary_of(object_resource),
        mime_type="application/json",
    )(object_resource)
