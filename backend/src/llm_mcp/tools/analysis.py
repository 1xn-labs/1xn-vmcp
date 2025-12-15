"""
Text analysis tools for summarization, translation, and more.
"""

import json
from typing import Any, Optional

import litellm

from llm_mcp.config import get_settings, DEFAULT_MODELS
from llm_mcp.models import (
    AnalyzeTextInput,
    SummarizeInput,
    TranslateInput,
    ExtractEntitiesInput,
    ExtractInfoInput,
    AnalysisType,
    SummaryStyle,
)
from llm_mcp.utils import handle_litellm_error, format_error_response


async def analyze_text(params: AnalyzeTextInput) -> str:
    """
    Perform comprehensive text analysis.

    This tool analyzes text for sentiment, topics, entities, and provides
    a summary. You can request specific analysis types or all.

    Args:
        params: Input parameters including:
            - text: Text to analyze
            - analysis_type: Type of analysis (sentiment, topics, entities, summary, all)
            - model: Model to use

    Returns:
        Analysis results including requested components.
    """
    settings = get_settings()
    model = params.model or DEFAULT_MODELS.get("extraction", settings.default_model)

    analysis_prompt = f"""Analyze the following text and provide a detailed analysis.

Text to analyze:
---
{params.text}
---

"""

    if params.analysis_type == AnalysisType.ALL:
        analysis_prompt += """Provide a comprehensive analysis including:
1. Sentiment: Is the text positive, negative, neutral, or mixed? Provide confidence (0-1) and brief reasoning.
2. Topics: What are the main topics discussed? List 3-5 key topics.
3. Entities: Extract named entities (people, organizations, locations, dates, monetary values).
4. Summary: Provide a brief 2-3 sentence summary.

Respond in JSON format:
{
    "sentiment": {"label": "positive|negative|neutral|mixed", "confidence": 0.0-1.0, "reasoning": "..."},
    "topics": ["topic1", "topic2", ...],
    "entities": {"people": [], "organizations": [], "locations": [], "dates": [], "money": []},
    "summary": "..."
}"""
    elif params.analysis_type == AnalysisType.SENTIMENT:
        analysis_prompt += """Analyze the sentiment of this text.

Respond in JSON format:
{
    "sentiment": {"label": "positive|negative|neutral|mixed", "confidence": 0.0-1.0, "reasoning": "..."}
}"""
    elif params.analysis_type == AnalysisType.TOPICS:
        analysis_prompt += """Extract the main topics from this text.

Respond in JSON format:
{
    "topics": ["topic1", "topic2", ...]
}"""
    elif params.analysis_type == AnalysisType.ENTITIES:
        analysis_prompt += """Extract named entities from this text.

Respond in JSON format:
{
    "entities": {"people": [], "organizations": [], "locations": [], "dates": [], "money": []}
}"""
    elif params.analysis_type == AnalysisType.SUMMARY:
        analysis_prompt += """Provide a concise summary of this text.

Respond in JSON format:
{
    "summary": "..."
}"""

    try:
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": analysis_prompt}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content

        # Parse and enrich result
        try:
            result = json.loads(content)
            result["model"] = response.model
            result["word_count"] = len(params.text.split())
            return json.dumps(result, indent=2)
        except json.JSONDecodeError:
            return json.dumps(
                {
                    "raw_response": content,
                    "model": response.model,
                    "word_count": len(params.text.split()),
                },
                indent=2,
            )

    except Exception as e:
        error = handle_litellm_error(e, model)
        return format_error_response(error)


