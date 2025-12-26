#!/usr/bin/env python3
"""
Test script for BreachVIP OSINT integration

Tests the BreachVIP client and API endpoints.
"""

import asyncio
import sys
sys.path.insert(0, "services/api")

from app.osint import BreachVIPClient, SearchField


async def test_basic_search():
    """Test basic search functionality"""
    print("=" * 60)
    print("Testing BreachVIP Integration")
    print("=" * 60)
    
    async with BreachVIPClient() as client:
        print("\n1. Testing email search (example.com)...")
        try:
            results = await client.search_email("test@example.com")
            print(f"   ✓ Found {len(results)} results")
            if results:
                print(f"   First result source: {results[0].source}")
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        print("\n2. Testing username search...")
        try:
            results = await client.search_username("admin")
            print(f"   ✓ Found {len(results)} results")
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        print("\n3. Testing wildcard search...")
        try:
            results = await client.search("test*", [SearchField.USERNAME])
            print(f"   ✓ Found {len(results)} results with wildcard")
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        print("\n4. Testing multi-field search...")
        try:
            results = await client.search_multi_field(
                "admin",
                [SearchField.EMAIL, SearchField.USERNAME]
            )
            print(f"   ✓ Found {len(results)} results across multiple fields")
        except Exception as e:
            print(f"   ✗ Error: {e}")
    
    print("\n" + "=" * 60)
    print("✓ All tests completed!")
    print("=" * 60)


async def test_api_endpoints():
    """Test API rate limiting and error handling"""
    print("\n\nTesting API Features:")
    print("-" * 60)
    
    async with BreachVIPClient() as client:
        print("\n5. Testing rate limiting (3 requests in quick succession)...")
        for i in range(3):
            try:
                results = await client.search_email(f"test{i}@example.com")
                print(f"   Request {i+1}: ✓ Completed ({len(results)} results)")
            except Exception as e:
                print(f"   Request {i+1}: ✗ {e}")


if __name__ == "__main__":
    print("\n🔍 BreachVIP OSINT Integration Test\n")
    print("This will make real API calls to breach.vip")
    print("Rate limit: 15 requests/minute\n")
    
    try:
        asyncio.run(test_basic_search())
        asyncio.run(test_api_endpoints())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
