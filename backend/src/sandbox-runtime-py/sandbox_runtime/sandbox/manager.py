"""Sandbox manager that handles both network and filesystem restrictions."""

import asyncio
import copy
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional

from sandbox_runtime.config.schemas import (
    RipgrepConfig,
    SandboxRuntimeConfig,
)
from sandbox_runtime.network.bridge import (
    LinuxNetworkBridgeContext,
    initialize_linux_network_bridge,
)
from sandbox_runtime.network.http_proxy import (
    HttpProxyServer,
    create_http_proxy_server,
)
from sandbox_runtime.network.socks_proxy import (
    SocksProxyWrapper,
    create_socks_proxy_server,
)
from sandbox_runtime.sandbox.linux_utils import (
    has_linux_sandbox_dependencies_sync,
    wrap_command_with_sandbox_linux,
)
from sandbox_runtime.sandbox.macos_utils import (
    start_macos_sandbox_log_monitor,
    wrap_command_with_sandbox_macos,
)
from sandbox_runtime.sandbox.utils import (
    contains_glob_chars,
    get_default_write_paths,
    remove_trailing_glob_suffix,
)
from sandbox_runtime.sandbox.violation_store import SandboxViolationStore
from sandbox_runtime.utils.debug import log_for_debugging
from sandbox_runtime.utils.platform import Platform, get_platform
from sandbox_runtime.utils.ripgrep import has_ripgrep_sync

# Type aliases for internal configs
FsReadRestrictionConfig = dict[str, list[str]]
FsWriteRestrictionConfig = dict[str, list[str]]
NetworkRestrictionConfig = dict[str, Optional[list[str]]]
SandboxAskCallback = Callable[[dict[str, Any]], bool | asyncio.Future[bool]]

# ============================================================================
# Private Module State
# ============================================================================

_config: Optional[SandboxRuntimeConfig] = None
_http_proxy_server: Optional[HttpProxyServer] = None
_socks_proxy_server: Optional[SocksProxyWrapper] = None
_manager_context: Optional[dict] = None
_initialization_promise: Optional[asyncio.Future] = None
_cleanup_registered = False
_log_monitor_shutdown: Optional[Callable[[], None]] = None
_sandbox_violation_store = SandboxViolationStore()


# ============================================================================
# Private Helper Functions
# ============================================================================


def _register_cleanup() -> None:
    """Register cleanup handlers for process exit.
    
    Note: Signal handlers are NOT registered here to avoid interfering with
    FastAPI/uvicorn's signal handling. Cleanup should be handled by the
    application's lifespan shutdown handler instead.
    """
    global _cleanup_registered
    if _cleanup_registered:
        return

    # Only register atexit handler as a fallback for non-FastAPI contexts
    # Signal handlers are skipped to let FastAPI handle SIGINT/SIGTERM properly
    def cleanup_handler():
        try:
            # Check if there's already an event loop running
            try:
                loop = asyncio.get_running_loop()
                # If we're in an async context, skip - let app handle it
                if loop.is_running():
                    log_for_debugging("Cleanup skipped - event loop is running (cleanup should be handled by app shutdown)", {"level": "debug"})
                    return
            except RuntimeError:
                # No event loop running, safe to use asyncio.run()
                pass

            # Only use asyncio.run() if no event loop exists
            try:
                asyncio.run(reset())
            except RuntimeError as e:
                # Event loop already exists - this is expected in some contexts
                # The app's lifespan handler should handle cleanup instead
                log_for_debugging(f"Cleanup skipped - event loop conflict (expected during app shutdown): {e}", {"level": "debug"})
        except Exception as e:
            log_for_debugging(f"Cleanup failed in register_cleanup {e}", {"level": "error"})

    # Only register atexit, NOT signal handlers (let FastAPI handle signals)
    import atexit
    atexit.register(cleanup_handler)
    _cleanup_registered = True


