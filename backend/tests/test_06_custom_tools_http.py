"""
Test Suite 6: Custom Tools - HTTP Type
Tests for HTTP-based custom tools with various authentication methods
"""

import pytest
import requests
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


@pytest.mark.http_tool
class TestCustomToolsHTTP:
    """Test HTTP-type custom tools"""

    def test_create_simple_http_get_tool(self, base_url, create_vmcp, test_http_server, helpers):
        """Test 6.1: Create a simple HTTP GET tool"""
        vmcp = create_vmcp
        print(f"\n📦 Test 6.1 - Creating simple HTTP GET tool: {vmcp['id']}")

        # Get vMCP data
        vmcp_data = helpers["get_vmcp"](vmcp["id"])

        # Add HTTP GET tool
        http_get_tool = {
            "name": "get_server_health",
            "description": "Get server health status",
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
            "atomic_blocks": []
        }

        vmcp_data["custom_tools"].append(http_get_tool)
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Verify
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        assert len(updated_vmcp["custom_tools"]) == 1
        assert updated_vmcp["custom_tools"][0]["tool_type"] == "http"

        print("✅ Simple HTTP GET tool created successfully")

    @pytest.mark.asyncio
    async def test_call_http_get_tool(self, base_url, create_vmcp, test_http_server, helpers):
        """Test 6.2: Call HTTP GET tool"""
        vmcp = create_vmcp
        print(f"\n📦 Test 6.2 - Calling HTTP GET tool: {vmcp['id']}")

        # Add HTTP GET tool
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "fetch_health",
            "description": "Fetch health status",
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
            "atomic_blocks": []
        })
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call tool
                result = await session.call_tool("fetch_health", arguments={})

                print(f"🔧 Tool result: {result}")

                # Verify
                assert len(result.content) > 0
                result_text = result.content[0].text
                assert "200" in result_text, f"Expected status 200, got: {result_text}"
                assert "healthy" in result_text.lower() or "success" in result_text.lower()

                print("✅ HTTP GET tool call successful")

    @pytest.mark.asyncio
    async def test_http_tool_with_api_key_header(self, base_url, create_vmcp, test_http_server, helpers):
        """Test 6.3: HTTP tool with API key header authentication"""
        vmcp = create_vmcp
        print(f"\n📦 Test 6.3 - HTTP tool with API key header: {vmcp['id']}")

        # Add HTTP tool with API key auth
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "get_users_with_apikey",
            "description": "Get users with API key",
            "tool_type": "http",
            "api_config": {
                "method": "GET",
                "url": f"{test_http_server}/users",
                "headers": {},
                "query_params": {},
                "auth": {
                    "type": "apikey",
                    "apiKey": "test-api-key-123",
                    "keyName": "X-API-Key"
                }
            },
            "variables": [],
            "environment_variables": [],
            "tool_calls": [],
            "atomic_blocks": []
        })
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call tool
                result = await session.call_tool("get_users_with_apikey", arguments={})

                print(f"🔧 Tool result: {result}")

                # Verify successful API call with authentication
                result_text = result.content[0].text
                assert "200" in result_text, f"Expected status 200, got: {result_text}"

                print("✅ HTTP tool with API key header successful")

    @pytest.mark.asyncio
    async def test_http_tool_with_bearer_token(self, base_url, create_vmcp, test_http_server, helpers):
        """Test 6.4: HTTP tool with Bearer token authentication"""
        vmcp = create_vmcp
        print(f"\n📦 Test 6.4 - HTTP tool with Bearer token: {vmcp['id']}")

        # Add HTTP tool with Bearer auth
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "get_user_profile",
            "description": "Get user profile",
            "tool_type": "http",
            "api_config": {
                "method": "GET",
                "url": f"{test_http_server}/users/1",
                "headers": {},
                "query_params": {},
                "auth": {
                    "type": "bearer",
                    "token": "bearer-token-admin"
                }
            },
            "variables": [],
            "environment_variables": [],
            "tool_calls": [],
            "atomic_blocks": []
        })
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call tool
                result = await session.call_tool("get_user_profile", arguments={})

                print(f"🔧 Tool result: {result}")

                # Verify
                result_text = result.content[0].text
                assert "200" in result_text, f"Expected status 200, got: {result_text}"

                print("✅ HTTP tool with Bearer token successful")

    @pytest.mark.asyncio
    async def test_http_tool_with_basic_auth(self, base_url, create_vmcp, test_http_server, helpers):
        """Test 6.5: HTTP tool with Basic authentication"""
        vmcp = create_vmcp
        print(f"\n📦 Test 6.5 - HTTP tool with Basic auth: {vmcp['id']}")

        # Add HTTP tool with Basic auth
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "create_user",
            "description": "Create a new user",
            "tool_type": "http",
            "api_config": {
                "method": "POST",
                "url": f"{test_http_server}/users",
                "headers": {"Content-Type": "application/json"},
                "query_params": {},
                "body_parsed": {
                    "username": "testuser",
                    "email": "test@example.com",
                    "full_name": "Test User",
                    "password": "testpass123"
                },
                "auth": {
                    "type": "basic",
                    "username": "admin",
                    "password": "admin123"
                }
            },
            "variables": [],
            "environment_variables": [],
            "tool_calls": [],
            "atomic_blocks": []
        })
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call tool
                result = await session.call_tool("create_user", arguments={})

                print(f"🔧 Tool result: {result}")

                # Verify (might get 200 or 400 if user exists)
                result_text = result.content[0].text
                assert "200" in result_text or "400" in result_text

                print("✅ HTTP tool with Basic auth successful")

    @pytest.mark.asyncio
    async def test_http_tool_with_query_params(self, base_url, create_vmcp, test_http_server, helpers):
        """Test 6.6: HTTP tool with query parameters"""
        vmcp = create_vmcp
        print(f"\n📦 Test 6.6 - HTTP tool with query parameters: {vmcp['id']}")

        # Add HTTP tool with query params
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "get_products_filtered",
            "description": "Get filtered products",
            "tool_type": "http",
            "api_config": {
                "method": "GET",
                "url": f"{test_http_server}/products",
                "headers": {},
                "query_params": {
                    "category": "Electronics",
                    "in_stock": "true",
                    "api_key": "test-api-key-123"
                },
                "auth": {"type": "none"}
            },
            "variables": [],
            "environment_variables": [],
            "tool_calls": [],
            "atomic_blocks": []
        })
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call tool
                result = await session.call_tool("get_products_filtered", arguments={})

                print(f"🔧 Tool result: {result}")

                # Verify
                result_text = result.content[0].text
                assert "200" in result_text, f"Expected status 200, got: {result_text}"

                print("✅ HTTP tool with query parameters successful")

    @pytest.mark.asyncio
    async def test_http_tool_with_param_substitution(self, base_url, create_vmcp, test_http_server, helpers):
        """Test 6.7: HTTP tool with @param variable substitution"""
        vmcp = create_vmcp
        print(f"\n📦 Test 6.7 - HTTP tool with param substitution: {vmcp['id']}")

        # Add HTTP tool with param substitution
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "get_user_by_id",
            "description": "Get user by ID",
            "tool_type": "http",
            "api_config": {
                "method": "GET",
                "url": f"{test_http_server}/users/@param.user_id",
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
            "atomic_blocks": []
        })
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call tool with user_id parameter
                result = await session.call_tool("get_user_by_id", arguments={"user_id": 2})

                print(f"🔧 Tool result: {result}")

                # Verify
                result_text = result.content[0].text
                assert "200" in result_text, f"Expected status 200, got: {result_text}"

                print("✅ HTTP tool with param substitution successful")

    @pytest.mark.asyncio
    async def test_http_tool_with_config_substitution(self, base_url, create_vmcp, test_http_server, helpers):
        """Test 6.8: HTTP tool with @config variable substitution"""
        vmcp = create_vmcp
        print(f"\n📦 Test 6.8 - HTTP tool with config substitution: {vmcp['id']}")

        # Add environment variables
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["environment_variables"] = [
            {"name": "api_key", "value": "test-api-key-123"}
        ]

        # Add HTTP tool with config substitution
        vmcp_data["custom_tools"].append({
            "name": "get_users_with_config",
            "description": "Get users using config API key",
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
            "atomic_blocks": []
        })
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call tool
                result = await session.call_tool("get_users_with_config", arguments={})

                print(f"🔧 Tool result: {result}")

                # Verify
                result_text = result.content[0].text
                assert "200" in result_text, f"Expected status 200, got: {result_text}"

                print("✅ HTTP tool with config substitution successful")

    @pytest.mark.asyncio
    async def test_http_post_with_json_body(self, base_url, create_vmcp, test_http_server, helpers):
        """Test 6.9: HTTP POST with JSON body and param substitution"""
        vmcp = create_vmcp
        print(f"\n📦 Test 6.9 - HTTP POST with JSON body: {vmcp['id']}")

        # Add HTTP POST tool with JSON body
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "create_product",
            "description": "Create a new product",
            "tool_type": "http",
            "api_config": {
                "method": "POST",
                "url": f"{test_http_server}/products",
                "headers": {"Content-Type": "application/json"},
                "query_params": {},
                "body_parsed": {
                    "name": "@param.product_name",
                    "description": "@param.description",
                    "price": "@param.price",
                    "category": "@param.category",
                    "in_stock": True,
                    "tags": [],
                    "metadata": {}
                },
                "auth": {
                    "type": "bearer",
                    "token": "bearer-token-admin"
                }
            },
            "variables": [
                {"name": "product_name", "description": "Product name", "type": "str", "required": True},
                {"name": "description", "description": "Product description", "type": "str", "required": True},
                {"name": "price", "description": "Product price", "type": "float", "required": True},
                {"name": "category", "description": "Product category", "type": "str", "required": True}
            ],
            "environment_variables": [],
            "tool_calls": [],
            "atomic_blocks": []
        })
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call tool with arguments
                result = await session.call_tool(
                    "create_product",
                    arguments={
                        "product_name": "Test Keyboard",
                        "description": "Mechanical keyboard",
                        "price": 99.99,
                        "category": "Electronics"
                    }
                )

                print(f"🔧 Tool result: {result}")

                # Verify
                result_text = result.content[0].text
                assert "200" in result_text, f"Expected status 200, got: {result_text}"

                print("✅ HTTP POST with JSON body successful")

    @pytest.mark.asyncio
    async def test_http_patch_method(self, base_url, create_vmcp, test_http_server, helpers):
        """Test 6.10: HTTP PATCH method"""
        vmcp = create_vmcp
        print(f"\n📦 Test 6.10 - HTTP PATCH method: {vmcp['id']}")

        # Add HTTP PATCH tool
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "update_product_price",
            "description": "Update product price",
            "tool_type": "http",
            "api_config": {
                "method": "PATCH",
                "url": f"{test_http_server}/products/@param.product_id",
                "headers": {"Content-Type": "application/json"},
                "query_params": {},
                "body_parsed": {
                    "price": "@param.new_price"
                },
                "auth": {
                    "type": "bearer",
                    "token": "bearer-token-admin"
                }
            },
            "variables": [
                {"name": "product_id", "description": "Product ID", "type": "int", "required": True},
                {"name": "new_price", "description": "New price", "type": "float", "required": True}
            ],
            "environment_variables": [],
            "tool_calls": [],
            "atomic_blocks": []
        })
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call tool
                result = await session.call_tool(
                    "update_product_price",
                    arguments={"product_id": 1, "new_price": 899.99}
                )

                print(f"🔧 Tool result: {result}")

                # Verify
                result_text = result.content[0].text
                assert "200" in result_text, f"Expected status 200, got: {result_text}"

                print("✅ HTTP PATCH method successful")
