"""
Tool modules for the LLM MCP Server.
"""

from llm_mcp.tools.discovery import (
    list_models,
    list_providers,
    get_model_info,
    estimate_cost,
    get_cheapest_model,
)
from llm_mcp.tools.direct import (
    llm_call,
    llm_chat,
    compare_models,
    llm_structured_output,
)
from llm_mcp.tools.analysis import (
    analyze_text,
    summarize,
    translate,
    extract_entities,
    extract_info,
    rewrite,
)
from llm_mcp.tools.multimodal import (
    analyze_image,
    describe_image,
    extract_text_from_image,
    analyze_pdf,
    compare_images,
    analyze_document,
)
from llm_mcp.tools.reasoning import (
    chain_of_thought,
    multi_step_reasoning,
    decompose_and_solve,
    self_critique,
    debate_reasoning,
    verify_with_evidence,
)
from llm_mcp.tools.stats import get_stats

__all__ = [
    # Discovery
    "list_models",
    "list_providers",
    "get_model_info",
    "estimate_cost",
    "get_cheapest_model",
    # Direct calls
    "llm_call",
    "llm_chat",
    "compare_models",
    "llm_structured_output",
    # Analysis
    "analyze_text",
    "summarize",
    "translate",
    "extract_entities",
    "extract_info",
    "rewrite",
    # Multimodal
    "analyze_image",
    "describe_image",
    "extract_text_from_image",
    "analyze_pdf",
    "compare_images",
    "analyze_document",
    # Reasoning
    "chain_of_thought",
    "multi_step_reasoning",
    "decompose_and_solve",
    "self_critique",
    "debate_reasoning",
    "verify_with_evidence",
    # Stats
    "get_stats",
]
