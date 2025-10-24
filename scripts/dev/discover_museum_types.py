#!/usr/bin/env python3
"""
Comprehensive object type discovery for any Smithsonian museum.
Usage: python discover_museum_types.py <MUSEUM_CODE>

This script samples a museum's collection using multiple strategies to discover
additional object types that may not have been captured in initial sampling.
"""

import asyncio
import sys
import os
import random
import time
from collections import defaultdict
from typing import List, Set

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from smithsonian_mcp.api_client import create_client
from smithsonian_mcp.config import Config
from smithsonian_mcp.models import CollectionSearchFilter


def generate_random_strategies(museum_code: str, total_samples: int = 2800) -> List[dict]:
    """Generate randomized sampling strategies for comprehensive discovery."""
    # Use a random seed based on current time and museum code for reproducibility
    seed = hash(f"{museum_code}_{random.randint(0, 1000000)}")
    random.seed(seed)
    
    strategies = []
    samples_per_strategy = total_samples // 8  # 8 strategies like before
    
    # Base strategies with randomization
    base_strategies = [
        {
            "name": "random_sample_1", 
            "limit": samples_per_strategy, 
            "offset": random.randint(0, 2000),
            "query": "*"
        },
        {
            "name": "random_sample_2", 
            "limit": samples_per_strategy, 
            "offset": random.randint(0, 2000),
            "query": "*"
        },
        {
            "name": "random_recent", 
            "limit": samples_per_strategy // 2, 
            "offset": random.randint(0, 500),
            "query": f"date:[{random.randint(1990, 2010)} TO *]"
        },
        {
            "name": "random_historical", 
            "limit": samples_per_strategy // 2, 
            "offset": random.randint(0, 500),
            "query": f"date:[* TO {random.randint(1950, 1980)}]"
        },
        {
            "name": "random_with_images", 
            "limit": samples_per_strategy // 2, 
            "offset": random.randint(0, 500),
            "has_images": True
        },
        {
            "name": "random_cc0", 
            "limit": samples_per_strategy // 3, 
            "offset": random.randint(0, 300),
            "is_cc0": True
        },
        {
            "name": "random_on_view", 
            "limit": samples_per_strategy // 3, 
            "offset": random.randint(0, 300),
            "on_view": True
        },
        {
            "name": "random_mixed", 
            "limit": samples_per_strategy // 2, 
            "offset": random.randint(0, 500),
            "query": random.choice(["*", "art", "object", "collection"])
        }
    ]
    
    return base_strategies


async def discover_museum_types(museum_code: str):
    """Discover additional object types for a specific museum."""
    print(f"🔍 Comprehensive Object Type Discovery for {museum_code}")
    print("=" * 60)
    start_time = time.time()

    try:
        api_client = await create_client()

        # Load existing types
        from smithsonian_mcp.museum_data import MUSEUM_OBJECT_TYPES
        existing_types = set(MUSEUM_OBJECT_TYPES.get(museum_code.upper(), []))
        print(f"📊 Existing {museum_code} object types: {len(existing_types)}")
        if existing_types:
            print(f"   {sorted(existing_types)}")

        # Generate randomized strategies
        strategies = generate_random_strategies(museum_code)
        print(f"\n🎯 Using {len(strategies)} randomized sampling strategies...")
        print("   Progress: ", end="", flush=True)

        all_types = set()
        total_sampled = 0

        for i, strategy in enumerate(strategies, 1):
            try:
                filters = CollectionSearchFilter(
                    query=strategy.get('query', '*'),
                    unit_code=museum_code,
                    limit=strategy.get('limit', 500),
                    offset=strategy.get('offset', 0),
                    object_type=None,
                    maker=None,
                    material=None,
                    topic=None,
                    has_images=strategy.get('has_images'),
                    is_cc0=strategy.get('is_cc0'),
                    on_view=strategy.get('on_view'),
                    date_start=None,
                    date_end=None,
                )

                results = await api_client.search_collections(filters)

                # Collect object types
                for obj in results.objects:
                    if obj.object_type:
                        all_types.add(obj.object_type.lower().strip())

                total_sampled += len(results.objects)

                # Progress indicator
                progress = int((i / len(strategies)) * 100)
                print(f"\r   Progress: [{'#' * (progress // 5)}{'.' * (20 - progress // 5)}] {progress}% ({i}/{len(strategies)})", end="", flush=True)

            except Exception as e:
                print(f"\r   ❌ Strategy {strategy['name']}: Error - {str(e)}")
                continue
        
        print()  # New line after progress

        # Check for new types
        new_types = all_types - existing_types
        combined_types = existing_types.union(all_types)

        elapsed_time = time.time() - start_time

        print(f"\n" + "=" * 60)
        print(f"🎉 {museum_code} DISCOVERY RESULTS")
        print("=" * 60)
        print(f"⏱️  Time elapsed: {elapsed_time:.1f} seconds")
        print(f"📦 Total objects sampled: {total_sampled}")
        print(f"📚 Existing types: {len(existing_types)}")
        print(f"🔍 Total types found: {len(all_types)}")
        print(f"📈 Combined types: {len(combined_types)}")
        print(f"✨ New types discovered: {len(new_types)}")

        if new_types:
            print(f"\n🆕 New object types found:")
            for obj_type in sorted(new_types):
                print(f"   • {obj_type}")
        else:
            print("\n✅ No new object types found.")

        return sorted(list(combined_types)), sorted(list(new_types))

    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"\n❌ Error after {elapsed_time:.1f} seconds: {e}")
        return [], []


