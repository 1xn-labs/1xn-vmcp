"""
Direct LLM call tools using LiteLLM.
"""

import asyncio
import json
import time
from typing import Any, Optional

import litellm

from llm_mcp.config import MODEL_CATALOG, get_settings
from llm_mcp.models import (
    LLMCallInput,
    LLMChatInput,
    CompareModelsInput,
    ResponseFormat,
    TokenUsage,
)
from llm_mcp.utils import handle_litellm_error, format_error_response, calculate_cost


async def llm_call(params: LLMCallInput) -> str:
    """
    Make a simple LLM completion call.

    This tool sends a prompt to an LLM and returns the response.
    It supports all models available through LiteLLM.

    Args:
        params: Input parameters including:
            - prompt: The prompt to send to the LLM
            - model: Model identifier (defaults to configured default)
            - system_prompt: Optional system prompt
            - temperature: Sampling temperature (0-2)
            - max_tokens: Maximum tokens to generate
            - response_format: Output format (text, json, markdown)

    Returns:
        The LLM's response with optional usage statistics and cost estimate.
    """
    settings = get_settings()
    model = params.model or settings.default_model

    try:
        # Build messages
        messages = []
        if params.system_prompt:
            messages.append({"role": "system", "content": params.system_prompt})
        messages.append({"role": "user", "content": params.prompt})

        # Build kwargs
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": params.temperature,
        }

        if params.max_tokens:
            kwargs["max_tokens"] = params.max_tokens
        elif settings.default_max_tokens:
            kwargs["max_tokens"] = settings.default_max_tokens

        # Request JSON mode if specified
        if params.response_format == ResponseFormat.JSON:
            kwargs["response_format"] = {"type": "json_object"}

        # Make the call
        response = await litellm.acompletion(**kwargs)

        # Extract response content
        content = response.choices[0].message.content

        # Build result
        result: dict[str, Any] = {
            "content": content,
            "model": response.model,
        }

        # Add usage info if available
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )
            result["usage"] = usage.model_dump()

            # Calculate cost if model info available
            if model in MODEL_CATALOG and settings.enable_cost_tracking:
                model_info = MODEL_CATALOG[model]
                cost = calculate_cost(
                    usage,
                    model_info.get("cost_per_1k_input", 0),
                    model_info.get("cost_per_1k_output", 0),
                )
                result["cost_estimate"] = round(cost, 6)

        return json.dumps(result, indent=2)

    except Exception as e:
        error = handle_litellm_error(e, model)
        return format_error_response(error)


