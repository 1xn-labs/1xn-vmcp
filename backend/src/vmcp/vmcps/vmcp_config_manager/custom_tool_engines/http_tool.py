#!/usr/bin/env python3
"""
HTTP Tool Engine
================

Execution engine for HTTP API-based custom tools with authentication support.
"""

import aiohttp
import json
import urllib.parse
import re
import base64
import logging
from typing import Dict, Any

from mcp.types import TextContent, PromptMessage, GetPromptResult, CallToolResult

logger = logging.getLogger("1xN_vMCP_HTTP_TOOL")


def substitute_variables(text: str, arguments: Dict[str, Any], environment_variables: Dict[str, Any]) -> str:
    """Substitute @param and @config variables in text"""
    # Substitute @param variables
    param_pattern = r'@param\.(\w+)'
    def replace_param(match):
        param_name = match.group(1)
        return str(arguments.get(param_name, f"[{param_name} not found]"))

    text = re.sub(param_pattern, replace_param, text)

    # Substitute @config variables
    config_pattern = r'@config\.(\w+)'
    def replace_config(match):
        config_name = match.group(1)
        return str(environment_variables.get(config_name, f"[{config_name} not found]"))

    text = re.sub(config_pattern, replace_config, text)

    return text


def substitute_url_variables(url: str, arguments: Dict[str, Any], environment_variables: Dict[str, Any]) -> str:
    """Substitute variables in URL (both {{variable}} and :pathParam patterns)"""
    # First substitute @param and @config variables
    url = substitute_variables(url, arguments, environment_variables)

    # Then substitute {{variable}} patterns
    curly_pattern = r'\{\{([^}]+)\}\}'
    def replace_curly(match):
        var_name = match.group(1)
        return str(arguments.get(var_name, environment_variables.get(var_name, f"[{var_name} not found]")))

    url = re.sub(curly_pattern, replace_curly, url)

    # Finally substitute :pathParam patterns
    path_param_pattern = r':([a-zA-Z_][a-zA-Z0-9_]*)'
    def replace_path_param(match):
        param_name = match.group(1)
        return str(arguments.get(param_name, environment_variables.get(param_name, f"[{param_name} not found]")))

    url = re.sub(path_param_pattern, replace_path_param, url)

    return url


def substitute_body_variables(body: Any, arguments: Dict[str, Any], environment_variables: Dict[str, Any]) -> Any:
    """Recursively substitute variables in request body"""
    if isinstance(body, dict):
        return {key: substitute_body_variables(value, arguments, environment_variables) for key, value in body.items()}
    elif isinstance(body, list):
        return [substitute_body_variables(item, arguments, environment_variables) for item in body]
    elif isinstance(body, str):
        return substitute_variables(body, arguments, environment_variables)
    else:
        return body


def get_auth_headers(auth: Dict[str, Any], arguments: Dict[str, Any], environment_variables: Dict[str, Any]) -> Dict[str, str]:
    """Generate authentication headers based on auth configuration"""
    auth_type = auth.get('type', 'none').lower()
    headers = {}

    if auth_type == 'bearer':
        token = auth.get('token', '')
        if token:
            # Substitute variables in token
            processed_token = substitute_variables(token, arguments, environment_variables)
            headers['Authorization'] = f"Bearer {processed_token}"

    elif auth_type == 'apikey':
        api_key = auth.get('apiKey', '')
        key_name = auth.get('keyName', 'X-API-Key')
        if api_key:
            # Substitute variables in API key
            processed_key = substitute_variables(api_key, arguments, environment_variables)
            headers[key_name] = processed_key

    elif auth_type == 'basic':
        username = auth.get('username', '')
        password = auth.get('password', '')
        if username and password:
            # Substitute variables in credentials
            processed_username = substitute_variables(username, arguments, environment_variables)
            processed_password = substitute_variables(password, arguments, environment_variables)

            # Create basic auth header
            credentials = f"{processed_username}:{processed_password}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            headers['Authorization'] = f"Basic {encoded_credentials}"

    elif auth_type == 'custom':
        # Handle custom headers
        custom_headers = auth.get('headers', {})
        for key, value in custom_headers.items():
            processed_value = substitute_variables(str(value), arguments, environment_variables)
            headers[key] = processed_value

    return headers


