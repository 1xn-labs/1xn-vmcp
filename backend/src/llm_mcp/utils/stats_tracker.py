"""
Usage statistics tracker for LLM MCP Server.

Tracks calls, tokens, and costs across all tool invocations.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from llm_mcp.models import TokenUsage


@dataclass
class CallRecord:
    """Record of a single LLM call."""

    timestamp: float
    model: str
    tool_name: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    success: bool = True
    error: Optional[str] = None


class StatsTracker:
    """Tracks usage statistics for LLM calls."""

    def __init__(self):
        self._calls: list[CallRecord] = []
        self._lock = False  # Simple flag for thread safety (can be enhanced)

    def record_call(
        self,
        model: str,
        tool_name: str,
        usage: Optional[TokenUsage] = None,
        cost: float = 0.0,
        success: bool = True,
        error: Optional[str] = None,
    ):
        """Record a single LLM call."""
        record = CallRecord(
            timestamp=time.time(),
            model=model,
            tool_name=tool_name,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            cost=cost,
            success=success,
            error=error,
        )
        self._calls.append(record)

    def get_stats(
        self,
        time_period: Optional[str] = None,
        model: Optional[str] = None,
    ) -> dict:
        """
        Get usage statistics.

        Args:
            time_period: Filter by time period ('hour', 'day', 'week', 'month', 'all')
            model: Filter by specific model

        Returns:
            Dictionary with statistics
        """
        # Filter by time period
        cutoff_time = None
        if time_period:
            now = datetime.now()
            if time_period == "hour":
                cutoff_time = now - timedelta(hours=1)
            elif time_period == "day":
                cutoff_time = now - timedelta(days=1)
            elif time_period == "week":
                cutoff_time = now - timedelta(weeks=1)
            elif time_period == "month":
                cutoff_time = now - timedelta(days=30)
            # 'all' or None means no time filter

        # Filter calls
        filtered_calls = self._calls
        if cutoff_time:
            cutoff_timestamp = cutoff_time.timestamp()
            filtered_calls = [c for c in filtered_calls if c.timestamp >= cutoff_timestamp]
        if model:
            filtered_calls = [c for c in filtered_calls if c.model == model]

        # Calculate statistics
        total_calls = len(filtered_calls)
        successful_calls = sum(1 for c in filtered_calls if c.success)
        failed_calls = total_calls - successful_calls

        total_prompt_tokens = sum(c.prompt_tokens for c in filtered_calls)
        total_completion_tokens = sum(c.completion_tokens for c in filtered_calls)
        total_tokens = sum(c.total_tokens for c in filtered_calls)
        total_cost = sum(c.cost for c in filtered_calls)

        # Per-model statistics
        model_stats: dict[str, dict] = defaultdict(
            lambda: {
                "calls": 0,
                "successful": 0,
                "failed": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost": 0.0,
            }
        )

        for call in filtered_calls:
            stats = model_stats[call.model]
            stats["calls"] += 1
            if call.success:
                stats["successful"] += 1
            else:
                stats["failed"] += 1
            stats["prompt_tokens"] += call.prompt_tokens
            stats["completion_tokens"] += call.completion_tokens
            stats["total_tokens"] += call.total_tokens
            stats["cost"] += call.cost

        # Per-tool statistics
        tool_stats: dict[str, dict] = defaultdict(
            lambda: {
                "calls": 0,
                "total_tokens": 0,
                "cost": 0.0,
            }
        )

        for call in filtered_calls:
            stats = tool_stats[call.tool_name]
            stats["calls"] += 1
            stats["total_tokens"] += call.total_tokens
            stats["cost"] += call.cost

        return {
            "summary": {
                "total_calls": total_calls,
                "successful_calls": successful_calls,
                "failed_calls": failed_calls,
                "total_prompt_tokens": total_prompt_tokens,
                "total_completion_tokens": total_completion_tokens,
                "total_tokens": total_tokens,
                "total_cost": round(total_cost, 6),
                "average_cost_per_call": round(total_cost / total_calls, 6) if total_calls > 0 else 0.0,
            },
            "by_model": dict(model_stats),
            "by_tool": dict(tool_stats),
            "filters": {
                "time_period": time_period or "all",
                "model": model or "all",
            },
        }

    def clear_stats(self):
        """Clear all statistics."""
        self._calls.clear()


# Global stats tracker instance
_stats_tracker = StatsTracker()


def get_stats_tracker() -> StatsTracker:
    """Get the global stats tracker instance."""
    return _stats_tracker
