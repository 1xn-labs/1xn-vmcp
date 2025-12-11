"""
Custom exceptions for vMCP SDK.

This module defines all custom exceptions used throughout the vMCP SDK,
providing clear error types for different failure scenarios.
"""

from typing import Any, Optional


class VMCPError(Exception):
    """Base exception for all VMCP SDK errors."""
    pass


class VMCPNotFoundError(VMCPError):
    """
    Raised when vMCP ID cannot be found or detected.

    This typically occurs when:
    - No .vmcp-config.json file exists in the sandbox directory
    - The vmcp_id is not provided and cannot be auto-detected
    - The sandbox path is invalid or inaccessible
    """
    pass


class VMCPToolNotFoundError(VMCPError):
    """
    Raised when a requested tool does not exist in the vMCP.

    This occurs when trying to access a tool that:
    - Doesn't exist in the vMCP configuration
    - Hasn't been discovered yet (progressive discovery)
    - Has an incorrect or misspelled name
    """

    def __init__(self, tool_name: str, available_tools: Optional[list] = None):
        """
        Initialize the exception.

        Args:
            tool_name: Name of the tool that was not found
            available_tools: Optional list of available tool names for suggestions
        """
        self.tool_name = tool_name
        self.available_tools = available_tools or []

        message = f"Tool '{tool_name}' not found"
        if self.available_tools:
            suggestions = ", ".join(self.available_tools[:5])
            message += f". Available tools: {suggestions}..."

        super().__init__(message)


class VMCPToolExecutionError(VMCPError):
    """
    Raised when a tool execution fails.

    This occurs when:
    - The MCP server returns an error
    - Tool execution times out
    - Invalid arguments are provided to the tool
    - The tool encounters an internal error
    """

    def __init__(self, tool_name: str, message: str, result: Optional[Any] = None):
        """
        Initialize the exception.

        Args:
            tool_name: Name of the tool that failed
            message: Error message describing the failure
            result: Optional SdkCallToolResult object containing error details
        """
        self.tool_name = tool_name
        self.result = result
        self.error_message = message

        full_message = f"Tool '{tool_name}' execution failed: {message}"
        super().__init__(full_message)


class VMCPConnectionError(VMCPError):
    """
    Raised when unable to connect to the vMCP or underlying MCP servers.

    This occurs when:
    - MCP server is unreachable
    - Network connectivity issues
    - Server authentication fails
    - Connection timeout
    """
    pass


class VMCPConfigurationError(VMCPError):
    """
    Raised when vMCP configuration is invalid or incomplete.

    This occurs when:
    - .vmcp-config.json is malformed
    - Required configuration fields are missing
    - Configuration values are invalid
    """
    pass
