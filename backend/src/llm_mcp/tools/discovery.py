"""
Discovery tools for listing available models and providers.
"""

import json
from typing import Optional

from llm_mcp.config import MODEL_CATALOG, get_settings
from llm_mcp.models import (
    ListModelsInput,
    EstimateCostInput,
    GetCheapestModelInput,
    TokenUsage,
)
from llm_mcp.utils.formatting import format_model_list
from llm_mcp.utils.formatting import calculate_cost


async def list_models(params: ListModelsInput) -> str:
    """
    List available LLM models.

    This tool returns a list of all available models across configured providers,
    with optional filtering by provider or capability.

    Args:
        params: Input parameters for filtering models.
            - provider: Filter by provider (openai, anthropic, google, etc.)
            - capability: Filter by capability (chat, vision, function_calling, json_mode)

    Returns:
        JSON or Markdown formatted list of available models with their capabilities,
        context windows, and pricing information.
    """
    settings = get_settings()
    available_providers = settings.get_available_providers()

    models = []
    for model_id, model_info in MODEL_CATALOG.items():
        # Check if provider is available
        provider = model_info.get("provider", "")
        if provider not in available_providers:
            continue

        # Apply provider filter
        if params.provider and provider != params.provider.lower():
            continue

        # Apply capability filter
        if params.capability:
            capabilities = model_info.get("capabilities", [])
            if params.capability.lower() not in [c.lower() for c in capabilities]:
                continue

        models.append(
            {
                "id": model_id,
                "name": model_info.get("name", model_id),
                "provider": provider,
                "capabilities": model_info.get("capabilities", []),
                "context_window": model_info.get("context_window", 0),
                "max_output_tokens": model_info.get("max_output_tokens", 0),
                "cost_per_1k_input": model_info.get("cost_per_1k_input", 0),
                "cost_per_1k_output": model_info.get("cost_per_1k_output", 0),
            }
        )

    # Sort by provider, then by name
    models.sort(key=lambda x: (x["provider"], x["name"]))

    return format_model_list(models, format_type="markdown")


async def list_providers() -> str:
    """
    List configured LLM providers.

    This tool returns information about all configured providers,
    including their status and available features.

    Returns:
        JSON formatted list of providers with their configuration status.
    """
    settings = get_settings()
    available = settings.get_available_providers()

    providers_info = []

    # OpenAI
    providers_info.append(
        {
            "name": "openai",
            "display_name": "OpenAI",
            "configured": "openai" in available,
            "models_available": len(
                [m for m in MODEL_CATALOG if MODEL_CATALOG[m]["provider"] == "openai"]
            ),
            "features": ["chat", "vision", "function_calling", "json_mode", "embeddings"],
            "docs_url": "https://platform.openai.com/docs",
        }
    )

    # Anthropic
    providers_info.append(
        {
            "name": "anthropic",
            "display_name": "Anthropic",
            "configured": "anthropic" in available,
            "models_available": len(
                [m for m in MODEL_CATALOG if MODEL_CATALOG[m]["provider"] == "anthropic"]
            ),
            "features": ["chat", "vision", "function_calling"],
            "docs_url": "https://docs.anthropic.com",
        }
    )

    # Google
    providers_info.append(
        {
            "name": "google",
            "display_name": "Google AI",
            "configured": "google" in available,
            "models_available": len(
                [m for m in MODEL_CATALOG if MODEL_CATALOG[m]["provider"] == "google"]
            ),
            "features": ["chat", "vision", "function_calling"],
            "docs_url": "https://ai.google.dev/docs",
        }
    )

    # Azure
    providers_info.append(
        {
            "name": "azure",
            "display_name": "Azure OpenAI",
            "configured": "azure" in available,
            "models_available": 0,
            "features": ["chat", "vision", "function_calling", "embeddings"],
            "docs_url": "https://learn.microsoft.com/azure/ai-services/openai/",
        }
    )

    # Together AI
    providers_info.append(
        {
            "name": "together",
            "display_name": "Together AI",
            "configured": "together" in available,
            "models_available": len(
                [m for m in MODEL_CATALOG if MODEL_CATALOG[m]["provider"] == "together"]
            ),
            "features": ["chat", "embeddings"],
            "docs_url": "https://docs.together.ai",
        }
    )

    # Groq
    providers_info.append(
        {
            "name": "groq",
            "display_name": "Groq",
            "configured": "groq" in available,
            "models_available": len(
                [m for m in MODEL_CATALOG if MODEL_CATALOG[m]["provider"] == "groq"]
            ),
            "features": ["chat"],
            "docs_url": "https://console.groq.com/docs",
            "note": "Ultra-fast inference",
        }
    )

    # Ollama
    providers_info.append(
        {
            "name": "ollama",
            "display_name": "Ollama (Local)",
            "configured": "ollama" in available,
            "models_available": len(
                [m for m in MODEL_CATALOG if MODEL_CATALOG[m]["provider"] == "ollama"]
            ),
            "features": ["chat"],
            "docs_url": "https://ollama.ai",
            "note": "Local models, no API key required",
        }
    )

    # Format as markdown
    lines = ["# Configured Providers", ""]

    configured = [p for p in providers_info if p["configured"]]
    not_configured = [p for p in providers_info if not p["configured"]]

    if configured:
        lines.append("## ✅ Available Providers")
        lines.append("")
        for p in configured:
            lines.append(f"### {p['display_name']}")
            lines.append(f"- **Models**: {p['models_available']} available")
            lines.append(f"- **Features**: {', '.join(p['features'])}")
            if p.get("note"):
                lines.append(f"- **Note**: {p['note']}")
            lines.append(f"- **Docs**: {p['docs_url']}")
            lines.append("")

    if not_configured:
        lines.append("## ⚠️ Not Configured")
        lines.append("")
        for p in not_configured:
            lines.append(f"- **{p['display_name']}**: Set `{p['name'].upper()}_API_KEY` to enable")
        lines.append("")

    lines.append("---")
    lines.append(f"**Default Model**: {settings.default_model}")

    return "\n".join(lines)


