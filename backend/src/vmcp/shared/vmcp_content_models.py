"""
Shared, type-safe content models used by vMCP and MCP routers.

These models purposefully allow extra fields to preserve backward compatibility
with existing stored payloads and to avoid changing any business logic. They add
shape and validation where we know the structure, while remaining permissive.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class _PermissiveBaseModel(BaseModel):
    class Config:
        extra = "allow"


class EnvironmentVariable(_PermissiveBaseModel):
    name: str = Field(..., description="Environment variable name")
    value: Any = Field(..., description="Environment variable value")
    description: Optional[str] = Field(None, description="Optional description")


class PromptVariable(_PermissiveBaseModel):
    name: Optional[str] = Field(None, description="Variable name")
    description: Optional[str] = Field(None, description="Variable description")
    required: Optional[bool] = Field(False, description="Whether the variable is required")


class ToolCall(_PermissiveBaseModel):
    name: Optional[str] = Field(None, description="Tool name to call")
    arguments: Optional[Dict[str, Any]] = Field(None, description="Tool arguments")


class SystemPrompt(_PermissiveBaseModel):
    text: str = Field(..., description="System prompt text")
    variables: List[PromptVariable] = Field(default_factory=list, description="Prompt variables")
    environment_variables: Optional[List[EnvironmentVariable]] = Field(default_factory=list, description="Env vars for prompt")
    tool_calls: Optional[List[ToolCall]] = Field(default_factory=list, description="Tool calls in prompt")


class CustomPrompt(_PermissiveBaseModel):
    name: Optional[str] = Field(None, description="Prompt name")
    text: Optional[str] = Field(None, description="Prompt body text/template")
    variables: List[PromptVariable] = Field(default_factory=list, description="Variables used by prompt")


class CustomTool(_PermissiveBaseModel):
    tool_type: Optional[str] = Field("prompt", description="Tool type: prompt|http|python")
    name: Optional[str] = Field(None, description="Tool name")
    description: Optional[str] = Field(None, description="Tool description")
    variables: Optional[List[PromptVariable]] = Field(default=None, description="Inputs this tool expects")


class CustomResource(_PermissiveBaseModel):
    name: Optional[str] = Field(None, description="Resource name")
    uri: Optional[str] = Field(None, description="Resource URI")
    description: Optional[str] = Field(None, description="Resource description")


class CustomResourceTemplate(_PermissiveBaseModel):
    name: Optional[str] = Field(None, description="Template name")
    uriTemplate: Optional[str] = Field(None, description="URI template")
    description: Optional[str] = Field(None, description="Template description")


class CustomWidget(_PermissiveBaseModel):
    widget_id: Optional[str] = Field(None, description="Widget identifier")
    name: Optional[str] = Field(None, description="Widget name")


class UploadedFile(_PermissiveBaseModel):
    name: Optional[str] = Field(None, description="Uploaded file name")
    path: Optional[str] = Field(None, description="Uploaded file path")
    mimeType: Optional[str] = Field(None, description="MIME type")


class SelectedItems(_PermissiveBaseModel):
    selected_servers: List[Dict[str, Any]] = Field(default_factory=list, description="Selected servers with details")
    selected_tools: Dict[str, List[str]] = Field(default_factory=dict, description="server_id -> tool names")
    selected_prompts: Dict[str, List[str]] = Field(default_factory=dict, description="server_id -> prompt names")
    selected_resources: Dict[str, List[str]] = Field(default_factory=dict, description="server_id -> resource URIs")


class VMCPConfigData(_PermissiveBaseModel):
    """Container for the vmcp_config field with selected items and any extra config."""
    selected_servers: List[Dict[str, Any]] = Field(default_factory=list)
    selected_tools: Dict[str, List[str]] = Field(default_factory=dict)
    selected_prompts: Dict[str, List[str]] = Field(default_factory=dict)
    selected_resources: Dict[str, List[str]] = Field(default_factory=dict)


