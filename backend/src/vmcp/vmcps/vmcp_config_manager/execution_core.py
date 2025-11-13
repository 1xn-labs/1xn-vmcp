#!/usr/bin/env python3
"""
Execution Core
==============

This module coordinates the execution of tools, prompts, system prompts, and resource templates
within a vMCP (Virtual MCP) context. It handles:

- Tool call execution (custom tools via engines, server tools with widget support)
- Prompt execution (default prompts, server prompts, custom prompts)
- System prompt generation with variable substitution
- Resource template processing with parameter interpolation

All functions include background logging capabilities to track operations for analytics and debugging.
"""

import asyncio
import logging
import urllib.parse
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from mcp.types import (
    CallToolResult,
    GetPromptResult,
    ReadResourceResult,
    Resource,
    TextContent,
    PromptMessage,
    TextResourceContents,
    EmbeddedResource
)

from vmcp.storage.base import StorageBase
from vmcp.mcps.mcp_client import MCPClientManager
from vmcp.vmcps.models import VMCPToolCallRequest, VMCPResourceTemplateRequest
from vmcp.vmcps.default_prompts import handle_default_prompt
from vmcp.utilities.tracing import trace_method, add_event

from vmcp.utilities.logging import setup_logging

logger = setup_logging("1xN_vMCP_EXECUTION_CORE")


# Widget support classes and utilities
@dataclass(frozen=True)
class UIWidget:
    """UI Widget for tool result rendering"""
    identifier: str
    title: str
    template_uri: str
    invoking: str
    invoked: str
    html: str
    response_text: str


MIME_TYPE = "text/html+skybridge"


def _embedded_widget_resource(widget: UIWidget) -> EmbeddedResource:
    """Create an embedded widget resource for tool results"""
    return EmbeddedResource(
        type="resource",
        resource=TextResourceContents(
            uri=widget.template_uri,
            mimeType=MIME_TYPE,
            text=widget.html,
            title=widget.title,
        ),
    )


