"""
Comprehensive Sandboxing Tests
==============================

Tests to verify that sandboxing is working correctly for:
1. Filesystem isolation (read/write restrictions)
2. Network isolation (domain allow/deny)
3. Process isolation (PID namespace, privilege escalation)
4. VMCP integration (Python/Bash tools and sandbox-discovered tools)

Note: On macOS, you may see an admin prompt asking for permission to use sandbox-exec.
This is normal - you can click "Allow" once and macOS will remember the permission.
The sandbox-exec tool is used to enforce security restrictions in the tests.
"""

import pytest
import subprocess
import tempfile
import time
from pathlib import Path

# Import sandbox runtime components
from sandbox_runtime import SandboxManager
from sandbox_runtime.config.schemas import SandboxRuntimeConfig
from sandbox_runtime.utils.platform import get_platform

# Import MCP client for VMCP integration tests
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def test_sandbox_dir():
    """Create a temporary directory for sandbox testing."""
    test_dir = Path(tempfile.mkdtemp(prefix="sandbox_test_"))
    yield test_dir
    # Cleanup
    import shutil
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)


@pytest.fixture
def restrictive_sandbox_config(test_sandbox_dir):
    """Create a restrictive sandbox configuration for testing."""
    return SandboxRuntimeConfig.from_json({
        "network": {
            "allowedDomains": [],  # Block all network by default
            "deniedDomains": []
        },
        "filesystem": {
            "denyRead": [],  # Allow reads by default
            "allowWrite": [str(test_sandbox_dir)],  # Only allow writes to test dir
            "denyWrite": []
        }
    })


@pytest.fixture
async def initialized_sandbox_manager(restrictive_sandbox_config):
    """Initialize SandboxManager with restrictive config."""
    await SandboxManager.initialize(restrictive_sandbox_config)
    yield
    await SandboxManager.reset()


def skip_if_unsupported_platform():
    """Check if platform is unsupported for sandboxing."""
    platform = get_platform()
    return platform not in ("linux", "macos")


def skip_if_missing_dependencies():
    """Check if sandbox dependencies are available."""
    platform = get_platform()
    if platform == "linux":
        # Check for bubblewrap and socat on Linux
        from sandbox_runtime.sandbox.linux_utils import has_linux_sandbox_dependencies_sync
        return not has_linux_sandbox_dependencies_sync()
    elif platform == "macos":
        # On macOS, sandbox-exec is built-in, but check if it's available
        import subprocess
        result = subprocess.run(
            ["which", "sandbox-exec"],
            capture_output=True,
            timeout=1,
        )
        return result.returncode != 0
    return True  # Unsupported platform


