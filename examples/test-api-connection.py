"""
Test API Connection and Basic Functionality

This script tests the Smithsonian MCP Server API connection and basic functionality
without requiring the full MCP server setup.
"""

import asyncio
import logging
from pathlib import Path
import sys

# Add parent directory to path to import smithsonian_mcp
sys.path.insert(0, str(Path(__file__).parent.parent))

from smithsonian_mcp import create_client, Config, CollectionSearchFilter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setting httpx logging to WARNING to reduce key leaks
logging.getLogger("httpx").setLevel(logging.WARNING)


async def test_api_connection():
    """Test basic API connectivity and functionality."""

    # Check API key
    if not Config.validate_api_key():
        print("❌ API key not configured!")
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
        async with await create_client() as client:

            # Test 1: Get Smithsonian units
            print("Test 1: Getting Smithsonian units...")
            units = await client.get_units()
            print(f"✅ Found {len(units)} Smithsonian units")
            for unit in units[:3]:  # Show first 3
                print(f"   • {unit.code}: {unit.name}")
            print()

            # Test 2: Basic search
            print("Test 2: Basic collection search...")
            filters = CollectionSearchFilter(
                query="pottery",
                limit=5,
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
                offset=0,
                on_view=None,
            )
            results = await client.search_collections(filters)
            print(
                f"✅ Search returned {results.returned_count} of {results.total_count} results"
            )

            for i, obj in enumerate(results.objects, 1):
                print(f"   {i}. {obj.title}")
                if obj.unit_name:
                    print(f"      Museum: {obj.unit_name}")
            print()

            # Test 3: Object details (if we have results)
            if results.objects:
                print("Test 3: Getting object details...")
                first_obj = results.objects[0]
                detailed_obj = await client.get_object_by_id(first_obj.id)

                if detailed_obj:
                    print(f"✅ Retrieved detailed info for: {detailed_obj.title}")
                    print(
                        f"   Images: {len(detailed_obj.images) if detailed_obj.images else 0} available"
                    )
                    print(
                        f"   3D Models: {len(detailed_obj.models_3d) if detailed_obj.models_3d else 0} available"
                    )
                else:
                    print("Warning: Object details not found")
                print()

            # Test 4: Collection statistics
            print("Test 4: Getting collection statistics...")
            stats = await client.get_collection_stats()
            print(f"✅ Collection statistics:")
            print(f"   Total objects: {stats.total_objects:,}")
            print(
                f"   CC0 licensed: {stats.total_cc0:,}"
                if stats.total_cc0
                else "   CC0 licensed: Not available from API"
            )
            print(
                f"   With CC0 media: {stats.total_with_images:,}"
                if stats.total_with_images
                else "   With CC0 media: Not available from API"
            )
            print()

        print("All tests passed! API connection is working.")
        print()
        print("Next steps:")
        print("1. Configure Claude Desktop with the MCP server")
        print("2. Test Claude Desktop integration")
        print("3. Try VS Code integration with the workspace")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        print()
        print("Troubleshooting:")
        print("1. Check your API key is valid")
        print("2. Verify internet connection")
        print("3. Check if api.data.gov is accessible")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_api_connection())
    sys.exit(0 if success else 1)