def _matches_domain_pattern(hostname: str, pattern: str) -> bool:
    """Check if hostname matches domain pattern (supports wildcards like *.example.com)."""
    if pattern.startswith("*."):
        base_domain = pattern[2:]  # Remove '*.'
        return hostname.lower().endswith("." + base_domain.lower())

    # Exact match for non-wildcard patterns
    return hostname.lower() == pattern.lower()


async def _filter_network_request(
    port: int,
    host: str,
    sandbox_ask_callback: Optional[SandboxAskCallback] = None,
) -> bool:
    """Filter network request based on config."""
    if not _config:
        log_for_debugging("No config available, denying network request")
        return False

    # Check denied domains first
    for denied_domain in _config.network.denied_domains:
        if _matches_domain_pattern(host, denied_domain):
            log_for_debugging(f"Denied by config rule: {host}:{port}")
            return False

    # If allowed_domains is empty, allow all (no network restrictions)
    if len(_config.network.allowed_domains) == 0:
        log_for_debugging(f"Allowed (no network restrictions): {host}:{port}")
        return True

    # Check allowed domains
    for allowed_domain in _config.network.allowed_domains:
        if _matches_domain_pattern(host, allowed_domain):
            log_for_debugging(f"Allowed by config rule: {host}:{port}")
            return True

    # No matching rules - ask user or deny
    if not sandbox_ask_callback:
        log_for_debugging(f"No matching config rule, denying: {host}:{port}")
        return False

    log_for_debugging(f"No matching config rule, asking user: {host}:{port}")
    try:
        if asyncio.iscoroutinefunction(sandbox_ask_callback):
            user_allowed = await sandbox_ask_callback({"host": host, "port": port})
        else:
            user_allowed = sandbox_ask_callback({"host": host, "port": port})

        if user_allowed:
            log_for_debugging(f"User allowed: {host}:{port}")
            return True
        else:
            log_for_debugging(f"User denied: {host}:{port}")
            return False
    except Exception as error:
        log_for_debugging(f"Error in permission callback: {error}", {"level": "error"})
        return False


async def _start_http_proxy_server(
    sandbox_ask_callback: Optional[SandboxAskCallback] = None,
) -> int:
    """Start HTTP proxy server and return the port."""
    global _http_proxy_server

    async def filter_func(port: int, hostname: str) -> bool:
        return await _filter_network_request(port, hostname, sandbox_ask_callback)

    _http_proxy_server = create_http_proxy_server(filter_func)
    port = await _http_proxy_server.listen("127.0.0.1", 0)
    _http_proxy_server.unref()
    return port


async def _start_socks_proxy_server(
    sandbox_ask_callback: Optional[SandboxAskCallback] = None,
) -> int:
    """Start SOCKS5 proxy server and return the port."""
    global _socks_proxy_server

    async def filter_func(port: int, hostname: str) -> bool:
        return await _filter_network_request(port, hostname, sandbox_ask_callback)

    _socks_proxy_server = create_socks_proxy_server(filter_func)
    port = await _socks_proxy_server.listen(0, "127.0.0.1")
    _socks_proxy_server.unref()
    return port


# ============================================================================
# Public Module Functions
# ============================================================================


