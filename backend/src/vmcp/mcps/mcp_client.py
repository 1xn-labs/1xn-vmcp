import asyncio
import traceback
from typing import Any, Dict, Optional

import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import (
    CallToolResult,
    GetPromptResult,
    Prompt,
    PromptMessage,
    ReadResourceResult,
    Resource,
    ResourceTemplate,
    TextContent,
    TextResourceContents,
    Tool,
)
from pydantic import AnyHttpUrl, AnyUrl

from vmcp.config import settings
from vmcp.config import settings as AuthSettings
from vmcp.mcps.mcp_auth_manager import MCPAuthManager
from vmcp.mcps.mcp_configmanager import MCPConfigManager
from vmcp.mcps.models import (
    AuthenticationError,
    BadMCPRequestError,
    HTTPError,
    InvalidSessionIdError,
    MCPConnectionStatus,
    MCPOperationError,
    MCPServerConfig,
    MCPTransportType,
    OperationCancelledError,
    OperationTimedOutError,
)
from vmcp.utilities.logging.config import setup_logging
from vmcp.utilities.tracing import trace_method

BACKEND_URL = AuthSettings.base_url

# Handle Python 3.11+ ExceptionGroup
try:
    _ = ExceptionGroup  # noqa: F821
except NameError:
    # For Python < 3.11, create a dummy class
    class ExceptionGroup(Exception):  # type: ignore
        def __init__(self, message, exceptions):
            super().__init__(message)
            self.exceptions = exceptions

logger = setup_logging("1xN_MCP_CLIENT")

def safe_extract_response_info(response):
    """Safely extract status code and text from an HTTP response, handling streaming responses"""
    status_code = None
    error_text = None

    try:
        if hasattr(response, 'status_code'):
            status_code = response.status_code

        # Try to safely extract text content
        if hasattr(response, 'text'):
            try:
                error_text = response.text
            except httpx.ResponseNotRead:
                # For streaming responses, we can't read the text directly
                error_text = f"[Streaming response - status: {status_code}]"
        elif hasattr(response, 'content'):
            try:
                # Try to read content if it's available
                content = response.content
                if hasattr(content, 'decode'):
                    error_text = content.decode('utf-8', errors='ignore')
                else:
                    error_text = str(content)
            except Exception:
                error_text = f"[Unable to read response content - status: {status_code}]"
        else:
            error_text = f"[No content available - status: {status_code}]"

    except Exception as e:
        error_text = f"[Error extracting response info: {e}]"

    return status_code, error_text