@trace_method("[ExecutionCore]: Call Tool")
async def call_tool(
    storage: StorageBase,
    mcp_client_manager: MCPClientManager,
    vmcp_id: str,
    user_id: str,
    vmcp_tool_call_request: VMCPToolCallRequest,
    call_custom_tool_func,
    log_vmcp_operation_func,
    connect_if_needed: bool = True,
    return_metadata: bool = False
) -> Dict[str, Any]:
    """
    Execute a tool call within a vMCP context.

    This function handles:
    1. Custom tools (executed via custom tool engines)
    2. Server tools (routed to appropriate MCP server)
    3. Widget attachments for tool results
    4. Background logging of tool calls

    Args:
        storage: Storage instance for loading vMCP config
        mcp_client_manager: MCP client manager for server tool calls
        vmcp_id: vMCP identifier
        user_id: User identifier
        vmcp_tool_call_request: Tool call request with tool name and arguments
        call_custom_tool_func: Function to execute custom tools
        log_vmcp_operation_func: Function to log operations in background
        connect_if_needed: Whether to connect to server if not connected
        return_metadata: Whether to return metadata along with result

    Returns:
        CallToolResult with optional metadata dict

    Raises:
        ValueError: If vMCP config not found or tool not found
    """
    logger.info(f"🔍 VMCP Config Manager: call_tool called for '{vmcp_tool_call_request.tool_name}'")
    add_event(
        f"🔍 VMCP Config Manager: call_tool called for '{vmcp_tool_call_request.tool_name}'",
        metadata={
            "server": "vmcp",
            "tool": vmcp_tool_call_request.tool_name,
            "server_id": vmcp_id
        }
    )

    vmcp_config = storage.load_vmcp_config(vmcp_id)
    if not vmcp_config:
        raise ValueError(f"vMCP config not found: {vmcp_id}")

    # Check custom tools first
    custom_tools = vmcp_config.custom_tools
    for tool in custom_tools:
        if tool.get('name') == vmcp_tool_call_request.tool_name:
            result = await call_custom_tool_func(
                vmcp_tool_call_request.tool_name,
                vmcp_tool_call_request.arguments
            )
            # Add background task to log the tool call
            logger.info(f"[BACKGROUND TASK LOGGING] Adding background task to log tool call for vMCP {vmcp_id}")
            if user_id:
                # Fire and forget - don't await, just call and let it run
                asyncio.create_task(
                    log_vmcp_operation_func(
                        operation_type="tool_call",
                        operation_id=vmcp_tool_call_request.tool_name,
                        arguments=vmcp_tool_call_request.arguments,
                        result=result,
                        metadata={"server": "custom_tool", "tool": vmcp_tool_call_request.tool_name, "server_id": "custom_tool"}
                    )
                )
            if return_metadata:
                return result, {"server": "custom_tool", "tool": vmcp_tool_call_request.tool_name}
            else:
                return result

    # Parse tool name to extract server and original tool name
    tool_server_name = vmcp_tool_call_request.tool_name.split('_')[0]
    tool_original_name = "_".join(vmcp_tool_call_request.tool_name.split('_')[1:])

    logger.info(f"🔍 VMCP Config Manager: Parsed tool name - server: '{tool_server_name}', original: '{tool_original_name}'")

    vmcp_servers = vmcp_config.vmcp_config.get('selected_servers', [])
    vmcp_selected_tool_overrides = vmcp_config.vmcp_config.get('selected_tool_overrides', {})
    logger.info(f"🔍 VMCP Config Manager: Found {len(vmcp_servers)} servers in vMCP config")
    logger.info(f"🔍 VMCP Config Manager: Server details: {[(s.get('name'), s.get('name', '').replace('_', '')) for s in vmcp_servers]}")

    # Find the matching server and execute tool call
    for server in vmcp_servers:
        server_name = server.get('name')
        server_id = server.get('server_id')
        server_name_clean = server_name.replace('_', '')

        logger.info(f"🔍 VMCP Config Manager: Checking server '{server_name}' (clean: '{server_name_clean}') against '{tool_server_name}'")

        if server_name_clean == tool_server_name:
            logger.info(f"✅ VMCP Config Manager: Found matching server '{server_name}' for tool '{vmcp_tool_call_request.tool_name}'")
            logger.info(f"🔍 VMCP Config Manager: Calling tool '{tool_original_name}' on server '{server_name}'")
            logger.info(f"🔍 VMCP Config Manager: Tool overrides: {vmcp_selected_tool_overrides.get(server_id, {})}")

            # Initialize widget_meta to empty dict for all code paths
            widget_meta = {}

            # Check for tool overrides (widget attachments)
            if vmcp_selected_tool_overrides.get(server_id, {}):
                server_tool_overrides = vmcp_selected_tool_overrides.get(server_id, {})
                for _original_tool in server_tool_overrides:
                    if server_tool_overrides.get(_original_tool).get("name") == tool_original_name:
                        tool_original_name = _original_tool
                        break

                tool_override_data = server_tool_overrides[tool_original_name]
                if "widget_id" in tool_override_data and tool_override_data["widget_id"]:
                    logger.info("Widget tool override detected but widgets are not supported in OSS version")
                    # Skip widget loading - widgets not supported in OSS
                    widget_meta = {}
                else:
                    logger.info(f"🔍 VMCP Config Manager: No tool overrides found for server '{server_name}'")

            # Execute the tool call via MCP client manager
            result = await mcp_client_manager.call_tool(
                server_id,
                tool_original_name,
                vmcp_tool_call_request.arguments
            )

            logger.info(f"✅ VMCP Config Manager: Tool call successful, result type: {type(result)}")

            # Add background task to log the tool call
            logger.info(f"[BACKGROUND TASK LOGGING] Adding background task to log tool call for vMCP {vmcp_id}")
            if user_id:
                # Fire and forget - don't await, just call and let it run
                asyncio.create_task(
                    log_vmcp_operation_func(
                        operation_type="tool_call",
                        operation_id=vmcp_tool_call_request.tool_name,
                        arguments=vmcp_tool_call_request.arguments,
                        result=result,
                        metadata={"server": server_name, "tool": tool_original_name, "server_id": server_id}
                    )
                )

            # Attach widget metadata to result if present
            if widget_meta:
                result = CallToolResult(
                    content=result.content,
                    structuredContent=result.structuredContent,
                    _meta=widget_meta,
                )

            if return_metadata:
                return result, {"server": server_name, "tool": tool_original_name, "server_id": server_id}
            else:
                return result

    # If we get here, the tool was not found in any server
    logger.error(f"❌ VMCP Config Manager: Tool '{vmcp_tool_call_request.tool_name}' not found in any server")
    logger.error(f"❌ VMCP Config Manager: Searched servers: {[s.get('name') for s in vmcp_servers]}")
    raise ValueError(f"Tool {vmcp_tool_call_request.tool_name} not found in vMCP {vmcp_id}")


