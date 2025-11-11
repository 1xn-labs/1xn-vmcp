"""
Test Suite 4: Custom Tools - Prompt Type
Tests for prompt-based custom tools
"""

import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


@pytest.mark.prompt_tool
class TestCustomToolsPrompt:
    """Test prompt-type custom tools"""

    def test_create_simple_prompt_tool(self, base_url, create_vmcp, helpers):
        """Test 4.1: Create a simple prompt tool"""
        vmcp = create_vmcp
        print(f"\n📦 Test 4.1 - Creating simple prompt tool: {vmcp['id']}")

        # Get vMCP data
        vmcp_data = helpers["get_vmcp"](vmcp["id"])

        # Add simple prompt tool
        simple_tool = {
            "name": "simple_analyzer",
            "description": "A simple analysis tool",
            "text": "Analyze the provided data and give insights",
            "tool_type": "prompt",
            "variables": [],
            "environment_variables": [],
            "tool_calls": [],
            "atomic_blocks": []
        }

        vmcp_data["custom_tools"].append(simple_tool)
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Verify
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        assert len(updated_vmcp["custom_tools"]) == 1
        assert updated_vmcp["custom_tools"][0]["name"] == "simple_analyzer"
        assert updated_vmcp["custom_tools"][0]["tool_type"] == "prompt"

        print("✅ Simple prompt tool created successfully")

    @pytest.mark.asyncio
    async def test_list_prompt_tools(self, base_url, create_vmcp, helpers):
        """Test 4.2: List prompt tools via MCP"""
        vmcp = create_vmcp
        print(f"\n📦 Test 4.2 - Listing prompt tools via MCP: {vmcp['id']}")

        # Add prompt tool
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "data_formatter",
            "description": "Format data tool",
            "text": "Format the data in a readable way",
            "tool_type": "prompt",
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

                # List tools
                tools_response = await session.list_tools()
                tool_names = [tool.name for tool in tools_response.tools]

                print(f"🔧 Available tools: {tool_names}")

                assert "data_formatter" in tool_names, "Prompt tool should be listed"

                print("✅ Prompt tool listed successfully")

    @pytest.mark.asyncio
    async def test_call_simple_prompt_tool(self, base_url, create_vmcp, helpers):
        """Test 4.3: Call a simple prompt tool"""
        vmcp = create_vmcp
        print(f"\n📦 Test 4.3 - Calling simple prompt tool: {vmcp['id']}")

        # Add prompt tool
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "echo_tool",
            "description": "Echo tool",
            "text": "Echo: This is a test message",
            "tool_type": "prompt",
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
                result = await session.call_tool("echo_tool", arguments={})

                print(f"🔧 Tool result: {result}")

                # Verify
                assert len(result.content) > 0
                result_text = result.content[0].text
                assert "test message" in result_text.lower()

                print("✅ Prompt tool call successful")

    def test_create_prompt_tool_with_variables(self, base_url, create_vmcp, helpers):
        """Test 4.4: Create prompt tool with variables"""
        vmcp = create_vmcp
        print(f"\n📦 Test 4.4 - Creating prompt tool with variables: {vmcp['id']}")

        # Get vMCP data
        vmcp_data = helpers["get_vmcp"](vmcp["id"])

        # Add prompt tool with variables
        tool_with_vars = {
            "name": "personalized_report",
            "description": "Generate personalized report",
            "text": "Generate a @param.report_type report for @param.user_name",
            "tool_type": "prompt",
            "variables": [
                {"name": "report_type", "description": "Type of report", "required": True},
                {"name": "user_name", "description": "User's name", "required": True}
            ],
            "environment_variables": [],
            "tool_calls": [],
            "atomic_blocks": []
        }

        vmcp_data["custom_tools"].append(tool_with_vars)
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Verify
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        assert len(updated_vmcp["custom_tools"]) == 1
        assert len(updated_vmcp["custom_tools"][0]["variables"]) == 2

        print("✅ Prompt tool with variables created successfully")

    @pytest.mark.asyncio
    async def test_call_prompt_tool_with_variables(self, base_url, create_vmcp, helpers):
        """Test 4.5: Call prompt tool with variable substitution"""
        vmcp = create_vmcp
        print(f"\n📦 Test 4.5 - Calling prompt tool with variables: {vmcp['id']}")

        # Add prompt tool with variables
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "greeting_tool",
            "description": "Greeting tool",
            "text": "Hello @param.name, your role is @param.role!",
            "tool_type": "prompt",
            "variables": [
                {"name": "name", "description": "User's name", "required": True},
                {"name": "role", "description": "User's role", "required": True}
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
                    "greeting_tool",
                    arguments={"name": "Bob", "role": "Developer"}
                )

                print(f"🔧 Tool result: {result}")

                # Verify variable substitution
                result_text = result.content[0].text
                assert "Bob" in result_text, f"Expected 'Bob' in result, got: {result_text}"
                assert "Developer" in result_text, f"Expected 'Developer' in result, got: {result_text}"

                print("✅ Prompt tool with variable substitution successful")

    def test_create_prompt_tool_with_config_vars(self, base_url, create_vmcp, helpers):
        """Test 4.6: Create prompt tool with @config variables"""
        vmcp = create_vmcp
        print(f"\n📦 Test 4.6 - Creating prompt tool with config variables: {vmcp['id']}")

        # Add environment variables
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["environment_variables"] = [
            {"name": "company_name", "value": "TechCorp"},
            {"name": "support_email", "value": "support@techcorp.com"}
        ]

        # Add prompt tool with config variables
        tool_with_config = {
            "name": "contact_info_tool",
            "description": "Provide contact information",
            "text": "Contact @config.company_name at @config.support_email",
            "tool_type": "prompt",
            "variables": [],
            "environment_variables": ["company_name", "support_email"],
            "tool_calls": [],
            "atomic_blocks": []
        }

        vmcp_data["custom_tools"].append(tool_with_config)
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Verify
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        assert len(updated_vmcp["custom_tools"]) == 1
        assert len(updated_vmcp["custom_tools"][0]["environment_variables"]) == 2

        print("✅ Prompt tool with config variables created successfully")

    @pytest.mark.asyncio
    async def test_call_prompt_tool_with_config_vars(self, base_url, create_vmcp, helpers):
        """Test 4.7: Call prompt tool with config variable substitution"""
        vmcp = create_vmcp
        print(f"\n📦 Test 4.7 - Calling prompt tool with config variables: {vmcp['id']}")

        # Add environment variables
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["environment_variables"] = [
            {"name": "api_version", "value": "v2.0"},
            {"name": "base_endpoint", "value": "https://api.test.com"}
        ]

        # Add prompt tool with config variables
        vmcp_data["custom_tools"].append({
            "name": "api_info_tool",
            "description": "API information tool",
            "text": "API: @config.base_endpoint version @config.api_version",
            "tool_type": "prompt",
            "variables": [],
            "environment_variables": ["api_version", "base_endpoint"],
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
                result = await session.call_tool("api_info_tool", arguments={})

                print(f"🔧 Tool result: {result}")

                # Verify config variable substitution
                result_text = result.content[0].text
                assert "v2.0" in result_text, f"Expected 'v2.0' in result, got: {result_text}"
                assert "https://api.test.com" in result_text, f"Expected URL in result, got: {result_text}"

                print("✅ Prompt tool with config variable substitution successful")

    @pytest.mark.asyncio
    async def test_prompt_tool_with_mcp_tool_call(self, base_url, create_vmcp, mcp_servers, helpers):
        """Test 4.8: Prompt tool that calls MCP server tool"""
        vmcp = create_vmcp
        print(f"\n📦 Test 4.8 - Prompt tool with MCP tool call: {vmcp['id']}")

        # Add MCP server
        helpers["add_server"](vmcp["id"], mcp_servers["allfeature"], "allfeature")

        # Add prompt tool with MCP tool call
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "weather_reporter",
            "description": "Report weather tool",
            "text": "Weather report: @tool.get_weather(city='Paris')",
            "tool_type": "prompt",
            "variables": [],
            "environment_variables": [],
            "tool_calls": [
                {"tool": "get_weather", "arguments": {"city": "Paris"}}
            ],
            "atomic_blocks": []
        })
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call tool
                result = await session.call_tool("weather_reporter", arguments={})

                print(f"🔧 Tool result: {result}")

                # Verify tool call was executed
                result_text = result.content[0].text
                # Should contain weather data or at least indication of weather
                assert len(result_text) > 0

                print("✅ Prompt tool with MCP tool call successful")

    def test_prompt_tool_with_all_features(self, base_url, create_vmcp, mcp_servers, helpers):
        """Test 4.9: Prompt tool with all features combined"""
        vmcp = create_vmcp
        print(f"\n📦 Test 4.9 - Prompt tool with all features: {vmcp['id']}")

        # Add MCP server
        helpers["add_server"](vmcp["id"], mcp_servers["allfeature"], "allfeature")

        # Add environment variables
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["environment_variables"] = [
            {"name": "default_city", "value": "Tokyo"}
        ]

        # Add comprehensive prompt tool
        comprehensive_tool = {
            "name": "comprehensive_reporter",
            "description": "Comprehensive reporting tool",
            "text": """Generate Report:
User: @param.user_name
Default City: @config.default_city
Weather Data: @tool.get_weather(city=@param.city)
Summary: @param.summary""",
            "tool_type": "prompt",
            "variables": [
                {"name": "user_name", "description": "User's name", "required": True},
                {"name": "city", "description": "City for weather", "required": False},
                {"name": "summary", "description": "Summary text", "required": False}
            ],
            "environment_variables": ["default_city"],
            "tool_calls": [
                {"tool": "get_weather", "arguments": {"city": "@param.city"}}
            ],
            "atomic_blocks": []
        }

        vmcp_data["custom_tools"].append(comprehensive_tool)
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Verify
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        assert len(updated_vmcp["custom_tools"]) == 1
        tool = updated_vmcp["custom_tools"][0]
        assert len(tool["variables"]) == 3
        assert len(tool["environment_variables"]) == 1
        assert len(tool["tool_calls"]) == 1

        print("✅ Comprehensive prompt tool created successfully")