def mcp_operation(func):
    """Decorator for MCP operations that handles connection management"""
    async def wrapper(self, server_name: str, *args, **kwargs):
        server_config = self.config_manager.get_server(server_name)
        if not server_config:
            server_config = self.config_manager.get_server_by_name(server_name)
            if not server_config:
                raise ValueError(f"Server configuration not found for: {server_name}")
        # Construct headers
        headers = server_config.headers or {}
        headers["mcp-protocol-version"] = "2025-06-18"
        # Add authentication headers
        if server_config.auth and server_config.auth.access_token:
            headers['Authorization'] = f'Bearer {server_config.auth.access_token}'
        if server_config.session_id:
            headers['mcp-session-id'] = server_config.session_id
        # headers['mcp-session-id'] = "kitemcp-07245b6c-77dc-4819-8798-3e8a8c1c7a39"
        # headers['mcp-session-id'] = "kitemcp-07245b6c-77dc-4819-8798-3e8a8c1c"
        logger.info(f"✅ Headers: {headers}")

        session = None
        context = None
        session_entered = False
        context_entered = False

        try:
            if server_config.transport_type == MCPTransportType.SSE:
                context = sse_client(server_config.url, headers)
                read_stream, write_stream = await context.__aenter__()
                context_entered = True
                session = ClientSession(read_stream, write_stream)
                await session.__aenter__()
                session_entered = True
                result = await session.initialize()
                logger.info(f"✅ Initialized session: {result}")
                self.connections[server_config.name] = session
                return await func(self, server_config, *args, **kwargs)
            elif server_config.transport_type == MCPTransportType.HTTP:
                context = streamablehttp_client(server_config.url, headers=headers,terminate_on_close=False)
                read_stream, write_stream, get_session_id = await context.__aenter__()
                context_entered = True
                session = ClientSession(read_stream, write_stream)
                await session.__aenter__()
                session_entered = True
                if not headers.get('mcp-session-id'):
                    result = await session.initialize()
                    session_id = get_session_id()

                    server_config.session_id = session_id
                    if self.config_manager:
                        self.config_manager.update_server_config(server_config.server_id, server_config)
                        logger.info(f"💾 [SESSION_PERSISTENCE: HTTP] Saved session ID to config for {server_config.name}: {session_id}")
                    logger.info(f"✅ Session ID: {session_id}")
                    logger.info(f"✅ Initialized session: {result}")
                else:
                    session_id = headers.get('mcp-session-id')
                    logger.info(f"✅ Using existing session ID: {session_id}")

                self.connections[server_config.name] = session
                return await func(self, server_config, *args, **kwargs)
            elif server_config.transport_type == MCPTransportType.STDIO:
                context = stdio_client(server_config.server_params)
                read_stream, write_stream = await context.__aenter__()
                context_entered = True
                session = ClientSession(read_stream, write_stream)
                await session.__aenter__()
                session_entered = True
                result = await session.initialize()
                logger.info(f"✅ Initialized session: {result}")
                self.connections[server_config.name] = session
                return await func(self, server_config, *args, **kwargs)
            else:
                logger.error(f"Invalid transport type for server {server_config.name}: {server_config.transport_type}")
                return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error(f"Authentication failed for server {server_config.name}: 401 Unauthorized")
                logger.error("Please check your access token and authentication configuration")
                raise AuthenticationError(f"Authentication failed for server {server_config.name}: 401 Unauthorized") from e
            else:
                status_code, error_text = safe_extract_response_info(e.response)
                logger.error(f"HTTP error for server {server_config.name}: {status_code} - {error_text}")
                raise HTTPError(f"HTTP error for server {server_config.name}: {status_code} - {error_text}") from e
        except asyncio.CancelledError as e:
            logger.warning(f"Operation cancelled for server {server_config.name}")
            raise OperationCancelledError(f"Operation cancelled for server {server_config.name}") from e
        except asyncio.TimeoutError as e:
            logger.error(f"Operation timed out for server {server_config.name}")
            raise OperationTimedOutError(f"Operation timed out for server {server_config.name}") from e
        except Exception as e:
            logger.error(f"Failed to connect to server {server_config.name}: {e}")
            logger.error(traceback.format_exc())

            # Handle ExceptionGroup and extract status code from nested exceptions
            status_code = None
            error_text = None
            nested_errors = []

            if isinstance(e, ExceptionGroup):
                logger.error(f"ExceptionGroup with {len(e.exceptions)} sub-exceptions:")
                for i, sub_exception in enumerate(e.exceptions):
                    nested_errors.append(f"{type(sub_exception).__name__}: {sub_exception}")

                    # Extract status code and error text safely
                    if hasattr(sub_exception, 'status_code'):
                        status_code = sub_exception.status_code
                    elif hasattr(sub_exception, 'response'):
                        status_code, error_text = safe_extract_response_info(sub_exception.response)
                    else:
                        error_text = str(sub_exception)
                    logger.error(f"Sub-exception {i+1}: {type(sub_exception).__name__}: {sub_exception} {status_code} {error_text} ")
                    logger.info("Handling 401 Unauthorized")
                    if status_code == 401:
                        if func.__name__ in ("call_tool", "get_prompt", "read_resource"):
                            logger.info(f"Handling 401 Unauthorized for {func.__name__}")
                            conversation_id = kwargs.get('conversation_id')
                            chat_client_callback_url = kwargs.get('chat_client_callback_url')
                            user_id = self.config_manager.user_id
                            logger.info(f"conversation_id in 401 Unauthorized: {conversation_id}")
                            logger.info(f"chat_client_callback_url in 401 Unauthorized: {chat_client_callback_url}")

                            if conversation_id and chat_client_callback_url:
                                logger.info(f"🔄 Using dynamic callback flow for conversation {conversation_id} to generate auth url")

                                enhanced_callback = f"{settings.base_url}/api/otherservers/oauth/callback"
                            else:
                                logger.info("🔄 Using default callback flow to generate auth url")
                                enhanced_callback = f"{settings.base_url}/api/otherservers/oauth/callback"

                            try:
                                oauth_result = await self.auth_manager.initiate_oauth_flow(
                                    server_name=server_name,
                                    server_url=server_config.url,
                                    user_id=user_id,
                                    callback_url=enhanced_callback,
                                    headers=server_config.headers,
                                    **kwargs
                                )
                                logger.info(f"initialise auth flow result: {oauth_result} in call_tool")

                                if oauth_result.get('status') == 'error':
                                    auth_text = f"OAuth initiation failed: {oauth_result.get('error')}"
                                else:
                                    auth_text_tool_call = f"Server {server_name} is unauthenticated. Please Show the following authorisation link to the user: {oauth_result['authorization_url']} to authenticate server {server_name}"
                                    auth_text_prompt = f"Server {server_name} is unauthenticated. Please authinticate using the link :  {oauth_result['authorization_url']} to authenticate server {server_name} to access the prompt"
                                    auth_text_resource = f"Server {server_name} is unauthenticated. Please authinticate using the link :  {oauth_result['authorization_url']} to authenticate server {server_name} to access the resource"

                                match func.__name__:
                                    case "call_tool":
                                        return CallToolResult(
                                            content=[TextContent(type="text", text=auth_text_tool_call)],
                                            isError=True
                                        )
                                    case "get_prompt":
                                        return GetPromptResult(
                                            description="Auth Error",
                                            messages=[PromptMessage(role="user",content=TextContent(type="text", text=auth_text_prompt))]
                                        )

                                    case "read_resource":
                                        return ReadResourceResult (
                                            contents=[TextResourceContents(uri=AnyHttpUrl("https://1xn.ai/auth-error"), mimeType='text/plain', text=auth_text_resource)]
                                        )


                            except Exception as oauth_error:
                                logger.error(f"❌ Error initiating OAuth flow: {oauth_error}")
                                # Fallback to frontend flow on error

                            # Fallback to frontend URL if missing parameters or OAuth initiation failed

                            auth_url = f"{BACKEND_URL}/web-client/oauth/authorize?server_name={server_name}"
                            auth_text = f"Ask user to authenticate server {server_name}. show the following authorisation link {auth_url} to the user. "
                            return CallToolResult(
                                content=[TextContent(type="text", text=auth_text)],
                                isError=True
                            )

                        else:
                            logger.error(f"Authentication failed for server {server_config.name}: 401 Unauthorized")
                            logger.error("Please check your access token and authentication configuration")
                            raise AuthenticationError(f"""
                            Authentication failed for server {server_config.name}: 401 Unauthorized
                            {error_text}
                            """) from e
                    elif status_code:
                        logger.error(f"HTTP error for server {server_config.name}: {status_code} - {error_text}")
                        raise MCPOperationError(f"HTTP error for server {server_config.name}: {status_code} - {error_text}") from e
            else:
                # Handle individual exceptions
                if hasattr(e, 'status_code'):
                    status_code = e.status_code
                elif hasattr(e, 'response'):
                    status_code, error_text = safe_extract_response_info(e.response)
                else:
                    error_text = str(e)

            if status_code:
                logger.error(f"Error status: {status_code}")
            if error_text:
                logger.error(f"Error text: {error_text}")
            if nested_errors:
                logger.error(f"Nested errors: {nested_errors}")

            return None
        finally:

            # Clean up session if it exists and was successfully entered
            if session and session_entered and hasattr(session, '__aexit__'):
                try:
                    await session.__aexit__(None, None, None)
                except asyncio.CancelledError:
                    logger.warning(f"Session cleanup cancelled for {server_config.name}")
                except Exception as cleanup_error:
                    logger.warning(f"Error during session cleanup for {server_config.name}: {cleanup_error}")
                    if isinstance(cleanup_error, ExceptionGroup):
                        logger.warning(f"Session cleanup ExceptionGroup details for {server_config.name}:")
                        for i, sub_exception in enumerate(cleanup_error.exceptions):
                            logger.warning(f"  Sub-exception {i+1}: {type(sub_exception).__name__}: {sub_exception}")


            # Clean up context if it exists and was successfully entered
            if context and context_entered and hasattr(context, '__aexit__'):
                try:
                    await context.__aexit__(None, None, None)
                except asyncio.CancelledError:
                    logger.warning(f"Context cleanup cancelled for {server_config.name}")
                except Exception as cleanup_error:
                    logger.warning(f"Error during context cleanup for {server_config.name}: {cleanup_error}")
                    if isinstance(cleanup_error, ExceptionGroup):
                        logger.warning(f"Context cleanup ExceptionGroup details for {server_config.name}:")
                        for i, sub_exception in enumerate(cleanup_error.exceptions):
                            logger.warning(f"  Sub-exception {i+1}: {type(sub_exception).__name__}: {sub_exception}")
                            # Extract status code and error text safely
                            # Initialize with defaults to avoid UnboundLocalError
                            status_code = None
                            error_text = str(sub_exception)

                            if hasattr(sub_exception, 'status_code'):
                                status_code = sub_exception.status_code
                            elif hasattr(sub_exception, 'response'):
                                status_code, error_text = safe_extract_response_info(sub_exception.response)

                            if status_code == 401:
                                logger.info("Handling 401 Unauthorized")
                                if func.__name__ in ("call_tool", "get_prompt", "read_resource"):
                                    logger.info(f"Handling 401 Unauthorized for {func.__name__}")
                                    conversation_id = kwargs.get('conversation_id')
                                    chat_client_callback_url = kwargs.get('chat_client_callback_url')
                                    user_id = self.config_manager.user_id
                                    logger.info(f"conversation_id in 401 Unauthorized: {conversation_id}")
                                    logger.info(f"chat_client_callback_url in 401 Unauthorized: {chat_client_callback_url}")

                                    if conversation_id and chat_client_callback_url:
                                        logger.info(f"🔄 Using dynamic callback flow for conversation {conversation_id} to generate auth url")

                                        enhanced_callback = f"{settings.base_url}/api/otherservers/oauth/callback"
                                    else:
                                        logger.info("🔄 Using default callback flow to generate auth url")
                                        enhanced_callback = f"{settings.base_url}/api/otherservers/oauth/callback"

                                    try:
                                        oauth_result = await self.auth_manager.initiate_oauth_flow(
                                            server_name=server_name,
                                            server_url=server_config.url,
                                            user_id=user_id,
                                            callback_url=enhanced_callback,
                                            headers=server_config.headers,
                                            **kwargs
                                        )
                                        logger.info(f"initialise auth flow result: {oauth_result} in {func.__name__}")

                                        if oauth_result.get('status') == 'error':
                                            auth_text = f"OAuth initiation failed: {oauth_result.get('error')}"
                                        else:
                                            auth_text = f"Server {server_name} is unauthenticated. Please Show the following authorisation link to the user: {oauth_result['authorization_url']} to authenticate server {server_name}"

                                        match func.__name__:
                                            case "call_tool":
                                                return CallToolResult(
                                                    content=[TextContent(type="text", text=auth_text)],
                                                    isError=True
                                                )
                                            case "get_prompt":
                                                return GetPromptResult(
                                                    description="Auth Error",
                                                    messages=[PromptMessage(role="user",content=TextContent(type="text", text=auth_text))]
                                                )

                                            case "read_resource":
                                                return ReadResourceResult (
                                                    contents=[TextResourceContents(uri=AnyHttpUrl("https://1xn.ai/auth-error"), mimeType='text/plain', text=auth_text)]
                                                )


                                    except Exception as oauth_error:
                                        logger.error(f"❌ Error initiating OAuth flow: {oauth_error}")

                                else:
                                    logger.error(f"Authentication failed for server {server_config.name}: 401 Unauthorized")
                                    logger.error("Please check your access token and authentication configuration")
                                    raise AuthenticationError(f"""
                                    Authentication failed for server {server_config.name}: 401 Unauthorized
                                    {error_text}
                                    """) from cleanup_error
                            elif status_code == 400:
                                logger.error(f"Bad request or Invalid session id for server {server_config.name}: 400 Bad Request")
                                logger.error("Please check your request and authentication configuration")
                                if headers.get('mcp-session-id'):
                                    raise InvalidSessionIdError("Reset session id and try initialize again") from cleanup_error
                                else:
                                    raise BadMCPRequestError("Bad request MCP errror") from cleanup_error
                            elif status_code:
                                logger.error(f"HTTP error for server {server_config.name}: {status_code} - {error_text}")
                                raise MCPOperationError(f"HTTP error for server {server_config.name}: {status_code} - {error_text}") from cleanup_error

            # Remove from connections if cleanup was successful
            if server_config.name in self.connections:
                del self.connections[server_config.name]

    async def retry_wrapper(self, server_name: str, *args, **kwargs):
        retries = 2
        server_config = self.config_manager.get_server(server_name)
        if not server_config:
            server_config = self.config_manager.get_server_by_name(server_name)
            if not server_config:
                raise ValueError(f"Server configuration not found for: {server_name}")

        for retry_count in range(retries):
            try:
                return await wrapper(self, server_name, *args, **kwargs)
            except InvalidSessionIdError:
                server_config.session_id = None
                if self.config_manager:
                    self.config_manager.update_server_config(server_config.server_id, server_config)
                continue
            except Exception as e:
                logger.error(f"Attempt {retry_count+1} of {retries} failed: {e}")
                raise

    return retry_wrapper

