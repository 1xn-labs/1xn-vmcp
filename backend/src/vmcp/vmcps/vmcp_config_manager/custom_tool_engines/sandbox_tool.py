#!/usr/bin/env python3
"""
Sandbox Tool Engine
===================

Execution engine for sandbox-discovered Python tools.
These tools are Python scripts stored in vmcp_tools/ directory and executed
in the sandbox environment using SandboxManager.
"""

import asyncio
import json
import os
import logging
import base64
from pathlib import Path
from typing import Dict, Any, Optional, Union

# NOTE: SandboxManager is NOT imported here because it is only available
# inside the sandbox's virtual environment, not in the backend environment.
# We interact with it by executing a script using the sandbox's Python.

from mcp.types import TextContent, PromptMessage, GetPromptResult, CallToolResult

from .models import DynamicToolOutput

logger = logging.getLogger("1xN_vMCP_SANDBOX_TOOL")


async def execute_dynamic_tool_in_sandbox(
    vmcp_id: str,
    script_path: str,
    arguments: Dict[str, Any]
) -> DynamicToolOutput:
    """
    Execute a dynamic tool script in sandbox and return structured output.
    
    This function wraps the sandbox execution logic and returns DynamicToolOutput
    which can be used with structured_output=True in Tool.from_function.
    
    Args:
        vmcp_id: The vMCP ID
        script_path: Relative path to the script from sandbox root
        arguments: Tool arguments dictionary
        
    Returns:
        DynamicToolOutput with result, stdout, and stderr
    """
    logger.info(f"🏖️  DYNAMIC_TOOL: Executing dynamic tool - vmcp_id={vmcp_id}, script_path={script_path}, arguments={arguments}")
    
    try:
        from vmcp.vmcps.sandbox_service import get_sandbox_service

        sandbox_service = get_sandbox_service()
        sandbox_path = sandbox_service.get_sandbox_path(vmcp_id)
        full_script_path = sandbox_path / script_path
        
        if not full_script_path.exists():
            return DynamicToolOutput(
                result={"error": f"Script not found: {script_path}"},  # Don't include 'success' field
                stdout="",
                stderr=f"Sandbox tool script not found: {script_path}. The tool file may have been deleted or moved."
            )

        # Get venv Python
        venv_python_path = sandbox_path / ".venv" / "bin" / "python"
        if not venv_python_path.exists():
            venv_python_path = sandbox_path / ".venv" / "Scripts" / "python.exe"
        venv_python = str(venv_python_path) if venv_python_path.exists() else "python3"
        
        # Write arguments to JSON file
        args_file = sandbox_path / "temp_tool_args.json"
        with open(args_file, 'w') as f:
            json.dump(arguments, f)
        
        sandbox_dir_str = str(sandbox_path)
        
        # Inner script that executes the tool
        inner_code = f"""
import sys
import json
import inspect
import pathlib
import os
import asyncio

sandbox_path_str = '{sandbox_dir_str}'
if sandbox_path_str not in sys.path:
    sys.path.insert(0, sandbox_path_str)

args_path = '{str(args_file)}'
try:
    with open(args_path, 'r') as f:
        args = json.load(f)
except Exception as e:
    print(json.dumps({{'success': False, 'error': f'Failed to load arguments: {{e}}'}}))
    sys.exit(1)

script_path_str = '{str(full_script_path)}'
script_path = pathlib.Path(script_path_str)
g = {{}}
try:
    exec(compile(script_path.read_text(), str(script_path), 'exec'), g)
except Exception as e:
    print(json.dumps({{'success': False, 'error': f'Failed to load tool script: {{e}}'}}))
    sys.exit(1)

main = g.get('main')
if main and callable(main):
    try:
        import sys
        from io import StringIO
        
        sig = inspect.signature(main)
        
        # Build filtered args with default values
        filtered = {{}}
        for param_name, param in sig.parameters.items():
            if param_name in args:
                filtered[param_name] = args[param_name]
            elif param.default != inspect.Parameter.empty:
                # Use default value if parameter not provided
                filtered[param_name] = param.default
        
        # Capture user print statements separately from JSON result
        user_output = StringIO()
        original_stdout = sys.stdout
        
        try:
            sys.stdout = user_output
            if inspect.iscoroutinefunction(main):
                res = asyncio.run(main(**filtered))
            else:
                res = main(**filtered)
            user_prints = user_output.getvalue()
        finally:
            sys.stdout = original_stdout
        
        # Convert Pydantic models to dict before JSON serialization
        from pydantic import BaseModel
        if isinstance(res, BaseModel):
            res = res.model_dump() if hasattr(res, 'model_dump') else res.dict()
        
        # Print user output to stdout, then JSON result as last line
        if user_prints:
            print(user_prints, end='')
        # Print JSON result as the last line in stdout
        print(json.dumps({{'success': True, 'result': res}}))
    except Exception as e:
        # Restore stdout if it was redirected
        try:
            if 'original_stdout' in locals():
                sys.stdout = original_stdout
        except:
            pass
        # Errors go to stderr
        print(str(e), file=sys.stderr)
        # But we still need JSON result in stdout for parsing
        print(json.dumps({{'success': False, 'error': f'Tool execution error: {{e}}'}}))
else:
    print(json.dumps({{'success': False, 'error': 'No main() function found'}}), file=sys.stderr)
"""
        
        inner_b64 = base64.b64encode(inner_code.encode('utf-8')).decode('utf-8')
        target_command = f"{venv_python} -c \"import base64; exec(base64.b64decode('{inner_b64}').decode('utf-8'))\""
        
        # Execute in sandbox
        original_cwd = os.getcwd()
        os.chdir(str(sandbox_path))
        
        try:
            process = await asyncio.create_subprocess_shell(
                target_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(sandbox_path)
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60
            )
            
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")
            
            # Parse result from stdout (JSON is the last line, user prints are before it)
            # Split stdout into user prints and JSON result
            stdout_lines = stdout_str.strip().split('\n')
            user_prints = ""
            result_data = None
            
            if stdout_lines:
                # Try to parse the last line as JSON
                try:
                    result_data = json.loads(stdout_lines[-1])
                    # If successful, everything before the last line is user prints
                    if len(stdout_lines) > 1:
                        user_prints = '\n'.join(stdout_lines[:-1]) + '\n'
                    else:
                        user_prints = ""
                except json.JSONDecodeError:
                    # Last line is not JSON, try parsing entire stdout as JSON (backward compatibility)
                    try:
                        result_data = json.loads(stdout_str.strip())
                        user_prints = ""
                    except json.JSONDecodeError:
                        result_data = {"success": False, "error": "Failed to parse result", "raw_output": stdout_str}
                        user_prints = stdout_str
            
            # Extract result from result_data (don't include 'success' field in result)
            if result_data and result_data.get('success', False):
                result = result_data.get('result', {})
            else:
                error_msg = result_data.get('error', 'Unknown error') if result_data else 'Failed to parse result'
                result = {"error": error_msg}  # Don't include 'success' field
            
            # Update stdout_str to only contain user prints
            stdout_str = user_prints
            
            return DynamicToolOutput(
                result=result,
                stdout=stdout_str,
                stderr=stderr_str
            )
            
        except asyncio.TimeoutError:
            return DynamicToolOutput(
                result={"error": "Tool execution timed out"},  # Don't include 'success' field
                stdout="",
                stderr="Tool execution timed out after 60 seconds"
            )
        finally:
            os.chdir(original_cwd)
            try:
                args_file.unlink()
            except:
                pass
                
    except Exception as e:
        logger.error(f"Error executing dynamic tool: {e}", exc_info=True)
        return DynamicToolOutput(
            result={"error": str(e)},  # Don't include 'success' field
            stdout="",
            stderr=f"Error executing dynamic tool: {str(e)}"
        )


