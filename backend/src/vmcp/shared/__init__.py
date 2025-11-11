"""
Shared models and utilities for vMCP system.

This package contains base response models, shared interfaces, and common
validation utilities used across MCP and vMCP modules.
"""

from .models import (
    BaseResponse,
    PaginatedResponse,
    ErrorResponse,
    ServerInfo,
    CapabilitiesInfo,
    ConnectionStatus,
    TransportType,
    AuthType,
    AuthConfig,
    ToolInfo,
    ResourceInfo,
    PromptInfo,
)

from .validators import (
    validate_server_id,
    validate_server_name,
    validate_transport_type,
    validate_auth_type,
    validate_connection_status,
    validate_url,
    validate_command,
    validate_environment_variables,
    validate_headers,
    validate_args,
    validate_description,
    validate_boolean_field,
    validate_optional_string,
    validate_required_string,
    validate_positive_integer,
    validate_non_negative_integer,
)

__all__ = [
    # Models
    "BaseResponse",
    "PaginatedResponse", 
    "ErrorResponse",
    "ServerInfo",
    "CapabilitiesInfo",
    "ConnectionStatus",
    "TransportType",
    "AuthType",
    "AuthConfig",
    "ToolInfo",
    "ResourceInfo",
    "PromptInfo",
    
    # Validators
    "validate_server_id",
    "validate_server_name",
    "validate_transport_type",
    "validate_auth_type",
    "validate_connection_status",
    "validate_url",
    "validate_command",
    "validate_environment_variables",
    "validate_headers",
    "validate_args",
    "validate_description",
    "validate_boolean_field",
    "validate_optional_string",
    "validate_required_string",
    "validate_positive_integer",
    "validate_non_negative_integer",
]
