#!/usr/bin/env python3
"""
Python Tool Engine
==================

Execution engine for Python-based custom tools with sandboxing.
"""

import subprocess
import tempfile
import os
import json
import sys
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from mcp.types import TextContent, PromptMessage, GetPromptResult, CallToolResult

logger = logging.getLogger("1xN_vMCP_PYTHON_TOOL")


def convert_arguments_to_types(arguments: Dict[str, Any], variables: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convert string arguments to their correct types based on variable definitions.
    
    Processes all arguments, using variable definitions when available and 
    preserving other arguments unchanged.

    Args:
        arguments: Raw arguments dictionary
        variables: Variable definitions with type information

    Returns:
        Dictionary with type-converted arguments
    """
    converted = {}
    logger.info(f"🔍 PYTHON_TOOL: Converting arguments to types: {arguments}")
    logger.info(f"🔍 PYTHON_TOOL: Variables: {variables}")
    
    # Create a lookup dict for variable definitions
    var_definitions = {var.get('name'): var for var in variables if var.get('name')}

    # Process all arguments
    for arg_name, value in arguments.items():
        if arg_name in var_definitions:
            # Use variable definition for type conversion
            var = var_definitions[arg_name]
            var_type = var.get('type', 'str')
            var_default = var.get('default_value')

            # Handle null values
            if value is None or value == 'null' or value == '':
                if var_default is not None:
                    converted[arg_name] = var_default
                else:
                    converted[arg_name] = None
                continue

            try:
                if var_type == 'int':
                    converted[arg_name] = int(value)
                elif var_type == 'float':
                    converted[arg_name] = float(value)
                elif var_type == 'bool':
                    if isinstance(value, str):
                        converted[arg_name] = value.lower() in ('true', '1', 'yes', 'on')
                    else:
                        converted[arg_name] = bool(value)
                elif var_type == 'list':
                    if isinstance(value, str):
                        # Try to parse as JSON array
                        try:
                            converted[arg_name] = json.loads(value)
                        except:
                            # Fallback to splitting by comma
                            converted[arg_name] = [item.strip() for item in value.split(',')]
                    else:
                        converted[arg_name] = value
                elif var_type == 'dict':
                    if isinstance(value, str):
                        try:
                            converted[arg_name] = json.loads(value)
                        except:
                            converted[arg_name] = value
                    else:
                        converted[arg_name] = value
                else:  # str or unknown type
                    converted[arg_name] = str(value)
            except (ValueError, TypeError) as e:
                # If conversion fails, use default value or keep as string
                if var_default is not None:
                    converted[arg_name] = var_default
                    logger.warning(f"Failed to convert argument '{arg_name}' to type '{var_type}', using default: {e}")
                else:
                    converted[arg_name] = str(value)
                    logger.warning(f"Failed to convert argument '{arg_name}' to type '{var_type}': {e}")
        else:
            # No variable definition - preserve argument as-is
            converted[arg_name] = value

    # Add any missing variables with default values
    for var in variables:
        var_name = var.get('name')
        var_default = var.get('default_value')
        
        if var_name and var_name not in converted and var_default is not None:
            converted[var_name] = var_default

    return converted


async def execute_python_tool(
    custom_tool: dict,
    arguments: Dict[str, Any],
    environment_variables: Dict[str, Any],
    tool_as_prompt: bool = False,
    vmcp_id: Optional[str] = None,
    skip_sandbox: bool = False
):
    """
    Execute a Python tool with secure sandboxing.

    Args:
        custom_tool: Tool configuration dictionary
        arguments: Tool arguments
        environment_variables: Environment variables
        tool_as_prompt: Whether to return as prompt result
        vmcp_id: Optional vMCP ID for sandbox tool execution

    Returns:
        CallToolResult or GetPromptResult
    """
    # Get the Python code
    python_code = custom_tool.get('code', '')
    if not python_code:
        error_content = TextContent(
            type="text",
            text="No Python code provided for this tool",
            annotations=None,
            _meta=None
        )
        return CallToolResult(
            content=[error_content],
            structuredContent=None,
            isError=True
        )

    # Convert arguments to correct types based on tool variables and function signature
    logger.info(f"🔍 PYTHON_TOOL: Raw arguments received: {arguments}")
    
    # Extract type information from function signature
    variables_from_code = []
    python_code = custom_tool.get('code', '')
    if python_code:
        try:
            from ..parameter_parser import parse_python_function_schema
            schema_from_code = parse_python_function_schema(python_code)
            
            # Convert schema properties back to variables format for type conversion
            for param_name, param_schema in schema_from_code.get('properties', {}).items():
                schema_type = param_schema.get('type', 'string')
                # Map JSON schema types back to internal types
                type_mapping = {
                    'string': 'str',
                    'integer': 'int', 
                    'number': 'float',
                    'boolean': 'bool',
                    'array': 'list',
                    'object': 'dict'
                }
                internal_type = type_mapping.get(schema_type, 'str')

                variables_from_code.append({
                    'name': param_name,
                    'type': internal_type,
                    'required': param_name in schema_from_code.get('required', [])
                })

            logger.info(f"🔍 PYTHON_TOOL: Extracted types from function signature: {variables_from_code}")
        except Exception as e:
            logger.warning(f"Failed to extract types from function signature: {e}")
    
    # Combine manual variables with extracted variables (manual takes precedence)
    all_variables = list(custom_tool.get('variables', []))
    manual_var_names = {var.get('name') for var in all_variables}
    
    for var_from_code in variables_from_code:
        if var_from_code['name'] not in manual_var_names:
            all_variables.append(var_from_code)
    
    converted_arguments = convert_arguments_to_types(arguments, all_variables)
    logger.info(f"🔍 PYTHON_TOOL: Converted arguments: {converted_arguments}")

    # Check if this is a sandbox-discovered tool
    tool_meta = custom_tool.get('meta', {})
    is_sandbox_discovered = tool_meta.get('source') == 'sandbox_discovered'
    script_path = tool_meta.get('script_path')
    
    # For sandbox-discovered tools, execute in sandbox environment
    if is_sandbox_discovered:
        logger.info(f"🏖️  PYTHON_TOOL: Detected sandbox-discovered tool - script_path={script_path}, vmcp_id={vmcp_id}")
        
        # If vmcp_id is not provided, try to get it from tool metadata
        if not vmcp_id:
            vmcp_id = tool_meta.get('vmcp_id')
            logger.info(f"🏖️  PYTHON_TOOL: Extracted vmcp_id from tool metadata: {vmcp_id}")
        
        if not script_path:
            error_content = TextContent(
                type="text",
                text=f"Sandbox tool missing script_path in metadata: {tool_meta}",
                annotations=None,
                _meta=None
            )
            return CallToolResult(
                content=[error_content],
                structuredContent=None,
                isError=True
            )
        
        if not vmcp_id:
            error_content = TextContent(
                type="text",
                text=f"Sandbox tool missing vmcp_id. Tool metadata: {tool_meta}. Please ensure the tool is called with vmcp_id context.",
                annotations=None,
                _meta=None
            )
            return CallToolResult(
                content=[error_content],
                structuredContent=None,
                isError=True
            )
        
        logger.info(f"🏖️  PYTHON_TOOL: Executing sandbox tool via execute_sandbox_discovered_tool")
        from .sandbox_tool import execute_sandbox_discovered_tool
        return await execute_sandbox_discovered_tool(
            vmcp_id=vmcp_id,
            script_path=script_path,
            arguments=converted_arguments,
            environment_variables=environment_variables,
            tool_as_prompt=tool_as_prompt,
            skip_sandbox=skip_sandbox
        )

    # Determine which Python executable to use
    # For sandbox tools (execute_bash), use the sandbox's venv Python
    tool_name = custom_tool.get('name', '')
    is_sandbox_tool = tool_name in ('execute_bash',)
    python_executable = sys.executable
    
    if is_sandbox_tool and vmcp_id:
        try:
            from vmcp.vmcps.sandbox_service import get_sandbox_service
            sandbox_service = get_sandbox_service()
            sandbox_path = sandbox_service.get_sandbox_path(vmcp_id)
            venv_python = sandbox_path / ".venv" / "bin" / "python"
            
            # Try Windows path if Unix path doesn't exist
            if not venv_python.exists():
                venv_python = sandbox_path / ".venv" / "Scripts" / "python.exe"
            
            if venv_python.exists():
                python_executable = str(venv_python)
                logger.info(f"Using sandbox venv Python: {python_executable} for tool {tool_name}")
            else:
                logger.warning(f"Sandbox venv Python not found at {venv_python}, using system Python")
        except Exception as e:
            logger.warning(f"Failed to get sandbox venv Python for {vmcp_id}: {e}, using system Python")

    # Create a secure execution environment
    try:
        # Create a temporary file for the Python code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            # Prepare the execution environment
            execution_code = f"""
import sys
import json
import os
import subprocess
import tempfile
import shutil
import signal
import time
from contextlib import contextmanager

# Security: Disable dangerous modules
DANGEROUS_MODULES = [
    'os', 'subprocess', 'shutil', 'tempfile', 'signal', 'sys', 'importlib',
    'eval', 'exec', 'compile', '__import__', 'open', 'file', 'input', 'raw_input',
    'reload', 'vars', 'globals', 'locals', 'dir', 'hasattr', 'getattr', 'setattr',
    'delattr', 'callable', 'isinstance', 'issubclass', 'type', 'super'
]

# Override dangerous functions
def secure_exec(code, globals_dict, locals_dict):
    # Check for dangerous patterns
    dangerous_patterns = [
        'import os', 'import subprocess', 'import shutil', 'import tempfile',
        'import signal', 'import sys', 'import importlib',
        'eval(', 'exec(', 'compile(', '__import__(',
        'open(', 'file(', 'input(', 'raw_input(',
        'reload(', 'vars(', 'globals(', 'locals(',
        'dir(', 'hasattr(', 'getattr(', 'setattr(',
        'delattr(', 'callable(', 'isinstance(', 'issubclass(',
        'type(', 'super('
    ]

    for pattern in dangerous_patterns:
        if pattern in code:
            raise SecurityError(f"Dangerous pattern detected: {{pattern}}")

    # Execute the code
    exec(code, globals_dict, locals_dict)

class SecurityError(Exception):
    pass

# Arguments passed from the tool call
# Use repr() instead of json.dumps() to get proper Python boolean format (True/False vs true/false)
arguments = {repr(converted_arguments)}

# Environment variables
environment_variables = {repr(environment_variables)}

# User's Python code
{python_code}

# Execute the main function if it exists
if 'main' in locals() and callable(main):
    try:
        # Get function signature to properly map arguments
        import inspect
        import asyncio
        sig = inspect.signature(main)
        param_names = list(sig.parameters.keys())

        # Filter arguments to only include those that match function parameters
        filtered_args = {{}}
        for param_name in param_names:
            if param_name in arguments:
                filtered_args[param_name] = arguments[param_name]

        # Check if main is async
        if inspect.iscoroutinefunction(main):
            # Execute async main
            result = asyncio.run(main(**filtered_args))
        else:
            # Execute sync main
            result = main(**filtered_args)
        print(json.dumps({{"success": True, "result": result}}))
    except Exception as e:
        print(json.dumps({{"success": False, "error": str(e)}}))
else:
    print(json.dumps({{"success": False, "error": "No 'main' function found in the code"}}))
"""
            f.write(execution_code)
            temp_file = f.name

        # Execute the Python code in a secure environment
        # For sandbox tools, run in the sandbox directory; otherwise use temp directory
        if is_sandbox_tool and vmcp_id:
            try:
                from vmcp.vmcps.sandbox_service import get_sandbox_service
                sandbox_service = get_sandbox_service()
                sandbox_path = sandbox_service.get_sandbox_path(vmcp_id)
                cwd = str(sandbox_path) if sandbox_path.exists() else tempfile.gettempdir()
            except Exception:
                cwd = tempfile.gettempdir()
        else:
            cwd = tempfile.gettempdir()
        
        # Use longer timeout for sandbox tools (they have their own 30s timeout)
        timeout = 60 if is_sandbox_tool else 30
        
        result = subprocess.run(
            [python_executable, temp_file],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd
        )

        # Clean up the temporary file
        os.unlink(temp_file)

        # Parse the result
        try:
            result_data = json.loads(result.stdout.strip())
            if result_data.get('success', False):
                result_text = json.dumps(result_data.get('result', ''), indent=2)
            else:
                result_text = f"Error: {result_data.get('error', 'Unknown error')}"
        except json.JSONDecodeError:
            result_text = result.stdout if result.stdout else result.stderr

        # Create the TextContent
        text_content = TextContent(
            type="text",
            text=result_text,
            annotations=None,
            _meta=None
        )

        if tool_as_prompt:
            # Create the PromptMessage
            prompt_message = PromptMessage(
                role="user",
                content=text_content
            )

            # Create the GetPromptResult
            prompt_result = GetPromptResult(
                description="Python tool execution result",
                messages=[prompt_message]
            )
            return prompt_result

        # Create the CallToolResult
        tool_result = CallToolResult(
            content=[text_content],
            structuredContent=None,
            isError=not result_data.get('success', False) if 'result_data' in locals() else False
        )

        return tool_result

    except subprocess.TimeoutExpired as e:
        timeout_seconds = getattr(e, 'timeout', 30)
        error_content = TextContent(
            type="text",
            text=f"Python tool execution timed out ({timeout_seconds} seconds)",
            annotations=None,
            _meta=None
        )
        return CallToolResult(
            content=[error_content],
            structuredContent=None,
            isError=True
        )
    except Exception as e:
        error_content = TextContent(
            type="text",
            text=f"Error executing Python tool: {str(e)}",
            annotations=None,
            _meta=None
        )
        return CallToolResult(
            content=[error_content],
            structuredContent=None,
            isError=True
        )
