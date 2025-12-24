#!/usr/bin/env python3
"""
Python Tool Engine
==================

Execution engine for Python-based custom tools with sandboxing.
"""

import json
import logging
from typing import Dict, Any, List, Optional

from mcp.types import TextContent, CallToolResult

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
    # Convert arguments to correct types based on tool variables and function signature
    logger.info(f"🔍 PYTHON_TOOL: Raw arguments received: {arguments}")
    
    # Get script_path from metadata (all Python tools are now file-based)
    tool_meta = custom_tool.get('meta', {})
    script_path = tool_meta.get('script_path')
    
    if not script_path:
        error_msg = "Python tool missing script_path in metadata. All Python tools must be stored as files."
        error_result = {"error": error_msg}
        structured_output: Dict[str, Any] = {
            "result": error_result,
            "stdout": "",
            "stderr": error_msg
        }
        error_text = json.dumps(structured_output, indent=2)
        return CallToolResult(
            content=[TextContent(type="text", text=error_text, annotations=None, _meta=None)],
            structuredContent=structured_output,
            isError=True
        )
    
    # Get vmcp_id from metadata if not provided
    if not vmcp_id:
        vmcp_id = tool_meta.get('vmcp_id')
        if not vmcp_id:
            error_msg = f"Python tool missing vmcp_id. Tool metadata: {tool_meta}."
            error_result = {"error": error_msg}
            structured_output: Dict[str, Any] = {
                "result": error_result,
                "stdout": "",
                "stderr": error_msg
            }
            error_text = json.dumps(structured_output, indent=2)
            return CallToolResult(
                content=[TextContent(type="text", text=error_text, annotations=None, _meta=None)],
                structuredContent=structured_output,
                isError=True
            )
    
    # Extract type information from function signature for type conversion
    # Try to read the script file to extract types
    variables_from_code = []
    try:
        from vmcp.vmcps.sandbox_service import get_sandbox_service
        sandbox_service = get_sandbox_service()
        sandbox_path = sandbox_service.get_sandbox_path(vmcp_id)
        full_script_path = sandbox_path / script_path
        
        if full_script_path.exists():
            python_code = full_script_path.read_text()
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
    
    # Use unified executor for all Python tools
    logger.info(f"🐍 PYTHON_TOOL: Executing Python tool via unified executor - script_path={script_path}, vmcp_id={vmcp_id}")
    from .unified_python_executor import execute_python_in_sandbox
    return await execute_python_in_sandbox(
        vmcp_id=vmcp_id,
        script_path=script_path,
        arguments=converted_arguments,
        environment_variables=environment_variables,
        tool_as_prompt=tool_as_prompt,
        skip_sandbox=skip_sandbox
    )