async def initialize(
    runtime_config: SandboxRuntimeConfig,
    sandbox_ask_callback: Optional[SandboxAskCallback] = None,
    enable_log_monitor: bool = False,
) -> None:
    """Initialize the sandbox manager with configuration."""
    global _config, _initialization_promise, _manager_context, _log_monitor_shutdown

    # Return if already initializing
    if _initialization_promise:
        await _initialization_promise
        return

    # Store config
    _config = runtime_config

    # Check dependencies
    if not check_dependencies():
        platform = get_platform()
        error_message = "Sandbox dependencies are not available on this system."

        if platform == "linux":
            error_message += " Required: ripgrep (rg), bubblewrap (bwrap), and socat."
        elif platform == "macos":
            error_message += " Required: ripgrep (rg)."
        else:
            error_message += f" Platform '{platform}' is not supported."

        raise RuntimeError(error_message)

    # Start log monitor for macOS if enabled
    if enable_log_monitor and get_platform() == "macos":
        ignore_violations_dict = (
            dict(_config.ignore_violations) if _config.ignore_violations else None
        )
        _log_monitor_shutdown = start_macos_sandbox_log_monitor(
            _sandbox_violation_store.add_violation,
            ignore_violations_dict,
        )
        log_for_debugging("Started macOS sandbox log monitor")

    # Register cleanup handlers
    _register_cleanup()

    # Initialize network infrastructure
    async def _do_initialize() -> dict[str, Any]:
        try:
            # Conditionally start proxy servers based on config
            http_proxy_port: int
            if _config.network.http_proxy_port is not None:
                # Use external HTTP proxy
                http_proxy_port = _config.network.http_proxy_port
                log_for_debugging(f"Using external HTTP proxy on port {http_proxy_port}")
            else:
                # Start local HTTP proxy
                http_proxy_port = await _start_http_proxy_server(sandbox_ask_callback)

            socks_proxy_port: int
            if _config.network.socks_proxy_port is not None:
                # Use external SOCKS proxy
                socks_proxy_port = _config.network.socks_proxy_port
                log_for_debugging(f"Using external SOCKS proxy on port {socks_proxy_port}")
            else:
                # Start local SOCKS proxy
                socks_proxy_port = await _start_socks_proxy_server(sandbox_ask_callback)

            # Initialize platform-specific infrastructure
            linux_bridge: Optional[LinuxNetworkBridgeContext] = None
            if get_platform() == "linux":
                linux_bridge = await initialize_linux_network_bridge(
                    http_proxy_port,
                    socks_proxy_port,
                )

            context = {
                "http_proxy_port": http_proxy_port,
                "socks_proxy_port": socks_proxy_port,
                "linux_bridge": linux_bridge,
            }
            return context
        except Exception as error:
            # Clear state on error so initialization can be retried
            global _initialization_promise, _manager_context
            _initialization_promise = None
            _manager_context = None
            await reset()
            raise error

    _initialization_promise = asyncio.create_task(_do_initialize())
    _manager_context = await _initialization_promise
    log_for_debugging("Network infrastructure initialized")


def is_supported_platform(platform: Platform) -> bool:
    """Check if platform is supported."""
    supported_platforms: list[Platform] = ["macos", "linux"]
    return platform in supported_platforms


def is_sandboxing_enabled() -> bool:
    """Check if sandboxing is enabled."""
    return _config is not None


def check_dependencies(
    ripgrep_config: Optional[RipgrepConfig] = None,
) -> bool:
    """Check if all sandbox dependencies are available."""
    platform = get_platform()

    # Check platform support
    if not is_supported_platform(platform):
        return False

    # Determine which ripgrep to check
    rg_to_check = ripgrep_config or (_config.ripgrep if _config else None)

    # Check ripgrep - only check 'rg' if no custom command is configured
    has_custom_ripgrep = rg_to_check and rg_to_check.command != "rg"
    if not has_custom_ripgrep:
        if not has_ripgrep_sync():
            return False

    # Platform-specific dependency checks
    if platform == "linux":
        allow_all_unix_sockets = (
            _config.network.allow_all_unix_sockets
            if _config and _config.network.allow_all_unix_sockets is not None
            else False
        )
        return has_linux_sandbox_dependencies_sync(allow_all_unix_sockets)

    # macOS only needs ripgrep (already checked above)
    return True


def get_fs_read_config() -> FsReadRestrictionConfig:
    """Get filesystem read restriction config."""
    if not _config:
        return {"denyOnly": []}

    # Filter out glob patterns on Linux
    deny_paths = [
        remove_trailing_glob_suffix(path)
        for path in _config.filesystem.deny_read
    ]
    deny_paths = [
        path
        for path in deny_paths
        if not (get_platform() == "linux" and contains_glob_chars(path))
    ]

    return {"denyOnly": deny_paths}


