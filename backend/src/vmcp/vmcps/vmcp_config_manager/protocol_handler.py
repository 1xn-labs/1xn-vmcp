#!/usr/bin/env python3
"""
MCP Protocol Handler
====================

This module implements the core MCP (Model Context Protocol) methods for listing
and managing tools, resources, resource templates, and prompts within a vMCP.

Functions in this module handle:
- Tools listing with widget attachments and overrides
- Resources listing including custom uploads and widgets
- Resource templates listing
- Prompts listing with custom prompts and default system prompts

Each function aggregates capabilities from multiple MCP servers attached to a vMCP,
applies vMCP-specific configuration (selections, overrides, custom items), and returns
a unified list of MCP protocol objects.
"""

import asyncio
import logging
import traceback
import urllib.parse
from typing import List, Dict, Any, Optional

from mcp.types import Tool, Resource, ResourceTemplate, Prompt, PromptArgument

from vmcp.config import settings
from vmcp.storage.base import StorageBase
from vmcp.mcps.mcp_configmanager import MCPConfigManager
from vmcp.vmcps.default_prompts import get_all_default_prompts
from vmcp.vmcps.vmcp_config_manager.widget_utils import UIWidget, _tool_meta
from vmcp.utilities.tracing import trace_method, add_event, log_to_span

logger = logging.getLogger("1xN_vMCP_PROTOCOL_HANDLER")


def _parse_python_function_schema(custom_tool: dict) -> dict:
    """
    Parse Python function to extract parameters and create input schema.
    
    Combines parameters from function signature with manually defined variables.
    Function signature parameters take precedence, with manual variables providing
    additional metadata like descriptions.

    Args:
        custom_tool: Dictionary containing tool configuration with 'code' and 'variables' keys

    Returns:
        JSON schema dictionary for tool input
    """
    from .parameter_parser import parse_python_function_schema
    
    variables = custom_tool.get('variables', [])
    code = custom_tool.get('code', '')

    # Map internal types to JSON schema types
    def map_to_json_schema_type(internal_type: str) -> str:
        type_mapping = {
            'str': 'string',
            'int': 'integer', 
            'float': 'number',
            'bool': 'boolean',
            'list': 'array',
            'dict': 'object'
        }
        return type_mapping.get(internal_type, 'string')

    # Start with extracting parameters from Python function code
    properties = {}
    required = []
    
    if code:
        # Create pre-parsed variables dict for descriptions from manual variables
        pre_parsed = {var.get('name'): var.get('description', '') 
                     for var in variables if var.get('name')}
        
        # Parse function signature to extract parameters
        try:
            schema_from_code = parse_python_function_schema(code, pre_parsed)
            properties = schema_from_code.get('properties', {})
            required = schema_from_code.get('required', [])
        except Exception as e:
            logger.warning(f"Failed to parse Python function signature: {e}")

    # Process manual variables (can override or supplement extracted parameters)
    for var in variables:
        var_name = var.get('name')
        var_type = var.get('type', 'str') 
        var_description = var.get('description', f"Parameter: {var_name}")
        var_required = var.get('required', True)
        var_default = var.get('default_value')

        if var_name:
            property_schema = {
                "type": map_to_json_schema_type(var_type),
                "description": var_description
            }

            # Add default value if present
            if var_default is not None:
                property_schema["default"] = var_default

            # Override or add the property
            properties[var_name] = property_schema

            # Handle required status
            if var_required and var_name not in required:
                required.append(var_name)
            elif not var_required and var_name in required:
                required.remove(var_name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
        "$schema": "http://json-schema.org/draft-07/schema#"
    }


