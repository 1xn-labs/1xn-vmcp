"""
Test Suite 2: MCP Server Integration - UPDATED VERSION
Tests adding MCP servers and verifying tools, resources, and prompts
Now properly imports the patched streamablehttp_client from conftest
"""

import asyncio
import os
import sys

import pytest
from mcp import ClientSession

# Add tests directory to path to import oauth script
tests_dir = os.path.dirname(os.path.abspath(__file__))
if tests_dir not in sys.path:
    sys.path.insert(0, tests_dir)

# Import the patched streamablehttp_client from conftest
# This ensures we always have the Authorization header
from conftest import streamablehttp_client


class MCPServerIntegration:
    """Test MCP server integration functionality"""

    @pytest.fixture(autouse=True)
    def setup_vmcp(self, base_url, create_vmcp):
        """Setup shared vMCP and streamable client for all tests in this class."""
        self._vmcp = create_vmcp
        self._base_url = base_url
        # Create the MCP URL for streamable client
        self._mcp_url = f"{base_url}private/{self._vmcp['name']}/vmcp"
        
    def test_add_everything_server(self, base_url, create_vmcp, mcp_servers, helpers):
        """Test 2.1: Add Everything MCP server to vMCP"""
        print(f"\n📦 Test 2.1 - Adding Everything server to vMCP: {self._vmcp['id']}")

        result = helpers["add_server"](
            self._vmcp["id"],
            mcp_servers["everything"],
            "everything"
        )

        assert result is not None
        print("✅ Everything server (HTTP) added successfully")

    def test_add_allfeature_server(self, base_url, create_vmcp, mcp_servers, helpers):
        """Test 2.2: Add AllFeature MCP server to vMCP"""
        print(f"\n📦 Test 2.2 - Adding AllFeature server to vMCP: {self._vmcp['id']}")

        result = helpers["add_server"](
            self._vmcp["id"],
            mcp_servers["allfeature"],
            "allfeature"
        )

        assert result is not None
        print("✅ AllFeature server added successfully")

    @pytest.mark.asyncio
    async def test_verify_tools_from_mcp_server(self, base_url, mcp_servers, helpers, auth_headers):
        """Test 2.3: Verify tools are accessible from MCP server"""
        print(f"\n📦 Test 2.3 - Verifying tools from MCP server: {self._vmcp['id']}")

        # Add server
        helpers["add_server"](self._vmcp["id"], mcp_servers["everything"], "everything")

        # The patched streamablehttp_client will add Authorization automatically
        async with streamablehttp_client(self._mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # List tools
                tools_response = await session.list_tools()
                tool_names = [tool.name for tool in tools_response.tools]

                print(f"🔧 Available tools: {tool_names}")

                # Verify some expected tools exist (tools are prefixed with server name)
                expected_tools = ["everything_test_simple_text", "everything_test_image_content", "everything_test_error_handling"]
                for expected_tool in expected_tools:
                    assert expected_tool in tool_names, f"Expected tool '{expected_tool}' not found"

                print(f"✅ Verified {len(tool_names)} tools available")

    @pytest.mark.asyncio
    async def test_verify_prompts_from_mcp_server(self, base_url, create_vmcp, mcp_servers, helpers, auth_headers):
        """Test 2.4: Verify prompts are accessible from MCP server"""
        vmcp = create_vmcp
        print(f"\n📦 Test 2.4 - Verifying prompts from MCP server: {vmcp['id']}")

        # Add server
        helpers["add_server"](vmcp["id"], mcp_servers["everything"], "everything")

        # Connect via MCP client
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        # The patched streamablehttp_client will add Authorization automatically
        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # List prompts
                prompts_response = await session.list_prompts()
                prompt_names = [prompt.name for prompt in prompts_response.prompts]

                print(f"📋 Available prompts: {prompt_names}")

                # Verify some expected prompts exist (prompts are prefixed with server name)
                expected_prompts = ["everything_test_simple_prompt", "everything_test_prompt_with_arguments", "everything_test_prompt_with_embedded_resource"]
                for expected_prompt in expected_prompts:
                    assert expected_prompt in prompt_names, f"Expected prompt '{expected_prompt}' not found"

                print(f"✅ Verified {len(prompt_names)} prompts available")

    @pytest.mark.asyncio
    async def test_verify_resources_from_mcp_server(self, base_url, create_vmcp, mcp_servers, helpers, auth_headers):
        """Test 2.5: Verify resources are accessible from MCP server"""
        vmcp = create_vmcp
        print(f"\n📦 Test 2.5 - Verifying resources from MCP server: {vmcp['id']}")

        # Add server
        helpers["add_server"](vmcp["id"], mcp_servers["everything"], "everything")

        # Connect via MCP client
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        # The patched streamablehttp_client will add Authorization automatically
        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # List resources
                resources_response = await session.list_resources()
                resource_uris = [resource.uri for resource in resources_response.resources]

                print(f"📚 Available resources: {resource_uris}")

                # Verify we have some resources
                assert len(resource_uris) > 0, "Expected at least one resource"

                print(f"✅ Verified {len(resource_uris)} resources available")

    @pytest.mark.asyncio
    async def test_call_mcp_tool(self, base_url, create_vmcp, mcp_servers, helpers, auth_headers):
        """Test 2.6: Call a tool from MCP server"""
        vmcp = create_vmcp
        print(f"\n📦 Test 2.6 - Calling MCP tool: {vmcp['id']}")

        # Add server
        helpers["add_server"](vmcp["id"], mcp_servers["allfeature"], "allfeature")

        # Connect via MCP client
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        # The patched streamablehttp_client will add Authorization automatically
        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call add tool (tool names are prefixed with server name)
                result = await session.call_tool("allfeature_add", arguments={"a": 5, "b": 3})

                print(f"🔧 Tool result: {result}")

                # Verify result
                assert len(result.content) > 0
                result_text = result.content[0].text
                assert "8" in result_text, f"Expected result to contain '8', got: {result_text}"

                print("✅ Tool call successful")

    @pytest.mark.asyncio
    async def test_get_mcp_prompt(self, base_url, create_vmcp, mcp_servers, helpers, auth_headers):
        """Test 2.7: Get a prompt from MCP server"""
        vmcp = create_vmcp
        print(f"\n📦 Test 2.7 - Getting MCP prompt: {vmcp['id']}")

        # Add server
        helpers["add_server"](vmcp["id"], mcp_servers["allfeature"], "allfeature")

        # Connect via MCP client
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        # The patched streamablehttp_client will add Authorization automatically
        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Get prompt (prompt names are prefixed with server name)
                result = await session.get_prompt("allfeature_greet_user", arguments={"name": "Alice", "style": "friendly"})

                print(f"📋 Prompt result: {result}")

                # Verify result
                assert len(result.messages) > 0
                prompt_text = result.messages[0].content.text
                assert "Alice" in prompt_text, f"Expected prompt to contain 'Alice', got: {prompt_text}"
                assert "friendly" in prompt_text or "warm" in prompt_text

                print("✅ Prompt retrieval successful")

    @pytest.mark.asyncio
    async def test_oauth_mcp_server(self, base_url, vmcp_name, helpers, auth_headers, request):
        """Test 2.8: Add OAuth MCP server with SSE transport, authenticate, and verify tools"""
        # Create vMCP manually
        import requests

        response = requests.post(
            base_url + "api/vmcps/create",
            json={
                "name": vmcp_name,
                "description": "Test vMCP for OAuth"
            },
            headers=auth_headers  # Use auth_headers directly
        )
        assert response.status_code == 200
        vmcp = response.json()["vMCP"]

        # Register cleanup to delete vMCP after test
        def cleanup():
            helpers["delete_vmcp"](vmcp["id"])

        request.addfinalizer(cleanup)

        print(f"\n📦 Test 2.8 - Adding OAuth MCP server: {vmcp['id']}")

        # Add server with SSE transport
        server_config = {
            "url": "https://example-server.modelcontextprotocol.io/sse",
            "name": "oauth_example_server",
            "transport": "sse"
        }

        result = helpers["add_server"](
            vmcp["id"],
            server_config,
            "oauth_example_server"
        )

        assert result is not None
        print("✅ OAuth server added successfully")

        # Extract server_id from the response
        server_info = result.get("server", {})
        server_id = server_info.get("server_id")

        if not server_id:
            # Try alternative path - might be in different location
            vmcp_config = result.get("vmcp_config", {})
            vmcp_config_dict = vmcp_config.get("vmcp_config", {})
            selected_servers = vmcp_config_dict.get("selected_servers", [])
            if selected_servers:
                server_id = selected_servers[0].get("server_id")

        assert server_id is not None, f"Could not find server_id in response: {result}"
        print(f"✅ Found server_id: {server_id}")

        # Perform OAuth authentication using the script
        print("\n🔐 Starting OAuth authentication flow...")
        from simple_oauth import simple_oauth

        oauth_result = simple_oauth(server_id)
        assert oauth_result == "oauth successful", f"OAuth failed: {oauth_result}"
        print("✅ OAuth authentication completed successfully")

        # Wait for OAuth handler to complete
        print("\n⏳ Waiting for OAuth handler to complete discovery...")
        await asyncio.sleep(3)  # Give OAuth handler time to discover and save

        connection_result = requests.post(
            f"{base_url}/api/mcps/{server_id}/connect",
            headers=auth_headers  # Add auth headers here too
        )
        assert connection_result.status_code == 200, f"Failed to connect to server: {connection_result.text}"


@pytest.mark.mcp_server
class TestHTTPMCPServerIntegration (MCPServerIntegration):
    """Test MCP server integration functionality"""
    pass

@pytest.mark.mcp_server
class TestSTDIOMCPServerIntegration (MCPServerIntegration):
    """Test MCP server integration functionality"""
    def test_add_everything_server(self, base_url, create_vmcp, mcp_servers, helpers):
        """Test 2.1: Add Everything MCP server to vMCP"""
        print(f"\n📦 Test 2.1 - Adding Everything server (STDIO) to vMCP: {self._vmcp['id']}")

        result = helpers["add_server"](
            self._vmcp["id"],
            mcp_servers["everything_stdio"],
            "everything_stdio",
        )

        assert result is not None
        print("✅ Everything server (STDIO) added successfully")
    
    def test_add_allfeature_server(self, base_url, create_vmcp, mcp_servers, helpers):
        """Test 2.2: Add AllFeature MCP server to vMCP"""
        print(f"\n📦 Test 2.2 - Adding AllFeature server (STDIO) to vMCP: {self._vmcp['id']}")

        result = helpers["add_server"](
            self._vmcp["id"],
            mcp_servers["allfeature_stdio"],
            "allfeature_stdio"
        )

        assert result is not None
        print("✅ AllFeature server added successfully")

    async def test_oauth_mcp_server(self, base_url, vmcp_name, helpers, auth_headers, request):
        pass  # Override to skip this test for STDIO transport

    

