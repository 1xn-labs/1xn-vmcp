"""
MCP-specific content models for type safety.

This module contains Pydantic models for MCP-specific data structures
that extend the core MCP SDK types from mcp.types to add server tracking
and additional metadata while maintaining full compatibility with the MCP protocol.

Inheritance Structure:
- MCPToolInfo extends mcp.types.Tool (adds server/server_id tracking)
- MCPResourceInfo extends mcp.types.Resource (adds server/server_id tracking)
- MCPPromptInfo extends mcp.types.Prompt (adds server/server_id tracking)
- MCPToolCallResult extends mcp.types.CallToolResult (adds server tracking)
- MCPPromptResult extends mcp.types.GetPromptResult (adds server tracking)
- MCPResourceContent wraps mcp.types.ReadResourceResult (adds server tracking)

All models maintain backward compatibility and can be used interchangeably
with their base MCP SDK types where server tracking is not needed.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, List, Any, Union
from datetime import datetime

# Import core MCP SDK types
from mcp.types import (
    Tool,
    Resource,
    ResourceTemplate,
    Prompt,
    PromptArgument,
    CallToolResult,
    GetPromptResult,
    ReadResourceResult,
    TextResourceContents,
    BlobResourceContents,
    ServerCapabilities,
)

# ============================================================================
# MCP CAPABILITIES MODELS
# ============================================================================

class MCPCapabilities(BaseModel):
    """MCP server capabilities information with extended metadata."""
    
    model_config = ConfigDict(extra="allow")
    
    tools: bool = Field(False, description="Whether server supports tools")
    resources: bool = Field(False, description="Whether server supports resources")
    prompts: bool = Field(False, description="Whether server supports prompts")
    tools_count: Optional[int] = Field(None, description="Number of available tools")
    resources_count: Optional[int] = Field(None, description="Number of available resources")
    prompts_count: Optional[int] = Field(None, description="Number of available prompts")
    logging: Optional[bool] = Field(None, description="Whether server supports logging")
    experimental: Optional[Dict[str, Any]] = Field(None, description="Experimental capabilities")
    
    @classmethod
    def from_server_capabilities(cls, capabilities: ServerCapabilities) -> "MCPCapabilities":
        """Create MCPCapabilities from MCP SDK ServerCapabilities."""
        return cls(
            tools=capabilities.tools is not None,
            resources=capabilities.resources is not None,
            prompts=capabilities.prompts is not None,
            logging=capabilities.logging is not None,
            experimental=capabilities.experimental,
        )

# ============================================================================
# MCP TOOL MODELS
# ============================================================================

# Backward compatibility: Export PromptArgument as MCPToolArgument and MCPPromptArgument
# Note: These are aliases - use PromptArgument from mcp.types for new code
MCPToolArgument = PromptArgument
MCPPromptArgument = PromptArgument

class MCPToolInfo(Tool):
    """MCP tool information extending the core MCP SDK Tool type.
    
    Adds server tracking fields while maintaining full compatibility with Tool.
    """
    
    model_config = ConfigDict(extra="allow")
    
    server: Optional[str] = Field(None, description="Server that provides this tool")
    server_id: Optional[str] = Field(None, description="Server ID")
    
    @classmethod
    def from_tool(cls, tool: Tool, server: Optional[str] = None, server_id: Optional[str] = None) -> "MCPToolInfo":
        """Create MCPToolInfo from MCP SDK Tool."""
        tool_dict = tool.model_dump()
        tool_dict["server"] = server
        tool_dict["server_id"] = server_id
        return cls(**tool_dict)

class MCPToolCallResult(CallToolResult):
    """MCP tool call execution result extending the core MCP SDK CallToolResult.
    
    Adds server tracking and execution metadata while maintaining compatibility.
    """
    
    model_config = ConfigDict(extra="allow")
    
    tool_name: Optional[str] = Field(None, description="Name of the tool that was called")
    server: Optional[str] = Field(None, description="Server that executed the tool")
    server_id: Optional[str] = Field(None, description="Server ID")
    execution_time: Optional[float] = Field(None, description="Execution time in seconds")
    
    @classmethod
    def from_call_tool_result(
        cls, 
        result: CallToolResult, 
        tool_name: Optional[str] = None,
        server: Optional[str] = None, 
        server_id: Optional[str] = None
    ) -> "MCPToolCallResult":
        """Create MCPToolCallResult from MCP SDK CallToolResult."""
        result_dict = result.model_dump()
        result_dict["tool_name"] = tool_name
        result_dict["server"] = server
        result_dict["server_id"] = server_id
        return cls(**result_dict)

# ============================================================================
# MCP RESOURCE MODELS
# ============================================================================

class MCPResourceInfo(Resource):
    """MCP resource information extending the core MCP SDK Resource type.
    
    Adds server tracking fields while maintaining full compatibility with Resource.
    """
    
    model_config = ConfigDict(extra="allow")
    
    server: Optional[str] = Field(None, description="Server that provides this resource")
    server_id: Optional[str] = Field(None, description="Server ID")
    
    @classmethod
    def from_resource(cls, resource: Resource, server: Optional[str] = None, server_id: Optional[str] = None) -> "MCPResourceInfo":
        """Create MCPResourceInfo from MCP SDK Resource."""
        resource_dict = resource.model_dump()
        resource_dict["server"] = server
        resource_dict["server_id"] = server_id
        return cls(**resource_dict)

class MCPResourceContent(BaseModel):
    """MCP resource content with server tracking.
    
    Wraps ReadResourceResult from MCP SDK to add server metadata.
    """
    
    model_config = ConfigDict(extra="allow")
    
    uri: str = Field(..., description="Resource URI")
    server: Optional[str] = Field(None, description="Server that provided the resource")
    server_id: Optional[str] = Field(None, description="Server ID")
    contents: List[Union[TextResourceContents, BlobResourceContents]] = Field(..., description="Resource content")
    mimeType: Optional[str] = Field(None, description="MIME type of the content")
    size: Optional[int] = Field(None, description="Content size in bytes")
    
    @classmethod
    def from_read_resource_result(
        cls,
        result: ReadResourceResult,
        uri: str,
        server: Optional[str] = None,
        server_id: Optional[str] = None
    ) -> "MCPResourceContent":
        """Create MCPResourceContent from MCP SDK ReadResourceResult."""
        # Extract mimeType and size from first content item if available
        mime_type = None
        size = None
        if result.contents:
            first_content = result.contents[0]
            mime_type = getattr(first_content, 'mimeType', None)
        
        return cls(
            uri=uri,
            server=server,
            server_id=server_id,
            contents=result.contents,
            mimeType=mime_type,
            size=size
        )

# ============================================================================
# MCP PROMPT MODELS
# ============================================================================

# Note: MCPPromptArgument removed - use PromptArgument from mcp.types directly
# The MCP SDK PromptArgument already has name, description, required fields

class MCPPromptInfo(Prompt):
    """MCP prompt information extending the core MCP SDK Prompt type.
    
    Adds server tracking fields while maintaining full compatibility with Prompt.
    """
    
    model_config = ConfigDict(extra="allow")
    
    server: Optional[str] = Field(None, description="Server that provides this prompt")
    server_id: Optional[str] = Field(None, description="Server ID")
    
    @classmethod
    def from_prompt(cls, prompt: Prompt, server: Optional[str] = None, server_id: Optional[str] = None) -> "MCPPromptInfo":
        """Create MCPPromptInfo from MCP SDK Prompt."""
        prompt_dict = prompt.model_dump()
        prompt_dict["server"] = server
        prompt_dict["server_id"] = server_id
        return cls(**prompt_dict)

class MCPPromptResult(GetPromptResult):
    """MCP prompt execution result extending the core MCP SDK GetPromptResult.
    
    Adds server tracking and error handling while maintaining compatibility.
    """
    
    model_config = ConfigDict(extra="allow")
    
    prompt_name: Optional[str] = Field(None, description="Name of the prompt that was executed")
    server: Optional[str] = Field(None, description="Server that executed the prompt")
    server_id: Optional[str] = Field(None, description="Server ID")
    error: Optional[str] = Field(None, description="Error message if execution failed")
    
    @classmethod
    def from_get_prompt_result(
        cls,
        result: GetPromptResult,
        prompt_name: Optional[str] = None,
        server: Optional[str] = None,
        server_id: Optional[str] = None
    ) -> "MCPPromptResult":
        """Create MCPPromptResult from MCP SDK GetPromptResult."""
        result_dict = result.model_dump()
        result_dict["prompt_name"] = prompt_name
        result_dict["server"] = server
        result_dict["server_id"] = server_id
        return cls(**result_dict)

# ============================================================================
# MCP SERVER STATUS MODELS
# ============================================================================

class MCPServerStatus(BaseModel):
    """MCP server status information."""
    
    model_config = ConfigDict(extra="allow")
    
    server_id: str = Field(..., description="Server ID")
    name: str = Field(..., description="Server name")
    status: str = Field(..., description="Connection status")
    last_updated: Optional[datetime] = Field(None, description="Last status update")
    last_connected: Optional[datetime] = Field(None, description="Last connection time")
    last_error: Optional[str] = Field(None, description="Last error message")
    requires_auth: bool = Field(False, description="Whether server requires authentication")

class MCPConnectionInfo(BaseModel):
    """MCP connection operation details."""
    
    model_config = ConfigDict(extra="allow")
    
    server_id: str = Field(..., description="Server ID")
    server_name: str = Field(..., description="Server name")
    status: str = Field(..., description="Connection status")
    requires_auth: bool = Field(False, description="Whether server requires authentication")
    auth_url: Optional[str] = Field(None, description="Authentication URL if required")
    error: Optional[str] = Field(None, description="Error message if connection failed")

class MCPPingInfo(BaseModel):
    """MCP ping operation details."""
    
    model_config = ConfigDict(extra="allow")
    
    server: str = Field(..., description="Server name or ID")
    server_id: Optional[str] = Field(None, description="Server ID")
    alive: bool = Field(..., description="Whether server is alive")
    timestamp: datetime = Field(..., description="Ping timestamp")
    response_time: Optional[float] = Field(None, description="Response time in milliseconds")
    error: Optional[str] = Field(None, description="Error message if ping failed")

# ============================================================================
# MCP STATISTICS MODELS
# ============================================================================

class MCPServerStats(BaseModel):
    """MCP server statistics."""
    
    model_config = ConfigDict(extra="allow")
    
    total: int = Field(0, description="Total number of servers")
    connected: int = Field(0, description="Number of connected servers")
    disconnected: int = Field(0, description="Number of disconnected servers")
    auth_required: int = Field(0, description="Number of servers requiring authentication")
    errors: int = Field(0, description="Number of servers with errors")

class MCPCapabilitiesStats(BaseModel):
    """MCP capabilities statistics."""
    
    model_config = ConfigDict(extra="allow")
    
    tools: int = Field(0, description="Total number of tools")
    resources: int = Field(0, description="Total number of resources")
    prompts: int = Field(0, description="Total number of prompts")

class MCPSystemStats(BaseModel):
    """MCP system statistics."""
    
    model_config = ConfigDict(extra="allow")
    
    servers: MCPServerStats = Field(..., description="Server statistics")
    capabilities: MCPCapabilitiesStats = Field(..., description="Capabilities statistics")

# ============================================================================
# MCP REGISTRY MODELS
# ============================================================================

class MCPRegistryConfig(BaseModel):
    """MCP registry configuration."""
    
    model_config = ConfigDict(extra="allow")
    
    name: Optional[str] = Field(None, description="Server name")
    transport_type: Optional[str] = Field(None, description="Transport type")
    description: Optional[str] = Field(None, description="Server description")
    url: Optional[str] = Field(None, description="Server URL")
    command: Optional[str] = Field(None, description="Command for stdio servers")
    args: Optional[List[str]] = Field(None, description="Command arguments")
    env: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    headers: Optional[Dict[str, str]] = Field(None, description="HTTP headers")

class MCPServerConfig(BaseModel):
    """MCP server configuration."""
    
    model_config = ConfigDict(extra="allow")
    
    name: Optional[str] = Field(None, description="Server name")
    transport_type: Optional[str] = Field(None, description="Transport type")
    description: Optional[str] = Field(None, description="Server description")
    url: Optional[str] = Field(None, description="Server URL")
    command: Optional[str] = Field(None, description="Command for stdio servers")
    args: Optional[List[str]] = Field(None, description="Command arguments")
    env: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    headers: Optional[Dict[str, str]] = Field(None, description="HTTP headers")
    auth: Optional[Dict[str, Any]] = Field(None, description="Authentication configuration")

class MCPRegistryStats(BaseModel):
    """MCP registry statistics."""
    
    model_config = ConfigDict(extra="allow")
    
    downloads: Optional[int] = Field(None, description="Number of downloads")
    rating: Optional[float] = Field(None, description="Server rating")
    last_updated: Optional[datetime] = Field(None, description="Last update time")
    version: Optional[str] = Field(None, description="Server version")

# ============================================================================
# MCP DISCOVERY MODELS
# ============================================================================

class MCPDiscoveredTool(MCPToolInfo):
    """Discovered MCP tool extending MCPToolInfo.
    
    Adds original_name tracking for prefixed tool names.
    """
    
    model_config = ConfigDict(extra="allow")
    
    original_name: str = Field(..., description="Original tool name (before prefix)")
    
    @classmethod
    def from_tool_with_prefix(
        cls,
        tool: Tool,
        server: str,
        server_id: str,
        prefixed_name: str,
        original_name: str
    ) -> "MCPDiscoveredTool":
        """Create MCPDiscoveredTool from MCP SDK Tool with prefix information."""
        tool_dict = tool.model_dump()
        tool_dict["name"] = prefixed_name
        tool_dict["original_name"] = original_name
        tool_dict["server"] = server
        tool_dict["server_id"] = server_id
        return cls(**tool_dict)

class MCPToolsDiscovery(BaseModel):
    """MCP tools discovery result."""
    
    model_config = ConfigDict(extra="allow")
    
    tools: List[MCPDiscoveredTool] = Field(..., description="List of discovered tools")
    total_tools: int = Field(..., description="Total number of tools")
    connected_servers: int = Field(..., description="Number of connected servers")
    server_details: Optional[Dict[str, Any]] = Field(None, description="Server details")