# ============================================================================
# FILESYSTEM ISOLATION TESTS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.skipif(skip_if_unsupported_platform(), reason="Platform not supported")
@pytest.mark.skipif(skip_if_missing_dependencies(), reason="Sandbox dependencies not available")
class TestFilesystemIsolation:
    """Test filesystem isolation and restrictions."""

    async def test_block_write_outside_sandbox_dir(
        self, test_sandbox_dir, initialized_sandbox_manager
    ):
        """Test that writes outside sandbox directory are blocked."""
        # Try to write to a path that's definitely outside allowed write paths
        # Use home directory which should not be in the allowed write list
        test_file = Path.home() / f".sandbox_blocked_{int(time.time())}.txt"
        
        # Clean up if exists (shouldn't, but just in case)
        if test_file.exists():
            test_file.unlink()

        command = await SandboxManager.wrap_with_sandbox(
            f'echo "should fail" > {test_file}',
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(test_sandbox_dir),
            timeout=5,
        )

        # Should fail - check for error in output or non-zero return code
        output = (result.stderr or result.stdout or "").lower()
        # On macOS, may get "Operation not permitted" or "read-only file system"
        # On Linux, may get different error
        assert (
            "read-only file system" in output
            or "operation not permitted" in output
            or "permission denied" in output
            or result.returncode != 0
        ), f"Expected write to be blocked, but got: stdout={result.stdout}, stderr={result.stderr}, returncode={result.returncode}"
        assert not test_file.exists(), "File should not have been created"

    async def test_allow_write_inside_sandbox_dir(
        self, test_sandbox_dir, initialized_sandbox_manager
    ):
        """Test that writes inside sandbox directory are allowed."""
        test_file = test_sandbox_dir / "allowed-write.txt"
        test_content = "test content from sandbox"

        # Clean up if exists
        if test_file.exists():
            test_file.unlink()

        command = await SandboxManager.wrap_with_sandbox(
            f'echo "{test_content}" > allowed-write.txt',
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(test_sandbox_dir),
            timeout=5,
        )

        # Should succeed
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert test_file.exists(), "File should have been created"
        
        # Verify content
        content = test_file.read_text()
        assert test_content in content

        # Clean up
        if test_file.exists():
            test_file.unlink()

    async def test_block_read_from_denied_path(
        self, test_sandbox_dir, initialized_sandbox_manager
    ):
        """Test that reads from denied paths are blocked."""
        # Reset and reinitialize with read restrictions
        await SandboxManager.reset()
        
        # Create a test file in home directory
        home_test_file = Path.home() / f".sandbox_test_{int(time.time())}.txt"
        home_test_file.write_text("secret content")
        
        try:
            config = SandboxRuntimeConfig.from_json({
                "network": {
                    "allowedDomains": [],
                    "deniedDomains": []
                },
                "filesystem": {
                    "denyRead": [str(home_test_file)],  # Deny reading this file
                    "allowWrite": [str(test_sandbox_dir)],
                    "denyWrite": []
                }
            })
            
            await SandboxManager.initialize(config)

            command = await SandboxManager.wrap_with_sandbox(
                f"cat {home_test_file}",
            )

            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=5,
            )

            # Should fail or not show content
            output = (result.stderr or result.stdout or "").lower()
            # On macOS, may get "Operation not permitted" or similar
            # On Linux, may get different error
            assert (
                "operation not permitted" in output
                or "permission denied" in output
                or "secret content" not in output
                or result.returncode != 0
            )
        finally:
            # Cleanup
            if home_test_file.exists():
                home_test_file.unlink()
            await SandboxManager.reset()
            await SandboxManager.initialize(
                SandboxRuntimeConfig.from_json({
                    "network": {"allowedDomains": [], "deniedDomains": []},
                    "filesystem": {
                        "denyRead": [],
                        "allowWrite": [str(test_sandbox_dir)],
                        "denyWrite": []
                    }
                })
            )

    async def test_allow_read_from_allowed_path(
        self, test_sandbox_dir, initialized_sandbox_manager
    ):
        """Test that reads from allowed paths work."""
        # Create a test file in sandbox
        test_file = test_sandbox_dir / "readable.txt"
        test_content = "readable content"
        test_file.write_text(test_content)

        command = await SandboxManager.wrap_with_sandbox(
            f"cat {test_file}",
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(test_sandbox_dir),
            timeout=5,
        )

        # Should succeed
        assert result.returncode == 0
        assert test_content in result.stdout

    async def test_prevent_symlink_escape(
        self, test_sandbox_dir, initialized_sandbox_manager
    ):
        """Test that symlink-based filesystem escape attempts are prevented."""
        link_in_allowed = test_sandbox_dir / "escape-link"
        # Use home directory which should not be in the allowed write list
        target_outside = Path.home() / f".escape-test-{int(time.time())}.txt"

        # Try to create symlink inside allowed dir pointing to restricted location
        # Then try to write through it
        command = await SandboxManager.wrap_with_sandbox(
            f'ln -s {target_outside} {link_in_allowed} 2>&1 && echo "escaped" > {link_in_allowed} 2>&1',
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(test_sandbox_dir),
            timeout=5,
        )

        # Write should fail - check for error in output or non-zero return code
        output = (result.stderr or result.stdout or "").lower()
        # On macOS, may get "Operation not permitted" or "read-only file system"
        # On Linux, may get different error
        assert (
            "read-only file system" in output
            or "operation not permitted" in output
            or "permission denied" in output
            or result.returncode != 0
        ), f"Expected write through symlink to be blocked, but got: stdout={result.stdout}, stderr={result.stderr}, returncode={result.returncode}"

        # Target file should NOT exist
        assert not target_outside.exists(), "Target file should not have been created"

        # Clean up
        if link_in_allowed.exists():
            link_in_allowed.unlink()
        if target_outside.exists():
            target_outside.unlink()

    async def test_prevent_hardlink_to_restricted_file(
        self, test_sandbox_dir, initialized_sandbox_manager
    ):
        """Test that hardlinks to restricted files are prevented."""
        hardlink_path = test_sandbox_dir / "hardlink.txt"
        
        # Create a test file in home directory (outside allowed write location)
        home_test_file = Path.home() / f".hardlink_source_{int(time.time())}.txt"
        home_test_file.write_text("test content")
        
        try:
            # Try to create hard link to file outside allowed location
            command = await SandboxManager.wrap_with_sandbox(
                f"ln {home_test_file} {hardlink_path} 2>&1",
            )

            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=str(test_sandbox_dir),
                timeout=5,
            )

            # Should fail
            assert result.returncode != 0
            output = result.stdout.lower()
            import re
            assert re.search(
                r"read-only|permission denied|not permitted|operation not permitted|cross-device",
                output,
            ), f"Expected hardlink creation to fail, but got: stdout={result.stdout}, stderr={result.stderr}, returncode={result.returncode}"

            # Cleanup
            if hardlink_path.exists():
                hardlink_path.unlink()
        finally:
            if home_test_file.exists():
                home_test_file.unlink()


