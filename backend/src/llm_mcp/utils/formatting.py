"""
Response formatting utilities.
"""

import json
from typing import Any, Optional

from llm_mcp.models import TokenUsage


def format_json_response(data: dict[str, Any], indent: int = 2) -> str:
    """Format data as pretty-printed JSON."""
    return json.dumps(data, indent=indent, default=str)


def format_markdown_response(
    title: str,
    content: str,
    metadata: Optional[dict[str, Any]] = None,
) -> str:
    """Format response as Markdown."""
    lines = [f"# {title}", "", content]

    if metadata:
        lines.extend(["", "---", ""])
        for key, value in metadata.items():
            lines.append(f"**{key}**: {value}")

    return "\n".join(lines)


def format_model_list(
    models: list[dict[str, Any]],
    format_type: str = "markdown",
) -> str:
    """Format a list of models."""
    if format_type == "json":
        return format_json_response({"models": models, "total": len(models)})

    # Markdown format
    lines = [f"# Available Models ({len(models)} total)", ""]

    # Group by provider
    by_provider: dict[str, list[dict[str, Any]]] = {}
    for model in models:
        provider = model.get("provider", "unknown")
        if provider not in by_provider:
            by_provider[provider] = []
        by_provider[provider].append(model)

    for provider, provider_models in sorted(by_provider.items()):
        lines.append(f"## {provider.title()}")
        lines.append("")
        for model in provider_models:
            caps = ", ".join(model.get("capabilities", []))
            ctx = model.get("context_window", "N/A")
            lines.append(f"- **{model['id']}** ({model.get('name', '')})")
            lines.append(f"  - Context: {ctx:,} tokens")
            lines.append(f"  - Capabilities: {caps}")
        lines.append("")

    return "\n".join(lines)


def format_comparison_result(
    prompt: str,
    results: dict[str, dict[str, Any]],
    format_type: str = "markdown",
) -> str:
    """Format model comparison results."""
    if format_type == "json":
        return format_json_response(
            {
                "prompt": prompt,
                "results": results,
            }
        )

    # Markdown format
    lines = ["# Model Comparison Results", "", f"**Prompt**: {prompt[:100]}...", ""]

    for model, result in results.items():
        lines.append(f"## {model}")
        lines.append("")

        if result.get("error"):
            lines.append(f"❌ Error: {result.get('error')}")
        else:
            lines.append(result.get("content", "No response"))
            lines.append("")

            if result.get("timing"):
                lines.append(f"⏱️ Time: {result['timing']:.2f}s")
            if result.get("tokens"):
                lines.append(f"📊 Tokens: {result['tokens']}")
            if result.get("cost"):
                lines.append(f"💰 Cost: ${result['cost']:.6f}")

        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def format_entity_extraction(
    entities: dict[str, list[str]],
    format_type: str = "markdown",
) -> str:
    """Format entity extraction results."""
    if format_type == "json":
        return format_json_response({"entities": entities})

    lines = ["# Extracted Entities", ""]

    entity_emojis = {
        "people": "👤",
        "organizations": "🏢",
        "locations": "📍",
        "dates": "📅",
        "money": "💰",
        "products": "📦",
        "other": "📌",
    }

    for entity_type, items in entities.items():
        if items:
            emoji = entity_emojis.get(entity_type, "•")
            lines.append(f"## {emoji} {entity_type.title()}")
            for item in items:
                lines.append(f"- {item}")
            lines.append("")

    if not any(entities.values()):
        lines.append("No entities found.")

    return "\n".join(lines)


def format_analysis_result(
    analysis: dict[str, Any],
    format_type: str = "markdown",
) -> str:
    """Format text analysis results."""
    if format_type == "json":
        return format_json_response(analysis)

    lines = ["# Text Analysis Results", ""]

    # Sentiment
    if "sentiment" in analysis and analysis["sentiment"]:
        sentiment = analysis["sentiment"]
        sentiment_emoji = {
            "positive": "😊",
            "negative": "😔",
            "neutral": "😐",
            "mixed": "🤔",
        }
        emoji = sentiment_emoji.get(sentiment.get("sentiment", ""), "")
        lines.append(f"## Sentiment {emoji}")
        lines.append(f"- **Label**: {sentiment.get('sentiment', 'N/A')}")
        lines.append(f"- **Confidence**: {sentiment.get('confidence', 0):.1%}")
        if sentiment.get("reasoning"):
            lines.append(f"- **Reasoning**: {sentiment['reasoning']}")
        lines.append("")

    # Topics
    if "topics" in analysis and analysis["topics"]:
        lines.append("## 📋 Topics")
        for topic in analysis["topics"]:
            lines.append(f"- {topic}")
        lines.append("")

    # Entities
    if "entities" in analysis and analysis["entities"]:
        lines.append("## 🏷️ Key Entities")
        entities = analysis["entities"]
        if isinstance(entities, dict):
            for etype, items in entities.items():
                if items:
                    lines.append(f"- **{etype.title()}**: {', '.join(items[:5])}")
        lines.append("")

    # Summary
    if "summary" in analysis and analysis["summary"]:
        lines.append("## 📝 Summary")
        lines.append(analysis["summary"])
        lines.append("")

    # Word count
    if "word_count" in analysis:
        lines.append(f"📊 **Word Count**: {analysis['word_count']:,}")

    return "\n".join(lines)


def calculate_cost(
    usage: TokenUsage,
    cost_per_1k_input: float,
    cost_per_1k_output: float,
) -> float:
    """Calculate cost based on token usage."""
    input_cost = (usage.prompt_tokens / 1000) * cost_per_1k_input
    output_cost = (usage.completion_tokens / 1000) * cost_per_1k_output
    return input_cost + output_cost


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """Truncate text to max length with suffix."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix
