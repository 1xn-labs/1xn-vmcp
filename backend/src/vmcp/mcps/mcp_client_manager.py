import asyncio, contextlib
from datetime import timedelta

from contextlib import AsyncExitStack
import traceback
from typing import Any, Callable, Dict, Optional

import anyio
import httpx
import mcp
from mcp import ClientSession, McpError, StdioServerParameters
from mcp.client.session_group import (
    ClientSessionGroup,
    SseServerParameters,
    StreamableHttpParameters,
)
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.server.session import ServerSession
from mcp.shared.session import RequestResponder
# Note: sse_client, stdio_client, streamablehttp_client are now handled by ClientSessionGroup
from mcp.types import (
    Prompt, Resource, ResourceTemplate, Tool,
    ServerNotification, ServerRequest, ClientResult,
    ToolListChangedNotification, ResourceListChangedNotification,
    PromptListChangedNotification, ResourceUpdatedNotification,
    LoggingMessageNotification, ProgressNotification,
)
from pydantic import AnyUrl

from vmcp.config import settings as AuthSettings
from vmcp.mcps.mcp_auth_manager import MCPAuthManager
from vmcp.mcps.mcp_config_manager import MCPConfigManager
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
from vmcp.utilities.logging.config import get_logger
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

logger = get_logger("VMCP_MCP_CLIENT")

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
    # from vmcp.config import settings
    from mcp.types import CallToolResult, GetPromptResult, PromptMessage, ReadResourceResult, TextContent, TextResourceContents
    from pydantic import AnyHttpUrl

    logger.info(f"Handling 401 Unauthorized for {func.__name__}")
    user_id = self.config_manager.user_id
    # enhanced_callback = f"{settings.base_url}/api/otherservers/oauth/callback"

    try:
        oauth_result = await self.auth_manager.initiate_oauth_flow(
            server_name=server_name,
            server_url=server_config.url,
            user_id=user_id,
            # callback_url=enhanced_callback,
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

    def __init__(self, config_manager: Optional[MCPConfigManager] = None, keep_alive: Optional[bool] = False) -> None:
        # Get the calling function for logging
        # import inspect
        # current_frame = inspect.currentframe()
        # caller_frame = current_frame.f_back if current_frame else None
        # caller_info = f"{caller_frame.f_code.co_filename}:{caller_frame.f_lineno} in {caller_frame.f_code.co_name}" if caller_frame else "Unknown"

        logger.debug(f"------------- Initializing MCPClientManager [KeepAlive: {keep_alive}] -------------")
        # logger.info(f"   📍 Called from: {caller_info}")

        self.auth_manager = MCPAuthManager()
        self.config_manager = config_manager
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()
        self._keep_alive = keep_alive
        self._exit_stack: AsyncExitStack = AsyncExitStack()
        # ClientSessionGroup manages all connections (stdio, SSE, HTTP)
        # self._session_group: ClientSessionGroup | None = None
        self._server_sessions: Dict[str, ClientSession] = {}  # server_id -> session mapping
        # Track raw cleanup tasks in detached context - each task will clean up its own resources
        self._session_cleanup_tasks: Dict[ClientSession, asyncio.Task] = {}
        self._server_id_to_name: Dict[str, str] = {}  # server_id -> server_name mapping
        self._started = False

        # Track detached connection tasks to prevent them from being garbage collected
        #self._connection_tasks: set[asyncio.Task] = set()

        # Notification forwarding: downstream session to forward notifications to
        self._downstream_session: ServerSession | None = None

    def set_downstream_session(self, session: ServerSession) -> None:
        """Set the downstream ServerSession to forward notifications to.

        This should be called by VMCPServer once the ServerSession is available.
        """
        logger.info("[MCPClientManager NOTIFICATION] Setting downstream session for notification forwarding")
        self._downstream_session = session

    def _create_notification_handler(self, server_name: str) -> Callable:
        """Create a message_handler callback for ClientSession that forwards notifications.

        Args:
            server_name: The name of the upstream MCP server (for logging)

        Returns:
            A callback function that handles messages from the upstream server
        """
        async def message_handler(
            message: RequestResponder[ServerRequest, ClientResult] | ServerNotification | Exception
        ) -> None:
            # Debug: log all incoming messages to see what we're receiving
            logger.debug(f"[MCPClientManager NOTIFICATION] message_handler received from {server_name}: {type(message).__name__}")

            # Handle exceptions from background receive loop
            if isinstance(message, Exception):
                logger.error(f"[MCPClientManager NOTIFICATION] Exception in receive loop for {server_name}: {type(message).__name__}: {message}")
                logger.error(f"[MCPClientManager NOTIFICATION] This may indicate a connection issue or timeout")
                # Don't re-raise - we've logged it, and re-raising will crash the background task
                # The session will be marked as failed and cleaned up by the exit stack
                return

            # Only handle notifications, not requests or exceptions
            if isinstance(message, ServerNotification):
                logger.debug(f"[MCPClientManager NOTIFICATION] ServerNotification.root type: {type(message.root).__name__}")
                await self._forward_notification(server_name, message)
            else:
                logger.debug(f"[MCPClientManager NOTIFICATION] Not a ServerNotification, skipping: {type(message).__name__}")
            # Let other messages pass through (handled by default behavior)
            await anyio.lowlevel.checkpoint()

        return message_handler

    async def _forward_notification(self, server_name: str, notification: ServerNotification) -> None:
        """Forward a notification from upstream MCP server to downstream client.

        Maps upstream notification types to downstream ServerSession methods.
        """
        if not self._downstream_session:
            logger.warning(f"[MCPClientManager NOTIFICATION] No downstream session to forward notification from {server_name}")
            return

        try:
            # Extract the actual notification from the root model
            inner = notification.root

            if isinstance(inner, ToolListChangedNotification):
                logger.info(f"[MCPClientManager NOTIFICATION] Forwarding ToolListChanged from {server_name}")
                await self._downstream_session.send_tool_list_changed()
            elif isinstance(inner, ResourceListChangedNotification):
                logger.info(f"[MCPClientManager NOTIFICATION] Forwarding ResourceListChanged from {server_name}")
                await self._downstream_session.send_resource_list_changed()
            elif isinstance(inner, PromptListChangedNotification):
                logger.info(f"[MCPClientManager NOTIFICATION] Forwarding PromptListChanged from {server_name}")
                await self._downstream_session.send_prompt_list_changed()
            elif isinstance(inner, ResourceUpdatedNotification):
                logger.info(f"[MCPClientManager NOTIFICATION] Forwarding ResourceUpdated from {server_name}")
                if inner.params and inner.params.uri:
                    await self._downstream_session.send_resource_updated(inner.params.uri)
            elif isinstance(inner, LoggingMessageNotification):
                # Forward logging messages from upstream servers
                if inner.params:
                    logger.info(f"[MCPClientManager NOTIFICATION] Forwarding LoggingMessage from {server_name}: {inner.params.level}")
                    await self._downstream_session.send_log_message(
                        level=inner.params.level,
                        data=inner.params.data,
                        logger=inner.params.logger or server_name,
                    )
            elif isinstance(inner, ProgressNotification):
                # Forward progress notifications from upstream servers
                if inner.params:
                    logger.debug(f"[MCPClientManager NOTIFICATION] Forwarding Progress from {server_name}: {inner.params.progress}/{inner.params.total or '?'}")
                    await self._downstream_session.send_progress_notification(
                        progress_token=inner.params.progressToken,
                        progress=inner.params.progress,
                        total=inner.params.total,
                        message=inner.params.message,
                    )
            else:
                # Log other notification types but don't forward
                logger.debug(f"[MCPClientManager NOTIFICATION] Ignoring notification type from {server_name}: {type(inner).__name__}")
        except Exception as e:
            logger.error(f"[MCPClientManager NOTIFICATION] Error forwarding notification from {server_name}: {e}")

    
    # _establish_session_with_handler removed in favor of nested context managers in connect_server
       
        
    async def start(self) -> None:
        """Initialize the session manager. Call once per vMCP session."""
        if self._started:
            logger.warning("[MCPClientManager] Already started, skipping")
            return

        self._started = True
        return

    async def stop(self) -> int:
        """Cleanup all connections. Call when vMCP session ends. Returns count of cleaned connections."""
        count = len(self._server_sessions)
        # Build list of "server_name (server_id)" for logging
        server_info = [f"{self._server_id_to_name.get(sid, 'unknown')} ({sid})" for sid in self._server_sessions.keys()]
        logger.info(f"[MCPClientManager] Client Stopped, Cleaning ({count} connections): {server_info}")

        # Cancel any pending connection tasks
        for task in self._session_cleanup_tasks.values():
            if not task.done():
                task.cancel()

        # Cancel all cleanup tasks (will trigger cleanup in their task context)
        logger.info(f"[MCPClientManager] Cancelling {len(self._session_cleanup_tasks)} cleanup tasks")
        cleanup_tasks = []
        for session, task in list(self._session_cleanup_tasks.items()):
            task.cancel()  # Cancel task - will trigger cleanup in except asyncio.CancelledError
            cleanup_tasks.append(task)

        # Wait for all cleanup tasks to complete (with timeout)
        if cleanup_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*cleanup_tasks, return_exceptions=True),
                    timeout=10.0
                )
                logger.info(f"[MCPClientManager] All cleanup tasks completed")
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ [MCPClientManager] Cleanup tasks timeout")

        self._session_cleanup_tasks.clear()

        # Cleanup tracking dictionaries
        self._server_sessions.clear()
        self._server_id_to_name.clear()
        self._started = False

        # Close main exit stack (should be empty now, but good practice)
        await self._exit_stack.aclose()

        logger.info(f"[MCPClientManager] Client Stopped, Cleaned {count} connections")
        return count

    def _to_server_params(self, server_config: MCPServerConfig) -> "StdioServerParameters | SseServerParameters | StreamableHttpParameters":
        """Convert MCPServerConfig to appropriate ServerParameters for ClientSessionGroup."""
        # Build headers
        headers = dict(server_config.headers) if server_config.headers else {}
        headers["mcp-protocol-version"] = "2025-06-18"

        if server_config.auth and server_config.auth.access_token:
            headers['Authorization'] = f'Bearer {server_config.auth.access_token}'
        # if server_config.session_id:
        #     headers['mcp-session-id'] = server_config.session_id

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
                terminate_on_close=True,
            )
        else:
            raise ValueError(f"Unknown transport type: {server_config.transport_type}")

    async def run_session_detached(self, server_config: MCPServerConfig, session_future: asyncio.Future[ClientSession]):
        """Run session in detached context and manage its lifecycle.

        This task stays alive to manage the session in the same task context
        where it was created. When task is cancelled, it cleans up the session.
        """
        #Get the task name from the current task
        task_name = asyncio.current_task().get_name()
        logger.info(f"[MCPClientManager DETACHED] Starting detached session task {task_name}")
        
        # Get server parameters
        server_params = self._to_server_params(server_config)
        server_name = server_config.name
        server_id = server_config.server_id or server_config.name
        
        # Create transport client based on transport type
        transport_cm = None
        if isinstance(server_params, StdioServerParameters):
            logger.info(f"📡 Opening Stdio transport connection for {server_name}({server_id})...")
            transport_cm = mcp.stdio_client(server_params)
        elif isinstance(server_params, SseServerParameters):
            logger.info(f"📡 Opening SSE transport connection for {server_name}({server_id})...")
            transport_cm = sse_client(
                url=server_params.url,
                headers=server_params.headers,
                timeout=server_params.timeout,
                sse_read_timeout=server_params.sse_read_timeout,
            )
        elif isinstance(server_params, StreamableHttpParameters):
            logger.info(f"📡 Opening StreamableHTTP transport connection for {server_name}({server_id}) headers: {server_params.headers}")
        
            transport_cm = streamablehttp_client(
                url=server_params.url,
                headers=server_params.headers,
                timeout=timedelta(seconds=60), # Explicit timeout as in snippet
                sse_read_timeout=server_params.sse_read_timeout,
                terminate_on_close=server_params.terminate_on_close,
            )
        else:
            raise ValueError(f"Unknown server parameters type: {type(server_params)}")
        
        try:
            # Use async with to properly manage contexts
            async with transport_cm as transport_result:                
                # Handle different return types from transport clients
                get_session_id = None
                if isinstance(server_params, StdioServerParameters):
                    read_stream, write_stream = transport_result
                elif isinstance(server_params, SseServerParameters):
                    read_stream, write_stream = transport_result
                else:
                    # StreamableHttpParameters returns 3 values
                    read_stream, write_stream, get_session_id = transport_result

                # Create ClientSession WITH message_handler for notification forwarding
                message_handler = self._create_notification_handler(server_name)
                
                async with ClientSession(read_stream, write_stream, message_handler=message_handler) as session:
                    logger.debug(f"✅ [MCPClientManager DETACHED] initializing session for {server_name}")
                    init_result = None
                    try:
                        init_result = await session.initialize()
                    except ExceptionGroup as eg:
                        logger.debug(f"[--------MCPClientManager DETACHED] MCPerr eg caught {eg}")
                        # Initialization failed - signal error and let contexts clean up
                        if not session_future.done():
                            session_future.set_exception(eg)
                        # Re-raise to trigger context cleanup
                        raise

                    logger.debug(f"✅ [MCPClientManager DETACHED] Session initialized for {server_name}: {init_result.serverInfo.name}")

                    if get_session_id:
                        session_id = get_session_id()
                        if session_id:
                            logger.debug(f"Session ID: {session_id}")
                            # Update session ID in config if available
                            if self.config_manager and server_config.server_id:
                                server_config.session_id = session_id
                                # We don't save to disk here to avoid excessive writes, 
                                # but it's available in memory

                    # Only assign session after successful initialization
                    self._server_sessions[server_id] = session
                    self._server_id_to_name[server_id] = server_config.name

                    # Signal that session is ready
                    session_future.set_result(session)

                    # Run interactive loop in this detached context
                    # This keeps the task and contexts alive
                    # await self.interactive_loop() 
                    # REPLACEMENT: Wait forever until cancelled
                    logger.debug(f"✅ [MCPClientManager DETACHED] waiting for task to be cancelled for {server_name}")
                    await asyncio.Event().wait()

        except asyncio.CancelledError:
            # Task cancelled - contexts will clean up automatically
            logger.info(f"[MCPClientManager DETACHED] Task cancelled for {server_config.name}, contexts cleaning up")
            # Clean up tracking
            if server_id in self._server_sessions:
                # Don't delete here, let disconnect_server handle it or just let it be overwritten
                pass
            raise  # Re-raise CancelledError
        except ExceptionGroup as eg:
            for e in eg.exceptions:
                logger.debug(f"[MCPClientManager DETACHED] eg exception: {e}")

            # Handle ExceptionGroup from anyio task groups during cleanup
            # Extract the first meaningful exception for the future if not already set
            if eg.exceptions and not session_future.done():
                first_exc = eg.exceptions[0]
                # Unwrap nested ExceptionGroups
                while isinstance(first_exc, ExceptionGroup) and first_exc.exceptions:
                    first_exc = first_exc.exceptions[0]
                session_future.set_exception(first_exc)
            # ExceptionGroup is from context cleanup - don't re-raise
        except Exception as e:
            logger.debug(f"[MCPClientManager DETACHED] exception caught: {e}")

            if not session_future.done():
                session_future.set_exception(e)
            # Don't re-raise - let task exit gracefully


    async def connect_server(self, server_config: MCPServerConfig) -> ClientSession:
        """Connect to a server using the session group. Returns the session."""
        server_id = server_config.server_id or server_config.name

        # Check if already connected
        if server_id in self._server_sessions:
            logger.info(f"♻️ ⬆️ [REUSE] Re-using existing connection for {server_config.name}")
            return self._server_sessions[server_id]

        # Create session in a detached background task to prevent ExceptionGroup from
        # the ClientSession's background receive loop from propagating to Starlette middleware.
        session_future: asyncio.Future[ClientSession] = asyncio.Future()

        # Start detached task and track it
        task = asyncio.create_task(self.run_session_detached(server_config, session_future), name=f"session_runner_{server_config.name}")

        # Wait for the session to be ready via future (NOT the task itself)
        try:
            session = await asyncio.wait_for(session_future, timeout=30.0)
            # Store the cleanup task for this session (task stays alive to manage exit stack)
            self._session_cleanup_tasks[session] = task
            return session
        except asyncio.TimeoutError:
            logger.error(f"[MCPClientManager] Session initialization timeout for {server_config.name}")
            task.cancel()
            raise MCPOperationError(f"Connection timeout for {server_config.name}")
        except Exception as e:
            logger.error(f"[MCPClientManager] Session initialization failed for {server_config.name}: {e}")
            task.cancel()
            raise
            

    async def disconnect_server(self, session: ClientSession) -> bool:
        """Disconnect from a specific server by cancelling its cleanup task."""
        try:
            # Cancel the detached task for this session (will trigger cleanup in same task context)
            if session in self._session_cleanup_tasks:
                task = self._session_cleanup_tasks.pop(session)
                task.cancel()  # Cancel task - will trigger cleanup in except asyncio.CancelledError

                # Wait for cleanup to complete (with timeout)
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except asyncio.CancelledError:
                    # Expected - task was cancelled and cleaned up
                    pass
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️ [DISCONNECT] Cleanup task timeout")
                except Exception as cleanup_err:
                    logger.error(f"❌ [DISCONNECT] Error waiting for cleanup: {cleanup_err}")

                # Remove from tracking dictionaries
                # Find and remove server_id for this session
                server_id_to_remove = None
                for server_id, tracked_session in self._server_sessions.items():
                    if tracked_session is session:
                        server_id_to_remove = server_id
                        break

                if server_id_to_remove:
                    del self._server_sessions[server_id_to_remove]
                    if server_id_to_remove in self._server_id_to_name:
                        server_name = self._server_id_to_name.pop(server_id_to_remove)
                        logger.info(f"✅ ⬇️ [DISCONNECT] Disconnected from Server: {server_name}")
                    else:
                        logger.info(f"✅ ⬇️ [DISCONNECT] Disconnected from Server (server_id: {server_id_to_remove})")
                else:
                    logger.info(f"✅ ⬇️ [DISCONNECT] Disconnected from Server (not found in tracking)")

                return True
            else:
                logger.warning(f"❌ [DISCONNECT] No cleanup task found for session, cannot disconnect properly")
                return False
        except Exception as e:
            logger.error(f"❌ [DISCONNECT] Error disconnecting from Server: {e}")
            return False

    def mcp_operation(func):
        """Decorator for MCP operations that handles connection management via ClientSessionGroup."""
        async def wrapper(self, server_name: str, *args, **kwargs):
            server_config = self.config_manager.get_server(server_name)
            if not server_config:
                server_config = self.config_manager.get_server_by_name(server_name)
                if not server_config:
                    raise ValueError(f"Server configuration not found for: {server_name}")

            session = None
            results = None
            try:
                # Use ClientSessionGroup for all transport types (persistent connections)
                session = await self.connect_server(server_config)
                if session:
                    results =  await func(self, server_config, session, *args, **kwargs)

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    logger.debug(f"Authentication failed for server {server_config.name}: 401 Unauthorized")
                    logger.debug("Please check your access token and authentication configuration")
                    return await _handle_401_oauth(self, server_name, server_config, func, kwargs)
                    #raise AuthenticationError(f"Authentication failed for server {server_config.name}: 401 Unauthorized") from e
                else:
                    status_code, error_text = safe_extract_response_info(e.response)
                    logger.error(f"HTTP error for server {server_config.name}: {status_code} - {error_text}")
                    raise HTTPError(f"HTTP error for server {server_config.name}: {status_code} - {error_text}") from e
            
            except httpx.ConnectError as e:
                logger.error(f"Connection error for server {server_config.name}: {e}")
                raise
            # except asyncio.CancelledError as e:
            #     logger.warning(f"Operation cancelled for server {server_config.name} : {e}")
            #     await self._session_group._session_exit_stacks[session].aclose()
            #     raise OperationCancelledError(f"Operation cancelled for server {server_config.name}") from e
            except asyncio.TimeoutError as e:
                logger.error(f"Operation timed out for server {server_config.name}")
                raise OperationTimedOutError(f"Operation timed out for server {server_config.name}") from e
            
            except ExceptionGroup as eg:
                logger.debug(f"Failed to connect to server {server_config.name}: {eg}")
                # logger.debug(traceback.format_exc())

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
                logger.error(f"Error for server {server_config.name}: {e}")
                raise MCPOperationError(f"Error: {e}") from e

            finally:
                # Disconnect MCP connection if not keeping alive
                if self._keep_alive is False and session is not None:
                    logger.debug(f"[MCPClientManager] Disconnecting from server {server_config.name} after operation (keep_alive=False)")
                    await self.disconnect_server(session)
                if results is not None:
                    return results

        async def retry_wrapper(self, server_name: str, *args, **kwargs):
            retries = 2
            server_config = self.config_manager.get_server(server_name)
            if not server_config:
                server_config = self.config_manager.get_server_by_name(server_name)
                if not server_config:
                    raise ValueError(f"Server configuration not found for: {server_name}")

            for retry_count in range(retries):
                try:
                    logger.debug(f"[MCPClientManager] ({server_name}) {retry_count+1}/{retries}: {func.__name__}")
                    logger.debug(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

                    return await wrapper(self, server_name, *args, **kwargs)
                except InvalidSessionIdError:
                    server_config.session_id = None
                    if self.config_manager:
                        self.config_manager.update_server_config(server_config.server_id, server_config)
                    continue
                except Exception as e:
                    logger.debug(f"[MCPClientManager] ({server_name}) {retry_count+1}/{retries} failed: {e}")
                    #cleanup before retrying

                    await asyncio.sleep(0.5 * (retry_count + 1))  # Exponential backoff
                    raise

        return retry_wrapper

    @mcp_operation
    @trace_method("[MCPClientManager]: List Tools", operation="list_tools")
    async def tools_list(self, server_config: MCPServerConfig, session: ClientSession, *args, **kwargs) -> Dict[str, Tool]:
        """List available tools from the MCP server"""
        logger.info(f"✅ Tools list for {server_config.name}")
        
        try:
            #result = await session.list_tools()
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
        result = await session.list_prompts()
        prompt_details = {}
        for prompt in result.prompts:
            prompt_details[prompt.name] = prompt
        logger.info(f"✅ Retrieved {len(prompt_details)} prompt details from server")
        return prompt_details
        

    @mcp_operation
    @trace_method("[MCPClientManager]: List Resource Templates", operation="list_resource_templates")
    async def resource_templates_list(self, server_config: MCPServerConfig, session: ClientSession, *args, **kwargs) -> Dict[str, ResourceTemplate]:
        """List available resource templates from the MCP server"""
        result = await session.list_resource_templates()
        resource_template_details = {}
        for resource_template in result.resourceTemplates:
            resource_template_details[resource_template.name] = resource_template
        logger.info(f"✅ Retrieved {len(resource_template_details)} resource template details from server")
        return resource_template_details
    
    @mcp_operation
    @trace_method("[MCPClientManager]: List Resources", operation="list_resources")
    async def resources_list(self, server_config: MCPServerConfig, session: ClientSession, *args, **kwargs) -> Dict[str, Resource]:
        """List available resources from the MCP server"""
        result = await session.list_resources()
        resource_details = {}
        for resource in result.resources:
            resource_details[str(resource.uri)] = resource
        logger.info(f"✅ Retrieved {len(resource_details)} resource details from server")
        return resource_details
        

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
            logger.debug(f"✅ Tools fetched: {len(tools_result.tools)}")
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
            logger.debug(f"✅ Resources fetched: {len(resources_result.resources)}")
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
            logger.debug(f"✅ Resource Templates fetched: {len(templates_result.resourceTemplates)}")
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
            logger.debug(f"✅ Prompts fetched: {len(prompts_result.prompts)}")
            capabilities['prompts'] = [prompt.name for prompt in prompts_result.prompts]
            capabilities['prompt_details'] = prompts_result.prompts
        except Exception as e:
            logger.warning(f"Failed to discover prompts from server: {e}")
            errors_if_any['prompts'] = e
            capabilities['prompts'] = []
            capabilities['prompt_details'] = []

        logger.info(f"✅ Retrieved capabilities from server [ERRORS_IF_ANY: {errors_if_any}]")
        return capabilities

    def _create_progress_callback(self, server_name: str, tool_name: str, progress_token: Any = None):
        """Create a progress callback that forwards progress to downstream session.

        Progress notifications from upstream servers are handled internally by the MCP SDK's
        BaseSession._receive_loop, which calls registered progress_callbacks directly.
        They don't reach the message_handler, so we need to pass this callback to call_tool.

        Args:
            server_name: Name of the upstream MCP server (for logging)
            tool_name: Name of the tool being called (for logging)
            progress_token: Optional progress token from downstream client. If provided, this token
                          will be used when forwarding progress notifications to the downstream client.
                          If not provided, a unique token will be generated (though this may not be
                          recognized by the downstream client).
        """
        # Use downstream client's progress token if provided, otherwise generate a unique one
        if progress_token is not None:
            downstream_token = progress_token
            logger.debug(f"[MCPClientManager PROGRESS] Using downstream client's progress token: {downstream_token}")
        else:
            import uuid
            downstream_token = f"{server_name}_{tool_name}_{uuid.uuid4().hex[:8]}"
            logger.debug(f"[MCPClientManager PROGRESS] Generated progress token (no downstream token provided): {downstream_token}")

        async def progress_callback(progress: float, total: float | None, message: str | None) -> None:
            if self._downstream_session:
                logger.debug(f"[MCPClientManager PROGRESS] Forwarding progress from {server_name}/{tool_name}: {progress}/{total or '?'} - {message} (token: {downstream_token})")
                try:
                    await self._downstream_session.send_progress_notification(
                        progress_token=downstream_token,
                        progress=progress,
                        total=total,
                        message=message,
                    )
                except Exception as e:
                    logger.warning(f"[MCPClientManager PROGRESS] Failed to forward progress: {e}")
            else:
                logger.debug(f"[MCPClientManager PROGRESS] No downstream session for progress from {server_name}/{tool_name}")

        return progress_callback

    @mcp_operation
    @trace_method("[MCPClientManager]: Call Tool", operation="call_tool")
    async def call_tool(self, server_config: MCPServerConfig, session: ClientSession, tool_name: str, arguments: dict, *args, progress_token: Any = None, **kwargs):
        """Call a tool on the MCP server.

        Args:
            server_config: Server configuration
            session: MCP client session
            tool_name: Name of the tool to call
            arguments: Tool arguments
            progress_token: Optional progress token from downstream client. When provided,
                          progress notifications from the upstream server will be forwarded
                          to the downstream client using this token.
        """
        # Create progress callback to forward progress notifications to downstream client
        # Use the downstream client's progress token if provided
        progress_callback = self._create_progress_callback(server_config.name, tool_name, progress_token)
        result = await session.call_tool(tool_name, arguments, progress_callback=progress_callback)
        logger.info(f"✅ Called tool {tool_name} on server")
        return result

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
                pass
                # server_config.status = MCPConnectionStatus.CONNECTED
                # self.config_manager.update_server_config(server_config.server_id, server_config)
                # logger.info(f"💾 [SESSION_PERSISTENCE: HTTP] Saved session ID to config for {server_config.name}: {server_config.session_id}")
            else:
                logger.warning(f"No config manager or server_id available for {server_config.name}")
            return MCPConnectionStatus.CONNECTED
        except Exception as e:
            logger.error(f"Failed to ping server: {e}")
            raise MCPOperationError(f"Failed to ping server: {e}") from e

