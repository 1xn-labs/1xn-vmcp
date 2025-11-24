"""
vMCP API Server - FastAPI Application
=====================================

This module contains the FastAPI application that serves as the HTTP server
for vMCP. It mounts the MCP protocol server and provides REST API endpoints.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from vmcp.config import settings
from vmcp.mcps.oauth_handler import router as oauth_handler_router
from vmcp.mcps.router_typesafe import router as mcp_router
from vmcp.server.middleware import register_middleware
from vmcp.server.vmcp_mcp_server import VMCPServer
from vmcp.storage.blob_router import router as blob_router
from vmcp.utilities.logging import get_logger
from vmcp.utilities.tracing import add_tracing_middleware
from vmcp.vmcps.router_typesafe import router as vmcp_router
from vmcp.vmcps.stats_router import router as stats_router


# Setup centralized logging for API server
logger = get_logger("VMCPApiServer")


# Create MCP server instance
logger.info("[VMCPApiServer] Creating VMCPServer instance...")
vmcp = VMCPServer("1xn vMCP MCP server")

# Create unified FastAPI server
# Create the FastMCP HTTP app first to get its lifespan
logger.info("[VMCPApiServer] Creating FastMCP streamable HTTP app...")
vmcp_http_app = vmcp.streamable_http_app()


# Lifespan context manager for MCP session management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the MCP session manager lifecycle and database initialization"""
    logger.info("[VMCPApiServer] Starting application startup...")

    # Initialize database tables (creates missing tables, preserves existing data)
    try:
        from vmcp.storage.database import init_db

        logger.info("[VMCPApiServer] Initializing database tables...")
        init_db()

        logger.info("[VMCPApiServer] Ensuring user exists...")
        # User creation is handled by oss_providers.ensure_dummy_user() during registration
        from vmcp.core.services.oss_providers import ensure_dummy_user
        ensure_dummy_user()

        logger.info("[VMCPApiServer] Database initialization complete")
    except Exception as e:
        logger.warning(f"[VMCPApiServer] Database initialization warning: {e}")
        logger.info("[VMCPApiServer] Continuing anyway (database may already be initialized)")

    logger.info("[VMCPApiServer] Starting MCP session manager...")

    # Create shutdown event
    shutdown_event = asyncio.Event()
    session_task = None

    async def run_session_manager():
        try:
            async with vmcp.session_manager.run():
                # Wait for shutdown signal instead of blocking indefinitely
                await shutdown_event.wait()
        except asyncio.CancelledError:
            logger.info("[VMCPApiServer] MCP session manager cancelled")
        except Exception as e:
            logger.error(f"[VMCPApiServer] MCP session manager error: {e}")

    # Start the session manager task
    session_task = asyncio.create_task(run_session_manager())

    try:
        logger.info("[VMCPApiServer] MCP session manager started")
        yield
    finally:
        logger.info("[VMCPApiServer] Shutting down MCP session manager...")
        # Note: stdio cleanup is now handled by VMCPSessionManager.run()

        # Signal shutdown
        shutdown_event.set()

        if session_task:
            try:
                await asyncio.wait_for(session_task, timeout=3.0)
            except asyncio.TimeoutError:
                logger.warning("[VMCPApiServer] MCP session manager shutdown timeout, forcing cancellation")
                session_task.cancel()
                try:
                    await asyncio.wait_for(session_task, timeout=1.0)
                except asyncio.CancelledError:
                    pass  # Expected
            except asyncio.CancelledError:
                pass  # Expected
        logger.info("[VMCPApiServer] MCP session manager shutdown complete")


# Use custom lifespan management for MCP session
app = FastAPI(
    title="1xn vMCP App server",
    description="1xn vMCP MCP server with management API",
    lifespan=lifespan,
    redirect_slashes=False  # Prevent automatic redirects that lose Authorization headers
)

app.state.vmcp_server = vmcp

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OSS version - no analytics middleware
logger.info("[VMCPApiServer] Analytics disabled in OSS version")

# Add tracing middleware with exclusions to reduce noise (if enabled)
if settings.enable_tracing:
    add_tracing_middleware(
        app,
        "vmcp-server",
        excluded_paths={
            "/health",
            "/api/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/favicon.ico"
        },
        excluded_prefixes={
            "/static/",
            "/assets/",
            "/app/",
            "/api/docs",
            "/api/traces"
        }
    )
    # Add traces API router if available
    try:
        from vmcp.utilities.tracing import traces_api_router  # type: ignore
        app.include_router(traces_api_router, prefix="/api")
    except (ImportError, AttributeError):
        logger.info("[VMCPApiServer] Traces API router not available")

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/api/proxystatic", StaticFiles(directory=str(static_dir)), name="static")

# Register middleware (routing first, then authentication)
register_middleware(app)


# ================================================
# API Endpoints
# ================================================

# OSS: Root redirects directly to vMCP list page
@app.get("/")
async def root():
    """Redirect to vMCP page - OSS has no separate landing page"""
    return RedirectResponse(url="/app/vmcp")


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


