"""
vMCP SDK - Lightweight Python SDK for Virtual MCP Servers

This SDK provides a simple, Pythonic interface to interact with vMCPs.
It automatically detects the vMCP from the sandbox config file.

Example:
    >>> import vmcp_sdk
    >>>
    >>> # SDK automatically uses the vMCP for the current sandbox
    >>> tools = vmcp_sdk.list_tools()
    >>> prompts = vmcp_sdk.list_prompts()
    >>> result = vmcp_sdk.some_tool_function(arg1="value")  # Typed function!
"""

from .active_vmcp import ActiveVMCPManager
from .client import VMCPClient, SdkCallToolResult



# Expose main functions and classes
__all__ = ["VMCPClient", "ActiveVMCPManager", "SdkCallToolResult"]
