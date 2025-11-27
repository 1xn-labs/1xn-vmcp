"""
Custom Session Manager for vMCP with MCP connection cleanup support.

Extends StreamableHTTPSessionManager to handle proper cleanup of all MCP
server connections (stdio, SSE, HTTP) when sessions end.

This module is responsible for:
- Session lifecycle management (start, end)
- VMCPConfigManager creation and caching per session
- MCP connection cleanup when sessions end
- TTL-based session expiration for disconnected clients
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Optional
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

from vmcp.config import settings
from vmcp.utilities.logging import get_logger
from vmcp.vmcps.vmcp_config_manager import VMCPConfigManager

logger = get_logger("VMCPSessionManager")


@dataclass
class SessionEntry:
    """Tracks a session with its manager and last access time for TTL."""
    manager: VMCPConfigManager
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class VMCPSessionManager(StreamableHTTPSessionManager):
    """
    Custom session manager that handles MCP connection cleanup when sessions end.

    Provides session lifecycle hooks:
    - on_session_start(session_id): Called once when a new session is created
    - on_session_end(session_id): Called once when a session ends (crash, close, or shutdown)

    All MCP connections (stdio, SSE, HTTP) are managed by ClientSessionGroup and
    cleaned up automatically when the session ends.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize session manager with TTL-based cleanup.
        """
        super().__init__(*args, **kwargs)
        self._sessions: dict[str, SessionEntry] = {}
        self._cleanup_task: Optional[TaskStatus] = None
        self._shutdown_event: Optional[anyio.Event] = None
        logger.info(f"[VMCPSessionManager] Initialized (TTL={settings.ttl_seconds}s, cleanup_interval={settings.cleanup_every_seconds}s)")

    def get_manager(self, session_id: str) -> Optional[VMCPConfigManager]:
        """
        Get the cached VMCPConfigManager for a session and update last_accessed.

        Args:
            session_id: The MCP session ID

        Returns:
            The cached VMCPConfigManager or None if not found
        """
        entry = self._sessions.get(session_id)
        if entry:
            entry.last_accessed = datetime.now(timezone.utc)
            return entry.manager
        return None

    def create_manager(self, session_id: str, user_id: str, vmcp_name: str) -> VMCPConfigManager:
        """
        Create and cache a VMCPConfigManager for a session.

        Args:
            session_id: The MCP session ID
            user_id: The user ID (string)
            vmcp_name: The vMCP name to resolve to UUID

        Returns:
            The newly created VMCPConfigManager
        """
        from vmcp.storage.base import StorageBase

        # Convert user_id to integer for storage operations
        user_id_int = int(user_id) if isinstance(user_id, str) else user_id

        # Resolve vmcp_name to UUID
        vmcp_id = None
        if vmcp_name:
            logger.debug(f"[VMCPSessionManager] Resolving vmcp_name '{vmcp_name}' to UUID for user '{user_id_int}'")
            storage = StorageBase(user_id=user_id_int)
            vmcp_id = storage.find_vmcp_name(vmcp_name)
            if vmcp_id:
                logger.debug(f"[VMCPSessionManager] Resolved '{vmcp_name}' -> '{vmcp_id}'")
            else:
                logger.warning(f"[VMCPSessionManager] Could not find vMCP UUID for name: {vmcp_name}")

        # Create the manager
        manager = VMCPConfigManager(
            user_id=str(user_id),
            vmcp_id=vmcp_id,
            mcp_keep_alive=True, # Enable MCP connection keep-alive for vMCP sessions
        )

        # Cache it with TTL tracking
        self._sessions[session_id] = SessionEntry(manager=manager)
        logger.info(f"[VMCPSessionManager] Created and cached VMCPConfigManager for session {session_id[:16]}...")

        return manager

    async def on_session_start(self, session_id: str) -> None:
        """
        Called once when a new MCP session is created.
        Override this to initialize session-specific resources.
        """
        logger.info(f"[VMCPSessionManager] Session started: {session_id[:16]}...")

    async def on_session_end(self, session_id: str) -> None:
        """
        Called once when an MCP session ends (crash, explicit close, shutdown, or TTL expiration).
        Cleans up all MCP connections (stdio, SSE, HTTP) for this session.
        """
        logger.info(f"[VMCPSessionManager] Session ending: {session_id[:16]}...")

        try:
            entry = self._sessions.get(session_id)
            if entry:
                if hasattr(entry.manager, 'mcp_client_manager') and entry.manager.mcp_client_manager:
                    # stop() cleans up all connections (stdio, SSE, HTTP) managed by ClientSessionGroup
                    cleaned = await entry.manager.mcp_client_manager.stop()
                    logger.info(f"[VMCPSessionManager] Cleaned up {cleaned} MCP connections for session {session_id[:16]}...")
                # Remove session from cache
                del self._sessions[session_id]
                logger.info(f"[VMCPSessionManager] Removed session {session_id[:16]}...")
        except Exception as e:
            logger.warning(f"[VMCPSessionManager] Error cleaning up session {session_id[:16]}...: {e}")

    async def _cleanup_expired_sessions(self) -> None:
        """
        Background task that periodically checks for and cleans up expired sessions.
        Sessions that haven't been accessed within SESSION_TTL are considered expired.
        """
        ttl = timedelta(seconds=settings.ttl_seconds)
        interval = settings.cleanup_every_seconds

        logger.info(f"[VMCPSessionManager] TTL cleanup task started (TTL={ttl}, interval={interval}s)")

        while True:
            try:
                await anyio.sleep(interval)

                now = datetime.now(timezone.utc)
                expired_sessions = [
                    session_id for session_id, entry in self._sessions.items()
                    if now - entry.last_accessed > ttl
                ]

                if expired_sessions:
                    logger.info(f"[VMCPSessionManager] Found {len(expired_sessions)} expired sessions to clean up")
                    for session_id in expired_sessions:
                        try:
                            logger.info(f"[VMCPSessionManager] TTL expired for session {session_id[:16]}...")
                            await self.on_session_end(session_id)
                        except Exception as e:
                            logger.warning(f"[VMCPSessionManager] Error cleaning up expired session {session_id[:16]}...: {e}")

            except anyio.get_cancelled_exc_class():
                logger.info("[VMCPSessionManager] TTL cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"[VMCPSessionManager] Error in TTL cleanup task: {e}")
                # Continue running despite errors

    @asynccontextmanager
    async def run(self) -> AsyncIterator[None]:
        """
        Run the session manager with proper lifecycle management.

        Starts a background task to clean up expired sessions based on TTL.
        Per-session cleanup is also handled by on_session_end().
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

            # Start the TTL cleanup background task
            tg.start_soon(self._cleanup_expired_sessions)

            logger.info("[VMCPSessionManager] Started with TTL cleanup task")
            try:
                yield  # Let the application run
            finally:
                logger.info("[VMCPSessionManager] Shutting down...")

                # Fallback cleanup for any remaining sessions
                remaining_sessions = list(self._sessions.keys())
                if remaining_sessions:
                    logger.info(f"[VMCPSessionManager] Fallback cleanup for {len(remaining_sessions)} remaining sessions...")
                    for session_id in remaining_sessions:
                        try:
                            await self.on_session_end(session_id)
                        except Exception as e:
                            logger.warning(f"[VMCPSessionManager] Error in fallback cleanup for session {session_id[:16]}...: {e}")

                # Cancel task group to stop all spawned tasks (including TTL cleanup)
                tg.cancel_scope.cancel()
                self._task_group = None
                self._server_instances.clear()
                logger.info("[VMCPSessionManager] Shutdown complete")

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