def get_fs_write_config() -> FsWriteRestrictionConfig:
    """Get filesystem write restriction config."""
    if not _config:
        return {"allowOnly": get_default_write_paths(), "denyWithinAllow": []}

    # Filter out glob patterns on Linux
    allow_paths = [
        remove_trailing_glob_suffix(path)
        for path in _config.filesystem.allow_write
    ]
    allow_paths = [
        path
        for path in allow_paths
        if not (get_platform() == "linux" and contains_glob_chars(path))
    ]

    deny_paths = [
        remove_trailing_glob_suffix(path)
        for path in _config.filesystem.deny_write
    ]
    deny_paths = [
        path
        for path in deny_paths
        if not (get_platform() == "linux" and contains_glob_chars(path))
    ]

    # Build allowOnly list: default paths + configured allow paths
    allow_only = get_default_write_paths() + allow_paths

    return {"allowOnly": allow_only, "denyWithinAllow": deny_paths}


def get_network_restriction_config() -> NetworkRestrictionConfig:
    """Get network restriction config."""
    if not _config:
        return {}

    allowed_hosts = _config.network.allowed_domains
    denied_hosts = _config.network.denied_domains

    result: dict[str, Optional[list[str]]] = {}
    if allowed_hosts:
        result["allowedHosts"] = allowed_hosts
    if denied_hosts:
        result["deniedHosts"] = denied_hosts

    return result


def get_allow_unix_sockets() -> Optional[list[str]]:
    """Get allowed Unix socket paths."""
    return _config.network.allow_unix_sockets if _config else None


def get_allow_all_unix_sockets() -> Optional[bool]:
    """Get allow all Unix sockets flag."""
    return _config.network.allow_all_unix_sockets if _config else None


def get_allow_local_binding() -> Optional[bool]:
    """Get allow local binding flag."""
    return _config.network.allow_local_binding if _config else None


def get_ignore_violations() -> Optional[dict[str, list[str]]]:
    """Get ignore violations config."""
    if _config and _config.ignore_violations:
        return dict(_config.ignore_violations)
    return None


def get_enable_weaker_nested_sandbox() -> Optional[bool]:
    """Get enable weaker nested sandbox flag."""
    return _config.enable_weaker_nested_sandbox if _config else None


def get_ripgrep_config() -> RipgrepConfig:
    """Get ripgrep config."""
    if _config and _config.ripgrep:
        return _config.ripgrep
    return RipgrepConfig(command="rg")


def get_proxy_port() -> Optional[int]:
    """Get HTTP proxy port."""
    return _manager_context.get("http_proxy_port") if _manager_context else None


def get_socks_proxy_port() -> Optional[int]:
    """Get SOCKS proxy port."""
    return _manager_context.get("socks_proxy_port") if _manager_context else None


def get_linux_http_socket_path() -> Optional[str]:
    """Get Linux HTTP socket path."""
    if _manager_context and _manager_context.get("linux_bridge"):
        return _manager_context["linux_bridge"].http_socket_path
    return None


def get_linux_socks_socket_path() -> Optional[str]:
    """Get Linux SOCKS socket path."""
    if _manager_context and _manager_context.get("linux_bridge"):
        return _manager_context["linux_bridge"].socks_socket_path
    return None


async def wait_for_network_initialization() -> bool:
    """Wait for network initialization to complete."""
    if not _config:
        return False
    if _initialization_promise:
        try:
            await _initialization_promise
            return True
        except Exception:
            return False
    return _manager_context is not None