async def llm_chat(params: LLMChatInput) -> str:
    """
    Make a multi-turn chat completion call.

    This tool handles multi-turn conversations with an LLM.

    Args:
        params: Input parameters including:
            - messages: List of chat messages with role and content
            - model: Model identifier
            - system_prompt: System prompt (prepended to messages)
            - temperature: Sampling temperature
            - max_tokens: Maximum tokens to generate

    Returns:
        The assistant's response with conversation context.
    """
    settings = get_settings()
    model = params.model or settings.default_model

    try:
        # Build messages list
        messages = []

        # Add system prompt if provided and not already in messages
        if params.system_prompt:
            has_system = any(m.role == "system" for m in params.messages)
            if not has_system:
                messages.append({"role": "system", "content": params.system_prompt})

        # Add conversation messages
        for msg in params.messages:
            messages.append({"role": msg.role, "content": msg.content})

        # Build kwargs
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": params.temperature,
        }

        if params.max_tokens:
            kwargs["max_tokens"] = params.max_tokens

        # Make the call
        response = await litellm.acompletion(**kwargs)

        content = response.choices[0].message.content

        result: dict[str, Any] = {
            "role": "assistant",
            "content": content,
            "model": response.model,
        }

        if response.usage:
            result["usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return json.dumps(result, indent=2)

    except Exception as e:
        error = handle_litellm_error(e, model)
        return format_error_response(error)


async def compare_models(params: CompareModelsInput) -> str:
    """
    Compare responses from multiple LLM models.

    This tool sends the same prompt to multiple models and returns
    their responses for comparison, including timing and cost info.

    Args:
        params: Input parameters including:
            - prompt: The prompt to send to all models
            - models: List of model identifiers to compare
            - temperature: Sampling temperature
            - return_timing: Whether to include response timing

    Returns:
        Comparison of responses from all models with timing and cost.
    """
    settings = get_settings()

    async def call_model(model: str) -> dict[str, Any]:
        """Call a single model and return result with timing."""
        start_time = time.time()

        try:
            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": params.prompt}],
                temperature=params.temperature,
            )

            elapsed = time.time() - start_time
            content = response.choices[0].message.content

            result: dict[str, Any] = {
                "content": content,
                "success": True,
            }

            if params.return_timing:
                result["timing"] = round(elapsed, 3)

            if response.usage:
                result["tokens"] = response.usage.total_tokens

                # Calculate cost
                if model in MODEL_CATALOG and settings.enable_cost_tracking:
                    model_info = MODEL_CATALOG[model]
                    usage = TokenUsage(
                        prompt_tokens=response.usage.prompt_tokens,
                        completion_tokens=response.usage.completion_tokens,
                        total_tokens=response.usage.total_tokens,
                    )
                    cost = calculate_cost(
                        usage,
                        model_info.get("cost_per_1k_input", 0),
                        model_info.get("cost_per_1k_output", 0),
                    )
                    result["cost"] = round(cost, 6)

            return result

        except Exception as e:
            elapsed = time.time() - start_time
            return {
                "error": str(e),
                "success": False,
                "timing": round(elapsed, 3) if params.return_timing else None,
            }

    # Run all models concurrently
    tasks = [call_model(model) for model in params.models]
    results_list = await asyncio.gather(*tasks)

    # Build results dict
    results = dict(zip(params.models, results_list))

    # Find fastest and cheapest
    fastest_model = None
    cheapest_model = None
    fastest_time = float("inf")
    cheapest_cost = float("inf")

    for model, result in results.items():
        if result.get("success"):
            if result.get("timing", float("inf")) < fastest_time:
                fastest_time = result["timing"]
                fastest_model = model
            if result.get("cost", float("inf")) < cheapest_cost:
                cheapest_cost = result["cost"]
                cheapest_model = model

    output = {
        "prompt": params.prompt[:200] + ("..." if len(params.prompt) > 200 else ""),
        "results": results,
    }

    if fastest_model:
        output["fastest_model"] = fastest_model
    if cheapest_model:
        output["cheapest_model"] = cheapest_model

    return json.dumps(output, indent=2)


async def llm_structured_output(
    prompt: str,
    schema: dict[str, Any],
    model: Optional[str] = None,
) -> str:
    """
    Generate structured JSON output matching a schema.

    This tool uses LiteLLM's JSON mode with schema guidance to generate
    structured output.

    Args:
        prompt: The prompt describing what to generate
        schema: JSON schema for the output structure
        model: Model to use (defaults to configured default)

    Returns:
        JSON output matching the provided schema.
    """
    settings = get_settings()
    model = model or settings.default_model

    # Build prompt with schema guidance
    schema_str = json.dumps(schema, indent=2)
    full_prompt = f"""Generate a JSON object that matches this schema:

```json
{schema_str}
```

Task: {prompt}

Respond ONLY with valid JSON that matches the schema. No explanation or markdown."""

    try:
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.3,  # Lower temperature for structured output
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content

        # Try to parse and re-format for consistency
        try:
            parsed = json.loads(content)
            return json.dumps(parsed, indent=2)
        except json.JSONDecodeError:
            # Return as-is if parsing fails
            return content

    except Exception as e:
        error = handle_litellm_error(e, model)
        return format_error_response(error)
