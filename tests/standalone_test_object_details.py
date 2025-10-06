#!/usr/bin/env python3
"""
Test script to verify object details handling with valid and invalid IDs.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smithsonian_mcp.server import get_api_client
from smithsonian_mcp.config import Config


async def test_object_details():
    """Test object details with both valid and invalid IDs."""
    print("Testing object details handling...")

    try:
        api_client = await get_api_client()

        # Test with invalid object ID (should return None gracefully)
        print("\n1. Testing invalid object ID (F1900.47)...")
        result = await api_client.get_object_by_id("F1900.47")
        if result is None:
            print("✓ Invalid object ID handled correctly (returned None)")
        else:
            print(f"✗ Expected None for invalid ID, got: {result}")
            return False

        # Test with another invalid ID
        print("\n2. Testing another invalid object ID (INVALID_123)...")
        result = await api_client.get_object_by_id("INVALID_123")
        if result is None:
            print("✓ Another invalid object ID handled correctly")
        else:
            print(f"✗ Expected None for invalid ID, got: {result}")
            return False

        # Test with a potentially valid ID format
        print("\n3. Testing object ID with valid format (edanmdm:NMAAHC_2008.24.1)...")
        result = await api_client.get_object_by_id("edanmdm:NMAAHC_2008.24.1")
        if result is None:
            print("✓ Valid format but non-existent ID handled correctly")
        elif result.title:
            print(f"✓ Found valid object: {result.title}")
        else:
            print("✓ Object ID handled (may or may not exist)")

        return True

    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


async def main():
    """Main test function."""
    print("Testing object details error handling...")
    print("=" * 50)

    # Check API key
    if not Config.validate_api_key():
        print("⚠ Warning: No API key configured. Tests may not work properly.")
        print("  Set SMITHSONIAN_API_KEY environment variable for full testing.")
        return 1

    success = await test_object_details()

    print("\n" + "=" * 50)
    if success:
        print("🎉 Object details error handling is working correctly!")
        print("404 errors will now return None instead of causing 500 server errors.")
    else:
        print("❌ Tests failed. Please check the error above.")

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
