"""
MCP (Model Context Protocol) models with proper inheritance and type safety.

This module contains all MCP-related request and response models that extend
the base shared models to provide type-safe API endpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from mcp.types import Prompt, Resource, ResourceTemplate, Tool
from pydantic import BaseModel, Field, validator

from vmcp.shared.mcp_content_models import (
    MCPCapabilities,
    MCPConnectionInfo,
    MCPPingInfo,
    MCPPromptResult,
    MCPResourceContent,
    MCPServerStatus,
    MCPSystemStats,
    # Backward compatibility exports
    MCPToolCallResult,
    MCPToolsDiscovery,
)
from vmcp.shared.mcp_content_models import (
    MCPRegistryConfig as MCPRegistryConfigModel,
)
from vmcp.shared.mcp_content_models import (
    MCPRegistryStats as MCPRegistryStatsModel,
)
from vmcp.shared.mcp_content_models import (
    MCPServerConfig as MCPServerConfigModel,
)
from vmcp.shared.models import (
    AuthConfig,
    BaseResponse,
    ConnectionStatus,
    PaginatedResponse,
    ServerInfo,
    TransportType,
)
from vmcp.shared.validators import (
    validate_args,
    validate_auth_type,
    validate_boolean_field,
    validate_command,
    validate_description,
    validate_environment_variables,
    validate_headers,
    validate_server_id,
    validate_server_name,
    validate_transport_type,
    validate_url,
)

# ============================================================================
# BASE MCP MODELS
# ============================================================================

class MCPBaseRequest(BaseModel):
    """Base request model for MCP operations."""
    
    class Config:
        json_schema_extra = {
            "example": {
                "description": "Base MCP request"
            }
        }

class MCPBaseResponse(BaseResponse[Any]):
    """Base response model for MCP operations."""
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "MCP operation completed successfully",
                "data": {}
            }
        }

class MCPServerBase(ServerInfo):
    """Base MCP server configuration model."""
    
    transport_type: TransportType = Field(..., description="Transport type")
    url: Optional[str] = Field(None, description="Server URL for http/sse mode")
    command: Optional[str] = Field(None, description="Command to run for stdio server")
    args: Optional[List[str]] = Field(None, description="Command arguments")
    env: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    headers: Optional[Dict[str, str]] = Field(None, description="HTTP headers")
    auth: Optional[AuthConfig] = Field(None, description="Authentication configuration")
    auto_connect: bool = Field(True, description="Auto-connect on startup")
    enabled: bool = Field(True, description="Server enabled")
    
    @validator('transport_type', pre=True)
    def validate_transport_type(cls, v):
        return validate_transport_type(v)
    
    @validator('url')
    def validate_url_field(cls, v, values):
        if v and 'transport_type' in values:
            transport_type = values['transport_type']
            if transport_type in [TransportType.HTTP, TransportType.SSE]:
                return validate_url(v)
        return v
    
    @validator('command')
    def validate_command_field(cls, v, values):
        if v and 'transport_type' in values:
            transport_type = values['transport_type']
            if transport_type == TransportType.STDIO:
                return validate_command(v)
        return v
    
    @validator('env')
    def validate_env_field(cls, v):
        return validate_environment_variables(v)
    
    @validator('headers')
    def validate_headers_field(cls, v):
        return validate_headers(v)
    
    @validator('args')
    def validate_args_field(cls, v):
        return validate_args(v)
    
    @validator('description')
    def validate_description_field(cls, v):
        return validate_description(v)

# ============================================================================
# MCP REQUEST MODELS
# ============================================================================

class MCPInstallRequest(MCPBaseRequest):
    """Request model for installing an MCP server."""
    
    name: str = Field(..., description="Unique name for the MCP server")
    mode: str = Field(..., description="Transport mode: stdio, http, or sse")
    description: Optional[str] = Field(None, description="Server description")
    
    # For stdio servers
    command: Optional[str] = Field(None, description="Command to run for stdio server")
    args: Optional[List[str]] = Field(None, description="Command arguments")
    env: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    
    # For HTTP/SSE servers
    url: Optional[str] = Field(None, description="Server URL for http/sse mode")
    headers: Optional[Dict[str, str]] = Field(None, description="HTTP headers")
    
    # Authentication
    auth_type: Optional[str] = Field("none", description="Auth type: none, oauth, bearer, basic")
    client_id: Optional[str] = Field(None, description="OAuth client ID")
    client_secret: Optional[str] = Field(None, description="OAuth client secret")
    auth_url: Optional[str] = Field(None, description="OAuth authorization URL")
    token_url: Optional[str] = Field(None, description="OAuth token URL")
    scope: Optional[str] = Field(None, description="OAuth scope")
    access_token: Optional[str] = Field(None, description="Bearer token")
    
    # Settings
    auto_connect: bool = Field(True, description="Auto-connect on startup")
    enabled: bool = Field(True, description="Server enabled")
    
    @validator('name')
    def validate_name(cls, v):
        return validate_server_name(v)
    
    @validator('mode')
    def validate_mode(cls, v):
        return validate_transport_type(v)
    
    @validator('description')
    def validate_description(cls, v):
        return validate_description(v)
    
    @validator('url')
    def validate_url(cls, v, values):
        if v and 'mode' in values:
            mode = values['mode']
            if mode in ['http', 'sse']:
                return validate_url(v)
        return v
    
    @validator('command')
    def validate_command(cls, v, values):
        if v and 'mode' in values:
            mode = values['mode']
            if mode == 'stdio':
                return validate_command(v)
        return v
    
    @validator('env')
    def validate_env(cls, v):
        return validate_environment_variables(v)
    
    @validator('headers')
    def validate_headers(cls, v):
        return validate_headers(v)
    
    @validator('args')
    def validate_args(cls, v):
        return validate_args(v)
    
    @validator('auth_type')
    def validate_auth_type(cls, v):
        return validate_auth_type(v)
    
    @validator('auto_connect')
    def validate_auto_connect(cls, v):
        return validate_boolean_field(v, 'auto_connect')
    
    @validator('enabled')
    def validate_enabled(cls, v):
        return validate_boolean_field(v, 'enabled')
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "My MCP Server",
                "mode": "stdio",
                "description": "My MCP Server Description",
                "command": "python",
                "args": ["-m", "my_server"],
                "env": {"PYTHONPATH": "/path/to/server"},
                "auto_connect": True,
                "enabled": True
            }
        }

class MCPUpdateRequest(MCPBaseRequest):
    """Request model for updating an MCP server."""
    
    name: str = Field(..., description="Server name (can be changed)")
    mode: str = Field(..., description="Transport mode: stdio, http, or sse")
    description: Optional[str] = Field(None, description="Server description")
    
    # For stdio servers
    command: Optional[str] = Field(None, description="Command to run for stdio server")
    args: Optional[List[str]] = Field(None, description="Command arguments")
    env: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    
    # For HTTP/SSE servers
    url: Optional[str] = Field(None, description="Server URL for http/sse mode")
    headers: Optional[Dict[str, str]] = Field(None, description="HTTP headers")
    
    # Authentication
    auth_type: Optional[str] = Field("none", description="Auth type: none, oauth, bearer, basic")
    client_id: Optional[str] = Field(None, description="OAuth client ID")
    client_secret: Optional[str] = Field(None, description="OAuth client secret")
    auth_url: Optional[str] = Field(None, description="OAuth authorization URL")
    token_url: Optional[str] = Field(None, description="OAuth token URL")
    scope: Optional[str] = Field(None, description="OAuth scope")
    access_token: Optional[str] = Field(None, description="Bearer token")
    
    # Settings
    auto_connect: bool = Field(True, description="Auto-connect on startup")
    enabled: bool = Field(True, description="Server enabled")
    
    @validator('name')
    def validate_name(cls, v):
        return validate_server_name(v)
    
    @validator('mode')
    def validate_mode(cls, v):
        return validate_transport_type(v)
    
    @validator('description')
    def validate_description(cls, v):
        return validate_description(v)
    
    @validator('url')
    def validate_url(cls, v, values):
        if v and 'mode' in values:
            mode = values['mode']
            if mode in ['http', 'sse']:
                return validate_url(v)
        return v

    @validator('command')
    def validate_command(cls, v, values):
        if v and 'mode' in values:
            mode = values['mode']
            if mode == 'stdio':
                return validate_command(v)
        return v
    
    @validator('env')
    def validate_env(cls, v):
        return validate_environment_variables(v)
    
    @validator('headers')
    def validate_headers(cls, v):
        return validate_headers(v)
    
    @validator('args')
    def validate_args(cls, v):
        return validate_args(v)
    
    @validator('auth_type')
    def validate_auth_type(cls, v):
        return validate_auth_type(v)
    
    @validator('auto_connect')
    def validate_auto_connect(cls, v):
        return validate_boolean_field(v, 'auto_connect')
    
    @validator('enabled')
    def validate_enabled(cls, v):
        return validate_boolean_field(v, 'enabled')

class RenameServerRequest(MCPBaseRequest):
    """Request model for renaming an MCP server."""
    
    new_name: str = Field(..., description="New server name")
    
    @validator('new_name')
    def validate_new_name(cls, v):
        return validate_server_name(v)
    
    class Config:
        json_schema_extra = {
            "example": {
                "new_name": "My Renamed Server"
            }
        }

class MCPToolCallRequest(MCPBaseRequest):
    """Request model for calling an MCP tool."""
    
    tool_name: str = Field(..., description="Name of the tool to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    
    @validator('tool_name')
    def validate_tool_name(cls, v):
        return validate_server_name(v)  # Reuse server name validation for tool names
    
    class Config:
        json_schema_extra = {
            "example": {
                "tool_name": "search_tool",
                "arguments": {
                    "query": "search term",
                    "limit": 10
                }
            }
        }

class MCPResourceRequest(MCPBaseRequest):
    """Request model for reading an MCP resource."""
    
    uri: str = Field(..., description="Resource URI to read")
    
    @validator('uri')
    def validate_uri(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("URI must be a non-empty string")
        if len(v) > 2000:
            raise ValueError("URI must be less than 2000 characters")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "uri": "file:///path/to/resource.txt"
            }
        }

class MCPPromptRequest(MCPBaseRequest):
    """Request model for getting an MCP prompt."""
    
    prompt_name: str = Field(..., description="Name of the prompt to get")
    arguments: Optional[Dict[str, Any]] = Field(None, description="Prompt arguments")
    
    @validator('prompt_name')
    def validate_prompt_name(cls, v):
        return validate_server_name(v)  # Reuse server name validation for prompt names
    
    class Config:
        json_schema_extra = {
            "example": {
                "prompt_name": "summarize_prompt",
                "arguments": {
                    "text": "Text to summarize",
                    "max_length": 100
                }
            }
        }

# ============================================================================
# MCP RESPONSE MODELS
# ============================================================================

class MCPServerInfo(MCPServerBase):
    """Response model for MCP server information."""
    
    last_connected: Optional[datetime] = Field(None, description="Last connection timestamp")
    last_error: Optional[str] = Field(None, description="Last error message")
    capabilities: Optional[MCPCapabilities] = Field(None, description="Server capabilities")
    tools: Optional[List[str]] = Field(None, description="Available tool names")
    resources: Optional[List[str]] = Field(None, description="Available resource URIs")
    resource_templates: Optional[List[str]] = Field(None, description="Available resource template URIs")
    prompts: Optional[List[str]] = Field(None, description="Available prompt names")
    tool_details: Optional[List[Tool]] = Field(None, description="Detailed tool information")
    resource_details: Optional[List[Resource]] = Field(None, description="Detailed resource information")
    resource_template_details: Optional[List[ResourceTemplate]] = Field(None, description="Detailed resource template information")
    prompt_details: Optional[List[Prompt]] = Field(None, description="Detailed prompt information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "server_123",
                "name": "My MCP Server",
                "description": "A sample MCP server",
                "status": "connected",
                "transport_type": "stdio",
                "command": "python",
                "args": ["-m", "my_server"],
                "auto_connect": True,
                "enabled": True,
                "capabilities": {
                    "tools": True,
                    "resources": False,
                    "prompts": True,
                    "tools_count": 5,
                    "resources_count": 0,
                    "prompts_count": 3
                }
            }
        }

class MCPInstallResponse(MCPBaseResponse):
    """Response model for MCP server installation."""
    
    data: MCPServerInfo = Field(..., description="Installed server information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "MCP server 'My Server' installed successfully",
                "data": {
                    "id": "server_123",
                    "name": "My Server",
                    "status": "disconnected",
                    "transport_type": "stdio"
                }
            }
        }

class MCPUpdateResponse(MCPBaseResponse):
    """Response model for MCP server update."""

    data: MCPServerInfo = Field(..., description="Updated server information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "MCP server 'My Server' updated successfully",
                "data": {
                    "id": "server_123",
                    "name": "My Server",
                    "status": "connected",
                    "transport_type": "stdio"
                }
            }
        }

class MCPRenameResponse(MCPBaseResponse):
    """Response model for MCP server rename."""
    
    data: Dict[str, str] = Field(..., description="Rename operation details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Server renamed from 'Old Name' to 'New Name' successfully",
                "data": {
                    "old_name": "Old Name",
                    "new_name": "New Name",
                    "server_id": "server_123"
                }
            }
        }

class MCPUninstallResponse(MCPBaseResponse):
    """Response model for MCP server uninstall."""
    
    data: Dict[str, str] = Field(..., description="Uninstall operation details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "MCP server 'My Server' uninstalled successfully",
                "data": {
                    "server_id": "server_123",
                    "server_name": "My Server"
                }
            }
        }

class MCPConnectionResponse(MCPBaseResponse):
    """Response model for MCP server connection operations."""
    
    data: MCPConnectionInfo = Field(..., description="Connection operation details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Successfully connected to server 'My Server'",
                "data": {
                    "server_id": "server_123",
                    "status": "connected",
                    "requires_auth": False
                }
            }
        }

class MCPDisconnectResponse(MCPBaseResponse):
    """Response model for MCP server disconnect operations."""
    
    data: Dict[str, str] = Field(..., description="Disconnect operation details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Server 'My Server' disconnected successfully",
                "data": {
                    "server_id": "server_123",
                    "status": "disconnected"
                }
            }
        }

class MCPPingResponse(MCPBaseResponse):
    """Response model for MCP server ping operations."""
    
    data: MCPPingInfo = Field(..., description="Ping operation details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Server ping successful",
                "data": {
                    "server": "server_123",
                    "alive": True,
                    "timestamp": "2024-01-01T00:00:00Z"
                }
            }
        }

class MCPStatusResponse(MCPBaseResponse):
    """Response model for MCP server status."""
    
    data: MCPServerStatus = Field(..., description="Server status details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Server status retrieved",
                "data": {
                    "server_id": "server_123",
                    "status": "connected",
                    "last_updated": "2024-01-01T00:00:00Z"
                }
            }
        }

class MCPCapabilitiesResponse(MCPBaseResponse):
    """Response model for MCP server capabilities discovery."""
    
    data: Dict[str, Any] = Field(..., description="Server capabilities details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Successfully discovered capabilities for server 'My Server'",
                "data": {
                    "capabilities": {
                        "tools_count": 5,
                        "resources_count": 3,
                        "prompts_count": 2
                    },
                    "tools_list": ["tool1", "tool2"],
                    "resources_list": ["resource1", "resource2"],
                    "prompts_list": ["prompt1", "prompt2"]
                }
            }
        }

class MCPToolsResponse(MCPBaseResponse):
    """Response model for MCP server tools list."""
    
    data: Dict[str, Any] = Field(..., description="Server tools details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Tools retrieved successfully",
                "data": {
                    "server": "server_123",
                    "tools": [
                        {
                            "name": "search_tool",
                            "description": "Search for information",
                            "inputSchema": {}
                        }
                    ],
                    "total_tools": 1
                }
            }
        }

class MCPResourcesResponse(MCPBaseResponse):
    """Response model for MCP server resources list."""
    
    data: Dict[str, Any] = Field(..., description="Server resources details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Resources retrieved successfully",
                "data": {
                    "server": "server_123",
                    "resources": [
                        {
                            "uri": "file:///path/to/resource",
                            "description": "A file resource"
                        }
                    ],
                    "total_resources": 1
                }
            }
        }

class MCPPromptsResponse(MCPBaseResponse):
    """Response model for MCP server prompts list."""
    
    data: Dict[str, Any] = Field(..., description="Server prompts details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Prompts retrieved successfully",
                "data": {
                    "server": "server_123",
                    "prompts": [
                        {
                            "name": "summarize_prompt",
                            "description": "Summarize text content"
                        }
                    ],
                    "total_prompts": 1
                }
            }
        }

class MCPToolCallResponse(MCPBaseResponse):
    """Response model for MCP tool call execution."""
    
    data: MCPToolCallResult = Field(..., description="Tool call execution details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Tool executed successfully",
                "data": {
                    "server": "server_123",
                    "tool": "search_tool",
                    "result": "Search results here"
                }
            }
        }

class MCPResourceResponse(MCPBaseResponse):
    """Response model for MCP resource read operations."""
    
    data: MCPResourceContent = Field(..., description="Resource read details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Resource read successfully",
                "data": {
                    "server": "server_123",
                    "uri": "file:///path/to/resource",
                    "contents": "Resource content here"
                }
            }
        }

class MCPPromptResponse(MCPBaseResponse):
    """Response model for MCP prompt operations."""
    
    data: MCPPromptResult = Field(..., description="Prompt operation details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Prompt retrieved successfully",
                "data": {
                    "server": "server_123",
                    "prompt": "summarize_prompt",
                    "messages": ["System message", "User message"]
                }
            }
        }

class MCPListResponse(PaginatedResponse[MCPServerInfo]):
    """Response model for MCP servers list."""
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Servers retrieved successfully",
                "data": [
                    {
                        "id": "server_123",
                        "name": "My Server",
                        "status": "connected",
                        "transport_type": "stdio"
                    }
                ],
                "pagination": {
                    "page": 1,
                    "limit": 50,
                    "total": 1,
                    "pages": 1
                }
            }
        }

class MCPStatsResponse(MCPBaseResponse):
    """Response model for MCP system statistics."""
    
    data: MCPSystemStats = Field(..., description="System statistics")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Statistics retrieved successfully",
                "data": {
                    "servers": {
                        "total": 5,
                        "connected": 3,
                        "disconnected": 1,
                        "auth_required": 1,
                        "errors": 0
                    },
                    "capabilities": {
                        "tools": 15,
                        "resources": 8,
                        "prompts": 5
                    }
                }
            }
        }

class MCPToolsDiscoverResponse(MCPBaseResponse):
    """Response model for discovering all available tools."""
    
    data: MCPToolsDiscovery = Field(..., description="Discovered tools details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Tools discovered successfully",
                "data": {
                    "tools": [
                        {
                            "name": "server1_search_tool",
                            "original_name": "search_tool",
                            "server": "server1",
                            "description": "Tool 'search_tool' from server1 server",
                            "server_id": "server_123"
                        }
                    ],
                    "total_tools": 1,
                    "connected_servers": 1
                }
            }
        }

# ============================================================================
# LEGACY COMPATIBILITY
# ============================================================================

# Keep the old enum names for backward compatibility
MCPTransportType = TransportType
MCPConnectionStatus = ConnectionStatus
MCPAuthConfig = AuthConfig

# Keep the old dataclass for backward compatibility (will be deprecated)
import hashlib
import json
from dataclasses import asdict, dataclass, field


@dataclass
class MCPServerConfig:
    """Legacy MCP Server configuration dataclass - DEPRECATED, use MCPServerInfo instead."""
    
    name: str
    transport_type: MCPTransportType
    description: Optional[str] = None
    server_id: Optional[str] = None
    favicon_url: Optional[str] = None
    
    # For stdio servers
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    
    # For HTTP/SSE servers
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    
    # Authentication
    auth: Optional[MCPAuthConfig] = None
    
    # Session ID for persistence across connections
    session_id: Optional[str] = None
    
    # Status and metadata
    status: MCPConnectionStatus = MCPConnectionStatus.UNKNOWN
    last_connected: Optional[datetime] = None
    last_error: Optional[str] = None
    
    # Capabilities discovered from server
    capabilities: Optional[Dict[str, Any]] = field(default_factory=dict)
    tools: Optional[List[str]] = field(default_factory=list)
    tool_details: Optional[List[Tool]] = field(default_factory=list)
    resources: Optional[List[str]] = field(default_factory=list)
    resource_details: Optional[List[Resource]] = field(default_factory=list)
    resource_templates: Optional[List[str]] = field(default_factory=list)
    resource_template_details: Optional[List[ResourceTemplate]] = field(default_factory=list)
    prompts: Optional[List[str]] = field(default_factory=list)
    prompt_details: Optional[List[Prompt]] = field(default_factory=list)
    
    # Auto-connect settings
    auto_connect: bool = True
    enabled: bool = True
    
    # vMCP usage tracking
    vmcps_using_server: List[str] = field(default_factory=list)
    
    def to_mcp_registry_config(self) -> 'MCPRegistryConfig':
        """Convert to MCPRegistryConfig for registry operations."""
        return MCPRegistryConfig(
            name=self.name,
            transport_type=self.transport_type,
            description=self.description,
            server_id=self.server_id,
            favicon_url=self.favicon_url,
            command=self.command,
            args=self.args,
            env=self.env,
            url=self.url,
            headers=self.headers,
        )
    
    def generate_server_id(self) -> str:
        """Generate a unique server ID based on transport configuration."""
        config_data = {
            "transport_type": self.transport_type.value,
        }
        
        if self.transport_type == MCPTransportType.STDIO:
            config_data.update({
                "command": self.command,
                "args": sorted(self.args) if self.args else [],
                "env": dict(sorted(self.env.items())) if self.env else {}
            })
        else:
            config_data.update({
                "url": self.url,
                "headers": dict(sorted(self.headers.items())) if self.headers else {}
            })
        
        config_json = json.dumps(config_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(config_json.encode()).hexdigest()[:16]
    
    def ensure_server_id(self) -> str:
        """Ensure server has an ID, generate if missing."""
        if not self.server_id:
            self.server_id = self.generate_server_id()
        return self.server_id
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['transport_type'] = self.transport_type.value
        data['status'] = self.status.value if self.status else 'unknown'
        
        if not data.get('server_id'):
            data['server_id'] = self.ensure_server_id()
        
        if self.last_connected:
            data['last_connected'] = self.last_connected.isoformat()
        
        # Handle auth serialization (could be dataclass, Pydantic model, or dict)
        if self.auth:
            from dataclasses import is_dataclass
            from pydantic import BaseModel
            
            if is_dataclass(self.auth):
                # It's a dataclass, use asdict
                data['auth'] = asdict(self.auth)
                if self.auth.expires_at:
                    data['auth']['expires_at'] = self.auth.expires_at.isoformat()
            elif isinstance(self.auth, BaseModel):
                # It's a Pydantic model, use model_dump
                data['auth'] = self.auth.model_dump()
            elif isinstance(self.auth, dict):
                # It's already a dict
                data['auth'] = self.auth
            else:
                # Unknown type, try to convert to dict
                data['auth'] = dict(self.auth) if hasattr(self.auth, '__dict__') else self.auth

        # Convert Pydantic models (Tool, Prompt, Resource, ResourceTemplate) to dicts
        from pydantic import BaseModel

        def serialize_pydantic(obj):
            """Serialize Pydantic model to dict, converting AnyUrl to string"""
            if isinstance(obj, BaseModel):
                # Use mode='python' to get Python objects, then convert AnyUrl to str
                result = obj.model_dump(mode='python')
                # Recursively convert any AnyUrl objects to strings
                return convert_anyurl_to_str(result)
            return obj
        
        def convert_anyurl_to_str(obj):
            """Recursively convert AnyUrl objects to strings in nested structures"""
            if hasattr(obj, '__class__') and obj.__class__.__name__ == 'AnyUrl':
                return str(obj)
            elif isinstance(obj, dict):
                return {k: convert_anyurl_to_str(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_anyurl_to_str(item) for item in obj]
            return obj
        
        if self.tool_details:
            data['tool_details'] = [
                serialize_pydantic(tool) for tool in self.tool_details
            ]
        
        if self.prompt_details:
            data['prompt_details'] = [
                serialize_pydantic(prompt) for prompt in self.prompt_details
            ]
        
        if self.resource_details:
            data['resource_details'] = [
                serialize_pydantic(resource) for resource in self.resource_details
            ]
        
        if self.resource_template_details:
            data['resource_template_details'] = [
                serialize_pydantic(template) for template in self.resource_template_details
            ]
        
        return data
    
    def to_dict_for_vmcp(self) -> Dict[str, Any]:
        """Convert to dictionary for vMCP usage, excluding auth and session_id fields."""
        data = self.to_dict()
        data.pop('auth', None)
        data.pop('session_id', None)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPServerConfig':
        """Create from dictionary (JSON deserialization)."""
        from mcp.types import Tool, Resource, ResourceTemplate, Prompt
        
        data['transport_type'] = MCPTransportType(data['transport_type'])
        data['status'] = MCPConnectionStatus(data['status'])
        
        if data.get('last_connected'):
            data['last_connected'] = datetime.fromisoformat(data['last_connected'])
        
        if data.get('auth'):
            auth_data = data['auth']
            if auth_data.get('expires_at'):
                auth_data['expires_at'] = datetime.fromisoformat(auth_data['expires_at'])
            data['auth'] = MCPAuthConfig(**auth_data)
        
        # Convert dictionaries back to Pydantic models for tool_details, prompt_details, etc.
        if data.get('tool_details'):
            data['tool_details'] = [
                Tool(**tool) if isinstance(tool, dict) else tool
                for tool in data['tool_details']
            ]
        
        if data.get('prompt_details'):
            data['prompt_details'] = [
                Prompt(**prompt) if isinstance(prompt, dict) else prompt
                for prompt in data['prompt_details']
            ]
        
        if data.get('resource_details'):
            data['resource_details'] = [
                Resource(**resource) if isinstance(resource, dict) else resource
                for resource in data['resource_details']
            ]
        
        if data.get('resource_template_details'):
            data['resource_template_details'] = [
                ResourceTemplate(**template) if isinstance(template, dict) else template
                for template in data['resource_template_details']
            ]
        
        list_fields = [
            'args', 'tools', 'resources', 
            'resource_templates', 'prompts',
            'vmcps_using_server'
        ]
        for field in list_fields:
            if data.get(field) is None:
                data[field] = []
        
        dict_fields = ['env', 'headers', 'capabilities']
        for field in dict_fields:
            if data.get(field) is None:
                data[field] = {}
        
        return cls(**data)

@dataclass
class MCPRegistryConfig:
    """MCP Registry configuration dataclass."""
    
    name: str
    transport_type: MCPTransportType
    description: Optional[str] = None
    server_id: Optional[str] = None
    favicon_url: Optional[str] = None
    
    # For stdio servers
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    
    # For HTTP/SSE servers
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['transport_type'] = self.transport_type.value
        return data


# ============================================================================
# REGISTRY RESPONSE MODELS
# ============================================================================

class RegistryServerInfo(BaseModel):
    """Information about a server in the registry."""
    
    id: str = Field(..., description="Server ID")
    name: str = Field(..., description="Server name")
    description: str = Field(..., description="Server description")
    transport: str = Field(..., description="Transport type")
    url: Optional[str] = Field(None, description="Server URL")
    favicon_url: Optional[str] = Field(None, description="Favicon URL")
    category: str = Field(..., description="Server category")
    icon: str = Field(..., description="Server icon")
    requiresAuth: bool = Field(False, description="Whether server requires authentication")
    env_vars: str = Field("", description="Environment variables")
    note: str = Field("", description="Additional notes")
    mcp_registry_config: MCPRegistryConfigModel = Field(..., description="MCP registry configuration")
    mcp_server_config: MCPServerConfigModel = Field(..., description="MCP server configuration")
    stats: MCPRegistryStatsModel = Field(..., description="Server statistics")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "server_123",
                "name": "example-server",
                "description": "Example MCP server",
                "transport": "http",
                "url": "http://localhost:8000/mcp",
                "favicon_url": "http://example.com/favicon.ico",
                "category": "Development",
                "icon": "🔧",
                "requiresAuth": False,
                "env_vars": "",
                "note": "",
                "mcp_registry_config": {},
                "mcp_server_config": {},
                "stats": {},
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }
        }

class RegistryServersResponse(BaseModel):
    """Response model for listing registry servers."""
    
    success: bool = Field(True, description="Whether the operation was successful")
    servers: List[RegistryServerInfo] = Field(..., description="List of registry servers")
    total: int = Field(..., description="Total number of servers")
    limit: int = Field(..., description="Pagination limit")
    offset: int = Field(..., description="Pagination offset")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "servers": [
                    {
                        "id": "server_123",
                        "name": "example-server",
                        "description": "Example MCP server",
                        "transport": "http",
                        "url": "http://localhost:8000/mcp",
                        "favicon_url": "http://example.com/favicon.ico",
                        "category": "Development",
                        "icon": "🔧",
                        "requiresAuth": False,
                        "env_vars": "",
                        "note": "",
                        "mcp_registry_config": {},
                        "mcp_server_config": {},
                        "stats": {},
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-01-01T00:00:00Z"
                    }
                ],
                "total": 1,
                "limit": 100,
                "offset": 0
            }
        }

# Custom exception classes for MCP operations
class AuthenticationError(Exception):
    """Raised when authentication fails"""
    pass

class HTTPError(Exception):
    """Raised when HTTP errors occur"""
    pass

class OperationCancelledError(Exception):
    """Raised when operations are cancelled"""
    pass

class OperationTimedOutError(Exception):
    """Raised when operations timeout"""
    pass

class MCPOperationError(Exception):
    """Raised when operations fail"""
    pass

class InvalidSessionIdError(Exception):
    """Raised when session id is invalid"""
    pass

class BadMCPRequestError(Exception):
    """Raised when MCP server returns a bad request"""
    pass

class MCPBadRequestError(Exception):
    """Raised when MCP server returns a bad request"""
    pass