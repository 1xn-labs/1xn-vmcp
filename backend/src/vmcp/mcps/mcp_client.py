import asyncio
from contextlib import AsyncExitStack
import traceback
from typing import Any, Dict, Optional

import anyio
import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.session_group import (
    ClientSessionGroup,
    SseServerParameters,
    StreamableHttpParameters,
)
# Note: sse_client, stdio_client, streamablehttp_client are now handled by ClientSessionGroup
from mcp.types import Prompt, Resource, ResourceTemplate, Tool
from pydantic import AnyUrl

from vmcp.config import settings as AuthSettings
from vmcp.mcps.mcp_auth_manager import MCPAuthManager
from vmcp.mcps.mcp_configmanager import MCPConfigManager
from vmcp.mcps.models import (
    AuthenticationError,
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


async def _handle_401_oauth(self, server_name: str, server_config, func, kwargs):
    """Handle 401 Unauthorized by initiating OAuth flow."""
    from vmcp.config import settings
    from mcp.types import CallToolResult, GetPromptResult, PromptMessage, ReadResourceResult, TextContent, TextResourceContents
    from pydantic import AnyHttpUrl

    logger.info(f"Handling 401 Unauthorized for {func.__name__}")
    user_id = self.config_manager.user_id
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
        logger.info(f"OAuth flow result: {oauth_result}")

        if oauth_result.get('status') == 'error':
            auth_text = f"OAuth initiation failed: {oauth_result.get('error')}"
        else:
            auth_url = oauth_result.get('authorization_url', '')
            auth_text = f"Server {server_name} is unauthenticated. Please authenticate using: {auth_url}"

        match func.__name__:
            case "call_tool":
                return CallToolResult(content=[TextContent(type="text", text=auth_text)], isError=True)
            case "get_prompt":
                return GetPromptResult(description="Auth Error", messages=[PromptMessage(role="user", content=TextContent(type="text", text=auth_text))])
            case "read_resource":
                return ReadResourceResult(contents=[TextResourceContents(uri=AnyHttpUrl("https://1xn.ai/auth-error"), mimeType='text/plain', text=auth_text)])
            case _:
                raise AuthenticationError(f"Authentication failed for server {server_name}: 401 Unauthorized")

    except Exception as oauth_error:
        logger.error(f"Error initiating OAuth flow: {oauth_error}")
        raise AuthenticationError(f"Authentication failed for server {server_name}: 401 Unauthorized") from oauth_error


def mcp_operation(func):
    """Decorator for MCP operations that handles connection management via ClientSessionGroup."""
    async def wrapper(self, server_name: str, *args, **kwargs):
        server_config = self.config_manager.get_server(server_name)
        if not server_config:
            server_config = self.config_manager.get_server_by_name(server_name)
            if not server_config:
                raise ValueError(f"Server configuration not found for: {server_name}")

        try:
            # Use ClientSessionGroup for all transport types (persistent connections)
            session = await self.connect_server(server_config)
            return await func(self, server_config, session, *args, **kwargs)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.debug(f"Authentication failed for server {server_config.name}: 401 Unauthorized")
                logger.debug("Please check your access token and authentication configuration")
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
        except ExceptionGroup as eg:
            logger.debug(f"Failed to connect to server {server_config.name}: {eg}")
            logger.debug(traceback.format_exc())

            # Handle ExceptionGroup and extract status code from nested exceptions
            status_code = None
            error_text = None

            if hasattr(eg, 'exceptions'):
                for sub_exception in eg.exceptions:
                    if hasattr(sub_exception, 'status_code'):
                        status_code = sub_exception.status_code
                    elif hasattr(sub_exception, 'response'):
                        status_code, error_text = safe_extract_response_info(sub_exception.response)

                    if status_code == 401:
                        # Handle 401 with OAuth flow
                        return await _handle_401_oauth(self, server_name, server_config, func, kwargs)

            if status_code:
                logger.error(f"HTTP error for server {server_config.name}: {status_code} - {error_text}")
                raise MCPOperationError(f"HTTP error: {status_code} - {error_text}") from eg
            raise MCPOperationError(f"Connection failed: {eg}") from eg
        except Exception as e:
            logger.error(f"Unexpected error for server {server_config.name}: {e}")
            raise MCPOperationError(f"Unexpected error: {e}") from e
        # Note: No finally block needed - ClientSessionGroup handles cleanup automatically

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
                logger.debug(f"Attempt {retry_count+1} of {retries} failed: {e}")
                raise

    return retry_wrapper

# Most flexible approach - Generic decorator for any MCP operation:
class MCPClientManager:
    """Manages multiple MCP server connections using ClientSessionGroup.

    Uses MCP's built-in ClientSessionGroup for persistent connections across all
    transport types (stdio, SSE, HTTP). Connections are established once and reused
    until the session ends.

    IMPORTANT: ClientSessionGroup uses AsyncExitStack internally, which has task context
    requirements - context managers must be entered and exited in the same task.
    We run the session group in a background task to avoid "Attempted to exit cancel
    scope in a different task" errors.
    """

    def __init__(self, config_manager: Optional[MCPConfigManager] = None):
        logger.info("------------- Initializing MCPClientManager -------------")
        self.auth_manager = MCPAuthManager()
        self.config_manager = config_manager
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()

        # ClientSessionGroup manages all connections (stdio, SSE, HTTP)
        self._session_group: ClientSessionGroup | None = None
        self._server_sessions: Dict[str, ClientSession] = {}  # server_id -> session mapping
        self._server_id_to_name: Dict[str, str] = {}  # server_id -> server_name mapping
        self._started = False

        # Background task infrastructure to avoid task context errors
        self._background_task: asyncio.Task | None = None
        self._ready_event: asyncio.Event | None = None
        self._shutdown_event: asyncio.Event | None = None
        self._request_queue: asyncio.Queue | None = None

    async def _session_group_task(self) -> None:
        """Background task that owns the ClientSessionGroup context.

        All session group operations run in this task to avoid AsyncExitStack
        task context issues.
        """
        logger.info("[MCPClientManager] Background task starting...")

        def name_hook(name: str, server_info) -> str:
            return f"{server_info.name}_{name}"

        async with ClientSessionGroup(component_name_hook=name_hook) as session_group:
            self._session_group = session_group
            self._ready_event.set()
            logger.info("[MCPClientManager] ClientSessionGroup ready in background task")

            # Process requests until shutdown
            while not self._shutdown_event.is_set():
                try:
                    # Wait for requests with timeout to check shutdown periodically
                    request = await asyncio.wait_for(
                        self._request_queue.get(),
                        timeout=0.5
                    )

                    operation, args, result_future = request

                    try:
                        if operation == "connect":
                            server_params = args["server_params"]
                            server_name = args.get("server_name", "unknown")
                            logger.info(f"[MCPClientManager] Background task connecting to: {server_name}")
                            session = await session_group.connect_to_server(server_params)
                            logger.info(f"[MCPClientManager] Background task connected to: {server_name}")
                            result_future.set_result(session)
                        elif operation == "disconnect":
                            session = args["session"]
                            server_name = args.get("server_name", "unknown")
                            logger.info(f"[MCPClientManager] Background task disconnecting from: {server_name}")
                            await session_group.disconnect_from_server(session)
                            logger.info(f"[MCPClientManager] Background task disconnected from: {server_name}")
                            result_future.set_result(True)
                        else:
                            result_future.set_exception(ValueError(f"Unknown operation: {operation}"))
                    except Exception as e:
                        result_future.set_exception(e)

                except asyncio.TimeoutError:
                    # Normal timeout, check shutdown flag
                    continue
                except asyncio.CancelledError:
                    logger.info("[MCPClientManager] Background task cancelled")
                    break
                except Exception as e:
                    logger.error(f"[MCPClientManager] Error in background task: {e}")

            # Log sessions that will be cleaned up by context manager exit
            # Note: We don't call disconnect_from_server here because it can cause
            # task context errors. The ClientSessionGroup.__aexit__ handles cleanup.
            logger.info(f"[MCPClientManager] Exiting context with {len(session_group.sessions)} sessions to clean up...")

        logger.info("[MCPClientManager] Background task exiting, session group cleaned up")

    async def start(self) -> None:
        """Initialize the session group in a background task. Call once per vMCP session."""
        if self._started:
            logger.warning("[MCPClientManager] Already started, skipping")
            return

        logger.info("[MCPClientManager] Starting ClientSessionGroup in background task...")

        self._ready_event = asyncio.Event()
        self._shutdown_event = asyncio.Event()
        self._request_queue = asyncio.Queue()

        # Start the background task
        self._background_task = asyncio.create_task(self._session_group_task())

        # Wait for the session group to be ready
        await self._ready_event.wait()
        self._started = True
        logger.info("[MCPClientManager] ClientSessionGroup started")

    async def stop(self) -> int:
        """Cleanup all connections. Call when vMCP session ends. Returns count of cleaned connections."""
        if not self._started:
            logger.warning("[MCPClientManager] Not started or already stopped")
            return 0

        count = len(self._server_sessions)
        # Build list of "server_name (server_id)" for logging
        server_info = [f"{self._server_id_to_name.get(sid, 'unknown')} ({sid})" for sid in self._server_sessions.keys()]
        logger.info(f"[MCPClientManager] Stopping ClientSessionGroup ({count} connections): {server_info}")

        # Signal shutdown
        if self._shutdown_event:
            self._shutdown_event.set()

        # Wait for background task to finish
        if self._background_task:
            try:
                await asyncio.wait_for(self._background_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("[MCPClientManager] Background task timeout, cancelling...")
                self._background_task.cancel()
                try:
                    await self._background_task
                except asyncio.CancelledError:
                    pass
            except Exception as e:
                logger.error(f"[MCPClientManager] Error stopping background task: {e}")

        # Cleanup
        self._session_group = None
        self._server_sessions.clear()
        self._server_id_to_name.clear()
        self._background_task = None
        self._ready_event = None
        self._shutdown_event = None
        self._request_queue = None
        self._started = False

        logger.info(f"[MCPClientManager] ClientSessionGroup stopped, cleaned {count} connections")
        return count

    def _to_server_params(self, server_config: "MCPServerConfig") -> "StdioServerParameters | SseServerParameters | StreamableHttpParameters":
        """Convert MCPServerConfig to appropriate ServerParameters for ClientSessionGroup."""
        # Build headers
        headers = dict(server_config.headers) if server_config.headers else {}
        headers["mcp-protocol-version"] = "2025-06-18"

        if server_config.auth and server_config.auth.access_token:
            headers['Authorization'] = f'Bearer {server_config.auth.access_token}'
        if server_config.session_id:
            headers['mcp-session-id'] = server_config.session_id

        if server_config.transport_type == MCPTransportType.STDIO:
            return server_config.server_params
        elif server_config.transport_type == MCPTransportType.SSE:
            return SseServerParameters(
                url=str(server_config.url),
                headers=headers,
            )
        elif server_config.transport_type == MCPTransportType.HTTP:
            return StreamableHttpParameters(
                url=str(server_config.url),
                headers=headers,
                terminate_on_close=False,
            )
        else:
            raise ValueError(f"Unknown transport type: {server_config.transport_type}")

    async def _send_request(self, operation: str, args: dict) -> Any:
        """Send a request to the background task and wait for result."""
        if not self._request_queue:
            raise RuntimeError("MCPClientManager not started")

        result_future = asyncio.get_event_loop().create_future()
        await self._request_queue.put((operation, args, result_future))
        return await result_future

    async def connect_server(self, server_config: "MCPServerConfig") -> ClientSession:
        """Connect to a server using the session group. Returns the session."""
        if not self._started:
            await self.start()

        server_id = server_config.server_id or server_config.name

        # Check if already connected
        if server_id in self._server_sessions:
            logger.info(f"♻️  [REUSE] Reusing existing connection for {server_config.name}")
            return self._server_sessions[server_id]

        logger.info(f"🆕 [CONNECT] Connecting to server {server_config.name} (id={server_id})")

        try:
            server_params = self._to_server_params(server_config)
            # Send connect request to background task
            session = await self._send_request("connect", {
                "server_params": server_params,
                "server_name": server_config.name
            })
            self._server_sessions[server_id] = session
            self._server_id_to_name[server_id] = server_config.name
            logger.info(f"✅ [CONNECT] Connected to {server_config.name}")
            return session
        except Exception as e:
            logger.error(f"❌ [CONNECT] Failed to connect to {server_config.name}: {e}")
            raise

    async def disconnect_server(self, server_config: "MCPServerConfig") -> bool:
        """Disconnect from a specific server."""
        if not self._started:
            return False

        server_id = server_config.server_id or server_config.name
        session = self._server_sessions.get(server_id)

        if not session:
            logger.warning(f"[DISCONNECT] No session found for {server_config.name}")
            return False

        try:
            # Send disconnect request to background task
            await self._send_request("disconnect", {
                "session": session,
                "server_name": server_config.name
            })
            self._server_sessions.pop(server_id, None)
            self._server_id_to_name.pop(server_id, None)
            logger.info(f"✅ [DISCONNECT] Disconnected from {server_config.name}")
            return True
        except Exception as e:
            logger.error(f"❌ [DISCONNECT] Error disconnecting from {server_config.name}: {e}")
            return False


    @mcp_operation
    @trace_method("[MCPClientManager]: List Tools", operation="list_tools")
    async def tools_list(self, server_config: MCPServerConfig, session: ClientSession, *args, **kwargs) -> Dict[str, Tool]:
        """List available tools from the MCP server"""
        logger.info(f"✅ Tools list for {server_config.name}")
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
    async def prompts_list(self, server_config: MCPServerConfig, session: ClientSession, *args, **kwargs) -> Dict[str, Prompt]:
        """List available prompts from the MCP server"""
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
    async def resource_templates_list(self, server_config: MCPServerConfig, session: ClientSession, *args, **kwargs) -> Dict[str, ResourceTemplate]:
        """List available resource templates from the MCP server"""
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
    async def resources_list(self, server_config: MCPServerConfig, session: ClientSession, *args, **kwargs) -> Dict[str, Resource]:
        """List available resources from the MCP server"""
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
    async def discover_capabilities(self, server_config: MCPServerConfig, session: ClientSession, *args, **kwargs) -> Dict[str, Any]:
        """Discover capabilities of the MCP server"""
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
            logger.warning(f"Failed to discover resources from server: {e}")
            errors_if_any['resources'] = e
            capabilities['resources'] = []
            capabilities['resource_details'] = []

        try:
            # Discover resource templates
            templates_result = await session.list_resource_templates()
            capabilities['resource_templates'] = [template.name for template in templates_result.resourceTemplates]
            capabilities['resource_template_details'] = templates_result.resourceTemplates
        except Exception as e:
            logger.warning(f"Failed to discover resource templates from server: {e}")
            errors_if_any['resource_templates'] = e
            capabilities['resource_templates'] = []
            capabilities['resource_template_details'] = []

        try:
            # Discover prompts
            prompts_result = await session.list_prompts()
            capabilities['prompts'] = [prompt.name for prompt in prompts_result.prompts]
            capabilities['prompt_details'] = prompts_result.prompts
        except Exception as e:
            logger.warning(f"Failed to discover prompts from server: {e}")
            errors_if_any['prompts'] = e
            capabilities['prompts'] = []
            capabilities['prompt_details'] = []

        logger.info(f"✅ Retrieved capabilities from server [ERRORS_IF_ANY: {errors_if_any}]")
        return capabilities

    @mcp_operation
    @trace_method("[MCPClientManager]: Call Tool", operation="call_tool")
    async def call_tool(self, server_config: MCPServerConfig, session: ClientSession, tool_name: str, arguments: dict, *args, **kwargs):
        """Call a tool on the MCP server"""
        try:
            result = await session.call_tool(tool_name, arguments)
            logger.info(f"✅ Called tool {tool_name} on server")
            return result
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name} on server: {e}")
            raise MCPOperationError(f"Failed to call tool {tool_name} on server: {e}") from e

    @mcp_operation
    @trace_method("[MCPClientManager]: Read Resource", operation="read_resource")
    async def read_resource(self, server_config: MCPServerConfig, session: ClientSession, resource_uri: str, *args, **kwargs):
        """Read a resource from the MCP server"""
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
    async def get_prompt(self, server_config: MCPServerConfig, session: ClientSession, prompt_name: str, arguments: dict, *args, **kwargs):
        """Get a prompt from the MCP server"""
        try:
            result = await session.get_prompt(prompt_name, arguments)
            logger.info(f"✅ Got prompt {prompt_name} from server")
            return result
        except Exception as e:
            logger.error(f"Failed to get prompt {prompt_name} from server: {e}")
            raise MCPOperationError(f"Failed to get prompt {prompt_name} from server: {e}") from e

    @mcp_operation
    @trace_method("[MCPClientManager]: Ping Server", operation="ping_server")
    async def ping_server(self, server_config: MCPServerConfig, session: ClientSession, *args, **kwargs):
        """Ping the MCP server to check connectivity"""
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

