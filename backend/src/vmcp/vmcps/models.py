"""
vMCP (Virtual Model Context Protocol) models with proper inheritance and type safety.

This module contains all vMCP-related request and response models that extend
the base shared models to provide type-safe API endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, model_validator, root_validator, validator

from vmcp.shared.models import (
    AuthConfig,
    AuthType,
    BaseResponse,
    CapabilitiesInfo,
    ConnectionStatus,
    ErrorResponse,
    PaginatedResponse,
    PromptInfo,
    ResourceInfo,
    ServerInfo,
    ToolInfo,
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
    validate_optional_string,
    validate_required_string,
    validate_server_id,
    validate_server_name,
    validate_transport_type,
    validate_url,
)
from vmcp.shared.vmcp_content_models import (
    CustomPrompt,
    CustomResource,
    CustomResourceTemplate,
    CustomTool,
    CustomWidget,
    EnvironmentVariable,
    SystemPrompt,
    UploadedFile,
    VMCPConfigData,
)

# ============================================================================
# BASE VMCP MODELS
# ============================================================================

class VMCPBaseRequest(BaseModel):
    """Base request model for vMCP operations."""

    class Config:
        # Allow empty dicts to be parsed
        extra = "allow"

class VMCPBaseResponse(BaseResponse[Any]):
    """Base response model for vMCP operations."""

    # class Config:
    #     json_schema_extra = {
    #         "example": {
    #             "success": True,
    #             "message": "vMCP operation completed successfully",
    #             "data": {}
    #         }
    #     }

class VMCPConfigBase(ServerInfo):
    """Base vMCP configuration model."""

    user_id: str = Field(..., description="User ID who owns this vMCP")
    system_prompt: Optional[SystemPrompt] = Field(None, description="System prompt configuration")
    vmcp_config: Optional[VMCPConfigData] = Field(None, description="vMCP configuration")
    custom_prompts: List[CustomPrompt] = Field(default_factory=list, description="Custom prompts")
    custom_tools: List[CustomTool] = Field(default_factory=list, description="Custom tools")
    custom_context: List[str] = Field(default_factory=list, description="Custom context")
    custom_resources: List[CustomResource] = Field(default_factory=list, description="Custom resources")
    custom_resource_templates: List[CustomResourceTemplate] = Field(default_factory=list, description="Custom resource templates")
    custom_widgets: List[CustomWidget] = Field(default_factory=list, description="Custom widgets")
    environment_variables: List[EnvironmentVariable] = Field(default_factory=list, description="Environment variables")
    uploaded_files: List[UploadedFile] = Field(default_factory=list, description="Uploaded files")
    custom_resource_uris: List[str] = Field(default_factory=list, description="Custom resource URIs")

    @validator('user_id')
    def validate_user_id(cls, v):
        return validate_required_string(v, 'user_id', 255)
    
    @validator('description')
    def validate_description(cls, v):
        return validate_description(v)

# ============================================================================
# VMCP REQUEST MODELS
# ============================================================================

class VMCPCreateRequest(VMCPBaseRequest):
    """Request model for creating a vMCP."""
    
    name: str = Field(..., description="vMCP name")
    description: Optional[str] = Field(None, description="vMCP description")
    system_prompt: Optional[SystemPrompt] = Field(None, description="System prompt object with text and variables")
    vmcp_config: Optional[VMCPConfigData] = Field(None, description="vMCP configuration")
    custom_prompts: Optional[List[CustomPrompt]] = Field(default_factory=list, description="Custom prompts")
    custom_tools: Optional[List[CustomTool]] = Field(default_factory=list, description="Custom tools")
    custom_context: Optional[List[str]] = Field(default_factory=list, description="Custom context")
    custom_resources: Optional[List[CustomResource]] = Field(default_factory=list, description="Custom resources")
    custom_resource_templates: Optional[List[CustomResourceTemplate]] = Field(default_factory=list, description="Custom resource templates")
    custom_resource_uris: Optional[List[str]] = Field(default_factory=list, description="Custom resource URIs")
    environment_variables: Optional[List[EnvironmentVariable]] = Field(default_factory=list, description="Environment variables")
    uploaded_files: Optional[List[UploadedFile]] = Field(default_factory=list, description="Uploaded files")
    
    class Config:
        extra = "allow"  # Allow extra fields for backward compatibility
    
    @validator('name')
    def validate_name(cls, v):
        return validate_server_name(v)
    
    @validator('description')
    def validate_description(cls, v):
        return validate_description(v)
    
    # class Config:
    #     json_schema_extra = {
    #         "example": {
    #             "name": "My vMCP",
    #             "description": "A sample vMCP configuration",
    #             "system_prompt": {
    #                 "text": "You are a helpful assistant",
    #                 "variables": []
    #             },
    #             "vmcp_config": {
    #                 "selected_servers": []
    #             },
    #             "custom_prompts": [],
    #             "custom_tools": [],
    #             "environment_variables": []
    #         }
    #     }

class VMCPUdateRequest(VMCPBaseRequest):
    """Request model for updating a vMCP."""
    
    name: Optional[str] = Field(None, description="vMCP name")
    description: Optional[str] = Field(None, description="vMCP description")
    system_prompt: Optional[SystemPrompt] = Field(None, description="System prompt object with text and variables")
    vmcp_config: Optional[VMCPConfigData] = Field(None, description="vMCP configuration")
    custom_prompts: Optional[List[CustomPrompt]] = Field(default_factory=list, description="Custom prompts")
    custom_tools: Optional[List[CustomTool]] = Field(default_factory=list, description="Custom tools")
    custom_context: Optional[List[str]] = Field(default_factory=list, description="Custom context")
    custom_resources: Optional[List[CustomResource]] = Field(default_factory=list, description="Custom resources")
    custom_resource_templates: Optional[List[CustomResourceTemplate]] = Field(default_factory=list, description="Custom resource templates")
    custom_resource_uris: Optional[List[str]] = Field(default_factory=list, description="Custom resource URIs")
    environment_variables: Optional[List[EnvironmentVariable]] = Field(default_factory=list, description="Environment variables")
    uploaded_files: Optional[List[UploadedFile]] = Field(default_factory=list, description="Uploaded files")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata")
    
    class Config:
        extra = "allow"  # Allow extra fields for backward compatibility
    
    @validator('name')
    def validate_name(cls, v):
        if v is not None:
            return validate_server_name(v)
        return v
    
    @validator('description')
    def validate_description(cls, v):
        return validate_description(v)

class VMCPToolCallRequest(VMCPBaseRequest):
    """Request model for calling a vMCP tool.
    
    Matches frontend interface: VMCPToolCallRequest
    - tool_name: Name of the tool to execute
    - arguments: Tool-specific parameters as key-value pairs
    """
    
    tool_name: str = Field(..., description="Name of the tool to call (without server prefix)")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments/parameters as a dictionary")
    
    @validator('tool_name')
    def validate_tool_name(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("tool_name must be a non-empty string")
        if len(v) > 255:
            raise ValueError("tool_name must be less than 255 characters")
        return v
    
    @validator('arguments')
    def validate_arguments(cls, v):
        if not isinstance(v, dict):
            raise ValueError("arguments must be a dictionary")
        return v
    
    class Config:
        pass

class VMCPResourceRequest(VMCPBaseRequest):
    """Request model for reading a vMCP resource.
    
    Matches frontend interface: VMCPResourceRequest
    - uri: Resource URI identifier
    """
    
    uri: str = Field(..., description="Resource URI to read (e.g., 'file:///path/to/resource', 'blob://blob-id')")
    
    @validator('uri')
    def validate_uri(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("URI must be a non-empty string")
        if len(v) > 2000:
            raise ValueError("URI must be less than 2000 characters")
        return v
    
    class Config:
        pass

class VMCPResourceTemplateRequest(VMCPBaseRequest):
    """Request model for using a vMCP resource template."""
    
    template_name: str = Field(..., description="Name of the resource template")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Template parameters")
    
    @validator('template_name')
    def validate_template_name(cls, v):
        return validate_server_name(v)  # Reuse server name validation for template names
    
    class Config:
        pass

class VMCPPromptRequest(VMCPBaseRequest):
    """Request model for getting a vMCP prompt.
    
    Matches frontend interface: VMCPPromptRequest
    - prompt_id: Can be a custom prompt (starts with '#') or server prompt name
    - arguments: Optional prompt arguments for variable substitution
    """
    
    prompt_id: str = Field(..., description="Prompt ID or name. Custom prompts use '#{name}' format, server prompts use the prompt name directly")
    arguments: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Prompt arguments for variable substitution")
    
    @validator('prompt_id')
    def validate_prompt_id(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("prompt_id must be a non-empty string")
        if len(v) > 255:
            raise ValueError("prompt_id must be less than 255 characters")
        return v
    
    class Config:
        pass

class VMCPEnvironmentVariablesRequest(VMCPBaseRequest):
    """Request model for updating vMCP environment variables.
    
    Matches frontend expectations from saveVMCPEnvironmentVariables.
    The frontend sends a list of EnvironmentVariable objects.
    """
    
    environment_variables: List[EnvironmentVariable] = Field(..., description="List of environment variables to save")
    
    class Config:
        pass

class VMCPShareState(str, Enum):
    """Enum for vMCP sharing states."""
    
    PUBLIC = "public"
    SHARED = "shared"
    PRIVATE = "private"

class VMCPShareRequest(VMCPBaseRequest):
    """Request model for sharing a vMCP."""
    
    vmcp_id: str = Field(..., description="vMCP ID to share")
    state: VMCPShareState = Field(..., description="Sharing state")
    tags: Optional[List[str]] = Field(None, description="Tags for the shared vMCP")
    
    @validator('vmcp_id')
    def validate_vmcp_id(cls, v):
        return validate_server_id(v)
    
    @validator('tags')
    def validate_tags(cls, v):
        if v is not None:
            if not isinstance(v, list):
                raise ValueError("Tags must be a list")
            
            for i, tag in enumerate(v):
                if not isinstance(tag, str):
                    raise ValueError(f"Tag {i} must be a string")
                if len(tag) > 50:
                    raise ValueError(f"Tag {i} must be less than 50 characters")
        
        return v
    
    class Config:
        extra = "forbid"  # Reject any extra fields

class VMCPInstallRequest(VMCPBaseRequest):
    """Request model for installing a public vMCP."""
    
    public_vmcp_id: str = Field(..., description="Public vMCP ID to install")
    
    @validator('public_vmcp_id')
    def validate_public_vmcp_id(cls, v):
        """Validate public vMCP ID format - allows @ and : characters for namespaced IDs."""
        import re
        if not v or not isinstance(v, str):
            raise ValueError("Public vMCP ID must be a non-empty string")
        
        if len(v) < 1:
            raise ValueError("Public vMCP ID must be at least 1 character long")
        
        if len(v) > 255:
            raise ValueError("Public vMCP ID must be less than 255 characters")
        
        # Allow alphanumeric, underscore, hyphen, @, and : for namespaced IDs like @user:vmcp_name
        if not re.match(r'^[a-zA-Z0-9_\-@:]+$', v):
            raise ValueError("Public vMCP ID can only contain alphanumeric characters, underscores, hyphens, @, and colons")
        
        return v
    
    class Config:
        pass

class VMCPAddServerData(BaseModel):
    """Server data model for adding a server to a vMCP.
    
    Matches frontend MCPInstallRequest structure with optional server_id for existing servers.
    Can be used directly or wrapped in mcp_server_config.
    """
    
    # Optional server_id for existing servers
    server_id: Optional[str] = Field(None, description="Existing server ID (if adding existing server)")
    
    # Required fields (name is required if server_id not provided)
    name: Optional[str] = Field(None, description="Server name (required if server_id not provided)")
    mode: Optional[str] = Field(None, description="Transport mode: stdio, http, or sse (alternative to transport)")
    transport: Optional[str] = Field(None, description="Transport type: stdio, http, or sse (alternative to mode)")
    description: Optional[str] = Field(None, description="Server description")
    
    # For stdio servers
    command: Optional[str] = Field(None, description="Command to run for stdio server")
    args: Optional[List[str]] = Field(None, description="Command arguments")
    env: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    
    # For HTTP/SSE servers
    url: Optional[str] = Field(None, description="Server URL for http/sse mode")
    headers: Optional[Dict[str, str]] = Field(None, description="HTTP headers")
    
    # Authentication
    auth_type: Optional[str] = Field(None, description="Auth type: none, oauth, bearer, basic")
    client_id: Optional[str] = Field(None, description="OAuth client ID")
    client_secret: Optional[str] = Field(None, description="OAuth client secret")
    auth_url: Optional[str] = Field(None, description="OAuth authorization URL")
    token_url: Optional[str] = Field(None, description="OAuth token URL")
    scope: Optional[str] = Field(None, description="OAuth scope")
    access_token: Optional[str] = Field(None, description="Bearer token")
    
    # Settings
    auto_connect: Optional[bool] = Field(True, description="Auto-connect on startup")
    enabled: Optional[bool] = Field(True, description="Server enabled")
    favicon_url: Optional[str] = Field(None, description="Favicon URL for the server")
    
    class Config:
        extra = "allow"  # Allow extra fields for backward compatibility
    
    @validator('name')
    def validate_name(cls, v):
        """Validate name format if provided."""
        if v:
            return validate_server_name(v)
        return v
    
    @validator('server_id')
    def validate_server_id_optional(cls, v):
        if v:
            return validate_server_id(v)
        return v
    
    @model_validator(mode='after')
    def validate_name_or_server_id(self):
        """Ensure either name or server_id is provided."""
        if not self.server_id and not self.name:
            raise ValueError("Either 'name' (for new server) or 'server_id' (for existing server) must be provided")
        return self
    
    @validator('mode', 'transport')
    def validate_transport_mode(cls, v):
        if v:
            return validate_transport_type(v)
        return v
    
    @validator('description')
    def validate_description(cls, v):
        return validate_description(v) if v else v
    
    @validator('url')
    def validate_url_field(cls, v):
        if v:
            return validate_url(v)
        return v
    
    @validator('command')
    def validate_command_field(cls, v):
        if v:
            return validate_command(v)
        return v
    
    @validator('env')
    def validate_env(cls, v):
        return validate_environment_variables(v) if v else v
    
    @validator('headers')
    def validate_headers(cls, v):
        return validate_headers(v) if v else v
    
    @validator('args')
    def validate_args(cls, v):
        return validate_args(v) if v else v
    
    @validator('auth_type')
    def validate_auth_type(cls, v):
        return validate_auth_type(v) if v else v
    
    @validator('auto_connect', 'enabled')
    def validate_boolean_fields(cls, v):
        return validate_boolean_field(v, 'field') if v is not None else v

class VMCPAddServerRequest(VMCPBaseRequest):
    """Request model for adding a server to a vMCP.
    
    Supports two formats:
    1. Direct server config: { server_data: { name, mode, ... } }
    2. Wrapped format: { server_data: { mcp_server_config: { name, mode, ... } } }
    """
    
    server_data: Union[VMCPAddServerData, Dict[str, Any]] = Field(..., description="Server data or MCP server configuration")
    
    @validator('server_data', pre=True)
    def validate_and_normalize_server_data(cls, v):
        """Normalize server_data to handle wrapped mcp_server_config format and registry server objects."""
        if isinstance(v, dict):
            # Check if this is a registry server object (has id, mcp_server_config, etc.)
            # If mcp_server_config exists, we need to merge top-level fields with it
            if "mcp_server_config" in v:
                mcp_config = v.get("mcp_server_config", {})
                # Create normalized dict with top-level fields taking precedence
                normalized = {}
                
                # Start with mcp_server_config fields (if they're not null/empty)
                for key, value in mcp_config.items():
                    if value is not None and value != "":
                        normalized[key] = value
                
                # Override with top-level fields (these take precedence)
                # Map common fields from registry server format to our format
                if v.get("name"):
                    normalized["name"] = v["name"]
                if v.get("id") and not normalized.get("server_id"):
                    # If there's an id, treat it as server_id for existing servers
                    normalized["server_id"] = v["id"]
                if v.get("transport"):
                    normalized["mode"] = v["transport"]
                    normalized["transport"] = v["transport"]
                if v.get("description"):
                    normalized["description"] = v["description"]
                if v.get("url"):
                    normalized["url"] = v["url"]
                if v.get("favicon_url"):
                    normalized["favicon_url"] = v["favicon_url"]
                
                # Also check mcp_registry_config for additional fields
                if "mcp_registry_config" in v:
                    registry_config = v.get("mcp_registry_config", {})
                    if registry_config.get("name") and not normalized.get("name"):
                        normalized["name"] = registry_config["name"]
                    if registry_config.get("transport_type") and not normalized.get("mode"):
                        normalized["mode"] = registry_config["transport_type"]
                        normalized["transport"] = registry_config["transport_type"]
                    if registry_config.get("url") and not normalized.get("url"):
                        normalized["url"] = registry_config["url"]
                    if registry_config.get("description") and not normalized.get("description"):
                        normalized["description"] = registry_config["description"]
                
                # Map transport_type to mode/transport if present
                if "transport_type" in normalized and not normalized.get("mode"):
                    normalized["mode"] = normalized["transport_type"]
                
                return normalized if normalized else v
            # Otherwise return as-is for validation
            return v
        return v
    
    @validator('server_data')
    def validate_server_data_structure(cls, v):
        """Ensure server_data is properly structured."""
        if isinstance(v, VMCPAddServerData):
            return v
        elif isinstance(v, dict):
            # Validate that it has required fields
            if not v.get('server_id') and not v.get('name'):
                raise ValueError("server_data must contain either 'server_id' (for existing server) or 'name' (for new server)")
            # Try to parse as VMCPAddServerData
            try:
                return VMCPAddServerData(**v)
            except Exception as e:
                # If parsing fails, allow as dict for backward compatibility
                return v
        else:
            raise ValueError("server_data must be a dictionary or VMCPAddServerData instance")
    
    class Config:
        pass

class VMCPRemoveServerRequest(VMCPBaseRequest):
    """Request model for removing a server from a vMCP."""

    server_id: str = Field(..., description="Server ID to remove")

    @validator('server_id')
    def validate_server_id(cls, v):
        return validate_server_id(v)

    class Config:
        pass

class VMCPRefreshRequest(VMCPBaseRequest):
    """Request model for refreshing a vMCP configuration."""
    
    force_refresh: bool = Field(False, description="Force refresh even if recently refreshed")
    
    class Config:
        pass

class VMCPForkRequest(VMCPBaseRequest):
    """Request model for forking a vMCP."""
    
    name: Optional[str] = Field(None, description="Custom name for the forked vMCP (defaults to '{original_name} (Fork)')")
    description: Optional[str] = Field(None, description="Custom description for the forked vMCP")
    
    @validator('name')
    def validate_name(cls, v):
        if v is not None:
            return validate_server_name(v)
        return v
    
    @validator('description')
    def validate_description(cls, v):
        return validate_description(v)
    
    class Config:
        pass

class VMCPListToolsRequest(VMCPBaseRequest):
    """Request model for listing tools in a vMCP."""
    
    filter_by_server: Optional[str] = Field(default=None, description="Filter tools by server ID")
    search: Optional[str] = Field(default=None, description="Search tools by name or description")
    
    @model_validator(mode='before')
    @classmethod
    def handle_empty_dict(cls, data):
        """Handle empty dict input by returning empty dict for default values."""
        if isinstance(data, dict) and len(data) == 0:
            return {}
        return data
    
    class Config:
        pass

class VMCPListResourcesRequest(VMCPBaseRequest):
    """Request model for listing resources in a vMCP."""
    
    filter_by_server: Optional[str] = Field(default=None, description="Filter resources by server ID")
    uri_pattern: Optional[str] = Field(default=None, description="Filter resources by URI pattern")
    
    @model_validator(mode='before')
    @classmethod
    def handle_empty_dict(cls, data):
        """Handle empty dict input by returning empty dict for default values."""
        if isinstance(data, dict) and len(data) == 0:
            return {}
        return data
    
    class Config:
        pass

class VMCPListPromptsRequest(VMCPBaseRequest):
    """Request model for listing prompts in a vMCP."""
    
    filter_by_server: Optional[str] = Field(default=None, description="Filter prompts by server ID")
    search: Optional[str] = Field(default=None, description="Search prompts by name or description")
    
    @model_validator(mode='before')
    @classmethod
    def handle_empty_dict(cls, data):
        """Handle empty dict input by returning empty dict for default values."""
        if isinstance(data, dict) and len(data) == 0:
            return {}
        return data
    
    class Config:
        pass

# ============================================================================
# RESPONSE DATA MODELS
# ============================================================================

class VMCPDeleteData(BaseModel):
    """Data model for vMCP deletion response."""
    
    vmcp_id: str = Field(..., description="Deleted vMCP ID")
    vmcp_name: str = Field(..., description="Deleted vMCP name")

class VMCPCapabilitiesData(BaseModel):
    """Data model for vMCP capabilities response."""
    
    tools: List[ToolInfo] = Field(default_factory=list, description="Available tools")
    resources: List[ResourceInfo] = Field(default_factory=list, description="Available resources")
    prompts: List[PromptInfo] = Field(default_factory=list, description="Available prompts")
    total_tools: int = Field(0, description="Total number of tools")
    total_resources: int = Field(0, description="Total number of resources")
    total_prompts: int = Field(0, description="Total number of prompts")

class VMCPRefreshData(BaseModel):
    """Data model for vMCP refresh response."""
    
    vmcp_id: str = Field(..., description="Refreshed vMCP ID")
    servers_updated: Optional[int] = Field(None, description="Number of servers updated")
    capabilities_updated: bool = Field(False, description="Whether capabilities were updated")

class VMCPToolCallData(BaseModel):
    """Data model for vMCP tool call response."""
    
    vmcp_id: str = Field(..., description="vMCP ID")
    server: Optional[str] = Field(None, description="Server that executed the tool")
    tool: str = Field(..., description="Tool name that was called")
    result: Dict[str, Any] = Field(..., description="Tool execution result")

class VMCPToolListData(BaseModel):
    """Data model for vMCP tool list response."""
    
    vmcp_id: str = Field(..., description="vMCP ID")
    tools: List[ToolInfo] = Field(default_factory=list, description="List of available tools")
    total_tools: int = Field(0, description="Total number of tools")

class VMCPResourceReadData(BaseModel):
    """Data model for vMCP resource read response."""
    
    vmcp_id: str = Field(..., description="vMCP ID")
    server: Optional[str] = Field(None, description="Server that provided the resource")
    uri: str = Field(..., description="Resource URI")
    contents: List[Dict[str, Any]] = Field(..., description="Resource contents")

class VMCPResourceListData(BaseModel):
    """Data model for vMCP resource list response."""
    
    vmcp_id: str = Field(..., description="vMCP ID")
    resources: List[ResourceInfo] = Field(default_factory=list, description="List of available resources")
    total_resources: int = Field(0, description="Total number of resources")

class VMCPPromptGetData(BaseModel):
    """Data model for vMCP prompt get response."""
    
    vmcp_id: str = Field(..., description="vMCP ID")
    server: Optional[str] = Field(None, description="Server that provided the prompt")
    prompt: str = Field(..., description="Prompt name")
    prompt_id: str = Field(..., description="Prompt ID (with # prefix for custom prompts)")
    messages: List[Dict[str, Any]] = Field(..., description="Prompt messages")

class VMCPPromptListData(BaseModel):
    """Data model for vMCP prompt list response."""
    
    vmcp_id: str = Field(..., description="vMCP ID")
    prompts: List[PromptInfo] = Field(default_factory=list, description="List of available prompts")
    total_prompts: int = Field(0, description="Total number of prompts")

class VMCPEnvironmentVariablesData(BaseModel):
    """Data model for vMCP environment variables response."""
    
    vmcp_id: str = Field(..., description="vMCP ID")
    variables_count: int = Field(0, description="Number of environment variables")
    variables: List[EnvironmentVariable] = Field(default_factory=list, description="List of environment variables")

class VMCPShareData(BaseModel):
    """Data model for vMCP share response."""
    
    vmcp_id: str = Field(..., description="vMCP ID")
    state: VMCPShareState = Field(..., description="Sharing state")
    tags: List[str] = Field(default_factory=list, description="Public tags")
    public_url: Optional[str] = Field(None, description="Public URL if shared")

class PaginationInfo(BaseModel):
    """Model for pagination metadata."""
    
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Items per page")
    total: int = Field(..., description="Total number of items")
    pages: int = Field(..., description="Total number of pages")

class VMCPListSummary(BaseModel):
    """Summary model for vMCP list items (lightweight version of VMCPInfo)."""
    
    id: str = Field(..., description="vMCP ID")
    name: str = Field(..., description="vMCP name")
    description: Optional[str] = Field(None, description="vMCP description")
    status: Optional[str] = Field("active", description="vMCP status")
    user_id: Optional[str] = Field(None, description="User ID")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    total_tools: Optional[int] = Field(0, description="Total number of tools")
    total_resources: Optional[int] = Field(0, description="Total number of resources")
    total_prompts: Optional[int] = Field(0, description="Total number of prompts")

# ============================================================================
# VMCP RESPONSE MODELS
# ============================================================================

class VMCPInfo(VMCPConfigBase):
    """Response model for vMCP information."""
    
    total_tools: Optional[int] = Field(None, description="Total number of tools")
    total_resources: Optional[int] = Field(None, description="Total number of resources")
    total_resource_templates: Optional[int] = Field(None, description="Total number of resource templates")
    total_prompts: Optional[int] = Field(None, description="Total number of prompts")
    creator_id: Optional[str] = Field(None, description="Creator user ID")
    creator_username: Optional[str] = Field(None, description="Creator username")
    
    # Sharing fields
    is_public: bool = Field(False, description="Whether vMCP is public")
    public_tags: List[str] = Field(default_factory=list, description="Public tags")
    public_at: Optional[str] = Field(None, description="When vMCP was made public")
    is_wellknown: bool = Field(False, description="Whether vMCP is well-known")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata")
    
    class Config:
        pass

class VMCPCreateResponse(BaseModel):
    """Response model for vMCP creation matching original router structure."""
    
    success: bool = Field(True, description="Whether the operation was successful")
    vMCP: VMCPInfo = Field(..., description="Created vMCP information")
    
    class Config:
        pass

class VMCPUpdateResponse(BaseModel):
    """Response model for vMCP update matching original router structure."""
    
    success: bool = Field(True, description="Whether the operation was successful")
    vMCP: VMCPInfo = Field(..., description="Updated vMCP information")
    
    class Config:
        pass

class VMCPDeleteResponse(VMCPBaseResponse):
    """Response model for vMCP deletion."""
    
    data: VMCPDeleteData = Field(..., description="Deletion operation details")
    
    class Config:
        pass

class VMCPDetailsResponse(BaseModel):
    """Response model for vMCP details matching original router structure."""
    
    # Since the original router returns vmcp_config.to_dict(), we need to be flexible
    # We'll use a generic dict structure that can accommodate all fields
    id: str = Field(..., description="vMCP ID")
    name: str = Field(..., description="vMCP name")
    user_id: int = Field(..., description="User ID")
    description: Optional[str] = Field(None, description="vMCP description")
    system_prompt: Optional[SystemPrompt] = Field(None, description="System prompt")
    vmcp_config: VMCPConfigData = Field(default_factory=VMCPConfigData, description="vMCP configuration")
    custom_prompts: List[CustomPrompt] = Field(default_factory=list, description="Custom prompts")
    custom_tools: List[CustomTool] = Field(default_factory=list, description="Custom tools")
    custom_context: List[str] = Field(default_factory=list, description="Custom context")
    custom_resources: List[CustomResource] = Field(default_factory=list, description="Custom resources")
    custom_resource_templates: List[CustomResourceTemplate] = Field(default_factory=list, description="Custom resource templates")
    custom_widgets: List[CustomWidget] = Field(default_factory=list, description="Custom widgets")
    uploaded_files: List[UploadedFile] = Field(default_factory=list, description="Uploaded files")
    custom_resource_uris: List[str] = Field(default_factory=list, description="Custom resource URIs")
    total_tools: Optional[int] = Field(None, description="Total number of tools")
    total_resources: Optional[int] = Field(None, description="Total number of resources")
    total_resource_templates: Optional[int] = Field(None, description="Total number of resource templates")
    total_prompts: Optional[int] = Field(None, description="Total number of prompts")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    creator_id: Optional[int] = Field(None, description="Creator ID")
    creator_username: Optional[Union[str, int]] = Field(None, description="Creator username")
    is_public: bool = Field(False, description="Whether vMCP is public")
    public_tags: List[str] = Field(default_factory=list, description="Public tags")
    public_at: Optional[str] = Field(None, description="When vMCP was made public")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata")
    environment_variables: List[EnvironmentVariable] = Field(default_factory=list, description="Environment variables")
    
    class Config:
        pass

class VMCPListData(BaseModel):
    """Data structure for vMCP list response matching original router structure."""
    private: List[VMCPListSummary] = Field(..., description="List of private vMCPs")
    public: List[VMCPListSummary] = Field(default_factory=list, description="List of public vMCPs")

class VMCPListResponse(BaseModel):
    """Response model for vMCP list matching original router structure."""
    
    private: List[VMCPListSummary] = Field(..., description="List of private vMCPs")
    public: List[VMCPListSummary] = Field(default_factory=list, description="List of public vMCPs")
    
    class Config:
        pass

class VMCPCapabilitiesResponse(VMCPBaseResponse):
    """Response model for vMCP capabilities."""
    
    data: VMCPCapabilitiesData = Field(..., description="vMCP capabilities details")
    
    class Config:
        pass

class VMCPRefreshResponse(VMCPBaseResponse):
    """Response model for vMCP refresh operations."""
    
    data: VMCPRefreshData = Field(..., description="Refresh operation details")
    
    class Config:
        pass

class VMCPToolCallResponse(VMCPBaseResponse):
    """Response model for vMCP tool call execution and tool listing.
    
    Matches frontend expectations from:
    - callVMCPTool: Tool execution result (uses VMCPToolCallData)
    - listVMCPTools: List of available tools (uses VMCPToolListData)
    
    Note: The data field can be either VMCPToolCallData or VMCPToolListData
    depending on the operation type.
    """
    
    data: Union[VMCPToolCallData, VMCPToolListData] = Field(..., description="Tool operation details - either execution result or tools list")
    
    class Config:
        pass

class VMCPResourceResponse(VMCPBaseResponse):
    """Response model for vMCP resource read operations and resource listing.
    
    Matches frontend expectations from:
    - getVMCPResource: Resource read result (uses VMCPResourceReadData)
    - listVMCPResources: List of available resources (uses VMCPResourceListData)
    
    Note: The data field can be either VMCPResourceReadData or VMCPResourceListData
    depending on the operation type.
    """
    
    data: Union[VMCPResourceReadData, VMCPResourceListData] = Field(..., description="Resource operation details - either read contents or resources list")
    
    class Config:
        pass

class VMCPResourceTemplateResponse(VMCPBaseResponse):
    """Response model for vMCP resource template operations."""
    
    data: Dict[str, Any] = Field(..., description="Resource template operation details")
    
    class Config:
        pass

class VMCPPromptResponse(VMCPBaseResponse):
    """Response model for vMCP prompt operations and prompt listing.
    
    Matches frontend expectations from:
    - getVMCPPrompt: Prompt retrieval result (uses VMCPPromptGetData)
    - listVMCPPrompts: List of available prompts (uses VMCPPromptListData)
    
    Note: The data field can be either VMCPPromptGetData or VMCPPromptListData
    depending on the operation type.
    """
    
    data: Union[VMCPPromptGetData, VMCPPromptListData] = Field(..., description="Prompt operation details - either messages for prompt or prompts list")
    
    class Config:
        pass

class VMCPEnvironmentVariablesResponse(VMCPBaseResponse):
    """Response model for vMCP environment variables operations."""
    
    data: VMCPEnvironmentVariablesData = Field(..., description="Environment variables operation details")
    
    class Config:
        pass

class VMCPShareResponse(VMCPBaseResponse):
    """Response model for vMCP sharing operations."""
    
    data: VMCPShareData = Field(..., description="Sharing operation details")
    
    class Config:
        pass

class ServerStatusSummary(BaseModel):
    """Summary of server statuses after installation."""
    
    connected: int = Field(0, description="Number of connected servers")
    disconnected: int = Field(0, description="Number of disconnected servers")
    error: int = Field(0, description="Number of servers with errors")
    auth_required: int = Field(0, description="Number of servers requiring authentication")

class VMCPInstallResponse(VMCPBaseResponse):
    """Response model for vMCP installation operations.
    
    Matches frontend expectations from installVMCP response.
    Response includes installed vMCP data and server processing information.
    """
    
    data: VMCPInfo = Field(..., description="Installed vMCP information")
    servers_processed: Optional[int] = Field(None, description="Number of servers processed during installation")
    server_status_summary: Optional[ServerStatusSummary] = Field(None, description="Summary of server statuses after installation")
    
    class Config:
        pass

# ============================================================================
# STATS MODELS
# ============================================================================

class StatsFilterRequest(BaseModel):
    """Request model for filtering stats."""
    
    agent_name: Optional[str] = Field(None, description="Filter by agent name")
    vmcp_name: Optional[str] = Field(None, description="Filter by vMCP name")
    method: Optional[str] = Field(None, description="Filter by method name")
    search: Optional[str] = Field(None, description="Search across all fields")
    page: int = Field(1, description="Page number for pagination")
    limit: int = Field(50, description="Number of items per page")
    
    @validator('page')
    def validate_page(cls, v):
        if v < 1:
            raise ValueError("Page must be at least 1")
        return v
    
    @validator('limit')
    def validate_limit(cls, v):
        if v < 1 or v > 1000:
            raise ValueError("Limit must be between 1 and 1000")
        return v
    
    class Config:
        pass

class LogEntry(BaseModel):
    """Model for log entry."""
    
    timestamp: str = Field(..., description="Log timestamp")
    method: str = Field(..., description="Method name")
    agent_name: str = Field(..., description="Agent name")
    agent_id: str = Field(..., description="Agent ID")
    user_id: int = Field(..., description="User ID")
    client_id: str = Field(..., description="Client ID")
    operation_id: str = Field(..., description="Operation ID")
    mcp_server: Optional[str] = Field(None, description="MCP server name")
    mcp_method: Optional[str] = Field(None, description="MCP method name")
    original_name: Optional[str] = Field(None, description="Original name")
    arguments: Optional[Any] = Field(None, description="Method arguments")
    result: Optional[Any] = Field(None, description="Method result")
    vmcp_id: Optional[str] = Field(None, description="vMCP ID")
    vmcp_name: Optional[str] = Field(None, description="vMCP name")
    total_tools: Optional[int] = Field(None, description="Total tools count")
    total_resources: Optional[int] = Field(None, description="Total resources count")
    total_resource_templates: Optional[int] = Field(None, description="Total resource templates count")
    total_prompts: Optional[int] = Field(None, description="Total prompts count")
    
    class Config:
        pass

class StatsSummary(BaseModel):
    """Model for stats summary."""
    
    total_logs: int = Field(..., description="Total number of logs")
    total_agents: int = Field(..., description="Total number of agents")
    total_vmcps: int = Field(..., description="Total number of vMCPs")
    total_tool_calls: int = Field(..., description="Total number of tool calls")
    total_resource_calls: int = Field(..., description="Total number of resource calls")
    total_prompt_calls: int = Field(..., description="Total number of prompt calls")
    unique_methods: List[str] = Field(..., description="List of unique methods")
    agent_breakdown: Dict[str, int] = Field(..., description="Agent breakdown")
    vmcp_breakdown: Dict[str, int] = Field(..., description="vMCP breakdown")
    method_breakdown: Dict[str, int] = Field(..., description="Method breakdown")
    
    class Config:
        pass

class StatsResponse(BaseModel):
    """Response model for stats."""
    
    logs: List[LogEntry] = Field(..., description="List of log entries")
    pagination: PaginationInfo = Field(..., description="Pagination metadata")
    stats: StatsSummary = Field(..., description="Statistics summary")
    filter_options: Dict[str, List[str]] = Field(..., description="Available filter options")
    
    class Config:
        pass

# ============================================================================
# LEGACY COMPATIBILITY
# ============================================================================

# Keep the old dataclass for backward compatibility (will be deprecated)
from dataclasses import dataclass, field, asdict
from copy import deepcopy

@dataclass
class PublicVMCPInfo(BaseModel):
    """Public vMCP information for sharing."""
    
    creator_id: str = Field(..., description="Creator user ID")
    creator_username: str = Field(..., description="Creator username")
    install_count: int = Field(0, description="Number of installations")
    rating: Optional[float] = Field(None, description="Average rating")
    rating_count: int = Field(0, description="Number of ratings")
    
    class Config:
        pass

@dataclass
class VMCPRegistryConfig:
    """vMCP Registry configuration dataclass - DEPRECATED, use VMCPInfo instead."""
    
    id: str
    name: str
    user_id: str
    description: Optional[str] = None
    vmcp_config: Optional[Dict[str, Any]] = field(default_factory=dict)
    environment_variables: Optional[List[Dict[str, Any]]] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    creator_id: Optional[str] = None
    creator_username: Optional[str] = None
    total_tools: Optional[int] = None
    total_resources: Optional[int] = None
    total_resource_templates: Optional[int] = None
    total_prompts: Optional[int] = None
    public_info: Optional[PublicVMCPInfo] = None
    is_public: bool = False
    public_tags: List[str] = field(default_factory=list)
    public_at: Optional[str] = None
    is_wellknown: bool = False
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        if self.updated_at:
            data['updated_at'] = self.updated_at.isoformat()
        
        if self.public_info:
            data['public_info'] = asdict(self.public_info)
        
        if self.vmcp_config and 'selected_servers' in self.vmcp_config:
            selected_servers = self.vmcp_config['selected_servers']
            if isinstance(selected_servers, list):
                serialized_servers = []
                for server in selected_servers:
                    if hasattr(server, 'to_dict'):
                        serialized_servers.append(server.to_dict())
                    else:
                        serialized_servers.append(server)
                data['vmcp_config']['selected_servers'] = serialized_servers
        
        return data

@dataclass
class VMCPConfig:
    """vMCP configuration dataclass - DEPRECATED, use VMCPInfo instead."""
    
    id: str
    name: str
    user_id: str
    description: Optional[str] = None
    system_prompt: Optional[Dict[str, Any]] = None
    vmcp_config: Optional[Dict[str, Any]] = field(default_factory=dict)
    custom_prompts: List[Dict[str, Any]] = field(default_factory=list)
    custom_tools: List[Dict[str, Any]] = field(default_factory=list)
    custom_context: List[str] = field(default_factory=list)
    custom_resources: List[Dict[str, Any]] = field(default_factory=list)
    custom_resource_templates: List[Dict[str, Any]] = field(default_factory=list)
    custom_widgets: List[Dict[str, Any]] = field(default_factory=list)
    environment_variables: List[Dict[str, Any]] = field(default_factory=list)
    uploaded_files: List[Dict[str, Any]] = field(default_factory=list)
    custom_resource_uris: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    creator_id: Optional[str] = None
    creator_username: Optional[str] = None
    total_tools: Optional[int] = None
    total_resources: Optional[int] = None
    total_resource_templates: Optional[int] = None
    total_prompts: Optional[int] = None
    public_info: Optional[PublicVMCPInfo] = None
    is_public: bool = False
    public_tags: List[str] = field(default_factory=list)
    public_at: Optional[str] = None
    is_wellknown: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Set default timestamps if not provided."""
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VMCPConfig':
        """Create VMCPConfig from dictionary."""
        processed_data = data.copy()
        
        if 'created_at' in processed_data and isinstance(processed_data['created_at'], str):
            try:
                processed_data['created_at'] = datetime.fromisoformat(processed_data['created_at'].replace('Z', '+00:00'))
            except (ValueError, TypeError):
                processed_data['created_at'] = None
        
        if 'updated_at' in processed_data and isinstance(processed_data['updated_at'], str):
            try:
                processed_data['updated_at'] = datetime.fromisoformat(processed_data['updated_at'].replace('Z', '+00:00'))
            except (ValueError, TypeError):
                processed_data['updated_at'] = None
        
        # Handle fields that should be nested in vmcp_config but might be at top level
        # This can happen when loading from database JSON that was stored incorrectly
        vmcp_config_fields = ['selected_servers', 'selected_tools', 'selected_prompts', 'selected_resources']
        
        # Ensure vmcp_config exists
        if 'vmcp_config' not in processed_data:
            processed_data['vmcp_config'] = {}
        elif not isinstance(processed_data['vmcp_config'], dict):
            processed_data['vmcp_config'] = {}
        
        # Move any top-level fields that should be in vmcp_config
        for field in vmcp_config_fields:
            if field in processed_data and field not in processed_data['vmcp_config']:
                processed_data['vmcp_config'][field] = processed_data.pop(field)
        
        # Remove any fields that don't belong to VMCPConfig dataclass
        valid_fields = {
            'id', 'name', 'user_id', 'description', 'system_prompt', 'vmcp_config',
            'custom_prompts', 'custom_tools', 'custom_context', 'custom_resources',
            'custom_resource_templates', 'custom_widgets', 'environment_variables',
            'uploaded_files', 'custom_resource_uris', 'created_at', 'updated_at',
            'creator_id', 'creator_username', 'total_tools', 'total_resources',
            'total_resource_templates', 'total_prompts', 'public_info', 'is_public',
            'public_tags', 'public_at', 'is_wellknown', 'metadata'
        }
        
        # Only keep valid fields
        filtered_data = {k: v for k, v in processed_data.items() if k in valid_fields}
        
        return cls(**filtered_data)
    
    def to_dict(self, include_environment_variables: bool = True) -> Dict[str, Any]:
        """Convert VMCPConfig to dictionary for JSON serialization."""
        vmcp_dict = {
            "id": self.id,
            "name": self.name,
            "user_id": self.user_id,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "vmcp_config": self.vmcp_config,
            "custom_prompts": self.custom_prompts,
            "custom_tools": self.custom_tools,
            "custom_context": self.custom_context,
            "custom_resources": self.custom_resources,
            "custom_resource_templates": self.custom_resource_templates,
            "custom_widgets": self.custom_widgets,
            "uploaded_files": self.uploaded_files,
            "custom_resource_uris": self.custom_resource_uris,
            "total_tools": self.total_tools,
            "total_resources": self.total_resources,
            "total_resource_templates": self.total_resource_templates,
            "total_prompts": self.total_prompts,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "creator_id": self.creator_id,
            "creator_username": self.creator_username,
            "is_public": self.is_public,
            "public_tags": self.public_tags,
            "public_at": self.public_at,
            "metadata": self.metadata
        }
        
        if include_environment_variables:
            vmcp_dict["environment_variables"] = self.environment_variables
        
        return vmcp_dict
    
    def to_vmcp_registry_config(self) -> VMCPRegistryConfig:
        """Convert to VMCPRegistryConfig for registry operations."""
        registry_vmcp_config = deepcopy(self.vmcp_config) if self.vmcp_config else {}
        
        if 'selected_servers' in registry_vmcp_config:
            from vmcp.mcps.models import MCPRegistryConfig
            selected_servers = registry_vmcp_config['selected_servers']
            if isinstance(selected_servers, list):
                registry_servers = []
                for server in selected_servers:
                    if isinstance(server, dict):
                        from vmcp.mcps.models import MCPServerConfig
                        loaded_server = MCPServerConfig.from_dict(server)
                        registry_servers.append(loaded_server.to_mcp_registry_config())
                    else:
                        registry_servers.append(server)
                registry_vmcp_config['selected_servers'] = registry_servers
        
        return VMCPRegistryConfig(
            id=self.id,
            name=self.name,
            user_id=self.user_id,
            description=self.description,
            vmcp_config=registry_vmcp_config,
            environment_variables=self.environment_variables,
            created_at=self.created_at,
            updated_at=self.updated_at,
            creator_id=self.creator_id,
            creator_username=self.creator_username,
            total_tools=self.total_tools,
            total_resources=self.total_resources,
            total_resource_templates=self.total_resource_templates,
            total_prompts=self.total_prompts,
            public_info=self.public_info,
            is_public=self.is_public,
            public_tags=self.public_tags,
            public_at=self.public_at,
            is_wellknown=self.is_wellknown,
            metadata=self.metadata,
        )

class VMCPAddServerResponse(BaseModel):
    """Response model for adding server to vMCP matching original router structure."""
    
    success: bool = Field(True, description="Whether the operation was successful")
    message: str = Field(..., description="Success message")
    vmcp_config: VMCPInfo = Field(..., description="Updated vMCP configuration")
    server: Dict[str, Any] = Field(..., description="Added server information (dict representation of server config)")
    
    class Config:
        pass

class VMCPRemoveServerResponse(BaseModel):
    """Response model for removing server from vMCP matching original router structure."""
    
    success: bool = Field(True, description="Whether the operation was successful")
    message: str = Field(..., description="Success message")
    vmcp_config: VMCPInfo = Field(..., description="Updated vMCP configuration")
    server: Optional[Dict[str, Any]] = Field(None, description="Removed server information (dict representation of server config)")
    
    class Config:
        pass
