"""
Entry point for running the LLM MCP Server.

Usage:
    python -m llm_mcp
    
Or with the installed script:
    llm-mcp
"""

import sys
import argparse

from llm_mcp.server import run_server
from llm_mcp.config import get_settings


def main():
    """Main entry point for the LLM MCP Server."""
    parser = argparse.ArgumentParser(
        description="LLM MCP Server - Comprehensive LLM operations via MCP"
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check configuration and available providers",
    )
    
    args = parser.parse_args()
    
    if args.version:
        from llm_mcp import __version__
        print(f"llm-mcp version {__version__}")
        sys.exit(0)
    
    if args.check:
        settings = get_settings()
        
        # Validate API keys
        is_valid, error_msg = settings.validate_api_keys()
        
        print("LLM MCP Server Configuration")
        print("=" * 40)
        
        if not is_valid:
            print("\n❌ Configuration Error:")
            print(error_msg)
            sys.exit(1)
        
        providers = settings.get_available_providers()
        print(f"Default Model: {settings.default_model}")
        print(f"Temperature: {settings.default_temperature}")
        print(f"Max Tokens: {settings.default_max_tokens}")
        print(f"Timeout: {settings.timeout}s")
        print()
        print("Available Providers:")
        for provider in providers:
            print(f"  ✓ {provider}")
        print()
        print("Features:")
        print(f"  BAML: {'enabled' if settings.enable_baml else 'disabled'}")
        print(f"  DSPy: {'enabled' if settings.enable_dspy else 'disabled'}")
        print(f"  Cost Tracking: {'enabled' if settings.enable_cost_tracking else 'disabled'}")
        
        # Show enabled tools
        enabled_tools = settings.get_enabled_tools()
        all_tools = settings.get_all_available_tools()
        if enabled_tools is None:
            print(f"\nEnabled Tools: All ({len(all_tools)} total)")
        else:
            print(f"\nEnabled Tools: {len(enabled_tools)}/{len(all_tools)}")
            print(f"  {', '.join(sorted(enabled_tools))}")
        
        sys.exit(0)
    
    # Run the server
    run_server()


if __name__ == "__main__":
    main()
