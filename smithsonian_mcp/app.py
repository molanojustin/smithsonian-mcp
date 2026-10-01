"""
Smithsonian Open Access MCP Application

Creates the FastMCP server and registers its tools, resources and prompts, so
``from smithsonian_mcp.app import mcp`` is a complete server.
"""

from fastmcp import FastMCP

from . import __version__
from .config import Config
from .prompts import register_prompts
from .resources import register_resources
from .server import server_lifespan
from .tools import register_tools

WEBSITE_URL = "https://github.com/molanojustin/smithsonian-mcp"

INSTRUCTIONS = """\
Search the Smithsonian Open Access collections: more than 14 million \
searchable records from 40+ Smithsonian museums, archives and libraries, \
covering art, history, natural history specimens, archival and library items.

- search_objects finds objects; get_object returns the full record and images \
for an id from any result. explore_topic returns a varied random sample for \
open-ended browsing. list_museums and get_collection_stats give units and counts.
- Pass museum as a name or unit code ("American History" or "NMAH"); results \
report the code that was used.
- Every word of query must match. Use 1-4 distinctive keywords, OR between \
alternatives ("muppet OR henson"), quotes for phrases, and maker for people. \
Leave out stop-words and questions.
- on_view=true returns objects on physical exhibit now, with exhibition titles \
and locations. Natural History (NMNH) records have no exhibit data.
- Year filters match by decade.
- Link objects with web_url from the results. Never construct Smithsonian URLs \
by hand.
- When a result includes a note, it explains empty or partial results.
"""


def create_app() -> FastMCP:
    """
    Create the FastMCP server with all tools, resources and prompts.

    Returns:
        FastMCP: The configured server.
    """
    server = FastMCP(
        Config.SERVER_NAME,
        instructions=INSTRUCTIONS,
        version=__version__,
        website_url=WEBSITE_URL,
        lifespan=server_lifespan,
        mask_error_details=True,
    )
    register_tools(server)
    register_resources(server)
    register_prompts(server)
    return server


mcp = create_app()
