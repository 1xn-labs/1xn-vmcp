"""
Test Suite 3: Custom Prompts
Tests custom prompts with variables, tool calls, resources, and system variables
"""

import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


@pytest.mark.custom_prompts
class TestCustomPrompts:
    """Test custom prompts functionality"""

    def test_create_simple_prompt(self, base_url, create_vmcp, helpers):
        """Test 3.1: Create a simple custom prompt without variables"""
        vmcp = create_vmcp
        print(f"\n📦 Test 3.1 - Creating simple custom prompt: {vmcp['id']}")

        # Get vMCP data
        vmcp_data = helpers["get_vmcp"](vmcp["id"])

        # Add simple prompt
        simple_prompt = {
            "name": "simple_greeting",
            "description": "A simple greeting prompt",
            "text": "Say hello to the user in a friendly manner",
            "variables": [],
            "environment_variables": [],
            "tool_calls": []
        }

        vmcp_data["custom_prompts"].append(simple_prompt)

        # Update vMCP
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Verify
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        assert len(updated_vmcp["custom_prompts"]) == 1
        assert updated_vmcp["custom_prompts"][0]["name"] == "simple_greeting"
        assert updated_vmcp["custom_prompts"][0]["text"] == "Say hello to the user in a friendly manner"

        print("✅ Simple prompt created successfully")

    @pytest.mark.asyncio
    async def test_list_custom_prompt(self, base_url, create_vmcp, helpers):
        """Test 3.2: List custom prompts via MCP"""
        vmcp = create_vmcp
        print(f"\n📦 Test 3.2 - Listing custom prompts via MCP: {vmcp['id']}")

        # Add a custom prompt
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_prompts"].append({
            "name": "test_prompt",
            "description": "Test prompt",
            "text": "This is a test prompt",
            "variables": [],
            "environment_variables": [],
            "tool_calls": []
        })
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # List prompts
                prompts_response = await session.list_prompts()
                prompt_names = [prompt.name for prompt in prompts_response.prompts]

                print(f"📋 Available prompts: {prompt_names}")

                assert "test_prompt" in prompt_names, "Custom prompt should be listed"

                print("✅ Custom prompt listed successfully")

    @pytest.mark.asyncio
    async def test_get_custom_prompt(self, base_url, create_vmcp, helpers):
        """Test 3.3: Get a custom prompt via MCP"""
        vmcp = create_vmcp
        print(f"\n📦 Test 3.3 - Getting custom prompt via MCP: {vmcp['id']}")

        # Add a custom prompt
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_prompts"].append({
            "name": "get_test_prompt",
            "description": "Prompt for testing get operation",
            "text": "Please analyze the following data carefully",
            "variables": [],
            "environment_variables": [],
            "tool_calls": []
        })
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Get prompt
                result = await session.get_prompt("get_test_prompt")

                print(f"📋 Prompt result: {result}")

                # Verify
                assert len(result.messages) > 0
                prompt_text = result.messages[0].content.text
                assert "analyze" in prompt_text.lower()
                assert "data" in prompt_text.lower()

                print("✅ Custom prompt retrieved successfully")

    def test_create_prompt_with_variables(self, base_url, create_vmcp, helpers):
        """Test 3.4: Create prompt with @param variables"""
        vmcp = create_vmcp
        print(f"\n📦 Test 3.4 - Creating prompt with variables: {vmcp['id']}")

        # Get vMCP data
        vmcp_data = helpers["get_vmcp"](vmcp["id"])

        # Add prompt with variables
        prompt_with_vars = {
            "name": "greet_in_language",
            "description": "Greet user in specific language",
            "text": "Greet the user @param.name in @param.language language",
            "variables": [
                {"name": "name", "description": "User's name", "required": True},
                {"name": "language", "description": "Language for greeting", "required": True}
            ],
            "environment_variables": [],
            "tool_calls": []
        }

        vmcp_data["custom_prompts"].append(prompt_with_vars)
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Verify
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        assert len(updated_vmcp["custom_prompts"]) == 1
        assert len(updated_vmcp["custom_prompts"][0]["variables"]) == 2

        print("✅ Prompt with variables created successfully")

    @pytest.mark.asyncio
    async def test_call_prompt_with_variables(self, base_url, create_vmcp, helpers):
        """Test 3.5: Call prompt with variable substitution"""
        vmcp = create_vmcp
        print(f"\n📦 Test 3.5 - Calling prompt with variables: {vmcp['id']}")

        # Add prompt with variables
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_prompts"].append({
            "name": "personalized_greeting",
            "description": "Personalized greeting",
            "text": "Hello @param.name, welcome to @param.location!",
            "variables": [
                {"name": "name", "description": "User's name", "required": True},
                {"name": "location", "description": "Location", "required": True}
            ],
            "environment_variables": [],
            "tool_calls": []
        })
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Get prompt with arguments
                result = await session.get_prompt(
                    "personalized_greeting",
                    arguments={"name": "Alice", "location": "Wonderland"}
                )

                print(f"📋 Prompt result: {result}")

                # Verify variable substitution
                prompt_text = result.messages[0].content.text
                assert "Alice" in prompt_text, f"Expected 'Alice' in prompt, got: {prompt_text}"
                assert "Wonderland" in prompt_text, f"Expected 'Wonderland' in prompt, got: {prompt_text}"

                print("✅ Prompt with variable substitution successful")

    def test_create_prompt_with_config_variables(self, base_url, create_vmcp, helpers):
        """Test 3.6: Create prompt with @config system variables"""
        vmcp = create_vmcp
        print(f"\n📦 Test 3.6 - Creating prompt with config variables: {vmcp['id']}")

        # First, add environment variables to vMCP
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["environment_variables"] = [
            {"name": "api_key", "value": "test-api-key-123"},
            {"name": "base_url", "value": "https://api.example.com"}
        ]

        # Add prompt with config variables
        prompt_with_config = {
            "name": "api_request_prompt",
            "description": "Prompt using API configuration",
            "text": "Make a request to @config.base_url using API key @config.api_key",
            "variables": [],
            "environment_variables": ["api_key", "base_url"],
            "tool_calls": []
        }

        vmcp_data["custom_prompts"].append(prompt_with_config)
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Verify
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        assert len(updated_vmcp["custom_prompts"]) == 1
        assert len(updated_vmcp["custom_prompts"][0]["environment_variables"]) == 2

        print("✅ Prompt with config variables created successfully")

    @pytest.mark.asyncio
    async def test_call_prompt_with_config_variables(self, base_url, create_vmcp, helpers):
        """Test 3.7: Call prompt with config variable substitution"""
        vmcp = create_vmcp
        print(f"\n📦 Test 3.7 - Calling prompt with config variables: {vmcp['id']}")

        # Save environment variables using the proper endpoint
        helpers["save_env_vars"](vmcp["id"], [
            {"name": "service_name", "value": "TestService"},
            {"name": "version", "value": "1.0.0"}
        ])

        # Add prompt with config variables
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_prompts"].append({
            "name": "system_info_prompt",
            "description": "System info prompt",
            "text": "Connect to @config.service_name version @config.version",
            "variables": [],
            "environment_variables": ["service_name", "version"],
            "tool_calls": []
        })
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Get prompt
                result = await session.get_prompt("system_info_prompt")

                print(f"📋 Prompt result: {result}")

                # Verify config variable substitution
                prompt_text = result.messages[0].content.text
                assert "TestService" in prompt_text, f"Expected 'TestService' in prompt, got: {prompt_text}"
                assert "1.0.0" in prompt_text, f"Expected '1.0.0' in prompt, got: {prompt_text}"

                print("✅ Prompt with config variable substitution successful")

    def test_create_prompt_with_tool_call(self, base_url, create_vmcp, mcp_servers, helpers):
        """Test 3.8: Create prompt with @tool call"""
        vmcp = create_vmcp
        print(f"\n📦 Test 3.8 - Creating prompt with tool call: {vmcp['id']}")

        # Add MCP server first
        helpers["add_server"](vmcp["id"], mcp_servers["allfeature"], "allfeature")

        # Get vMCP data
        vmcp_data = helpers["get_vmcp"](vmcp["id"])

        # Add prompt with tool call
        prompt_with_tool = {
            "name": "weather_analysis_prompt",
            "description": "Analyze weather data",
            "text": "Get the current weather: @tool.get_weather(city='London') and analyze it",
            "variables": [],
            "environment_variables": [],
            "tool_calls": [
                {"tool": "get_weather", "arguments": {"city": "London"}}
            ]
        }

        vmcp_data["custom_prompts"].append(prompt_with_tool)
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Verify
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        assert len(updated_vmcp["custom_prompts"]) == 1
        assert len(updated_vmcp["custom_prompts"][0]["tool_calls"]) == 1

        print("✅ Prompt with tool call created successfully")

    def test_create_prompt_with_prompt_reference(self, base_url, create_vmcp, helpers):
        """Test 3.9: Create prompt that references another prompt"""
        vmcp = create_vmcp
        print(f"\n📦 Test 3.9 - Creating prompt with prompt reference: {vmcp['id']}")

        # Get vMCP data
        vmcp_data = helpers["get_vmcp"](vmcp["id"])

        # Add base prompt
        vmcp_data["custom_prompts"].append({
            "name": "base_greeting",
            "description": "Base greeting",
            "text": "Hello, welcome!",
            "variables": [],
            "environment_variables": [],
            "tool_calls": []
        })

        # Add prompt that references base prompt
        vmcp_data["custom_prompts"].append({
            "name": "extended_greeting",
            "description": "Extended greeting with base",
            "text": "@prompt.base_greeting Now let me help you with your questions.",
            "variables": [],
            "environment_variables": [],
            "tool_calls": []
        })

        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Verify
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        assert len(updated_vmcp["custom_prompts"]) == 2
        assert "@prompt.base_greeting" in updated_vmcp["custom_prompts"][1]["text"]

        print("✅ Prompt with prompt reference created successfully")

    def test_create_prompt_with_resource(self, base_url, create_vmcp, mcp_servers, helpers):
        """Test 3.10: Create prompt with @resource reference"""
        vmcp = create_vmcp
        print(f"\n📦 Test 3.10 - Creating prompt with resource reference: {vmcp['id']}")

        # Add MCP server
        helpers["add_server"](vmcp["id"], mcp_servers["everything"], "everything")

        # Get vMCP data
        vmcp_data = helpers["get_vmcp"](vmcp["id"])

        # Add prompt with resource
        prompt_with_resource = {
            "name": "dashboard_analysis_prompt",
            "description": "Analyze dashboard data",
            "text": "Analyze the following dashboard data: @resource.everything://dashboard",
            "variables": [],
            "environment_variables": [],
            "tool_calls": []
        }

        vmcp_data["custom_prompts"].append(prompt_with_resource)
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Verify
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        assert len(updated_vmcp["custom_prompts"]) == 1
        assert "@resource.everything://dashboard" in updated_vmcp["custom_prompts"][0]["text"]

        print("✅ Prompt with resource reference created successfully")

    def test_create_complex_prompt(self, base_url, create_vmcp, mcp_servers, helpers):
        """Test 3.11: Create prompt with all features combined"""
        vmcp = create_vmcp
        print(f"\n📦 Test 3.11 - Creating complex prompt with all features: {vmcp['id']}")

        # Add MCP server
        helpers["add_server"](vmcp["id"], mcp_servers["allfeature"], "allfeature")

        # Add environment variables
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["environment_variables"] = [
            {"name": "default_city", "value": "London"}
        ]

        # Add complex prompt
        complex_prompt = {
            "name": "comprehensive_analysis",
            "description": "Comprehensive analysis with all features",
            "text": """Analyze the following:
User: @param.user_name
City: @config.default_city
Weather: @tool.get_weather(city=@param.city)
Additional Info: @param.details""",
            "variables": [
                {"name": "user_name", "description": "User's name", "required": True},
                {"name": "city", "description": "City name", "required": False},
                {"name": "details", "description": "Additional details", "required": False}
            ],
            "environment_variables": ["default_city"],
            "tool_calls": [
                {"tool": "get_weather", "arguments": {"city": "@param.city"}}
            ]
        }

        vmcp_data["custom_prompts"].append(complex_prompt)
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Verify
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        assert len(updated_vmcp["custom_prompts"]) == 1
        prompt = updated_vmcp["custom_prompts"][0]
        assert len(prompt["variables"]) == 3
        assert len(prompt["environment_variables"]) == 1
        assert len(prompt["tool_calls"]) == 1

        print("✅ Complex prompt with all features created successfully")

    def test_create_prompt_with_add_tool_call(self, base_url, create_vmcp, mcp_servers, helpers):
        """Test 3.12: Create prompt with add tool call from allfeature server"""
        vmcp = create_vmcp
        print(f"\n📦 Test 3.12 - Creating prompt with add tool call: {vmcp['id']}")

        # Add allfeature MCP server
        helpers["add_server"](vmcp["id"], mcp_servers["allfeature"], "allfeature")

        # Get vMCP data
        vmcp_data = helpers["get_vmcp"](vmcp["id"])

        # Add prompt with add tool call
        # Format: @tool.<server_name>.<tool_name>(arguments)
        prompt_with_add_tool = {
            "name": "calculation_prompt",
            "description": "Calculate sum using add tool",
            "text": "Calculate the sum: @tool.allfeature.add(a: int = 5, b: int = 3)",
            "variables": [],
            "environment_variables": [],
            "tool_calls": [
                {"tool": "add", "arguments": {"a": 5, "b": 3}}
            ]
        }

        vmcp_data["custom_prompts"].append(prompt_with_add_tool)
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Verify
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        assert len(updated_vmcp["custom_prompts"]) == 1
        assert len(updated_vmcp["custom_prompts"][0]["tool_calls"]) == 1
        assert updated_vmcp["custom_prompts"][0]["tool_calls"][0]["tool"] == "add"
        assert updated_vmcp["custom_prompts"][0]["tool_calls"][0]["arguments"]["a"] == 5
        assert updated_vmcp["custom_prompts"][0]["tool_calls"][0]["arguments"]["b"] == 3
        assert "@tool.allfeature.add" in updated_vmcp["custom_prompts"][0]["text"]

        print("✅ Prompt with add tool call created successfully")

    @pytest.mark.asyncio
    async def test_call_prompt_with_add_tool_execution(self, base_url, create_vmcp, mcp_servers, helpers):
        """Test 3.13: Call prompt with add tool and verify execution"""
        vmcp = create_vmcp
        print(f"\n📦 Test 3.13 - Calling prompt with add tool execution: {vmcp['id']}")

        # Add allfeature MCP server
        helpers["add_server"](vmcp["id"], mcp_servers["allfeature"], "allfeature")

        # Get vMCP data
        vmcp_data = helpers["get_vmcp"](vmcp["id"])

        # Add prompt with add tool call
        vmcp_data["custom_prompts"].append({
            "name": "sum_calculation",
            "description": "Calculate sum of two numbers",
            "text": "The sum of 7 and 4 is: @tool.allfeature.add(a: int = 7, b: int = 4)",
            "variables": [],
            "environment_variables": [],
            "tool_calls": [
                {"tool": "add", "arguments": {"a": 7, "b": 4}}
            ]
        })
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Get prompt (this should execute the tool call)
                result = await session.get_prompt("sum_calculation")

                print(f"📋 Prompt result: {result}")

                # Verify tool was executed
                assert len(result.messages) > 0
                prompt_text = result.messages[0].content.text
                
                # The tool should have executed and returned the sum (11)
                assert "11" in prompt_text, f"Expected '11' in prompt result, got: {prompt_text}"

                print("✅ Prompt with add tool execution successful")

    def test_create_prompt_with_context7_tool_call(self, base_url, create_vmcp, mcp_servers, helpers):
        """Test 3.14: Create prompt with context7 resolve-library-id tool call"""
        vmcp = create_vmcp
        print(f"\n📦 Test 3.14 - Creating prompt with context7 tool call: {vmcp['id']}")

        # Add context7 MCP server
        helpers["add_server"](vmcp["id"], mcp_servers["context7"], "context7")

        # Get vMCP data
        vmcp_data = helpers["get_vmcp"](vmcp["id"])

        # Add prompt with context7 tool call
        prompt_with_context7_tool = {
            "name": "resolve_nextra_library",
            "description": "Resolve Nextra library ID using context7",
            "text": "@tool.context7.resolve-library-id(libraryName: str = \"Nextra\")",
            "variables": [],
            "environment_variables": [],
            "tool_calls": [
                {"tool": "resolve-library-id", "arguments": {"libraryName": "Nextra"}}
            ]
        }

        vmcp_data["custom_prompts"].append(prompt_with_context7_tool)
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Verify
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        assert len(updated_vmcp["custom_prompts"]) == 1
        assert len(updated_vmcp["custom_prompts"][0]["tool_calls"]) == 1
        assert updated_vmcp["custom_prompts"][0]["tool_calls"][0]["tool"] == "resolve-library-id"
        assert updated_vmcp["custom_prompts"][0]["tool_calls"][0]["arguments"]["libraryName"] == "Nextra"
        assert "@tool.context7.resolve-library-id" in updated_vmcp["custom_prompts"][0]["text"]

        print("✅ Prompt with context7 tool call created successfully")

    @pytest.mark.asyncio
    async def test_call_prompt_with_context7_tool_and_param(self, base_url, create_vmcp, mcp_servers, helpers):
        """Test 3.15: Call prompt with context7 tool using @param variable"""
        vmcp = create_vmcp
        print(f"\n📦 Test 3.15 - Calling prompt with context7 tool and parameter: {vmcp['id']}")

        # Add context7 MCP server
        helpers["add_server"](vmcp["id"], mcp_servers["context7"], "context7")

        # Get vMCP data
        vmcp_data = helpers["get_vmcp"](vmcp["id"])

        # Add prompt with context7 tool call using @param variable
        vmcp_data["custom_prompts"].append({
            "name": "resolve_library_by_name",
            "description": "Resolve library ID by name using context7",
            "text": "@tool.context7.resolve-library-id(libraryName: str = \"@param.libname\")",
            "variables": [
                {"name": "libname", "description": "Library name to resolve", "required": True}
            ],
            "environment_variables": [],
            "tool_calls": [
                {"tool": "resolve-library-id", "arguments": {"libraryName": "@param.libname"}}
            ]
        })
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Get prompt with library name argument
                result = await session.get_prompt(
                    "resolve_library_by_name",
                    arguments={"libname": "Typescript"}
                )

                print(f"📋 Prompt result: {result}")

                # Verify tool was executed
                assert len(result.messages) > 0
                prompt_text = result.messages[0].content.text
                
                # The output should contain "available libraries" and "typescript" (case-insensitive)
                prompt_text_lower = prompt_text.lower()
                assert "available libraries" in prompt_text_lower, \
                    f"Expected 'available libraries' in prompt result, got: {prompt_text}"
                assert "typescript" in prompt_text_lower, \
                    f"Expected 'typescript' in prompt result, got: {prompt_text}"

                print("✅ Prompt with context7 tool and parameter execution successful")

    def test_create_comprehensive_prompt_with_all_variations(self, base_url, create_vmcp, mcp_servers, helpers):
        """Test 3.16: Create comprehensive prompt with all variations: 2 params, 1 config, 1 tool with prefilled param, 1 tool with param, 1 prompt reference"""
        vmcp = create_vmcp
        print(f"\n📦 Test 3.16 - Creating comprehensive prompt with all variations: {vmcp['id']}")

        # Add MCP server
        helpers["add_server"](vmcp["id"], mcp_servers["allfeature"], "allfeature")

        # Add environment variable for @config
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["environment_variables"] = [
            {"name": "api_key", "value": "test-api-key-12345"}
        ]

        # First, create a base prompt that will be referenced
        base_prompt = {
            "name": "base_greeting",
            "description": "Base greeting prompt",
            "text": "Hello! Welcome to our service.",
            "variables": [],
            "environment_variables": [],
            "tool_calls": []
        }

        # Create comprehensive prompt with all variations
        comprehensive_prompt = {
            "name": "comprehensive_service",
            "description": "Comprehensive prompt with all feature variations",
            "text": """@prompt.base_greeting

User Information:
- Name: @param.user_name
- API Key: @config.api_key

Calculations:
- Static calculation: @tool.allfeature.add(a: int = 5, b: int = 3)

Weather Check:
- Get weather: @tool.allfeature.get_weather(city: str = "@param.city")

Please process the request for @param.user_name in @param.city.""",
            "variables": [
                {"name": "user_name", "description": "User's name", "required": True},
                {"name": "city", "description": "City name", "required": True}
            ],
            "environment_variables": ["api_key"],
            "tool_calls": [
                {"tool": "add", "arguments": {"a": 5, "b": 3}},
                {"tool": "get_weather", "arguments": {"city": "@param.city"}}
            ]
        }

        # Add both prompts
        vmcp_data["custom_prompts"].append(base_prompt)
        vmcp_data["custom_prompts"].append(comprehensive_prompt)
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Verify
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        assert len(updated_vmcp["custom_prompts"]) == 2
        
        # Find the comprehensive prompt
        comprehensive = None
        for prompt in updated_vmcp["custom_prompts"]:
            if prompt["name"] == "comprehensive_service":
                comprehensive = prompt
                break
        
        assert comprehensive is not None, "Comprehensive prompt not found"
        
        # Verify all features
        assert len(comprehensive["variables"]) == 2, f"Expected 2 variables, got {len(comprehensive['variables'])}"
        assert len(comprehensive["environment_variables"]) == 1, f"Expected 1 config variable, got {len(comprehensive['environment_variables'])}"
        assert len(comprehensive["tool_calls"]) == 2, f"Expected 2 tool calls, got {len(comprehensive['tool_calls'])}"
        
        # Verify variables
        var_names = [v["name"] for v in comprehensive["variables"]]
        assert "user_name" in var_names, "user_name variable not found"
        assert "city" in var_names, "city variable not found"
        
        # Verify config variable
        assert "api_key" in comprehensive["environment_variables"], "api_key config variable not found"
        
        # Verify tool calls
        tool_names = [tc["tool"] for tc in comprehensive["tool_calls"]]
        assert "add" in tool_names, "add tool call not found"
        assert "get_weather" in tool_names, "get_weather tool call not found"
        
        # Verify text contains all features
        text = comprehensive["text"]
        assert "@prompt.base_greeting" in text, "Prompt reference not found in text"
        assert "@param.user_name" in text, "user_name param not found in text"
        assert "@param.city" in text, "city param not found in text"
        assert "@config.api_key" in text, "api_key config not found in text"
        assert "@tool.allfeature.add" in text, "add tool call not found in text"
        assert "@tool.allfeature.get_weather" in text, "get_weather tool call not found in text"
        
        # Verify tool calls have correct arguments
        add_tool = next(tc for tc in comprehensive["tool_calls"] if tc["tool"] == "add")
        assert add_tool["arguments"]["a"] == 5, "add tool should have a=5"
        assert add_tool["arguments"]["b"] == 3, "add tool should have b=3"
        
        weather_tool = next(tc for tc in comprehensive["tool_calls"] if tc["tool"] == "get_weather")
        assert weather_tool["arguments"]["city"] == "@param.city", "get_weather should use @param.city"

        print("✅ Comprehensive prompt with all variations created successfully")

    @pytest.mark.asyncio
    async def test_call_comprehensive_prompt_with_all_variations(self, base_url, create_vmcp, mcp_servers, helpers):
        """Test 3.17: Call comprehensive prompt with all variations"""
        vmcp = create_vmcp
        print(f"\n📦 Test 3.17 - Calling comprehensive prompt with all variations: {vmcp['id']}")

        # Add MCP server
        helpers["add_server"](vmcp["id"], mcp_servers["allfeature"], "allfeature")

        # Add environment variable
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["environment_variables"] = [
            {"name": "api_key", "value": "test-api-key-12345"}
        ]

        # Create base prompt
        base_prompt = {
            "name": "welcome_message",
            "description": "Welcome message prompt",
            "text": "Welcome! Let's get started.",
            "variables": [],
            "environment_variables": [],
            "tool_calls": []
        }

        # Create comprehensive prompt
        comprehensive_prompt = {
            "name": "full_featured_prompt",
            "description": "Full featured prompt with all variations",
            "text": """@prompt.welcome_message

Processing request for @param.user_name
Using API key: @config.api_key

Step 1 - Calculate: @tool.allfeature.add(a: int = 10, b: int = 20)
Step 2 - Get weather: @tool.allfeature.get_weather(city: str = "@param.city")

Complete!""",
            "variables": [
                {"name": "user_name", "description": "User's name", "required": True},
                {"name": "city", "description": "City name", "required": True}
            ],
            "environment_variables": ["api_key"],
            "tool_calls": [
                {"tool": "add", "arguments": {"a": 10, "b": 20}},
                {"tool": "get_weather", "arguments": {"city": "@param.city"}}
            ]
        }

        # Add both prompts
        vmcp_data["custom_prompts"].append(base_prompt)
        vmcp_data["custom_prompts"].append(comprehensive_prompt)
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call prompt with arguments
                result = await session.get_prompt(
                    "full_featured_prompt",
                    arguments={
                        "user_name": "Alice",
                        "city": "London"
                    }
                )

                print(f"📋 Prompt result: {result}")

                # Verify result
                assert len(result.messages) > 0
                prompt_text = result.messages[0].content.text
                
                # Verify all features were processed
                prompt_text_lower = prompt_text.lower()
                
                # Check that prompt reference was resolved
                assert "welcome" in prompt_text_lower, "Prompt reference should be resolved"
                
                # Check that params were substituted
                assert "alice" in prompt_text_lower, "user_name param should be substituted"
                assert "london" in prompt_text_lower, "city param should be substituted"
                
                # Check that config was substituted
                assert "test-api-key-12345" in prompt_text or "test-api-key" in prompt_text_lower, "api_key config should be substituted"
                
                # Check that tool calls were executed
                # The add tool should return 30 (10+20)
                assert "30" in prompt_text, f"Add tool should return 30, got: {prompt_text}"
                
                # The get_weather tool should have executed (may return weather info)
                # We'll check for any indication that the tool ran
                assert len(prompt_text) > 50, "Prompt should have substantial content from tool executions"

                print("✅ Comprehensive prompt with all variations executed successfully")
