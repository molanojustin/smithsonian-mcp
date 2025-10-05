#!/usr/bin/env python3
"""
Find some valid object IDs from the Smithsonian API for testing.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smithsonian_mcp.server import get_api_client
from smithsonian_mcp.config import Config


async def find_valid_objects():
    """Find some valid object IDs for testing."""
    print("Searching for valid Smithsonian objects...")
    
    try:
        api_client = await get_api_client()
        
        # Search for some objects
        from smithsonian_mcp.models import CollectionSearchFilter
        
        filters = CollectionSearchFilter(
            query="painting",
            limit=5,
            unit_code=None,
            object_type=None,
            date_start=None,
            date_end=None,
            maker=None,
            material=None,
            topic=None,
            has_images=True,
            has_3d=None,
            is_cc0=None
        )
        
        results = await api_client.search_collections(filters)
        
        print(f"\nFound {len(results.objects)} objects:")
        for obj in results.objects:
            print(f"• {obj.title}")
            print(f"  ID: {obj.id}")
            print(f"  Museum: {obj.unit_name}")
            print(f"  Images: {len(obj.images) if obj.images else 0}")
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