async def wrap_with_sandbox(
    command: str,
    bin_shell: Optional[str] = None,
    custom_config: Optional[dict] = None,
    sandbox_dir: Optional[str] = None,
) -> str:
    """Wrap a command with sandbox restrictions."""
    # If no config, return command as-is
    if not _config:
        return command

    platform = get_platform()

    # Get configs - use custom if provided, otherwise fall back to main config
    if custom_config:
        user_allow_write = custom_config.get("filesystem", {}).get("allowWrite", []) or []
        user_deny_write = custom_config.get("filesystem", {}).get("denyWrite", []) or []
        user_deny_read = custom_config.get("filesystem", {}).get("denyRead", []) or []
        allowed_domains = custom_config.get("network", {}).get("allowedDomains", []) or []
    else:
        user_allow_write = _config.filesystem.allow_write or []
        user_deny_write = _config.filesystem.deny_write or []
        user_deny_read = _config.filesystem.deny_read or []
        allowed_domains = _config.network.allowed_domains or []

    write_config = {
        "allowOnly": get_default_write_paths() + user_allow_write,
        "denyWithinAllow": user_deny_write,
    }
    read_config = {
        "denyOnly": user_deny_read,
    }

    # Check if network proxy is needed
    needs_network_proxy = len(allowed_domains) > 0

    # Wait for network initialization only if proxy is actually needed
    if needs_network_proxy:
        await wait_for_network_initialization()

    if platform == "macos":
        return await wrap_command_with_sandbox_macos(
            command=command,
            needs_network_restriction=needs_network_proxy,
            http_proxy_port=get_proxy_port() if needs_network_proxy else None,
            socks_proxy_port=get_socks_proxy_port() if needs_network_proxy else None,
            read_config=read_config,
            write_config=write_config,
            allow_unix_sockets=get_allow_unix_sockets(),
            allow_all_unix_sockets=get_allow_all_unix_sockets(),
            allow_local_binding=get_allow_local_binding(),
            bin_shell=bin_shell,
            ripgrep_config=get_ripgrep_config(),
            sandbox_dir=sandbox_dir,
        )

    elif platform == "linux":
        return wrap_command_with_sandbox_linux(
            command=command,
            needs_network_restriction=needs_network_proxy,
            http_socket_path=get_linux_http_socket_path(),
            socks_socket_path=get_linux_socks_socket_path(),
            http_proxy_port=_manager_context.get("http_proxy_port")
            if _manager_context and needs_network_proxy
            else None,
            socks_proxy_port=_manager_context.get("socks_proxy_port")
            if _manager_context and needs_network_proxy
            else None,
            read_config=read_config,
            write_config=write_config,
            enable_weaker_nested_sandbox=get_enable_weaker_nested_sandbox(),
            allow_all_unix_sockets=get_allow_all_unix_sockets(),
            bin_shell=bin_shell,
            ripgrep_config=get_ripgrep_config(),
        )

    else:
        raise RuntimeError(
            f"Sandbox configuration is not supported on platform: {platform}"
        )


def get_config() -> Optional[SandboxRuntimeConfig]:
    """Get the current sandbox configuration."""
    return _config


def update_config(new_config: SandboxRuntimeConfig) -> None:
    """Update the sandbox configuration."""
    global _config
    # Deep clone the config to avoid mutations
    _config = copy.deepcopy(new_config)
    log_for_debugging("Sandbox configuration updated")