@trace_method("[ExecutionCore]: Get Prompt")
async def get_prompt(
    storage: StorageBase,
    mcp_client_manager: MCPClientManager,
    vmcp_id: str,
    user_id: str,
    prompt_id: str,
    get_custom_prompt_func,
    call_custom_tool_func,
    log_vmcp_operation_func,
    arguments: Optional[Dict[str, Any]] = None,
    connect_if_needed: bool = True
) -> Dict[str, Any]:
    """
    Get and execute a prompt within a vMCP context.

    This function handles:
    1. Default system prompts (e.g., vmcp_feedback)
    2. Server prompts (from attached MCP servers)
    3. Custom prompts (defined in vMCP config)
    4. Custom tools used as prompts
    5. Background logging of prompt requests

    Args:
        storage: Storage instance for loading vMCP config
        mcp_client_manager: MCP client manager for server prompt requests
        vmcp_id: vMCP identifier
        user_id: User identifier
        prompt_id: Prompt identifier (may include # prefix or server prefix)
        get_custom_prompt_func: Function to execute custom prompts
        call_custom_tool_func: Function to execute custom tools as prompts
        log_vmcp_operation_func: Function to log operations in background
        arguments: Optional arguments for prompt execution
        connect_if_needed: Whether to connect to server if not connected

    Returns:
        GetPromptResult with prompt messages

    Raises:
        ValueError: If vMCP not found or prompt not found
    """
    logger.info(f"🔍 VMCP Config Manager: Searching for prompt '{prompt_id}' in vMCP '{vmcp_id}'")

    # Check for default system prompts first
    original_prompt_id = prompt_id
    prompt_id = prompt_id[1:] if prompt_id.startswith("#") else prompt_id

    # Handle default prompts (these work without vMCP)
    default_prompt_names = ["vmcp_feedback"]  # Add more as needed
    if prompt_id in default_prompt_names:
        logger.info(f"✅ VMCP Config Manager: Found default prompt '{prompt_id}'")
        return await handle_default_prompt(original_prompt_id, user_id, vmcp_id, arguments)

    if not vmcp_id:
        raise ValueError("No vMCP ID specified")

    vmcp_config = storage.load_vmcp_config(vmcp_id)
    if not vmcp_config:
        raise ValueError(f"vMCP config not found: {vmcp_id}")

    vmcp_servers = vmcp_config.vmcp_config.get('selected_servers', [])
    logger.info(f"🔍 VMCP Config Manager: Found {len(vmcp_servers)} servers in vMCP config")
    vmcp_selected_prompts = vmcp_config.vmcp_config.get('selected_prompts', {})

    # Try to find the prompt in the servers
    for server in vmcp_servers:
        server_name = server.get('name')
        server_id = server.get('server_id')
        server_prompts = vmcp_selected_prompts.get(server_id, [])

        logger.info(f"🔍 VMCP Config Manager: Checking server '{server_name}' with {len(server_prompts)} prompts: {server_prompts}")

        # Check if this is a prefixed prompt name (server_promptname)
        expected_prefix = f"{server_name.replace('_', '')}_"
        logger.info(f"🔍 VMCP Config Manager: Expected prefix for server '{server_name}': '{expected_prefix}'")

        if prompt_id.startswith(expected_prefix):
            # Extract the original prompt name by removing the server prefix
            original_prompt_name = prompt_id[len(expected_prefix):]
            logger.info(f"🔍 VMCP Config Manager: Detected prefixed prompt. Original name: '{original_prompt_name}'")

            # Check if the original prompt name exists in the server's prompts
            if original_prompt_name in server_prompts:
                logger.info(f"✅ VMCP Config Manager: Found prompt '{original_prompt_name}' in server '{server_name}'")
                try:
                    result = await mcp_client_manager.get_prompt(
                        server_id,
                        original_prompt_name,
                        arguments,
                        connect_if_needed=connect_if_needed
                    )
                    logger.info(f"[BACKGROUND TASK LOGGING] Adding background task to log tool call for vMCP {vmcp_id}")
                    if user_id:
                        # Fire and forget - don't await, just call and let it run
                        asyncio.create_task(
                            log_vmcp_operation_func(
                                operation_type="prompt_get",
                                operation_id=original_prompt_name,
                                arguments=arguments,
                                result=result,
                                metadata={"server": server_name, "prompt": original_prompt_name, "server_id": server_id}
                            )
                        )

                    return result
                except Exception as e:
                    logger.error(f"❌ VMCP Config Manager: Failed to get prompt {original_prompt_name} from server {server_name}: {e}")
                    logger.error(f"❌ VMCP Config Manager: Server ID: {server_id}")
                    continue
            else:
                logger.warning(f"⚠️ VMCP Config Manager: Original prompt name '{original_prompt_name}' not found in server '{server_name}' prompts list")
        else:
            logger.info(f"🔍 VMCP Config Manager: Prompt '{prompt_id}' does not start with expected prefix '{expected_prefix}' for server '{server_name}'")

    # Check custom prompts
    logger.info(f"🔍 VMCP Config Manager: Checking {len(vmcp_config.custom_prompts)} custom prompts")
    for prompt in vmcp_config.custom_prompts:
        custom_prompt_name = prompt.get('name')
        logger.info(f"🔍 VMCP Config Manager: Checking custom prompt: '{custom_prompt_name}'")
        if custom_prompt_name == prompt_id:
            logger.info(f"✅ VMCP Config Manager: Found custom prompt '{prompt_id}'")
            result = await get_custom_prompt_func(prompt_id, arguments)
            logger.info(f"[BACKGROUND TASK LOGGING] Adding background task to log tool call for vMCP {vmcp_id}")
            if user_id:
                # Fire and forget - don't await, just call and let it run
                asyncio.create_task(
                    log_vmcp_operation_func(
                        operation_type="prompt_get",
                        operation_id=prompt_id,
                        arguments=arguments,
                        result=result,
                        metadata={"server": "custom_prompt", "prompt": prompt_id, "server_id": "custom_prompt"}
                    )
                )

            return result

    # Check if this is a custom tool being used as a prompt
    for tool in vmcp_config.custom_tools:
        custom_tool_name = tool.get('name')
        logger.info(f"🔍 VMCP Config Manager: Checking custom tool: '{custom_tool_name}'")
        if custom_tool_name == prompt_id:
            logger.info(f"✅ VMCP Config Manager: Found custom tool '{prompt_id}'")
            result = await call_custom_tool_func(prompt_id, arguments, tool_as_prompt=True)
            logger.info(f"[BACKGROUND TASK LOGGING] Adding background task to log tool call for vMCP {vmcp_id}")
            if user_id:
                # Fire and forget - don't await, just call and let it run
                asyncio.create_task(
                    log_vmcp_operation_func(
                        operation_type="prompt_get",
                        operation_id=prompt_id,
                        arguments=arguments,
                        result=result,
                        metadata={"server": "custom_tool", "tool": prompt_id, "server_id": "custom_tool"}
                    )
                )
            return result

    logger.error(f"❌ VMCP Config Manager: Prompt '{prompt_id}' not found in vMCP '{vmcp_id}'")
    logger.error(f"❌ VMCP Config Manager: Searched through {len(vmcp_servers)} servers and {len(vmcp_config.custom_prompts)} custom prompts")
    raise ValueError(f"Prompt {prompt_id} not found in vMCP {vmcp_id}")