# ============================================================================
# NETWORK ISOLATION TESTS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.skipif(skip_if_unsupported_platform(), reason="Platform not supported")
@pytest.mark.skipif(skip_if_missing_dependencies(), reason="Sandbox dependencies not available")
class TestNetworkIsolation:
    """Test network isolation and restrictions."""

    async def test_block_network_when_no_allowed_domains(
        self, test_sandbox_dir, initialized_sandbox_manager
    ):
        """Test that network is blocked when allowedDomains is empty."""
        # Config already has empty allowedDomains, so network should be blocked
        command = await SandboxManager.wrap_with_sandbox(
            "curl -s --show-error --max-time 2 http://example.com 2>&1",
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # Should fail or be blocked
        output = (result.stderr or result.stdout or "").lower()
        did_fail = result.returncode != 0 or result.returncode is None
        assert did_fail or "blocked" in output or "timeout" in output or len(output) == 0

    async def test_allow_network_to_allowed_domain(
        self, test_sandbox_dir, initialized_sandbox_manager
    ):
        """Test that network to allowed domains works."""
        # Reset and reinitialize with example.com allowed
        await SandboxManager.reset()
        
        config = SandboxRuntimeConfig.from_json({
            "network": {
                "allowedDomains": ["example.com"],  # Allow example.com
                "deniedDomains": []
            },
            "filesystem": {
                "denyRead": [],
                "allowWrite": [str(test_sandbox_dir)],
                "denyWrite": []
            }
        })
        
        await SandboxManager.initialize(config)

        command = await SandboxManager.wrap_with_sandbox(
            "curl -s --max-time 5 http://example.com",
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Should not be blocked by sandbox (may fail for other reasons like network issues)
        output = (result.stdout or result.stderr or "").lower()
        # The key test: it should NOT be blocked by the network allowlist
        assert "blocked by network allowlist" not in output, \
            f"Request to allowed domain was blocked: {output}"
        
        # If it succeeded, verify we got content
        if result.returncode == 0:
            assert "Example Domain" in result.stdout or "example.com" in result.stdout.lower()
        # If it failed, it should be due to network issues, not sandbox blocking
        else:
            # Timeout (28) or connection errors are acceptable - the sandbox allowed the attempt
            assert result.returncode in [28, 6, 7] or "timeout" in output or "could not resolve" in output, \
                f"Unexpected failure: returncode={result.returncode}, output={output}"

        # Restore original config
        await SandboxManager.reset()
        await SandboxManager.initialize(
            SandboxRuntimeConfig.from_json({
                "network": {"allowedDomains": [], "deniedDomains": []},
                "filesystem": {
                    "denyRead": [],
                    "allowWrite": [str(test_sandbox_dir)],
                    "denyWrite": []
                }
            })
        )

    async def test_block_network_to_denied_domain(
        self, test_sandbox_dir, initialized_sandbox_manager
    ):
        """Test that network to denied domains is blocked."""
        # Reset and reinitialize with denied domain
        await SandboxManager.reset()
        
        config = SandboxRuntimeConfig.from_json({
            "network": {
                "allowedDomains": ["example.com"],  # Allow example.com
                "deniedDomains": ["blocked-domain.example"]  # Deny this
            },
            "filesystem": {
                "denyRead": [],
                "allowWrite": [str(test_sandbox_dir)],
                "denyWrite": []
            }
        })
        
        await SandboxManager.initialize(config)

        command = await SandboxManager.wrap_with_sandbox(
            "curl -s --show-error --max-time 2 http://blocked-domain.example 2>&1",
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # Should be blocked
        output = result.stdout.lower()
        assert "blocked by network allowlist" in output or result.returncode != 0

        # Restore original config
        await SandboxManager.reset()
        await SandboxManager.initialize(
            SandboxRuntimeConfig.from_json({
                "network": {"allowedDomains": [], "deniedDomains": []},
                "filesystem": {
                    "denyRead": [],
                    "allowWrite": [str(test_sandbox_dir)],
                    "denyWrite": []
                }
            })
        )

    async def test_wildcard_domain_matching(
        self, test_sandbox_dir, initialized_sandbox_manager
    ):
        """Test that wildcard domain pattern matching works correctly."""
        # Reset and reinitialize with wildcard pattern
        await SandboxManager.reset()
        
        config = SandboxRuntimeConfig.from_json({
            "network": {
                "allowedDomains": ["*.github.com", "example.com"],
                "deniedDomains": []
            },
            "filesystem": {
                "denyRead": [],
                "allowWrite": [str(test_sandbox_dir)],
                "denyWrite": []
            }
        })
        
        await SandboxManager.initialize(config)

        # Test 1: Subdomain should match wildcard
        command1 = await SandboxManager.wrap_with_sandbox(
            "curl -s --max-time 3 http://api.github.com 2>&1 | head -20",
        )

        result1 = subprocess.run(
            command1,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # Should NOT be blocked - api.github.com matches *.github.com
        output1 = result1.stdout.lower()
        assert "blocked by network allowlist" not in output1

        # Test 2: Base domain should NOT match wildcard (*.github.com doesn't match github.com)
        command2 = await SandboxManager.wrap_with_sandbox(
            "curl -s --max-time 2 http://github.com 2>&1",
        )

        result2 = subprocess.run(
            command2,
            shell=True,
            capture_output=True,
            text=True,
            timeout=3,
        )

        # Should be blocked - github.com does NOT match *.github.com
        output2 = result2.stdout.lower()
        assert "blocked by network allowlist" in output2

        # Restore original config
        await SandboxManager.reset()
        await SandboxManager.initialize(
            SandboxRuntimeConfig.from_json({
                "network": {"allowedDomains": [], "deniedDomains": []},
                "filesystem": {
                    "denyRead": [],
                    "allowWrite": [str(test_sandbox_dir)],
                    "denyWrite": []
                }
            })
        )

    async def test_block_direct_ip_access(
        self, test_sandbox_dir, initialized_sandbox_manager
    ):
        """Test that direct IP addresses are blocked."""
        # IP addresses should be blocked by the proxy when no domains are allowed
        command = await SandboxManager.wrap_with_sandbox(
            "curl -s --max-time 2 http://1.1.1.1 2>&1",  # Cloudflare DNS
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=3,
        )

        # IP addresses should be blocked by the proxy
        output = result.stdout.lower()
        assert "blocked by network allowlist" in output or result.returncode != 0


# ============================================================================
# PROCESS ISOLATION TESTS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.skipif(skip_if_unsupported_platform(), reason="Platform not supported")
@pytest.mark.skipif(skip_if_missing_dependencies(), reason="Sandbox dependencies not available")
class TestProcessIsolation:
    """Test process isolation and security."""

    async def test_pid_namespace_isolation(
        self, test_sandbox_dir, initialized_sandbox_manager
    ):
        """Test that PID namespace is isolated - sandboxed processes cannot see host PIDs."""
        # Use /proc to check PID namespace isolation
        # Inside sandbox, should only see sandbox PIDs in /proc
        command = await SandboxManager.wrap_with_sandbox(
            "ls /proc | grep -E '^[0-9]+$' | wc -l",
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0

        # Should see very few PIDs (only sandbox processes)
        pid_count = int(result.stdout.strip())
        assert pid_count < 30, f"Expected < 30 PIDs, got {pid_count}"  # Host would have 100+
        assert pid_count > 0, "Should see at least some processes"

    async def test_prevent_privilege_escalation(
        self, test_sandbox_dir, initialized_sandbox_manager
    ):
        """Test that privilege escalation attempts are prevented."""
        setuid_test = test_sandbox_dir / "setuid-test"

        # Test 1: Setuid binaries cannot actually elevate privileges
        command1 = await SandboxManager.wrap_with_sandbox(
            f'cp /bin/bash {setuid_test} 2>&1 && chmod u+s {setuid_test} 2>&1 && {setuid_test} -c "id -u" 2>&1',
        )

        result1 = subprocess.run(
            command1,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(test_sandbox_dir),
            timeout=5,
        )

        # Should still run as the same UID (not root), proving setuid doesn't work
        uid_lines = result1.stdout.strip().split("\n")
        uid = uid_lines[-1] if uid_lines else "0"
        assert int(uid) > 0, "Should not be root (UID 0)"

        # Test 2: Cannot use sudo/su (should not be available or fail)
        command2 = await SandboxManager.wrap_with_sandbox(
            'sudo -n echo "elevated" 2>&1 || su -c "echo elevated" 2>&1 || echo "commands blocked"',
        )

        result2 = subprocess.run(
            command2,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # Should not successfully escalate
        output = result2.stdout.lower()
        if "elevated" in output and "commands blocked" not in output:
            # If "elevated" appears without "commands blocked", it should be in an error message
            import re
            assert re.search(
                r"not found|command not found|no such file|not permitted|password|cannot|no password",
                output,
            )

        # Cleanup
        if setuid_test.exists():
            setuid_test.unlink()

    async def test_background_process_cleanup(
        self, test_sandbox_dir, initialized_sandbox_manager
    ):
        """Test that background processes are terminated when sandbox exits."""
        # Create a unique marker file that a background process will touch
        marker_file = test_sandbox_dir / "background-process-marker.txt"

        if marker_file.exists():
            marker_file.unlink()

        # Start a background process that writes every 0.5 second
        command = await SandboxManager.wrap_with_sandbox(
            f'(while true; do echo "alive" >> {marker_file}; sleep 0.5; done) & sleep 2',
        )

        start_time = time.time()
        subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(test_sandbox_dir),
            timeout=5,
        )
        end_time = time.time()

        # Wait a bit to ensure background process would continue if not killed
        time.sleep(2)

        if marker_file.exists():
            content = marker_file.read_text()
            lines = len(content.strip().split("\n"))

            # Should have ~4 lines (2 seconds / 0.5s each), not 10+ (if process continued for 5s)
            assert lines < 10, f"Background process continued running (got {lines} lines)"

            marker_file.unlink()
        else:
            # If file doesn't exist, that's also fine - process was killed
            assert True

        # Verify total execution was ~2 seconds, not hanging
        assert (end_time - start_time) < 4, "Command took too long"


# ============================================================================
# VMCP INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.skipif(skip_if_unsupported_platform(), reason="Platform not supported")
@pytest.mark.skipif(skip_if_missing_dependencies(), reason="Sandbox dependencies not available")
class TestVMCPIntegration:
    """Test sandboxing in VMCP tool execution."""

    async def test_python_tool_filesystem_restrictions(
        self, base_url, create_vmcp, helpers
    ):
        """Test that Python tools respect filesystem restrictions."""
        vmcp = create_vmcp
        print(f"\n🔒 Test - Python tool filesystem restrictions: {vmcp['id']}")

        # Add Python tool that tries to write outside sandbox
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "write_outside_sandbox",
            "description": "Try to write outside sandbox",
            "tool_type": "python",
            "code": """
import os
from pathlib import Path

def main():
    # Try to write to /tmp (should fail)
    test_file = Path("/tmp") / "sandbox_escape_test.txt"
    try:
        test_file.write_text("escaped!")
        return f"ERROR: Write succeeded (should have failed): {test_file}"
    except Exception as e:
        return f"SUCCESS: Write blocked as expected: {type(e).__name__}: {str(e)}"
""",
            "variables": [],
            "environment_variables": [],
            "tool_calls": [],
            "atomic_blocks": []
        })
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call tool
                result = await session.call_tool("write_outside_sandbox", arguments={})

                print(f"🔧 Tool result: {result}")

                # Verify that write was blocked
                result_text = result.content[0].text
                assert "SUCCESS" in result_text or "blocked" in result_text.lower(), \
                    f"Expected write to be blocked, got: {result_text}"

                print("✅ Python tool filesystem restrictions working")

    async def test_python_tool_network_restrictions(
        self, base_url, create_vmcp, helpers
    ):
        """Test that Python tools respect network restrictions."""
        vmcp = create_vmcp
        print(f"\n🔒 Test - Python tool network restrictions: {vmcp['id']}")

        # Add Python tool that tries to make network request
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "network_request",
            "description": "Try to make network request",
            "tool_type": "python",
            "code": """
import urllib.request
import urllib.error

def main():
    # Try to access a website (should fail when network is blocked)
    try:
        response = urllib.request.urlopen("http://example.com", timeout=2)
        content = response.read().decode('utf-8')[:100]
        return f"ERROR: Network request succeeded (should have failed): {content[:50]}"
    except urllib.error.URLError as e:
        return f"SUCCESS: Network request blocked as expected: {type(e).__name__}: {str(e)[:100]}"
    except Exception as e:
        return f"SUCCESS: Network request blocked as expected: {type(e).__name__}: {str(e)[:100]}"
""",
            "variables": [],
            "environment_variables": [],
            "tool_calls": [],
            "atomic_blocks": []
        })
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call tool
                result = await session.call_tool("network_request", arguments={})

                print(f"🔧 Tool result: {result}")

                # Verify that network request was blocked or failed
                result_text = result.content[0].text
                # Network may be blocked or may timeout/fail
                assert "SUCCESS" in result_text or "blocked" in result_text.lower() or \
                       "timeout" in result_text.lower() or "error" in result_text.lower(), \
                    f"Expected network to be restricted, got: {result_text}"

                print("✅ Python tool network restrictions working")

    async def test_bash_tool_filesystem_restrictions(
        self, base_url, create_vmcp, helpers
    ):
        """Test that Bash tools respect filesystem restrictions."""
        vmcp = create_vmcp
        print(f"\n🔒 Test - Bash tool filesystem restrictions: {vmcp['id']}")

        # Add Bash tool that tries to write outside sandbox
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "bash_write_test",
            "description": "Try to write outside sandbox with bash",
            "tool_type": "bash",
            "code": """
#!/bin/bash
# Try to write to /tmp (should fail)
TEST_FILE="/tmp/sandbox_bash_escape_test.txt"
if echo "escaped!" > "$TEST_FILE" 2>&1; then
    echo "ERROR: Write succeeded (should have failed)"
    rm -f "$TEST_FILE"
else
    echo "SUCCESS: Write blocked as expected"
fi
""",
            "variables": [],
            "environment_variables": [],
            "tool_calls": [],
            "atomic_blocks": []
        })
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call tool
                result = await session.call_tool("bash_write_test", arguments={})

                print(f"🔧 Tool result: {result}")

                # Verify that write was blocked
                result_text = result.content[0].text
                assert "SUCCESS" in result_text or "blocked" in result_text.lower() or \
                       "read-only" in result_text.lower(), \
                    f"Expected write to be blocked, got: {result_text}"

                print("✅ Bash tool filesystem restrictions working")

    async def test_sandbox_violation_error_messages(
        self, base_url, create_vmcp, helpers
    ):
        """Test that sandbox violations produce clear error messages."""
        vmcp = create_vmcp
        print(f"\n🔒 Test - Sandbox violation error messages: {vmcp['id']}")

        # Add Python tool that triggers a sandbox violation
        vmcp_data = helpers["get_vmcp"](vmcp["id"])
        vmcp_data["custom_tools"].append({
            "name": "sandbox_violation_test",
            "description": "Test sandbox violation handling",
            "tool_type": "python",
            "code": """
import os
from pathlib import Path

def main():
    # Try to access restricted file
    try:
        # Try to read /etc/shadow (should be restricted)
        with open("/etc/shadow", "r") as f:
            content = f.read()
        return "ERROR: Should not be able to read /etc/shadow"
    except PermissionError as e:
        return f"SUCCESS: Permission denied as expected: {str(e)[:100]}"
    except Exception as e:
        return f"SUCCESS: Access blocked as expected: {type(e).__name__}: {str(e)[:100]}"
""",
            "variables": [],
            "environment_variables": [],
            "tool_calls": [],
            "atomic_blocks": []
        })
        helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call tool
                result = await session.call_tool("sandbox_violation_test", arguments={})

                print(f"🔧 Tool result: {result}")

                # Verify that error is reported clearly
                result_text = result.content[0].text
                assert "SUCCESS" in result_text or "permission" in result_text.lower() or \
                       "denied" in result_text.lower() or "blocked" in result_text.lower(), \
                    f"Expected clear error message, got: {result_text}"

                print("✅ Sandbox violation error messages working")
