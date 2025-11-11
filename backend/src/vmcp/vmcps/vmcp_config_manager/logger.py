#!/usr/bin/env python3
"""
vMCP Logger Module
==================

This module provides logging functionality for vMCP operations.
It handles background logging of agent operations including tool calls,
resource requests, and prompt requests.
"""

import logging
import asyncio
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any

from vmcp.storage.base import StorageBase


logger = logging.getLogger("1xN_vMCP_LOGGER")


async def log_vmcp_operation(
    storage: StorageBase,
    vmcp_id: str,
    vmcp_config: Any,
    user_id: str,
    logging_config: Dict[str, Any],
    operation_type: str,
    operation_id: str,
    arguments: Optional[Dict[str, Any]],
    result: Optional[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]]
) -> None:
    """
    Background task to log agent operations (tool calls, resource requests, prompt requests, etc.)

    Args:
        storage: Storage backend for saving logs
        vmcp_id: Virtual MCP identifier
        vmcp_config: Configuration object for the vMCP
        user_id: User identifier
        logging_config: Configuration dictionary for logging settings
        operation_type: Type of operation being logged
        operation_id: Unique identifier for the operation
        arguments: Operation arguments
        result: Operation result
        metadata: Additional metadata about the operation
    """
    try:
        # OSS - log_vmcp_operation_to_span disabled

        # ORIGINAL: Keep file logging as fallback/backup
        total_tools = vmcp_config.total_tools if vmcp_config else 0
        total_resources = vmcp_config.total_resources if vmcp_config else 0
        total_resource_templates = vmcp_config.total_resource_templates if vmcp_config else 0
        total_prompts = vmcp_config.total_prompts if vmcp_config else 0

        # Log the operation
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "method": operation_type,
            "agent_name": logging_config.get("agent_name", "unknown"),
            "agent_id": logging_config.get("agent_id", "unknown"),
            "user_id": user_id,
            "client_id": logging_config.get("client_id", "unknown"),
            "operation_id": operation_id,
            "mcp_server": metadata.get("server"),
            "mcp_method": operation_type,
            "original_name": metadata.get("tool") if operation_type in ["tool_call"] else metadata.get("prompt") if operation_type in ["prompt_get"] else metadata.get("resource") if operation_type in ["resource_read"] else operation_type,
            "arguments": arguments,
            "result": result.to_dict() if hasattr(result, 'to_dict') else str(result),
            "vmcp_id": vmcp_id,
            "vmcp_name": vmcp_config.name if vmcp_config else None,
            "total_tools": total_tools,
            "total_resources": total_resources,
            "total_resource_templates": total_resource_templates,
            "total_prompts": total_prompts
        }

        # Save to the appropriate log file with suffix
        storage.save_user_vmcp_logs(log_entry)
        logger.info(f"[BACKGROUND TASK LOGGING] Successfully logged {operation_type} for user {user_id} ({user_id})")
    except Exception as e:
        # Silently fail for logging - don't affect the main request
        logger.error(f"[BACKGROUND TASK LOGGING] Traceback: {traceback.format_exc()}")
        logger.error(f"[BACKGROUND TASK LOGGING] Could not log {operation_type} for user {user_id}: {e}")
