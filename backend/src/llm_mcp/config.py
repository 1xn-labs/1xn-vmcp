"""
Configuration management for the LLM MCP Server.

Loads settings from environment variables and provides typed access.
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMMCPSettings(BaseSettings):
    """Settings for the LLM MCP Server."""

    model_config = SettingsConfigDict(
        env_prefix="LLM_MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provider API Keys
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    azure_api_key: Optional[str] = Field(default=None, alias="AZURE_API_KEY")
    azure_api_base: Optional[str] = Field(default=None, alias="AZURE_API_BASE")
    azure_api_version: Optional[str] = Field(
        default="2024-02-15-preview", alias="AZURE_API_VERSION"
    )
    together_api_key: Optional[str] = Field(default=None, alias="TOGETHER_API_KEY")
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    ollama_base_url: Optional[str] = Field(
        default="http://localhost:11434", alias="OLLAMA_BASE_URL"
    )

    # Server Configuration
    default_model: str = Field(default="openai/gpt-4o")
    default_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    default_max_tokens: int = Field(default=4096, ge=1)
    timeout: int = Field(default=60, ge=1)

    # Feature Flags
    enable_baml: bool = Field(default=True)
    enable_dspy: bool = Field(default=True)
    enable_cost_tracking: bool = Field(default=True)

    # Tool Configuration
    enabled_tools: Optional[str] = Field(
        default=None,
        description="Comma-separated list of enabled tool names, or 'all' for all tools. "
        "If not set, all tools are enabled by default.",
    )

    # Logging
    log_level: str = Field(default="INFO")

    def get_available_providers(self) -> list[str]:
        """Return list of providers with configured API keys."""
        providers = []
        if self.openai_api_key:
            providers.append("openai")
        if self.anthropic_api_key:
            providers.append("anthropic")
        if self.google_api_key:
            providers.append("google")
        if self.azure_api_key and self.azure_api_base:
            providers.append("azure")
        if self.together_api_key:
            providers.append("together")
        if self.groq_api_key:
            providers.append("groq")
        # Ollama is always potentially available (local)
        providers.append("ollama")
        return providers

    def validate_default_model(self) -> bool:
        """Check if the default model's provider is configured."""
        if "/" in self.default_model:
            provider = self.default_model.split("/")[0]
            return provider in self.get_available_providers()
        return True

    def get_enabled_tools(self) -> set[str]:
        """
        Get set of enabled tool names.

        Returns:
            Set of enabled tool names. If enabled_tools is None or 'all', returns None (all enabled).
        """
        if not self.enabled_tools or self.enabled_tools.lower() == "all":
            return None  # None means all tools enabled
        # Parse comma-separated list
        tools = [t.strip() for t in self.enabled_tools.split(",") if t.strip()]
        return set(tools)

    def is_tool_enabled(self, tool_name: str) -> bool:
        """
        Check if a specific tool is enabled.

        Args:
            tool_name: The tool name to check (e.g., 'llm_call', 'analyze_text')

        Returns:
            True if tool is enabled, False otherwise.
        """
        enabled = self.get_enabled_tools()
        if enabled is None:
            return True  # All tools enabled by default
        return tool_name in enabled

    @staticmethod
    def get_all_available_tools() -> list[str]:
        """
        Get list of all available tool names.

        Returns:
            List of all available tool names.
        """
        return [
            # Discovery
            "llm_list_models",
            "llm_list_providers",
            "llm_get_model_info",
            "llm_estimate_cost",
            "llm_get_cheapest_model",
            # Direct calls
            "llm_call",
            "llm_chat",
            "llm_compare_models",
            "llm_structured_output",
            # Analysis
            "llm_analyze_text",
            "llm_summarize",
            "llm_translate",
            "llm_extract_entities",
            "llm_extract_info",
            "llm_rewrite",
            # Multimodal
            "llm_analyze_image",
            "llm_describe_image",
            "llm_extract_text_from_image",
            "llm_analyze_pdf",
            "llm_analyze_document",
            "llm_compare_images",
            # Reasoning
            "llm_chain_of_thought",
            "llm_multi_step_reasoning",
            "llm_decompose_and_solve",
            "llm_self_critique",
            "llm_debate_reasoning",
            "llm_verify_with_evidence",
            # Stats
            "llm_get_stats",
        ]

    def validate_api_keys(self) -> tuple[bool, Optional[str]]:
        """
        Validate that at least one API key is configured.
        
        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is None.
        """
        providers = self.get_available_providers()
        # Remove ollama as it doesn't require API key
        cloud_providers = [p for p in providers if p != "ollama"]
        
        if not cloud_providers:
            missing_keys = []
            if not self.openai_api_key:
                missing_keys.append("OPENAI_API_KEY")
            if not self.anthropic_api_key:
                missing_keys.append("ANTHROPIC_API_KEY")
            if not self.google_api_key:
                missing_keys.append("GOOGLE_API_KEY")
            if not (self.azure_api_key and self.azure_api_base):
                missing_keys.append("AZURE_API_KEY and AZURE_API_BASE")
            if not self.together_api_key:
                missing_keys.append("TOGETHER_API_KEY")
            if not self.groq_api_key:
                missing_keys.append("GROQ_API_KEY")
            
            error_msg = (
                "❌ No API keys configured. At least one provider API key is required.\n\n"
                "Please configure at least one of the following API keys:\n"
                f"  • {', '.join(missing_keys[:3])}\n\n"
                "You can configure these in the vMCP UI when adding the LLM MCP server:\n"
                "  1. Go to MCP Servers tab\n"
                "  2. Add 'LLM MCP' server\n"
                "  3. Configure API keys in the Environment Variables section\n\n"
                "Or set them as environment variables before running:\n"
                "  export OPENAI_API_KEY='sk-...'\n"
                "  export ANTHROPIC_API_KEY='sk-ant-...'\n\n"
                "For more information, visit: https://1xn.ai/docs"
            )
            return False, error_msg
        
        return True, None


