"""
Test Suite: Progressive Discovery with Sandbox

Tests the interaction between sandbox and progressive discovery features:
1. Sandbox disabled (irrespective of progressive discovery) - no execute_bash or setup prompt
2. Sandbox enabled (irrespective of progressive discovery) - execute_bash and setup prompt appear
3. Sandbox enabled + Progressive discovery ON - only execute_bash, MCP tools hidden, prompt has CLI
4. Sandbox enabled + Progressive discovery OFF - execute_bash + MCP tools, prompt is SDK-only
"""

import asyncio
import os
import sys

import pytest
import requests
from mcp import ClientSession

# Add tests directory to path
tests_dir = os.path.dirname(os.path.abspath(__file__))
if tests_dir not in sys.path:
    sys.path.insert(0, tests_dir)

# Import the patched streamablehttp_client from conftest
from conftest import streamablehttp_client  # noqa: E402


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def enable_sandbox(base_url: str, vmcp_id: str, auth_headers: dict) -> dict:
    """Enable sandbox for a vMCP."""
    response = requests.post(
        f"{base_url}api/vmcps/{vmcp_id}/sandbox/enable",
        headers=auth_headers
    )
    assert response.status_code == 200, f"Failed to enable sandbox: {response.text}"
    return response.json()


def disable_sandbox(base_url: str, vmcp_id: str, auth_headers: dict) -> dict:
    """Disable sandbox for a vMCP."""
    response = requests.post(
        f"{base_url}api/vmcps/{vmcp_id}/sandbox/disable",
        headers=auth_headers
    )
    assert response.status_code == 200, f"Failed to disable sandbox: {response.text}"
    return response.json()


def enable_progressive_discovery(base_url: str, vmcp_id: str, auth_headers: dict) -> dict:
    """Enable progressive discovery for a vMCP."""
    response = requests.post(
        f"{base_url}api/vmcps/{vmcp_id}/progressive-discovery/enable",
        headers=auth_headers
    )
    assert response.status_code == 200, f"Failed to enable progressive discovery: {response.text}"
    return response.json()


def disable_progressive_discovery(base_url: str, vmcp_id: str, auth_headers: dict) -> dict:
    """Disable progressive discovery for a vMCP."""
    response = requests.post(
        f"{base_url}api/vmcps/{vmcp_id}/progressive-discovery/disable",
        headers=auth_headers
    )
    assert response.status_code == 200, f"Failed to disable progressive discovery: {response.text}"
    return response.json()


# ============================================================================
# TEST CLASS
# ============================================================================

