#!/usr/bin/env python3
"""
Agent Configuration Manager
===========================

This module manages agent configurations and modifies MCP server behavior
based on active agent settings. It reads agent JSON configs from ~/.1xn/agents/
and applies custom prompts, tools, context, and resources.

**REFACTORED STRUCTURE:**
==========================
This file has been refactored into a modular package structure located in the
`vmcp_config_manager/` directory. This file now serves as a backward-compatible
facade to maintain existing imports without requiring code changes.

The original 3311-line monolithic file has been broken down into:
- config_core.py - Main VMCPConfigManager orchestrator class
- protocol_handler.py - MCP protocol implementation (tools, resources, prompts)
- execution_core.py - Execution coordination (tool calls, prompt execution)
- resource_manager.py - Resource CRUD and fetching operations
- server_manager.py - Server installation and configuration
- template_parser.py - Template processing (@param, @config, @resource, @tool, @prompt)
- parameter_parser.py - Parameter parsing with AST
- logger.py - Background operation logging
- widget_utils.py - Widget utilities for UI integration
- custom_tool_engines/ - Prompt, Python, and HTTP tool execution engines

For implementation details, see:
- vmcp_config_manager/config_core.py - Main class
- vmcp_config_manager/ - All sub-modules
- REFACTORING_PLAN.md - Complete refactoring documentation
- REFACTORING_STATUS.md - Progress tracking
- REFACTORING_COMPLETION_GUIDE.md - Detailed completion instructions

Benefits of the refactored structure:
- Maintainability: ~200-700 line modules instead of 3311-line monolith
- Testability: Each module can be tested independently
- Reusability: Tool engines can be used in other contexts
- Clarity: Clear separation of concerns
- OSS-Ready: Professional structure suitable for open source release
"""

# Re-export everything from the new modular structure for backward compatibility
from .vmcp_config_manager import (
    MIME_TYPE,
    ReadResourceContents,
    UIWidget,
    VMCPConfigManager,
)

# Re-export for complete backward compatibility
__all__ = [
    'VMCPConfigManager',
    'UIWidget',
    'ReadResourceContents',
    'MIME_TYPE',
]

# Note: All existing code continues to work without changes:
# from vmcp.vmcps.vmcp_config_manger import VMCPConfigManager, UIWidget
# manager = VMCPConfigManager(user_id="test")
# All methods work exactly the same
