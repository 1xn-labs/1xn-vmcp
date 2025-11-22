"""
Test Suite 9: MCP Server Composition
Tests adding MCP servers and verifying tools, resources, and prompts.
Uses a shared vMCP setup for all tests in the class.
"""

import os
import sys
import uuid

import pytest
import requests
from mcp import ClientSession

# Add tests directory to path to import oauth script
tests_dir = os.path.dirname(os.path.abspath(__file__))
if tests_dir not in sys.path:
    sys.path.insert(0, tests_dir)

# Import the patched streamablehttp_client from conftest
from conftest import streamablehttp_client, get_test_dummy_token


def get_auth_headers():
    """Get authentication headers"""
    token = get_test_dummy_token()
    return {"Authorization": f"Bearer {token}"}


def create_test_vmcp(base_url: str, name: str) -> dict:
    """Create a vMCP for testing"""
    response = requests.post(
        base_url + "api/vmcps/create",
        json={"name": name, "description": "Test vMCP"},
        headers=get_auth_headers()
    )
    assert response.status_code == 200, f"Failed to create vMCP: {response.text}"
    return response.json()["vMCP"]


def delete_test_vmcp(base_url: str, vmcp_id: str):
    """Delete a test vMCP"""
    try:
        response = requests.delete(
            base_url + f"api/vmcps/{vmcp_id}",
            headers=get_auth_headers()
        )
        if response.status_code == 200:
            print(f"🗑️  Deleted test vMCP: {vmcp_id}")
    except Exception as e:
        print(f"⚠️  Failed to delete vMCP {vmcp_id}: {e}")


def add_server_to_vmcp(base_url: str, vmcp_id: str, server_config: dict, name: str):
    """Add an MCP server to a vMCP"""
    config = server_config.copy()
    config["name"] = name
    response = requests.post(
        base_url + f"api/vmcps/{vmcp_id}/add-server",
        json={"server_data": config},
        headers=get_auth_headers()
    )
    assert response.status_code == 200, f"Failed to add server: {response.text}"
    return response.json()


