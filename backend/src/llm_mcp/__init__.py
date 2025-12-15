"""
LLM MCP Server - A comprehensive MCP server for LLM operations.

This package provides a Model Context Protocol server with:
- Multi-provider LLM support via LiteLLM
- Structured output extraction
- Text analysis and transformation
- Multimodal capabilities (vision, PDF)
- Advanced reasoning tools
"""

__version__ = "1.0.0"

from llm_mcp.server import mcp, run_server
from llm_mcp.config import get_settings, LLMMCPSettings

__all__ = [
    "mcp",
    "run_server",
    "get_settings",
    "LLMMCPSettings",
    "__version__",
]
