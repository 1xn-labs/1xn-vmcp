"""
Type-Safe MCP Router with Proper Request/Response Models

This router provides type-safe endpoints for managing MCP (Model Context Protocol) servers.
All endpoints now use proper Pydantic request and response models for full type safety.
"""

import traceback
from datetime import datetime
from typing import Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

# Import type-safe models
from vmcp.mcps.mcp_client import AuthenticationError, MCPClientManager
from vmcp.mcps.mcp_configmanager import MCPConfigManager
from vmcp.mcps.models import (
    MCPAuthConfig,
    MCPCapabilitiesResponse,
    MCPConnectionResponse,
    MCPConnectionStatus,
    MCPDisconnectResponse,
    # Request models
    MCPInstallRequest,
    # Response models
    MCPInstallResponse,
    MCPListResponse,
    MCPPingResponse,
    MCPPromptRequest,
    MCPPromptResponse,
    MCPPromptsResponse,
    MCPRenameResponse,
    MCPResourceRequest,
    MCPResourceResponse,
    MCPResourcesResponse,
    MCPServerConfig,
    # Base models
    MCPServerInfo,
    MCPStatsResponse,
    MCPStatusResponse,
    MCPToolCallRequest,
    MCPToolCallResponse,
    MCPToolsDiscoverResponse,
    MCPToolsResponse,
    # Legacy compatibility
    MCPTransportType,
    MCPUninstallResponse,
    MCPUpdateRequest,
    MCPUpdateResponse,
    RegistryServerInfo,
    # Registry models
    RegistryServersResponse,
    RenameServerRequest,
)
from vmcp.shared.mcp_content_models import (
    MCPCapabilitiesStats,
    MCPConnectionInfo,
    MCPPingInfo,
    MCPServerStats,
    MCPServerStatus,
    MCPSystemStats,
    MCPToolsDiscovery,
)
from vmcp.shared.models import BaseResponse
from vmcp.storage.dummy_user import UserContext, get_user_context
from vmcp.utilities.logging.config import setup_logging
from vmcp.vmcps.vmcp_config_manager import VMCPConfigManager

logger = setup_logging("1xN_MCP_ROUTER_TYPESAFE")

def get_server_not_found_error(server_name: str, config_manager: MCPConfigManager) -> HTTPException:
    """Helper function to create a helpful server not found error"""
    available_servers = config_manager.list_servers()
    available_names = [s.name for s in available_servers]

    error_detail = f"Server '{server_name}' not found"
    if available_names:
        error_detail += f". Available servers: {', '.join(available_names)}"
    else:
        error_detail += ". No servers are currently installed. Please install a server first using the /install endpoint."

    return HTTPException(status_code=404, detail=error_detail)

def get_server_not_found_error_by_id(server_id: str, config_manager: MCPConfigManager) -> HTTPException:
    """Helper function to create a helpful server not found error for server ID"""
    available_servers = config_manager.list_servers()
    available_ids = [s.server_id for s in available_servers if s.server_id]

    error_detail = f"Server with ID '{server_id}' not found"
    if available_ids:
        error_detail += f". Available server IDs: {', '.join(available_ids[:5])}"  # Show first 5 IDs
        if len(available_ids) > 5:
            error_detail += f" and {len(available_ids) - 5} more"
    else:
        error_detail += ". No servers are currently installed. Please install a server first using the /install endpoint."

    return HTTPException(status_code=404, detail=error_detail)

router = APIRouter(prefix="/mcps", tags=["MCPs"])

# ============================================================================
# HEALTH AND UTILITY ENDPOINTS
# ============================================================================

@router.get("/health", response_model=BaseResponse[Dict[str, str]])
async def health_check() -> BaseResponse[Dict[str, str]]:
    """Health check endpoint for the unified backend server management"""
    return BaseResponse(
        success=True,
        message="MCP service is healthy",
        data={
            "status": "healthy",
            "service": "1xN Unified Backend - MCP Server Management"
        }
    )

# ============================================================================
# SERVER MANAGEMENT ENDPOINTS
# ============================================================================

