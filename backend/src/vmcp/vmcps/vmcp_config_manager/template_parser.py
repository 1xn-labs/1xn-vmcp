#!/usr/bin/env python3
"""
Template Parser
===============

Handles parsing and processing of VMCP text templates with support for:
- @config.VAR substitution (environment variables)
- @param.VAR substitution (arguments)
- @resource.server.name fetching
- @tool.server.tool() execution
- @prompt.server.prompt() execution
- Jinja2 template processing
"""

import re
import json
import logging
from typing import Dict, Any, Tuple, Optional
from jinja2 import Environment, DictLoader

from .parameter_parser import parse_parameters

logger = logging.getLogger("1xN_vMCP_TEMPLATE_PARSER")


def is_jinja_template(text: str, jinja_env: Environment) -> bool:
    """Check if text contains Jinja2 patterns (after @param variables have been substituted)"""
    # Check for Jinja2 patterns
    jinja_patterns = [
        r'\{\{[^}]*\}\}',
        r'\{%[^%]*%\}',
        r'\{#[^#]*#\}'
    ]

    has_jinja_patterns = any(re.search(pattern, text) for pattern in jinja_patterns)

    if not has_jinja_patterns:
        logger.info(f"🔍 No Jinja2 patterns found in text")
        return False

    # Validate Jinja2 syntax
    try:
        jinja_env.parse(text)
        logger.info(f"✅ Valid Jinja2 template detected")
        return True
    except Exception as e:
        logger.info(f"❌ Jinja2 syntax validation failed: {e}")
        return False


def preprocess_jinja_to_regex(
    text: str,
    arguments: Dict[str, Any],
    environment_variables: Dict[str, Any],
    jinja_env: Environment
) -> str:
    """Convert Jinja2 templates to plain text for existing regex system"""
    if not is_jinja_template(text, jinja_env):
        logger.info(f"✅ Not a Jinja2 template")
        return text

    try:
        # Create Jinja2 template
        template = jinja_env.from_string(text)

        # Prepare context
        context = {
            **arguments,
            **environment_variables,
            'param': arguments,
            'config': environment_variables,
        }

        # Render the template to get final text
        rendered_text = template.render(**context)
        logger.info(f"✅ Jinja2 template rendered successfully")
        return rendered_text

    except Exception as e:
        logger.warning(f"Jinja2 preprocessing failed, using original text: {e}")
        return text