async def get_model_info(model_id: str) -> str:
    """
    Get detailed information about a specific model.

    Args:
        model_id: The model identifier (e.g., 'openai/gpt-4o')

    Returns:
        Detailed information about the model including capabilities,
        pricing, and context limits.
    """
    settings = get_settings()

    # Check if model exists in catalog
    if model_id not in MODEL_CATALOG:
        # Try to find partial match
        matches = [m for m in MODEL_CATALOG if model_id.lower() in m.lower()]
        if matches:
            return json.dumps(
                {
                    "error": True,
                    "message": f"Model '{model_id}' not found",
                    "suggestions": matches[:5],
                },
                indent=2,
            )
        return json.dumps(
            {
                "error": True,
                "message": f"Model '{model_id}' not found",
                "hint": "Use llm_list_models to see available models",
            },
            indent=2,
        )

    model_info = MODEL_CATALOG[model_id]
    provider = model_info.get("provider", "")

    # Check if provider is configured
    available_providers = settings.get_available_providers()
    is_available = provider in available_providers

    result = {
        "id": model_id,
        "name": model_info.get("name", model_id),
        "provider": provider,
        "available": is_available,
        "capabilities": model_info.get("capabilities", []),
        "context_window": model_info.get("context_window", 0),
        "max_output_tokens": model_info.get("max_output_tokens", 0),
        "pricing": {
            "input_per_1k_tokens": model_info.get("cost_per_1k_input", 0),
            "output_per_1k_tokens": model_info.get("cost_per_1k_output", 0),
            "currency": "USD",
        },
    }

    if not is_available:
        result["warning"] = (
            f"Provider '{provider}' is not configured. "
            f"Set {provider.upper()}_API_KEY to use this model."
        )

    return json.dumps(result, indent=2)


