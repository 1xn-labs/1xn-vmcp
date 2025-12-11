"""
vMCP SDK - Async Python Client for Virtual MCP Servers.

This is an async-only SDK. All methods must be awaited.

This is a thin wrapper around the existing VMCPConfigManager that creates
typed Python functions from tool schemas.

Basic Usage:
    >>> import asyncio
    >>> from vmcp_sdk import VMCPClient
    >>>
    >>> def main():
    >>>     # Auto-detect from sandbox
    >>>     client = VMCPClient()
    >>>
    >>>     # List available tools
    >>>     tools = asyncio.run(client.list_tools())
    >>>
    >>>     # Call a tool
    >>>     result = asyncio.run(client.some_tool(param="value"))
    >>>     print(result.value)

Advanced Usage:
    >>> import asyncio
    >>> from vmcp_sdk import VMCPClient
    >>>
    >>> def main():
    >>>     # Explicit vMCP
    >>>     client = VMCPClient(vmcp_id="my-vmcp-id")
    >>>
    >>>     # Error handling
    >>>     async def run():
    >>>         try:
    >>>             result = await client.some_tool(arg="test")
    >>>             if result.is_success():
    >>>                 print(result.value)
    >>>         except VMCPToolExecutionError as e:
    >>>             print(f"Tool failed: {e}")
    >>>
    >>>     asyncio.run(run())
    >>>
    >>>     # Context manager (recommended)
    >>>     async def run_with_context():
    >>>         async with VMCPClient() as client:
    >>>             tools = await client.list_tools()
    >>>             result = await client.some_tool(arg="value")
    >>>
    >>>     asyncio.run(run_with_context())
"""

import asyncio
import json
import logging
from difflib import get_close_matches
from typing import Any, Callable, Dict, List, Optional

from vmcp.storage.dummy_user import UserContext
from vmcp.vmcps.vmcp_config_manager.config_core import VMCPConfigManager
from vmcp.vmcps.models import VMCPToolCallRequest
from mcp.types import CallToolResult, TextContent

from .schema import create_function_with_signature, normalize_name
from .exceptions import (
    VMCPNotFoundError,
    VMCPToolNotFoundError,
    VMCPToolExecutionError,
)

# Module logger
logger = logging.getLogger('vmcp_sdk')

class SdkCallToolResult(CallToolResult):
    """
    SDK response to a tool call.

    Attributes:
        content: List of text/content items from the tool
        structuredContent: Structured output data (if outputSchema available)
        isError: Boolean indicating if there was an error
        result: Extracted result data (dict, list, or None)
    """
    result: dict[str, Any] | list[str] | None = None

    @property
    def value(self) -> Any:
        """
        Convenient accessor for result data.

        Returns:
            The result data, same as .result
        """
        return self.result

    def is_success(self) -> bool:
        """
        Check if tool call succeeded.

        Returns:
            True if no error occurred, False otherwise
        """
        return not self.isError

    def raise_for_error(self) -> 'SdkCallToolResult':
        """
        Raise exception if error occurred.

        Returns:
            Self for method chaining

        Raises:
            VMCPToolExecutionError: If the tool execution failed
        """
        if self.isError:
            error_msg = "Unknown error"
            if self.content:
                first_content = self.content[0]
                if isinstance(first_content, TextContent):
                    error_msg = first_content.text
                else:
                    error_msg = str(first_content)
            raise VMCPToolExecutionError(
                tool_name="unknown",
                message=error_msg,
                result=self
            )
        return self

    def __repr__(self) -> str:
        """Better debugging representation."""
        return f"<SdkCallToolResult isError={self.isError} result={self.result}>"


