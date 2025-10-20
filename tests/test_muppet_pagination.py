"""
Test to see if Bert and Ernie appear when searching for 'muppet' vs 'bert ernie'.
This tests whether pagination would help or if they simply don't match 'muppet' query.
"""

import asyncio
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from smithsonian_mcp.api_client import create_client
from smithsonian_mcp.models import CollectionSearchFilter

pytest.importorskip("pytest_asyncio")


@pytest.mark.asyncio
async def test_search_terms():
    """Test different search approaches."""
    print("=" * 80)
    print("Testing Search Terms for Finding Bert and Ernie")
    print("=" * 80)

    client = await create_client()

    try:
        print("\n1. Searching for 'muppet' (broad search)...")
        filters = CollectionSearchFilter(
            query="muppet",
            unit_code="NMAH",
            on_view=None,
            limit=1000,
            offset=0,
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

        results = await client.search_collections(filters)
        on_view = [obj for obj in results.objects if obj.is_on_view]
        titles = [obj.title for obj in results.objects]

        print(f"   Total results: {results.total_count}")
        print(f"   Returned: {results.returned_count}")
        print(f"   On-view: {len(on_view)}")

        bert_in_muppet = any(
            "bert" in t.lower() and "ernie" not in t.lower() for t in titles
        )
        ernie_in_muppet = any(
            "ernie" in t.lower() and "bert" not in t.lower() for t in titles
        )
        both_in_muppet = any(
            "bert" in t.lower() and "ernie" in t.lower() for t in titles
        )

        print(f"   Contains 'Bert': {bert_in_muppet}")
        print(f"   Contains 'Ernie': {ernie_in_muppet}")
        print(f"   Contains 'Bert and Ernie': {both_in_muppet}")

        print("\n2. Searching for 'muppet OR bert OR ernie' (combined search)...")
        filters.query = "muppet OR bert OR ernie"
        results = await client.search_collections(filters)
        on_view = [obj for obj in results.objects if obj.is_on_view]

        print(f"   Total results: {results.total_count}")
        print(f"   Returned: {results.returned_count}")
        print(f"   On-view: {len(on_view)}")

        bert_puppet = [obj for obj in on_view if "bert puppet" in obj.title.lower()]
        ernie_puppet = [obj for obj in on_view if "ernie puppet" in obj.title.lower()]

        print(f"   Found 'Bert Puppet' on view: {len(bert_puppet) > 0}")
        print(f"   Found 'Ernie Puppet' on view: {len(ernie_puppet) > 0}")

        if bert_puppet:
            print(f"      - {bert_puppet[0].title} (ID: {bert_puppet[0].id})")
        if ernie_puppet:
            print(f"      - {ernie_puppet[0].title} (ID: {ernie_puppet[0].id})")

        print("\n3. Searching for 'sesame street' (alternative approach)...")
        filters.query = "sesame street"
        results = await client.search_collections(filters)
        on_view = [obj for obj in results.objects if obj.is_on_view]

        print(f"   Total results: {results.total_count}")
        print(f"   Returned: {results.returned_count}")
        print(f"   On-view: {len(on_view)}")

        bert_puppet = [obj for obj in on_view if "bert puppet" in obj.title.lower()]
        ernie_puppet = [obj for obj in on_view if "ernie puppet" in obj.title.lower()]

        print(f"   Found 'Bert Puppet' on view: {len(bert_puppet) > 0}")
        print(f"   Found 'Ernie Puppet' on view: {len(ernie_puppet) > 0}")

        # Test assertions
        assert results.total_count > 0, "Should find at least some results"

        print("\n" + "=" * 80)
        print("CONCLUSION:")
        print("=" * 80)
        print("The search term 'muppet' may not match Bert and Ernie puppets in the")
        print(
            "metadata. Using more specific terms like 'bert ernie' or 'sesame street'"
        )
        print("or using OR operators provides better results.")
        print("\nThe multi-page pagination fix ensures that when items DO match,")
        print("they will be found even if they appear beyond the first 1000 results.")

    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(test_search_terms())
