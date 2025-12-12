"""
Terminal Session Manager for vMCP

Manages persistent PTY terminal sessions that can be reconnected to.
Sessions are keyed by (vmcp_id, user_id) and persist across WebSocket disconnects.
"""

import os
import pty
import struct
import fcntl
import termios
import select
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from uuid import uuid4

from vmcp.utilities.logging import get_logger
from sandbox_runtime import SandboxManager
from sandbox_runtime.config.schemas import SandboxRuntimeConfig

logger = get_logger(__name__)


@dataclass
class TerminalSession:
    """Represents a persistent terminal session."""
    
    session_id: str
    vmcp_id: str
    user_id: str
    master_fd: int
    slave_fd: int
    pid: int
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active_connections: int = 0  # Number of active WebSocket connections
    
    def is_alive(self) -> bool:
        """Check if the terminal process is still alive."""
        try:
            # Check if process exists (doesn't kill it)
            os.kill(self.pid, 0)
            return True
        except (ProcessLookupError, OSError):
            return False
    
    def update_access(self):
        """Update last accessed timestamp."""
        self.last_accessed = datetime.now(timezone.utc)


class TerminalSessionManager:
    """
    Manages persistent terminal sessions.
    
    Sessions persist across WebSocket disconnects and can be reconnected to.
    Sessions are automatically cleaned up after a period of inactivity.
    """
    
    def __init__(self, session_timeout_seconds: int = 3600, cleanup_interval_seconds: int = 300):
        """
        Initialize the terminal session manager.
        
        Args:
            session_timeout_seconds: Time in seconds before inactive sessions are cleaned up (default: 1 hour)
            cleanup_interval_seconds: Interval between cleanup runs (default: 5 minutes)
        """
        self._sessions: Dict[str, TerminalSession] = {}  # session_id -> TerminalSession
        self._session_keys: Dict[Tuple[str, str], str] = {}  # (vmcp_id, user_id) -> session_id
        self._session_timeout = session_timeout_seconds
        self._cleanup_interval = cleanup_interval_seconds
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        logger.info(f"TerminalSessionManager initialized (timeout={session_timeout_seconds}s, cleanup_interval={cleanup_interval_seconds}s)")
    
    def _get_session_key(self, vmcp_id: str, user_id: str) -> Tuple[str, str]:
        """Get the session key for a vmcp_id and user_id."""
        return (vmcp_id, user_id)
    
    async def get_or_create_session(
        self,
        vmcp_id: str,
        user_id: str,
        sandbox_path: str
    ) -> TerminalSession:
        """
        Get an existing session or create a new one.
        
        Args:
            vmcp_id: The vMCP ID
            user_id: The user ID
            sandbox_path: Path to the sandbox directory
            
        Returns:
            TerminalSession instance
        """
        async with self._lock:
            session_key = self._get_session_key(vmcp_id, user_id)
            
            # Check if session exists
            if session_key in self._session_keys:
                session_id = self._session_keys[session_key]
                session = self._sessions.get(session_id)
                
                if session and session.is_alive():
                    # Session exists and is alive, update access time
                    session.update_access()
                    logger.info(f"Reusing existing terminal session {session_id} for vMCP {vmcp_id}")
                    return session
                else:
                    # Session exists but process is dead, remove it
                    logger.info(f"Terminal session {session_id} process is dead, removing")
                    if session:
                        await self._cleanup_session(session)
                    del self._session_keys[session_key]
                    if session_id in self._sessions:
                        del self._sessions[session_id]
            
            # Create new session
            session_id = str(uuid4())
            logger.info(f"Creating new terminal session {session_id} for vMCP {vmcp_id}")
            
            # Initialize sandbox config before forking
            sandbox_dir_str = str(sandbox_path)
            allow_read_paths = [
                sandbox_dir_str,
                "/usr/lib",
                "/System/Library",
                "/Library/Frameworks",
                "/usr/bin",
                "/bin",
                "/lib",
                "/lib64",
            ]
            
            sandbox_config = SandboxRuntimeConfig.from_json({
                "network": {
                    "allowedDomains": [],  # Empty = allow all network access
                    "deniedDomains": []
                },
                "filesystem": {
                    "allowRead": allow_read_paths,
                    "allowWrite": [sandbox_dir_str],
                    "denyWrite": []
                }
            })
            
            # Initialize sandbox (this is async, so we need to await it)
            # Sandboxing is mandatory - fail if initialization fails
            await SandboxManager.initialize(sandbox_config)
            
            # Create PTY
            master_fd, slave_fd = pty.openpty()
            
            # Set terminal size (default 80x24)
            try:
                winsize = struct.pack('HHHH', 24, 80, 0, 0)
                fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)
            except Exception:
                pass
            
            # Spawn shell in sandbox
            pid = os.fork()
            if pid == 0:
                # Child process
                os.setsid()
                os.close(master_fd)
                os.dup2(slave_fd, 0)
                os.dup2(slave_fd, 1)
                os.dup2(slave_fd, 2)
                os.close(slave_fd)
                
                # Change to sandbox directory
                os.chdir(sandbox_path)
                
                # Activate venv if it exists
                venv_bin = os.path.join(sandbox_path, ".venv", "bin")
                if os.path.exists(venv_bin):
                    current_path = os.environ.get('PATH', '')
                    os.environ['PATH'] = f"{venv_bin}:{current_path}"
                
                # Wrap bash command with sandbox - sandboxing is mandatory
                # Use asyncio.run() since we're in a fresh child process
                sandboxed_cmd = asyncio.run(
                    SandboxManager.wrap_with_sandbox(
                        "bash",
                        bin_shell="bash",
                        sandbox_dir=sandbox_dir_str
                    )
                )
                # Execute the sandboxed command
                # The wrapped command will be something like "bwrap ... bash" or "sandbox-exec ... bash"
                os.execvp('sh', ['sh', '-c', sandboxed_cmd])
            else:
                # Parent process
                os.close(slave_fd)
                
                # Set non-blocking mode
                fcntl.fcntl(master_fd, fcntl.F_SETFL, os.O_NONBLOCK)
                
                # Create session
                session = TerminalSession(
                    session_id=session_id,
                    vmcp_id=vmcp_id,
                    user_id=user_id,
                    master_fd=master_fd,
                    slave_fd=slave_fd,
                    pid=pid
                )
                
                # Store session
                self._sessions[session_id] = session
                self._session_keys[session_key] = session_id
                
                # Start cleanup task if not already running
                if self._cleanup_task is None or self._cleanup_task.done():
                    self._cleanup_task = asyncio.create_task(self._cleanup_loop())
                
                return session
    
    async def get_session(self, vmcp_id: str, user_id: str) -> Optional[TerminalSession]:
        """
        Get an existing session without creating a new one.
        
        Args:
            vmcp_id: The vMCP ID
            user_id: The user ID
            
        Returns:
            TerminalSession if found, None otherwise
        """
        async with self._lock:
            session_key = self._get_session_key(vmcp_id, user_id)
            if session_key in self._session_keys:
                session_id = self._session_keys[session_key]
                session = self._sessions.get(session_id)
                if session and session.is_alive():
                    session.update_access()
                    return session
            return None
    
    def register_connection(self, session_id: str) -> bool:
        """
        Register a new WebSocket connection to a session.
        
        Returns:
            True if this is a new connection, False if reconnecting
        """
        if session_id in self._sessions:
            was_reconnecting = self._sessions[session_id].active_connections > 0
            self._sessions[session_id].active_connections += 1
            self._sessions[session_id].update_access()
            return not was_reconnecting
        return True
    
    def unregister_connection(self, session_id: str):
        """Unregister a WebSocket connection from a session."""
        if session_id in self._sessions:
            self._sessions[session_id].active_connections = max(0, self._sessions[session_id].active_connections - 1)
            self._sessions[session_id].update_access()
    
    async def _cleanup_session(self, session: TerminalSession):
        """Clean up a terminal session."""
        try:
            # Close file descriptors
            try:
                os.close(session.master_fd)
            except OSError:
                pass

            # Kill the process with timeout to avoid hanging
            try:
                if session.is_alive():
                    os.kill(session.pid, 15)  # SIGTERM
                    # Wait for process with timeout to avoid blocking
                    try:
                        # Use asyncio to wait with timeout
                        import signal as signal_module
                        for _ in range(10):  # Check up to 10 times (1 second total)
                            try:
                                # Non-blocking check if process is still alive
                                os.kill(session.pid, 0)  # Check if process exists
                                await asyncio.sleep(0.1)  # Wait 100ms
                            except ProcessLookupError:
                                # Process is dead
                                break
                            except OSError:
                                # Process is dead
                                break
                        else:
                            # Process still alive after timeout, force kill
                            try:
                                os.kill(session.pid, 9)  # SIGKILL
                                await asyncio.sleep(0.1)
                            except (ProcessLookupError, OSError):
                                pass  # Process already dead
                    except ChildProcessError:
                        pass
            except ProcessLookupError:
                pass  # Process already dead
            except Exception as e:
                logger.warning(f"Error killing terminal process {session.pid}: {e}")

            logger.info(f"Cleaned up terminal session {session.session_id}")
        except Exception as e:
            logger.error(f"Error cleaning up terminal session {session.session_id}: {e}")
    
    async def _cleanup_loop(self):
        """Background task to clean up inactive sessions."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_inactive_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in terminal session cleanup loop: {e}")
    
    async def _cleanup_inactive_sessions(self):
        """Clean up sessions that have been inactive for too long."""
        async with self._lock:
            now = datetime.now(timezone.utc)
            sessions_to_remove = []
            
            for session_id, session in list(self._sessions.items()):
                # Check if session is inactive
                time_since_access = (now - session.last_accessed).total_seconds()
                
                # Remove if:
                # 1. Inactive for too long AND no active connections, OR
                # 2. Process is dead
                if (time_since_access > self._session_timeout and session.active_connections == 0) or not session.is_alive():
                    sessions_to_remove.append(session)
            
            for session in sessions_to_remove:
                session_key = self._get_session_key(session.vmcp_id, session.user_id)
                await self._cleanup_session(session)
                del self._sessions[session.session_id]
                if session_key in self._session_keys:
                    del self._session_keys[session_key]
            
            if sessions_to_remove:
                logger.info(f"Cleaned up {len(sessions_to_remove)} inactive terminal sessions")
    
    async def close_session(self, vmcp_id: str, user_id: str):
        """Explicitly close a terminal session."""
        async with self._lock:
            session_key = self._get_session_key(vmcp_id, user_id)
            if session_key in self._session_keys:
                session_id = self._session_keys[session_key]
                session = self._sessions.get(session_id)
                if session:
                    await self._cleanup_session(session)
                    del self._sessions[session_id]
                    del self._session_keys[session_key]
                    logger.info(f"Closed terminal session {session_id} for vMCP {vmcp_id}")


# Global instance
_terminal_session_manager: Optional[TerminalSessionManager] = None


def get_terminal_session_manager() -> TerminalSessionManager:
    """Get the global terminal session manager instance."""
    global _terminal_session_manager
    if _terminal_session_manager is None:
        _terminal_session_manager = TerminalSessionManager()
    return _terminal_session_manager

