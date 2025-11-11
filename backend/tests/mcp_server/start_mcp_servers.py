#!/usr/bin/env python3
"""
MCP Server Launcher - Starts both everything and allfeature servers
on localhost:8001 with endpoints /everything and /allfeature
"""

import contextlib

import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount

# Import the MCP servers
try:
    # Try relative imports first (when used as a package)
    from .all_feature_server import mcp as all_feature_mcp  # type: ignore[import-untyped]
    from .everything_server import mcp as everything_mcp  # type: ignore[import-untyped]
except ImportError:
    # Fall back to absolute imports (when run directly)
    from all_feature_server import mcp as all_feature_mcp  # type: ignore[import-untyped]
    from everything_server import mcp as everything_mcp  # type: ignore[import-untyped]


@contextlib.asynccontextmanager
async def lifespan(app: Starlette):
    """Manage the lifespan of both MCP servers."""
    async with contextlib.AsyncExitStack() as stack:
        # Start both session managers
        await stack.enter_async_context(all_feature_mcp.session_manager.run())
        await stack.enter_async_context(everything_mcp.session_manager.run())
        yield


# Create the Starlette app and mount the MCP servers
app = Starlette(
    routes=[
        Mount("/allfeature", all_feature_mcp.streamable_http_app()),
        Mount("/everything", everything_mcp.streamable_http_app()),
    ],
    lifespan=lifespan,
)


@app.route("/health")
async def health_check(request):
    """Health check endpoint."""
    return JSONResponse({
        "status": "healthy",
        "service": "mcp_servers",
        "endpoints": {
            "everything": "/everything",
            "allfeature": "/allfeature"
        },
        "port": 8001
    })


@app.route("/")
async def root(request):
    """Root endpoint with service information."""
    return JSONResponse({
        "service": "MCP Servers",
        "version": "1.0.0",
        "description": "Combined MCP server with everything and allfeature endpoints",
        "endpoints": {
            "everything": "http://localhost:8001/everything",
            "allfeature": "http://localhost:8001/allfeature",
            "health": "http://localhost:8001/health"
        },
        "usage": {
            "uvx": "uvx vmcp start_mcp_servers",
            "uv_run": "uv run vmcp start_mcp_servers",
            "direct": "python start_mcp_servers.py"
        }
    })


def main():
    """Main entry point for the MCP servers."""
    print("🚀 Starting MCP Servers...")
    print("📊 Everything Server: http://localhost:8001/everything")
    print("🔧 All Feature Server: http://localhost:8001/allfeature")
    print("❤️  Health Check: http://localhost:8001/health")
    print("=" * 60)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )


if __name__ == "__main__":
    main()
