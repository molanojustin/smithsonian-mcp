"""
Search for Bert and Ernie specifically in the Smithsonian database.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from smithsonian_mcp.api_client import create_client
from smithsonian_mcp.models import CollectionSearchFilter


async def search_for_bert_and_ernie():
    """Search for Bert and Ernie in different ways."""
    print("=" * 80)
    print("Searching for Bert and Ernie")
    print("=" * 80)

    client = await create_client()

    try:
        search_terms = [
            "bert ernie",
            "bert",
            "ernie",
            "sesame street bert",
            "sesame street ernie",
        ]

        for term in search_terms:
            print(f"\n{'=' * 80}")
            print(f"Searching for: '{term}' at NMAH")
            print(f"{'=' * 80}")

            filters = CollectionSearchFilter(
                query=term,
                unit_code="NMAH",
                on_view=None,
                limit=100,
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

            print(
                f"Found {results.total_count} total results, returned {results.returned_count}"
            )

            if results.objects:
                print(f"\nFirst 10 results:")
                for idx, obj in enumerate(results.objects[:10], 1):
                    on_view_status = "ON VIEW" if obj.is_on_view else "not on view"
                    print(f"{idx}. {obj.title} [{on_view_status}]")
                    if obj.is_on_view and obj.exhibition_location:
                        print(f"   Location: {obj.exhibition_location}")

                on_view = [obj for obj in results.objects if obj.is_on_view]
                print(f"\nOn-view items: {len(on_view)}")
                for obj in on_view:
                    print(f"  - {obj.title}")
                    if obj.exhibition_location:
                        print(f"    Location: {obj.exhibition_location}")

    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(search_for_bert_and_ernie())
