import asyncio
import os
from pathlib import Path
from sandbox_runtime import SandboxManager
from sandbox_runtime.config.schemas import SandboxRuntimeConfig

SANDBOX_DIR = Path("{sandbox_path_str}")

async def execute_bash(command: str, timeout: int = 30):
    """
    Execute a bash command in a sandboxed environment.

    Args:
        command: The bash command to execute (e.g., "ls -la", "echo 'hello'")
        timeout: Maximum execution time in seconds (default: 30)
        
    Returns:
        A dictionary containing:
        - stdout: Standard output from the command
        - stderr: Standard error output (may include sandbox violation info)
        - returncode: Exit code of the command (0 = success)
        - success: Boolean indicating if command succeeded
    """
    # Initialize sandbox config
    # Use deny-by-default (whitelist) approach - only allow sandbox directory + minimal system paths
    # This matches the Seatbelt profile pattern: (deny default) then allow specific paths
    sandbox_dir_str = str(SANDBOX_DIR)

    # Allow reads only from:
    # 1. The sandbox directory itself
    # 2. Minimal system paths needed for the process to run
    allow_read_paths = [
        sandbox_dir_str,
        "/usr/lib",           # System libraries (Linux/macOS)
        "/System/Library",    # macOS system libraries
        "/Library/Frameworks", # macOS frameworks
        "/usr/bin",           # System binaries (needed for Python, etc.)
        "/bin",               # Core system binaries
        "/lib",               # Core system libraries
        "/lib64",             # 64-bit libraries (Linux)
    ]

    # Empty allowedDomains = no network restrictions (allow all)
    # This allows MCP server connections and other network access from sandbox
    sandbox_config = SandboxRuntimeConfig.from_json({
        "network": {
            "allowedDomains": [],  # Empty = allow all network access
            "deniedDomains": []
        },
        "filesystem": {
            "allowRead": allow_read_paths,
            "allowWrite": [
                sandbox_dir_str
            ],
            "denyWrite": []
        }
    })

    await SandboxManager.initialize(sandbox_config)

    # Change to sandbox directory
    original_cwd = os.getcwd()
    os.chdir(str(SANDBOX_DIR))

    try:
        # Prepend virtual environment activation to every command
        # This ensures the venv is activated for all bash commands
        activated_command = f"source .venv/bin/activate && {command}"
        
        # Wrap command with sandbox restrictions
        # Mount sandbox directory as /root so it appears as /root/ to the LLM
        activated_cmd = f"source .venv/bin/activate && {command}"
        sandboxed_command = await SandboxManager.wrap_with_sandbox(
            activated_cmd,
            bin_shell="bash",
            sandbox_dir=str(SANDBOX_DIR)
        )
        
        # Execute the sandboxed command
        # Note: cwd is still SANDBOX_DIR, but inside the sandbox it appears as /root
        # Pass environment variables explicitly, but filter out proxy vars when network restrictions aren't needed
        # (proxy vars can cause httpx to fail with ProxyError when no proxy is actually available)
        env = os.environ.copy()
        # Since allowedDomains is empty (no network restrictions), remove proxy env vars that might interfere
        proxy_vars_to_remove = [
            'HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy',
            'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy',
            'FTP_PROXY', 'ftp_proxy', 'SOCKS_PROXY', 'socks_proxy'
        ]
        for var in proxy_vars_to_remove:
            env.pop(var, None)
        process = await asyncio.create_subprocess_shell(
            sandboxed_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(SANDBOX_DIR),
            env=env
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds",
                "returncode": -1,
                "success": False
            }
        
        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")
        
        # Annotate stderr with sandbox violations if any
        stderr_str = SandboxManager.annotate_stderr_with_sandbox_failures(
            command,
            stderr_str
        )
        
        return {
            "stdout": stdout_str,
            "stderr": stderr_str,
            "returncode": process.returncode or 0,
            "success": process.returncode == 0,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Error executing command: {str(e)}",
            "returncode": -1,
            "success": False
        }
    finally:
        # Always restore CWD
        os.chdir(original_cwd)

def main(command: str, timeout: int = 30):
    """
    Synchronous wrapper for execute_bash.
    This is called by the Python tool executor.
    """
    return asyncio.run(execute_bash(command, timeout))
