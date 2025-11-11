#!/usr/bin/env python3
"""
Prompt Tool Engine
==================

Execution engine for prompt-based custom tools.
"""

import logging
from typing import Dict, Any, Optional

from mcp.types import TextContent, PromptMessage, GetPromptResult, CallToolResult

logger = logging.getLogger("1xN_vMCP_PROMPT_TOOL")


async def get_custom_prompt(
    prompt_id: str,
    storage,
    vmcp_id: str,
    parse_vmcp_text_func,
    arguments: Optional[Dict[str, Any]] = None
) -> GetPromptResult:
    """
    Get a custom prompt with variable substitution and tool call execution.

    Args:
        prompt_id: Prompt identifier
        storage: Storage backend
        vmcp_id: Virtual MCP identifier
        parse_vmcp_text_func: Function to parse VMCP text with substitutions
        arguments: Optional arguments for substitution

    Returns:
        GetPromptResult with processed prompt
    """
    vmcp_config = storage.load_vmcp_config(vmcp_id)
    if not vmcp_config:
        raise ValueError(f"vMCP config not found: {vmcp_id}")

    # Find the custom prompt
    custom_prompt = None
    for prompt in vmcp_config.custom_prompts:
        if prompt.get('name') == prompt_id:
            custom_prompt = prompt
            break

    if not custom_prompt:
        raise ValueError(f"Custom prompt {prompt_id} not found in vMCP {vmcp_id}")

    # Get the prompt text
    prompt_text = custom_prompt.get('text', '')
    if arguments is None:
        arguments = {}

    # Read the corresponding environment variable file for the vmcp_id from storage if available
    environment_variables = storage.load_vmcp_environment(vmcp_id)
    if not environment_variables:
        environment_variables = {}

    # Parse and substitute using regex patterns
    prompt_text, _resource_content = await parse_vmcp_text_func(
        prompt_text,
        custom_prompt,
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
        description=custom_prompt.get('description'),
        messages=[prompt_message]
    )

    return prompt_result


async def call_custom_tool(
    tool_id: str,
    storage,
    vmcp_id: str,
    execute_python_tool_func,
    execute_http_tool_func,
    parse_vmcp_text_func,
    arguments: Optional[Dict[str, Any]] = None,
    tool_as_prompt: bool = False
):
    """
    Call a custom tool with appropriate execution engine based on tool type.

    Args:
        tool_id: Tool identifier
        storage: Storage backend
        vmcp_id: Virtual MCP identifier
        execute_python_tool_func: Function to execute Python tools
        execute_http_tool_func: Function to execute HTTP tools
        parse_vmcp_text_func: Function to parse VMCP text
        arguments: Optional tool arguments
        tool_as_prompt: Whether to return as prompt result

    Returns:
        CallToolResult or GetPromptResult depending on tool_as_prompt
    """
    vmcp_config = storage.load_vmcp_config(vmcp_id)
    if not vmcp_config:
        raise ValueError(f"vMCP config not found: {vmcp_id}")

    # Find the custom tool
    custom_tool = None
    for tool in vmcp_config.custom_tools:
        if tool.get('name') == tool_id:
            custom_tool = tool
            break

    if not custom_tool:
        raise ValueError(f"Custom tool {tool_id} not found in vMCP {vmcp_id}")

    if arguments is None:
        arguments = {}

    logger.info(f"🔍 PROMPT_TOOL: Received arguments for tool '{tool_id}': {arguments}")

    # Read the corresponding environment variable file for the vmcp_id from storage if available
    environment_variables = storage.load_vmcp_environment(vmcp_id)
    if not environment_variables:
        environment_variables = {}

    # Handle different tool types
    tool_type = custom_tool.get('tool_type', 'prompt')

    if tool_type == 'python':
        logger.info(f"🔍 PROMPT_TOOL: Calling Python tool with arguments: {arguments}")
        return await execute_python_tool_func(custom_tool, arguments, environment_variables, tool_as_prompt)
    elif tool_type == 'http':
        return await execute_http_tool_func(custom_tool, arguments, environment_variables, tool_as_prompt)
    else:  # prompt tool (default)
        return await execute_prompt_tool(custom_tool, arguments, environment_variables, parse_vmcp_text_func, tool_as_prompt)


async def execute_prompt_tool(
    custom_tool: dict,
    arguments: Dict[str, Any],
    environment_variables: Dict[str, Any],
    parse_vmcp_text_func,
    tool_as_prompt: bool = False
):
    """
    Execute a prompt-based tool.

    Args:
        custom_tool: Tool configuration dictionary
        arguments: Tool arguments
        environment_variables: Environment variables
        parse_vmcp_text_func: Function to parse VMCP text
        tool_as_prompt: Whether to return as prompt result

    Returns:
        CallToolResult or GetPromptResult
    """
    # Get the tool text
    tool_text = custom_tool.get('text', '')

    # Parse and substitute using regex patterns
    tool_text, _resource_content = await parse_vmcp_text_func(
        tool_text,
        custom_tool,
        arguments,
        environment_variables,
        is_prompt=tool_as_prompt
    )
    logger.info(f"🔍 Tool text: {tool_text}")
    if tool_as_prompt:
        tool_text, _resource_content = tool_text
        logger.info(f"�� Tool as prompt: {tool_text}")

    # Create the TextContent
    text_content = TextContent(
        type="text",
        text=tool_text,
        annotations=None,
        meta=None
    )

    if tool_as_prompt:
        # Create the PromptMessage
        prompt_message = PromptMessage(
            role="user",
            content=text_content
        )

        # Create the GetPromptResult
        prompt_result = GetPromptResult(
            description="Tool call result",
            messages=[prompt_message]
        )
        return prompt_result

    # Create the CallToolResult
    tool_result = CallToolResult(
        content=[text_content],
        structuredContent=None,
        isError=False
    )

    return tool_result
