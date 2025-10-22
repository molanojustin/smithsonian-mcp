#!/usr/bin/env python3
"""
Collect object types for all Smithsonian museums with Open Access objects.
This will update the MUSEUM_OBJECT_TYPES in museum_data.py.
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


async def collect_object_types_for_museum(api_client, museum_code, sample_size=500):
    """Collect object types for a specific museum."""
    print(f"Collecting object types for {museum_code} (sampling {sample_size} objects)...")
    
    try:
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
        
        object_types = set()
        for obj in results.objects:
            if obj.object_type:
                object_types.add(obj.object_type.lower().strip())
        
        sorted_types = sorted(list(object_types))
        print(f"  Found {len(sorted_types)} unique object types")
        
        return sorted_types, len(results.objects)
        
    except Exception as e:
        print(f"  Error collecting types for {museum_code}: {e}")
        return [], 0


async def collect_all_museum_types():
    """Collect object types for all museums with Open Access objects."""
    print("Collecting object types for all Smithsonian museums...")
    print("=" * 60)
    
    try:
        api_client = await create_client()
        
        # Museums that have objects (from our previous test)
        museums_with_objects = [
            "NPG", "SAAM", "HMSG", "FSG", "NMAfA", "NMAI", "NASM", 
            "NMAH", "CHNDM", "NMAAHC", "SIA", "NPM", "NZP", "ACM"
        ]
        
        # NMNH sub-units (from our sampling)
        nmnh_subunits = [
            "NMNHANTHRO", "NMNHBOTANY", "NMNHENTO", "NMNHFISHES", 
            "NMNHHERPS", "NMNHINV", "NMNHMAMMALS", "NMNHMINSCI", "NMNHPALEO"
        ]
        
        all_results = {}
        
        # Collect for regular museums
        for museum in museums_with_objects:
            types, sampled = await collect_object_types_for_museum(api_client, museum)
            if types:
                all_results[museum] = types
            print(f"  {museum}: {len(types)} types from {sampled} objects")
        
        # Collect for NMNH sub-units and combine
        print(f"\nCollecting NMNH sub-units...")
        nmnh_all_types = set()
        nmnh_total_sampled = 0
        
        for subunit in nmnh_subunits:
            types, sampled = await collect_object_types_for_museum(api_client, subunit, sample_size=200)
            nmnh_all_types.update(types)
            nmnh_total_sampled += sampled
            print(f"  {subunit}: {len(types)} types from {sampled} objects")
        
        if nmnh_all_types:
            all_results["NMNH"] = sorted(list(nmnh_all_types))
            print(f"  NMNH (combined): {len(all_results['NMNH'])} types from {nmnh_total_sampled} objects")
        
        # Generate the Python code for MUSEUM_OBJECT_TYPES
        print(f"\n" + "=" * 60)
        print("GENERATED MUSEUM_OBJECT_TYPES CODE:")
        print("=" * 60)
        
        print("# Museum-specific object types discovered from Smithsonian Open Access API")
        print("# These represent the actual object types available in each museum's collections")
        print("MUSEUM_OBJECT_TYPES: Dict[str, List[str]] = {")
        
        for museum, types in sorted(all_results.items()):
            print(f'    "{museum}": [')
            for i, obj_type in enumerate(types):
                comma = "," if i < len(types) - 1 else ""
                print(f'        "{obj_type}"{comma}')
            print("    ],")
        
        print("    # Note: AAA (Archives of American Art) has no Open Access objects")
        print("}")
        
        # Save to file
        output_file = "museum_object_types_collected.py"
        with open(output_file, "w") as f:
            f.write("# Generated museum object types\n")
            f.write("# Run: python scripts/dev/collect_museum_object_types.py\n\n")
            f.write("MUSEUM_OBJECT_TYPES = {\n")
            
            for museum, types in sorted(all_results.items()):
                f.write(f'    "{museum}": [\n')
                for obj_type in types:
                    f.write(f'        "{obj_type}",\n')
                f.write("    ],\n")
            
            f.write("    # AAA has no Open Access objects\n")
            f.write("}\n")
        
        print(f"\nSaved detailed results to {output_file}")
        
        return all_results
        
    except Exception as e:
        print(f"Error: {e}")
        return {}


async def main():
    """Main function."""
    if not Config.validate_api_key():
        print("Please set SMITHSONIAN_API_KEY environment variable")
        return 1
    
    results = await collect_all_museum_types()
    
    print(f"\nCollected object types for {len(results)} museums")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
