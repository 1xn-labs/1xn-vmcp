"""
Shared models and interfaces for vMCP system.

This module contains base response models, shared interfaces, and common
validation utilities used across MCP and vMCP modules to ensure type safety
and eliminate duplication.
"""

from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, Dict, List, Any, Generic, TypeVar
from enum import Enum
from datetime import datetime

# Import MCP SDK types for inheritance
from mcp.types import Tool, Resource, Prompt, PromptArgument

# Generic type for response data
T = TypeVar('T')

class BaseResponse(BaseModel, Generic[T]):
    """Base response model with common fields for all API responses."""
    
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Human-readable message about the operation")
    data: Optional[T] = Field(None, description="Response data payload")

class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response model extending BaseResponse."""
    
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Human-readable message about the operation")
    data: List[T] = Field(..., description="List of items in current page")
    pagination: Dict[str, Any] = Field(..., description="Pagination metadata")

class ErrorResponse(BaseModel):
    """Standardized error response format."""
    
    success: bool = Field(False, description="Always false for error responses")
    message: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Machine-readable error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")

class ServerInfo(BaseModel):
    """Common server information fields shared between MCP and vMCP."""
    
    id: str = Field(..., description="Unique server identifier")
    name: str = Field(..., description="Server name")
    description: Optional[str] = Field(None, description="Server description")
    status: str = Field(..., description="Current server status")
    created_at: Optional[datetime] = Field(None, description="Server creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

class CapabilitiesInfo(BaseModel):
    """Standardized capabilities structure."""
    
    tools: bool = Field(False, description="Whether server supports tools")
    resources: bool = Field(False, description="Whether server supports resources")
    prompts: bool = Field(False, description="Whether server supports prompts")
    tools_count: int = Field(0, description="Number of available tools")
    resources_count: int = Field(0, description="Number of available resources")
    prompts_count: int = Field(0, description="Number of available prompts")

class ConnectionStatus(str, Enum):
    """Enum for connection states."""
    
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    AUTH_REQUIRED = "auth_required"
    ERROR = "error"
    UNKNOWN = "unknown"
    NOT_FOUND = "not_found"

class TransportType(str, Enum):
    """Enum for transport types."""
    
    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"

class AuthType(str, Enum):
    """Enum for authentication types."""
    
    NONE = "none"
    OAUTH = "oauth"
    BEARER = "bearer"
    BASIC = "basic"

class AuthConfig(BaseModel):
    """Base authentication configuration."""
    
    type: AuthType = Field(AuthType.NONE, description="Authentication type")
    client_id: Optional[str] = Field(None, description="OAuth client ID")
    client_secret: Optional[str] = Field(None, description="OAuth client secret")
    auth_url: Optional[str] = Field(None, description="OAuth authorization URL")
    token_url: Optional[str] = Field(None, description="OAuth token URL")
    scope: Optional[str] = Field(None, description="OAuth scope")
    access_token: Optional[str] = Field(None, description="Bearer token")
    refresh_token: Optional[str] = Field(None, description="OAuth refresh token")
    expires_at: Optional[datetime] = Field(None, description="Token expiration time")

class ToolInfo(Tool):
    """Standardized tool information extending the core MCP SDK Tool type.
    
    Maintains compatibility with MCP Tool while providing simplified access.
    """
    
    model_config = ConfigDict(extra="allow")
    
    @property
    def input_schema(self) -> Optional[Dict[str, Any]]:
        """Get input schema (alias for inputSchema)."""
        return self.inputSchema
    
    @property
    def annotations_dict(self) -> Optional[Dict[str, Any]]:
        """Get annotations as dict."""
        if self.annotations:
            return self.annotations.model_dump() if hasattr(self.annotations, 'model_dump') else self.annotations
        return None

class ResourceInfo(Resource):
    """Standardized resource information extending the core MCP SDK Resource type.
    
    Maintains compatibility with MCP Resource while providing simplified access.
    """
    
    model_config = ConfigDict(extra="allow")
    
    @property
    def annotations_dict(self) -> Optional[Dict[str, Any]]:
        """Get annotations as dict."""
        if self.annotations:
            return self.annotations.model_dump() if hasattr(self.annotations, 'model_dump') else self.annotations
        return None

class PromptInfo(Prompt):
    """Standardized prompt information extending the core MCP SDK Prompt type.
    
    Maintains compatibility with MCP Prompt while providing simplified access.
    """
    
    model_config = ConfigDict(extra="allow")
    
    @property
    def arguments_dict(self) -> Optional[Dict[str, Any]]:
        """Get arguments schema as dict."""
        if self.arguments:
            # Convert list of PromptArgument to dict format
            args_dict = {}
            for arg in self.arguments:
                arg_dict = arg.model_dump() if hasattr(arg, 'model_dump') else {
                    "name": arg.name,
                    "description": arg.description,
                    "required": arg.required
                }
                args_dict[arg.name] = arg_dict
            return args_dict
        return None

# Validation utilities
def validate_server_id(server_id: str) -> str:
    """Validate server ID format."""
    if not server_id or not isinstance(server_id, str):
        raise ValueError("Server ID must be a non-empty string")
    
    if len(server_id) < 3:
        raise ValueError("Server ID must be at least 3 characters long")
    
    if len(server_id) > 255:
        raise ValueError("Server ID must be less than 255 characters")
    
    # Check for valid characters (alphanumeric, underscore, hyphen)
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', server_id):
        raise ValueError("Server ID can only contain alphanumeric characters, underscores, and hyphens")
    
    return server_id

def validate_transport_type(transport_type: str) -> TransportType:
    """Validate transport type."""
    try:
        return TransportType(transport_type.lower())
    except ValueError:
        raise ValueError(f"Invalid transport type '{transport_type}'. Must be one of: {', '.join([t.value for t in TransportType])}")

def validate_auth_config(auth_config: Optional[Dict[str, Any]]) -> Optional[AuthConfig]:
    """Validate authentication configuration."""
    if not auth_config:
        return None
    
    try:
        return AuthConfig(**auth_config)
    except Exception as e:
        raise ValueError(f"Invalid auth configuration: {str(e)}")

def validate_connection_status(status: str) -> ConnectionStatus:
    """Validate connection status."""
    try:
        return ConnectionStatus(status.lower())
    except ValueError:
        raise ValueError(f"Invalid connection status '{status}'. Must be one of: {', '.join([s.value for s in ConnectionStatus])}")