@trace_method("[ProtocolHandler]: List Tools")
async def tools_list(
    vmcp_id: str,
    user_id: Optional[str],
    storage: StorageBase,
    mcp_config_manager: MCPConfigManager,
    log_vmcp_operation: Optional[callable] = None
) -> List[Tool]:
    """
    List all tools from the vMCP's selected servers and custom tools.

    Aggregates tools from:
    1. All selected MCP servers (with optional filtering by selected_tools)
    2. Applies tool overrides (name, description, widget attachments)
    3. Adds custom tools (prompt-based, HTTP-based, Python-based)

    Args:
        vmcp_id: The vMCP identifier
        user_id: User ID for logging operations (optional)
        storage: Storage instance for loading vMCP config
        mcp_config_manager: MCP config manager for accessing server tools
        log_vmcp_operation: Optional callback for logging operations

    Returns:
        List of Tool objects available in this vMCP
    """
    if not vmcp_id:
        log_to_span(
            "No vmcp_id provided for tools_list",
            operation_type="tools_list",
            operation_id="tools_list_no_vmcp_id",
            result={"success": False, "error": "No vmcp_id provided"},
            level="warning"
        )
        return []

    vmcp_config = storage.load_vmcp_config(vmcp_id)
    if not vmcp_config:
        log_to_span(
            f"VMCP config not found for {vmcp_id}",
            operation_type="tools_list",
            operation_id=f"tools_list_{vmcp_id}",
            result={"success": False, "error": "VMCP config not found"},
            level="warning"
        )
        return []

    vmcp_servers = vmcp_config.vmcp_config.get('selected_servers', [])
    vmcp_selected_tools = vmcp_config.vmcp_config.get('selected_tools', {})
    vmcp_selected_tool_overrides = vmcp_config.vmcp_config.get('selected_tool_overrides', {})
    all_tools = []

    # Process tools from each server
    for server in vmcp_servers:
        server_id = server.get('server_id')
        server_name = server.get('name')
        server_tools = mcp_config_manager.tools_list(server_id)

        # Filter by selected tools if specified
        if server_id in vmcp_selected_tools:
            selected_tools = vmcp_selected_tools.get(server_id, [])
            server_tools = [tool for tool in server_tools if tool.name in selected_tools]

        selected_tool_overrides = {}
        if server_id in vmcp_selected_tool_overrides:
            selected_tool_overrides = vmcp_selected_tool_overrides.get(server_id, {})

        for tool in server_tools:
            # Apply tool overrides (name, description)
            tool_override = selected_tool_overrides.get(tool.name, {})
            _tool_name = tool_override.get("name", tool.name)
            _tool_description = tool_override.get("description", tool.description)

            # Build tool meta including widget information if attached
            tool_meta = {
                **(tool.meta or {}),
                "original_name": tool.name,
                "server": server_name,
                "vmcp_id": vmcp_id,
                "server_id": server_id
            }

            widget_meta = {}
            # Widget support removed in OSS version
            # Skip widget processing if widget_id is present
            if "widget_id" in tool_override and tool_override["widget_id"]:
                logger.info("Widget tool override detected but widgets are not supported in OSS version")
                widget_meta = {}

            tool_meta.update(widget_meta)

            vmcp_tool = Tool(
                name=f"{server_name.replace('_','')}_{_tool_name}",
                description=_tool_description,
                inputSchema=tool.inputSchema,
                outputSchema=tool.outputSchema,
                annotations=tool.annotations,
                meta=tool_meta
            )
            all_tools.append(vmcp_tool)

    # Add custom tools
    for custom_tool in vmcp_config.custom_tools:
        tool_type = custom_tool.get('tool_type', 'prompt')

        if tool_type == 'python':
            # For Python tools, parse the function to extract parameters
            tool_input_schema = _parse_python_function_schema(custom_tool)
        else:
            # For prompt and HTTP tools, use the existing logic
            tool_input_variables = custom_tool.get("variables", [])
            tool_input_schema = {
                "type": "object",
                "properties": {
                    var.get("name"): {
                        "type": "string",
                        "description": var.get("description")
                    }
                    for var in tool_input_variables
                },
                "required": [var.get("name") for var in tool_input_variables if var.get("required")],
                "additionalProperties": False,
                "$schema": "http://json-schema.org/draft-07/schema#"
            }

        # Get keywords from custom tool config and append to description
        keywords = custom_tool.get("keywords", [])
        description = custom_tool.get("description", "")

        # Append keywords to description if they exist
        if keywords:
            keywords_str = ", ".join(keywords) if isinstance(keywords, list) else str(keywords)
            description = f"{description} [Keywords: {keywords_str}]"

        title = custom_tool.get('name')

        custom_tool_obj = Tool(
            name=custom_tool.get("name"),
            description=description,
            inputSchema=tool_input_schema,
            title=title,
            meta={
                "type": "custom",
                "tool_type": tool_type,
                "vmcp_id": vmcp_id
            }
        )
        all_tools.append(custom_tool_obj)

    # Log operation if callback provided
    if user_id and log_vmcp_operation:
        asyncio.create_task(
            log_vmcp_operation(
                operation_type="tools_list",
                operation_id=vmcp_id,
                arguments=None,
                result=all_tools,
                metadata={"server": "vmcp", "tool": "all_tools", "server_id": vmcp_id}
            )
        )

    # Log success to span
    log_to_span(
        f"Successfully listed {len(all_tools)} tools for vMCP {vmcp_id}",
        operation_type="tools_list",
        operation_id=f"tools_list_{vmcp_id}",
        result={"success": True, "tool_count": len(all_tools), "tools": [tool.name for tool in all_tools[:5]]},
        level="info"
    )

    return all_tools


