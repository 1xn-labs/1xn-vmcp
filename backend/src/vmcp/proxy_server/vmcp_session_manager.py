"""
Custom Session Manager for vMCP with MCP connection cleanup support.

Extends StreamableHTTPSessionManager to handle proper cleanup of all MCP
server connections (stdio, SSE, HTTP) when sessions end.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus
from uuid import uuid4

import anyio
from anyio.abc import TaskStatus
from mcp.server.streamable_http import (
    MCP_SESSION_ID_HEADER,
    StreamableHTTPServerTransport,
)
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Receive, Scope, Send

from vmcp.utilities.logging import get_logger

logger = get_logger("VMCPSessionManager")


class VMCPSessionManager(StreamableHTTPSessionManager):
    """
    Custom session manager that handles MCP connection cleanup when sessions end.

    Provides session lifecycle hooks:
    - on_session_start(session_id): Called once when a new session is created
    - on_session_end(session_id): Called once when a session ends (crash, close, or shutdown)

    All MCP connections (stdio, SSE, HTTP) are managed by ClientSessionGroup and
    cleaned up automatically when the session ends.
    """

    def __init__(self, vmcp_managers_ref: dict, *args, **kwargs):
        """
        Initialize with a reference to the VMCPServer's _vmcp_managers dict.
        This allows us to cleanup all session-specific MCP client connections.
        """
        super().__init__(*args, **kwargs)
        self._vmcp_managers_ref = vmcp_managers_ref

    async def on_session_start(self, session_id: str) -> None:
        """
        Called once when a new MCP session is created.
        Override this to initialize session-specific resources.
        """
        logger.info(f"[VMCP SESSION_START] New session created: {session_id[:16]}...")

    async def on_session_end(self, session_id: str) -> None:
        """
        Called once when an MCP session ends (crash, explicit close, or shutdown).
        Cleans up all MCP connections (stdio, SSE, HTTP) for this session.
        """
        logger.info(f"[VMCP SESSION_END] Session ending: {session_id[:16]}...")

        try:
            if session_id in self._vmcp_managers_ref:
                vmcp_manager = self._vmcp_managers_ref[session_id]
                if hasattr(vmcp_manager, 'mcp_client_manager') and vmcp_manager.mcp_client_manager:
                    # stop() cleans up all connections (stdio, SSE, HTTP) managed by ClientSessionGroup
                    cleaned = await vmcp_manager.mcp_client_manager.stop()
                    logger.info(f"[SESSION_END] Cleaned up {cleaned} MCP connections for session {session_id[:16]}...")
                # Remove vmcp_manager from cache
                del self._vmcp_managers_ref[session_id]
                logger.info(f"[SESSION_END] Removed VMCPConfigManager for session {session_id[:16]}...")
        except Exception as e:
            logger.warning(f"[SESSION_END] Error cleaning up session {session_id[:16]}...: {e}")

    @asynccontextmanager
    async def run(self) -> AsyncIterator[None]:
        """
        Run the session manager with proper lifecycle management.

        Note: Per-session cleanup is handled by on_session_end().
        This only handles fallback cleanup for any remaining sessions on shutdown.
        """
        # Thread-safe check to ensure run() is only called once
        async with self._run_lock:
            if self._has_started:
                raise RuntimeError(
                    "VMCPSessionManager .run() can only be called "
                    "once per instance. Create a new instance if you need to run again."
                )
            self._has_started = True

        async with anyio.create_task_group() as tg:
            self._task_group = tg
            logger.info("VMCPSessionManager started")
            try:
                yield  # Let the application run
            finally:
                logger.info("VMCPSessionManager shutting down")

                # Fallback cleanup for any sessions that weren't cleaned up via on_session_end
                # (e.g., if shutdown happens before sessions end gracefully)
                remaining_sessions = list(self._vmcp_managers_ref.keys())
                if remaining_sessions:
                    logger.info(f"Fallback cleanup for {len(remaining_sessions)} remaining sessions...")
                    for session_id in remaining_sessions:
                        try:
                            await self.on_session_end(session_id)
                        except Exception as e:
                            logger.warning(f"Error in fallback cleanup for session {session_id[:16]}...: {e}")

                # Cancel task group to stop all spawned tasks
                tg.cancel_scope.cancel()
                self._task_group = None
                self._server_instances.clear()
                logger.info("VMCPSessionManager shutdown complete")

    async def _handle_stateful_request(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """
        Process request in stateful mode with session lifecycle hooks.

        This is a full override of the parent implementation to add:
        - on_session_start() callback when new sessions are created
        - on_session_end() callback when sessions end (via wrapped run_server task)
        """
        request = Request(scope, receive)
        request_mcp_session_id = request.headers.get(MCP_SESSION_ID_HEADER)

        # Existing session - route to existing transport
        if request_mcp_session_id is not None and request_mcp_session_id in self._server_instances:
            transport = self._server_instances[request_mcp_session_id]
            logger.debug(f"Routing request to existing session {request_mcp_session_id[:16]}...")
            await transport.handle_request(scope, receive, send)
            return

        # New session - create transport and start server
        if request_mcp_session_id is None:
            logger.debug("Creating new session...")
            async with self._session_creation_lock:
                new_session_id = uuid4().hex
                http_transport = StreamableHTTPServerTransport(
                    mcp_session_id=new_session_id,
                    is_json_response_enabled=self.json_response,
                    event_store=self.event_store,
                    security_settings=self.security_settings,
                )

                assert http_transport.mcp_session_id is not None
                self._server_instances[http_transport.mcp_session_id] = http_transport
                logger.info(f"Created new transport with session ID: {new_session_id[:16]}...")

                # Call session start hook
                await self.on_session_start(new_session_id)

                # Define the server runner with session end hook
                async def run_server(*, task_status: TaskStatus[None] = anyio.TASK_STATUS_IGNORED) -> None:
                    async with http_transport.connect() as streams:
                        read_stream, write_stream = streams
                        task_status.started()
                        try:
                            await self.app.run(
                                read_stream,
                                write_stream,
                                self.app.create_initialization_options(),
                                stateless=False,
                            )
                        except Exception as e:
                            logger.error(
                                f"Session {http_transport.mcp_session_id} crashed: {e}",
                                exc_info=True,
                            )
                        finally:
                            # Call session end hook
                            if http_transport.mcp_session_id:
                                await self.on_session_end(http_transport.mcp_session_id)

                            # Remove from instances if not terminated
                            if (
                                http_transport.mcp_session_id
                                and http_transport.mcp_session_id in self._server_instances
                                and not http_transport.is_terminated
                            ):
                                logger.info(
                                    f"Cleaning up session {http_transport.mcp_session_id[:16]}... from active instances."
                                )
                                del self._server_instances[http_transport.mcp_session_id]

                # Start the server task
                assert self._task_group is not None
                await self._task_group.start(run_server)

                # Handle the HTTP request
                await http_transport.handle_request(scope, receive, send)
        else:
            # Invalid session ID (client provided non-existent session)
            response = Response(
                "Bad Request: No valid session ID provided",
                status_code=HTTPStatus.BAD_REQUEST,
            )
            await response(scope, receive, send)
