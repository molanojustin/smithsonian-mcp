#!/usr/bin/env python3
"""
Quick collection of object types for museums with Open Access objects.
"""

import asyncio
import sys
import os
from collections import defaultdict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from smithsonian_mcp.api_client import create_client
from smithsonian_mcp.config import Config
from smithsonian_mcp.models import CollectionSearchFilter


async def collect_types_quick():
    """Quick collection using existing get_museum_collection_types function."""
    print("Using existing get_museum_collection_types function...")
    
    try:
        api_client = await create_client()
        
        # Import the existing function
        from smithsonian_mcp.tools import get_museum_collection_types
        
        # Get types for all museums (with small sample)
        results = await get_museum_collection_types(
            unit_code=None,  # All museums
            sample_size=50,  # Small sample for speed
            use_cache=False  # Force fresh sampling
        )
        
        # Convert to dict format
        museum_types = {}
        for result in results:
            if result.available_object_types:
                museum_types[result.museum_code] = result.available_object_types
        
        print(f"\nCollected types for {len(museum_types)} museums")
        
        # Show summary
        for code, types in sorted(museum_types.items()):
            print(f"  {code}: {len(types)} types")
        
        # Generate update for museum_data.py
        print(f"\n" + "=" * 50)
        print("UPDATE FOR museum_data.py:")
        print("=" * 50)
        
        print("MUSEUM_OBJECT_TYPES: Dict[str, List[str]] = {")
        for code, types in sorted(museum_types.items()):
            print(f'    "{code}": {types},')
        print("    # Note: AAA has no Open Access objects")
        print("}")
        
        return museum_types
        
    except Exception as e:
        print(f"Error: {e}")
        return {}


async def main():
    if not Config.validate_api_key():
        print("Please set SMITHSONIAN_API_KEY environment variable")
        return 1
    
    await collect_types_quick()
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
