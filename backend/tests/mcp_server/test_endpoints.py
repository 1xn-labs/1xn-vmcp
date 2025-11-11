#!/usr/bin/env python3
"""
Test script to verify MCP server endpoints
"""

import asyncio

import httpx


async def test_endpoints():
    """Test all MCP server endpoints."""
    base_url = "http://localhost:8001"

    async with httpx.AsyncClient() as client:
        print("🧪 Testing MCP Server Endpoints...")
        print("=" * 50)

        # Test root endpoint
        try:
            response = await client.get(f"{base_url}/")
            print(f"✅ Root endpoint: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Service: {data.get('service')}")
                print(f"   Endpoints: {list(data.get('endpoints', {}).keys())}")
        except Exception as e:
            print(f"❌ Root endpoint failed: {e}")

        # Test health endpoint
        try:
            response = await client.get(f"{base_url}/health")
            print(f"✅ Health endpoint: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Status: {data.get('status')}")
                print(f"   Port: {data.get('port')}")
        except Exception as e:
            print(f"❌ Health endpoint failed: {e}")

        # Test everything endpoint (MCP protocol)
        try:
            response = await client.post(
                f"{base_url}/everything",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "test-client",
                            "version": "1.0.0"
                        }
                    }
                }
            )
            print(f"✅ Everything endpoint: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Response ID: {data.get('id')}")
                print(f"   Result: {data.get('result', {}).get('serverInfo', {}).get('name', 'Unknown')}")
        except Exception as e:
            print(f"❌ Everything endpoint failed: {e}")

        # Test allfeature endpoint (MCP protocol)
        try:
            response = await client.post(
                f"{base_url}/allfeature",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "test-client",
                            "version": "1.0.0"
                        }
                    }
                }
            )
            print(f"✅ Allfeature endpoint: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Response ID: {data.get('id')}")
                print(f"   Result: {data.get('result', {}).get('serverInfo', {}).get('name', 'Unknown')}")
        except Exception as e:
            print(f"❌ Allfeature endpoint failed: {e}")

        print("=" * 50)
        print("🎉 Endpoint testing completed!")


if __name__ == "__main__":
    print("⚠️  Make sure the MCP server is running on localhost:8001")
    print("   Start it with: python start_mcp_servers.py")
    print()
    asyncio.run(test_endpoints())

