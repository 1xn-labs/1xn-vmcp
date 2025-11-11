"""
Middleware for the vMCP proxy server.

Handles URL routing and authentication for MCP requests.
"""

import json
import re
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from fastapi import FastAPI, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.requests import Request as StarletteRequest

from vmcp.config import settings
from vmcp.core.services import TokenInfo, get_jwt_service
from vmcp.utilities.logging import get_logger

# Setup centralized logging for middleware
logger = get_logger("vMCP Server Middleware")

# Setup Jinja2 templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Base URL from settings
BASE_URL = settings.base_url


def _inject_oss_dummy_token(request: Request) -> None:
    """
    Inject dummy Bearer token for OSS mode when Authorization header is missing.

    This allows OSS version to work without requiring real authentication.
    In Enterprise, this middleware can be overridden to skip token injection.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        # Inject dummy token for OSS
        dummy_token = f"Bearer {settings.dummy_user_token}"
        request.headers.__dict__["_list"].append((b"authorization", dummy_token.encode()))
        logger.debug(f"🔑 OSS: Injected dummy Bearer token for request to {request.url.path}")


def render_unauthorized_template(
    resource_metadata: str,
    error_description: str,
    vmcp_username: Optional[str] = None,
    vmcp_name: Optional[str] = None,
    base_url: Optional[str] = None,
    share_vMCP: bool = False,
    request_type: Optional[str] = None,
    is_sse_request: bool = False,
) -> Union[HTMLResponse, JSONResponse]:
    """Render the unauthorized HTML template with proper context"""
    if base_url is None:
        base_url = BASE_URL

    # Create a minimal request object for Jinja2 templating
    # Create a minimal scope for the request
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/vmcp/mcp",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 8000),
        "server": ("1xn.ai", 443),
        "scheme": "https",
        "extensions": {},
    }

    # Create a minimal request object
    request = StarletteRequest(scope)

    if request_type == "GET" and not is_sse_request:
        return templates.TemplateResponse(
            "simple_unauthorized.html",
            {
                "request": request,
                "resource_metadata": resource_metadata,
                "error_description": error_description,
                "base_url": base_url,
                # get the absolute url of the request
                "request_url": (
                    f"{base_url}/{vmcp_username}/{vmcp_name}/vmcp"
                    if vmcp_username
                    else f"{base_url}/{vmcp_name}/vmcp"
                ),
                "vmcp_username": vmcp_username,
                "vmcp_name": vmcp_name,
                "share_vMCP": share_vMCP,
            },
            status_code=200,
            headers={
                "WWW-Authenticate": (
                    f'Bearer error="invalid_token", error_description="{error_description}", '
                    f'resource_metadata="{resource_metadata}"'
                ),
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization, Content-Type, MCP-Protocol-Version, Accept",
            },
        )
    else:
        return JSONResponse(
            status_code=401,
            content={
                "error": "invalid_token",
                "error_description": error_description,
                "resource_metadata": resource_metadata,
            },
            headers={
                "WWW-Authenticate": (
                    f'Bearer error="invalid_token", error_description="{error_description}", '
                    f'resource_metadata="{resource_metadata}"'
                ),
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization, Content-Type, MCP-Protocol-Version, Accept",
            },
        )


async def handle_agent_initialize(request: Request, json_body: dict, bearer_token: str) -> None:
    """Handle agent initialization and management for MCP initialize requests"""
    logger.info("🚀 MCP INITIALIZE REQUEST DETECTED - Handling agent management")

    # Extract clientInfo from params
    params = json_body.get("params", {})
    client_info = params.get("clientInfo", {})
    agent_name = client_info.get("name", "unknown")
    agent_version = client_info.get("version", "unknown")

    # Sanitize agent name by replacing "/" with "_" to avoid file path issues
    agent_name = agent_name.replace("/", "_")

    logger.info("📋 Agent Info:")
    logger.info(f"   Agent Name: {agent_name}")
    logger.info(f"   Agent Version: {agent_version}")
    logger.info(f"   Bearer Token: {bearer_token[:10]}...")

    # Validate token and get user info
    jwt_service = get_jwt_service()
    try:
        raw_info = jwt_service.extract_token_info(bearer_token)
        token_info = TokenInfo(
            user_id=raw_info.get("user_id", ""),
            username=raw_info.get("username", ""),
            email=raw_info.get("email"),
            client_id=raw_info.get("client_id"),
            client_name=raw_info.get("client_name"),
            token=bearer_token,
        )
    except (ValueError, KeyError):
        logger.warning("❌ Invalid Bearer token for agent management")
        return

    # Extract normalized user information
    user_id = token_info.user_id
    user_name = token_info.username
    client_id = token_info.client_id or ""
    client_name = token_info.client_name or ""

    logger.info("📋 User Info:")
    logger.info(f"   User ID: {user_id}")
    logger.info(f"   Client ID: {client_id}")
    logger.info(f"   User Name: {user_name}")
    logger.info(f"   Client Name: {client_name}")

    # Store agent_name and user_id in request.state for response handler
    # Session ID will be available in response headers, not request headers
    request.state.agent_name = agent_name
    request.state.agent_user_id = int(user_id)

    # Handle agent management
    try:
        from vmcp.storage.base import StorageBase

        # Create user-specific storage handler
        user_storage = StorageBase(user_id=int(user_id))  # User mode

        # Save agent info
        agent_info = {
            "name": agent_name,
            "version": agent_version,
            "user_id": user_id,
            "client_id": client_id,
            "user_name": user_name,
            "client_name": client_name,
            "created_at": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "initialize_params": params,
        }

        info_success = user_storage.save_agent_info(agent_name, agent_info)  # type: ignore
        if info_success:
            logger.info(f"✅ Saved agent info for {agent_name}")
        else:
            logger.error(f"❌ Failed to save agent info for {agent_name}")

        # Save agent tokens
        tokens_success = user_storage.save_agent_tokens(agent_name, bearer_token)  # type: ignore
        if tokens_success:
            logger.info(f"✅ Saved agent tokens for {agent_name}")
        else:
            logger.error(f"❌ Failed to save agent tokens for {agent_name}")

        # Log the initialize call (session_id will be added later when available)
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "method": "initialize",
            "agent_name": agent_name,
            "user_id": user_id,
            "client_id": client_id,
            "params": params,
            "bearer_token": bearer_token[:10] + "...",
            "ip_address": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
            "session_id": None,  # Will be set when session_id is available in response
        }

        logs_success = user_storage.save_agent_logs(agent_name, log_entry)  # type: ignore
        if logs_success:
            logger.info(f"✅ Logged initialize call for {agent_name}")
        else:
            logger.error(f"❌ Failed to log initialize call for {agent_name}")

    except Exception as e:
        logger.error(f"❌ Error handling agent management: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")

    logger.info("✅ MCP INITIALIZE REQUEST PROCESSED")


async def log_mcp_call_for_agent(request: Request, json_body: dict, bearer_token: str) -> None:
    """Log MCP calls for agents (non-initialize requests)"""
    try:
        from vmcp.storage.base import StorageBase

        # Extract mcp-session-id from request headers (REQUIRED)
        session_id = request.headers.get("mcp-session-id")
        if not session_id:
            logger.debug("⚠️ No mcp-session-id in request headers - skipping agent logging")
            return

        # Get agent name from session mapping
        # Try with user_id from token first, then without
        jwt_service = get_jwt_service()
        try:
            raw_info = jwt_service.extract_token_info(bearer_token)
            token_info = TokenInfo(
                user_id=raw_info.get("user_id", ""),
                username=raw_info.get("username", ""),
                email=raw_info.get("email"),
                client_id=raw_info.get("client_id"),
                client_name=raw_info.get("client_name"),
                token=bearer_token,
            )
        except (ValueError, KeyError):
            logger.debug("⚠️ Invalid token for agent logging")
            return

        user_id = token_info.user_id
        client_id = token_info.client_id or ""

        # Get agent name from session mapping
        user_storage = StorageBase(user_id=int(user_id))
        agent_name = user_storage.get_agent_name_from_session(session_id)

        if not agent_name:
            logger.debug(f"⚠️ No agent mapping found for session {session_id[:20]}... - skipping agent logging")
            return

        # Log the MCP call
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "method": json_body.get("method", "unknown"),
            "agent_name": agent_name,
            "user_id": user_id,
            "client_id": client_id,
            "params": json_body.get("params", {}),
            "id": json_body.get("id"),
            "session_id": session_id,
            "bearer_token": bearer_token[:10] + "...",
            "ip_address": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
        }

        user_storage.save_agent_logs(agent_name, log_entry)  # type: ignore

    except Exception as e:
        # Silently fail for logging - don't affect the main request
        logger.debug(f"Could not log MCP call for agent: {e}")


async def vmcp_routing_middleware(request: Request, call_next):
    """Middleware to handle vMCP URL patterns and route them to MCP endpoint"""

    # Frontend routes that should NOT be processed by vMCP routing
    frontend_routes = {
        "app",
        "api",
        "health",
        "docs",
        "documentation",
        "static",
        "assets",
        "_next",
        "favicon.ico",
        "manifest.json",
        "robots.txt",
        "sitemap.xml",
    }

    path = request.url.path

    # Pattern: /{vmcp_username}/{vmcp_name}/vmcp
    match = re.match(r"^/([^/]+)/([^/]+)/vmcp/?$", path)
    if match:
        vmcp_username, vmcp_name = match.groups()

        # Skip if this is a frontend route
        if vmcp_username in frontend_routes or vmcp_name in frontend_routes:
            return await call_next(request)

        logger.info(f"🔄 vMCP Middleware: {vmcp_username}/{vmcp_name}/vmcp -> /vmcp/mcp")

        # Inject dummy Bearer token for OSS if missing
        _inject_oss_dummy_token(request)

        # Set headers and forward to MCP endpoint
        request.headers.__dict__["_list"].append((b"vmcp-username", vmcp_username.encode()))
        request.headers.__dict__["_list"].append((b"vmcp-name", vmcp_name.encode()))

        # Modify the request path
        request.scope["path"] = "/vmcp/mcp"
        return await call_next(request)

    # Pattern: /{vmcp_name}/vmcp (no username)
    match = re.match(r"^/([^/]+)/vmcp/?$", path)
    if match:
        vmcp_name = match.group(1)

        # Skip if this is a frontend route
        if vmcp_name in frontend_routes:
            return await call_next(request)

        logger.info(f"🔄 vMCP Middleware: {vmcp_name}/vmcp -> /vmcp/mcp")

        # Inject dummy Bearer token for OSS if missing
        _inject_oss_dummy_token(request)

        # Set headers and forward to MCP endpoint
        request.headers.__dict__["_list"].append((b"vmcp-name", vmcp_name.encode()))

        # Modify the request path
        request.scope["path"] = "/vmcp/mcp"
        return await call_next(request)

    # Pattern: /private/{vmcp_name}/vmcp (special case for private vMCPs)
    match = re.match(r"^/private/([^/]+)/vmcp/?$", path)
    if match:
        vmcp_name = match.group(1)

        # Skip if this is a frontend route
        if vmcp_name in frontend_routes:
            return await call_next(request)

        logger.info(f"🔄 vMCP Middleware: private/{vmcp_name}/vmcp -> /vmcp/mcp")

        # Inject dummy Bearer token for OSS if missing
        _inject_oss_dummy_token(request)

        # Set headers and forward to MCP endpoint
        request.headers.__dict__["_list"].append((b"vmcp-name", vmcp_name.encode()))
        request.headers.__dict__["_list"].append((b"vmcp-username", b"private"))

        # Modify the request path
        request.scope["path"] = "/vmcp/mcp"
        return await call_next(request)

    # No vMCP pattern matched, continue with normal processing
    return await call_next(request)


async def mcp_auth_middleware(request: Request, call_next):
    """MCP Authentication middleware per MCP Authorization specification"""
    logger.debug("In mcp_auth_middleware")
    # Determine if this is an MCP request
    is_mcp_request = request.url.path.startswith("/vmcp/mcp")  # or request.url.path == "/"

    logger.debug(f"is_mcp_request: {is_mcp_request} [request.url.path: {request.url.path}]")

    # Skip authentication for OAuth callback endpoints
    if request.url.path.startswith("/otherservers/oauth/callback"):
        logger.info(f"🔄 OAuth callback endpoint - skipping authentication: {request.url.path}")
        return await call_next(request)

    if is_mcp_request:
        # Redirect mcp/ -> mcp
        if request.url.path == "/vmcp/mcp/":
            logger.warning(f"🔄 MCP Redirect: {request.method} {request.url.path} -> /mcp")

            # Create redirect response
            redirect_response = RedirectResponse(url="/vmcp/mcp", status_code=307)

            # Preserve ALL headers from the original request
            for header_name, header_value in request.headers.items():
                # Skip some headers that shouldn't be forwarded
                if header_name.lower() not in ["host", "content-length"]:
                    redirect_response.headers[header_name] = header_value

            logger.info(f"📋 Preserved headers in redirect: {list(request.headers.keys())}")
            return redirect_response

        # Comprehensive MCP request logging
        logger.info("=" * 80)
        logger.info("🔄 MCP REQUEST RECEIVED")
        logger.info("=" * 80)
        logger.info("📋 Request Details:")
        logger.info(f"   Method: {request.method}")
        logger.info(f"   Full URL: {request.url}")
        logger.info(f"   Client Host: {request.client.host if request.client else 'Unknown'}")
        logger.info(f"   User Agent: {request.headers.get('user-agent', 'Unknown')}")

        # Log all headers
        logger.info("📋 Request Headers:")
        for header_name, header_value in request.headers.items():
            # Mask sensitive headers
            if header_name.lower() in ["authorization", "cookie"]:
                masked_value = f"{header_value[:10]}..." if len(header_value) > 10 else "***"
                logger.info(f"   {header_name}: {masked_value}")
            else:
                logger.info(f"   {header_name}: {header_value}")

        # Log query parameters if any
        if request.query_params:
            logger.info("📋 Query Parameters:")
            for key, value in request.query_params.items():
                logger.info(f"   {key}: {value}")

        # Log request body for POST/PUT requests
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    body_str = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
                    logger.info(f"📋 Request Body: {body_str}")
                    # Try to parse as JSON for better readability
                    try:
                        json_body = json.loads(body)
                        logger.info("📋 Parsed JSON Body:")
                        for key, value in json_body.items():
                            logger.info(f"   {key}: {value}")

                        # ==================== Check if this is an initialize request and handle agent management
                        if json_body.get("method") == "initialize":
                            # Extract Bearer token
                            bearer_token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
                            if bearer_token:
                                await handle_agent_initialize(request, json_body, bearer_token)
                            else:
                                logger.warning("❌ No Bearer token found for agent management")

                        # For all MCP calls, try to log them for the agent
                        else:
                            # Extract Bearer token and try to log the call
                            bearer_token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
                            if bearer_token:
                                await log_mcp_call_for_agent(request, json_body, bearer_token)
                        # ==================== End of agent management check
                    except json.JSONDecodeError:
                        logger.info(f"📋 Body is not JSON: {body_str}")
                else:
                    logger.info("📋 Request Body: Empty")
            except Exception as e:
                logger.info(f"📋 Could not read request body: {e}")

        # Handle CORS preflight
        if request.method == "OPTIONS":
            logger.info("📋 Handling CORS preflight for MCP")
            return Response(
                status_code=204,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
                    "Access-Control-Allow-Headers": "Authorization, Content-Type, MCP-Protocol-Version, Accept",
                    "Access-Control-Max-Age": "86400",
                },
            )

        # MCP Authorization specification: "When authorization is required and not yet proven by the client,
        # servers MUST respond with HTTP 401 Unauthorized"
        auth_header = request.headers.get("Authorization")
        logger.info(f"🔄 MCP AUTH: Authorization header: {auth_header}")
        vmcp_name = request.headers.get("vmcp-name")
        vmcp_username = request.headers.get("vmcp-username")
        share_vMCP_str = request.headers.get("share-vMCP", "false")
        share_vMCP = share_vMCP_str.lower() == "true" if isinstance(share_vMCP_str, str) else False

        # Check if this is an SSE request (GET with text/event-stream Accept header)
        is_sse_request = request.method == "GET" and "text/event-stream" in request.headers.get("Accept", "")
        if not auth_header:
            logger.info("❌ MCP AUTH: No Authorization header - returning HTTP 401")
            if vmcp_username:
                resource_metadata = (
                    f"{BASE_URL}/.well-known/oauth-protected-resource/{vmcp_username}/{vmcp_name}/vmcp"
                )
            else:
                resource_metadata = f"{BASE_URL}/.well-known/oauth-protected-resource/{vmcp_name}/vmcp"

            logger.info(f"🔄 MCP AUTH: Resource metadata URL: {resource_metadata}")
            return render_unauthorized_template(
                resource_metadata=resource_metadata,
                vmcp_username=vmcp_username,
                vmcp_name=vmcp_name,
                error_description="Missing Authorization header",
                share_vMCP=share_vMCP,
                request_type=request.method,  # POST or GET
                is_sse_request=is_sse_request,
            )

        if not auth_header.startswith("Bearer "):
            logger.info("❌ MCP AUTH: Invalid Authorization header format - returning HTTP 401")
            if vmcp_username:
                resource_metadata = (
                    f"{BASE_URL}/.well-known/oauth-protected-resource/{vmcp_username}/{vmcp_name}/vmcp"
                )
            else:
                resource_metadata = f"{BASE_URL}/.well-known/oauth-protected-resource/{vmcp_name}/vmcp"
            return render_unauthorized_template(
                resource_metadata=resource_metadata,
                vmcp_username=vmcp_username,
                vmcp_name=vmcp_name,
                error_description="Invalid authorization header format. Expected: Bearer <token>",
                share_vMCP=share_vMCP,
                request_type=request.method,  # POST or GET
                is_sse_request=is_sse_request,
            )

        # Extract token for validation
        token = auth_header.replace("Bearer", "").strip()

        # Add detailed token logging
        logger.info(
            f"🔍 MCP AUTH: Extracted token: {token[:20]}...{token[-10:] if len(token) > 30 else token}"
        )
        logger.info(f"🔍 MCP AUTH: Token length: {len(token)}")

        # Validate access token directly using JWT service
        try:
            jwt_service = get_jwt_service()

            # Validate token and extract normalized information
            try:
                raw_info = jwt_service.extract_token_info(token)
                token_info = TokenInfo(
                    user_id=raw_info.get("user_id", ""),
                    username=raw_info.get("username", ""),
                    email=raw_info.get("email"),
                    client_id=raw_info.get("client_id"),
                    client_name=raw_info.get("client_name"),
                    token=token,
                )
                logger.info(
                    f"🔍 MCP AUTH: JWT Token payload: user_id={token_info.user_id}, "
                    f"username={token_info.username}"
                )
            except (ValueError, KeyError) as e:
                logger.info(f"❌ MCP AUTH: Invalid access token - returning HTTP 401: {e}")
                if vmcp_username:
                    resource_metadata = (
                        f"{BASE_URL}/.well-known/oauth-protected-resource/{vmcp_username}/{vmcp_name}/vmcp"
                    )
                else:
                    resource_metadata = f"{BASE_URL}/.well-known/oauth-protected-resource/{vmcp_name}/vmcp"
                return render_unauthorized_template(
                    resource_metadata=resource_metadata,
                    vmcp_username=vmcp_username,
                    vmcp_name=vmcp_name,
                    error_description="Invalid or expired access token",
                    share_vMCP=share_vMCP,
                    request_type=request.method,  # POST or GET
                    is_sse_request=is_sse_request,
                )

            # Check if token is blacklisted (OSS version - no blacklist check)
            # db = next(get_db())  # OSS - no auth database
            # if jwt_service.is_token_blacklisted(token, db):  # OSS - no blacklist
            #     logger.warning("❌ MCP AUTH: Token has been revoked - returning HTTP 401")
            #     if vmcp_username:
            #         resource_metadata = f"{BASE_URL}/.well-known/oauth-protected-resource/{vmcp_username}/{vmcp_name}/vmcp"
            #     else:
            #         resource_metadata = f"{BASE_URL}/.well-known/oauth-protected-resource/{vmcp_name}/vmcp"
            #     return render_unauthorized_template(
            #         resource_metadata=resource_metadata,
            #         vmcp_username=vmcp_username,
            #         vmcp_name=vmcp_name,
            #         error_description="Token has been revoked",
            #         share_vMCP=share_vMCP,
            #         request_type=request.method,  # POST or GET
            #         is_sse_request=is_sse_request
            #     )

            # Extract normalized user information
            user_id = token_info.user_id
            client_id = token_info.client_id or ""
            client_name = token_info.client_name or ""

            # Store user context in request state for MCP methods to access
            request.state.user_id = user_id
            request.state.client_id = client_id
            request.state.client_name = client_name

            logger.info(
                f"✅ MCP AUTH: Verified access token for user {user_id}, "
                f"client {client_id if client_id else 'N/A'} - proceeding with request"
            )

        except Exception as e:
            logger.error(f"❌ MCP AUTH: Session validation error: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "auth_service_error"},
            )

    # Process the request
    response = await call_next(request)

    # Handle session mapping for initialize requests
    # Session ID is created by server and returned in response headers
    if is_mcp_request and hasattr(request.state, 'agent_name'):
        # This was an initialize request - capture session_id from response
        session_id = response.headers.get('mcp-session-id')
        if session_id:
            agent_name = getattr(request.state, 'agent_name', None)
            user_id = getattr(request.state, 'agent_user_id', None)
            
            if agent_name and user_id:
                try:
                    from vmcp.storage.base import StorageBase
                    user_storage = StorageBase(user_id=int(user_id))
                    mapping_success = user_storage.save_session_mapping(session_id, agent_name, int(user_id))
                    if mapping_success:
                        logger.info(f"✅ Saved session mapping: {session_id[:20]}... -> {agent_name}")
                        
                        # Update agent_info to include session_id
                        agent_info = user_storage.get_agent_info(agent_name)
                        if agent_info:
                            agent_info['session_id'] = session_id
                            agent_info['last_seen'] = datetime.now().isoformat()
                            user_storage.save_agent_info(agent_name, agent_info)
                    else:
                        logger.error(f"❌ Failed to save session mapping for {agent_name}")
                except Exception as e:
                    logger.error(f"❌ Error saving session mapping: {e}")
            else:
                logger.warning("⚠️ Missing agent_name or user_id for session mapping")
        else:
            logger.debug("⚠️ No mcp-session-id in response headers for initialize request")

    # Log response for MCP requests
    if is_mcp_request:
        logger.info("=" * 80)
        logger.info("✅ MCP RESPONSE SENT")
        logger.info("=" * 80)
        logger.info("📋 Response Details:")
        logger.info(f"   Status Code: {response.status_code}")
        logger.info(f"   Method: {request.method}")
        logger.info(f"   Path: {request.url.path}")

        # Log response headers
        logger.info("📋 Response Headers:")
        for header_name, header_value in response.headers.items():
            logger.info(f"   {header_name}: {header_value}")

        # Log response body for error responses
        if response.status_code >= 400:
            try:
                # For error responses, try to log the response body
                if hasattr(response, "body"):
                    response_body = response.body
                    if response_body:
                        logger.info(f"📋 Error Response Body: {response_body}")
            except Exception as e:
                logger.info(f"📋 Could not read error response body: {e}")

        logger.info("=" * 80)

    return response


def register_middleware(app: FastAPI) -> None:
    """
    Register all middleware functions on the FastAPI app.

    Note: In FastAPI/Starlette, middleware execute in REVERSE order of registration.
    So we register mcp_auth_middleware first, then vmcp_routing_middleware,
    which results in execution order:
    1. vmcp_routing_middleware - runs first to rewrite URLs
    2. mcp_auth_middleware - runs second to handle authentication
    """
    app.middleware("http")(mcp_auth_middleware)
    app.middleware("http")(vmcp_routing_middleware)
    logger.info("✅ Middleware registered: mcp_auth_middleware, vmcp_routing_middleware (executes in reverse order)")

