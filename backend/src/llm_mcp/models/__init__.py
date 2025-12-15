"""
Pydantic models for input validation and output types.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# =============================================================================
# Enums
# =============================================================================


class ResponseFormat(str, Enum):
    """Output format for tool responses."""

    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"


class AnalysisType(str, Enum):
    """Type of text analysis to perform."""

    SENTIMENT = "sentiment"
    TOPICS = "topics"
    ENTITIES = "entities"
    SUMMARY = "summary"
    ALL = "all"


class SummaryStyle(str, Enum):
    """Style for text summarization."""

    BRIEF = "brief"
    DETAILED = "detailed"
    BULLETS = "bullets"


class SentimentLabel(str, Enum):
    """Sentiment classification labels."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


# =============================================================================
# Input Models
# =============================================================================


class ListModelsInput(BaseModel):
    """Input for listing available models."""

    model_config = ConfigDict(str_strip_whitespace=True)

    provider: Optional[str] = Field(
        default=None,
        description="Filter by provider (openai, anthropic, google, etc.)",
    )
    capability: Optional[str] = Field(
        default=None,
        description="Filter by capability (chat, vision, function_calling, json_mode)",
    )


class LLMCallInput(BaseModel):
    """Input for basic LLM completion."""

    model_config = ConfigDict(str_strip_whitespace=True)

    prompt: str = Field(
        ...,
        description="The prompt to send to the LLM",
        min_length=1,
        max_length=100000,
    )
    model: Optional[str] = Field(
        default=None,
        description="Model identifier (e.g., 'openai/gpt-4o'). Uses default if not specified.",
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="Optional system prompt to set context",
        max_length=50000,
    )
    temperature: float = Field(
        default=0.7,
        description="Sampling temperature (0-2). Higher = more creative.",
        ge=0.0,
        le=2.0,
    )
    max_tokens: Optional[int] = Field(
        default=None,
        description="Maximum tokens to generate. Uses model default if not specified.",
        ge=1,
        le=100000,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.TEXT,
        description="Output format: text, json, or markdown",
    )

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Prompt cannot be empty or whitespace only")
        return v


class ChatMessage(BaseModel):
    """A single message in a chat conversation."""

    role: str = Field(
        ...,
        description="Message role: 'user', 'assistant', or 'system'",
    )
    content: str = Field(
        ...,
        description="Message content",
    )

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid_roles = {"user", "assistant", "system"}
        if v.lower() not in valid_roles:
            raise ValueError(f"Role must be one of: {valid_roles}")
        return v.lower()


class LLMChatInput(BaseModel):
    """Input for multi-turn chat completion."""

    model_config = ConfigDict(str_strip_whitespace=True)

    messages: list[ChatMessage] = Field(
        ...,
        description="List of chat messages",
        min_length=1,
    )
    model: Optional[str] = Field(
        default=None,
        description="Model identifier",
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="System prompt (added as first message if not present)",
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=100000)


