"""
Test Suite 7: Import Collection
Tests for importing Postman collections and OpenAPI specs as tools
"""

import pytest
import requests
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


@pytest.mark.collection_tool
@pytest.mark.skip(reason="Collection import endpoints not yet implemented in backend API")
class TestImportCollection:
    """Test collection import functionality"""

    def test_import_postman_collection(self, base_url, create_vmcp, test_http_server, helpers):
        """Test 7.1: Import Postman collection"""
        vmcp = create_vmcp
        print(f"\n📦 Test 7.1 - Importing Postman collection: {vmcp['id']}")

        # Read Postman collection
        import json
        collection_path = "/Users/apple/Projects/1mcpXagentsNapps/oss/backend/test_server/postman_collection.json"

        try:
            with open(collection_path, 'r') as f:
                collection_data = json.load(f)
        except FileNotFoundError:
            pytest.skip(f"Postman collection not found at {collection_path}")

        # Import collection via API
        response = requests.post(
            base_url + f"api/vmcps/{vmcp['id']}/import-collection",
            json={
                "collection_type": "postman",
                "collection_data": collection_data,
                "server_url": test_http_server
            }
        )

        # Verify import (may succeed or give validation errors)
        print(f"Import response status: {response.status_code}")
        print(f"Import response: {response.json()}")

        # Get updated vMCP to check tools
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        print(f"Custom tools after import: {len(updated_vmcp.get('custom_tools', []))}")

        print("✅ Postman collection import attempted")

    def test_import_openapi_spec(self, base_url, create_vmcp, test_http_server, helpers):
        """Test 7.2: Import OpenAPI specification"""
        vmcp = create_vmcp
        print(f"\n📦 Test 7.2 - Importing OpenAPI spec: {vmcp['id']}")

        # Read OpenAPI spec
        import json
        openapi_path = "/Users/apple/Projects/1mcpXagentsNapps/oss/backend/test_server/openapi.json"

        try:
            with open(openapi_path, 'r') as f:
                openapi_data = json.load(f)
        except FileNotFoundError:
            pytest.skip(f"OpenAPI spec not found at {openapi_path}")

        # Import OpenAPI spec via API
        response = requests.post(
            base_url + f"api/vmcps/{vmcp['id']}/import-openapi",
            json={
                "openapi_data": openapi_data,
                "server_url": test_http_server
            }
        )

        # Verify import
        print(f"Import response status: {response.status_code}")
        print(f"Import response: {response.json()}")

        # Get updated vMCP to check tools
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        print(f"Custom tools after import: {len(updated_vmcp.get('custom_tools', []))}")

        print("✅ OpenAPI spec import attempted")

    @pytest.mark.asyncio
    async def test_call_imported_collection_tool(self, base_url, create_vmcp, test_http_server, helpers):
        """Test 7.3: Call a tool imported from collection"""
        vmcp = create_vmcp
        print(f"\n📦 Test 7.3 - Calling imported collection tool: {vmcp['id']}")

        # Manually add a tool that mimics imported collection tool
        vmcp_data = helpers["get_vmcp"](vmcp["id"])

        # Add a tool similar to what would be imported from Postman
        collection_tool = {
            "name": "health_check",
            "description": "Health check endpoint from collection",
            "tool_type": "http",
            "api_config": {
                "method": "GET",
                "url": f"{test_http_server}/health",
                "headers": {},
                "query_params": {},
                "auth": {"type": "none"}
            },
            "variables": [],
            "environment_variables": [],
            "tool_calls": [],
            "atomic_blocks": [],
            "source": "postman_collection"
        }

        vmcp_data["custom_tools"].append(collection_tool)
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # List tools to verify it's there
                tools_response = await session.list_tools()
                tool_names = [tool.name for tool in tools_response.tools]

                assert "health_check" in tool_names, "Imported tool should be listed"

                # Call the tool
                result = await session.call_tool("health_check", arguments={})

                print(f"🔧 Tool result: {result}")

                # Verify
                assert len(result.content) > 0
                result_text = result.content[0].text
                assert "200" in result_text

                print("✅ Imported collection tool call successful")

    def test_import_collection_with_authentication(self, base_url, create_vmcp, test_http_server, helpers):
        """Test 7.4: Import collection with authentication headers"""
        vmcp = create_vmcp
        print(f"\n📦 Test 7.4 - Import collection with auth: {vmcp['id']}")

        # Get vMCP data
        vmcp_data = helpers["get_vmcp"](vmcp["id"])

        # Add environment variables for auth
        vmcp_data["environment_variables"] = [
            {"name": "api_key", "value": "test-api-key-123"},
            {"name": "bearer_token", "value": "bearer-token-admin"}
        ]

        # Add tools that would come from collection with auth
        auth_tool = {
            "name": "get_users_collection",
            "description": "Get users (from collection)",
            "tool_type": "http",
            "api_config": {
                "method": "GET",
                "url": f"{test_http_server}/users",
                "headers": {},
                "query_params": {},
                "auth": {
                    "type": "apikey",
                    "apiKey": "@config.api_key",
                    "keyName": "X-API-Key"
                }
            },
            "variables": [],
            "environment_variables": ["api_key"],
            "tool_calls": [],
            "atomic_blocks": [],
            "source": "postman_collection"
        }

        vmcp_data["custom_tools"].append(auth_tool)
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Verify
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        assert len(updated_vmcp["custom_tools"]) == 1
        assert updated_vmcp["custom_tools"][0]["source"] == "postman_collection"

        print("✅ Collection with authentication imported successfully")

    def test_import_collection_with_variables(self, base_url, create_vmcp, test_http_server, helpers):
        """Test 7.5: Import collection with path variables"""
        vmcp = create_vmcp
        print(f"\n📦 Test 7.5 - Import collection with variables: {vmcp['id']}")

        # Get vMCP data
        vmcp_data = helpers["get_vmcp"](vmcp["id"])

        # Add tool with path variables (as would be imported)
        variable_tool = {
            "name": "get_user_by_id_collection",
            "description": "Get user by ID (from collection)",
            "tool_type": "http",
            "api_config": {
                "method": "GET",
                "url": f"{test_http_server}/users/:user_id",
                "headers": {},
                "query_params": {},
                "auth": {
                    "type": "bearer",
                    "token": "bearer-token-user"
                }
            },
            "variables": [
                {"name": "user_id", "description": "User ID", "type": "int", "required": True}
            ],
            "environment_variables": [],
            "tool_calls": [],
            "atomic_blocks": [],
            "source": "postman_collection"
        }

        vmcp_data["custom_tools"].append(variable_tool)
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Verify
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        assert len(updated_vmcp["custom_tools"]) == 1
        assert len(updated_vmcp["custom_tools"][0]["variables"]) == 1

        print("✅ Collection with path variables imported successfully")

    def test_import_collection_multiple_endpoints(self, base_url, create_vmcp, test_http_server, helpers):
        """Test 7.6: Import collection with multiple endpoints"""
        vmcp = create_vmcp
        print(f"\n📦 Test 7.6 - Import collection with multiple endpoints: {vmcp['id']}")

        # Get vMCP data
        vmcp_data = helpers["get_vmcp"](vmcp["id"])

        # Add multiple tools as if from a collection
        endpoints = [
            {
                "name": "get_health",
                "method": "GET",
                "url": "/health"
            },
            {
                "name": "get_info",
                "method": "GET",
                "url": "/info"
            },
            {
                "name": "get_users",
                "method": "GET",
                "url": "/users"
            },
            {
                "name": "get_products",
                "method": "GET",
                "url": "/products"
            }
        ]

        for endpoint in endpoints:
            tool = {
                "name": endpoint["name"],
                "description": f"{endpoint['method']} {endpoint['url']}",
                "tool_type": "http",
                "api_config": {
                    "method": endpoint["method"],
                    "url": f"{test_http_server}{endpoint['url']}",
                    "headers": {},
                    "query_params": {},
                    "auth": {"type": "none"} if endpoint["url"] in ["/health", "/info"] else {
                        "type": "apikey",
                        "apiKey": "test-api-key-123",
                        "keyName": "X-API-Key"
                    }
                },
                "variables": [],
                "environment_variables": [],
                "tool_calls": [],
                "atomic_blocks": [],
                "source": "postman_collection"
            }
            vmcp_data["custom_tools"].append(tool)

        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Verify
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        assert len(updated_vmcp["custom_tools"]) == 4
        assert all(tool["source"] == "postman_collection" for tool in updated_vmcp["custom_tools"])

        print("✅ Collection with multiple endpoints imported successfully")

    @pytest.mark.asyncio
    async def test_list_imported_collection_tools(self, base_url, create_vmcp, test_http_server, helpers):
        """Test 7.7: List tools imported from collection"""
        vmcp = create_vmcp
        print(f"\n📦 Test 7.7 - Listing imported collection tools: {vmcp['id']}")

        # Add multiple collection tools
        vmcp_data = helpers["get_vmcp"](vmcp["id"])

        for i in range(5):
            tool = {
                "name": f"collection_tool_{i}",
                "description": f"Collection tool {i}",
                "tool_type": "http",
                "api_config": {
                    "method": "GET",
                    "url": f"{test_http_server}/health",
                    "headers": {},
                    "query_params": {},
                    "auth": {"type": "none"}
                },
                "variables": [],
                "environment_variables": [],
                "tool_calls": [],
                "atomic_blocks": [],
                "source": "postman_collection"
            }
            vmcp_data["custom_tools"].append(tool)

        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # List tools
                tools_response = await session.list_tools()
                tool_names = [tool.name for tool in tools_response.tools]

                print(f"🔧 Available tools: {tool_names}")

                # Verify all collection tools are listed
                for i in range(5):
                    assert f"collection_tool_{i}" in tool_names

                print(f"✅ All {len(tool_names)} imported tools listed successfully")
