"""
Usage statistics tools for LLM MCP Server.
"""

import json
from typing import Optional

from llm_mcp.models import GetStatsInput
from llm_mcp.utils.stats_tracker import get_stats_tracker


async def get_stats(params: GetStatsInput) -> str:
    """
    Get usage statistics for LLM calls.

    This tool returns comprehensive statistics about:
    - Total calls, tokens, and costs
    - Statistics per model
    - Statistics per tool
    - Filtered by time period and/or model

    Args:
        params: Input parameters including:
            - time_period: Filter by time period ('hour', 'day', 'week', 'month', 'all')
            - model: Filter by specific model

    Returns:
        Usage statistics in JSON format.
    """
    tracker = get_stats_tracker()
    stats = tracker.get_stats(
        time_period=params.time_period,
        model=params.model,
    )

    # Format as markdown for better readability
    lines = ["# Usage Statistics", ""]

    # Summary
    summary = stats["summary"]
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Calls**: {summary['total_calls']:,}")
    lines.append(f"  - Successful: {summary['successful_calls']:,}")
    lines.append(f"  - Failed: {summary['failed_calls']:,}")
    lines.append("")
    lines.append(f"- **Total Tokens**: {summary['total_tokens']:,}")
    lines.append(f"  - Input: {summary['total_prompt_tokens']:,}")
    lines.append(f"  - Output: {summary['total_completion_tokens']:,}")
    lines.append("")
    lines.append(f"- **Total Cost**: ${summary['total_cost']:.6f}")
    if summary['total_calls'] > 0:
        lines.append(f"- **Average Cost per Call**: ${summary['average_cost_per_call']:.6f}")
    lines.append("")

    # Filters
    filters = stats["filters"]
    lines.append("## Filters")
    lines.append(f"- **Time Period**: {filters['time_period']}")
    lines.append(f"- **Model**: {filters['model']}")
    lines.append("")

    # By Model
    if stats["by_model"]:
        lines.append("## Statistics by Model")
        lines.append("")
        # Sort by total tokens
        sorted_models = sorted(
            stats["by_model"].items(),
            key=lambda x: x[1]["total_tokens"],
            reverse=True,
        )
        for model_id, model_stats in sorted_models[:10]:  # Top 10
            lines.append(f"### {model_id}")
            lines.append(f"- Calls: {model_stats['calls']:,} ({model_stats['successful']} successful, {model_stats['failed']} failed)")
            lines.append(f"- Tokens: {model_stats['total_tokens']:,} (input: {model_stats['prompt_tokens']:,}, output: {model_stats['completion_tokens']:,})")
            lines.append(f"- Cost: ${model_stats['cost']:.6f}")
            lines.append("")

    # By Tool
    if stats["by_tool"]:
        lines.append("## Statistics by Tool")
        lines.append("")
        # Sort by calls
        sorted_tools = sorted(
            stats["by_tool"].items(),
            key=lambda x: x[1]["calls"],
            reverse=True,
        )
        for tool_name, tool_stats in sorted_tools:
            lines.append(f"- **{tool_name}**: {tool_stats['calls']:,} calls, {tool_stats['total_tokens']:,} tokens, ${tool_stats['cost']:.6f}")
        lines.append("")

    # Also return JSON for programmatic access
    result = {
        "formatted": "\n".join(lines),
        "raw": stats,
    }

    return json.dumps(result, indent=2)