async def execute_http_tool(
    custom_tool: dict,
    arguments: Dict[str, Any],
    environment_variables: Dict[str, Any],
    tool_as_prompt: bool = False
):
    """
    Execute an HTTP tool with full parameter substitution and authentication support.

    Args:
        custom_tool: Tool configuration dictionary
        arguments: Tool arguments
        environment_variables: Environment variables
        tool_as_prompt: Whether to return as prompt result

    Returns:
        CallToolResult or GetPromptResult
    """
    # Get the API configuration
    api_config = custom_tool.get('api_config', {})
    if not api_config.get('url'):
        error_content = TextContent(
            type="text",
            text="No URL configured for this HTTP tool",
            annotations=None,
            meta=None
        )
        return CallToolResult(
            content=[error_content],
            structuredContent=None,
            isError=True
        )

    try:
        # Prepare the request
        method = api_config.get('method', 'GET').upper()
        url = api_config.get('url', '')
        headers = api_config.get('headers', {})
        body = api_config.get('body')
        body_parsed = api_config.get('body_parsed')
        query_params = api_config.get('query_params', {})
        auth = api_config.get('auth', {})

        logger.info(f"🔍 HTTP Tool Execution: {custom_tool.get('name')}")
        logger.info(f"🔍 Method: {method}, URL: {url}")
        logger.info(f"🔍 Arguments: {arguments}")
        logger.info(f"🔍 Environment variables: {environment_variables}")

        # Step 1: Substitute variables in URL (both {{variable}} and :pathParam patterns)
        url = substitute_url_variables(url, arguments, environment_variables)
        logger.info(f"🔍 Processed URL: {url}")

        # Step 2: Process headers with variable substitution
        processed_headers = {}
        for key, value in headers.items():
            processed_headers[key] = substitute_variables(str(value), arguments, environment_variables)

        # Step 3: Add authentication headers if configured
        if auth and auth.get('type') != 'none':
            auth_headers = get_auth_headers(auth, arguments, environment_variables)
            processed_headers.update(auth_headers)
            logger.info(f"🔍 Added auth headers: {list(auth_headers.keys())}")

        # Step 4: Process query parameters with variable substitution
        processed_query_params = {}
        for key, value in query_params.items():
            processed_value = substitute_variables(str(value), arguments, environment_variables)
            # Only add non-empty values
            if processed_value and processed_value not in ['<string>', '<long>', '<boolean>', '<number>', '']:
                processed_query_params[key] = processed_value

        # Add query parameters to URL
        if processed_query_params:
            query_string = urllib.parse.urlencode(processed_query_params)
            url = f"{url}?{query_string}" if '?' not in url else f"{url}&{query_string}"
            logger.info(f"🔍 Final URL with query params: {url}")

        # Step 5: Prepare request body for POST/PUT/PATCH requests
        request_data = None
        if method in ['POST', 'PUT', 'PATCH', 'DELETE'] and (body or body_parsed):
            if body_parsed:
                # Use the parsed body with @param substitutions
                processed_body = substitute_body_variables(body_parsed, arguments, environment_variables)
                request_data = json.dumps(processed_body, indent=2)
                processed_headers.setdefault('Content-Type', 'application/json')
                logger.info(f"🔍 Using body_parsed: {processed_body}")
            elif body:
                # Use the raw body with variable substitution
                if isinstance(body, dict):
                    processed_body = substitute_body_variables(body, arguments, environment_variables)
                    request_data = json.dumps(processed_body, indent=2)
                    processed_headers.setdefault('Content-Type', 'application/json')
                else:
                    request_data = substitute_variables(str(body), arguments, environment_variables)
                    processed_headers.setdefault('Content-Type', 'application/json')
                logger.info(f"🔍 Using raw body: {request_data}")

        # Step 6: Make the HTTP request
        logger.info(f"🔍 Making {method} request to: {url}")
        logger.info(f"🔍 Headers: {processed_headers}")

        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=method,
                url=url,
                headers=processed_headers,
                data=request_data,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response_text = await response.text()

                # Try to parse JSON response for better formatting
                try:
                    response_json = json.loads(response_text)
                    formatted_response = json.dumps(response_json, indent=2)
                except json.JSONDecodeError:
                    formatted_response = response_text

                # Create result text
                result_text = f"Status: {response.status}\n"
                result_text += f"Status Text: {response.reason}\n"
                result_text += f"Headers: {dict(response.headers)}\n"
                result_text += f"Response:\n{formatted_response}"

                

                # Create the TextContent
                text_content = TextContent(
                    type="text",
                    text=result_text,
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
                        description="HTTP tool execution result",
                        messages=[prompt_message]
                    )
                    return prompt_result

                # Create the CallToolResult
                tool_result = CallToolResult(
                    content=[text_content],
                    structuredContent=None,
                    isError=response.status >= 400
                )

                logger.info(f"✅ HTTP tool execution completed with status: {response.status}")
                return tool_result

    except Exception as e:
        logger.error(f"❌ Error executing HTTP tool: {str(e)}")
        error_content = TextContent(
            type="text",
            text=f"Error executing HTTP tool: {str(e)}",
            annotations=None,
            meta=None
        )
        return CallToolResult(
            content=[error_content],
            structuredContent=None,
            isError=True
        )
