#!/usr/bin/env python3
"""
Test script to verify mcpo compatibility fix.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smithsonian_mcp.server import get_api_client
from smithsonian_mcp.config import Config


async def test_api_client():
    """Test that the API client can be created without context."""
    print("Testing API client creation without context...")
    
    try:
        # This should work without any context
        api_client = await get_api_client()
        print("✓ API client created successfully")
        
        # Test a simple API call
        print("Testing API call...")
        units = await api_client.get_units()
        print(f"✓ Retrieved {len(units)} Smithsonian units")
        
        # Test stats
        stats = await api_client.get_collection_stats()
        print(f"✓ Retrieved collection statistics: {stats.total_objects:,} total objects")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


async def main():
    """Main test function."""
    print("Testing mcpo compatibility fix...")
    print("=" * 50)
    
    # Check API key
    if not Config.validate_api_key():
        print("⚠ Warning: No API key configured. Some tests may fail.")
        print("  Set SMITHSONIAN_API_KEY environment variable for full testing.")
    
    success = await test_api_client()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 All tests passed! The fix should work with mcpo.")
    else:
        print("❌ Tests failed. Please check the error above.")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)