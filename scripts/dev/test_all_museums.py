#!/usr/bin/env python3
"""
Test all Smithsonian museums to see which ones have Open Access objects.
This helps determine which museums can be included in MUSEUM_OBJECT_TYPES.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from smithsonian_mcp.api_client import create_client
from smithsonian_mcp.config import Config
from smithsonian_mcp.models import CollectionSearchFilter


async def test_all_museums():
    """Test all Smithsonian museums for Open Access objects."""
    print("Testing all Smithsonian museums for Open Access objects...")
    print("=" * 60)
    
    try:
        api_client = await create_client()
        units = await api_client.get_units()
        
        results = []
        
        for unit in units:
            print(f"Testing {unit.code} ({unit.name})...")
            
            try:
                # Test with the fixed unit_code filtering
                filters = CollectionSearchFilter(
                    query="*",
                    unit_code=unit.code,
                    limit=1,  # Just check if any exist
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
                
                search_results = await api_client.search_collections(filters)
                
                if search_results.total_count > 0:
                    print(f"  ✓ {unit.code}: {search_results.total_count} objects")
                    results.append((unit.code, unit.name, search_results.total_count, True))
                else:
                    print(f"  ✗ {unit.code}: 0 objects")
                    results.append((unit.code, unit.name, 0, False))
                    
            except Exception as e:
                print(f"  ✗ {unit.code}: Error - {str(e)}")
                results.append((unit.code, unit.name, 0, False))
        
        print("\n" + "=" * 60)
        print("SUMMARY:")
        print("=" * 60)
        
        with_objects = [r for r in results if r[3]]
        without_objects = [r for r in results if not r[3]]
        
        print(f"Museums WITH Open Access objects: {len(with_objects)}")
        for code, name, count, _ in with_objects:
            print(f"  {code}: {count} objects")
            
        print(f"\nMuseums WITHOUT Open Access objects: {len(without_objects)}")
        for code, name, _, _ in without_objects:
            print(f"  {code}: {name}")
            
        # Save results for further analysis
        print(f"\nSaving results to museum_test_results.txt...")
        with open("museum_test_results.txt", "w") as f:
            f.write("Smithsonian Museum Open Access Test Results\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"Museums WITH Open Access objects: {len(with_objects)}\n")
            for code, name, count, _ in with_objects:
                f.write(f"  {code}: {count} objects - {name}\n")
                
            f.write(f"\nMuseums WITHOUT Open Access objects: {len(without_objects)}\n")
            for code, name, _, _ in without_objects:
                f.write(f"  {code}: {name}\n")
                
    except Exception as e:
        print(f"Error: {e}")


async def main():
    """Main function."""
    if not Config.validate_api_key():
        print("Please set SMITHSONIAN_API_KEY environment variable")
        return 1
    
    await test_all_museums()
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
