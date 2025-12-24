#!/usr/bin/env python3
"""
Bash Tool Engine
================

Backend-native executor for execute_bash tool.
Uses simple subprocess execution with SandboxManager isolation.
"""

import asyncio
import os
import json
import logging
from typing import Dict, Any

from mcp.types import TextContent, CallToolResult

from vmcp.vmcps.sandbox_service import get_sandbox_service
from sandbox_runtime import SandboxManager
from sandbox_runtime.config.schemas import SandboxRuntimeConfig

logger = logging.getLogger("1xN_vMCP_BASH_TOOL")


async def execute_bash_tool(
    vmcp_id: str,
    command: str,
    timeout: int = 30,
    user_id: str = "1"
) -> CallToolResult:
    """
    Execute a bash command in a sandboxed environment.
    
    Args:
        vmcp_id: The vMCP ID
        command: Bash command to execute
        timeout: Maximum execution time in seconds
        user_id: User ID (defaults to "1" for OSS)
        
    Returns:
        CallToolResult with stdout, stderr, returncode
    """
    try:
        # Get sandbox service and path
        sandbox_service = get_sandbox_service()
        if not sandbox_service.sandbox_exists(vmcp_id):
            error_result = {
                "result": {"error": "Sandbox not found. Attach sandbox first."},
                "stdout": "",
                "stderr": "Sandbox not found. Attach sandbox first."
            }
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps(error_result, indent=2),
                    annotations=None,
                    _meta=None
                )],
                structuredContent=error_result,
                isError=True
            )
        
        sandbox_path = sandbox_service.get_sandbox_path(vmcp_id)
        sandbox_dir_str = str(sandbox_path)
        
        # Initialize sandbox config
        # Use deny-by-default (whitelist) approach - only allow sandbox directory + minimal system paths
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
        os.chdir(sandbox_dir_str)
        
        try:
            # Prepend virtual environment activation to every command
            # This ensures the venv is activated for all bash commands
            activated_cmd = f"source .venv/bin/activate && {command}"
            
            # Wrap command with sandbox restrictions
            sandboxed_command = await SandboxManager.wrap_with_sandbox(
                activated_cmd,
                bin_shell="bash",
                sandbox_dir=sandbox_dir_str
            )
            
            # Execute the sandboxed command
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
                cwd=sandbox_dir_str,
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
                error_result = {
                    "result": {"error": f"Command timed out after {timeout} seconds"},
                    "stdout": "",
                    "stderr": f"Command timed out after {timeout} seconds"
                }
                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text=json.dumps(error_result, indent=2),
                        annotations=None,
                        _meta=None
                    )],
                    structuredContent=error_result,
                    isError=True
                )
            
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")
            
            # Annotate stderr with sandbox violations if any
            stderr_str = SandboxManager.annotate_stderr_with_sandbox_failures(
                command,
                stderr_str
            )
            
            return_code = process.returncode or 0
            success = return_code == 0
            
            result_dict = {
                "stdout": stdout_str,
                "stderr": stderr_str,
                "returncode": return_code,
                "success": success
            }
            
            structured_output = {
                "result": result_dict,
                "stdout": stdout_str,
                "stderr": stderr_str
            }
            
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps(structured_output, indent=2),
                    annotations=None,
                    _meta=None
                )],
                structuredContent=structured_output,
                isError=not success
            )
            
        except Exception as e:
            logger.error(f"Error executing bash command: {e}", exc_info=True)
            error_result = {
                "result": {"error": str(e)},
                "stdout": "",
                "stderr": f"Error executing command: {str(e)}"
            }
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps(error_result, indent=2),
                    annotations=None,
                    _meta=None
                )],
                structuredContent=error_result,
                isError=True
            )
        finally:
            # Always restore CWD
            os.chdir(original_cwd)
            
    except Exception as e:
        logger.error(f"Error in execute_bash_tool: {e}", exc_info=True)
        error_result = {
            "result": {"error": str(e)},
            "stdout": "",
            "stderr": str(e)
        }
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=json.dumps(error_result, indent=2),
                annotations=None,
                _meta=None
            )],
            structuredContent=error_result,
            isError=True
        )