async def execute_sandbox_discovered_tool(
    vmcp_id: str,
    script_path: str,
    arguments: Dict[str, Any],
    environment_variables: Dict[str, Any],
    tool_as_prompt: bool = False,
    skip_sandbox: bool = False
) -> Union[CallToolResult, GetPromptResult]:
    """
    Execute a sandbox-discovered tool script in the sandbox environment.
    Uses SandboxManager for isolation and sandbox's venv Python.

    Args:
        vmcp_id: The vMCP ID
        script_path: Relative path to the script from sandbox root
        arguments: Tool arguments dictionary
        environment_variables: Environment variables dictionary
        tool_as_prompt: Whether to return as prompt result

    Returns:
        CallToolResult or GetPromptResult
    """
    logger.info(f"🏖️  SANDBOX_TOOL: Executing sandbox tool - vmcp_id={vmcp_id}, script_path={script_path}, arguments={arguments}")
    
    try:
        from vmcp.vmcps.sandbox_service import get_sandbox_service

        sandbox_service = get_sandbox_service()
        sandbox_path = sandbox_service.get_sandbox_path(vmcp_id)
        full_script_path = sandbox_path / script_path
        
        logger.info(f"🏖️  SANDBOX_TOOL: Sandbox path: {sandbox_path}, Full script path: {full_script_path}")

        if not full_script_path.exists():
            error_msg = f"Sandbox tool script not found: {script_path}. The tool file may have been deleted or moved."
            error_result = {"error": error_msg}
            structured_output: Dict[str, Any] = {
                "result": error_result,
                "stdout": "",
                "stderr": error_msg
            }
            error_text = json.dumps(structured_output, indent=2)
            return CallToolResult(
                content=[TextContent(type="text", text=error_text, annotations=None, _meta=None)],
                structuredContent=structured_output,
                isError=True
            )

        # Get venv Python
        venv_python_path = sandbox_path / ".venv" / "bin" / "python"
        if not venv_python_path.exists():
            venv_python_path = sandbox_path / ".venv" / "Scripts" / "python.exe"
        if venv_python_path.exists():
            venv_python = str(venv_python_path)
        else:
            venv_python = "python3"

        # Write arguments to JSON file for safe passing
        args_file = sandbox_path / "temp_tool_args.json"
        
        with open(args_file, 'w') as f:
            json.dump(arguments, f)

        # Initialize sandbox config keys/paths for the outer script
        sandbox_dir_str = str(sandbox_path)
        
        # ------------------------------------------------------------------
        # INNER SCRIPT: The code that runs the actual tool logic
        # ------------------------------------------------------------------
        # This runs INSIDE the sandbox environment (bubwrap).
        # It needs to load args, import the tool script, and call main().
        # Supports both sync and async main() functions.
        inner_code = f"""
import sys
import json
import inspect
import pathlib
import os
import asyncio

# Add sandbox path to sys.path so we can import the tool
sandbox_path_str = '{sandbox_dir_str}'
if sandbox_path_str not in sys.path:
    sys.path.insert(0, sandbox_path_str)

# Load arguments
args_path = '{str(args_file)}'
try:
    with open(args_path, 'r') as f:
        args = json.load(f)
except Exception as e:
    print(json.dumps({{'success': False, 'error': f'Failed to load arguments: {{e}}'}}))
    sys.exit(1)

# Import tool script
script_path_str = '{str(full_script_path)}'
script_path = pathlib.Path(script_path_str)
g = {{}}
try:
    exec(compile(script_path.read_text(), str(script_path), 'exec'), g)
except Exception as e:
    print(json.dumps({{'success': False, 'error': f'Failed to load tool script: {{e}}'}}))
    sys.exit(1)

# Call main
main = g.get('main')
if main and callable(main):
    try:
        import sys
        from io import StringIO
        
        sig = inspect.signature(main)
        
        # Build filtered args with default values
        filtered = {{}}
        for param_name, param in sig.parameters.items():
            if param_name in args:
                filtered[param_name] = args[param_name]
            elif param.default != inspect.Parameter.empty:
                # Use default value if parameter not provided
                filtered[param_name] = param.default
        
        # Capture user print statements separately from JSON result
        user_output = StringIO()
        original_stdout = sys.stdout
        
        try:
            sys.stdout = user_output
            # Check if main is async
            if inspect.iscoroutinefunction(main):
                # Execute async main
                res = asyncio.run(main(**filtered))
            else:
                # Execute sync main
                res = main(**filtered)
            user_prints = user_output.getvalue()
        finally:
            sys.stdout = original_stdout
        
        # Convert Pydantic models to dict before JSON serialization
        from pydantic import BaseModel
        if isinstance(res, BaseModel):
            res = res.model_dump() if hasattr(res, 'model_dump') else res.dict()
        
        # Print user output to stdout, JSON result to stderr
        if user_prints:
            print(user_prints, end='')
        print(json.dumps({{'success': True, 'result': res}}), file=sys.stderr)
    except Exception as e:
        # Restore stdout if it was redirected
        try:
            if 'original_stdout' in locals():
                sys.stdout = original_stdout
        except:
            pass
        print(json.dumps({{'success': False, 'error': f'Tool execution error: {{e}}'}}), file=sys.stderr)
else:
    print(json.dumps({{'success': False, 'error': 'No main() function found'}}), file=sys.stderr)
"""
        # Base64 encode the inner code to avoid escaping hell when passing to python -c
        inner_b64 = base64.b64encode(inner_code.encode('utf-8')).decode('utf-8')
        
        # The command that the sandbox manager will wrap
        # This effectively runs: python -c "exec(b64decode(...))"
        target_command = f"{venv_python} -c \"import base64; exec(base64.b64decode('{inner_b64}').decode('utf-8'))\""

        # ------------------------------------------------------------------
        # SKIP SANDBOX MODE: Execute directly without nested sandboxing
        # ------------------------------------------------------------------
        # When skip_sandbox=True, we're already inside a sandbox (called via SDK)
        # so we skip the outer SandboxManager wrapper to avoid nested sandbox-exec
        if skip_sandbox:
            logger.info(f"🏖️  SANDBOX_TOOL: skip_sandbox=True, executing tool directly without nested sandbox wrapper")
            
            # Change to sandbox directory for the execution context
            original_cwd = os.getcwd()
            os.chdir(str(sandbox_path))
            
            try:
                # Execute the inner command directly (no outer sandbox wrapper)
                process = await asyncio.create_subprocess_shell(
                    target_command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(sandbox_path)
                )
                
                stdout, stderr = await process.communicate()
                
                # Parse result
                stdout_str = stdout.decode("utf-8", errors="replace")
                stderr_str = stderr.decode("utf-8", errors="replace")
                
                # Parse result_data from stdout (JSON is the last line, user prints are before it)
                # Split stdout into user prints and JSON result
                stdout_lines = stdout_str.strip().split('\n')
                user_prints = ""
                result_data = None
                
                if stdout_lines:
                    # Try to parse the last line as JSON
                    try:
                        result_data = json.loads(stdout_lines[-1])
                        # If successful, everything before the last line is user prints
                        if len(stdout_lines) > 1:
                            user_prints = '\n'.join(stdout_lines[:-1]) + '\n'
                        else:
                            user_prints = ""
                    except json.JSONDecodeError:
                        # Last line is not JSON, try parsing entire stdout as JSON (backward compatibility)
                        try:
                            result_data = json.loads(stdout_str.strip())
                            user_prints = ""
                        except json.JSONDecodeError:
                            result_data = {"success": False, "error": "Failed to parse result", "raw_output": stdout_str}
                            user_prints = stdout_str
                
                # Update stdout_str to only contain user prints
                stdout_str = user_prints
                
                is_error = bool(process.returncode != 0 or (result_data and not result_data.get('success', False)))
                
                # Extract actual return value
                if result_data and result_data.get('success', False):
                    actual_result = result_data.get('result')
                else:
                    error_msg = result_data.get('error', 'Unknown error') if result_data else 'Failed to parse result'
                    actual_result = {"error": error_msg}
                
                # Create structured output dict: {"result": ..., "stdout": ..., "stderr": ...}
                structured_output: Dict[str, Any] = {
                    "result": actual_result,
                    "stdout": stdout_str,
                    "stderr": stderr_str
                }
                
                # Create JSON object for text content (same structure)
                text_content_json = json.dumps(structured_output, indent=2)
                
                if tool_as_prompt:
                    combined_content = TextContent(
                        type="text",
                        text=text_content_json,
                        annotations=None,
                        _meta=None
                    )
                    return GetPromptResult(
                        description="Tool executed successfully",
                        messages=[PromptMessage(role="user", content=combined_content)]
                    )
                
                # Return with structuredContent containing the full output structure
                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text=text_content_json,
                        annotations=None,
                        _meta=None
                    )],
                    structuredContent=structured_output,  # Full structure: {result, stdout, stderr}
                    isError=is_error
                )
                    
            finally:
                # Always restore CWD
                os.chdir(original_cwd)
                # Clean up temp args file
                try:
                    args_file.unlink()
                except:
                    pass

        # ------------------------------------------------------------------
        # OUTER SCRIPT: The code that sets up SandboxManager and runs the tool
        # ------------------------------------------------------------------
        # This runs in the sandbox VENV (uncaged), so it has access to SandboxManager.
        outer_code = f"""
import asyncio
import os
import sys
from pathlib import Path
import json

# Try to import SandboxManager (available in venv)
try:
    from sandbox_runtime import SandboxManager
    from sandbox_runtime.config.schemas import SandboxRuntimeConfig
except ImportError as e:
    print(json.dumps({{'success': False, 'error': f'Failed to import sandbox_runtime: {{e}}'}}))
    sys.exit(1)

async def run_sandboxed():
    sandbox_dir_str = '{sandbox_dir_str}'
    
    # Configure sandbox
    allow_read_paths = [
        sandbox_dir_str,
        "/usr/lib", "/System/Library", "/Library/Frameworks", 
        "/usr/bin", "/bin", "/lib", "/lib64"
    ]
    
    sandbox_config = SandboxRuntimeConfig.from_json({{
        "network": {{
            "allowedDomains": [], 
            "deniedDomains": []
        }},
        "filesystem": {{
            "allowRead": allow_read_paths,
            "allowWrite": [sandbox_dir_str],
            "denyWrite": []
        }}
    }})
    
    await SandboxManager.initialize(sandbox_config)
    
    # Wrap the command
    cmd_str = {repr(target_command)}
    
    try:
        sandboxed_cmd = await SandboxManager.wrap_with_sandbox(
            cmd_str, 
            bin_shell="bash", 
            sandbox_dir=sandbox_dir_str
        )
        
        # Prepare env
        env = os.environ.copy()
        # Filter proxy vars
        for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
            env.pop(var, None)
            
        # Execute
        proc = await asyncio.create_subprocess_shell(
            sandboxed_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=sandbox_dir_str,
            env=env
        )
        
        stdout, stderr = await proc.communicate()
        
        # Forward output directly
        sys.stdout.buffer.write(stdout)
        sys.stderr.buffer.write(stderr)
        sys.exit(proc.returncode or 0)
        
    except Exception as e:
        print(f"Outer wrapper error: {{e}}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_sandboxed())
"""
        # Base64 encode the outer code as well
        outer_b64 = base64.b64encode(outer_code.encode('utf-8')).decode('utf-8')
        
        # Final execution command: Backends runs venv python -> Outer Script -> Sandbox Setup -> Wrapped Tool Script
        final_command = f"{venv_python} -c \"import base64; exec(base64.b64decode('{outer_b64}').decode('utf-8'))\""

        # Change to sandbox directory for the execution context
        original_cwd = os.getcwd()
        os.chdir(str(sandbox_path))

        try:
            # Execute
            process = await asyncio.create_subprocess_shell(
                final_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(sandbox_path)
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=60
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                timeout_msg = "Tool execution timed out after 60 seconds"
                timeout_result = {"error": timeout_msg}
                structured_output: Dict[str, Any] = {
                    "result": timeout_result,
                    "stdout": "",
                    "stderr": timeout_msg
                }
                timeout_text = json.dumps(structured_output, indent=2)
                return CallToolResult(
                    content=[TextContent(type="text", text=timeout_text, annotations=None, _meta=None)],
                    structuredContent=structured_output,
                    isError=True
                )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            # Check for sandbox violation patterns in stderr
            sandbox_violation_patterns = [
                "Operation not permitted",
                "sandbox violation",
                "deny",
                "EPERM"
            ]
            if any(pattern.lower() in stderr_str.lower() for pattern in sandbox_violation_patterns):
                stderr_str = f"⚠️ SANDBOX RESTRICTION: {stderr_str}"

            # Parse result_data from stdout (JSON is the last line, user prints are before it)
            # Split stdout into user prints and JSON result
            stdout_lines = stdout_str.strip().split('\n')
            user_prints = ""
            result_data = None
            
            if stdout_lines:
                # Try to parse the last line as JSON
                try:
                    result_data = json.loads(stdout_lines[-1])
                    # If successful, everything before the last line is user prints
                    if len(stdout_lines) > 1:
                        user_prints = '\n'.join(stdout_lines[:-1]) + '\n'
                    else:
                        user_prints = ""
                except json.JSONDecodeError:
                    # Last line is not JSON, try parsing entire stdout as JSON (backward compatibility)
                    try:
                        result_data = json.loads(stdout_str.strip())
                        user_prints = ""
                    except json.JSONDecodeError:
                        result_data = {"success": False, "error": "Failed to parse result", "raw_output": stdout_str}
                        user_prints = stdout_str
            
            # Update stdout_str to only contain user prints
            stdout_str = user_prints
            
            is_error = bool(process.returncode != 0 or (result_data and not result_data.get('success', False)))
            
            # Extract actual return value
            if result_data and result_data.get('success', False):
                actual_result = result_data.get('result')
            else:
                error_msg = result_data.get('error', 'Unknown error') if result_data else 'Failed to parse result'
                actual_result = {"error": error_msg}
            
            # Create structured output dict: {"result": ..., "stdout": ..., "stderr": ...}
            structured_output: Dict[str, Any] = {
                "result": actual_result,
                "stdout": stdout_str,
                "stderr": stderr_str
            }
            text_content_json = json.dumps(structured_output, indent=2)

            if tool_as_prompt:
                combined_content = TextContent(
                    type="text",
                    text=text_content_json,
                    annotations=None,
                    _meta=None
                )
                prompt_message = PromptMessage(
                    role="user",
                    content=combined_content
                )
                return GetPromptResult(
                    description="Sandbox tool execution result",
                    messages=[prompt_message]
                )

            # Return with structuredContent containing the full output structure
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=text_content_json,
                    annotations=None,
                    _meta=None
                )],
                structuredContent=structured_output,  # Full structure: {result, stdout, stderr}
                isError=is_error
            )

        finally:
            os.chdir(original_cwd)
            try:
                args_file.unlink()
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Error executing sandbox tool: {e}", exc_info=True)
        
        # Generate descriptive error message for LLM
        exc_type = type(e).__name__
        exc_str = str(e)
        
        if "ModuleNotFoundError" in exc_type:
            error_msg = f"Sandbox tool execution failed: Missing Python module. Error: {exc_str}. The tool may require additional dependencies to be installed in the sandbox environment."
        elif "PermissionError" in exc_type:
            error_msg = f"Sandbox tool execution failed: Permission denied. Error: {exc_str}. The tool may be trying to access files or resources outside its sandbox."
        elif "FileNotFoundError" in exc_type:
            error_msg = f"Sandbox tool execution failed: File not found. Error: {exc_str}. A required file may have been deleted or moved."
        elif "TimeoutError" in exc_type or "timeout" in exc_str.lower():
            error_msg = f"Sandbox tool execution timed out. Error: {exc_str}. The tool took too long to complete."
        elif "ConnectionError" in exc_type or "connection" in exc_str.lower():
            error_msg = f"Sandbox tool execution failed: Connection error. Error: {exc_str}. The tool may be trying to access a network resource that is unavailable."
        else:
            error_msg = f"Sandbox tool execution failed. Error type: {exc_type}. Details: {exc_str}"
        
        error_result = {"error": error_msg}
        structured_output: Dict[str, Any] = {
            "result": error_result,
            "stdout": "",
            "stderr": error_msg
        }
        error_text = json.dumps(structured_output, indent=2)
        return CallToolResult(
            content=[TextContent(type="text", text=error_text, annotations=None, _meta=None)],
            structuredContent=structured_output,
            isError=True
        )