@trace_method("[ExecutionCore]: Get System Prompt")
async def get_system_prompt(
    storage: StorageBase,
    vmcp_id: str,
    parse_vmcp_text_func,
    arguments: Optional[Dict[str, Any]] = None
) -> GetPromptResult:
    """
    Get and process the system prompt for a vMCP.

    This function:
    1. Loads the system prompt from vMCP config
    2. Loads environment variables for the vMCP
    3. Saves any new environment variables from arguments
    4. Parses and substitutes variables (@param, @config, @resource, @tool)
    5. Returns formatted GetPromptResult

    Args:
        storage: Storage instance for loading vMCP config and environment
        vmcp_id: vMCP identifier
        parse_vmcp_text_func: Function to parse and substitute variables in text
        arguments: Optional arguments for variable substitution

    Returns:
        GetPromptResult with processed system prompt

    Raises:
        ValueError: If vMCP config or system prompt not found
    """
    vmcp_config = storage.load_vmcp_config(vmcp_id)
    if not vmcp_config:
        raise ValueError(f"vMCP config not found: {vmcp_id}")

    system_prompt = vmcp_config.system_prompt

    if not system_prompt:
        raise ValueError(f"System prompt not found in vMCP {vmcp_id}")

    # Get the prompt text
    prompt_text = system_prompt.get('text', '')

    # Read the corresponding environment variable file for the vmcp_id from storage if available
    environment_variables = storage.load_vmcp_environment(vmcp_id)

    # We also need to save the environment variables which are also part of argument
    # Check for each environment variable if the key is present in the arguments
    # We need to store these values in the vmcp environment file so that future use we can use them
    for env_var in environment_variables:
        if env_var in arguments:
            environment_variables[env_var] = arguments[env_var]
    storage.save_vmcp_environment(vmcp_id, environment_variables)

    # Parse and substitute using regex patterns
    prompt_text, _resource_content = await parse_vmcp_text_func(
        prompt_text,
        system_prompt,
        arguments,
        environment_variables,
        is_prompt=True
    )

    # Create the TextContent
    text_content = TextContent(
        type="text",
        text=prompt_text,
        annotations=None,
        meta=None
    )

    # Create the PromptMessage
    prompt_message = PromptMessage(
        role="user",
        content=text_content
    )

    # Create the GetPromptResult
    prompt_result = GetPromptResult(
        description=system_prompt.get('description'),
        messages=[prompt_message]
    )

    return prompt_result


@trace_method("[ExecutionCore]: Get Resource Template")
async def get_resource_template(
    storage: StorageBase,
    mcp_client_manager: MCPClientManager,
    vmcp_id: str,
    vmcp_template_request: VMCPResourceTemplateRequest
) -> Resource:
    """
    Get and process a resource template within a vMCP context.

    This function:
    1. Finds the resource template in server or custom templates
    2. Processes URI template with provided parameters
    3. Returns Resource object with processed URI

    Resource templates allow dynamic resource URIs with placeholders like:
    - {user_id} - replaced with actual user ID
    - {project_id} - replaced with actual project ID
    - etc.

    Args:
        storage: Storage instance for loading vMCP config
        mcp_client_manager: MCP client manager for server template lookups
        vmcp_id: vMCP identifier
        vmcp_template_request: Template request with name and parameters

    Returns:
        Resource object with processed URI

    Raises:
        ValueError: If vMCP not found or template not found
    """
    if not vmcp_id:
        raise ValueError("No vMCP ID specified")

    vmcp_config = storage.load_vmcp_config(vmcp_id)
    if not vmcp_config:
        raise ValueError(f"vMCP config not found: {vmcp_id}")

    template_name = vmcp_template_request.template_name
    parameters = vmcp_template_request.parameters or {}

    vmcp_servers = vmcp_config.vmcp_config.get('selected_servers', [])
    vmcp_selected_resource_templates = vmcp_config.vmcp_config.get('selected_resource_templates', {})

    # Try to find the resource template in the servers
    for server in vmcp_servers:
        if template_name in vmcp_selected_resource_templates.get(server.get('name'), []):
            try:
                # Get the resource template details
                template_detail = await mcp_client_manager.get_resource_template_detail(
                    server.get('name'), template_name, connect_if_needed=True
                )
                if template_detail:
                    # Process the URI template with parameters
                    uri_template = template_detail.uriTemplate
                    processed_uri = uri_template
                    for param_name, param_value in parameters.items():
                        placeholder = f"{{{param_name}}}"
                        processed_uri = processed_uri.replace(placeholder, str(param_value))

                    # Create a resource from the template
                    resource = Resource(
                        uri=processed_uri,
                        name=template_name,
                        description=template_detail.description,
                        mimeType=template_detail.mimeType,
                        annotations=template_detail.annotations
                    )

                    return resource
            except Exception as e:
                logger.error(f"Failed to get resource template {template_name} from server {server.get('name')}: {e}")
                continue

    # Check custom resource templates
    for template in vmcp_config.custom_resource_templates:
        if template.get('name') == template_name:
            # Process custom resource template
            uri_template = template.get('uri_template', '')
            processed_uri = uri_template
            for param_name, param_value in parameters.items():
                placeholder = f"{{{param_name}}}"
                processed_uri = processed_uri.replace(placeholder, str(param_value))

            # Create a resource from the custom template
            resource = Resource(
                uri=processed_uri,
                name=template_name,
                description=template.get('description', f"Custom resource template: {template_name}"),
                mimeType=template.get('mime_type'),
                annotations=template.get('annotations')
            )

            return resource

    raise ValueError(f"Resource template {template_name} not found in vMCP {vmcp_id}")