async def parse_vmcp_text(
    text: str,
    config_item: dict,
    arguments: Dict[str, Any],
    environment_variables: Dict[str, Any],
    jinja_env: Environment,
    get_resource_func,
    call_tool_func,
    get_prompt_func,
    is_prompt: bool = False
) -> Tuple[str, Optional[Any]]:
    """
    Parse VMCP text: substitute @param/@config variables, process @resource/@tool/@prompt, then Jinja2.

    Args:
        text: Text to parse
        config_item: Configuration item context
        arguments: Argument dictionary for @param substitution
        environment_variables: Environment variables for @config substitution
        jinja_env: Jinja2 environment
        get_resource_func: Function to call for @resource fetching (async)
        call_tool_func: Function to call for @tool execution (async)
        get_prompt_func: Function to call for @prompt execution (async)
        is_prompt: Whether this is being parsed in a prompt context

    Returns:
        Tuple of (processed_text, resource_content)
    """
    resource_content = None

    logger.info(f"🔍 Parsing VMCP text: {text}")
    logger.info(f"🔍 Environment variables: {environment_variables}")
    logger.info(f"🔍 Arguments: {arguments}")
    logger.info(f"🔍 Is prompt: {is_prompt}")

    # Step 1: First substitute @param and @config variables using existing regex system
    processed_text = text

    # 1. Parse and substitute environment variables: @config.VAR_NAME
    env_pattern = r'@config\.(\w+)'
    def replace_env(match):
        env_name = match.group(1)
        env_value = environment_variables.get(env_name, arguments.get(env_name, f"[{env_name} not found]"))
        logger.info(f"🔄 Substituting @config.{env_name} with: {env_value}")
        return str(env_value)

    processed_text = re.sub(env_pattern, replace_env, processed_text)

    # 2. Parse and substitute local variables: @param.variable_name
    var_pattern = r'@param\.(\w+)'
    def replace_var(match):
        var_name = match.group(1)
        var_value = arguments.get(var_name, f"[{var_name} not found]")
        logger.info(f"🔄 Substituting @param.{var_name} with: {var_value}")
        return str(var_value)

    processed_text = re.sub(var_pattern, replace_var, processed_text)

    # 3. Parse and handle resource references: @resource.server.resource_name
    resource_pattern = r'@resource\.(\w+)\.([\w\/\:\.\-]+)'
    resources_to_fetch = []

    def collect_resource(match):
        server_name = match.group(1)
        resource_name = match.group(2)
        resources_to_fetch.append((server_name, resource_name, match.group(0)))
        return match.group(0)  # Keep original for now, will replace after fetching

    processed_text = re.sub(resource_pattern, collect_resource, processed_text)

    # Fetch resources and substitute
    for server_name, resource_name, original_match in resources_to_fetch:
        try:
            logger.info(f"🔍 Fetching resource: {server_name}.{resource_name}")

            # Create the resource name with server prefix
            if server_name == "vmcp":
                prefixed_resource_name = f"{resource_name}"
            else:
                prefixed_resource_name = f"{server_name.replace('_', '')}:{resource_name}"

            # Fetch the resource
            resource_result = await get_resource_func(prefixed_resource_name, connect_if_needed=True)
            logger.info(f"🔍 Resource result: {resource_result}")

            # Convert result to string
            if hasattr(resource_result, 'contents') and resource_result.contents:
                if len(resource_result.contents) > 1:
                    resource_str = json.dumps(resource_result.contents, indent=2, default=str)
                else:
                    resource_str = resource_result.contents[0].text if hasattr(resource_result.contents[0], 'text') else str(resource_result.contents[0])
            else:
                resource_str = str(resource_result)

            # For prompts, resources should be attached as separate user messages
            # For tools, just substitute inline
            if is_prompt:
                # TODO: Handle resource attachment as separate message
                processed_text = processed_text.replace(original_match, resource_str)
            else:
                processed_text = processed_text.replace(original_match, resource_str)

            logger.info(f"✅ Successfully fetched and substituted resource {server_name}.{resource_name}")

        except Exception as e:
            logger.error(f"❌ Failed to fetch resource {server_name}.{resource_name}: {e}")
            processed_text = processed_text.replace(original_match, f"[Resource fetch failed: {str(e)}]")

    # 4. Parse and handle tool calls: @tool.server.tool_name(param1="value", param2="value")
    # Allow hyphens in tool names (e.g., resolve-library-id)
    tool_pattern = r'@tool\.(\w+)\.([\w\-]+)\(([^)]*)\)'

    async def replace_tool(match):
        server_name = match.group(1)
        tool_name = match.group(2)
        params_str = match.group(3).strip()

        try:
            logger.info(f"🔍 Executing tool call: {server_name}.{tool_name}")

            # Parse parameters
            tool_arguments = {}
            if params_str:
                logger.info(f"🔍 Parsing tool parameters: {params_str}")
                tool_arguments = parse_parameters(params_str, arguments, environment_variables)

            logger.info(f"🔍 Tool arguments: {tool_arguments}")

            if server_name == "vmcp":
                prefixed_tool_name = f"{tool_name}"
            else:
                # Create the tool name with server prefix
                prefixed_tool_name = f"{server_name.replace('_', '')}_{tool_name}"
            logger.info(f"🔍 Prefixed tool name: {prefixed_tool_name}")

            # Execute the tool call
            tool_result = await call_tool_func(prefixed_tool_name, tool_arguments)

            # Extract result text
            try:
                tool_result_str = ""
                if hasattr(tool_result, 'content'):
                    if len(tool_result.content) > 1:
                        tool_result_str = json.dumps(tool_result.content, indent=2, default=str)
                    else:
                        tool_result_str = str(tool_result.content[0].text)
                else:
                    tool_result_str = str(tool_result)
            except Exception as e:
                if isinstance(tool_result, dict):
                    tool_result_str = json.dumps(tool_result, indent=2, default=str)
                else:
                    tool_result_str = str(tool_result)

            logger.info(f"✅ Successfully executed tool call {server_name}.{tool_name}")
            return tool_result_str

        except Exception as e:
            logger.error(f"❌ Failed to execute tool call {server_name}.{tool_name}: {e}")
            return f"[Tool call failed: {str(e)}]"

    # Process tool calls sequentially (since they're async)
    while True:
        match = re.search(tool_pattern, processed_text)
        if not match:
            break

        replacement = await replace_tool(match)
        processed_text = processed_text[:match.start()] + replacement + processed_text[match.end():]

    # 5. Parse and handle prompt calls: @prompt.server.prompt_name(param1="value")
    # Allow hyphens in prompt names (e.g., my-prompt-name)
    prompt_pattern = r'@prompt\.(\w+)\.([\w\-]+)\(([^)]*)\)'

    async def replace_prompt(match):
        server_name = match.group(1)
        prompt_name = match.group(2)
        params_str = match.group(3).strip()

        try:
            logger.info(f"🔍 Executing prompt call: {server_name}.{prompt_name}")

            # Parse parameters
            prompt_arguments = {}
            if params_str:
                prompt_arguments = parse_parameters(params_str, arguments, environment_variables)

            # Create the prompt name with server prefix
            if server_name == "vmcp":
                prefixed_prompt_name = f"{prompt_name}"
            else:
                prefixed_prompt_name = f"{server_name.replace('_', '')}_{prompt_name}"

            # Execute the prompt call
            prompt_result = await get_prompt_func(prefixed_prompt_name, prompt_arguments)

            # Extract result text (assuming first message content)
            try:
                if hasattr(prompt_result, 'messages') and prompt_result.messages:
                    prompt_result_str = prompt_result.messages[0].content.text
                else:
                    prompt_result_str = str(prompt_result)
            except Exception as e:
                if isinstance(prompt_result, dict):
                    prompt_result_str = json.dumps(prompt_result, indent=2, default=str)
                else:
                    prompt_result_str = str(prompt_result)

            logger.info(f"✅ Successfully executed prompt call {server_name}.{prompt_name}")
            return prompt_result_str

        except Exception as e:
            logger.error(f"❌ Failed to execute prompt call {server_name}.{prompt_name}: {e}")
            return f"[Prompt call failed: {str(e)}]"

    # Process prompt calls sequentially (since they're async)
    while True:
        match = re.search(prompt_pattern, processed_text)
        if not match:
            break

        replacement = await replace_prompt(match)
        processed_text = processed_text[:match.start()] + replacement + processed_text[match.end():]

    # Final step: Check if the fully processed text is a Jinja2 template and process it
    if is_jinja_template(processed_text, jinja_env):
        logger.info(f"🔍 Detected Jinja2 template after all substitutions")
        # Pass original context in case there are other variables not substituted by regex
        processed_text = preprocess_jinja_to_regex(processed_text, arguments, environment_variables, jinja_env)

    return processed_text, resource_content
