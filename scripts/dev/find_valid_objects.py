#!/usr/bin/env python3
"""
Find some valid object IDs from the Smithsonian API for testing.
"""
# TODO: FIX OR REMOVE FROM GIT TRACKING
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smithsonian_mcp.api_client import create_client
from smithsonian_mcp.config import Config


async def find_valid_objects():
    """Find some valid object IDs for testing."""
    print("Searching for valid Smithsonian objects...")

    try:
        api_client = await create_client()

        # Search for some objects
        from smithsonian_mcp.models import CollectionSearchFilter

        filters = CollectionSearchFilter(
            query="painting",
            limit=5,
            unit_code="NPG",  # National Portrait Gallery
            object_type=None,
            date_start=None,
            date_end=None,
            maker=None,
            material=None,
            topic=None,
            has_images=None,  # Remove image filter
            is_cc0=None,
            on_view=None,
        )

        results = await api_client.search_collections(filters)

        print(f"\nFound {len(results.objects)} objects:")
        for obj in results.objects:
            print(f"• {obj.title}")
            print(f"  ID: {obj.id}")
            print(f"  Museum: {obj.unit_name}")
            print(f"  Images: {len(obj.images) if obj.images else 0}")

            # Debug: Get raw content to see full structure
            try:
                raw_content = await api_client._make_request(f"content/{obj.id}")
                content = raw_content.get("response", {}).get("content", {})
                descriptive_non_repeating = content.get("descriptiveNonRepeating", {})
                online_media = descriptive_non_repeating.get("online_media", {})
                print(f"  Raw online_media: {online_media}")
                print(f"  Content keys: {list(content.keys())}")
                print(f"  DescriptiveNonRepeating keys: {list(descriptive_non_repeating.keys())}")
                indexed_structured = content.get("indexedStructured", {})
                print(f"  IndexedStructured keys: {list(indexed_structured.keys())}")
                # Check if images are in indexedStructured
                if "online_media" in indexed_structured:
                    print(f"  IndexedStructured online_media: {indexed_structured['online_media']}")
            except Exception as e:
                print(f"  Error getting raw content: {e}")
            print()

        return results.objects[:3]  # Return first 3 for testing

    except Exception as e:
        print(f"Error: {e}")
        return []


async def main():
    """Main function."""
    if not Config.validate_api_key():
        print("Please set SMITHSONIAN_API_KEY environment variable")
        return 1

    objects = await find_valid_objects()

    if objects:
        print("Valid object IDs for testing:")
        for obj in objects:
            print(f"  {obj.id}")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
