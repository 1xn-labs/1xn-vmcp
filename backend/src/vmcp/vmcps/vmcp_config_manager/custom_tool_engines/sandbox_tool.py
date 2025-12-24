#!/usr/bin/env python3
"""
Sandbox Tool Engine
===================

Execution engine for sandbox-discovered Python tools.
These tools are Python scripts stored in vmcp_tools/ directory and executed
in the sandbox environment using unified Python executor.
"""

import logging
from typing import Dict, Any, Optional, Union

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
        from .unified_python_executor import execute_python_in_sandbox
        
        # Call unified executor
        result = await execute_python_in_sandbox(
            vmcp_id=vmcp_id,
            script_path=script_path,
            arguments=arguments,
            environment_variables={},
            tool_as_prompt=False,
            skip_sandbox=False
        )
        
        # Convert CallToolResult to DynamicToolOutput
        if isinstance(result, CallToolResult):
            structured = result.structuredContent or {}
            return DynamicToolOutput(
                result=structured.get('result', {}),
                stdout=structured.get('stdout', ''),
                stderr=structured.get('stderr', '')
            )
        else:
            # Should not happen, but handle gracefully
            return DynamicToolOutput(
                result={"error": "Unexpected result type"},
                stdout="",
                stderr="Unexpected result type from unified executor"
            )
                
    except Exception as e:
        logger.error(f"Error executing dynamic tool: {e}", exc_info=True)
        return DynamicToolOutput(
            result={"error": str(e)},
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
    Uses unified Python executor for consistent execution.

    Args:
        vmcp_id: The vMCP ID
        script_path: Relative path to the script from sandbox root
        arguments: Tool arguments dictionary
        environment_variables: Environment variables dictionary
        tool_as_prompt: Whether to return as prompt result
        skip_sandbox: Skip sandbox wrapping (for nested calls)

    Returns:
        CallToolResult or GetPromptResult
    """
    logger.info(f"🏖️  SANDBOX_TOOL: Executing sandbox tool via unified executor - vmcp_id={vmcp_id}, script_path={script_path}, arguments={arguments}")
    
    # Use unified executor (same as Python tools now)
    from .unified_python_executor import execute_python_in_sandbox
    return await execute_python_in_sandbox(
        vmcp_id=vmcp_id,
        script_path=script_path,
        arguments=arguments,
        environment_variables=environment_variables,
        tool_as_prompt=tool_as_prompt,
        skip_sandbox=skip_sandbox
    )
