#!/usr/bin/env python3
"""
Targeted search for additional museum object types.
Focus on museums most likely to have additional types.
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


async def targeted_sample_museum(api_client, museum_code, sample_size=300):
    """Sample a museum with a large, diverse sample to find additional object types."""
    print(f"  Targeted sampling {museum_code} with {sample_size} objects...")
    
    try:
        # Single large sample to get maximum diversity
        filters = CollectionSearchFilter(
            query="*",
            unit_code=museum_code,
            limit=sample_size,
            offset=0,
            object_type=None,
            maker=None,
            material=None,
            topic=None,
            has_images=None,
            is_cc0=None,
            on_view=None,
            date_start=None,
            date_end=None,
        )
        
        results = await api_client.search_collections(filters)
        
        # Collect object types
        object_types = set()
        for obj in results.objects:
            if obj.object_type:
                object_types.add(obj.object_type.lower().strip())
        
        sorted_types = sorted(list(object_types))
        print(f"    Found {len(sorted_types)} unique object types from {len(results.objects)} objects")
        
        return sorted_types
        
    except Exception as e:
        print(f"    Error sampling {museum_code}: {e}")
        return []


async def targeted_search():
    """Targeted search for additional object types."""
    print("Targeted Smithsonian Museum Object Type Search")
    print("=" * 50)
    
    try:
        api_client = await create_client()
        
        # Focus on museums with largest collections that might have more diverse types
        priority_museums = [
            "NMAH",    # Largest collection
            "NMAI",    # Large and diverse
            "NMAAHC",  # Large and diverse
            "CHNDM",   # Design museum with many types
            "SIA",     # Archives with many types
            "NASM",    # Technical objects
        ]
        
        # Load existing types
        from smithsonian_mcp.museum_data import MUSEUM_OBJECT_TYPES
        existing_types = MUSEUM_OBJECT_TYPES.copy()
        
        results = {}
        new_types_found = defaultdict(list)
        
        for museum in priority_museums:
            print(f"\nSampling {museum}...")
            types = await targeted_sample_museum(api_client, museum, sample_size=500)
            
            # Merge with existing types
            existing = set(existing_types.get(museum, []))
            combined = existing.union(set(types))
            results[museum] = sorted(list(combined))
            
            # Track new types
            new_types = set(types) - existing
            if new_types:
                new_types_found[museum] = sorted(list(new_types))
                print(f"  ✓ Found {len(new_types)} new types:")
                for obj_type in sorted(new_types):
                    print(f"    - {obj_type}")
            else:
                print(f"  ✓ No new types found ({len(types)} total types)")
        
        # Summary
        print(f"\n" + "=" * 50)
        print("TARGETED SEARCH RESULTS")
        print("=" * 50)
        
        total_new_types = sum(len(types) for types in new_types_found.values())
        museums_with_new_types = len(new_types_found)
        
        print(f"New object types discovered: {total_new_types}")
        print(f"Museums with new types: {museums_with_new_types}")
        
        if new_types_found:
            print(f"\nAll new types by museum:")
            for museum, types in new_types_found.items():
                print(f"  {museum}: {len(types)} new types")
        
        # Update MUSEUM_OBJECT_TYPES if new types found
        if new_types_found:
            print(f"\n" + "=" * 50)
            print("UPDATING MUSEUM_OBJECT_TYPES")
            print("=" * 50)
            
            # Generate updated dict
            updated_types = MUSEUM_OBJECT_TYPES.copy()
            for museum, new_types in new_types_found.items():
                if museum in updated_types:
                    updated_types[museum] = sorted(list(set(updated_types[museum] + new_types)))
            
            # Save to file
            with open("updated_museum_types.py", "w") as f:
                f.write("# Updated museum object types with additional discoveries\n\n")
                f.write("MUSEUM_OBJECT_TYPES = {\n")
                for museum, types in sorted(updated_types.items()):
                    f.write(f'    "{museum}": {types},\n')
                f.write("    # Note: AAA has no Open Access objects\n")
                f.write("}\n\n")
                
                f.write("NEW_TYPES_ADDED = {\n")
                for museum, types in sorted(new_types_found.items()):
                    f.write(f'    "{museum}": {types},\n')
                f.write("}\n")
            
            print("Updated types saved to updated_museum_types.py")
            
            return updated_types, new_types_found
        else:
            print("\nNo new object types found in this search.")
            return MUSEUM_OBJECT_TYPES, {}
        
    except Exception as e:
        print(f"Error: {e}")
        return {}, {}


async def main():
    """Main function."""
    if not Config.validate_api_key():
        print("Please set SMITHSONIAN_API_KEY environment variable")
        return 1
    
    updated_types, new_types = await targeted_search()
    
    if new_types:
        print(f"\nFound new types for {len(new_types)} museums. Update museum_data.py to include them.")
    else:
        print("\nNo additional object types found.")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