class VMCPClient:
    """
    Client for interacting with vMCPs.
    
    This is a thin wrapper around VMCPConfigManager that provides
    typed Python functions for each tool.
    """
    
    def __init__(self, vmcp_id: Optional[str] = None, user_id: str = "1"):
        """
        Initialize the vMCP client.
        
        Args:
            vmcp_id: ID of the vMCP to connect to. If None, auto-detects from sandbox config.
            user_id: User ID for database access (default: 1 for OSS)
        """
        self.user_id = user_id
        self.user_context = UserContext(user_id=user_id)
        
        # Auto-detect vmcp_id from sandbox config if not provided
        if vmcp_id is None:
            vmcp_id = self._detect_vmcp_id_from_sandbox()
        
        self.vmcp_id = vmcp_id

        if not self.vmcp_id:
            raise VMCPNotFoundError(
                "No vMCP ID found. Ensure you're running in a sandbox directory "
                "with .vmcp-config.json file, or provide vmcp_id parameter."
            )
        
        # Initialize manager
        self.manager = VMCPConfigManager(
            user_id=str(user_id),
            vmcp_id=self.vmcp_id,
            logging_config={
                "agent_name": "vmcp_sdk",
                "agent_id": "vmcp_sdk",
                "client_id": "vmcp_sdk"
            }
        )

        self._vmcpconfig = self.manager.load_vmcp_config()
        
        # Cache for tools and typed functions
        self._tools_cache: Optional[List[Dict[str, Any]]] = None
        self._typed_functions: Dict[str, Any] = {}
        self._tools_loaded = False
    
    def _detect_vmcp_id_from_sandbox(self) -> Optional[str]:
        """Detect vmcp_id from sandbox config file."""
        from .active_vmcp import ActiveVMCPManager
        manager = ActiveVMCPManager()
        return manager.get_active_vmcp_id()
    
    
    async def _load_tools(self) -> None:
        """Load tools and create typed functions."""
        if self._tools_loaded:
            return

        if not self.vmcp_id:
            raise VMCPNotFoundError("No vMCP specified")
        
        tools = await self.manager.tools_list(bypass_pd_filter=True)
        
        # Convert Tool objects to dicts
        self._tools_cache = []
        for tool in tools:
            if hasattr(tool, 'model_dump'):
                tool_dict = tool.model_dump()
            elif isinstance(tool, dict):
                tool_dict = tool
            else:
                # Fallback: convert to dict manually
                tool_dict = {
                    "name": getattr(tool, 'name', str(tool)),
                    "description": getattr(tool, 'description', ''),
                    "inputSchema": getattr(tool, 'inputSchema', {})
                }
            self._tools_cache.append(tool_dict)
        
        # Create typed functions for each tool
        for tool_dict in self._tools_cache:
            tool_name = tool_dict.get("name", "")
            if not tool_name:
                continue

            # Normalize name for Python attribute access
            normalized_name = normalize_name(tool_name)

            # Create implementation function - capture tool_name in closure
            # Use a factory function to properly capture the tool_name
            def make_tool_impl(original_name: str):
                """Create a tool implementation function."""
                async def async_impl(**kwargs) -> SdkCallToolResult:
                    logger.debug(f"[vmcp_sdk.client] Calling tool: {original_name}")
                    request = VMCPToolCallRequest(
                        tool_name=original_name,
                        arguments=kwargs,
                        skip_sandbox=True  # SDK calls are always from within sandbox, skip nested sandboxing
                    )
                    mcp_result:CallToolResult = await self.manager.call_tool(
                        request,
                        connect_if_needed=True,
                        return_metadata=False
                    )
                    logger.debug(f"[vmcp_sdk.client] Tool result: {mcp_result.model_dump_json()}")

                    if mcp_result.isError: 
                        raise VMCPToolExecutionError(
                            tool_name=original_name,
                            message=mcp_result.content[0].text,
                            result=self
                        )
                    # Extract result data. Return all kinds of outputs in result.result
                    result = SdkCallToolResult(content=mcp_result.content, 
                                                structuredContent=mcp_result.structuredContent, 
                                                isError=mcp_result.isError,
                                                result=None)

                    structured = result.structuredContent

                        # Extract content if not structured output
                    if not structured:
                        content = result.content[0]
                        if isinstance(content, TextContent):
                            # Check if the first element's text response is actually a valid json
                            text_data = content.text
                            if text_data:
                                try:
                                    parsed_json = json.loads(text_data)
                                    result.result = parsed_json
                                except (json.JSONDecodeError, TypeError):
                                    # Not valid JSON, combine text from all content elements as JSON array
                                    all_texts = [item.text for item in result.content if isinstance(item, TextContent)]
                                    result.result = all_texts if len(all_texts) else {}
                    else:
                        # Return the structured data as the tool call result
                        result.result = structured

                    return result
                    
                # Return async function directly (no sync wrapper)
                return async_impl

            # Create typed function
            input_schema = tool_dict.get("inputSchema", {})
            description = tool_dict.get("description", "")

            # Create implementation - properly capture tool_name
            tool_impl = make_tool_impl(tool_name)

            # Create typed function with signature
            typed_func = create_function_with_signature(
                name=normalized_name,
                description=description,
                input_schema=input_schema,
                implementation=tool_impl
            )

            logger.debug(f"Created typed function for tool: {normalized_name}")
            self._typed_functions[normalized_name] = typed_func
            # Also store by original name for lookup
            # logger.debug(f"Stored typed function for tool: {tool_name}")
            # self._typed_functions[tool_name] = typed_func
        
        self._tools_loaded = True

    async def __aenter__(self) -> 'VMCPClient':
        """
        Async context manager entry.

        Automatically loads tools when entering the context.

        Returns:
            Self for use in async with statement

        Example:
            >>> async with VMCPClient() as client:
            >>>     tools = await client.list_tools()
        """
        await self._load_tools()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """
        Async context manager exit.

        Performs cleanup when exiting the context.

        Returns:
            False to propagate any exceptions
        """
        await self.close()
        return False

    async def close(self) -> None:
        """
        Clean up resources and cached data.

        Clears tools cache and typed functions.
        This method is called automatically when using async context manager.
        """
        logger.debug("[vmcp_sdk.client] Closing VMCPClient and clearing cache")
        # Clear cached data
        self._tools_cache = None
        self._typed_functions.clear()
        self._tools_loaded = False

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all tools available in this vMCP.
        
        This method honors tool selection and overrides by bypassing the progressive
        discovery filter, similar to the progressive discovery tools_list tool.
        This ensures that selected MCP tools and tool overrides are properly included
        in the results.
        """
        if not self.vmcp_id:
            raise ValueError("No vMCP specified. Set vmcp_name or use set_active_vmcp()")
        
        # Bypass PD filter to get all tools with selection/overrides honored
        # This matches the behavior of the progressive discovery tools_list tool
        tools = await self.manager.tools_list(bypass_pd_filter=True)
        
        # Convert Tool objects to dicts
        tools_list = []
        for tool in tools:
            if hasattr(tool, 'model_dump'):
                tools_list.append(tool.model_dump())
            elif isinstance(tool, dict):
                tools_list.append(tool)
            else:
                # Fallback: convert to dict manually
                tools_list.append({
                    "name": getattr(tool, 'name', str(tool)),
                    "description": getattr(tool, 'description', ''),
                    "inputSchema": getattr(tool, 'inputSchema', {})
                })
        
        return tools_list
    
    async def list_prompts(self) -> List[Dict[str, Any]]:
        """List all prompts available in this vMCP."""
        if not self.vmcp_id:
            raise VMCPNotFoundError("No vMCP specified")
        
        prompts = await self.manager.prompts_list()
        
        # Convert Prompt objects to dicts
        prompts_list = []
        for prompt in prompts:
            if hasattr(prompt, 'model_dump'):
                prompts_list.append(prompt.model_dump())
            elif isinstance(prompt, dict):
                prompts_list.append(prompt)
            else:
                prompts_list.append({
                    "name": getattr(prompt, 'name', str(prompt)),
                    "description": getattr(prompt, 'description', ''),
                    "arguments": getattr(prompt, 'arguments', [])
                })
        
        return prompts_list
    
    async def list_resources(self) -> List[Dict[str, Any]]:
        """List all resources available in this vMCP."""
        if not self.vmcp_id:
            raise VMCPNotFoundError("No vMCP specified")
        
        vmcp_config = self.manager.load_vmcp_config(self.vmcp_id)
        if not vmcp_config:
            return []
        
        resources = vmcp_config.resources or []
        return resources
    
    # def get_tool_function(self, tool_name: str) -> Optional[Callable]:
    #     """
    #     Get a typed function for a tool.

    #     Args:
    #         tool_name: Name of the tool (original or normalized)

    #     Returns:
    #         Typed Python function for the tool, or None if not found
    #     """
    #     # Ensure tools are loaded
    #     asyncio.run(self._load_tools())

    #     # Try exact match first
    #     func = self._typed_functions.get(tool_name)
    #     if func:
    #         return func

    #     # Try with normalized name
    #     normalized = normalize_name(tool_name)
    #     return self._typed_functions.get(normalized)
    
    def __getattr__(self, name: str):
        """
        Dynamically access tool functions.

        Args:
            name: Tool name to access

        Returns:
            Tool function if found

        Raises:
            VMCPToolNotFoundError: If tool is not found
        """
        # Ensure tools are loaded
        if not self._tools_loaded:
            try:
                loop = asyncio.get_running_loop()
                # If we are in a running loop, we can't use asyncio.run
                raise RuntimeError(
                    "Cannot lazy-load tools inside a running event loop. "
                    "Use 'async with VMCPClient() as client:' or await client.load_tools() first."
                )
            except RuntimeError:
                # No running loop, safe to use asyncio.run
                asyncio.run(self._load_tools())

        # logger.debug(f"[vmcp_sdk.client] Accessing tool: {name}")
        # Try exact match first
        if name in self._typed_functions:
            return self._typed_functions[name]

        # Try normalized version
        normalized = normalize_name(name)
        if normalized != name and normalized in self._typed_functions:
            logger.warning(
                f"[vmcp_sdk.client] Tool accessed as '{name}' but normalized to '{normalized}'. "
                f"Consider using the normalized name directly."
            )
            return self._typed_functions[normalized]

        # Use fuzzy matching to find similar tool names
        all_tool_names = list(self._typed_functions.keys())
        # Get close matches (up to 5, with 60% similarity threshold)
        similar_tools = get_close_matches(name, all_tool_names, n=5, cutoff=0.6)

        # If no close matches, just show first 5 tools
        suggested_tools = similar_tools if similar_tools else all_tool_names[:5]

        raise VMCPToolNotFoundError(
            tool_name=name,
            available_tools=suggested_tools
        )

