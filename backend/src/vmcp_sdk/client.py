"""
Core vMCP client for interacting with vMCPs.

This is a thin wrapper around the existing VMCPConfigManager that creates
typed Python functions from tool schemas.
"""

import asyncio
from typing import Any, Dict, List, Optional

from vmcp.storage.dummy_user import UserContext
from vmcp.vmcps.vmcp_config_manager.config_core import VMCPConfigManager
from vmcp.vmcps.models import VMCPToolCallRequest

from .schema import create_function_with_signature, normalize_name


class VMCPClient:
    """
    Client for interacting with vMCPs.
    
    This is a thin wrapper around VMCPConfigManager that provides
    typed Python functions for each tool.
    """
    
    def __init__(self, vmcp_id: Optional[str] = None, user_id: int = 1):
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
            raise ValueError(
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
            raise ValueError("No vMCP specified. Set vmcp_name or use set_active_vmcp()")
        
        tools = await self.manager.tools_list()
        
        # Check if progressive discovery is enabled - if so, filter tools
        vmcp_config = self.manager.load_vmcp_config(self.vmcp_id)
        progressive_discovery_enabled = False
        if vmcp_config:
            metadata = getattr(vmcp_config, 'metadata', {}) or {}
            if isinstance(metadata, dict):
                progressive_discovery_enabled = metadata.get('progressive_discovery_enabled', False) is True
        
        # If progressive discovery is enabled, only expose PD tools
        if progressive_discovery_enabled:
            # Filter to only tools_list, tool_detail, upload_prompt
            pd_tool_names = ['tools_list', 'tool_detail', 'upload_prompt']
            tools = [t for t in tools if t.name in pd_tool_names]
        
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
                async def async_impl(**kwargs):
                    request = VMCPToolCallRequest(
                        tool_name=original_name,
                        arguments=kwargs,
                        skip_sandbox=True  # SDK calls are always from within sandbox, skip nested sandboxing
                    )
                    result = await self.manager.call_tool(
                        request,
                        connect_if_needed=True,
                        return_metadata=False
                    )

                    # Extract result data
                    if isinstance(result, dict):
                        return result
                    elif hasattr(result, 'model_dump'):
                        return result.model_dump()
                    elif hasattr(result, 'dict'):
                        return result.dict()
                    else:
                        return {"result": str(result)}

                # Wrap in sync function for compatibility
                def sync_wrapper(**kwargs):
                    return asyncio.run(async_impl(**kwargs))

                return sync_wrapper

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

            self._typed_functions[normalized_name] = typed_func
            # Also store by original name for lookup
            self._typed_functions[tool_name] = typed_func
        
        self._tools_loaded = True
    
    
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
            raise ValueError("No vMCP specified. Set vmcp_name or use set_active_vmcp()")
        
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
            raise ValueError("No vMCP specified. Set vmcp_name or use set_active_vmcp()")
        
        vmcp_config = self.manager.load_vmcp_config(self.vmcp_id)
        if not vmcp_config:
            return []
        
        resources = vmcp_config.resources or []
        return resources
    
    def get_tool_function(self, tool_name: str):
        """
        Get a typed function for a tool.
        
        Args:
            tool_name: Name of the tool (original or normalized)
            
        Returns:
            Typed Python function for the tool
        """
        # Ensure tools are loaded
        asyncio.run(self._load_tools())
        
        # Try normalized name first, then original
        func = self._typed_functions.get(tool_name)
        if func:
            return func
        
        # Try with normalized name
        normalized = normalize_name(tool_name)
        return self._typed_functions.get(normalized)
    
    def __getattr__(self, name: str):
        """Dynamically access tool functions."""
        # Ensure tools are loaded
        asyncio.run(self._load_tools())
        
        # Check if it's a tool function
        if name in self._typed_functions:
            return self._typed_functions[name]
        
        # Check if it's a method
        if name in ["list_tools", "list_prompts", "list_resources"]:
            return getattr(self, name)
        
        # Check if it might be an MCP server tool (format: ServerName_tool_name)
        # This allows calling MCP tools even when progressive discovery hides them from the tools list
        if '_' in name:
            # Try to create a dynamic function for MCP server tools
            def make_mcp_tool_impl(tool_name: str):
                """Create a tool implementation function for MCP server tools."""
                async def async_impl(**kwargs):
                    request = VMCPToolCallRequest(
                        tool_name=tool_name,
                        arguments=kwargs
                    )
                    result = await self.manager.call_tool(
                        request,
                        connect_if_needed=True,
                        return_metadata=False
                    )
                    # Extract result data
                    if isinstance(result, dict):
                        return result
                    elif hasattr(result, 'model_dump'):
                        return result.model_dump()
                    elif hasattr(result, 'dict'):
                        return result.dict()
                    else:
                        return {"result": str(result)}
                
                # Wrap in sync function for compatibility
                def sync_wrapper(**kwargs):
                    return asyncio.run(async_impl(**kwargs))
                
                return sync_wrapper
            
            # Return a generic function that accepts any kwargs
            # This allows calling MCP tools even without type information
            return make_mcp_tool_impl(name)
        
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