# Global settings instance
_settings: Optional[LLMMCPSettings] = None


def get_settings() -> LLMMCPSettings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = LLMMCPSettings()
    return _settings


def reload_settings() -> LLMMCPSettings:
    """Reload settings from environment."""
    global _settings
    _settings = LLMMCPSettings()
    return _settings


# Model catalog with capabilities
MODEL_CATALOG = {
    # OpenAI Models
    "openai/gpt-4o": {
        "name": "GPT-4o",
        "provider": "openai",
        "capabilities": ["chat", "vision", "function_calling", "json_mode"],
        "context_window": 128000,
        "max_output_tokens": 16384,
        "cost_per_1k_input": 0.0025,
        "cost_per_1k_output": 0.01,
    },
    "openai/gpt-4o-mini": {
        "name": "GPT-4o Mini",
        "provider": "openai",
        "capabilities": ["chat", "vision", "function_calling", "json_mode"],
        "context_window": 128000,
        "max_output_tokens": 16384,
        "cost_per_1k_input": 0.00015,
        "cost_per_1k_output": 0.0006,
    },
    "openai/gpt-4-turbo": {
        "name": "GPT-4 Turbo",
        "provider": "openai",
        "capabilities": ["chat", "vision", "function_calling", "json_mode"],
        "context_window": 128000,
        "max_output_tokens": 4096,
        "cost_per_1k_input": 0.01,
        "cost_per_1k_output": 0.03,
    },
    "openai/gpt-3.5-turbo": {
        "name": "GPT-3.5 Turbo",
        "provider": "openai",
        "capabilities": ["chat", "function_calling", "json_mode"],
        "context_window": 16385,
        "max_output_tokens": 4096,
        "cost_per_1k_input": 0.0005,
        "cost_per_1k_output": 0.0015,
    },
    # Anthropic Models
    "anthropic/claude-3-5-sonnet-20241022": {
        "name": "Claude 3.5 Sonnet",
        "provider": "anthropic",
        "capabilities": ["chat", "vision", "function_calling"],
        "context_window": 200000,
        "max_output_tokens": 8192,
        "cost_per_1k_input": 0.003,
        "cost_per_1k_output": 0.015,
    },
    "anthropic/claude-3-opus-20240229": {
        "name": "Claude 3 Opus",
        "provider": "anthropic",
        "capabilities": ["chat", "vision", "function_calling"],
        "context_window": 200000,
        "max_output_tokens": 4096,
        "cost_per_1k_input": 0.015,
        "cost_per_1k_output": 0.075,
    },
    "anthropic/claude-3-haiku-20240307": {
        "name": "Claude 3 Haiku",
        "provider": "anthropic",
        "capabilities": ["chat", "vision", "function_calling"],
        "context_window": 200000,
        "max_output_tokens": 4096,
        "cost_per_1k_input": 0.00025,
        "cost_per_1k_output": 0.00125,
    },
    # Google Models
    "google/gemini-1.5-pro": {
        "name": "Gemini 1.5 Pro",
        "provider": "google",
        "capabilities": ["chat", "vision", "function_calling"],
        "context_window": 1000000,
        "max_output_tokens": 8192,
        "cost_per_1k_input": 0.00125,
        "cost_per_1k_output": 0.005,
    },
    "google/gemini-1.5-flash": {
        "name": "Gemini 1.5 Flash",
        "provider": "google",
        "capabilities": ["chat", "vision", "function_calling"],
        "context_window": 1000000,
        "max_output_tokens": 8192,
        "cost_per_1k_input": 0.000075,
        "cost_per_1k_output": 0.0003,
    },
    # Together AI Models
    "together/meta-llama/Llama-3-70b-chat-hf": {
        "name": "Llama 3 70B",
        "provider": "together",
        "capabilities": ["chat"],
        "context_window": 8192,
        "max_output_tokens": 4096,
        "cost_per_1k_input": 0.0009,
        "cost_per_1k_output": 0.0009,
    },
    "together/mistralai/Mixtral-8x7B-Instruct-v0.1": {
        "name": "Mixtral 8x7B",
        "provider": "together",
        "capabilities": ["chat"],
        "context_window": 32768,
        "max_output_tokens": 4096,
        "cost_per_1k_input": 0.0006,
        "cost_per_1k_output": 0.0006,
    },
    # Groq Models
    "groq/llama3-70b-8192": {
        "name": "Llama 3 70B (Groq)",
        "provider": "groq",
        "capabilities": ["chat"],
        "context_window": 8192,
        "max_output_tokens": 8192,
        "cost_per_1k_input": 0.00059,
        "cost_per_1k_output": 0.00079,
    },
    "groq/mixtral-8x7b-32768": {
        "name": "Mixtral 8x7B (Groq)",
        "provider": "groq",
        "capabilities": ["chat"],
        "context_window": 32768,
        "max_output_tokens": 32768,
        "cost_per_1k_input": 0.00027,
        "cost_per_1k_output": 0.00027,
    },
    # Ollama Models (local)
    "ollama/llama3:8b": {
        "name": "Llama 3 8B (Local)",
        "provider": "ollama",
        "capabilities": ["chat"],
        "context_window": 8192,
        "max_output_tokens": 4096,
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
    },
    "ollama/mistral:7b": {
        "name": "Mistral 7B (Local)",
        "provider": "ollama",
        "capabilities": ["chat"],
        "context_window": 8192,
        "max_output_tokens": 4096,
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
    },
}

# Default models for specific tasks
DEFAULT_MODELS = {
    "chat": "openai/gpt-4o",
    "fast": "anthropic/claude-3-haiku-20240307",
    "reasoning": "anthropic/claude-3-5-sonnet-20241022",
    "vision": "openai/gpt-4o",
    "code": "anthropic/claude-3-5-sonnet-20241022",
    "extraction": "openai/gpt-4o-mini",
    "local": "ollama/llama3:8b",
}
