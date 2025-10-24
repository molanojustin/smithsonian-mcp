#!/usr/bin/env python3
"""
Comprehensive search for additional museum object types.
This script tries multiple sampling strategies to find object types that may have been missed.
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


async def comprehensive_sample_museum(api_client, museum_code, strategies):
    """Sample a museum using multiple strategies to find diverse object types."""
    all_types = set()
    total_sampled = 0
    
    print(f"  Comprehensive sampling for {museum_code}...")
    
    for strategy_name, params in strategies:
        try:
            filters = CollectionSearchFilter(
                query=params.get('query', '*'),
                unit_code=museum_code,
                limit=params.get('limit', 100),
                offset=params.get('offset', 0),
                object_type=params.get('object_type'),
                maker=params.get('maker'),
                material=params.get('material'),
                topic=params.get('topic'),
                has_images=params.get('has_images'),
                is_cc0=params.get('is_cc0'),
                on_view=params.get('on_view'),
                date_start=params.get('date_start'),
                date_end=params.get('date_end'),
            )
            
            results = await api_client.search_collections(filters)
            
            # Collect object types
            for obj in results.objects:
                if obj.object_type:
                    all_types.add(obj.object_type.lower().strip())
            
            total_sampled += len(results.objects)
            print(f"    {strategy_name}: {len(results.objects)} objects, {len(all_types)} types so far")
            
        except Exception as e:
            print(f"    {strategy_name}: Error - {str(e)}")
    
    return sorted(list(all_types)), total_sampled


async def comprehensive_search():
    """Conduct comprehensive search for object types across all museums."""
    print("Comprehensive Smithsonian Museum Object Type Search")
    print("=" * 60)
    
    try:
        api_client = await create_client()
        
        # Museums to search (excluding AAA which has no objects)
        museums = [
            "ACM", "CHNDM", "FSG", "HMSG", "NASM", "NMAAHC", "NMAH", 
            "NMAI", "NMAfA", "NPG", "NPM", "SAAM", "SIA"
        ]
        
        # NMNH sub-units
        nmnh_subunits = [
            "NMNHANTHRO", "NMNHBOTANY", "NMNHENTO", "NMNHFISHES", 
            "NMNHHERPS", "NMNHINV", "NMNHMAMMALS", "NMNHMINSCI", "NMNHPALEO"
        ]
        
        # Different sampling strategies
        strategies = [
            ("large_sample", {"limit": 200, "offset": 0}),
            ("offset_sample", {"limit": 100, "offset": 200}),
            ("recent_sample", {"limit": 100, "offset": 0, "query": "date:[2020 TO *]"}),
            ("older_sample", {"limit": 100, "offset": 0, "query": "date:[* TO 2000]"}),
            ("with_images", {"limit": 100, "offset": 0, "has_images": True}),
            ("cc0_only", {"limit": 100, "offset": 0, "is_cc0": True}),
            ("on_view", {"limit": 50, "offset": 0, "on_view": True}),
        ]
        
        # Load existing types to avoid removing them
        from smithsonian_mcp.museum_data import MUSEUM_OBJECT_TYPES
        existing_types = MUSEUM_OBJECT_TYPES.copy()
        
        results = {}
        new_types_found = defaultdict(list)
        
        # Sample regular museums
        for museum in museums:
            print(f"\nSampling {museum}...")
            types, sampled = await comprehensive_sample_museum(api_client, museum, strategies)
            
            # Merge with existing types
            existing = set(existing_types.get(museum, []))
            combined = existing.union(set(types))
            results[museum] = sorted(list(combined))
            
            # Track new types
            new_types = set(types) - existing
            if new_types:
                new_types_found[museum] = sorted(list(new_types))
                print(f"  ✓ Found {len(new_types)} new types: {list(new_types)[:5]}{'...' if len(new_types) > 5 else ''}")
            else:
                print(f"  ✓ No new types found ({len(types)} total)")
        
        # Sample NMNH sub-units
        print(f"\nSampling NMNH sub-units...")
        nmnh_all_types = set()
        nmnh_total_sampled = 0
        
        for subunit in nmnh_subunits:
            types, sampled = await comprehensive_sample_museum(api_client, subunit, strategies[:3])  # Fewer strategies for sub-units
            nmnh_all_types.update(types)
            nmnh_total_sampled += sampled
        
        # Merge NMNH types
        existing_nmnh = set(existing_types.get("NMNH", []))
        combined_nmnh = existing_nmnh.union(nmnh_all_types)
        results["NMNH"] = sorted(list(combined_nmnh))
        
        new_nmnh_types = nmnh_all_types - existing_nmnh
        if new_nmnh_types:
            new_types_found["NMNH"] = sorted(list(new_nmnh_types))
            print(f"  ✓ NMNH: Found {len(new_nmnh_types)} new types: {list(new_nmnh_types)[:5]}{'...' if len(new_nmnh_types) > 5 else ''}")
        else:
            print(f"  ✓ NMNH: No new types found ({len(combined_nmnh)} total)")
        
        # Summary
        print(f"\n" + "=" * 60)
        print("COMPREHENSIVE SEARCH RESULTS")
        print("=" * 60)
        
        total_new_types = sum(len(types) for types in new_types_found.values())
        museums_with_new_types = len(new_types_found)
        
        print(f"New object types discovered: {total_new_types}")
        print(f"Museums with new types: {museums_with_new_types}")
        
        if new_types_found:
            print(f"\nNew types by museum:")
            for museum, types in new_types_found.items():
                print(f"  {museum}: {len(types)} new types")
                for obj_type in types:
                    print(f"    - {obj_type}")
        
        # Generate updated MUSEUM_OBJECT_TYPES
        print(f"\n" + "=" * 60)
        print("UPDATED MUSEUM_OBJECT_TYPES")
        print("=" * 60)
        
        print("# Museum-specific object types discovered from Smithsonian Open Access API")
        print("# These represent the actual object types available in each museum's collections")
        print("MUSEUM_OBJECT_TYPES: Dict[str, List[str]] = {")
        
        for museum, types in sorted(results.items()):
            print(f'    "{museum}": [')
            for i, obj_type in enumerate(types):
                comma = ',' if i < len(types) - 1 else ''
                print(f'        "{obj_type}"{comma}')
            print("    ],")
        
        print("    # Note: AAA (Archives of American Art) has no Open Access objects")
        print("}")
        
        # Save results
        with open("comprehensive_search_results.py", "w") as f:
            f.write("# Comprehensive search results - new object types found\n")
            f.write(f"# Total new types: {total_new_types}\n")
            f.write(f"# Museums with new types: {museums_with_new_types}\n\n")
            
            f.write("NEW_TYPES_FOUND = {\n")
            for museum, types in sorted(new_types_found.items()):
                f.write(f'    "{museum}": {types},\n')
            f.write("}\n\n")
            
            f.write("UPDATED_MUSEUM_OBJECT_TYPES = {\n")
            for museum, types in sorted(results.items()):
                f.write(f'    "{museum}": {types},\n')
            f.write("}\n")
        
        print(f"\nDetailed results saved to comprehensive_search_results.py")
        
        return results, new_types_found
        
    except Exception as e:
        print(f"Error: {e}")
        return {}, {}


async def main():
    """Main function."""
    if not Config.validate_api_key():
        print("Please set SMITHSONIAN_API_KEY environment variable")
        return 1
    
    results, new_types = await comprehensive_search()
    
    print(f"\nComprehensive search completed. Found new types for {len(new_types)} museums.")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