@router.post("/install", response_model=MCPInstallResponse)
async def install_mcp_server(
    request: MCPInstallRequest,
    background_tasks: BackgroundTasks,
    user_context: UserContext = Depends(get_user_context)
) -> MCPInstallResponse:
    """Install a new MCP server with type-safe request/response models."""

    # Get managers from global connection manager
    config_manager = MCPConfigManager(str(user_context.user_id))

    # Validate transport mode
    try:
        transport_type = MCPTransportType(request.mode.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode. Use: {', '.join([t.value for t in MCPTransportType])}"
        ) from None

    # Validate required fields based on transport type
    if transport_type == MCPTransportType.STDIO:
        if not request.command:
            raise HTTPException(status_code=400, detail="Command required for stdio mode")
    elif transport_type in [MCPTransportType.HTTP, MCPTransportType.SSE]:
        if not request.url:
            raise HTTPException(status_code=400, detail="URL required for http/sse mode")

    # Check if server already exists
    if config_manager.get_server(request.name):
        raise HTTPException(status_code=409, detail=f"Server '{request.name}' already exists")

    # Create auth config
    auth_config = None
    if request.auth_type and request.auth_type != "none":
        from vmcp.shared.models import AuthType
        auth_config = MCPAuthConfig(
            type=AuthType(request.auth_type),
            client_id=request.client_id,
            client_secret=request.client_secret,
            auth_url=request.auth_url,
            token_url=request.token_url,
            scope=request.scope,
            access_token=request.access_token,
            refresh_token=None,
            expires_at=None
        )

    # Create server config
    server_config = MCPServerConfig(
        name=request.name,
        transport_type=transport_type,
        description=request.description,
        command=request.command,
        args=request.args,
        env=request.env,
        url=request.url,
        headers=request.headers,
        auth=auth_config,
        auto_connect=request.auto_connect,
        enabled=request.enabled
    )

    # Generate server ID
    server_id = server_config.ensure_server_id()
    logger.info(f"Generated server ID: {server_id} for server: {server_config.name}")

    logger.info(f"Adding server to config: {server_config}")
    # Add to config
    success = config_manager.add_server(server_config)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save server configuration")

    # Try to connect if enabled and auto_connect
    if server_config.enabled and server_config.auto_connect:
        background_tasks.add_task(connect_server_background,
                                  server_id, user_context.user_id, config_manager)

    # Create response with proper type-safe model
    server_info = MCPServerInfo(
        id=server_config.server_id or "",
        name=server_config.name,
        description=server_config.description,
        status=server_config.status.value,
        transport_type=server_config.transport_type.value,  # type: ignore  # Enum value is string
        url=server_config.url,
        command=server_config.command,
        args=server_config.args,
        env=server_config.env,
        headers=server_config.headers,
        auth=auth_config,
        auto_connect=server_config.auto_connect,
        enabled=server_config.enabled,
        last_connected=server_config.last_connected,
        last_error=server_config.last_error,
        capabilities=server_config.capabilities,  # type: ignore  # May be dict
        tools=server_config.tools or [],
        resources=server_config.resources or [],
        resource_templates=server_config.resource_templates or [],
        prompts=server_config.prompts or [],
        tool_details=server_config.tool_details or [],
        resource_details=server_config.resource_details or [],
        resource_template_details=server_config.resource_template_details or [],
        prompt_details=server_config.prompt_details or [],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    return MCPInstallResponse(
        success=True,
        message=f"MCP server '{request.name}' installed successfully",
        data=server_info
    )

@router.post("/generate-server-id", response_model=BaseResponse[Dict[str, str]])
async def generate_server_id(request: MCPInstallRequest) -> BaseResponse[Dict[str, str]]:
    """Generate a consistent server ID from server configuration without saving"""
    try:
        # Validate transport mode
        transport_type = MCPTransportType(request.mode.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode. Use: {', '.join([t.value for t in MCPTransportType])}"
        ) from None

    # Create a temporary server config to generate ID
    temp_server_config = MCPServerConfig(
        name=request.name,
        transport_type=transport_type,
        description=request.description,
        url=request.url,
        command=request.command,
        args=request.args,
        env=request.env,
        headers=request.headers,
        auto_connect=request.auto_connect,
        enabled=request.enabled
    )

    # Generate the server ID
    server_id = temp_server_config.generate_server_id()

    return BaseResponse(
        success=True,
        message=f"Generated server ID for '{request.name}'",
        data={
            "server_id": server_id,
            "server_name": request.name
        }
    )

@router.put("/{server_id}/rename", response_model=MCPRenameResponse)
async def rename_mcp_server(
    server_id: str,
    request: RenameServerRequest,
    user_context: UserContext = Depends(get_user_context)
) -> MCPRenameResponse:
    """Rename an MCP server with type-safe request/response models."""
    logger.info(f"📋 Rename server endpoint called: {server_id} -> {request.new_name}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")

    try:
        # Get managers from global connection manager
        config_manager = MCPConfigManager(str(user_context.user_id))

        # Check if server exists
        server_config = config_manager.get_server(server_id)
        if not server_config:
            raise get_server_not_found_error(server_id, config_manager)

        # Check if new name already exists
        existing_server = config_manager.get_server(request.new_name)
        if existing_server:
            raise HTTPException(status_code=409, detail=f"Server with name '{request.new_name}' already exists")

        # Rename the server
        success = config_manager.rename_server(server_id, request.new_name)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to rename server")

        logger.info(f"   ✅ Successfully renamed server '{server_id}' to '{request.new_name}'")

        return MCPRenameResponse(
            success=True,
            message=f"Server renamed from '{server_id}' to '{request.new_name}' successfully",
            data={
                "old_name": server_id,
                "new_name": request.new_name,
                "server_id": server_config.server_id
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error renaming server: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to rename server: {str(e)}") from e

@router.put("/{server_id}/update", response_model=MCPUpdateResponse)
async def update_mcp_server(
    server_id: str,
    request: MCPUpdateRequest,
    user_context: UserContext = Depends(get_user_context)
) -> MCPUpdateResponse:
    """Update an MCP server configuration with type-safe request/response models."""
    logger.info(f"📋 Update server endpoint called: {server_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")

    try:
        # Get managers from global connection manager
        config_manager = MCPConfigManager(str(user_context.user_id))

        # Check if server exists
        server_config = config_manager.get_server(server_id)
        if not server_config:
            raise get_server_not_found_error(server_id, config_manager)

        # Check if name is being changed
        new_name = request.name
        if new_name != server_config.name:
            # Check if new name already exists
            existing_server = config_manager.get_server(new_name)
            if existing_server:
                raise HTTPException(status_code=409, detail=f"Server with name '{new_name}' already exists")
            logger.info(f"   🔄 Server name will be changed from '{server_config.name}' to '{new_name}'")

        # Validate transport mode
        try:
            transport_type = MCPTransportType(request.mode.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode. Use: {', '.join([t.value for t in MCPTransportType])}"
            ) from None

        # Validate required fields based on transport type
        if transport_type == MCPTransportType.STDIO:
            if not request.command:
                raise HTTPException(status_code=400, detail="Command required for stdio mode")
        elif transport_type in [MCPTransportType.HTTP, MCPTransportType.SSE]:
            if not request.url:
                raise HTTPException(status_code=400, detail="URL required for http/sse mode")

        # Create auth config
        auth_config = None
        if request.auth_type and request.auth_type != "none":
            from vmcp.shared.models import AuthType
            auth_config = MCPAuthConfig(
                type=AuthType(request.auth_type),
                client_id=request.client_id,
                client_secret=request.client_secret,
                auth_url=request.auth_url,
                token_url=request.token_url,
                scope=request.scope,
                access_token=request.access_token,
                refresh_token=None,
                expires_at=None
            )

        # Create updated server config
        updated_config = MCPServerConfig(
            name=new_name,  # Use the new name from request
            transport_type=transport_type,
            description=request.description,
            command=request.command,
            args=request.args,
            env=request.env,
            url=request.url,
            headers=request.headers,
            auth=auth_config,
            auto_connect=request.auto_connect,
            enabled=request.enabled
        )

        # Preserve the server ID and connection status
        updated_config.server_id = server_config.server_id
        updated_config.status = server_config.status
        updated_config.last_connected = server_config.last_connected
        updated_config.last_error = server_config.last_error
        updated_config.tools = server_config.tools
        updated_config.resources = server_config.resources
        updated_config.prompts = server_config.prompts
        updated_config.capabilities = server_config.capabilities

        # Just update the existing server
        success = config_manager.update_server_config(server_config.server_id, updated_config)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update server configuration")
        logger.info(f"   ✅ Successfully updated server '{server_config.name}' '{server_config.server_id}'")

        # Create response with proper type-safe model
        server_info = MCPServerInfo(
            id=updated_config.server_id or "",
            name=updated_config.name,
            description=updated_config.description,
            status=updated_config.status.value,
            transport_type=updated_config.transport_type.value,  # type: ignore  # Enum value is string
            url=updated_config.url,
            command=updated_config.command,
            args=updated_config.args,
            env=updated_config.env,
            headers=updated_config.headers,
            auth=auth_config,
            auto_connect=updated_config.auto_connect,
            enabled=updated_config.enabled,
            last_connected=updated_config.last_connected,
            last_error=updated_config.last_error,
            capabilities=updated_config.capabilities,  # type: ignore  # May be dict
            tools=updated_config.tools or [],
            resources=updated_config.resources or [],
            resource_templates=updated_config.resource_templates or [],
            prompts=updated_config.prompts or [],
            tool_details=updated_config.tool_details or [],
            resource_details=updated_config.resource_details or [],
            resource_template_details=updated_config.resource_template_details or [],
            prompt_details=updated_config.prompt_details or [],
            created_at=server_config.created_at if hasattr(server_config, 'created_at') else datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        return MCPUpdateResponse(
            success=True,
            message=f"MCP server '{server_id}' updated successfully" + (f" and renamed to '{new_name}'" if new_name != server_config.name else ""),
            data=server_info
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error updating server: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to update server: {str(e)}") from e

@router.delete("/{server_id}/uninstall", response_model=MCPUninstallResponse)
async def uninstall_mcp_server(
    server_id: str,
    user_context: UserContext = Depends(get_user_context)
) -> MCPUninstallResponse:
    """Uninstall an MCP server with type-safe response model."""

    # Get managers from global connection manager
    config_manager = MCPConfigManager(str(user_context.user_id))

    # Check if server exists
    server_config = config_manager.get_server(server_id)
    if not server_config:
        raise get_server_not_found_error(server_id, config_manager)

    # If it's a stdio server, disconnect it first before uninstalling
    if server_config.transport_type == TransportType.STDIO:
        logger.info(f"   🔌 Disconnecting stdio server before uninstall: {server_id}")
        await MCPClientManager.disconnect_stdio_server(server_id)

    # Remove from config
    success = config_manager.remove_server(server_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to remove server configuration")

    return MCPUninstallResponse(
        success=True,
        message=f"MCP server '{server_id}' uninstalled successfully",
        data={
            "server_id": server_id,
            "server_name": server_config.name
        }
    )

# ============================================================================
# CONNECTION MANAGEMENT ENDPOINTS
# ============================================================================

@router.post("/{server_id}/connect", response_model=MCPConnectionResponse)
async def connect_mcp_server_with_capabilities(
    server_id: str,
    user_context: UserContext = Depends(get_user_context)
) -> MCPConnectionResponse:
    """Connect to an MCP server by pinging and discovering capabilities with type-safe response model."""
    logger.info(f"📋 Connect server endpoint called for server: {server_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")

    try:
        # Get managers from global connection manager
        config_manager = MCPConfigManager(str(user_context.user_id))
        client_manager = MCPClientManager(config_manager)

        # Check if server exists
        server_config = config_manager.get_server(server_id)
        if not server_config:
            raise get_server_not_found_error(server_id, config_manager)

        if not server_config.enabled:
            raise HTTPException(status_code=400, detail=f"Server '{server_id}' is disabled")

        # Try to ping the server first
        try:
            current_status = await client_manager.ping_server(server_id)
            logger.info(f"   🔍 Server {server_id}: ping result = {current_status.value if current_status else 'None'}")
        except AuthenticationError as e:
            logger.debug(f"   ❌ Authentication error for server {server_id}: {e}")
            current_status = MCPConnectionStatus.AUTH_REQUIRED
        except Exception as e:
            logger.error(f"   ❌ Error pinging server {server_id}: {traceback.format_exc()}")
            logger.error(f"   ❌ Error pinging server {server_id}: {e}")
            current_status = MCPConnectionStatus.ERROR
            config_manager.update_server_status(server_id, current_status, str(e))
            return MCPConnectionResponse(
                success=False,
                message=f"Failed to connect to server '{server_id}'",
                data=MCPConnectionInfo(
                    server_id=server_id,
                    server_name=server_config.name,
                    status=current_status.value,
                    error=str(e),
                    requires_auth=False,
                    auth_url=None
                )
            )

        # Update server status
        config_manager.update_server_status(server_id, current_status)

        # If connected, discover capabilities
        if current_status == MCPConnectionStatus.CONNECTED:
            try:
                capabilities = await client_manager.discover_capabilities(server_id)
                if capabilities:
                    # Update server config with discovered capabilities
                    if capabilities.get('tools',[]):
                        server_config.tools = capabilities.get('tools', []).copy()
                    if capabilities.get('resources',[]):
                        server_config.resources = capabilities.get('resources', [])
                    if capabilities.get('prompts',[]):
                        server_config.prompts = capabilities.get('prompts', [])
                    if capabilities.get('tool_details',[]):
                        server_config.tool_details = capabilities.get('tool_details', []).copy()
                    if capabilities.get('resource_details',[]):
                        server_config.resource_details = capabilities.get('resource_details', [])
                    if capabilities.get('resource_templates',[]):
                        server_config.resource_templates = capabilities.get('resource_templates', [])
                    if capabilities.get('resource_template_details',[]):
                        server_config.resource_template_details = capabilities.get('resource_template_details', [])
                    if capabilities.get('prompt_details',[]):
                        server_config.prompt_details = capabilities.get('prompt_details', [])
                    server_config.capabilities = {
                        "tools": bool(server_config.tools and len(server_config.tools) > 0),
                        "resources": bool(server_config.resources and len(server_config.resources) > 0),
                        "prompts": bool(server_config.prompts and len(server_config.prompts) > 0)
                    }

                    # Save updated config
                    config_manager.update_server_config(server_id, server_config)
                    logger.info(f"   ✅ Successfully discovered capabilities for server '{server_id}'")
            except Exception as e:
                logger.error(f"   ❌ Error discovering capabilities for server {server_id}: {e}")
                # Don't fail the connection if capabilities discovery fails

        # Update vMCPs using server status
        vmcps_using_server = server_config.vmcps_using_server
        if vmcps_using_server:
            logger.info(f"   🔄 Updating vMCPs using {server_id} status: {current_status.value}")
            vmcp_config_manager = VMCPConfigManager(str(user_context.user_id))
            for vmcp_id in vmcps_using_server:
                if vmcp_id.startswith('@'):
                    continue
                vmcp_config = vmcp_config_manager.load_vmcp_config(specific_vmcp_id=vmcp_id)
                if vmcp_config:
                    vmcp_config_manager.update_vmcp_server(vmcp_id, server_config)

        # Create response data with required server_name field
        if current_status == MCPConnectionStatus.AUTH_REQUIRED:
            return MCPConnectionResponse(
                success=False,
                message=f"Authentication required for server '{server_id}'",
                data=MCPConnectionInfo(
                    server_id=server_id,
                    server_name=server_config.name,
                    status=current_status.value,
                    requires_auth=True,
                    auth_url=None,
                    error=None
                )
            )
        elif current_status == MCPConnectionStatus.CONNECTED:
            return MCPConnectionResponse(
                success=True,
                message=f"Successfully connected to server '{server_id}'",
                data=MCPConnectionInfo(
                    server_id=server_id,
                    server_name=server_config.name,
                    status=current_status.value,
                    requires_auth=False,
                    auth_url=None,
                    error=None
                )
            )
        else:
            return MCPConnectionResponse(
                success=False,
                message=f"Failed to connect to server '{server_id}'",
                data=MCPConnectionInfo(
                    server_id=server_id,
                    server_name=server_config.name,
                    status=current_status.value,
                    requires_auth=False,
                    auth_url=None,
                    error=None
                )
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error connecting server: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to connect server: {str(e)}") from e

@router.post("/{server_id}/disconnect", response_model=MCPDisconnectResponse)
async def disconnect_mcp_server(
    server_id: str,
    user_context: UserContext = Depends(get_user_context)
) -> MCPDisconnectResponse:
    """Disconnect an MCP server by clearing auth and session, setting status to disconnected with type-safe response model."""
    logger.info(f"📋 Disconnect server endpoint called for server: {server_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")

    try:
        # Get managers from global connection manager
        config_manager = MCPConfigManager(str(user_context.user_id))

        # Check if server exists
        server_config = config_manager.get_server(server_id)
        if not server_config:
            raise get_server_not_found_error(server_id, config_manager)

        # Clear auth and session information
        server_config.auth = None
        server_config.session_id = None

        # If it's a stdio server, explicitly disconnect it from the connection pool
        if server_config.transport_type == TransportType.STDIO:
            logger.info(f"   🔌 Disconnecting stdio server: {server_id}")
            disconnected = await MCPClientManager.disconnect_stdio_server(server_id)
            if disconnected:
                logger.info(f"   ✅ Successfully closed stdio connection for: {server_id}")
            else:
                logger.warning(f"   ⚠️  No active stdio connection found for: {server_id}")

        # Set status to disconnected
        config_manager.update_server_status(server_id, MCPConnectionStatus.DISCONNECTED)

        # Update vMCPs using server status
        vmcps_using_server = server_config.vmcps_using_server
        if vmcps_using_server:
            logger.info(f"   🔄 Updating vMCPs using {server_id} status: disconnected")
            vmcp_config_manager = VMCPConfigManager(str(user_context.user_id))
            for vmcp_id in vmcps_using_server:
                if vmcp_id.startswith('@'):
                    continue
                vmcp_config = vmcp_config_manager.load_vmcp_config(specific_vmcp_id=vmcp_id)
                if vmcp_config:
                    vmcp_config_manager.update_vmcp_server(vmcp_id, server_config)

        logger.info(f"   ✅ Successfully disconnected server '{server_id}'")

        return MCPDisconnectResponse(
            success=True,
            message=f"Server '{server_id}' disconnected successfully",
            data={
                "server_id": server_id,
                "status": "disconnected"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error disconnecting server: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to disconnect server: {str(e)}") from e

@router.post("/{server_id}/ping", response_model=MCPPingResponse)
async def ping_mcp_server(
    server_id: str,
    user_context: UserContext = Depends(get_user_context)
) -> MCPPingResponse:
    """Ping an MCP server to check connectivity with type-safe response model."""

    # Get managers from global connection manager
    config_manager = MCPConfigManager(str(user_context.user_id))
    client_manager = MCPClientManager(config_manager)

    server_config = config_manager.get_server(server_id)
    if not server_config:
        raise get_server_not_found_error(server_id, config_manager)

    success = False
    try:
        status = await client_manager.ping_server(server_id, server_config)
        if status:
            success = True
    except AuthenticationError as e:
        logger.debug(f"   ❌ Authentication error for server {server_id}: {e}")
    except Exception as e:
        logger.error(f"   ❌ Error pinging server {server_id}: {e}")

    return MCPPingResponse(
        success=True,
        message="Server ping completed",
        data=MCPPingInfo(
            server=server_id,
            alive=success,
            timestamp=datetime.now(),
            server_id=server_id,
            response_time=None,
            error=None
        )
    )

@router.get("/{server_id}/status", response_model=MCPStatusResponse)
async def get_server_status(
    server_id: str,
    user_context: UserContext = Depends(get_user_context)
) -> MCPStatusResponse:
    """Get real-time status for a specific server by pinging it with type-safe response model."""
    logger.info(f"📋 Get server status endpoint called for: {server_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")

    try:
        # Get managers from global connection manager
        config_manager = MCPConfigManager(str(user_context.user_id))
        client_manager = MCPClientManager(config_manager)

        # Check if server exists
        server_config = config_manager.get_server(server_id)
        if not server_config:
            raise get_server_not_found_error(server_id, config_manager)

        # Ping the server to get current status
        try:
            current_status = await client_manager.ping_server(server_id)
            logger.info(f"   🔍 Server {server_id}: ping result = {current_status.value}")
        except AuthenticationError as e:
            logger.debug(f"   ❌ Authentication error for server {server_id}: {e}")
            current_status = MCPConnectionStatus.AUTH_REQUIRED
        except Exception as e:
            logger.error(f"   ❌ Error pinging server {server_id}: {e}")
            current_status = MCPConnectionStatus.UNKNOWN

        # Update stored status if it changed
        if current_status != server_config.status:
            logger.info(f"   🔄 Updating {server_id} status: {server_config.status.value} → {current_status.value}")
            config_manager.update_server_status(server_id, current_status)

        # Update vMCPs using server status
        vmcps_using_server = server_config.vmcps_using_server
        logger.info(f"   🔄 vMCPs using server {server_id}: {vmcps_using_server}")
        if vmcps_using_server:
            logger.info(f"   🔄 Updating vMCPs using {server_id} status: {current_status.value}")
            vmcp_config_manager = VMCPConfigManager(str(user_context.user_id))
            for vmcp_id in vmcps_using_server:
                if vmcp_id.startswith('@'):
                    continue
                vmcp_config = vmcp_config_manager.load_vmcp_config(specific_vmcp_id=vmcp_id)
                if vmcp_config:
                    vmcp_config_manager.update_vmcp_server(vmcp_id, server_config)

        return MCPStatusResponse(
            success=True,
            message="Server status retrieved",
            data=MCPServerStatus(
                server_id=server_id,
                name=server_config.name,
                status=current_status.value,
                last_updated=datetime.now(),
                last_connected=server_config.last_connected,
                last_error=server_config.last_error,
                requires_auth=current_status == MCPConnectionStatus.AUTH_REQUIRED
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error getting server status: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get server status: {str(e)}") from e

# ============================================================================
# CAPABILITIES DISCOVERY ENDPOINTS
# ============================================================================

@router.post("/{server_id}/discover-capabilities", response_model=MCPCapabilitiesResponse)
async def discover_server_capabilities(
    server_id: str,
    user_context: UserContext = Depends(get_user_context)
) -> MCPCapabilitiesResponse:
    """Discover capabilities of an MCP server with type-safe response model."""
    logger.info(f"📋 Discover capabilities endpoint called for server: {server_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")

    try:
        # Get managers from global connection manager
        config_manager = MCPConfigManager(str(user_context.user_id))
        client_manager = MCPClientManager(config_manager)

        server_config = config_manager.get_server(server_id)
        if not server_config:
            raise get_server_not_found_error(server_id, config_manager)

        # Discover capabilities using the client manager
        try:
            capabilities = await client_manager.discover_capabilities(server_id)
            if capabilities:
                # Update server config with discovered capabilities
                if capabilities.get('tools',[]):
                    server_config.tools = capabilities.get('tools', []).copy()
                    logger.info(f"   🔍 Updated tools: {server_config.tools}")
                if capabilities.get('resources',[]):
                    server_config.resources = capabilities.get('resources', [])
                if capabilities.get('prompts',[]):
                    server_config.prompts = capabilities.get('prompts', [])
                if capabilities.get('tool_details',[]):
                    server_config.tool_details = capabilities.get('tool_details', []).copy()
                    logger.info(f"   🔍 Updated tool details: {server_config.tool_details}")
                if capabilities.get('resource_details',[]):
                    server_config.resource_details = capabilities.get('resource_details', [])
                if capabilities.get('resource_templates',[]):
                    server_config.resource_templates = capabilities.get('resource_templates', [])
                if capabilities.get('resource_template_details',[]):
                    server_config.resource_template_details = capabilities.get('resource_template_details', [])
                if capabilities.get('prompt_details',[]):
                    server_config.prompt_details = capabilities.get('prompt_details', [])
                server_config.capabilities = {
                    "tools": bool(server_config.tools and len(server_config.tools) > 0),
                    "resources": bool(server_config.resources and len(server_config.resources) > 0),
                    "prompts": bool(server_config.prompts and len(server_config.prompts) > 0)
                }

                # Save updated config
                config_manager.update_server_config(server_id, server_config)
                # Update vMCPs using server status
                vmcps_using_server = server_config.vmcps_using_server
                if vmcps_using_server:
                    logger.info(
            f"   🔄 Updating vMCPs using {server_id} status: {server_config.status.value} and "
            f"Capabilities: Tools: {len(capabilities.get('tools',[]))}, "
            f"Resources: {len(capabilities.get('resources',[]))}, "
            f"Prompts: {len(capabilities.get('prompts',[]))}"
        )
                    vmcp_config_manager = VMCPConfigManager(str(user_context.user_id))
                    for vmcp_id in vmcps_using_server:
                        if vmcp_id.startswith('@'):
                            continue
                        vmcp_config = vmcp_config_manager.load_vmcp_config(specific_vmcp_id=vmcp_id)
                        if vmcp_config:
                            vmcp_config_manager.update_vmcp_server(vmcp_id, server_config)


                logger.info(f"   ✅ Successfully discovered capabilities for server '{server_id}'")
                return MCPCapabilitiesResponse(
                    success=True,
                    message=f"Successfully discovered capabilities for server '{server_id}'",
                    data={
                        "capabilities": {
                            "tools_count": len(server_config.tools) if server_config.tools else 0,
                            "resources_count": len(server_config.resources) if server_config.resources else 0,
                            "prompts_count": len(server_config.prompts) if server_config.prompts else 0
                        },
                        "tools_list": server_config.tools if server_config.tools else [],
                        "resources_list": server_config.resources if server_config.resources else [],
                        "prompts_list": server_config.prompts if server_config.prompts else [],
                        "tool_details": server_config.tool_details if server_config.tool_details else [],
                        "resource_details": server_config.resource_details if server_config.resource_details else [],
                        "resource_templates": server_config.resource_templates if server_config.resource_templates else [],
                        "resource_template_details": server_config.resource_template_details if server_config.resource_template_details else [],
                        "prompt_details": server_config.prompt_details if server_config.prompt_details else []
                    }
                )
            else:
                raise HTTPException(status_code=500, detail="Failed to discover capabilities")

        except AuthenticationError as e:
            logger.debug(f"   ❌ Authentication error for server {server_id}: {e}")
            return MCPCapabilitiesResponse(
                success=False,
                message=f"Authentication required for server '{server_id}'",
                data={
                    "error": "Authentication required",
                    "capabilities": {
                        "tools": 0,
                        "resources": 0,
                        "prompts": 0
                    }
                }
            )
        except Exception as e:
            logger.error(f"   ❌ Error discovering capabilities for server {server_id}: {e}")
            return MCPCapabilitiesResponse(
                success=False,
                message=f"Failed to discover capabilities for server '{server_id}'",
                data={
                    "error": str(e),
                    "capabilities": {
                        "tools": 0,
                        "resources": 0,
                        "prompts": 0
                    }
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error in discover capabilities endpoint: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to discover capabilities: {str(e)}") from e

# ============================================================================
# TOOL/RESOURCE/PROMPT EXECUTION ENDPOINTS
# ============================================================================

@router.post("/{server_id}/tools/call", response_model=MCPToolCallResponse)
async def call_mcp_tool(
    server_id: str,
    request: MCPToolCallRequest,
    user_context: UserContext = Depends(get_user_context)
) -> MCPToolCallResponse:
    """Call a tool on an MCP server with type-safe request/response models."""
    logger.info(f"📋 Call MCP tool endpoint called for server: {server_id}, tool: {request.tool_name}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")

    try:
        # Get managers from global connection manager
        config_manager = MCPConfigManager(str(user_context.user_id))
        client_manager = MCPClientManager(config_manager)

        try:
            result = await client_manager.call_tool(
                server_id,
                request.tool_name,
                request.arguments,
                connect_if_needed=True
            )
        except Exception as tool_error:
            logger.error(f"   ❌ Tool call failed: {tool_error}")
            logger.error(f"   ❌ Tool call exception type: {type(tool_error).__name__}")
            logger.error(f"   ❌ Tool call full traceback: {traceback.format_exc()}")
            raise

        if result is None:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to call tool '{request.tool_name}' on server '{server_id}'"
            )

        logger.info(f"   ✅ Successfully called tool '{request.tool_name}' on server '{server_id}'")

        # Convert CallToolResult to MCPToolCallResult with server tracking
        from vmcp.shared.mcp_content_models import MCPToolCallResult
        mcp_result = MCPToolCallResult.from_call_tool_result(
            result=result,
            tool_name=request.tool_name,
            server=server_id,
            server_id=server_id
        )

        return MCPToolCallResponse(
            success=True,
            message=f"Tool '{request.tool_name}' executed successfully",
            data=mcp_result
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error calling MCP tool: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to call MCP tool: {str(e)}") from e

@router.post("/{server_id}/resources/read", response_model=MCPResourceResponse)
async def get_mcp_resource(
    server_id: str,
    request: MCPResourceRequest,
    user_context: UserContext = Depends(get_user_context)
) -> MCPResourceResponse:
    """Get a resource from an MCP server with type-safe request/response models."""
    logger.info(f"📋 Get MCP resource endpoint called for server: {server_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")

    try:
        # Get managers from global connection manager
        config_manager = MCPConfigManager(str(user_context.user_id))
        client_manager = MCPClientManager(config_manager)

        try:
            contents = await client_manager.read_resource(server_id, request.uri)
            logger.info(f"   🔍 get_resource returned: {contents}")
        except Exception as e:
            logger.error(f"   ❌ Exception in client_manager.read_resource: {e}")
            logger.error(f"   ❌ Exception type: {type(e).__name__}")
            logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
            raise e

        if contents is None:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get resource '{request.uri}' from server '{server_id}'"
            )

        logger.info(f"   ✅ Successfully retrieved resource '{request.uri}' from server '{server_id}'")

        # Convert ReadResourceResult to MCPResourceContent with server tracking
        from vmcp.shared.mcp_content_models import MCPResourceContent
        mcp_content = MCPResourceContent.from_read_resource_result(
            result=contents,
            uri=request.uri,
            server=server_id,
            server_id=server_id
        )

        return MCPResourceResponse(
            success=True,
            message=f"Resource '{request.uri}' retrieved successfully",
            data=mcp_content
        )
    except Exception as e:
        logger.error(f"   ❌ Error getting MCP resource: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get MCP resource: {str(e)}") from e

@router.post("/{server_id}/prompts/get", response_model=MCPPromptResponse)
async def get_mcp_prompt(
    server_id: str,
    request: MCPPromptRequest,
    user_context: UserContext = Depends(get_user_context)
) -> MCPPromptResponse:
    """Get a prompt from an MCP server with type-safe request/response models."""
    logger.info(f"📋 Get MCP prompt endpoint called for server: {server_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")

    try:
        # Get managers from global connection manager
        config_manager = MCPConfigManager(str(user_context.user_id))
        client_manager = MCPClientManager(config_manager)

        try:
            messages = await client_manager.get_prompt(
                server_id,
                request.prompt_name,
                request.arguments,
                connect_if_needed=True
            )
            logger.info(f"   🔍 get_prompt returned: {messages}")
        except Exception as e:
            logger.error(f"   ❌ Exception in client_manager.get_prompt: {e}")
            logger.error(f"   ❌ Exception type: {type(e).__name__}")
            logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
            raise e

        if messages is None:
            logger.error(f"   ❌ get_prompt returned None for prompt '{request.prompt_name}' from server '{server_id}'")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get prompt '{request.prompt_name}' from server '{server_id}'"
            )

        logger.info(f"   ✅ Successfully retrieved prompt '{request.prompt_name}' from server '{server_id}'")

        # Convert GetPromptResult to MCPPromptResult with server tracking
        from vmcp.shared.mcp_content_models import MCPPromptResult
        mcp_result = MCPPromptResult.from_get_prompt_result(
            result=messages,
            prompt_name=request.prompt_name,
            server=server_id,
            server_id=server_id
        )

        return MCPPromptResponse(
            success=True,
            message=f"Prompt '{request.prompt_name}' retrieved successfully",
            data=mcp_result
        )
    except Exception as e:
        logger.error(f"   ❌ Error getting MCP prompt: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")

        # If it's a validation error, return 422 with details
        if hasattr(e, 'status_code') and e.status_code == 422:
            logger.error(f"   ❌ Validation error details: {getattr(e, 'detail', 'No details')}")
            raise HTTPException(status_code=422, detail=f"Validation error: {str(e)}") from e

        raise HTTPException(status_code=500, detail=f"Failed to get MCP prompt: {str(e)}") from e

# ============================================================================
# LISTING ENDPOINTS
# ============================================================================

@router.get("/tools/discover", response_model=MCPToolsDiscoverResponse)
async def discover_mcp_tools(
    user_context: UserContext = Depends(get_user_context)
) -> MCPToolsDiscoverResponse:
    """Discover all available tools from connected MCP servers with type-safe response model."""
    logger.info("📋 Discover MCP tools endpoint called")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")

    try:
        # Get managers from global connection manager
        config_manager = MCPConfigManager(str(user_context.user_id))

        servers = config_manager.list_servers()

        tools = []

        for server in servers:
            if server.status == MCPConnectionStatus.CONNECTED and server.tools:
                for tool in server.tools:
                    # Prefix tool name with server name to avoid conflicts
                    prefixed_name = f"{server.name}_{tool}"
                    tools.append({
                        "name": prefixed_name,
                        "original_name": tool,
                        "server": server.name,
                        "description": f"Tool '{tool}' from {server.name} server",
                        "server_id": server.server_id
                    })

        return MCPToolsDiscoverResponse(
            success=True,
            message="Tools discovered successfully",
            data=MCPToolsDiscovery(
                tools=tools,  # type: ignore  # List of dicts compatible with MCPDiscoveredTool
                total_tools=len(tools),
                connected_servers=len([s for s in servers if s.status == MCPConnectionStatus.CONNECTED])
            )
        )
    except Exception as e:
        logger.error(f"   ❌ Error discovering MCP tools: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to discover MCP tools: {str(e)}") from e

@router.get("/{server_id}/tools/list", response_model=MCPToolsResponse)
async def list_server_tools(
    server_id: str,
    user_context: UserContext = Depends(get_user_context)
) -> MCPToolsResponse:
    """List all tools for a specific server with type-safe response model."""
    logger.info(f"📋 List server tools endpoint called for server: {server_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")

    try:
        # Create fresh managers for this request
        config_manager = MCPConfigManager(str(user_context.user_id))
        client_manager = MCPClientManager(config_manager)

        server_config = config_manager.get_server(server_id)
        if not server_config:
            raise get_server_not_found_error(server_id, config_manager)

        tools_dict = await client_manager.tools_list(server_id)
    except AuthenticationError as e:
        logger.debug(f"   ❌ Authentication error for server {server_id}: {e}")
        raise HTTPException(status_code=401, detail=f"Authentication error for server {server_id}: {e}") from e
    except Exception as e:
        logger.error(f"   ❌ Error listing server tools: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to list server tools: {str(e)}") from e

    # Get tools from live connection
    tools = []
    for tool_name, tool_info in tools_dict.items():
        tool_data = {
            "name": tool_name,
            "server": server_id,
            "description": tool_info.description,
            "inputSchema": tool_info.inputSchema,
            "annotations": tool_info.annotations,
        }
        tools.append(tool_data)

    # Update server config after successful operation
    config_manager.update_server_status(server_id, MCPConnectionStatus.CONNECTED)

    logger.info(f"   ✅ Successfully listed {len(tools)} tools for server '{server_id}'")

    return MCPToolsResponse(
        success=True,
        message=f"Tools listed successfully for server '{server_id}'",
        data={
            "server": server_id,
            "tools": tools,
            "total_tools": len(tools)
        }
    )

@router.get("/{server_id}/resources/list", response_model=MCPResourcesResponse)
async def list_server_resources(
    server_id: str,
    user_context: UserContext = Depends(get_user_context)
) -> MCPResourcesResponse:
    """List all resources for a specific server with type-safe response model."""
    logger.info(f"📋 List server resources endpoint called for server: {server_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")

    try:
        # Create fresh managers for this request
        config_manager = MCPConfigManager(str(user_context.user_id))
        client_manager = MCPClientManager(config_manager)

        server_config = config_manager.get_server(server_id)
        if not server_config:
            raise get_server_not_found_error(server_id, config_manager)

        resources_dict = await client_manager.resources_list(server_id)
    except AuthenticationError as e:
        logger.debug(f"   ❌ Authentication error for server {server_id}: {e}")
        raise HTTPException(status_code=401, detail=f"Authentication error for server {server_id}: {e}") from e
    except Exception as e:
        logger.error(f"   ❌ Error listing server resources: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to list server resources: {str(e)}") from e

    resources = []
    for resource_uri, resource_info in resources_dict.items():
        resources.append({
            "uri": resource_uri,
            "server": server_id,
            "description": resource_info.description,
            "annotations": resource_info.annotations,
        })

    logger.info(f"   ✅ Successfully listed {len(resources)} resources for server '{server_id}'")

    return MCPResourcesResponse(
        success=True,
        message=f"Resources listed successfully for server '{server_id}'",
        data={
            "server": server_id,
            "resources": resources,
            "total_resources": len(resources)
        }
    )

@router.get("/{server_id}/prompts/list", response_model=MCPPromptsResponse)
async def list_server_prompts(
    server_id: str,
    user_context: UserContext = Depends(get_user_context)
) -> MCPPromptsResponse:
    """List all prompts for a specific server with type-safe response model."""
    logger.info(f"📋 List server prompts endpoint called for server: {server_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")

    try:
        # Create fresh managers for this request
        config_manager = MCPConfigManager(str(user_context.user_id))
        client_manager = MCPClientManager(config_manager)

        server_config = config_manager.get_server(server_id)
        if not server_config:
            raise get_server_not_found_error(server_id, config_manager)

        prompts_dict = await client_manager.prompts_list(server_id)
    except AuthenticationError as e:
        logger.error(f"   ❌ Authentication error for server {server_id}: {e}")
        raise HTTPException(status_code=401, detail=f"Authentication error for server {server_id}: {e}") from e
    except Exception as e:
        logger.error(f"   ❌ Error listing server prompts: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to list server prompts: {str(e)}") from e

    prompts = []
    for prompt_name, prompt_info in prompts_dict.items():
        prompts.append({
            "name": prompt_name,
            "server": server_id,
            "description": prompt_info.description,
            "arguments": prompt_info.arguments
        })

    # Update server config after successful operation
    config_manager.update_server_status(server_id, MCPConnectionStatus.CONNECTED)

    logger.info(f"   ✅ Successfully listed {len(prompts)} prompts for server '{server_id}'")

    return MCPPromptsResponse(
        success=True,
        message=f"Prompts listed successfully for server '{server_id}'",
        data={
            "server": server_id,
            "prompts": prompts,
            "total_prompts": len(prompts)
        }
    )

# ============================================================================
# STATISTICS AND LISTING ENDPOINTS
# ============================================================================

@router.get("/list", response_model=MCPListResponse)
async def list_mcp_servers(
    user_context: UserContext = Depends(get_user_context),
    background_tasks: BackgroundTasks = None
) -> MCPListResponse:
    """List all configured MCP servers without pinging (fast response) with type-safe response model."""
    logger.info("📋 List servers endpoint called (fast mode)")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")

    try:
        # Get managers from global connection manager
        logger.info("   🔧 Getting managers from global connection manager...")
        config_manager = MCPConfigManager(str(user_context.user_id))

        logger.info(f"   🔍 Config manager available: {config_manager is not None}")

        if not config_manager:
            logger.error("   ❌ Config manager is None - cannot list servers!")
            raise HTTPException(status_code=500, detail="Configuration manager not available")

        logger.info("   📊 Listing servers from config manager...")
        servers = config_manager.list_servers()
        logger.info(f"   📊 Found {len(servers)} servers in config")

        server_info = []
        for server in servers:
            # Convert auth to dict (handle both dataclass and Pydantic model)
            auth_dict = None
            if server.auth:
                from dataclasses import asdict, is_dataclass

                from pydantic import BaseModel

                if is_dataclass(server.auth):
                    # It's a dataclass, use asdict
                    auth_dict = asdict(server.auth)
                    # Convert datetime to ISO string if present
                    if auth_dict.get('expires_at'):
                        auth_dict['expires_at'] = auth_dict['expires_at'].isoformat()
                elif isinstance(server.auth, BaseModel):
                    # It's a Pydantic model, use model_dump
                    auth_dict = server.auth.model_dump()
                elif isinstance(server.auth, dict):
                    # It's already a dict
                    auth_dict = server.auth

            # Convert to MCPServerInfo for type safety
            # Pydantic will handle serialization of nested Pydantic models (Tool, Resource, Prompt, etc.)
            server_data = MCPServerInfo(
                id=server.server_id or "",
                name=server.name,
                description=server.description,
                status=server.status.value,
                transport_type=server.transport_type.value,  # type: ignore  # Enum value is string
                url=server.url,
                command=server.command,
                args=server.args,
                env=server.env,
                headers=server.headers,
                auth=server.auth,  # type: ignore  # Pass auth object directly
                auto_connect=server.auto_connect,
                enabled=server.enabled,
                last_connected=server.last_connected,
                last_error=server.last_error,
                capabilities=server.capabilities,  # type: ignore  # May be dict
                tools=server.tools or [],
                resources=server.resources or [],
                resource_templates=server.resource_templates or [],
                prompts=server.prompts or [],
                tool_details=server.tool_details or [],  # Pass Tool objects directly
                resource_details=server.resource_details or [],  # Pass Resource objects directly
                resource_template_details=server.resource_template_details or [],  # Pass ResourceTemplate objects directly
                prompt_details=server.prompt_details or [],  # Pass Prompt objects directly
                created_at=datetime.utcnow(),  # Use current time as fallback
                updated_at=datetime.utcnow()
            )
            server_info.append(server_data)

        # Log the response summary
        logger.info("   📊 Response summary (from stored status):")
        logger.info(f"      • Total servers: {len(server_info)}")
        logger.info("   ✅ Successfully returning server list (fast mode)")

        return MCPListResponse(
            success=True,
            message="Servers retrieved successfully",
            data=server_info,
            pagination={
                "page": 1,
                "limit": len(server_info),
                "total": len(server_info),
                "pages": 1
            }
        )
    except Exception as e:
        logger.error(f"   ❌ Error in list_mcp_servers: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") from e

@router.get("/stats", response_model=MCPStatsResponse)
async def get_mcp_stats(
    user_context: UserContext = Depends(get_user_context)
) -> MCPStatsResponse:
    """Get MCP system statistics with type-safe response model."""
    logger.info("📋 Get MCP stats endpoint called")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")

    try:
        # Get managers from global connection manager
        config_manager = MCPConfigManager(str(user_context.user_id))

        servers = config_manager.list_servers()

        total_tools = 0
        total_resources = 0
        total_prompts = 0
        connected_count = 0

        for server in servers:
            if server.status == MCPConnectionStatus.CONNECTED:
                connected_count += 1
                if server.tools:
                    total_tools += len(server.tools)
                if server.resources:
                    total_resources += len(server.resources)
                if server.prompts:
                    total_prompts += len(server.prompts)

        logger.info(f"   ✅ Successfully retrieved stats: {len(servers)} servers, {connected_count} connected")

        return MCPStatsResponse(
            success=True,
            message="Statistics retrieved successfully",
            data=MCPSystemStats(
                servers=MCPServerStats(
                    total=len(servers),
                    connected=connected_count,
                    disconnected=len([s for s in servers if s.status == MCPConnectionStatus.DISCONNECTED]),
                    auth_required=len([s for s in servers if s.status == MCPConnectionStatus.AUTH_REQUIRED]),
                    errors=len([s for s in servers if s.status == MCPConnectionStatus.ERROR])
                ),
                capabilities=MCPCapabilitiesStats(
                    tools=total_tools,
                    resources=total_resources,
                    prompts=total_prompts
                )
            )
        )
    except Exception as e:
        logger.error(f"   ❌ Error getting MCP stats: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get MCP stats: {str(e)}") from e

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@router.post("/{server_id}/auth", response_model=BaseResponse[Dict[str, str]])
async def initiate_auth(
    server_id: str,
    user_context: UserContext = Depends(get_user_context)
) -> BaseResponse[Dict[str, str]]:
    """Initiate OAuth authentication for a server with type-safe response model."""
    logger.info(f"📋 Initiate auth endpoint called for server: {server_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")

    try:
        # Get managers from global connection manager
        config_manager = MCPConfigManager(str(user_context.user_id))
        client_manager = MCPClientManager(config_manager)

        # Find the server configuration
        server_config = config_manager.get_server(server_id)
        if not server_config:
            raise get_server_not_found_error(server_id, config_manager)

        if not server_config.url:
            raise HTTPException(status_code=400, detail=f"Server '{server_id}' does not have a URL")

        # Initiate OAuth flow with callback URL to MCP proxy server
        # The callback should go to the OSS server where tokens are saved
        from vmcp.config import settings
        callback_url = f"{settings.base_url}/api/otherservers/oauth/callback"

        logger.info(f"   🔗 Using OAuth callback URL: {callback_url}")

        # Let MCPAuthManager generate its own state and initiate the flow
        result = await client_manager.auth_manager.initiate_oauth_flow(
            server_name=server_id,
            server_url=server_config.url,
            callback_url=callback_url,
            user_id=str(user_context.user_id),
            headers=server_config.headers
        )

        if result.get('status') == 'error':
            error_detail = result.get('error', 'Unknown error during OAuth flow initiation')
            logger.error(f"   ❌ OAuth flow initiation failed: {error_detail}")
            raise HTTPException(status_code=400, detail=error_detail)

        # Get the state that MCPAuthManager generated
        mcp_state = result.get('state')
        if not mcp_state:
            raise HTTPException(status_code=500, detail="No state returned from OAuth flow")

        logger.info(f"   🔑 Using MCP-generated state: {mcp_state[:8]}...")
        logger.info(f"   ✅ Successfully initiated OAuth flow for server '{server_id}'")

        return BaseResponse(
            success=True,
            message=f"OAuth flow initiated for server '{server_id}'",
            data={
                "authorization_url": result['authorization_url'],
                "state": mcp_state,  # Return the MCP-generated state
                "instructions": "The URL will open in your default browser. After authorization, you'll be redirected back to complete the setup."
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error initiating auth for server '{server_id}': {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e)) from e

# ============================================================================
# BACKGROUND TASKS
# ============================================================================

async def connect_server_background(server_id: str, user_id: str,
                                    config_manager: MCPConfigManager):
    """Background task to connect to a server"""
    logger.info(
        f"🔄 Background connection attempt for server '{server_id}' by user '{user_id}' and "
        f"config manager {config_manager._servers.keys()}"
    )

    try:
        # Load server configuration from shared storage
        server_config = config_manager.get_server(server_id)
        if server_config and server_config.enabled:
            try:
                # Update status to indicate connection attempt
                config_manager.update_server_status(server_id, MCPConnectionStatus.DISCONNECTED)
                logger.info(f"✅ Background connection request sent for server '{server_id}'")
                logger.info("   ℹ️ Actual connection will be handled by MCP server")
            except Exception as e:
                logger.error(f"❌ Background connection failed for server '{server_id}': {e}")
                config_manager.update_server_status(server_id, MCPConnectionStatus.ERROR, str(e))
        else:
            logger.warning(f"⚠️ Server '{server_id}' not found or not enabled for background connection")
    except Exception as e:
        logger.error(f"❌ Error in background connection task for server '{server_id}': {e}")
        logger.error(f"❌ Exception type: {type(e).__name__}")
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")

# ============================================================================
# REGISTRY ENDPOINTS
# ============================================================================

@router.get("/registry/servers", response_model=RegistryServersResponse)
async def list_global_mcp_servers(
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 300,
    offset: int = 0,
    user_context: UserContext = Depends(get_user_context)
) -> RegistryServersResponse:
    """
    List all global MCP servers with optional filtering

    Returns a list of pre-configured MCP servers that are available globally.
    """
    try:
        logger.info(f"📋 Listing global MCP servers for user {user_context.user_id}")

        # Import here to avoid circular imports
        from vmcp.storage.database import SessionLocal
        from vmcp.storage.models import GlobalMCPServerRegistry

        # Get database session
        db = SessionLocal()

        # Build query
        query = db.query(GlobalMCPServerRegistry)

        # Apply filters
        if category:
            query = query.filter(GlobalMCPServerRegistry.server_metadata['category'].astext == category)

        if search:
            search_term = f"%{search.lower()}%"
            query = query.filter(
                db.or_(
                    GlobalMCPServerRegistry.name.ilike(search_term),
                    GlobalMCPServerRegistry.description.ilike(search_term)
                )
            )

        # Apply pagination
        total_count = query.count()
        servers = query.offset(offset).limit(limit).all()

        # Convert to response format
        server_list = []
        for server in servers:
            server_data = RegistryServerInfo(
                id=server.server_id,
                name=server.name,
                description=server.description,
                transport=server.mcp_registry_config.get("transport_type", "http"),
                url=server.mcp_registry_config.get("url"),
                favicon_url=server.mcp_registry_config.get("favicon_url"),
                category=server.server_metadata.get("category", "MCP Servers"),
                icon=server.server_metadata.get("icon", "🔍"),
                requiresAuth=server.server_metadata.get("requiresAuth", False),
                env_vars=server.server_metadata.get("env_vars", ""),
                note=server.server_metadata.get("note", ""),
                mcp_registry_config=server.mcp_registry_config,
                mcp_server_config=server.mcp_server_config,
                stats=server.stats,
                created_at=server.created_at.isoformat() if server.created_at else None,
                updated_at=server.updated_at.isoformat() if server.updated_at else None
            )
            server_list.append(server_data)

        logger.info(f"✅ Retrieved {len(server_list)} global MCP servers (total: {total_count})")

        return RegistryServersResponse(
            success=True,
            servers=server_list,
            total=total_count,
            limit=limit,
            offset=offset
        )

    except Exception as e:
        logger.error(f"❌ Error listing global MCP servers: {e}")
        logger.error(f"❌ Exception type: {type(e).__name__}")
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to list global MCP servers: {str(e)}") from e
    finally:
        if 'db' in locals():
            db.close()