class CompareModelsInput(BaseModel):
    """Input for comparing responses across models."""

    model_config = ConfigDict(str_strip_whitespace=True)

    prompt: str = Field(
        ...,
        description="The prompt to send to all models",
        min_length=1,
    )
    models: list[str] = Field(
        default=["openai/gpt-4o", "anthropic/claude-3-5-sonnet-20241022"],
        description="List of model identifiers to compare",
        min_length=1,
        max_length=5,
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    return_timing: bool = Field(
        default=True,
        description="Include response timing information",
    )


class ExtractEntitiesInput(BaseModel):
    """Input for entity extraction."""

    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(
        ...,
        description="Text to extract entities from",
        min_length=1,
        max_length=100000,
    )
    entity_types: Optional[list[str]] = Field(
        default=None,
        description="Types of entities to extract (person, organization, location, date, money, product)",
    )
    model: Optional[str] = Field(default=None)


class ExtractInfoInput(BaseModel):
    """Input for custom schema extraction."""

    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(
        ...,
        description="Text to extract information from",
        min_length=1,
    )
    output_schema: dict[str, Any] = Field(
        ...,
        description="JSON schema defining the structure to extract",
        alias="schema",
    )
    model: Optional[str] = Field(default=None)
    instructions: Optional[str] = Field(
        default=None,
        description="Additional instructions for extraction",
    )


class StructuredOutputInput(BaseModel):
    """Input for generic structured output."""

    model_config = ConfigDict(str_strip_whitespace=True)

    prompt: str = Field(
        ...,
        description="The prompt describing what to generate",
        min_length=1,
    )
    output_schema: dict[str, Any] = Field(
        ...,
        description="JSON schema for the output structure",
        alias="schema",
    )
    model: Optional[str] = Field(default=None)


class AnalyzeTextInput(BaseModel):
    """Input for text analysis."""

    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(
        ...,
        description="Text to analyze",
        min_length=1,
        max_length=100000,
    )
    analysis_type: AnalysisType = Field(
        default=AnalysisType.ALL,
        description="Type of analysis to perform",
    )
    model: Optional[str] = Field(default=None)


class SummarizeInput(BaseModel):
    """Input for text summarization."""

    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(
        ...,
        description="Text to summarize",
        min_length=10,
        max_length=200000,
    )
    style: SummaryStyle = Field(
        default=SummaryStyle.BRIEF,
        description="Summary style: brief, detailed, or bullets",
    )
    max_length: Optional[int] = Field(
        default=None,
        description="Maximum length of summary in words",
        ge=10,
        le=5000,
    )
    model: Optional[str] = Field(default=None)


class TranslateInput(BaseModel):
    """Input for text translation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(
        ...,
        description="Text to translate",
        min_length=1,
        max_length=50000,
    )
    target_language: str = Field(
        ...,
        description="Target language (e.g., 'Spanish', 'French', 'Japanese')",
    )
    source_language: Optional[str] = Field(
        default=None,
        description="Source language (auto-detected if not specified)",
    )
    model: Optional[str] = Field(default=None)


class ChainOfThoughtInput(BaseModel):
    """Input for chain-of-thought reasoning."""

    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(
        ...,
        description="The question to answer with reasoning",
        min_length=1,
    )
    context: Optional[str] = Field(
        default=None,
        description="Optional context to inform the answer",
    )
    model: Optional[str] = Field(default=None)


class AnalyzeImageInput(BaseModel):
    """Input for image analysis."""

    model_config = ConfigDict(str_strip_whitespace=True)

    image: str = Field(
        ...,
        description="Base64-encoded image data or URL",
    )
    prompt: str = Field(
        default="Describe this image in detail.",
        description="What to analyze or describe about the image",
    )
    model: Optional[str] = Field(
        default=None,
        description="Vision-capable model to use",
    )

    @field_validator("image")
    @classmethod
    def validate_image(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Image cannot be empty")
        # Basic validation - should be URL or base64
        if not (v.startswith("http") or len(v) > 100):
            raise ValueError("Image must be a URL or base64-encoded data")
        return v


class AnalyzePDFInput(BaseModel):
    """Input for PDF analysis."""

    model_config = ConfigDict(str_strip_whitespace=True)

    pdf_content: str = Field(
        ...,
        description="Base64-encoded PDF content",
    )
    prompt: str = Field(
        default="Analyze this PDF document and summarize its contents.",
        description="What to analyze about the PDF",
    )
    extract_images: bool = Field(
        default=False,
        description="Whether to also analyze images in the PDF",
    )
    model: Optional[str] = Field(default=None)


class AnalyzeDocumentInput(BaseModel):
    """Input for universal document analysis (auto-detects type)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    document: str = Field(
        ...,
        description="Document content: text, base64-encoded PDF, base64-encoded image, or image URL",
    )
    prompt: Optional[str] = Field(
        default=None,
        description="What to analyze about the document (optional)",
    )
    model: Optional[str] = Field(default=None)


class EstimateCostInput(BaseModel):
    """Input for cost estimation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    prompt: str = Field(
        ...,
        description="The prompt to estimate cost for",
        min_length=1,
    )
    model: Optional[str] = Field(
        default=None,
        description="Model identifier (uses default if not specified)",
    )
    estimated_output_tokens: Optional[int] = Field(
        default=None,
        description="Estimated output tokens (defaults to 500 if not specified)",
        ge=1,
        le=100000,
    )


class GetCheapestModelInput(BaseModel):
    """Input for finding the cheapest model."""

    model_config = ConfigDict(str_strip_whitespace=True)

    capability: Optional[str] = Field(
        default=None,
        description="Required capability (chat, vision, function_calling, etc.)",
    )
    provider: Optional[str] = Field(
        default=None,
        description="Filter by provider (openai, anthropic, etc.)",
    )
    prompt: Optional[str] = Field(
        default=None,
        description="Optional prompt to estimate cost based on actual usage",
    )
    estimated_output_tokens: Optional[int] = Field(
        default=None,
        description="Estimated output tokens for cost calculation",
        ge=1,
        le=100000,
    )


class GetStatsInput(BaseModel):
    """Input for usage statistics."""

    model_config = ConfigDict(str_strip_whitespace=True)

    time_period: Optional[str] = Field(
        default=None,
        description="Time period filter: 'hour', 'day', 'week', 'month', or 'all' (default)",
    )
    model: Optional[str] = Field(
        default=None,
        description="Filter by specific model",
    )


# =============================================================================
# Output Models
# =============================================================================


class TokenUsage(BaseModel):
    """Token usage information."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class LLMResponse(BaseModel):
    """Standard LLM response."""

    content: str
    model: str
    usage: Optional[TokenUsage] = None
    cost_estimate: Optional[float] = None


class EntityList(BaseModel):
    """Extracted entities."""

    people: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    money: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    other: list[str] = Field(default_factory=list)


class SentimentResult(BaseModel):
    """Sentiment analysis result."""

    sentiment: SentimentLabel
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class TextAnalysisResult(BaseModel):
    """Comprehensive text analysis result."""

    sentiment: Optional[SentimentResult] = None
    topics: list[str] = Field(default_factory=list)
    entities: Optional[EntityList] = None
    summary: Optional[str] = None
    word_count: int = 0
    model: str = ""


class ChainOfThoughtResult(BaseModel):
    """Chain-of-thought reasoning result."""

    reasoning: str
    answer: str
    model: str


class ModelInfo(BaseModel):
    """Information about a model."""

    id: str
    name: str
    provider: str
    capabilities: list[str]
    context_window: int
    max_output_tokens: int
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0


class ModelComparisonResult(BaseModel):
    """Result of comparing multiple models."""

    prompt: str
    results: dict[str, dict[str, Any]]
    fastest_model: Optional[str] = None
    cheapest_model: Optional[str] = None