async def reset() -> None:
    """Reset and cleanup all sandbox resources."""
    global _log_monitor_shutdown
    global _http_proxy_server
    global _socks_proxy_server
    global _manager_context
    global _initialization_promise

    # Stop log monitor
    if _log_monitor_shutdown:
        _log_monitor_shutdown()
        _log_monitor_shutdown = None

    # Clean up Linux bridge
    if _manager_context and _manager_context.get("linux_bridge"):
        bridge = _manager_context["linux_bridge"]
        http_bridge_process = bridge.http_bridge_process
        socks_bridge_process = bridge.socks_bridge_process

        # Kill HTTP bridge
        if http_bridge_process.pid:
            try:
                http_bridge_process.terminate()
                log_for_debugging("Sent SIGTERM to HTTP bridge process")
                # Wait with timeout
                try:
                    http_bridge_process.wait(timeout=5)
                    log_for_debugging("HTTP bridge process exited")
                except subprocess.TimeoutExpired:
                    log_for_debugging(
                        "HTTP bridge did not exit, forcing SIGKILL", {"level": "warn"}
                    )
                    http_bridge_process.kill()
                    http_bridge_process.wait()
            except Exception as err:
                if not (hasattr(err, "errno") and err.errno == 3):  # ESRCH
                    log_for_debugging(f"Error killing HTTP bridge: {err}", {"level": "error"})

        # Kill SOCKS bridge
        if socks_bridge_process.pid:
            try:
                socks_bridge_process.terminate()
                log_for_debugging("Sent SIGTERM to SOCKS bridge process")
                try:
                    socks_bridge_process.wait(timeout=5)
                    log_for_debugging("SOCKS bridge process exited")
                except subprocess.TimeoutExpired:
                    log_for_debugging(
                        "SOCKS bridge did not exit, forcing SIGKILL", {"level": "warn"}
                    )
                    socks_bridge_process.kill()
                    socks_bridge_process.wait()
            except Exception as err:
                if not (hasattr(err, "errno") and err.errno == 3):  # ESRCH
                    log_for_debugging(f"Error killing SOCKS bridge: {err}", {"level": "error"})

        # Clean up sockets
        if bridge.http_socket_path:
            try:
                Path(bridge.http_socket_path).unlink(missing_ok=True)
                log_for_debugging("Cleaned up HTTP socket")
            except Exception as err:
                log_for_debugging(f"HTTP socket cleanup error: {err}", {"level": "error"})

        if bridge.socks_socket_path:
            try:
                Path(bridge.socks_socket_path).unlink(missing_ok=True)
                log_for_debugging("Cleaned up SOCKS socket")
            except Exception as err:
                log_for_debugging(f"SOCKS socket cleanup error: {err}", {"level": "error"})

    # Close servers
    if _http_proxy_server:
        await _http_proxy_server.close()
    if _socks_proxy_server:
        await _socks_proxy_server.close()

    # Clear references
    _http_proxy_server = None
    _socks_proxy_server = None
    _manager_context = None
    _initialization_promise = None


def get_sandbox_violation_store() -> SandboxViolationStore:
    """Get the sandbox violation store."""
    return _sandbox_violation_store


def annotate_stderr_with_sandbox_failures(command: str, stderr: str) -> str:
    """Annotate stderr with sandbox violations."""
    if not _config:
        return stderr

    violations = _sandbox_violation_store.get_violations_for_command(command)
    if len(violations) == 0:
        return stderr

    annotated = stderr + "\n<sandbox_violations>\n"
    for violation in violations:
        annotated += violation.line + "\n"
    annotated += "</sandbox_violations>"

    return annotated


def get_linux_glob_pattern_warnings() -> list[str]:
    """Get glob patterns that are not fully supported on Linux."""
    # Only warn on Linux
    if get_platform() != "linux" or not _config:
        return []

    glob_patterns = []

    # Check filesystem paths for glob patterns
    all_paths = (
        _config.filesystem.deny_read
        + _config.filesystem.allow_write
        + _config.filesystem.deny_write
    )

    for path in all_paths:
        # Strip trailing /** since that's just a subpath
        path_without_trailing_star = remove_trailing_glob_suffix(path)

        # Only warn if there are still glob characters after removing trailing /**
        if contains_glob_chars(path_without_trailing_star):
            glob_patterns.append(path)

    return glob_patterns


# ============================================================================
# Public API - SandboxManager class-like interface
# ============================================================================