async def summarize(params: SummarizeInput) -> str:
    """
    Summarize text with configurable style.

    This tool generates summaries in different styles: brief (1-2 sentences),
    detailed (paragraph), or bullet points.

    Args:
        params: Input parameters including:
            - text: Text to summarize
            - style: Summary style (brief, detailed, bullets)
            - max_length: Maximum summary length in words
            - model: Model to use

    Returns:
        Summary of the text in the requested style.
    """
    settings = get_settings()
    model = params.model or settings.default_model

    style_instructions = {
        SummaryStyle.BRIEF: "Provide a very brief summary in 1-2 sentences capturing the key point.",
        SummaryStyle.DETAILED: "Provide a detailed summary in one paragraph covering all main points.",
        SummaryStyle.BULLETS: "Provide a summary as bullet points, with each point being a key takeaway.",
    }

    prompt = f"""Summarize the following text.

{style_instructions[params.style]}

"""
    if params.max_length:
        prompt += f"Maximum length: approximately {params.max_length} words.\n\n"

    prompt += f"""Text to summarize:
---
{params.text}
---

Summary:"""

    try:
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        content = response.choices[0].message.content

        result = {
            "summary": content.strip(),
            "style": params.style.value,
            "original_word_count": len(params.text.split()),
            "summary_word_count": len(content.split()),
            "model": response.model,
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        error = handle_litellm_error(e, model)
        return format_error_response(error)


async def translate(params: TranslateInput) -> str:
    """
    Translate text between languages.

    This tool translates text to the specified target language.
    Source language is auto-detected if not specified.

    Args:
        params: Input parameters including:
            - text: Text to translate
            - target_language: Target language name
            - source_language: Source language (optional, auto-detected)
            - model: Model to use

    Returns:
        Translated text with language information.
    """
    settings = get_settings()
    model = params.model or settings.default_model

    if params.source_language:
        prompt = f"""Translate the following text from {params.source_language} to {params.target_language}.

Text:
{params.text}

Translation:"""
    else:
        prompt = f"""Translate the following text to {params.target_language}. 
Detect the source language automatically.

Text:
{params.text}

Respond in JSON format:
{{"source_language": "detected language", "translation": "translated text"}}"""

    try:
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        content = response.choices[0].message.content

        # Try to parse JSON response
        if not params.source_language:
            try:
                result = json.loads(content)
                result["target_language"] = params.target_language
                result["model"] = response.model
                return json.dumps(result, indent=2)
            except json.JSONDecodeError:
                pass

        # Fallback to simple format
        result = {
            "source_language": params.source_language or "auto-detected",
            "target_language": params.target_language,
            "translation": content.strip(),
            "model": response.model,
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        error = handle_litellm_error(e, model)
        return format_error_response(error)


async def extract_entities(params: ExtractEntitiesInput) -> str:
    """
    Extract named entities from text.

    This tool identifies and extracts named entities like people,
    organizations, locations, dates, and monetary values.

    Args:
        params: Input parameters including:
            - text: Text to extract entities from
            - entity_types: Specific types to extract (optional)
            - model: Model to use

    Returns:
        Extracted entities organized by type.
    """
    settings = get_settings()
    model = params.model or DEFAULT_MODELS.get("extraction", settings.default_model)

    if params.entity_types:
        types_str = ", ".join(params.entity_types)
        prompt = f"""Extract the following types of named entities from the text: {types_str}

Text:
{params.text}

Respond in JSON format with arrays for each entity type."""
    else:
        prompt = f"""Extract all named entities from the following text.

Text:
{params.text}

Respond in JSON format:
{{
    "people": ["list of person names"],
    "organizations": ["list of organization names"],
    "locations": ["list of location names"],
    "dates": ["list of dates or time references"],
    "money": ["list of monetary amounts"],
    "products": ["list of product names"],
    "other": ["other notable entities"]
}}

Only include categories that have entities found. Use empty arrays for categories with no entities."""

    try:
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content

        try:
            result = json.loads(content)
            result["model"] = response.model
            return json.dumps(result, indent=2)
        except json.JSONDecodeError:
            return json.dumps(
                {"raw_response": content, "model": response.model},
                indent=2,
            )

    except Exception as e:
        error = handle_litellm_error(e, model)
        return format_error_response(error)


async def extract_info(params: ExtractInfoInput) -> str:
    """
    Extract structured information using a custom schema.

    This tool extracts information from text according to a user-defined
    JSON schema.

    Args:
        params: Input parameters including:
            - text: Text to extract information from
            - schema: JSON schema defining the structure to extract
            - instructions: Additional extraction instructions
            - model: Model to use

    Returns:
        Extracted information matching the provided schema.
    """
    settings = get_settings()
    model = params.model or DEFAULT_MODELS.get("extraction", settings.default_model)

    schema_str = json.dumps(params.output_schema, indent=2)

    prompt = f"""Extract structured information from the following text according to this JSON schema:

Schema:
```json
{schema_str}
```

"""

    if params.instructions:
        prompt += f"""Additional instructions: {params.instructions}

"""

    prompt += f"""Text to extract from:
---
{params.text}
---

Respond ONLY with valid JSON matching the schema. Use null for missing values."""

    try:
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content

        try:
            result = json.loads(content)
            return json.dumps(
                {
                    "extracted": result,
                    "model": response.model,
                },
                indent=2,
            )
        except json.JSONDecodeError:
            return json.dumps(
                {
                    "raw_response": content,
                    "model": response.model,
                    "parse_error": "Failed to parse as JSON",
                },
                indent=2,
            )

    except Exception as e:
        error = handle_litellm_error(e, model)
        return format_error_response(error)


async def rewrite(
    text: str,
    style: Optional[str] = None,
    tone: Optional[str] = None,
    audience: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Rewrite text with a different style, tone, or for a different audience.

    Args:
        text: Text to rewrite
        style: Writing style (formal, casual, academic, etc.)
        tone: Tone (friendly, professional, persuasive, etc.)
        audience: Target audience (experts, beginners, executives, etc.)
        model: Model to use

    Returns:
        Rewritten text with the specified modifications.
    """
    settings = get_settings()
    model = model or settings.default_model

    instructions = []
    if style:
        instructions.append(f"Style: {style}")
    if tone:
        instructions.append(f"Tone: {tone}")
    if audience:
        instructions.append(f"Target audience: {audience}")

    if not instructions:
        instructions.append("Improve clarity and readability")

    prompt = f"""Rewrite the following text with these specifications:
{chr(10).join('- ' + i for i in instructions)}

Original text:
---
{text}
---

Rewritten text:"""

    try:
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )

        content = response.choices[0].message.content

        result = {
            "rewritten": content.strip(),
            "modifications": {
                "style": style,
                "tone": tone,
                "audience": audience,
            },
            "model": response.model,
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        error = handle_litellm_error(e, model)
        return format_error_response(error)
