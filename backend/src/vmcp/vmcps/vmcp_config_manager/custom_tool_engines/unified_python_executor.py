#!/usr/bin/env python3
"""
Unified Python Executor
=======================

Unified execution engine for all Python tools (both inline and file-based).
All Python code execution runs in the sandbox with SandboxManager isolation.
"""

import asyncio
import json
import os
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, Union

from mcp.types import TextContent, PromptMessage, GetPromptResult, CallToolResult

from vmcp.vmcps.sandbox_service import get_sandbox_service
from sandbox_runtime import SandboxManager
from sandbox_runtime.config.schemas import SandboxRuntimeConfig

logger = logging.getLogger("1xN_vMCP_UNIFIED_PYTHON")


async def execute_python_in_sandbox(
    vmcp_id: str,
    script_path: str,
    arguments: Dict[str, Any],
    environment_variables: Dict[str, Any],
    tool_as_prompt: bool = False,
    skip_sandbox: bool = False
) -> Union[CallToolResult, GetPromptResult]:
    """
    Execute a Python tool script in the sandbox environment.
    
    This is the unified executor for all Python tools:
    - Python tools created via UI (stored in vmcp_tools/)
    - Sandbox-discovered tools (stored in vmcp_tools/)
    
    Args:
        vmcp_id: The vMCP ID
        script_path: Relative path to the script from sandbox root (e.g., "vmcp_tools/tool_name.py")
        arguments: Tool arguments dictionary
        environment_variables: Environment variables dictionary
        tool_as_prompt: Whether to return as prompt result
        skip_sandbox: Skip sandbox wrapping (for nested calls)
        
    Returns:
        CallToolResult or GetPromptResult
    """
    logger.info(f"🐍 UNIFIED_PYTHON: Executing Python tool - vmcp_id={vmcp_id}, script_path={script_path}, arguments={arguments}")
    
    try:
        sandbox_service = get_sandbox_service()
        sandbox_path = sandbox_service.get_sandbox_path(vmcp_id)
        full_script_path = sandbox_path / script_path
        
        logger.info(f"🐍 UNIFIED_PYTHON: Sandbox path: {sandbox_path}, Full script path: {full_script_path}")
        
        if not full_script_path.exists():
            error_msg = f"Python tool script not found: {script_path}. The tool file may have been deleted or moved."
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
        
        # Write arguments to JSON file
        args_file = sandbox_path / "temp_tool_args.json"
        with open(args_file, 'w') as f:
            json.dump(arguments, f)
        
        # Create .tmp directory for result files
        tmp_dir = sandbox_path / ".tmp"
        tmp_dir.mkdir(exist_ok=True)
        
        # Create unique result file
        result_file = tmp_dir / f"temp_tool_result_{uuid.uuid4().hex}.json"
        
        sandbox_dir_str = str(sandbox_path)
        
        # Create wrapper script that loads the tool script and executes it
        wrapper_code = f"""
import sys
import json
import inspect
import pathlib
import os
import asyncio
from io import StringIO

# Add sandbox path to sys.path
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

# Load tool script
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
        sig = inspect.signature(main)
        
        # Helper function to convert argument to correct type
        def convert_arg_to_type(value, param):
            if value is None:
                return param.default if param.default != inspect.Parameter.empty else None
            
            param_type = param.annotation
            if param_type == inspect.Parameter.empty:
                return value
            
            # Handle Optional types
            import typing
            if hasattr(typing, 'get_origin') and hasattr(typing, 'get_args'):
                origin = typing.get_origin(param_type)
                if origin is typing.Union:
                    args = typing.get_args(param_type)
                    if len(args) == 2 and type(None) in args:
                        param_type = args[0] if args[0] is not type(None) else args[1]
            
            # Convert based on type
            try:
                if param_type == int or param_type == 'int':
                    return int(value)
                elif param_type == float or param_type == 'float':
                    return float(value)
                elif param_type == bool or param_type == 'bool':
                    if isinstance(value, str):
                        return value.lower() in ('true', '1', 'yes', 'on')
                    return bool(value)
                elif param_type == str or param_type == 'str':
                    return str(value)
                else:
                    return value
            except (ValueError, TypeError):
                return param.default if param.default != inspect.Parameter.empty else value
        
        # Build filtered args with default values and type conversion
        filtered = {{}}
        for param_name, param in sig.parameters.items():
            if param_name in args:
                filtered[param_name] = convert_arg_to_type(args[param_name], param)
            elif param.default != inspect.Parameter.empty:
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
        
        # Print user output to stdout (only prints/logs, no JSON)
        if user_prints:
            print(user_prints, end='')
        # Write result to file
        result_path = '{str(result_file)}'
        with open(result_path, 'w') as f:
            json.dump({{'success': True, 'result': res}}, f)
    except Exception as e:
        # Restore stdout if it was redirected
        try:
            if 'original_stdout' in locals():
                sys.stdout = original_stdout
        except:
            pass
        # Errors go to stderr
        print(str(e), file=sys.stderr)
        # Write error to file
        result_path = '{str(result_file)}'
        with open(result_path, 'w') as f:
            json.dump({{'success': False, 'error': f'Tool execution error: {{e}}'}}, f)
else:
    # Write error to file
    result_path = '{str(result_file)}'
    with open(result_path, 'w') as f:
        json.dump({{'success': False, 'error': 'No main() function found'}}, f)
"""
        
        # Write wrapper to temp file
        wrapper_file = tmp_dir / f"tool_wrapper_{uuid.uuid4().hex}.py"
        wrapper_file.write_text(wrapper_code)
        
        # Command to execute the wrapper
        target_command = f"{venv_python} {str(wrapper_file)}"
        
        # Skip sandbox mode: Execute directly without SandboxManager wrapper
        if skip_sandbox:
            logger.info(f"🐍 UNIFIED_PYTHON: skip_sandbox=True, executing tool directly")
            
            original_cwd = os.getcwd()
            os.chdir(str(sandbox_path))
            
            try:
                process = await asyncio.create_subprocess_shell(
                    target_command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(sandbox_path)
                )
                
                stdout, stderr = await process.communicate()
                
                stdout_str = stdout.decode("utf-8", errors="replace").strip()
                stderr_str = stderr.decode("utf-8", errors="replace")
                
                # Read result from file
                result_data = None
                if result_file.exists():
                    try:
                        with open(result_file, 'r') as f:
                            result_data = json.load(f)
                    except Exception as e:
                        logger.warning(f"Failed to read result file: {e}")
                        result_data = None
                
                is_error = bool(process.returncode != 0 or (result_data and not result_data.get('success', False)))
                
                # Extract actual return value
                if result_data and result_data.get('success', False):
                    actual_result = result_data.get('result')
                else:
                    error_msg = result_data.get('error', 'Unknown error') if result_data else 'Failed to parse result'
                    actual_result = {"error": error_msg}
                
                # Create structured output
                structured_output: Dict[str, Any] = {
                    "result": actual_result,
                    "stdout": stdout_str,
                    "stderr": stderr_str
                }
                
                text_content_json = json.dumps(structured_output, indent=2)
                
                if tool_as_prompt:
                    return GetPromptResult(
                        description="Tool executed successfully",
                        messages=[PromptMessage(role="user", content=TextContent(
                            type="text",
                            text=text_content_json,
                            annotations=None,
                            _meta=None
                        ))]
                    )
                
                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text=text_content_json,
                        annotations=None,
                        _meta=None
                    )],
                    structuredContent=structured_output,
                    isError=is_error
                )
                    
            finally:
                os.chdir(original_cwd)
                # Clean up temp files
                try:
                    args_file.unlink()
                except:
                    pass
                try:
                    result_file.unlink()
                except:
                    pass
                try:
                    wrapper_file.unlink()
                except:
                    pass
        
        # Normal mode: Wrap with SandboxManager
        # Create outer script that sets up SandboxManager
        outer_code = f"""
import asyncio
import os
import sys
from pathlib import Path
import json

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
    wrapper_file_str = '{str(wrapper_file)}'
    cmd_str = '{venv_python} ' + wrapper_file_str
    
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
        
        # Write outer script to temp file
        outer_file = tmp_dir / f"tool_outer_{uuid.uuid4().hex}.py"
        outer_file.write_text(outer_code)
        
        # Final command: Execute outer script with venv Python
        final_command = f"{venv_python} {str(outer_file)}"
        
        original_cwd = os.getcwd()
        os.chdir(str(sandbox_path))
        
        try:
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
            
            stdout_str = stdout.decode("utf-8", errors="replace").strip()
            stderr_str = stderr.decode("utf-8", errors="replace")
            
            # Check for sandbox violation patterns
            sandbox_violation_patterns = [
                "Operation not permitted",
                "sandbox violation",
                "deny",
                "EPERM"
            ]
            if any(pattern.lower() in stderr_str.lower() for pattern in sandbox_violation_patterns):
                stderr_str = f"⚠️ SANDBOX RESTRICTION: {stderr_str}"
            
            # Read result from file
            result_data = None
            if result_file.exists():
                try:
                    with open(result_file, 'r') as f:
                        result_data = json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to read result file: {e}")
                    result_data = None
            
            is_error = bool(process.returncode != 0 or (result_data and not result_data.get('success', False)))
            
            # Extract actual return value
            if result_data and result_data.get('success', False):
                actual_result = result_data.get('result')
            else:
                error_msg = result_data.get('error', 'Unknown error') if result_data else 'Failed to parse result'
                actual_result = {"error": error_msg}
            
            # Create structured output
            structured_output: Dict[str, Any] = {
                "result": actual_result,
                "stdout": stdout_str,
                "stderr": stderr_str
            }
            text_content_json = json.dumps(structured_output, indent=2)
            
            if tool_as_prompt:
                return GetPromptResult(
                    description="Python tool execution result",
                    messages=[PromptMessage(role="user", content=TextContent(
                        type="text",
                        text=text_content_json,
                        annotations=None,
                        _meta=None
                    ))]
                )
            
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=text_content_json,
                    annotations=None,
                    _meta=None
                )],
                structuredContent=structured_output,
                isError=is_error
            )
            
        finally:
            os.chdir(original_cwd)
            # Clean up temp files
            try:
                args_file.unlink()
            except:
                pass
            try:
                result_file.unlink()
            except:
                pass
            try:
                wrapper_file.unlink()
            except:
                pass
            try:
                outer_file.unlink()
            except:
                pass
                
    except Exception as e:
        logger.error(f"Error executing Python tool: {e}", exc_info=True)
        
        exc_type = type(e).__name__
        exc_str = str(e)
        
        if "ModuleNotFoundError" in exc_type:
            error_msg = f"Python tool execution failed: Missing Python module. Error: {exc_str}."
        elif "PermissionError" in exc_type:
            error_msg = f"Python tool execution failed: Permission denied. Error: {exc_str}."
        elif "FileNotFoundError" in exc_type:
            error_msg = f"Python tool execution failed: File not found. Error: {exc_str}."
        elif "TimeoutError" in exc_type or "timeout" in exc_str.lower():
            error_msg = f"Python tool execution timed out. Error: {exc_str}."
        else:
            error_msg = f"Python tool execution failed. Error type: {exc_type}. Details: {exc_str}"
        
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

