#!/usr/bin/env python3
"""
Parameter Parser
================

Handles parsing of function-like parameter strings with type annotations.
Supports AST-based parsing with regex fallback for compatibility.
"""

import ast
import re
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("1xN_vMCP_PARAMETER_PARSER")


def parse_parameters(params_str: str, arguments: Dict[str, Any], environment_variables: Dict[str, Any]) -> Dict[str, Any]:
    """Parse parameter string using Python AST to handle function-like syntax with type annotations"""
    params = {}
    if not params_str.strip():
        return params

    try:
        # Preprocess the parameter string to handle @var and @env references
        processed_params_str = _preprocess_parameter_string(params_str, arguments, environment_variables)

        # Use Python's AST parser to parse the parameter string
        # We'll create a mock function definition to parse the parameters
        function_def = f"def mock_function({processed_params_str}): pass"

        # Parse the function definition
        tree = ast.parse(function_def)
        func_def = tree.body[0]

        # Extract parameters from the function definition
        for arg in func_def.args.args:
            param_name = arg.arg
            param_type = None
            default_value = None

            # Get type annotation if present
            if arg.annotation:
                param_type = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else _ast_to_string(arg.annotation)

            # Get default value if present
            # We need to find the corresponding default value by position
            arg_index = func_def.args.args.index(arg)
            if arg_index < len(func_def.args.defaults):
                default_ast = func_def.args.defaults[arg_index]
                default_value = _evaluate_ast_node(default_ast, arguments, environment_variables)

            # If no default value from AST, try to get from arguments
            if default_value is None and param_name in arguments:
                default_value = arguments[param_name]

            # Type cast the value if type annotation is present
            if param_type and default_value is not None:
                default_value = cast_value_to_type(default_value, param_type)

            params[param_name] = default_value

    except Exception as e:
        logger.warning(f"Failed to parse parameters with AST, falling back to regex: {e}")
        # Fallback to the original regex-based parsing
        return _parse_parameters_regex(params_str, arguments, environment_variables)

    return params


def _preprocess_parameter_string(params_str: str, arguments: Dict[str, Any], environment_variables: Dict[str, Any]) -> str:
    """Preprocess parameter string to replace @var and @env references with actual values"""
    # Replace @var.name references
    var_pattern = r'@param\.(\w+)'
    def replace_var(match):
        var_name = match.group(1)
        var_value = arguments.get(var_name, f"[{var_name} not found]")
        # If it's a string, wrap in quotes
        if isinstance(var_value, str) and not (var_value.startswith('"') and var_value.endswith('"')):
            return f'"{var_value}"'
        return str(var_value)

    processed_str = re.sub(var_pattern, replace_var, params_str)

    # Replace @env.name references
    env_pattern = r'@config\.(\w+)'
    def replace_env(match):
        env_name = match.group(1)
        env_value = environment_variables.get(env_name, f"[{env_name} not found]")
        # If it's a string, wrap in quotes
        if isinstance(env_value, str) and not (env_value.startswith('"') and env_value.endswith('"')):
            return f'"{env_value}"'
        return str(env_value)

    processed_str = re.sub(env_pattern, replace_env, processed_str)

    return processed_str