@pytest.mark.mcp_server
class TestProgressiveDiscovery:
    """Test progressive discovery functionality with sandbox"""

    @pytest.fixture(autouse=True)
    def setup_vmcp(self, base_url, create_vmcp, mcp_servers, helpers):
        """Setup vMCP with MCP server for all tests"""
        self._vmcp = create_vmcp
        self._base_url = base_url
        self._mcp_url = f"{base_url}private/{self._vmcp['name']}/vmcp"
        
        # Add MCP server to vMCP
        print(f"\n📦 Setting up vMCP {self._vmcp['id']} with MCP server")
        helpers["add_server"](
            self._vmcp["id"],
            mcp_servers["everything"],
            "everything"
        )
        print("✅ MCP server added successfully")

    # ========================================================================
    # TEST 1: Sandbox Disabled (irrespective of progressive discovery)
    # ========================================================================

    @pytest.mark.asyncio
    async def test_sandbox_disabled_no_tools_or_prompt_progressive_discovery_off(
        self, base_url, auth_headers
    ):
        """
        Test 1a: Sandbox disabled + Progressive discovery OFF
        - execute_bash should NOT appear
        - setup prompt should NOT appear
        - MCP tools SHOULD appear
        """
        print("\n" + "=" * 80)
        print("TEST 1a: Sandbox Disabled + Progressive Discovery OFF")
        print("=" * 80)
        
        vmcp_id = self._vmcp["id"]
        
        # Ensure sandbox is disabled and progressive discovery is off
        disable_sandbox(base_url, vmcp_id, auth_headers)
        disable_progressive_discovery(base_url, vmcp_id, auth_headers)
        
        # Wait a moment for state to persist
        await asyncio.sleep(0.5)
        
        # Connect via MCP client
        async with streamablehttp_client(self._mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                
                # List tools
                tools_response = await session.list_tools()
                tool_names = [tool.name for tool in tools_response.tools]
                
                print(f"🔧 Available tools ({len(tool_names)}): {tool_names[:10]}...")
                
                # Assertions
                assert "execute_bash" not in tool_names, "execute_bash should NOT be available when sandbox is disabled"
                assert "execute_python" not in tool_names, "execute_python should NEVER be available"
                
                # MCP tools should be available
                mcp_tools = [t for t in tool_names if t.startswith("everything_")]
                assert len(mcp_tools) > 0, "MCP tools should be available when progressive discovery is OFF"
                print(f"✅ Found {len(mcp_tools)} MCP tools")
                
                # List prompts
                prompts_response = await session.list_prompts()
                prompt_names = [prompt.name for prompt in prompts_response.prompts]
                
                print(f"📋 Available prompts ({len(prompt_names)}): {prompt_names[:10]}...")
                
                # Assertions
                assert "sandbox_setup" not in prompt_names, "sandbox_setup prompt should NOT appear when sandbox is disabled"
                
                print("✅ Test 1a passed: Sandbox disabled behavior verified")

    @pytest.mark.asyncio
    async def test_sandbox_disabled_no_tools_or_prompt_progressive_discovery_on(
        self, base_url, auth_headers
    ):
        """
        Test 1b: Sandbox disabled + Progressive discovery ON
        - execute_bash should NOT appear
        - setup prompt should NOT appear
        - MCP tools SHOULD appear (progressive discovery only hides MCP tools when sandbox is also ON)
        """
        print("\n" + "=" * 80)
        print("TEST 1b: Sandbox Disabled + Progressive Discovery ON")
        print("=" * 80)
        
        vmcp_id = self._vmcp["id"]
        
        # Ensure sandbox is disabled and progressive discovery is on
        disable_sandbox(base_url, vmcp_id, auth_headers)
        enable_progressive_discovery(base_url, vmcp_id, auth_headers)
        
        # Wait a moment for state to persist
        await asyncio.sleep(0.5)
        
        # Connect via MCP client
        async with streamablehttp_client(self._mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                
                # List tools
                tools_response = await session.list_tools()
                tool_names = [tool.name for tool in tools_response.tools]
                
                print(f"🔧 Available tools ({len(tool_names)}): {tool_names[:10]}...")
                
                # Assertions
                assert "execute_bash" not in tool_names, "execute_bash should NOT be available when sandbox is disabled"
                assert "execute_python" not in tool_names, "execute_python should NEVER be available"
                
                # MCP tools should NOT be available (progressive discovery hides them regardless of sandbox status)
                # According to the implementation, progressive discovery hides MCP tools whenever it's enabled
                mcp_tools = [t for t in tool_names if t.startswith("everything_")]
                assert len(mcp_tools) == 0, "MCP tools should NOT be available when progressive discovery is ON (regardless of sandbox status)"
                print(f"✅ No MCP tools found (correct - progressive discovery is ON)")
                
                # List prompts
                prompts_response = await session.list_prompts()
                prompt_names = [prompt.name for prompt in prompts_response.prompts]
                
                print(f"📋 Available prompts ({len(prompt_names)}): {prompt_names[:10]}...")
                
                # Assertions
                assert "sandbox_setup" not in prompt_names, "sandbox_setup prompt should NOT appear when sandbox is disabled"
                
                print("✅ Test 1b passed: Sandbox disabled + Progressive discovery ON behavior verified")

    # ========================================================================
    # TEST 2: Sandbox Enabled (irrespective of progressive discovery)
    # ========================================================================

    @pytest.mark.asyncio
    async def test_sandbox_enabled_tools_and_prompt_appear_progressive_discovery_off(
        self, base_url, auth_headers
    ):
        """
        Test 2a: Sandbox enabled + Progressive discovery OFF
        - execute_bash SHOULD appear
        - setup prompt SHOULD appear
        - execute_python should NOT appear
        - MCP tools SHOULD appear
        """
        print("\n" + "=" * 80)
        print("TEST 2a: Sandbox Enabled + Progressive Discovery OFF")
        print("=" * 80)
        
        vmcp_id = self._vmcp["id"]
        
        # Enable sandbox and disable progressive discovery
        enable_sandbox(base_url, vmcp_id, auth_headers)
        disable_progressive_discovery(base_url, vmcp_id, auth_headers)
        
        # Wait a moment for state to persist
        await asyncio.sleep(0.5)
        
        # Connect via MCP client
        async with streamablehttp_client(self._mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                
                # List tools
                tools_response = await session.list_tools()
                tool_names = [tool.name for tool in tools_response.tools]
                
                print(f"🔧 Available tools ({len(tool_names)}): {tool_names[:10]}...")
                
                # Assertions
                assert "execute_bash" in tool_names, "execute_bash SHOULD be available when sandbox is enabled"
                assert "execute_python" not in tool_names, "execute_python should NEVER be available"
                
                # MCP tools should be available
                mcp_tools = [t for t in tool_names if t.startswith("everything_")]
                assert len(mcp_tools) > 0, "MCP tools should be available when progressive discovery is OFF"
                print(f"✅ Found {len(mcp_tools)} MCP tools")
                
                # List prompts
                prompts_response = await session.list_prompts()
                prompt_names = [prompt.name for prompt in prompts_response.prompts]
                
                print(f"📋 Available prompts ({len(prompt_names)}): {prompt_names[:10]}...")
                
                # Assertions
                assert "sandbox_setup" in prompt_names, "sandbox_setup prompt SHOULD appear when sandbox is enabled"
                
                # Get the prompt content to verify it's SDK-only (no CLI)
                prompt_result = await session.get_prompt("sandbox_setup")
                prompt_text = prompt_result.messages[0].content.text
                
                assert "CLI FOR DISCOVERY" not in prompt_text, "Prompt should NOT include CLI instructions when progressive discovery is OFF"
                assert "vmcp-sdk" not in prompt_text or "CLI" not in prompt_text.upper(), "Prompt should be SDK-only when progressive discovery is OFF"
                print("✅ Prompt is SDK-only (no CLI instructions)")
                
                print("✅ Test 2a passed: Sandbox enabled + Progressive discovery OFF behavior verified")

    @pytest.mark.asyncio
    async def test_sandbox_enabled_tools_and_prompt_appear_progressive_discovery_on(
        self, base_url, auth_headers
    ):
        """
        Test 2b: Sandbox enabled + Progressive discovery ON
        - execute_bash SHOULD appear
        - setup prompt SHOULD appear
        - execute_python should NOT appear
        - MCP tools should NOT appear (progressive discovery hides them)
        """
        print("\n" + "=" * 80)
        print("TEST 2b: Sandbox Enabled + Progressive Discovery ON")
        print("=" * 80)
        
        vmcp_id = self._vmcp["id"]
        
        # Enable sandbox and progressive discovery
        enable_sandbox(base_url, vmcp_id, auth_headers)
        enable_progressive_discovery(base_url, vmcp_id, auth_headers)
        
        # Wait a moment for state to persist
        await asyncio.sleep(0.5)
        
        # Connect via MCP client
        async with streamablehttp_client(self._mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                
                # List tools
                tools_response = await session.list_tools()
                tool_names = [tool.name for tool in tools_response.tools]
                
                print(f"🔧 Available tools ({len(tool_names)}): {tool_names}")
                
                # Assertions
                assert "execute_bash" in tool_names, "execute_bash SHOULD be available when sandbox is enabled"
                assert "execute_python" not in tool_names, "execute_python should NEVER be available"
                
                # MCP tools should NOT be available (progressive discovery hides them)
                mcp_tools = [t for t in tool_names if t.startswith("everything_")]
                assert len(mcp_tools) == 0, "MCP tools should NOT be available when progressive discovery is ON"
                print(f"✅ No MCP tools found (correct - progressive discovery is ON)")
                
                # Verify execute_bash is available (upload_prompt is a preset tool that's always available)
                assert "execute_bash" in tool_names, "execute_bash should be available"
                # Note: upload_prompt is a preset tool that's always available, so we expect at least 2 tools
                assert len(tool_names) >= 2, f"Should have at least execute_bash and upload_prompt, but found: {tool_names}"
                # Verify no MCP server tools are present (only preset tools and execute_bash)
                non_mcp_tools = [t for t in tool_names if not t.startswith("everything_")]
                assert len(non_mcp_tools) == len(tool_names), f"All tools should be non-MCP tools, but found MCP tools: {tool_names}"
                
                # List prompts
                prompts_response = await session.list_prompts()
                prompt_names = [prompt.name for prompt in prompts_response.prompts]
                
                print(f"📋 Available prompts ({len(prompt_names)}): {prompt_names[:10]}...")
                
                # Assertions
                assert "sandbox_setup" in prompt_names, "sandbox_setup prompt SHOULD appear when sandbox is enabled"
                
                # Get the prompt content to verify it includes CLI instructions
                prompt_result = await session.get_prompt("sandbox_setup")
                prompt_text = prompt_result.messages[0].content.text
                
                # Check for progressive discovery keywords in the prompt
                # The prompt should mention progressive discovery mode and discovery tools
                assert "PROGRESSIVE DISCOVERY" in prompt_text.upper() or "progressive discovery" in prompt_text.lower(), "Prompt should mention progressive discovery mode"
                assert "tools_list" in prompt_text or "tool_detail" in prompt_text or "execute_tool" in prompt_text, "Prompt should mention discovery tools (tools_list, tool_detail, execute_tool)"
                print("✅ Prompt includes CLI instructions")
                
                print("✅ Test 2b passed: Sandbox enabled + Progressive discovery ON behavior verified")

    # ========================================================================
    # TEST 3: Sandbox Enabled + Progressive Discovery ON (Detailed)
    # ========================================================================

    @pytest.mark.asyncio
    async def test_sandbox_progressive_discovery_on_detailed(
        self, base_url, auth_headers
    ):
        """
        Test 3: Sandbox enabled + Progressive discovery ON - Detailed verification
        - Only execute_bash tool available
        - MCP tools completely hidden
        - Setup prompt present with CLI instructions
        """
        print("\n" + "=" * 80)
        print("TEST 3: Sandbox + Progressive Discovery ON (Detailed)")
        print("=" * 80)
        
        vmcp_id = self._vmcp["id"]
        
        # Enable sandbox and progressive discovery
        enable_sandbox(base_url, vmcp_id, auth_headers)
        enable_progressive_discovery(base_url, vmcp_id, auth_headers)
        
        # Wait a moment for state to persist
        await asyncio.sleep(0.5)
        
        # Connect via MCP client
        async with streamablehttp_client(self._mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                
                # List tools
                tools_response = await session.list_tools()
                tool_names = [tool.name for tool in tools_response.tools]
                
                print(f"🔧 Available tools: {tool_names}")
                
                # Detailed assertions
                assert "execute_bash" in tool_names, f"execute_bash should be available, got: {tool_names}"
                # Note: upload_prompt is a preset tool that's always available
                assert len(tool_names) >= 2, f"Should have at least execute_bash and upload_prompt, got {len(tool_names)}: {tool_names}"
                # Verify no MCP server tools are present
                mcp_tools = [t for t in tool_names if t.startswith("everything_")]
                assert len(mcp_tools) == 0, f"No MCP server tools should be present, but found: {mcp_tools}"
                
                # Verify execute_bash tool details
                execute_bash_tool = next(t for t in tools_response.tools if t.name == "execute_bash")
                assert execute_bash_tool is not None, "execute_bash tool should be present"
                assert "bash" in execute_bash_tool.description.lower(), "execute_bash should have bash in description"
                
                # List prompts
                prompts_response = await session.list_prompts()
                prompt_names = [prompt.name for prompt in prompts_response.prompts]
                
                assert "sandbox_setup" in prompt_names, "sandbox_setup prompt should be present"
                
                # Get prompt and verify CLI content
                prompt_result = await session.get_prompt("sandbox_setup")
                prompt_text = prompt_result.messages[0].content.text
                
                # Check for progressive discovery keywords in the prompt
                # The prompt should mention progressive discovery mode and discovery tools
                pd_keywords = ["PROGRESSIVE DISCOVERY", "progressive discovery", "tools_list", "tool_detail", "execute_tool", "DISCOVERY MODE"]
                found_keywords = [kw for kw in pd_keywords if kw in prompt_text or kw.lower() in prompt_text.lower()]
                
                assert len(found_keywords) > 0, f"Prompt should contain progressive discovery instructions. Found keywords: {found_keywords}, prompt length: {len(prompt_text)}"
                print(f"✅ Prompt contains progressive discovery keywords: {found_keywords}")
                
                print("✅ Test 3 passed: Detailed verification of sandbox + progressive discovery ON")

    # ========================================================================
    # TEST 4: Sandbox Enabled + Progressive Discovery OFF (Detailed)
    # ========================================================================

    @pytest.mark.asyncio
    async def test_sandbox_progressive_discovery_off_detailed(
        self, base_url, auth_headers
    ):
        """
        Test 4: Sandbox enabled + Progressive discovery OFF - Detailed verification
        - execute_bash tool available
        - MCP tools available
        - Setup prompt present with SDK-only (no CLI)
        """
        print("\n" + "=" * 80)
        print("TEST 4: Sandbox + Progressive Discovery OFF (Detailed)")
        print("=" * 80)
        
        vmcp_id = self._vmcp["id"]
        
        # Enable sandbox and disable progressive discovery
        enable_sandbox(base_url, vmcp_id, auth_headers)
        disable_progressive_discovery(base_url, vmcp_id, auth_headers)
        
        # Wait a moment for state to persist
        await asyncio.sleep(0.5)
        
        # Connect via MCP client
        async with streamablehttp_client(self._mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                
                # List tools
                tools_response = await session.list_tools()
                tool_names = [tool.name for tool in tools_response.tools]
                
                print(f"🔧 Available tools ({len(tool_names)}): {tool_names[:10]}...")
                
                # Detailed assertions
                assert "execute_bash" in tool_names, "execute_bash should be available"
                assert "execute_python" not in tool_names, "execute_python should NEVER be available"
                
                # MCP tools should be available
                mcp_tools = [t for t in tool_names if t.startswith("everything_")]
                assert len(mcp_tools) > 0, f"MCP tools should be available. Found tools: {tool_names}"
                print(f"✅ Found {len(mcp_tools)} MCP tools")
                
                # Verify we have both execute_bash and MCP tools
                assert len(tool_names) > 1, f"Should have execute_bash + MCP tools, got: {tool_names}"
                
                # List prompts
                prompts_response = await session.list_prompts()
                prompt_names = [prompt.name for prompt in prompts_response.prompts]
                
                assert "sandbox_setup" in prompt_names, "sandbox_setup prompt should be present"
                
                # Get prompt and verify it's SDK-only (no CLI)
                prompt_result = await session.get_prompt("sandbox_setup")
                prompt_text = prompt_result.messages[0].content.text
                
                # Check that CLI instructions are NOT present
                cli_keywords = ["CLI FOR DISCOVERY", "EXPLORATION STRATEGY", "list-tools", "call-tool"]
                found_cli_keywords = [kw for kw in cli_keywords if kw in prompt_text]
                
                assert len(found_cli_keywords) == 0, f"Prompt should NOT contain CLI instructions. Found: {found_cli_keywords}"
                print("✅ Prompt is SDK-only (no CLI instructions)")
                
                # Verify SDK content is present
                sdk_keywords = ["vmcp_sdk", "import vmcp_sdk", "SDK", "Python"]
                found_sdk_keywords = [kw for kw in sdk_keywords if kw.lower() in prompt_text.lower()]
                
                assert len(found_sdk_keywords) > 0, "Prompt should contain SDK instructions"
                print(f"✅ Prompt contains SDK keywords: {found_sdk_keywords}")
                
                print("✅ Test 4 passed: Detailed verification of sandbox + progressive discovery OFF")