@trace_method("[ProtocolHandler]: List Resources")
async def resources_list(
    vmcp_id: str,
    user_id: Optional[str],
    storage: StorageBase,
    mcp_config_manager: MCPConfigManager,
    log_vmcp_operation: Optional[callable] = None
) -> List[Resource]:
    """
    List all resources from the vMCP's selected servers, custom uploads, and widgets.

    Aggregates resources from:
    1. All selected MCP servers (with optional filtering by selected_resources)
    2. Custom uploaded files/resources
    3. Built widget resources (HTML+Skybridge widgets)

    Args:
        vmcp_id: The vMCP identifier
        user_id: User ID for loading widgets and logging operations (optional)
        storage: Storage instance for loading vMCP config
        mcp_config_manager: MCP config manager for accessing server resources
        log_vmcp_operation: Optional callback for logging operations

    Returns:
        List of Resource objects available in this vMCP
    """
    if not vmcp_id:
        return []

    logger.info(f"Fetching resources for vMCP: {vmcp_id}")
    vmcp_config = storage.load_vmcp_config(vmcp_id)
    vmcp_name = vmcp_config.name
    if not vmcp_config:
        return []

    # Widgets not supported in OSS version
    vmcp_config.custom_widgets = []
    logger.info(f"Widgets not supported in OSS version, skipping widget loading for vMCP: {vmcp_id}")

    vmcp_servers = vmcp_config.vmcp_config.get('selected_servers', [])
    vmcp_selected_resources = vmcp_config.vmcp_config.get('selected_resources', {})
    logger.info(f"VMCP Config Manager: Selected resources: {vmcp_selected_resources}")
    all_resources = []

    # Process resources from each server
    for server in vmcp_servers:
        server_name = server.get('name')
        server_id = server.get('server_id')
        server_resources = mcp_config_manager.resources_list(server_id)
        logger.info(f"VMCP Config Manager: Server resources: {server_resources}")

        # Filter by selected resources if specified
        if server_id in vmcp_selected_resources:
            selected_resources = vmcp_selected_resources.get(server_id, [])
            server_resources = [resource for resource in server_resources if str(resource.uri) in selected_resources]

        logger.info(f"VMCP Config Manager: Server resources: {server_resources}")
        for resource in server_resources:
            vmcp_resource = Resource(
                name=f"{server_name.replace('_','')}_{resource.name}",
                uri=f"{server_name.replace('_','')}:{resource.uri}",
                description=resource.description,
                mimeType=resource.mimeType,
                size=resource.size,
                annotations=resource.annotations,
                meta={
                    **(resource.meta or {}),
                    "original_name": resource.name,
                    "server": server_name,
                    "vmcp_id": vmcp_id,
                    "server_id": server_id
                }
            )
            all_resources.append(vmcp_resource)

    # Add custom resources (uploaded files)
    custom_resources = vmcp_config.custom_resources
    for file in custom_resources:
        # Create a valid URI by using a proper scheme and URL-encoding the filename
        original_filename = file.get('original_filename', 'unknown_file')
        encoded_filename = urllib.parse.quote(original_filename, safe='')
        vmcp_scheme = f"vmcp-{vmcp_name.replace('_', '-')}"

        vmcp_resource = Resource(
            name=original_filename,
            title=original_filename,
            uri=f"custom:{vmcp_scheme}://{encoded_filename}",
            mimeType=file.get('content_type'),
            size=file.get('size'),
            meta={
                "original_name": original_filename,
                "server": "vmcp",
                "vmcp_id": vmcp_id
            }
        )
        all_resources.append(vmcp_resource)

    # Widget resources not supported in OSS version - skipped

    # Log operation if callback provided
    if user_id and log_vmcp_operation:
        asyncio.create_task(
            log_vmcp_operation(
                operation_type="resource_list",
                operation_id=vmcp_id,
                arguments=None,
                result=all_resources,
                metadata={"server": "vmcp", "resource": "all_resources", "server_id": vmcp_id}
            )
        )

    return all_resources