# Most flexible approach - Generic decorator for any MCP operation:
class MCPClientManager:
    """Manages multiple MCP server connections"""

    def __init__(self, config_manager: Optional[MCPConfigManager] = None):
        self.auth_manager = MCPAuthManager()
        self.config_manager = config_manager
        self.connections: Dict[str, ClientSession] = {}

    @mcp_operation
    @trace_method("[MCPClientManager]: List Tools", operation="list_tools")
    async def tools_list(self, server_config: MCPServerConfig, *args, **kwargs) -> Dict[str, Tool]:
        """List available tools from the MCP server"""
        session = self.connections[server_config.name]
        logger.info(f"✅ Tools list: {self.connections}")
        try:
            result = await session.list_tools()
            tool_details = {}
            for tool in result.tools:
                tool_details[tool.name] = tool
            logger.info(f"✅ Retrieved {len(tool_details)} tool details from server")
            return tool_details
        except asyncio.CancelledError as e:
            logger.warning(f"Tools list operation cancelled for server {server_config.name}")
            raise OperationCancelledError(f"Tools list operation cancelled for server {server_config.name}") from e
        except asyncio.TimeoutError as e:
            logger.error(f"Tools list operation timed out for server {server_config.name}")
            raise OperationTimedOutError(f"Tools list operation timed out for server {server_config.name}") from e
        except Exception as e:
            logger.error(f"Failed to list tools from server {server_config.name}: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(traceback.format_exc())

            raise MCPOperationError(f"Failed to list tools from server {server_config.name}: {e}") from e

    @mcp_operation
    @trace_method("[MCPClientManager]: List Prompts", operation="list_prompts")
    async def prompts_list(self, server_config: MCPServerConfig, *args, **kwargs) -> Dict[str, Prompt]:
        """List available prompts from the MCP server"""
        session = self.connections[server_config.name]
        try:
            result = await session.list_prompts()
            prompt_details = {}
            for prompt in result.prompts:
                prompt_details[prompt.name] = prompt
            logger.info(f"✅ Retrieved {len(prompt_details)} prompt details from server")
            return prompt_details
        except Exception as e:
            logger.error(f"Failed to list prompts from server: {e}")
            raise MCPOperationError(f"Failed to list prompts from server: {e}") from e

    @mcp_operation
    @trace_method("[MCPClientManager]: List Resource Templates", operation="list_resource_templates")
    async def resource_templates_list(self, server_config: MCPServerConfig, *args, **kwargs) -> Dict[str, ResourceTemplate]:
        """List available resource templates from the MCP server"""
        session = self.connections[server_config.name]
        try:
            result = await session.list_resource_templates()
            resource_template_details = {}
            for resource_template in result.resourceTemplates:
                resource_template_details[resource_template.name] = resource_template
            logger.info(f"✅ Retrieved {len(resource_template_details)} resource template details from server")
            return resource_template_details
        except Exception as e:
            logger.error(f"Failed to list resource templates from server: {e}")
            raise MCPOperationError(f"Failed to list resource templates from server: {e}") from e

    @mcp_operation
    @trace_method("[MCPClientManager]: List Resources", operation="list_resources")
    async def resources_list(self, server_config: MCPServerConfig, *args, **kwargs) -> Dict[str, Resource]:
        """List available resources from the MCP server"""
        session = self.connections[server_config.name]
        try:
            result = await session.list_resources()
            resource_details = {}
            for resource in result.resources:
                resource_details[str(resource.uri)] = resource
            logger.info(f"✅ Retrieved {len(resource_details)} resource details from server")
            return resource_details
        except Exception as e:
            logger.error(f"Failed to list resources from server: {e}")
            raise MCPOperationError(f"Failed to list resources from server: {e}") from e

    @mcp_operation
    @trace_method("[MCPClientManager]: Discover Capabilities", operation="discover_capabilities")
    async def discover_capabilities(self, server_config: MCPServerConfig, *args, **kwargs) -> Dict[str, Any]:
        """Discover capabilities of the MCP server"""
        session = self.connections[server_config.name]
        capabilities: Dict[str, Any] = {}
        errors_if_any: Dict[str, Any] = {}
        try:
            # Discover tools
            tools_result = await session.list_tools()
            for tool in tools_result.tools:
                _orig_meta = {}
                if tool.meta:
                    _orig_meta = tool.meta
                _orig_meta['server_name'] = server_config.name
                tool.meta = _orig_meta.copy()
            logger.info(f"✅ Added metadata to {server_config.name} tools")
            capabilities['tools'] = [tool.name for tool in tools_result.tools]
            capabilities['tool_details'] = tools_result.tools
        except Exception as e:
            logger.error(f"Failed to discover tools from server: {e}")
            errors_if_any['tools'] = e
            capabilities['tools'] = []
            capabilities['tool_details'] = []

        try:
            # Discover resources
            resources_result = await session.list_resources()
            capabilities['resources'] = [str(resource.uri) for resource in resources_result.resources]
            capabilities['resource_details'] = resources_result.resources
        except Exception as e:
            logger.error(f"Failed to discover resources from server: {e}")
            errors_if_any['resources'] = e
            capabilities['resources'] = []
            capabilities['resource_details'] = []

        try:
            # Discover resource templates
            templates_result = await session.list_resource_templates()
            capabilities['resource_templates'] = [template.name for template in templates_result.resourceTemplates]
            capabilities['resource_template_details'] = templates_result.resourceTemplates
        except Exception as e:
            logger.error(f"Failed to discover resource templates from server: {e}")
            errors_if_any['resource_templates'] = e
            capabilities['resource_templates'] = []
            capabilities['resource_template_details'] = []

        try:
            # Discover prompts
            prompts_result = await session.list_prompts()
            capabilities['prompts'] = [prompt.name for prompt in prompts_result.prompts]
            capabilities['prompt_details'] = prompts_result.prompts
        except Exception as e:
            logger.error(f"Failed to discover prompts from server: {e}")
            errors_if_any['prompts'] = e
            capabilities['prompts'] = []
            capabilities['prompt_details'] = []

        logger.info(f"✅ Retrieved capabilities from server [ERRORS_IF_ANY: {errors_if_any}]")
        return capabilities

    @mcp_operation
    @trace_method("[MCPClientManager]: Call Tool", operation="call_tool")
    async def call_tool(self, server_config: MCPServerConfig, tool_name: str, arguments: dict, *args, **kwargs):
        """Call a tool on the MCP server"""
        session = self.connections[server_config.name]
        try:
            result = await session.call_tool(tool_name, arguments)
            logger.info(f"✅ Called tool {tool_name} on server")
            return result
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name} on server: {e}")
            raise MCPOperationError(f"Failed to call tool {tool_name} on server: {e}") from e

    @mcp_operation
    @trace_method("[MCPClientManager]: Read Resource", operation="read_resource")
    async def read_resource(self, server_config: MCPServerConfig, resource_uri: str, *args, **kwargs):
        """Read a resource from the MCP server"""
        session = self.connections[server_config.name]
        try:
            # MCP resources can have custom URI schemes (e.g., everything://dashboard)
            # Convert string to AnyUrl (supports any URI scheme) for type compatibility
            uri: AnyUrl = AnyUrl(resource_uri)  # type: ignore[assignment]
            result = await session.read_resource(uri)
            logger.info(f"✅ Read resource {resource_uri} from server")
            return result
        except Exception as e:
            logger.error(f"Failed to read resource {resource_uri} from server: {e}")
            raise MCPOperationError(f"Failed to read resource {resource_uri} from server: {e}") from e

    @mcp_operation
    @trace_method("[MCPClientManager]: Get Prompt", operation="get_prompt")
    async def get_prompt(self, server_config: MCPServerConfig, prompt_name: str, arguments: dict, *args, **kwargs):
        """Get a prompt from the MCP server"""
        session = self.connections[server_config.name]
        try:
            result = await session.get_prompt(prompt_name, arguments)
            logger.info(f"✅ Got prompt {prompt_name} from server")
            return result
        except Exception as e:
            logger.error(f"Failed to get prompt {prompt_name} from server: {e}")
            raise MCPOperationError(f"Failed to get prompt {prompt_name} from server: {e}") from e

    @mcp_operation
    @trace_method("[MCPClientManager]: Ping Server", operation="ping_server")
    async def ping_server(self, server_config: MCPServerConfig, *args, **kwargs):
        """Ping the MCP server to check connectivity"""
        session = self.connections[server_config.name]
        try:
            await session.send_ping()
            logger.info("✅ Pinged server")
            # Update the server config status to CONNECTED
            if self.config_manager and server_config.server_id:
                server_config.status = MCPConnectionStatus.CONNECTED
                self.config_manager.update_server_config(server_config.server_id, server_config)
                logger.info(f"💾 [SESSION_PERSISTENCE: HTTP] Saved session ID to config for {server_config.name}: {server_config.session_id}")
            else:
                logger.warning(f"No config manager or server_id available for {server_config.name}")
            return MCPConnectionStatus.CONNECTED
        except Exception as e:
            logger.error(f"Failed to ping server: {e}")
            raise MCPOperationError(f"Failed to ping server: {e}") from e