@pytest.mark.mcp_server
class TestMCPServerComposition:
    """
    Test MCP server composition - all tests share a single vMCP.

    Setup creates vMCP and adds servers once. Each async test creates
    its own MCP session (lightweight) while reusing the vMCP (expensive).
    """

    @pytest.fixture(autouse=True, scope="class")
    def setup_class_vmcp(self, request, base_url, mcp_servers):
        """
        Class-level setup: Create vMCP and add servers.
        Runs once for the entire test class.
        """
        vmcp_name = f"test_vmcp_composition_{uuid.uuid4().hex[:12]}"

        # Create vMCP
        vmcp = create_test_vmcp(base_url, vmcp_name)
        request.cls._vmcp = vmcp
        request.cls._base_url = base_url
        request.cls._mcp_servers = mcp_servers

        print(f"\n✅ [setup] Created vMCP: {vmcp['id']}")

        # Add servers
        add_server_to_vmcp(base_url, vmcp["id"], mcp_servers["everything"], "everything")
        add_server_to_vmcp(base_url, vmcp["id"], mcp_servers["allfeature"], "allfeature")
        print(f"✅ [setup] Added MCP servers to vMCP")

        # Store MCP URL
        request.cls._mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        yield

        # Cleanup
        delete_test_vmcp(base_url, vmcp["id"])

    def test_servers_added(self):
        """Test: Verify servers were added in setup"""
        print(f"\n📦 Test - Servers added to vMCP: {self._vmcp['id']}")
        assert self._vmcp is not None
        print("✅ Everything and AllFeature servers added successfully")

    @pytest.mark.asyncio
    async def test_verify_tools(self):
        """Test: Verify tools are accessible from MCP server"""
        print(f"\n📦 Test - Verifying tools from MCP server: {self._vmcp['id']}")

        async with streamablehttp_client(self._mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                tools_response = await session.list_tools()
                tools = tools_response.tools
                tool_names = [tool.name for tool in tools]

                print(f"🔧 Found {len(tool_names)} tools:")
                for tool in tools:
                    print(f"   - {tool.name}: {tool.description[:50] if tool.description else 'No description'}...")

                # Verify we have tools from both servers (prefixed with server name)
                everything_tools = [t for t in tool_names if t.startswith("everything_")]
                allfeature_tools = [t for t in tool_names if t.startswith("allfeature_")]

                assert len(everything_tools) > 0, "Expected at least one tool from 'everything' server"
                assert len(allfeature_tools) > 0, "Expected at least one tool from 'allfeature' server"

                print(f"✅ Verified {len(everything_tools)} tools from 'everything' server")
                print(f"✅ Verified {len(allfeature_tools)} tools from 'allfeature' server")
                print(f"✅ Total: {len(tool_names)} tools available")

    @pytest.mark.asyncio
    async def test_verify_prompts(self):
        """Test: Verify prompts are accessible from MCP server"""
        print(f"\n📦 Test - Verifying prompts from MCP server: {self._vmcp['id']}")

        async with streamablehttp_client(self._mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                prompts_response = await session.list_prompts()
                prompts = prompts_response.prompts
                prompt_names = [prompt.name for prompt in prompts]

                print(f"📋 Found {len(prompt_names)} prompts:")
                for prompt in prompts:
                    print(f"   - {prompt.name}: {prompt.description[:50] if prompt.description else 'No description'}...")

                # Verify we have prompts from both servers (prefixed with server name)
                everything_prompts = [p for p in prompt_names if p.startswith("everything_")]
                allfeature_prompts = [p for p in prompt_names if p.startswith("allfeature_")]

                assert len(everything_prompts) > 0, "Expected at least one prompt from 'everything' server"
                assert len(allfeature_prompts) > 0, "Expected at least one prompt from 'allfeature' server"

                print(f"✅ Verified {len(everything_prompts)} prompts from 'everything' server")
                print(f"✅ Verified {len(allfeature_prompts)} prompts from 'allfeature' server")
                print(f"✅ Total: {len(prompt_names)} prompts available")

    @pytest.mark.asyncio
    async def test_verify_resources(self):
        """Test: Verify resources are accessible from MCP server"""
        print(f"\n📦 Test - Verifying resources from MCP server: {self._vmcp['id']}")

        async with streamablehttp_client(self._mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                resources_response = await session.list_resources()
                resources = resources_response.resources
                resource_uris = [str(resource.uri) for resource in resources]

                print(f"📚 Found {len(resource_uris)} resources:")
                for resource in resources:
                    print(f"   - {resource.uri}: {resource.name if resource.name else 'No name'}")

                # Verify we have resources from both servers (prefixed with server name)
                everything_resources = [r for r in resource_uris if r.startswith("everything:")]
                allfeature_resources = [r for r in resource_uris if r.startswith("allfeature:")]

                assert len(everything_resources) > 0, "Expected at least one resource from 'everything' server"
                assert len(allfeature_resources) > 0, "Expected at least one resource from 'allfeature' server"

                print(f"✅ Verified {len(everything_resources)} resources from 'everything' server")
                print(f"✅ Verified {len(allfeature_resources)} resources from 'allfeature' server")
                print(f"✅ Total: {len(resource_uris)} resources available")

    @pytest.mark.asyncio
    async def test_call_tool(self):
        """Test: Call a tool from each composed MCP server"""
        print(f"\n📦 Test - Calling tools from composed MCP servers: {self._vmcp['id']}")

        async with streamablehttp_client(self._mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call tool from 'allfeature' server
                print("\n🔧 Calling allfeature_add tool...")
                allfeature_result = await session.call_tool("allfeature_add", arguments={"a": 5, "b": 3})
                print(f"   Result: {allfeature_result}")

                assert len(allfeature_result.content) > 0
                allfeature_text = allfeature_result.content[0].text
                assert "8" in allfeature_text, f"Expected result to contain '8', got: {allfeature_text}"
                print("   ✅ allfeature_add tool call successful")

                # Call tool from 'everything' server
                print("\n🔧 Calling everything_test_simple_text tool...")
                everything_result = await session.call_tool("everything_test_simple_text", arguments={})
                print(f"   Result: {everything_result}")

                assert len(everything_result.content) > 0
                everything_text = everything_result.content[0].text
                assert "This is a simple text response for testing." in everything_text, f"Expected result to contain 'This is a simple text response.', got: {everything_text}"
                print("   ✅ everything_test_simple_text tool call successful")

                print("\n✅ Successfully called tools from both composed MCP servers")

    @pytest.mark.asyncio
    async def test_get_prompt(self):
        """Test: Get a prompt from each composed MCP server"""
        print(f"\n📦 Test - Getting prompts from composed MCP servers: {self._vmcp['id']}")

        async with streamablehttp_client(self._mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Get prompt from 'allfeature' server
                print("\n📋 Getting allfeature_greet_user prompt...")
                allfeature_result = await session.get_prompt(
                    "allfeature_greet_user",
                    arguments={"name": "Alice", "style": "friendly"}
                )
                print(f"   Result: {allfeature_result}")

                assert len(allfeature_result.messages) > 0
                allfeature_text = allfeature_result.messages[0].content.text
                assert "Alice" in allfeature_text, f"Expected prompt to contain 'Alice', got: {allfeature_text}"
                print("   ✅ allfeature_greet_user prompt retrieval successful")

                # Get prompt from 'everything' server
                print("\n📋 Getting everything_test_simple_prompt prompt...")
                everything_result = await session.get_prompt(
                    "everything_test_simple_prompt",
                    arguments={}
                )
                print(f"   Result: {everything_result}")

                assert len(everything_result.messages) > 0
                everything_text = everything_result.messages[0].content.text
                print(f"   Prompt text: {everything_text[:100]}...")
                print("   ✅ everything_system_administration_prompt prompt retrieval successful")

                print("\n✅ Successfully retrieved prompts from both composed MCP servers")

    @pytest.mark.asyncio
    async def test_get_resource(self):
        """Test: Read a resource from each composed MCP server"""
        print(f"\n📦 Test - Reading resources from composed MCP servers: {self._vmcp['id']}")

        async with streamablehttp_client(self._mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Read resource from 'everything' server
                print("\n📚 Reading everything:test://static-text resource...")
                everything_result = await session.read_resource("everything:test://static-text")
                print(f"   Result: {everything_result}")

                assert len(everything_result.contents) > 0
                everything_content = everything_result.contents[0]
                print(f"   Content type: {type(everything_content)}")
                print("   ✅ everything resource read successful")

                # Read resource from 'allfeature' server
                print("\n📚 Reading allfeature:config://settings resource...")
                allfeature_result = await session.read_resource("allfeature:config://settings")
                print(f"   Result: {allfeature_result}")

                assert len(allfeature_result.contents) > 0
                allfeature_content = allfeature_result.contents[0]
                print(f"   Content type: {type(allfeature_content)}")
                print("   ✅ allfeature resource read successful")

                print("\n✅ Successfully read resources from both composed MCP servers")

    @pytest.mark.asyncio
    async def test_prompt_with_arguments(self):
        """Test: Get a prompt with specific arguments and verify they are included"""
        print(f"\n📦 Test - Getting prompt with arguments: {self._vmcp['id']}")

        async with streamablehttp_client(self._mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Get prompt with 'hello' and 'world' arguments
                print("\n📋 Getting everything_test_prompt_with_arguments prompt with args: hello, world...")
                result = await session.get_prompt(
                    "everything_test_prompt_with_arguments",
                    arguments={"arg1": "hello", "arg2": "world"}
                )
                print(f"   Result: {result}")

                assert len(result.messages) > 0
                prompt_text = result.messages[0].content.text
                print(f"   Prompt text: {prompt_text}")

                # Assert that both arguments are present in the prompt
                assert "hello" in prompt_text, f"Expected prompt to contain 'hello', got: {prompt_text}"
                assert "world" in prompt_text, f"Expected prompt to contain 'world', got: {prompt_text}"

                print("   ✅ Prompt contains 'hello' argument")
                print("   ✅ Prompt contains 'world' argument")
                print("\n✅ Prompt with arguments test successful")