class SandboxManager:
    """Global sandbox manager that handles both network and filesystem restrictions."""

    @staticmethod
    async def initialize(
        runtime_config: SandboxRuntimeConfig,
        sandbox_ask_callback: Optional[SandboxAskCallback] = None,
        enable_log_monitor: bool = False,
    ) -> None:
        """Initialize the sandbox manager."""
        await initialize(runtime_config, sandbox_ask_callback, enable_log_monitor)

    @staticmethod
    def is_supported_platform(platform: Platform) -> bool:
        """Check if platform is supported."""
        return is_supported_platform(platform)

    @staticmethod
    def is_sandboxing_enabled() -> bool:
        """Check if sandboxing is enabled."""
        return is_sandboxing_enabled()

    @staticmethod
    def check_dependencies(ripgrep_config: Optional[RipgrepConfig] = None) -> bool:
        """Check if all dependencies are available."""
        return check_dependencies(ripgrep_config)

    @staticmethod
    def get_fs_read_config() -> FsReadRestrictionConfig:
        """Get filesystem read restriction config."""
        return get_fs_read_config()

    @staticmethod
    def get_fs_write_config() -> FsWriteRestrictionConfig:
        """Get filesystem write restriction config."""
        return get_fs_write_config()

    @staticmethod
    def get_network_restriction_config() -> NetworkRestrictionConfig:
        """Get network restriction config."""
        return get_network_restriction_config()

    @staticmethod
    def get_allow_unix_sockets() -> Optional[list[str]]:
        """Get allowed Unix socket paths."""
        return get_allow_unix_sockets()

    @staticmethod
    def get_allow_local_binding() -> Optional[bool]:
        """Get allow local binding flag."""
        return get_allow_local_binding()

    @staticmethod
    def get_ignore_violations() -> Optional[dict[str, list[str]]]:
        """Get ignore violations config."""
        return get_ignore_violations()

    @staticmethod
    def get_enable_weaker_nested_sandbox() -> Optional[bool]:
        """Get enable weaker nested sandbox flag."""
        return get_enable_weaker_nested_sandbox()

    @staticmethod
    def get_proxy_port() -> Optional[int]:
        """Get HTTP proxy port."""
        return get_proxy_port()

    @staticmethod
    def get_socks_proxy_port() -> Optional[int]:
        """Get SOCKS proxy port."""
        return get_socks_proxy_port()

    @staticmethod
    def get_linux_http_socket_path() -> Optional[str]:
        """Get Linux HTTP socket path."""
        return get_linux_http_socket_path()

    @staticmethod
    def get_linux_socks_socket_path() -> Optional[str]:
        """Get Linux SOCKS socket path."""
        return get_linux_socks_socket_path()

    @staticmethod
    async def wait_for_network_initialization() -> bool:
        """Wait for network initialization."""
        return await wait_for_network_initialization()

    @staticmethod
    async def wrap_with_sandbox(
        command: str,
        bin_shell: Optional[str] = None,
        custom_config: Optional[dict] = None,
        sandbox_dir: Optional[str] = None,
    ) -> str:
        """Wrap a command with sandbox restrictions."""
        return await wrap_with_sandbox(command, bin_shell, custom_config, sandbox_dir)

    @staticmethod
    def get_sandbox_violation_store() -> SandboxViolationStore:
        """Get the sandbox violation store."""
        return get_sandbox_violation_store()

    @staticmethod
    def annotate_stderr_with_sandbox_failures(command: str, stderr: str) -> str:
        """Annotate stderr with sandbox violations."""
        return annotate_stderr_with_sandbox_failures(command, stderr)

    @staticmethod
    def get_linux_glob_pattern_warnings() -> list[str]:
        """Get Linux glob pattern warnings."""
        return get_linux_glob_pattern_warnings()

    @staticmethod
    def get_config() -> Optional[SandboxRuntimeConfig]:
        """Get the current configuration."""
        return get_config()

    @staticmethod
    def update_config(new_config: SandboxRuntimeConfig) -> None:
        """Update the configuration."""
        update_config(new_config)

    @staticmethod
    async def reset() -> None:
        """Reset and cleanup."""
        await reset()
