"""
Check what Bert/Ernie items appear in 'muppet' search.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from smithsonian_mcp.api_client import create_client
from smithsonian_mcp.models import CollectionSearchFilter


async def check_items():
    """Check what Bert/Ernie items appear in muppet search."""

    client = await create_client()

    try:
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

        print("Items containing 'Bert' or 'Ernie' in 'muppet' search:")
        print("=" * 80)

        for obj in results.objects:
            if "bert" in obj.title.lower() or "ernie" in obj.title.lower():
                on_view = "ON VIEW" if obj.is_on_view else "not on view"
                print(f"\n{obj.title} [{on_view}]")
                print(f"  ID: {obj.id}")
                if obj.is_on_view and obj.exhibition_location:
                    print(f"  Location: {obj.exhibition_location}")

        print("\n" + "=" * 80)
        print("\nNow checking 'sesame street' search for Bert and Ernie PUPPETS:")
        print("=" * 80)

        filters.query = "sesame street"
        results = await client.search_collections(filters)

        for obj in results.objects:
            if (
                "bert puppet" in obj.title.lower()
                or "ernie puppet" in obj.title.lower()
            ):
                on_view = "ON VIEW" if obj.is_on_view else "not on view"
                print(f"\n{obj.title} [{on_view}]")
                print(f"  ID: {obj.id}")
                if obj.is_on_view:
                    if obj.exhibition_location:
                        print(f"  Location: {obj.exhibition_location}")
                    if obj.exhibition_title:
                        print(f"  Exhibition: {obj.exhibition_title}")

    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(check_items())
