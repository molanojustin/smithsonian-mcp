"""
Test script to verify the multi-page search implementation for find_on_view_items.
This test searches for 'muppet' items to verify Bert and Ernie are found.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from smithsonian_mcp.api_client import create_client
from smithsonian_mcp.models import CollectionSearchFilter


async def test_muppet_search():
    """Test that we can find Bert and Ernie by searching through pagination."""
    print("=" * 80)
    print("Testing multi-page search for 'muppet' items")
    print("=" * 80)

    client = await create_client()

    try:
        batch_size = 1000
        max_results = 5000
        all_objects = []
        offset = 0

        print(f"\nSearching for 'muppet' items (up to {max_results} results)...\n")

        while offset < max_results:
            current_batch_size = min(batch_size, max_results - offset)

            filters = CollectionSearchFilter(
                query="muppet",
                unit_code="NMAH",
                on_view=None,
                limit=current_batch_size,
                offset=offset,
                object_type=None,
                maker=None,
                material=None,
                topic=None,
                has_images=None,
                has_3d=None,
                is_cc0=None,
                date_start=None,
                date_end=None,
            )

            batch_results = await client.search_collections(filters)
            all_objects.extend(batch_results.objects)

            print(
                f"Batch {offset//batch_size + 1}: Fetched {len(batch_results.objects)} items "
                f"(offset {offset}, total so far: {len(all_objects)})"
            )

            if not batch_results.has_more:
                print(f"\nReached end of available results at offset {offset}")
                break

            offset += current_batch_size

        on_view_items = [obj for obj in all_objects if obj.is_on_view]

        print(f"\n{'=' * 80}")
        print(f"RESULTS SUMMARY")
        print(f"{'=' * 80}")
        print(f"Total items searched: {len(all_objects)}")
        print(f"On-view items found: {len(on_view_items)}")
        print(f"\nOn-view items:")

        bert_found = False
        ernie_found = False

        for idx, item in enumerate(on_view_items, 1):
            print(f"\n{idx}. {item.title}")
            print(f"   ID: {item.id}")
            if item.exhibition_location:
                print(f"   Location: {item.exhibition_location}")
            if item.exhibition_title:
                print(f"   Exhibition: {item.exhibition_title}")

            if "bert" in item.title.lower():
                bert_found = True
                print("   *** BERT FOUND! ***")
            if "ernie" in item.title.lower():
                ernie_found = True
                print("   *** ERNIE FOUND! ***")

        print(f"\n{'=' * 80}")
        print(f"TEST RESULTS")
        print(f"{'=' * 80}")
        print(f"Bert found: {'✓ YES' if bert_found else '✗ NO'}")
        print(f"Ernie found: {'✓ YES' if ernie_found else '✗ NO'}")

        if bert_found and ernie_found:
            print(
                "\n✓ SUCCESS: Multi-page search successfully found both Bert and Ernie!"
            )
            return True
        else:
            print("\n✗ PARTIAL: Some muppets not found in on-view results")
            print("   (This may be expected if they're not currently on display)")
            return False

    finally:
        await client.disconnect()


if __name__ == "__main__":
    result = asyncio.run(test_muppet_search())
    sys.exit(0 if result else 1)