@trace_method("[ProtocolHandler]: List Resource Templates")
async def resource_templates_list(
    vmcp_id: str,
    user_id: Optional[str],
    storage: StorageBase,
    mcp_config_manager: MCPConfigManager,
    log_vmcp_operation: Optional[callable] = None
) -> List[ResourceTemplate]:
    """
    List all resource templates from the vMCP's selected servers.

    Resource templates are parameterized resources that can be instantiated
    with specific values (e.g., file://{path}, http://{url}).

    Args:
        vmcp_id: The vMCP identifier
        user_id: User ID for logging operations (optional)
        storage: Storage instance for loading vMCP config
        mcp_config_manager: MCP config manager for accessing server resource templates
        log_vmcp_operation: Optional callback for logging operations

    Returns:
        List of ResourceTemplate objects available in this vMCP
    """
    if not vmcp_id:
        return []

    vmcp_config = storage.load_vmcp_config(vmcp_id)
    if not vmcp_config:
        return []

    vmcp_servers = vmcp_config.vmcp_config.get('selected_servers', [])
    vmcp_selected_resource_templates = vmcp_config.vmcp_config.get('selected_resource_templates', {})
    all_resource_templates = []

    # Process resource templates from each server
    for server in vmcp_servers:
        server_name = server.get('name')
        server_id = server.get('server_id')
        server_resource_templates = mcp_config_manager.resource_templates_list(server_id)

        # Filter by selected resource templates if specified
        if server_id in vmcp_selected_resource_templates:
            selected_resource_templates = vmcp_selected_resource_templates.get(server_id, [])
            server_resource_templates = [template for template in server_resource_templates
                                        if template.name in selected_resource_templates]

        for template in server_resource_templates:
            # Create a new ResourceTemplate object with vMCP-specific naming
            vmcp_template = ResourceTemplate(
                name=f"{server_name.replace('_','')}_{template.name}",
                uriTemplate=template.uriTemplate,
                description=template.description,
                mimeType=template.mimeType,
                annotations=template.annotations,
                meta={
                    **(template.meta or {}),
                    "original_name": template.name,
                    "server": server_name,
                    "vmcp_id": vmcp_id,
                    "server_id": server_id
                }
            )
            all_resource_templates.append(vmcp_template)

    # Log operation if callback provided
    if user_id and log_vmcp_operation:
        asyncio.create_task(
            log_vmcp_operation(
                operation_type="resource_template_list",
                operation_id=vmcp_id,
                arguments=None,
                result=all_resource_templates,
                metadata={"server": "vmcp", "resource_template": "all_resource_templates", "server_id": vmcp_id}
            )
        )

    return all_resource_templates


