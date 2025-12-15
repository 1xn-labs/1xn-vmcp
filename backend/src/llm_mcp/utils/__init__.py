"""
Utility modules for the LLM MCP Server.
"""

from llm_mcp.utils.errors import (
    LLMMCPError,
    ValidationError,
    AuthenticationError,
    ProviderError,
    RateLimitError,
    ModelNotFoundError,
    TimeoutError,
    ContentFilterError,
    UnsupportedFeatureError,
    handle_litellm_error,
    format_error_response,
)
from llm_mcp.utils.formatting import (
    format_json_response,
    format_markdown_response,
    format_model_list,
    format_comparison_result,
    format_entity_extraction,
    format_analysis_result,
    calculate_cost,
    truncate_text,
)
from llm_mcp.utils.stats_tracker import StatsTracker, get_stats_tracker

__all__ = [
    # Errors
    "LLMMCPError",
    "ValidationError",
    "AuthenticationError",
    "ProviderError",
    "RateLimitError",
    "ModelNotFoundError",
    "TimeoutError",
    "ContentFilterError",
    "UnsupportedFeatureError",
    "handle_litellm_error",
    "format_error_response",
    # Formatting
    "format_json_response",
    "format_markdown_response",
    "format_model_list",
    "format_comparison_result",
    "format_entity_extraction",
    "format_analysis_result",
    "calculate_cost",
    "truncate_text",
    # Stats
    "StatsTracker",
    "get_stats_tracker",
]
