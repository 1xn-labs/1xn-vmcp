"""
Test Suite 11: vMCP SDK
Tests the async Python SDK for programmatic MCP tool access
"""

import asyncio
import os
import pytest
import sys

from vmcp.utilities.logging.config import settings, get_logger

from vmcp_sdk import (
    VMCPClient,
    VMCPError,
    VMCPToolNotFoundError,
    VMCPToolExecutionError,
)

# import logging

# Configure logging for VMCP MCP Client Manager
# logging.basicConfig(
#     format='[%(name)s] %(levelname)s: %(message)s',
#     stream=sys.stderr,
#     level=logging.DEBUG,
#     force=True  # Override any existing configuration
# )



@pytest.mark.sdk
class TestVMCPSDK:
    """Test vMCP SDK functionality"""

    @pytest.fixture(autouse=True)
    def setup_vmcp(self, base_url, create_vmcp, mcp_servers, helpers):
        """Setup vMCP with test servers for SDK testing"""
        self._vmcp = create_vmcp
        self._base_url = base_url

        # Add allfeature server for testing
        helpers["add_server"](
            self._vmcp["id"],
            mcp_servers["allfeature"],
            "allfeature"
        )


        yield

        # VMCP deletion is autmatic in conftest.py

       

    @pytest.mark.asyncio
    async def test_sdk_basic_usage(self):
        """Test 11.1: Basic SDK usage with context manager"""
        print(f"\n🧪 Test 11.1 - Basic SDK usage")

        async with VMCPClient(vmcp_id=self._vmcp["id"]) as client:
            # Call a simple tool
            result = await client.allfeature_add_numbers(a=5, b=3)

            # Verify result
            assert result.is_success()
            assert result.value is not None
            assert result.value.get("result") == 8

            print(f"✅ Basic tool call successful: 5 + 3 = {result.value['result']}")

    @pytest.mark.asyncio
    async def test_sdk_tool_chaining(self):
        """Test 11.2: Chaining multiple tool calls"""
        print(f"\n🧪 Test 11.2 - Tool chaining")

        async with VMCPClient(vmcp_id=self._vmcp["id"]) as client:
            # Get location
            location_result = await client.allfeature_get_location(city="Tokyo")
            assert location_result.is_success()

            location = location_result.value
            print(f"   Location: {location['name']} at ({location['latitude']}, {location['longitude']})")

            # Use location to get weather
            weather_result = await client.allfeature_get_weather_from_location(
                lat=location['latitude'],
                lng=location['longitude']
            )
            assert weather_result.is_success()

            weather = weather_result.value
            print(f"   Weather: {weather['temperature']}°C, {weather['condition']}")
            print(f"✅ Tool chaining successful")

    @pytest.mark.asyncio
    async def test_sdk_parallel_execution(self):
        """Test 11.3: Parallel tool execution with asyncio.gather"""
        print(f"\n🧪 Test 11.3 - Parallel execution")

        async with VMCPClient(vmcp_id=self._vmcp["id"]) as client:
            # Execute multiple tools in parallel
            results = await asyncio.gather(
                client.allfeature_add_numbers(a=10, b=20),
                client.allfeature_sum_of_array([50, 100, 200]),
                client.allfeature_hello(name="SDK Test"),
                return_exceptions=True
            )

            # Verify all succeeded
            assert len(results) == 3
            assert all(not isinstance(r, Exception) for r in results)
            assert results[0].value["result"] == 30
            assert results[1].value["result"] == 350

            print(f"✅ Parallel execution successful: {len(results)} tools executed")

    @pytest.mark.asyncio
    async def test_sdk_array_operations(self):
        """Test 11.4: Working with array parameters"""
        print(f"\n🧪 Test 11.4 - Array operations")

        async with VMCPClient(vmcp_id=self._vmcp["id"]) as client:
            # Sum an array
            numbers = [10, 20, 30, 40, 50]
            result = await client.allfeature_sum_of_array(array=numbers)

            assert result.is_success()
            assert result.value["result"] == 150

            print(f"✅ Array operation successful: sum({numbers}) = {result.value['result']}")

    @pytest.mark.asyncio
    async def test_sdk_tool_not_found_error(self):
        """Test 11.5: VMCPToolNotFoundError with fuzzy matching"""
        print(f"\n🧪 Test 11.5 - Tool not found error")

        async with VMCPClient(vmcp_id=self._vmcp["id"]) as client:
            with pytest.raises(VMCPToolNotFoundError) as exc_info:
                await client.nonexistent_tool()

            error = exc_info.value
            # Verify error has tool name
            assert error.tool_name == "nonexistent_tool"
            # Verify error has suggestions
            assert len(error.available_tools) > 0

            print(f"✅ VMCPToolNotFoundError raised with {len(error.available_tools)} suggestions")

    @pytest.mark.asyncio
    async def test_sdk_tool_execution_error(self):
        """Test 11.6: VMCPToolExecutionError for validation failures"""
        print(f"\n🧪 Test 11.6 - Tool execution error")

        async with VMCPClient(vmcp_id=self._vmcp["id"]) as client:
            with pytest.raises(VMCPToolExecutionError) as exc_info:
                # Pass wrong type (integer instead of string)
                await client.allfeature_get_user(user_id=123)

            error = exc_info.value
            assert error.tool_name == "allfeature_get_user"
            assert "validation error" in error.error_message.lower()

            print(f"✅ VMCPToolExecutionError raised for validation failure")

    @pytest.mark.asyncio
    async def test_sdk_fuzzy_tool_matching(self):
        """Test 11.7: Fuzzy tool name matching with warning"""
        print(f"\n🧪 Test 11.7 - Fuzzy tool matching")

        async with VMCPClient(vmcp_id=self._vmcp["id"]) as client:
            # Use camelCase instead of snake_case
            result = await client.allfeature_addNumbers(a=5, b=3)

            assert result.is_success()
            assert result.value["result"] == 8

            print(f"✅ Fuzzy matching successful: addNumbers → add_numbers")

    @pytest.mark.asyncio
    async def test_sdk_result_value_property(self):
        """Test 11.8: Result .value property access"""
        print(f"\n🧪 Test 11.8 - Result value property")

        async with VMCPClient(vmcp_id=self._vmcp["id"]) as client:
            result = await client.allfeature_add_numbers(a=100, b=200)

            # Test .value property
            assert result.value is not None
            assert result.value["result"] == 300

            # Test .is_success()
            assert result.is_success() is True

            print(f"✅ Result properties work correctly")

    @pytest.mark.asyncio
    async def test_sdk_exception_handling(self):
        """Test 11.9: Generic exception handling pattern"""
        print(f"\n🧪 Test 11.9 - Exception handling")

        error_caught = False

        try:
            async with VMCPClient(vmcp_id=self._vmcp["id"]) as client:
                # This should raise VMCPToolNotFoundError
                await client.this_tool_does_not_exist()
        except Exception as e:
            error_caught = True
            # Verify the exception message is descriptive
            assert "not found" in str(e).lower()
            print(f"   Caught exception: {type(e).__name__}")

        assert error_caught, "Expected exception was not raised"
        print(f"✅ Generic exception handling works")

    @pytest.mark.asyncio
    async def test_sdk_context_manager_cleanup(self):
        """Test 11.10: Context manager cleanup"""
        print(f"\n🧪 Test 11.10 - Context manager cleanup")

        client = VMCPClient(vmcp_id=self._vmcp["id"])

        # Enter context
        async with client as c:
            assert c._tools_loaded is True
            result = await c.allfeature_add_numbers(a=1, b=2)
            assert result.value["result"] == 3

        # After exit, tools should be cleared
        assert client._tools_loaded is False
        assert len(client._typed_functions) == 0

        print(f"✅ Context manager cleanup successful")

    @pytest.mark.asyncio
    async def test_sdk_list_tools(self):
        """Test 11.11: List available tools"""
        print(f"\n🧪 Test 11.11 - List tools")

        async with VMCPClient(vmcp_id=self._vmcp["id"]) as client:
            tools = await client.list_tools()

            assert len(tools) > 0
            # Verify tools have expected structure
            assert all("name" in tool for tool in tools)
            assert all("description" in tool for tool in tools)

            print(f"✅ Listed {len(tools)} available tools")

    @pytest.mark.asyncio
    async def test_sdk_without_context_manager_error(self):
        """Test 11.12: Error when accessing tools without loading"""
        print(f"\n🧪 Test 11.12 - Access without loading error")

        client = VMCPClient(vmcp_id=self._vmcp["id"])

        # Try to access tool without entering context or loading
        with pytest.raises((VMCPError, RuntimeError)) as exc_info:
            # This should fail because tools aren't loaded
            func = client.allfeature_add_numbers

        print(f"✅ Proper error raised when tools not loaded")
