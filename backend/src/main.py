"""
vMCP - Virtual Model Context Protocol
======================================

Main application entry point.
Creates and configures the FastAPI application with MCP server.
"""

import uvicorn
from vmcp.config import settings
from vmcp.utilities.logging import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


def main():
    """Run the vMCP server."""
    # CRITICAL: Register OSS services BEFORE creating app
    # Only register when running as main, not when imported by enterprise
    from vmcp.core.services import register_oss_services
    from vmcp.proxy_server import create_app

    register_oss_services()
    logger.info("✅ OSS services registered")

    # Create the FastAPI application with MCP server
    app = create_app()

    logger.info(f"🚀 Starting vMCP server on {settings.host}:{settings.port}")

    uvicorn.run(
        app,  # Pass app instance directly
        host=settings.host,
        port=settings.port,
        reload=settings.env == "development",
        log_level=settings.log_level.lower(),
        access_log=True
    )


if __name__ == "__main__":
    main()
