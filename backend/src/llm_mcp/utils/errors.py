"""
Error handling utilities for the LLM MCP Server.
"""

from typing import Any, Optional


class LLMMCPError(Exception):
    """Base exception for LLM MCP Server errors."""

    def __init__(
        self,
        message: str,
        error_type: str = "LLMMCPError",
        details: Optional[dict[str, Any]] = None,
        suggestions: Optional[list[str]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.details = details or {}
        self.suggestions = suggestions or []

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for response."""
        return {
            "error": True,
            "error_type": self.error_type,
            "message": self.message,
            "details": self.details,
            "suggestions": self.suggestions,
        }


class ValidationError(LLMMCPError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(
            message=message,
            error_type="ValidationError",
            details={"field": field} if field else {},
            suggestions=["Check the input parameters and try again"],
        )


class AuthenticationError(LLMMCPError):
    """Raised when API authentication fails."""

    def __init__(self, provider: str, message: Optional[str] = None):
        super().__init__(
            message=message or f"Authentication failed for provider: {provider}",
            error_type="AuthenticationError",
            details={"provider": provider},
            suggestions=[
                f"Check that your {provider.upper()}_API_KEY is set correctly",
                "Verify the API key is valid and not expired",
                f"Visit the {provider} dashboard to generate a new key if needed",
            ],
        )


class ProviderError(LLMMCPError):
    """Raised when an LLM provider returns an error."""

    def __init__(
        self,
        provider: str,
        model: str,
        message: str,
        status_code: Optional[int] = None,
    ):
        super().__init__(
            message=f"Provider error from {provider}: {message}",
            error_type="ProviderError",
            details={
                "provider": provider,
                "model": model,
                "status_code": status_code,
            },
            suggestions=[
                "Check if the model is available and correctly specified",
                "Verify your API key has access to this model",
                "Try a different model or provider",
            ],
        )


class RateLimitError(LLMMCPError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        provider: str,
        model: str,
        retry_after: Optional[int] = None,
    ):
        suggestions = [
            f"Wait before making more requests",
            "Try a different model: consider using a smaller/cheaper model",
            f"Check your rate limits at the {provider} dashboard",
        ]
        if retry_after:
            suggestions[0] = f"Wait {retry_after} seconds before retrying"

        super().__init__(
            message=f"Rate limit exceeded for {model}",
            error_type="RateLimitError",
            details={
                "provider": provider,
                "model": model,
                "retry_after": retry_after,
            },
            suggestions=suggestions,
        )


class ModelNotFoundError(LLMMCPError):
    """Raised when a model is not found or not accessible."""

    def __init__(self, model: str, available_models: Optional[list[str]] = None):
        suggestions = [
            f"Check that the model identifier '{model}' is correct",
            "Use llm_list_models to see available models",
        ]
        if available_models:
            suggestions.append(f"Available models include: {', '.join(available_models[:5])}")

        super().__init__(
            message=f"Model not found: {model}",
            error_type="ModelNotFoundError",
            details={"model": model, "available_models": available_models},
            suggestions=suggestions,
        )


class TimeoutError(LLMMCPError):
    """Raised when a request times out."""

    def __init__(self, model: str, timeout: int):
        super().__init__(
            message=f"Request to {model} timed out after {timeout} seconds",
            error_type="TimeoutError",
            details={"model": model, "timeout": timeout},
            suggestions=[
                "Try again - the provider may be experiencing high load",
                "Use a smaller prompt or reduce max_tokens",
                "Try a faster model like gpt-3.5-turbo or claude-3-haiku",
            ],
        )


class ContentFilterError(LLMMCPError):
    """Raised when content is filtered by the provider."""

    def __init__(self, provider: str, model: str):
        super().__init__(
            message=f"Content was filtered by {provider}'s safety system",
            error_type="ContentFilterError",
            details={"provider": provider, "model": model},
            suggestions=[
                "Review the prompt for potentially problematic content",
                "Rephrase the request to be more specific and appropriate",
            ],
        )


class UnsupportedFeatureError(LLMMCPError):
    """Raised when a feature is not supported by the model."""

    def __init__(self, feature: str, model: str, supported_models: Optional[list[str]] = None):
        suggestions = [f"Use a model that supports {feature}"]
        if supported_models:
            suggestions.append(f"Models with {feature}: {', '.join(supported_models[:3])}")

        super().__init__(
            message=f"Model {model} does not support {feature}",
            error_type="UnsupportedFeatureError",
            details={
                "feature": feature,
                "model": model,
                "supported_models": supported_models,
            },
            suggestions=suggestions,
        )


def handle_litellm_error(error: Exception, model: str) -> LLMMCPError:
    """Convert LiteLLM exceptions to LLMMCPError."""
    error_str = str(error).lower()
    error_class = type(error).__name__

    # Extract provider from model
    provider = model.split("/")[0] if "/" in model else "unknown"

    # Check for common error patterns
    if "rate limit" in error_str or "429" in error_str:
        return RateLimitError(provider=provider, model=model)

    if "authentication" in error_str or "401" in error_str or "api key" in error_str:
        return AuthenticationError(provider=provider)

    if "not found" in error_str or "404" in error_str or "does not exist" in error_str:
        return ModelNotFoundError(model=model)

    if "timeout" in error_str or error_class == "Timeout":
        return TimeoutError(model=model, timeout=60)

    if "content" in error_str and ("filter" in error_str or "policy" in error_str):
        return ContentFilterError(provider=provider, model=model)

    if "context length" in error_str or "too long" in error_str:
        return ValidationError(
            message=f"Input exceeds model's context length",
            field="prompt",
        )

    # Generic provider error
    return ProviderError(
        provider=provider,
        model=model,
        message=str(error),
    )


def format_error_response(error: Exception) -> str:
    """Format an error as a JSON string for tool response."""
    import json

    if isinstance(error, LLMMCPError):
        return json.dumps(error.to_dict(), indent=2)

    # Generic error
    return json.dumps(
        {
            "error": True,
            "error_type": type(error).__name__,
            "message": str(error),
            "suggestions": ["Try again or check the server logs for more details"],
        },
        indent=2,
    )