def update_museum_data_file(museum_code: str, new_types_list: List[str]):
    """Update the MUSEUM_OBJECT_TYPES in museum_data.py with new types."""
    file_path = 'smithsonian_mcp/museum_data.py'
    try:

        # Read the current file
        with open(file_path, 'r') as f:
            content = f.read()

        # Create the replacement string with proper formatting
        replacement = f'    "{museum_code.upper()}": {new_types_list},'

        # Find the old line using precise line-by-line matching
        import re
        # Match the exact museum line with proper line boundaries
        pattern = rf'(?m)^(\s*)"({museum_code.upper()})":\s*\[.*?\],$'
        match = re.search(pattern, content, re.MULTILINE)

        if match:
            old_line = match.group(0)
            new_content = content.replace(old_line, replacement)

            # Write back
            with open(file_path, 'w') as f:
                f.write(new_content)

            print(f"✅ Updated MUSEUM_OBJECT_TYPES for {museum_code} in {file_path}")
            return True
        else:
            print(f"❌ Could not find {museum_code} entry in MUSEUM_OBJECT_TYPES")
            print("   This may be due to case sensitivity issues or the museum not being in the file.")
            return False

    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return False
    except PermissionError:
        print(f"❌ Permission denied writing to: {file_path}")
        return False
    except Exception as e:
        print(f"❌ Error updating museum_data.py: {e}")
        return False


async def main():
    """Main function."""
    if len(sys.argv) != 2:
        print("❌ Usage: python discover_museum_types.py <MUSEUM_CODE>")
        print("📝 Example: python discover_museum_types.py FSG")
        print("🏛️  Valid museum codes: ACM, CHNDM, FSG, HMSG, NASM, NMAAHC, NMAH, NMAI, NPM, NPG, SAAM, SIA")
        return 1

    museum_code = sys.argv[1].upper()

    if not Config.validate_api_key():
        print("❌ Please set SMITHSONIAN_API_KEY environment variable")
        print("   Get a free key from: https://api.data.gov/signup/")
        return 1

    print(f"🚀 Starting discovery for museum: {museum_code}")

    all_types, new_types = await discover_museum_types(museum_code)

    if new_types:
        print(f"\n🎯 Found {len(new_types)} new object types for {museum_code}!")

        # Update the museum data file
        success = update_museum_data_file(museum_code, all_types)

        if success:
            print(f"✅ Successfully updated museum_data.py with {len(all_types)} total types for {museum_code}")
        else:
            print("❌ Failed to update museum_data.py automatically.")
            print("📝 Please manually update MUSEUM_OBJECT_TYPES with these new types:")
            print(f'    "{museum_code}": {all_types},')
    else:
        print(f"\n✅ No additional object types found for {museum_code}.")
        print("   This museum may already have comprehensive type coverage.")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
