"""
Test API Connection and Basic Functionality

This script checks the Smithsonian API key and connection by calling the MCP
server's tools in process, without an MCP client application. It makes about
six API requests.
"""

import asyncio
import json
import logging
from pathlib import Path
import random
import sys
from typing import Any, Dict, Optional

# Add parent directory to path to import smithsonian_mcp
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastmcp import Client  # noqa: E402
from fastmcp.exceptions import ToolError  # noqa: E402

from smithsonian_mcp import Config, mcp  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Keep httpx quiet; it logs every request URL at INFO
logging.getLogger("httpx").setLevel(logging.WARNING)


async def call(
    client: Client, tool: str, arguments: Optional[Dict[str, Any]] = None
) -> Any:
    """
    Call a tool and return its structured result.

    Args:
        client: Connected MCP client.
        tool: Tool name.
        arguments: Tool arguments.

    Returns:
        Any: The structured result (a list result is unwrapped).
    """
    result = await client.call_tool(tool, arguments or {})
    data = result.structured_content or {}
    return data.get("result", data) if isinstance(data, dict) else data


async def test_api_connection() -> bool:
    """
    Test API connectivity through the MCP tools.

    Returns:
        bool: True if every check passed.
    """

    # Check API key
    if not Config.validate_api_key():
        print("Error: API key not configured.")
        print()
        print("Please set your API key:")
        print("1. Get a key from https://api.data.gov/signup/")
        print("2. Set environment variable: SMITHSONIAN_API_KEY=your_key")
        print("3. Or create .env file with: SMITHSONIAN_API_KEY=your_key")
        return False

    print("Testing Smithsonian MCP Server API Connection")
    print("=" * 60)
    print()

    try:
        async with Client(mcp) as client:
            tools = await client.list_tools()
            print(f"Server exposes {len(tools)} tools:")
            print("   " + ", ".join(tool.name for tool in tools))
            print()

            # Test 1: Smithsonian units
            print("Test 1: list_museums...")
            museums = await call(client, "list_museums")
            print(f"OK: Found {len(museums)} Smithsonian units")
            for museum in museums[:3]:
                print(f"   - {museum['code']}: {museum['name']}")
            print()

            # Test 2: Basic search
            print("Test 2: search_objects(query='pottery', limit=5)...")
            results = await call(
                client, "search_objects", {"query": "pottery", "limit": 5}
            )
            print(
                f"OK: Search returned {results['returned']} of "
                f"{results['total_count']} results"
            )
            for i, obj in enumerate(results["objects"], 1):
                print(f"   {i}. {obj['title']}")
                if obj.get("museum_name"):
                    print(f"      Museum: {obj['museum_name']}")
            print()

            # Test 3: Object details (if we have results)
            if results["objects"]:
                print("Test 3: get_object...")
                details = await call(
                    client, "get_object", {"object_id": results["objects"][0]["id"]}
                )
                print(f"OK: Retrieved detailed info for: {details['title']}")
                print(f"   Images: {len(details.get('images', []))} listed")
                print(f"   Page: {details.get('web_url', 'none')}")
                print()

            # Test 4: Collection statistics (3 random museums)
            print("Test 4: get_collection_stats...")
            stats = await call(client, "get_collection_stats")
            print(f"OK: {stats['total_objects']:,} records in total")
            sample = random.sample(stats["museums"], min(3, len(stats["museums"])))
            for museum in sample:
                print(f"   {museum['name']}: {museum['object_count']:,} records")
            print()

        print("All tests passed! API connection is working.")
        print()
        print("Next steps:")
        print("1. Configure Claude Desktop with the MCP server")
        print("2. Test Claude Desktop integration")
        print("3. Try VS Code integration with the workspace")
        return True

    except (ToolError, KeyError, json.JSONDecodeError) as e:
        print(f"Error: Test failed: {e}")
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Error: Test failed: {type(e).__name__}: {e}")

    print()
    print("Troubleshooting:")
    print("1. Check your API key is valid")
    print("2. Verify internet connection")
    print("3. Check if api.data.gov is accessible")
    return False


if __name__ == "__main__":
    success = asyncio.run(test_api_connection())
    sys.exit(0 if success else 1)