@trace_method("[ProtocolHandler]: List Prompts")
async def prompts_list(
    vmcp_id: str,
    user_id: Optional[str],
    storage: StorageBase,
    mcp_config_manager: MCPConfigManager,
    log_vmcp_operation: Optional[callable] = None
) -> List[Prompt]:
    """
    List all prompts from the vMCP's selected servers, custom prompts, and default system prompts.

    Aggregates prompts from:
    1. All selected MCP servers (with optional filtering by selected_prompts)
    2. Custom prompts defined in the vMCP config
    3. Custom tools (also exposed as prompts for consistency)
    4. Default system prompts (built-in prompts available in all vMCPs)

    Args:
        vmcp_id: The vMCP identifier
        user_id: User ID for logging operations (optional)
        storage: Storage instance for loading vMCP config
        mcp_config_manager: MCP config manager for accessing server prompts
        log_vmcp_operation: Optional callback for logging operations

    Returns:
        List of Prompt objects available in this vMCP
    """
    if not vmcp_id:
        # Return default system prompts even without vMCP
        return get_all_default_prompts()

    vmcp_config = storage.load_vmcp_config(vmcp_id)
    if not vmcp_config:
        return []

    vmcp_servers = vmcp_config.vmcp_config.get('selected_servers', [])
    vmcp_selected_prompts = vmcp_config.vmcp_config.get('selected_prompts', {})
    all_prompts = []

    logger.info(f"Collecting prompts from {len(vmcp_servers)} servers...")

    # Add prompts from attached servers
    for server in vmcp_servers:
        server_name = server.get('name')
        server_id = server.get('server_id')
        server_prompts = mcp_config_manager.prompts_list(server_id)

        # Filter by selected prompts if specified
        if server_id in vmcp_selected_prompts:
            selected_prompts = vmcp_selected_prompts.get(server_id, [])
            server_prompts = [prompt for prompt in server_prompts if prompt.name in selected_prompts]

        logger.info(f"Collected {len(server_prompts)} prompts from {server_name}...")

        for prompt in server_prompts:
            # Create a new Prompt object with vMCP-specific naming
            vmcp_prompt = Prompt(
                name=f"{server_name.replace('_','')}_{prompt.name}",
                title=f"#{server_name.replace('_','')}_{prompt.name}",
                description=prompt.description,
                arguments=prompt.arguments,
                meta={
                    **(prompt.meta or {}),
                    "original_name": prompt.name,
                    "server": server_name,
                    "vmcp_id": vmcp_id,
                    "server_id": server_id
                }
            )
            all_prompts.append(vmcp_prompt)

    # Add custom prompts from vMCP config
    for custom_prompt in vmcp_config.custom_prompts:
        # Convert custom prompt variables to PromptArgument objects
        prompt_arguments = []

        # Add variables from custom prompt
        if custom_prompt.get('variables'):
            for var in custom_prompt['variables']:
                prompt_arg = PromptArgument(
                    name=var.get('name'),
                    description=var.get('description', f"Variable: {var.get('name')}"),
                    required=var.get('required', False)
                )
                prompt_arguments.append(prompt_arg)

        # Note: Environment variables logic commented out in original

        # Create a new Prompt object for custom prompt
        custom_prompt_obj = Prompt(
            name=f"{custom_prompt.get('name')}",
            title=f"#{custom_prompt.get('name')}",
            description=custom_prompt.get("description", ""),
            arguments=prompt_arguments,
            meta={
                "type": "custom",
                "vmcp_id": vmcp_id,
                "custom_prompt_id": custom_prompt.get("id")
            }
        )
        all_prompts.append(custom_prompt_obj)

    # Add custom tools as prompts too
    for custom_tool in vmcp_config.custom_tools:
        # Convert custom tool variables to PromptArgument objects
        prompt_arguments = []

        # Add variables from custom tool
        if custom_tool.get('variables'):
            for var in custom_tool['variables']:
                prompt_arg = PromptArgument(
                    name=var.get('name'),
                    description=var.get('description', f"Variable: {var.get('name')}"),
                    required=var.get('required', False)
                )
                prompt_arguments.append(prompt_arg)

        # Create a new Prompt object for custom tool
        custom_prompt_obj = Prompt(
            name=f"{custom_tool.get('name')}",
            title=f"#{custom_tool.get('name')}",
            description=custom_tool.get("description", ""),
            arguments=prompt_arguments,
            meta={
                "type": "custom",
                "vmcp_id": vmcp_id,
                "custom_tool_id": custom_tool.get("id")
            }
        )
        all_prompts.append(custom_prompt_obj)

    # Add default system prompts
    default_prompts = get_all_default_prompts(vmcp_id)
    all_prompts.extend(default_prompts)

    # Log operation if callback provided
    if user_id and log_vmcp_operation:
        asyncio.create_task(
            log_vmcp_operation(
                operation_type="prompt_list",
                operation_id=vmcp_id,
                arguments=None,
                result=all_prompts,
                metadata={"server": "vmcp", "prompt": "all_prompts", "server_id": vmcp_id}
            )
        )

    return all_prompts
