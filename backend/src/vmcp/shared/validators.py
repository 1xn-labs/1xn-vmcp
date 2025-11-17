"""
Shared validation utilities for vMCP system.

This module contains common validation functions used across MCP and vMCP modules
to ensure data consistency and type safety.
"""

import re
from typing import Optional, Dict, Any, List
from datetime import datetime
from vmcp.shared.models import TransportType, AuthType, ConnectionStatus

def validate_server_id(server_id: str) -> str:
    """Validate server ID format."""
    if not server_id or not isinstance(server_id, str):
        raise ValueError("Server ID must be a non-empty string")
    
    if len(server_id) < 3:
        raise ValueError("Server ID must be at least 3 characters long")
    
    if len(server_id) > 255:
        raise ValueError("Server ID must be less than 255 characters")
    
    # Check for valid characters (alphanumeric, underscore, hyphen)
    if not re.match(r'^[a-zA-Z0-9_-]+$', server_id):
        raise ValueError("Server ID can only contain alphanumeric characters, underscores, and hyphens")
    
    return server_id

def validate_server_name(name: str) -> str:
    """Validate server name format."""
    if not name or not isinstance(name, str):
        raise ValueError("Server name must be a non-empty string")
    
    if len(name) < 1:
        raise ValueError("Server name must be at least 1 character long")
    
    if len(name) > 255:
        raise ValueError("Server name must be less than 255 characters")
    
    # Check for valid characters (alphanumeric, underscore, hyphen, space)
    if not re.match(r'^[a-zA-Z0-9_\- ]+$', name):
        raise ValueError("Server name can only contain alphanumeric characters, underscores, hyphens, and spaces")
    
    return name.strip()

def validate_transport_type(transport_type: str) -> TransportType:
    """Validate transport type."""
    try:
        return TransportType(transport_type.lower())
    except ValueError:
        raise ValueError(f"Invalid transport type '{transport_type}'. Must be one of: {', '.join([t.value for t in TransportType])}")

def validate_auth_type(auth_type: str) -> AuthType:
    """Validate authentication type."""
    try:
        return AuthType(auth_type.lower())
    except ValueError:
        raise ValueError(f"Invalid auth type '{auth_type}'. Must be one of: {', '.join([a.value for a in AuthType])}")

def validate_connection_status(status: str) -> ConnectionStatus:
    """Validate connection status."""
    try:
        return ConnectionStatus(status.lower())
    except ValueError:
        raise ValueError(f"Invalid connection status '{status}'. Must be one of: {', '.join([s.value for s in ConnectionStatus])}")

def validate_url(url: str) -> str:
    """Validate URL format."""
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string")
    
    # Basic URL validation regex
    # url_pattern = re.compile(
    #     r'^https?://'  # http:// or https://
    #     r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
    #     r'localhost|'  # localhost...
    #     r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
    #     r'(?::\d+)?'  # optional port
    #     r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    #
    # if not url_pattern.match(url):
    #     raise ValueError("Invalid URL format")
    
    return url

def validate_command(command: str) -> str:
    """Validate command format for stdio transport."""
    if not command or not isinstance(command, str):
        raise ValueError("Command must be a non-empty string")
    
    if len(command) > 1000:
        raise ValueError("Command must be less than 1000 characters")
    
    return command.strip()

def validate_environment_variables(env_vars: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """Validate environment variables."""
    if not env_vars:
        return None
    
    if not isinstance(env_vars, dict):
        raise ValueError("Environment variables must be a dictionary")
    
    validated_env = {}
    for key, value in env_vars.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("Environment variable keys and values must be strings")
        
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', key):
            raise ValueError(f"Invalid environment variable name '{key}'. Must start with letter or underscore and contain only alphanumeric characters and underscores")
        
        validated_env[key] = value
    
    return validated_env

def validate_headers(headers: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """Validate HTTP headers."""
    if not headers:
        return None
    
    if not isinstance(headers, dict):
        raise ValueError("Headers must be a dictionary")
    
    validated_headers = {}
    for key, value in headers.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("Header keys and values must be strings")
        
        # Basic header name validation
        if not re.match(r'^[A-Za-z0-9\-_]+$', key):
            raise ValueError(f"Invalid header name '{key}'. Must contain only alphanumeric characters, hyphens, and underscores")
        
        validated_headers[key] = value
    
    return validated_headers

def validate_args(args: Optional[List[str]]) -> Optional[List[str]]:
    """Validate command arguments."""
    if not args:
        return None
    
    if not isinstance(args, list):
        raise ValueError("Arguments must be a list")
    
    validated_args = []
    for arg in args:
        if not isinstance(arg, str):
            raise ValueError("All arguments must be strings")
        
        if len(arg) > 1000:
            raise ValueError("Argument must be less than 1000 characters")
        
        validated_args.append(arg)
    
    return validated_args

def validate_description(description: Optional[str]) -> Optional[str]:
    """Validate description field."""
    if not description:
        return None
    
    if not isinstance(description, str):
        raise ValueError("Description must be a string")
    
    if len(description) > 1000:
        raise ValueError("Description must be less than 1000 characters")
    
    return description.strip()

def validate_boolean_field(value: Any, field_name: str) -> bool:
    """Validate boolean field."""
    if isinstance(value, bool):
        return value
    
    if isinstance(value, str):
        if value.lower() in ('true', '1', 'yes', 'on'):
            return True
        elif value.lower() in ('false', '0', 'no', 'off'):
            return False
    
    raise ValueError(f"Invalid boolean value for {field_name}: {value}")

def validate_optional_string(value: Any, field_name: str, max_length: int = 1000) -> Optional[str]:
    """Validate optional string field."""
    if value is None:
        return None
    
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    
    if len(value) > max_length:
        raise ValueError(f"{field_name} must be less than {max_length} characters")
    
    return value.strip()

def validate_required_string(value: Any, field_name: str, max_length: int = 1000) -> str:
    """Validate required string field."""
    if not value or not isinstance(value, str):
        raise ValueError(f"{field_name} is required and must be a string")
    
    if len(value) > max_length:
        raise ValueError(f"{field_name} must be less than {max_length} characters")
    
    return value.strip()

def validate_positive_integer(value: Any, field_name: str) -> int:
    """Validate positive integer field."""
    if not isinstance(value, int):
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise ValueError(f"{field_name} must be an integer")
    
    if value < 0:
        raise ValueError(f"{field_name} must be a positive integer")
    
    return value

def validate_non_negative_integer(value: Any, field_name: str) -> int:
    """Validate non-negative integer field."""
    if not isinstance(value, int):
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise ValueError(f"{field_name} must be an integer")
    
    if value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    
    return value