def _parse_parameters_regex(params_str: str, arguments: Dict[str, Any], environment_variables: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback regex-based parameter parsing for compatibility"""
    params = {}
    if not params_str.strip():
        return params

    # Simple parameter parsing - handles param="value" format
    param_pattern = r'(\w+)\s*=\s*([^,]+?)(?=\s*,\s*\w+\s*=|$)'

    for match in re.finditer(param_pattern, params_str):
        param_name = match.group(1)
        param_value = match.group(2)
        if param_value.startswith('"') and param_value.endswith('"'):
            param_value = param_value[1:-1]
        # Substitute any @var.name or @env.name references in the parameter value
        param_value = re.sub(r'@param\.(\w+)', lambda m: str(arguments.get(m.group(1), f"[{m.group(1)} not found]")), param_value)
        param_value = re.sub(r'@config\.(\w+)', lambda m: str(environment_variables.get(m.group(1), f"[{m.group(1)} not found]")), param_value)

        params[param_name] = param_value

    return params


def _ast_to_string(node: ast.AST) -> str:
    """Convert AST node to string representation"""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Constant):
        return str(node.value)
    elif isinstance(node, ast.Str):  # Python < 3.8 compatibility
        return node.s
    elif isinstance(node, ast.Num):  # Python < 3.8 compatibility
        return str(node.n)
    elif isinstance(node, ast.NameConstant):  # Python < 3.8 compatibility
        return str(node.value)
    else:
        return str(node)


def _evaluate_ast_node(node: ast.AST, arguments: Dict[str, Any], environment_variables: Dict[str, Any]) -> Any:
    """Evaluate an AST node to get its value"""
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.Str):  # Python < 3.8 compatibility
        return node.s
    elif isinstance(node, ast.Num):  # Python < 3.8 compatibility
        return node.n
    elif isinstance(node, ast.NameConstant):  # Python < 3.8 compatibility
        return node.value
    elif isinstance(node, ast.Name):
        # Check if it's a variable reference
        var_name = node.id
        if var_name in arguments:
            return arguments[var_name]
        elif var_name in environment_variables:
            return environment_variables[var_name]
        else:
            return f"[{var_name} not found]"
    elif isinstance(node, ast.Str):  # String literal
        return node.s
    elif isinstance(node, ast.Num):  # Numeric literal
        return node.n
    elif isinstance(node, ast.NameConstant):  # Boolean/None literals
        return node.value
    else:
        # For complex expressions, try to evaluate safely
        try:
            # This is a simplified evaluation - in production you might want more robust handling
            return ast.literal_eval(node)
        except:
            return str(node)


def cast_value_to_type(value: Any, type_str: str) -> Any:
    """Cast a value to the specified type"""
    try:
        # Handle common type annotations
        if type_str == "str":
            return str(value)
        elif type_str == "int":
            return int(value)
        elif type_str == "float":
            return float(value)
        elif type_str == "bool":
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            return bool(value)
        elif type_str == "list":
            if isinstance(value, str):
                # Try to parse as JSON list
                try:
                    return json.loads(value)
                except:
                    return [value]
            return list(value) if hasattr(value, '__iter__') else [value]
        elif type_str == "dict":
            if isinstance(value, str):
                # Try to parse as JSON dict
                try:
                    return json.loads(value)
                except:
                    return {"value": value}
            return dict(value) if hasattr(value, 'items') else {"value": value}
        else:
            # For custom types or unknown types, return as-is
            logger.warning(f"Unknown type annotation: {type_str}, returning value as-is")
            return value
    except Exception as e:
        logger.warning(f"Failed to cast {value} to {type_str}: {e}")
        return value


def parse_python_function_schema(
    function_code: str,
    pre_parsed_variables: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Parse Python function to extract input schema for tool definition.

    Args:
        function_code: Python function code as string
        pre_parsed_variables: Pre-parsed variables from previous parsing (optional)

    Returns:
        Dictionary with 'properties' and 'required' fields for JSON schema
    """
    if pre_parsed_variables is None:
        pre_parsed_variables = {}

    properties = {}
    required = []

    try:
        # Parse the function definition
        tree = ast.parse(function_code)
        if not tree.body or not isinstance(tree.body[0], ast.FunctionDef):
            return {"properties": properties, "required": required}

        func_def = tree.body[0]

        # Extract parameters
        for arg in func_def.args.args:
            param_name = arg.arg

            # Skip 'self' parameter
            if param_name == 'self':
                continue

            param_schema = {"type": "string"}  # Default type

            # Get type annotation if present
            if arg.annotation:
                type_str = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else _ast_to_string(arg.annotation)

                # Map Python types to JSON Schema types
                if type_str in ['str', 'string']:
                    param_schema["type"] = "string"
                elif type_str in ['int', 'integer']:
                    param_schema["type"] = "integer"
                elif type_str in ['float', 'number']:
                    param_schema["type"] = "number"
                elif type_str in ['bool', 'boolean']:
                    param_schema["type"] = "boolean"
                elif type_str in ['list', 'List']:
                    param_schema["type"] = "array"
                elif type_str in ['dict', 'Dict']:
                    param_schema["type"] = "object"

            # Check if parameter has a default value
            arg_index = func_def.args.args.index(arg)
            defaults_offset = len(func_def.args.args) - len(func_def.args.defaults)

            if arg_index >= defaults_offset:
                default_index = arg_index - defaults_offset
                default_ast = func_def.args.defaults[default_index]
                try:
                    default_value = ast.literal_eval(default_ast)
                    param_schema["default"] = default_value
                except:
                    pass
            else:
                # No default value means it's required
                required.append(param_name)

            # Use pre-parsed variable description if available
            if param_name in pre_parsed_variables:
                param_schema["description"] = pre_parsed_variables[param_name]

            properties[param_name] = param_schema

    except Exception as e:
        logger.error(f"Error parsing function schema: {e}")

    return {"properties": properties, "required": required}