async def estimate_cost(params: EstimateCostInput) -> str:
    """
    Estimate the cost for a prompt/model combination without making the call.

    Args:
        params: Input parameters including:
            - prompt: The prompt to estimate cost for
            - model: Model identifier (uses default if not specified)
            - estimated_output_tokens: Estimated output tokens (defaults to 500)

    Returns:
        Cost estimate breakdown with input/output costs.
    """
    settings = get_settings()
    model = params.model or settings.default_model

    # Check if model exists in catalog
    if model not in MODEL_CATALOG:
        return json.dumps(
            {
                "error": True,
                "message": f"Model '{model}' not found in catalog",
                "hint": "Use llm_list_models to see available models",
            },
            indent=2,
        )

    model_info = MODEL_CATALOG[model]
    cost_per_1k_input = model_info.get("cost_per_1k_input", 0)
    cost_per_1k_output = model_info.get("cost_per_1k_output", 0)

    # Estimate input tokens (rough approximation: ~1.3 tokens per word)
    # More accurate would use tiktoken, but this is a reasonable estimate
    word_count = len(params.prompt.split())
    estimated_input_tokens = int(word_count * 1.3)

    # Use provided estimate or default to 500
    estimated_output_tokens = params.estimated_output_tokens or 500

    # Calculate costs
    input_cost = (estimated_input_tokens / 1000) * cost_per_1k_input
    output_cost = (estimated_output_tokens / 1000) * cost_per_1k_output
    total_cost = input_cost + output_cost

    result = {
        "model": model,
        "model_name": model_info.get("name", model),
        "prompt_length": len(params.prompt),
        "word_count": word_count,
        "estimated_tokens": {
            "input": estimated_input_tokens,
            "output": estimated_output_tokens,
            "total": estimated_input_tokens + estimated_output_tokens,
        },
        "pricing": {
            "input_per_1k_tokens": cost_per_1k_input,
            "output_per_1k_tokens": cost_per_1k_output,
            "currency": "USD",
        },
        "cost_estimate": {
            "input_cost": round(input_cost, 6),
            "output_cost": round(output_cost, 6),
            "total_cost": round(total_cost, 6),
        },
        "note": "Token estimates are approximate. Actual usage may vary.",
    }

    return json.dumps(result, indent=2)


async def get_cheapest_model(params: GetCheapestModelInput) -> str:
    """
    Find the cheapest model matching the specified criteria.

    Args:
        params: Input parameters including:
            - capability: Required capability (chat, vision, etc.)
            - provider: Filter by provider
            - prompt: Optional prompt to estimate actual cost
            - estimated_output_tokens: Estimated output tokens

    Returns:
        Information about the cheapest matching model.
    """
    settings = get_settings()
    available_providers = settings.get_available_providers()

    # Filter models
    candidate_models = []
    for model_id, model_info in MODEL_CATALOG.items():
        provider = model_info.get("provider", "")
        if provider not in available_providers:
            continue

        # Apply provider filter
        if params.provider and provider != params.provider.lower():
            continue

        # Apply capability filter
        if params.capability:
            capabilities = model_info.get("capabilities", [])
            if params.capability.lower() not in [c.lower() for c in capabilities]:
                continue

        candidate_models.append((model_id, model_info))

    if not candidate_models:
        return json.dumps(
            {
                "error": True,
                "message": "No models found matching the criteria",
                "filters": {
                    "capability": params.capability,
                    "provider": params.provider,
                },
            },
            indent=2,
        )

    # Calculate costs for each model
    cheapest_model = None
    cheapest_cost = float("inf")
    model_costs = []

    for model_id, model_info in candidate_models:
        cost_per_1k_input = model_info.get("cost_per_1k_input", 0)
        cost_per_1k_output = model_info.get("cost_per_1k_output", 0)

        if params.prompt:
            # Estimate based on actual prompt
            word_count = len(params.prompt.split())
            estimated_input_tokens = int(word_count * 1.3)
            estimated_output_tokens = params.estimated_output_tokens or 500
            input_cost = (estimated_input_tokens / 1000) * cost_per_1k_input
            output_cost = (estimated_output_tokens / 1000) * cost_per_1k_output
            total_cost = input_cost + output_cost
        else:
            # Just compare base pricing (use average of input/output)
            total_cost = (cost_per_1k_input + cost_per_1k_output) / 2

        model_costs.append(
            {
                "model_id": model_id,
                "model_name": model_info.get("name", model_id),
                "provider": model_info.get("provider", ""),
                "cost": round(total_cost, 6),
                "pricing": {
                    "input_per_1k": cost_per_1k_input,
                    "output_per_1k": cost_per_1k_output,
                },
            }
        )

        if total_cost < cheapest_cost:
            cheapest_cost = total_cost
            cheapest_model = model_id

    # Sort by cost
    model_costs.sort(key=lambda x: x["cost"])

    result = {
        "cheapest_model": cheapest_model,
        "cheapest_cost": round(cheapest_cost, 6),
        "filters": {
            "capability": params.capability,
            "provider": params.provider,
        },
        "all_matching_models": model_costs[:10],  # Top 10 cheapest
        "total_matching": len(model_costs),
    }

    if params.prompt:
        result["note"] = "Costs estimated based on provided prompt"
    else:
        result["note"] = "Costs based on average pricing (input + output) / 2"

    return json.dumps(result, indent=2)