@app.get("/api/config")
async def get_config():
    """Get server configuration including base URL"""
    return {
        "base_url": settings.base_url,
        "host": settings.host,
        "port": settings.port,
        "app_name": settings.app_name,
        "version": settings.app_version
    }


# ================================================
# Mount API Routers
# ================================================

# Mount the API routes (OSS version - minimal routers)
logger.info("[VMCPApiServer] Mounting API routes...")
app.include_router(mcp_router, prefix="/api")
app.include_router(vmcp_router, prefix="/api")
app.include_router(oauth_handler_router, prefix="/api")
app.include_router(blob_router, prefix="/api")
app.include_router(stats_router, prefix="/api")

# Mount the MCP server (now with shared lifespan)
logger.info("[VMCPApiServer] Mounting MCP server with shared lifespan...")
app.mount("/vmcp/", vmcp_http_app, name="1xn_mcp_server")
logger.debug(f"[VMCPApiServer] MCP HTTP app routes: {app.routes}")
logger.info("[VMCPApiServer] MCP server mounted at /vmcp/mcp")


# ================================================
# Serve frontend with SPA routing support
# Try to find frontend in public/frontend (for packaged version or development)
# First try: environment variable (for enterprise override)
# ================================================

frontend_path_env = os.getenv("VMCP_FRONTEND_PATH")
if frontend_path_env:
    frontend_dist = Path(frontend_path_env)
    # If relative path, resolve from project root
    if not frontend_dist.is_absolute():
        project_root = os.getenv("VMCP_PROJECT_ROOT")
        if project_root:
            frontend_dist = Path(project_root) / frontend_dist
else:
    # Second try: packaged version (vmcp/public/frontend inside site-packages)
    frontend_dist = Path(__file__).parent.parent / "public" / "frontend"
    # Third try: development version (backend/public/frontend)
    if not frontend_dist.exists():
        frontend_dist = Path(__file__).parent.parent.parent.parent / "public" / "frontend"

if frontend_dist.exists():
    logger.info(f"[VMCPApiServer] Serving frontend from {frontend_dist}")

    # Serve static assets (CSS, JS, etc.)
    @app.get("/app/assets/{file_path:path}")
    async def serve_assets(file_path: str):
        """Serve static assets"""
        asset_file = frontend_dist / "assets" / file_path
        if asset_file.is_file():
            # Determine media type based on file extension
            media_type = None
            headers = {}

            if file_path.endswith('.css'):
                media_type = 'text/css; charset=utf-8'
                headers['Cache-Control'] = 'public, max-age=31536000'
            elif file_path.endswith('.js'):
                media_type = 'application/javascript; charset=utf-8'
                headers['Cache-Control'] = 'public, max-age=31536000'
            elif file_path.endswith('.ico'):
                media_type = 'image/x-icon'
                headers['Cache-Control'] = 'public, max-age=31536000'

            return FileResponse(asset_file, media_type=media_type, headers=headers)
        raise HTTPException(status_code=404, detail="Asset not found")

    # Catch-all for SPA routes - serve index.html for all other /app/* routes
    @app.get("/app/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve SPA - index.html for all routes, or specific files if they exist"""
        # Check if it's a specific file request (has extension)
        if "." in full_path:
            file_path = frontend_dist / full_path
            if file_path.is_file():
                return FileResponse(file_path)
        # For routes without extension, serve index.html (SPA routing)
        return FileResponse(frontend_dist / "index.html")

    # Serve index.html for /app/ (root of app)
    @app.get("/app/")
    async def serve_app_root():
        """Serve index.html for app root"""
        return FileResponse(frontend_dist / "index.html")

    logger.info("[VMCPApiServer] Frontend served at /app with SPA routing")
else:
    logger.warning(f"[VMCPApiServer] Frontend build directory not found at {frontend_dist}")


# ================================================
# Serve documentation from public/documentation
# First try: environment variable (for enterprise override)
# ================================================

docs_path_env = os.getenv("VMCP_DOCS_PATH")
if docs_path_env:
    documentation_dist = Path(docs_path_env)
    # If relative path, resolve from project root
    if not documentation_dist.is_absolute():
        project_root = os.getenv("VMCP_PROJECT_ROOT")
        if project_root:
            documentation_dist = Path(project_root) / documentation_dist
else:
    # Second try: packaged version
    documentation_dist = Path(__file__).parent.parent / "public" / "documentation"
    # Third try: development version
    if not documentation_dist.exists():
        documentation_dist = Path(__file__).parent.parent.parent.parent / "public" / "documentation"

if documentation_dist.exists():
    logger.info(f"[VMCPApiServer] Serving documentation from {documentation_dist}")

    # Mount documentation as static files
    app.mount("/documentation", StaticFiles(directory=str(documentation_dist), html=True), name="documentation")
    logger.info("[VMCPApiServer] Documentation served at /documentation")
else:
    logger.debug(f"[VMCPApiServer] Documentation build directory not found at {documentation_dist}")


def create_app():
    """Factory function to create FastAPI app instance."""
    return app
