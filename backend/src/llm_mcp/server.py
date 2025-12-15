"""
LLM MCP Server - Main server implementation.

A comprehensive MCP server for LLM operations with support for
multiple providers, structured outputs, and advanced reasoning.
"""

import logging
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from llm_mcp.config import get_settings
from llm_mcp.models import (
    ListModelsInput,
    LLMCallInput,
    LLMChatInput,
    CompareModelsInput,
    AnalyzeTextInput,
    SummarizeInput,
    TranslateInput,
    ExtractEntitiesInput,
    ExtractInfoInput,
    AnalyzeImageInput,
    AnalyzePDFInput,
    AnalyzeDocumentInput,
    EstimateCostInput,
    GetCheapestModelInput,
    GetStatsInput,
    ChainOfThoughtInput,
    ChatMessage,
    AnalysisType,
    SummaryStyle,
    ResponseFormat,
)
from llm_mcp.tools import (
    list_models,
    list_providers,
    get_model_info,
    estimate_cost,
    get_cheapest_model,
    llm_call,
    llm_chat,
    compare_models,
    llm_structured_output,
    analyze_text,
    summarize,
    translate,
    extract_entities,
    extract_info,
    rewrite,
    analyze_image,
    describe_image,
    extract_text_from_image,
    analyze_pdf,
    analyze_document,
    compare_images,
    chain_of_thought,
    multi_step_reasoning,
    decompose_and_solve,
    self_critique,
    debate_reasoning,
    verify_with_evidence,
    get_stats,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the MCP server
mcp = FastMCP("llm_mcp")

# Get settings for tool configuration
settings = get_settings()


def conditional_tool(tool_name: str, **tool_kwargs):
    """
    Conditionally register a tool based on configuration.

    Args:
        tool_name: The name of the tool (e.g., 'llm_call')
        **tool_kwargs: Keyword arguments to pass to @mcp.tool decorator

    Returns:
        Decorator function that conditionally registers the tool.
    """
    def decorator(func):
        if settings.is_tool_enabled(tool_name):
            return mcp.tool(name=tool_name, **tool_kwargs)(func)
        else:
            logger.debug(f"Tool '{tool_name}' is disabled, skipping registration")
            return func  # Return function unchanged if disabled
    return decorator


# =============================================================================
# Discovery Tools
# =============================================================================


@conditional_tool(
    "llm_list_models",
    annotations={
        "title": "List Available LLM Models",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def tool_list_models(
    provider: Optional[str] = None,
    capability: Optional[str] = None,
) -> str:
    """
    List available LLM models across all configured providers.

    Args:
        provider: Filter by provider (openai, anthropic, google, etc.)
        capability: Filter by capability (chat, vision, function_calling)

    Returns:
        Formatted list of available models with capabilities and pricing.
    """
    params = ListModelsInput(provider=provider, capability=capability)
    return await list_models(params)


@conditional_tool(
    "llm_list_providers",
    annotations={
        "title": "List Configured Providers",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def tool_list_providers() -> str:
    """List all LLM providers and their configuration status."""
    return await list_providers()


@conditional_tool(
    "llm_get_model_info",
    annotations={
        "title": "Get Model Information",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def tool_get_model_info(model_id: str) -> str:
    """
    Get detailed information about a specific LLM model.

    Args:
        model_id: Model identifier (e.g., 'openai/gpt-4o')

    Returns:
        Detailed model info including capabilities, context window, pricing.
    """
    return await get_model_info(model_id)


@conditional_tool(
    "llm_estimate_cost",
    annotations={
        "title": "Estimate Cost",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def tool_estimate_cost(
    prompt: str,
    model: Optional[str] = None,
    estimated_output_tokens: Optional[int] = None,
) -> str:
    """
    Estimate the cost for a prompt/model combination without making the call.

    Args:
        prompt: The prompt to estimate cost for
        model: Model identifier (uses default if not specified)
        estimated_output_tokens: Estimated output tokens (defaults to 500)

    Returns:
        Cost estimate breakdown with input/output costs.
    """
    params = EstimateCostInput(
        prompt=prompt,
        model=model,
        estimated_output_tokens=estimated_output_tokens,
    )
    return await estimate_cost(params)


@conditional_tool(
    "llm_get_cheapest_model",
    annotations={
        "title": "Get Cheapest Model",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def tool_get_cheapest_model(
    capability: Optional[str] = None,
    provider: Optional[str] = None,
    prompt: Optional[str] = None,
    estimated_output_tokens: Optional[int] = None,
) -> str:
    """
    Find the cheapest model matching the specified criteria.

    Args:
        capability: Required capability (chat, vision, function_calling, etc.)
        provider: Filter by provider (openai, anthropic, etc.)
        prompt: Optional prompt to estimate cost based on actual usage
        estimated_output_tokens: Estimated output tokens for cost calculation

    Returns:
        Information about the cheapest matching model.
    """
    params = GetCheapestModelInput(
        capability=capability,
        provider=provider,
        prompt=prompt,
        estimated_output_tokens=estimated_output_tokens,
    )
    return await get_cheapest_model(params)


# =============================================================================
# Direct LLM Call Tools
# =============================================================================


@conditional_tool(
    "llm_call",
    annotations={
        "title": "LLM Completion",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_llm_call(
    prompt: str,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    response_format: str = "text",
) -> str:
    """
    Make a simple LLM completion call.

    Args:
        prompt: The prompt to send to the LLM
        model: Model identifier (e.g., 'openai/gpt-4o')
        system_prompt: Optional system prompt to set context
        temperature: Sampling temperature (0-2). Default: 0.7
        max_tokens: Maximum tokens to generate
        response_format: Output format - 'text' or 'json'

    Returns:
        The LLM's response with usage statistics.
    """
    format_enum = ResponseFormat(response_format) if response_format else ResponseFormat.TEXT
    params = LLMCallInput(
        prompt=prompt,
        model=model,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=format_enum,
    )
    return await llm_call(params)


@conditional_tool(
    "llm_chat",
    annotations={
        "title": "LLM Chat Completion",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_llm_chat(
    messages: list[dict[str, str]],
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> str:
    """
    Make a multi-turn chat completion call.

    Args:
        messages: List of messages with 'role' and 'content' keys
        model: Model identifier
        system_prompt: System prompt (prepended if not in messages)
        temperature: Sampling temperature (0-2)
        max_tokens: Maximum tokens to generate

    Returns:
        The assistant's response.
    """
    chat_messages = [ChatMessage(role=m["role"], content=m["content"]) for m in messages]
    params = LLMChatInput(
        messages=chat_messages,
        model=model,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return await llm_chat(params)


@conditional_tool(
    "llm_compare_models",
    annotations={
        "title": "Compare LLM Models",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_compare_models(
    prompt: str,
    models: Optional[list[str]] = None,
    temperature: float = 0.7,
    return_timing: bool = True,
) -> str:
    """
    Compare responses from multiple LLM models.

    Args:
        prompt: The prompt to send to all models
        models: List of model identifiers to compare
        temperature: Sampling temperature (0-2)
        return_timing: Include response timing information

    Returns:
        Comparison of responses with timing and cost.
    """
    params = CompareModelsInput(
        prompt=prompt,
        models=models or ["openai/gpt-4o", "anthropic/claude-3-5-sonnet-20241022"],
        temperature=temperature,
        return_timing=return_timing,
    )
    return await compare_models(params)


@conditional_tool(
    "llm_structured_output",
    annotations={
        "title": "Generate Structured Output",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_structured_output(
    prompt: str,
    schema: dict[str, Any],
    model: Optional[str] = None,
) -> str:
    """
    Generate structured JSON output matching a schema.

    Args:
        prompt: The prompt describing what to generate
        schema: JSON schema defining the output structure
        model: Model to use

    Returns:
        JSON output matching the provided schema.
    """
    return await llm_structured_output(prompt, schema, model)


# =============================================================================
# Text Analysis Tools
# =============================================================================


@conditional_tool(
    "llm_analyze_text",
    annotations={
        "title": "Analyze Text",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_analyze_text(
    text: str,
    analysis_type: str = "all",
    model: Optional[str] = None,
) -> str:
    """
    Perform comprehensive text analysis.

    Args:
        text: Text to analyze
        analysis_type: 'sentiment', 'topics', 'entities', 'summary', or 'all'
        model: Model to use

    Returns:
        Analysis results.
    """
    type_enum = AnalysisType(analysis_type) if analysis_type else AnalysisType.ALL
    params = AnalyzeTextInput(text=text, analysis_type=type_enum, model=model)
    return await analyze_text(params)


@conditional_tool(
    "llm_summarize",
    annotations={
        "title": "Summarize Text",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_summarize(
    text: str,
    style: str = "brief",
    max_length: Optional[int] = None,
    model: Optional[str] = None,
) -> str:
    """
    Summarize text with configurable style.

    Args:
        text: Text to summarize
        style: 'brief', 'detailed', or 'bullets'
        max_length: Maximum summary length in words
        model: Model to use

    Returns:
        Summary of the text.
    """
    style_enum = SummaryStyle(style) if style else SummaryStyle.BRIEF
    params = SummarizeInput(text=text, style=style_enum, max_length=max_length, model=model)
    return await summarize(params)


@conditional_tool(
    "llm_translate",
    annotations={
        "title": "Translate Text",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_translate(
    text: str,
    target_language: str,
    source_language: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Translate text between languages.

    Args:
        text: Text to translate
        target_language: Target language (e.g., 'Spanish', 'French')
        source_language: Source language (auto-detected if not specified)
        model: Model to use

    Returns:
        Translated text.
    """
    params = TranslateInput(
        text=text,
        target_language=target_language,
        source_language=source_language,
        model=model,
    )
    return await translate(params)


@conditional_tool(
    "llm_extract_entities",
    annotations={
        "title": "Extract Named Entities",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_extract_entities(
    text: str,
    entity_types: Optional[list[str]] = None,
    model: Optional[str] = None,
) -> str:
    """
    Extract named entities from text.

    Args:
        text: Text to extract entities from
        entity_types: Specific types to extract
        model: Model to use

    Returns:
        Extracted entities organized by type.
    """
    params = ExtractEntitiesInput(text=text, entity_types=entity_types, model=model)
    return await extract_entities(params)


@conditional_tool(
    "llm_extract_info",
    annotations={
        "title": "Extract Structured Information",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_extract_info(
    text: str,
    schema: dict[str, Any],
    instructions: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Extract structured information using a custom schema.

    Args:
        text: Text to extract information from
        schema: JSON schema defining the structure to extract
        instructions: Additional extraction instructions
        model: Model to use

    Returns:
        Extracted information matching the schema.
    """
    params = ExtractInfoInput(text=text, schema=schema, instructions=instructions, model=model)
    return await extract_info(params)


@conditional_tool(
    "llm_rewrite",
    annotations={
        "title": "Rewrite Text",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_rewrite(
    text: str,
    style: Optional[str] = None,
    tone: Optional[str] = None,
    audience: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Rewrite text with a different style, tone, or audience.

    Args:
        text: Text to rewrite
        style: Writing style (formal, casual, academic, etc.)
        tone: Tone (friendly, professional, persuasive, etc.)
        audience: Target audience (experts, beginners, etc.)
        model: Model to use

    Returns:
        Rewritten text.
    """
    return await rewrite(text, style, tone, audience, model)


# =============================================================================
# Multimodal Tools
# =============================================================================


@conditional_tool(
    "llm_analyze_image",
    annotations={
        "title": "Analyze Image",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_analyze_image(
    image: str,
    prompt: str = "Describe this image in detail.",
    model: Optional[str] = None,
) -> str:
    """
    Analyze an image using a vision-capable LLM.

    Args:
        image: Base64-encoded image data or URL
        prompt: What to analyze about the image
        model: Vision-capable model to use

    Returns:
        Analysis of the image.
    """
    params = AnalyzeImageInput(image=image, prompt=prompt, model=model)
    return await analyze_image(params)


@conditional_tool(
    "llm_describe_image",
    annotations={
        "title": "Describe Image",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_describe_image(image: str, model: Optional[str] = None) -> str:
    """
    Generate a detailed description of an image.

    Args:
        image: Base64-encoded image data or URL
        model: Vision-capable model to use

    Returns:
        Detailed description of the image.
    """
    return await describe_image(image, model)


@conditional_tool(
    "llm_extract_text_from_image",
    annotations={
        "title": "OCR - Extract Text from Image",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_extract_text_from_image(image: str, model: Optional[str] = None) -> str:
    """
    Extract text from an image (OCR).

    Args:
        image: Base64-encoded image data or URL
        model: Vision-capable model to use

    Returns:
        Extracted text from the image.
    """
    return await extract_text_from_image(image, model)


@conditional_tool(
    "llm_analyze_pdf",
    annotations={
        "title": "Analyze PDF Document",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_analyze_pdf(
    pdf_content: str,
    prompt: str = "Analyze this PDF document and summarize its contents.",
    extract_images: bool = False,
    model: Optional[str] = None,
) -> str:
    """
    Analyze a PDF document.

    Args:
        pdf_content: Base64-encoded PDF content
        prompt: What to analyze about the PDF
        extract_images: Whether to analyze images in the PDF
        model: Model to use

    Returns:
        Analysis of the PDF content.
    """
    params = AnalyzePDFInput(
        pdf_content=pdf_content,
        prompt=prompt,
        extract_images=extract_images,
        model=model,
    )
    return await analyze_pdf(params)


@conditional_tool(
    "llm_analyze_document",
    annotations={
        "title": "Analyze Document (Universal)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_analyze_document(
    document: str,
    prompt: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Universal document analyzer that auto-detects document type.

    Automatically detects whether the input is text, PDF, or image,
    then routes to the appropriate analyzer.

    Args:
        document: Document content (text, base64-encoded PDF, base64-encoded image, or image URL)
        prompt: Optional analysis prompt
        model: Optional model to use

    Returns:
        Analysis results with detected document type.
    """
    params = AnalyzeDocumentInput(
        document=document,
        prompt=prompt,
        model=model,
    )
    return await analyze_document(params)


@conditional_tool(
    "llm_compare_images",
    annotations={
        "title": "Compare Images",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_compare_images(
    images: list[str],
    prompt: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Compare multiple images (2-4).

    Args:
        images: List of base64-encoded images or URLs
        prompt: Specific comparison criteria
        model: Vision-capable model to use

    Returns:
        Comparison analysis of the images.
    """
    return await compare_images(images, prompt, model)


# =============================================================================
# Reasoning Tools
# =============================================================================


@conditional_tool(
    "llm_chain_of_thought",
    annotations={
        "title": "Chain of Thought Reasoning",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_chain_of_thought(
    question: str,
    context: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Answer using step-by-step chain-of-thought reasoning.

    Args:
        question: The question to answer
        context: Optional context to inform the answer
        model: Model to use

    Returns:
        The reasoning steps and final answer.
    """
    params = ChainOfThoughtInput(question=question, context=context, model=model)
    return await chain_of_thought(params)


@conditional_tool(
    "llm_multi_step_reasoning",
    annotations={
        "title": "Multi-Step Reasoning",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_multi_step_reasoning(
    question: str,
    steps: Optional[list[str]] = None,
    model: Optional[str] = None,
) -> str:
    """
    Solve a problem using predefined reasoning steps.

    Args:
        question: The question or problem to solve
        steps: Custom reasoning steps (optional)
        model: Model to use

    Returns:
        Results from each step and final answer.
    """
    return await multi_step_reasoning(question, steps, model)


@conditional_tool(
    "llm_decompose_and_solve",
    annotations={
        "title": "Decompose and Solve",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_decompose_and_solve(
    problem: str,
    max_subproblems: int = 5,
    model: Optional[str] = None,
) -> str:
    """
    Decompose a complex problem into sub-problems and solve each.

    Args:
        problem: The complex problem to solve
        max_subproblems: Maximum sub-problems to create
        model: Model to use

    Returns:
        Sub-problems, solutions, and synthesized answer.
    """
    return await decompose_and_solve(problem, max_subproblems, model)


@conditional_tool(
    "llm_self_critique",
    annotations={
        "title": "Self-Critique and Improve",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_self_critique(
    question: str,
    initial_answer: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Generate, critique, and improve an answer.

    Args:
        question: The question to answer
        initial_answer: Optional initial answer to critique
        model: Model to use

    Returns:
        Initial answer, critique, and improved answer.
    """
    return await self_critique(question, initial_answer, model)


@conditional_tool(
    "llm_debate_reasoning",
    annotations={
        "title": "Multi-Perspective Debate",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_debate_reasoning(
    question: str,
    perspectives: Optional[list[str]] = None,
    model: Optional[str] = None,
) -> str:
    """
    Explore a question from multiple perspectives.

    Args:
        question: The question to debate
        perspectives: List of perspectives to consider
        model: Model to use

    Returns:
        Arguments from each perspective and conclusion.
    """
    return await debate_reasoning(question, perspectives, model)


@conditional_tool(
    "llm_verify_with_evidence",
    annotations={
        "title": "Verify Claim with Evidence",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tool_verify_with_evidence(
    claim: str,
    context: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Verify a claim by identifying supporting and contradicting evidence.

    Args:
        claim: The claim to verify
        context: Optional context with relevant information
        model: Model to use

    Returns:
        Supporting/contradicting evidence and verdict.
    """
    return await verify_with_evidence(claim, context, model)


# =============================================================================
# Statistics Tools
# =============================================================================


@conditional_tool(
    "llm_get_stats",
    annotations={
        "title": "Get Usage Statistics",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def tool_get_stats(
    time_period: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Get usage statistics for LLM calls.

    Returns comprehensive statistics about:
    - Total calls, tokens, and costs
    - Statistics per model
    - Statistics per tool
    - Filtered by time period and/or model

    Args:
        time_period: Filter by time period ('hour', 'day', 'week', 'month', 'all')
        model: Filter by specific model

    Returns:
        Usage statistics in JSON format.
    """
    params = GetStatsInput(
        time_period=time_period,
        model=model,
    )
    return await get_stats(params)


# =============================================================================
# Server Entry Point
# =============================================================================


def run_server():
    """Run the MCP server."""
    import sys
    
    settings = get_settings()
    
    # Validate API keys before starting
    is_valid, error_msg = settings.validate_api_keys()
    if not is_valid:
        # Write error to stderr so it's visible in vMCP UI and logs
        sys.stderr.write(f"{error_msg}\n")
        sys.stderr.flush()
        # Also log it
        logger.error(error_msg)
        # Exit with error code so vMCP can detect the failure
        sys.exit(1)
    
    logger.info(f"Starting LLM MCP Server with default model: {settings.default_model}")
    logger.info(f"Available providers: {', '.join(settings.get_available_providers())}")
    
    # Log enabled tools
    enabled_tools = settings.get_enabled_tools()
    all_tools = settings.get_all_available_tools()
    if enabled_tools is None:
        logger.info(f"All tools are enabled ({len(all_tools)} total)")
    else:
        logger.info(f"Enabled tools: {len(enabled_tools)}/{len(all_tools)}")
        logger.info(f"  Enabled: {', '.join(sorted(enabled_tools))}")
        disabled = set(all_tools) - enabled_tools
        if disabled:
            logger.info(f"  Disabled: {', '.join(sorted(disabled))}")
    
    mcp.run()


if __name__ == "__main__":
    run_server()
