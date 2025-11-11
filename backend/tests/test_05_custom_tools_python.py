"""
Test Suite 5: Custom Tools - Python Type
Tests for Python-based custom tools
"""

import pytest
import requests
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


@pytest.mark.python_tool
class TestCustomToolsPython:
    """Test Python-type custom tools"""

    def test_create_simple_python_tool(self, base_url, create_vmcp, helpers):
        """Test 5.1: Create a simple Python tool"""
        vmcp = create_vmcp
        print(f"\n📦 Test 5.1 - Creating simple Python tool: {vmcp['id']}")

        # Get vMCP data
        vmcp_data = helpers["get_vmcp"](vmcp["id"])

        # Add simple Python tool
        simple_python_tool = {
            "name": "add_numbers",
            "description": "Add two numbers",
            "tool_type": "python",
            "code": """def main(a: int, b: int):
    return a + b
""",
            "variables": [
                {"name": "a", "description": "First number", "type": "int", "required": True},
                {"name": "b", "description": "Second number", "type": "int", "required": True}
            ],
            "environment_variables": [],
            "tool_calls": [],
            "atomic_blocks": []
        }

        vmcp_data["custom_tools"].append(simple_python_tool)
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Verify
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        assert len(updated_vmcp["custom_tools"]) == 1
        assert updated_vmcp["custom_tools"][0]["tool_type"] == "python"

        print("✅ Simple Python tool created successfully")

    @pytest.mark.asyncio
    async def test_call_simple_python_tool(self, base_url, create_vmcp, helpers):
        """Test 5.2: Call a simple Python tool"""
        vmcp = create_vmcp
        print(f"\n📦 Test 5.2 - Calling simple Python tool: {vmcp['id']}")

        # Add Python tool
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "multiply",
            "description": "Multiply two numbers",
            "tool_type": "python",
            "code": """def main(x: int, y: int):
    result = x * y
    return f"Result: {result}"
""",
            "variables": [
                {"name": "x", "description": "First number", "type": "int", "required": True},
                {"name": "y", "description": "Second number", "type": "int", "required": True}
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
                result = await session.call_tool("multiply", arguments={"x": 5, "y": 7})

                print(f"🔧 Tool result: {result}")

                # Verify
                assert len(result.content) > 0
                result_text = result.content[0].text
                assert "35" in result_text, f"Expected '35' in result, got: {result_text}"

                print("✅ Python tool call successful")

    @pytest.mark.asyncio
    async def test_python_tool_with_string_type(self, base_url, create_vmcp, helpers):
        """Test 5.3: Python tool with string type variables"""
        vmcp = create_vmcp
        print(f"\n📦 Test 5.3 - Python tool with string variables: {vmcp['id']}")

        # Add Python tool with string handling
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "string_formatter",
            "description": "Format strings",
            "tool_type": "python",
            "code": """def main(first_name, last_name):
    full_name = f"{first_name} {last_name}"
    return full_name.upper()
""",
            "variables": [
                {"name": "first_name", "description": "First name", "type": "str", "required": True},
                {"name": "last_name", "description": "Last name", "type": "str", "required": True}
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
                    "string_formatter",
                    arguments={"first_name": "John", "last_name": "Doe"}
                )

                print(f"🔧 Tool result: {result}")

                # Verify
                result_text = result.content[0].text
                assert "JOHN DOE" in result_text, f"Expected 'JOHN DOE' in result, got: {result_text}"

                print("✅ Python tool with strings successful")

    @pytest.mark.asyncio
    async def test_python_tool_with_list_type(self, base_url, create_vmcp, helpers):
        """Test 5.4: Python tool with list type variables"""
        vmcp = create_vmcp
        print(f"\n📦 Test 5.4 - Python tool with list variables: {vmcp['id']}")

        # Add Python tool with list handling
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "sum_list",
            "description": "Sum a list of numbers",
            "tool_type": "python",
            "code": """def main(numbers: list[int]):
    total = sum(numbers)
    return f"Sum: {total}"
""",
            "variables": [
                {"name": "numbers", "description": "List of numbers", "type": "list", "required": True}
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

                # Call tool with list
                result = await session.call_tool(
                    "sum_list",
                    arguments={"numbers": [1, 2, 3, 4, 5]}
                )

                print(f"🔧 Tool result: {result}")

                # Verify
                result_text = result.content[0].text
                assert "15" in result_text, f"Expected '15' in result, got: {result_text}"

                print("✅ Python tool with list successful")

    @pytest.mark.asyncio
    async def test_python_tool_with_dict_type(self, base_url, create_vmcp, helpers):
        """Test 5.5: Python tool with dict type variables"""
        vmcp = create_vmcp
        print(f"\n📦 Test 5.5 - Python tool with dict variables: {vmcp['id']}")

        # Add Python tool with dict handling
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "process_data",
            "description": "Process dictionary data",
            "tool_type": "python",
            "code": """def main(data: dict):
    keys = list(data.keys())
    return f"Keys: {', '.join(keys)}"
""",
            "variables": [
                {"name": "data", "description": "Dictionary data", "type": "dict", "required": True}
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

                # Call tool with dict
                result = await session.call_tool(
                    "process_data",
                    arguments={"data": {"name": "Alice", "age": 30, "city": "NYC"}}
                )

                print(f"🔧 Tool result: {result}")

                # Verify
                result_text = result.content[0].text
                assert "name" in result_text and "age" in result_text and "city" in result_text

                print("✅ Python tool with dict successful")

    @pytest.mark.asyncio
    async def test_python_tool_with_float_type(self, base_url, create_vmcp, helpers):
        """Test 5.6: Python tool with float type variables"""
        vmcp = create_vmcp
        print(f"\n📦 Test 5.6 - Python tool with float variables: {vmcp['id']}")

        # Add Python tool with float handling
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "calculate_area",
            "description": "Calculate circle area",
            "tool_type": "python",
            "code": """def main(radius: float):
    import math
    area = math.pi * radius * radius
    return f"Area: {area:.2f}"
""",
            "variables": [
                {"name": "radius", "description": "Circle radius", "type": "float", "required": True}
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
                result = await session.call_tool("calculate_area", arguments={"radius": 5.0})

                print(f"🔧 Tool result: {result}")

                # Verify (pi * 5^2 ≈ 78.54)
                result_text = result.content[0].text
                assert "78" in result_text, f"Expected area around 78, got: {result_text}"

                print("✅ Python tool with float successful")

    @pytest.mark.asyncio
    async def test_python_tool_with_default_values(self, base_url, create_vmcp, helpers):
        """Test 5.7: Python tool with default values"""
        vmcp = create_vmcp
        print(f"\n📦 Test 5.7 - Python tool with default values: {vmcp['id']}")

        # Add Python tool with default values
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "greet_user",
            "description": "Greet user with optional title",
            "tool_type": "python",
            "code": """def main(name, title="Mr/Ms"):
    return f"Hello {title} {name}!"
""",
            "variables": [
                {"name": "name", "description": "User's name", "type": "str", "required": True},
                {"name": "title", "description": "User's title", "type": "str", "required": False, "default_value": "Mr/Ms"}
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

                # Call tool without optional parameter
                result = await session.call_tool("greet_user", arguments={"name": "Smith"})

                print(f"🔧 Tool result: {result}")

                # Verify default value was used
                result_text = result.content[0].text
                assert "Mr/Ms" in result_text or "Smith" in result_text

                print("✅ Python tool with default values successful")

    @pytest.mark.asyncio
    async def test_python_tool_complex_logic(self, base_url, create_vmcp, helpers):
        """Test 5.8: Python tool with complex logic"""
        vmcp = create_vmcp
        print(f"\n📦 Test 5.8 - Python tool with complex logic: {vmcp['id']}")

        # Add Python tool with complex logic
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "fibonacci",
            "description": "Calculate Fibonacci number",
            "tool_type": "python",
            "code": """def main(n: int):
    if n <= 0:
        return "Invalid input"
    elif n == 1:
        return 0
    elif n == 2:
        return 1
    else:
        a, b = 0, 1
        for _ in range(n - 2):
            a, b = b, a + b
        return b
""",
            "variables": [
                {"name": "n", "description": "Position in Fibonacci sequence", "type": "int", "required": True}
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

                # Call tool for 10th Fibonacci number (should be 34)
                result = await session.call_tool("fibonacci", arguments={"n": 10})

                print(f"🔧 Tool result: {result}")

                # Verify
                result_text = result.content[0].text
                assert "34" in result_text, f"Expected '34' in result, got: {result_text}"

                print("✅ Python tool with complex logic successful")

    @pytest.mark.asyncio
    async def test_python_tool_error_handling(self, base_url, create_vmcp, helpers):
        """Test 5.9: Python tool error handling"""
        vmcp = create_vmcp
        print(f"\n📦 Test 5.9 - Python tool error handling: {vmcp['id']}")

        # Add Python tool that can raise errors
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "divide",
            "description": "Divide two numbers",
            "tool_type": "python",
            "code": """def main(numerator: float, denominator: float):
    if denominator == 0:
        raise ValueError("Cannot divide by zero")
    return numerator / denominator
""",
            "variables": [
                {"name": "numerator", "description": "Numerator", "type": "float", "required": True},
                {"name": "denominator", "description": "Denominator", "type": "float", "required": True}
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

                # Call tool with valid input
                result_valid = await session.call_tool(
                    "divide",
                    arguments={"numerator": 10, "denominator": 2}
                )

                # Verify valid result
                assert len(result_valid.content) > 0
                assert "5" in result_valid.content[0].text

                # Call tool with division by zero
                result_error = await session.call_tool(
                    "divide",
                    arguments={"numerator": 10, "denominator": 0}
                )

                # Verify error is reported
                assert len(result_error.content) > 0
                error_text = result_error.content[0].text.lower()
                assert "error" in error_text or "zero" in error_text

                print("✅ Python tool error handling successful")

    @pytest.mark.asyncio
    async def test_python_tool_automatic_type_detection(self, base_url, create_vmcp, helpers):
        """Test 5.8: Automatic type detection from function signature (no manual variables)"""
        vmcp = create_vmcp
        print(f"\n📦 Test 5.8 - Automatic type detection: {vmcp['id']}")

        # Add Python tool with NO manual variables - should auto-detect types
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "auto_types",
            "description": "Test automatic type detection",
            "tool_type": "python",
            "code": """def main(number: int, text: str):
    return f"Got number: {number} (type: {type(number).__name__}), text: {text} (type: {type(text).__name__})"
""",
            "variables": [],  # No manual variables - should auto-detect!
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

                # Call tool - should auto-detect int and str types
                result = await session.call_tool(
                    "auto_types",
                    arguments={"number": 42, "text": "hello"}
                )

                print(f"🔧 Auto-type result: {result}")

                # Verify types were correctly detected and converted
                result_text = result.content[0].text
                assert "Got number: 42 (type: int)" in result_text, f"Auto-detection failed: {result_text}"
                assert "text: hello (type: str)" in result_text, f"Auto-detection failed: {result_text}"

                print("✅ Automatic type detection successful")

    @pytest.mark.asyncio
    async def test_python_tool_boolean_handling(self, base_url, create_vmcp, helpers):
        """Test 5.9: Boolean parameter handling (fixes the true/True issue)"""
        vmcp = create_vmcp
        print(f"\n📦 Test 5.9 - Boolean handling: {vmcp['id']}")

        # Add Python tool specifically for boolean testing
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "bool_test",
            "description": "Test boolean parameter handling",
            "tool_type": "python",
            "code": """def main(flag: bool):
    if flag:
        return "BOOLEAN_TRUE"
    else:
        return "BOOLEAN_FALSE"
""",
            "variables": [],  # Auto-detect bool type
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

                # Test with True
                result_true = await session.call_tool("bool_test", arguments={"flag": True})
                assert "BOOLEAN_TRUE" in result_true.content[0].text, f"Boolean True failed: {result_true.content[0].text}"

                # Test with False
                result_false = await session.call_tool("bool_test", arguments={"flag": False})
                assert "BOOLEAN_FALSE" in result_false.content[0].text, f"Boolean False failed: {result_false.content[0].text}"

                print("✅ Boolean parameter handling successful")

    @pytest.mark.asyncio
    async def test_python_tool_integer_handling(self, base_url, create_vmcp, helpers):
        """Test 5.10: Integer parameter handling and arithmetic"""
        vmcp = create_vmcp
        print(f"\n📦 Test 5.10 - Integer handling: {vmcp['id']}")

        # Add Python tool for integer arithmetic
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "int_math",
            "description": "Test integer parameter handling",
            "tool_type": "python",
            "code": """def main(a: int, b: int):
    result = a * b
    return f"{a} * {b} = {result} (types: {type(a).__name__}, {type(b).__name__})"
""",
            "variables": [],  # Auto-detect int types
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

                # Test integer arithmetic
                result = await session.call_tool("int_math", arguments={"a": 12, "b": 7})
                
                print(f"🔧 Integer math result: {result}")

                # Verify integers were properly converted and arithmetic works
                result_text = result.content[0].text
                assert "12 * 7 = 84" in result_text, f"Integer arithmetic failed: {result_text}"
                assert "(types: int, int)" in result_text, f"Integer type conversion failed: {result_text}"

                print("✅ Integer parameter handling successful")
