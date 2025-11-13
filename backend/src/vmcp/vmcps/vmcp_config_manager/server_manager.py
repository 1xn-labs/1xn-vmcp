#!/usr/bin/env python3
"""
Server Manager
==============

Handles MCP server installation, configuration, and usage tracking for vMCP.
"""

import logging
from typing import Dict, Any, Optional

from vmcp.mcps.models import MCPServerConfig, MCPTransportType, MCPConnectionStatus

from vmcp.utilities.logging import setup_logging

logger = setup_logging("1xN_vMCP_SERVER_MANAGER")


def install_public_vmcp(
    storage,
    user_id: str,
    mcp_config_manager,
    create_vmcp_config_func,
    public_vmcp: Dict[str, Any],
    server_conflicts: Dict[str, str]
) -> Dict[str, Any]:
    """
    Install a public vMCP to the current user's account.

    Args:
        storage: StorageBase instance
        user_id: User identifier
        mcp_config_manager: MCP config manager for server operations
        create_vmcp_config_func: Function to create vMCP config
        public_vmcp: Public vMCP data dictionary
        server_conflicts: Server conflict resolution mapping

    Returns:
        Dictionary with installation result
    """
    try:
        # Create a new vMCP configuration for the current user
        vmcp_config = public_vmcp.get("vmcp_config", {})

        # Handle server conflicts
        server_installations = []
        resolved_config = vmcp_config.copy()

        if "selected_servers" in resolved_config:
            for server in resolved_config["selected_servers"]:
                server_name = server.get("name")
                if server_name in server_conflicts:
                    action = server_conflicts[server_name]

                    if action == "use_existing":
                        # Replace server name with existing one
                        existing_server_name = server_conflicts.get(f"{server_name}_existing")
                        if existing_server_name:
                            server["name"] = existing_server_name
                            server_installations.append({
                                "server_name": server_name,
                                "action": "use_existing",
                                "resolved_name": existing_server_name
                            })
                    elif action == "install_new":
                        # Install new server with different name
                        new_server_name = f"{server_name}_{user_id[:8]}"
                        server["name"] = new_server_name

                        # Install the server configuration
                        server_install_result = _install_server_from_config(server, mcp_config_manager)
                        if server_install_result:
                            server_installations.append({
                                "server_name": server_name,
                                "action": "install_new",
                                "new_name": new_server_name,
                                "status": "installed"
                            })
                        else:
                            server_installations.append({
                                "server_name": server_name,
                                "action": "install_new",
                                "new_name": new_server_name,
                                "status": "failed"
                            })

        # Create the vMCP for the current user
        vmcp_id = create_vmcp_config_func(
            name=f"{public_vmcp['name']} (Installed)",
            description=public_vmcp.get('description', ''),
            system_prompt=resolved_config.get('system_prompt'),
            vmcp_config=resolved_config,
            custom_prompts=resolved_config.get('custom_prompts', []),
            custom_tools=resolved_config.get('custom_tools', []),
            custom_context=resolved_config.get('custom_context', []),
            custom_resources=resolved_config.get('custom_resources', []),
            custom_resource_uris=resolved_config.get('custom_resource_uris', []),
            environment_variables=resolved_config.get('environment_variables', []),
            uploaded_files=resolved_config.get('uploaded_files', [])
        )

        if vmcp_id:
            # Update install count for the public vMCP
            storage.increment_public_vmcp_install_count(public_vmcp['id'])

            return {
                "success": True,
                "installed_vmcp_id": vmcp_id,
                "server_installations": server_installations
            }
        else:
            return {
                "success": False,
                "error": "Failed to create vMCP configuration"
            }

    except Exception as e:
        logger.error(f"Error installing public vMCP: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def _install_server_from_config(server_config: Dict[str, Any], mcp_config_manager) -> bool:
    """
    Install a server from vMCP configuration.

    Args:
        server_config: Server configuration dictionary
        mcp_config_manager: MCP config manager instance

    Returns:
        True if successful, False otherwise
    """
    try:
        # Extract server configuration
        server_name = server_config.get("name")
        transport_type = server_config.get("transport_type", "http")
        url = server_config.get("url")
        description = server_config.get("description", "")

        # Create MCP server configuration
        mcp_config = {
            "name": server_name,
            "mode": transport_type,
            "description": description,
            "url": url,
            "auto_connect": False,
            "enabled": True
        }

        # Install the server using MCP config manager
        return mcp_config_manager.add_server_from_dict(mcp_config)

    except Exception as e:
        logger.error(f"Error installing server from config: {e}")
        return False


def get_username_by_id(user_id: str) -> str:
    """
    Get username by user ID.

    Args:
        user_id: User identifier

    Returns:
        Username string
    """
    try:
        # This would typically query a user service
        # For now, return a placeholder
        return f"user_{user_id[:8]}"
    except Exception as e:
        logger.error(f"Error getting username: {e}")
        return f"user_{user_id[:8]}"


def handle_server_usage_changes(
    vmcp_id: str,
    old_config: Dict[str, Any],
    new_config: Dict[str, Any],
    mcp_config_manager
):
    """
    Handle server usage tracking when vMCP configuration changes.

    Args:
        vmcp_id: VMCP identifier
        old_config: Old configuration dictionary
        new_config: New configuration dictionary
        mcp_config_manager: MCP config manager instance
    """
    try:
        # Get old and new server lists
        old_servers = old_config.get('selected_servers', []) if old_config else []
        new_servers = new_config.get('selected_servers', []) if new_config else []

        # Convert to sets of server IDs for easier comparison
        old_server_ids = {server.get('server_id') for server in old_servers if server.get('server_id')}
        new_server_ids = {server.get('server_id') for server in new_servers if server.get('server_id')}

        # Find servers that were added
        added_servers = new_server_ids - old_server_ids
        # Find servers that were removed
        removed_servers = old_server_ids - new_server_ids

        # Handle newly added servers
        for server_id in added_servers:
            if server_id:
                # Check if server exists in backend
                existing_server = mcp_config_manager.get_server(server_id)
                if not existing_server:
                    # Server doesn't exist, create it from the vMCP config
                    server_data = next((s for s in new_servers if s.get('server_id') == server_id), None)
                    if server_data:
                        create_server_from_vmcp_config(server_data, vmcp_id, mcp_config_manager)
                else:
                    # Server exists, just add vMCP to its usage list
                    mcp_config_manager.add_vmcp_to_server(server_id, vmcp_id)
                    logger.info(f"✅ Added vMCP {vmcp_id} to existing server {server_id}")

        # Remove vMCP from removed servers
        for server_id in removed_servers:
            if server_id:
                mcp_config_manager.remove_vmcp_from_server(server_id, vmcp_id)
                logger.info(f"✅ Removed vMCP {vmcp_id} from server {server_id}")

    except Exception as e:
        logger.error(f"❌ Error handling server usage changes for vMCP {vmcp_id}: {e}")


def create_server_from_vmcp_config(
    server_data: Dict[str, Any],
    vmcp_id: str,
    mcp_config_manager
):
    """
    Create a new server from vMCP configuration data.

    Args:
        server_data: Server data dictionary
        vmcp_id: VMCP identifier
        mcp_config_manager: MCP config manager instance
    """
    try:
        # Map transport type
        transport_type = MCPTransportType(server_data.get('transport_type', 'http'))

        # Create server config
        server_config = MCPServerConfig(
            name=server_data.get('name', ''),
            transport_type=transport_type,
            description=server_data.get('description', ''),
            url=server_data.get('url'),
            headers=server_data.get('headers', {}),
            status=MCPConnectionStatus.DISCONNECTED,
            auto_connect=server_data.get('auto_connect', True),
            enabled=server_data.get('enabled', True),
            vmcps_using_server=[vmcp_id]  # Initialize with the vMCP that's creating it
        )

        # Generate server ID
        server_id = server_config.ensure_server_id()

        # Add server to backend
        success = mcp_config_manager.add_server(server_config)
        if success:
            logger.info(f"✅ Created new server {server_id} ({server_config.name}) for vMCP {vmcp_id}")
        else:
            logger.error(f"❌ Failed to create server {server_id} for vMCP {vmcp_id}")

    except Exception as e:
        logger.error(f"❌ Error creating server from vMCP config: {e}")


def update_vmcp_server(
    vmcp_id: str,
    server_config: MCPServerConfig,
    storage,
    update_vmcp_config_func,
    load_vmcp_config_func
) -> bool:
    """
    Update the server configuration for a vMCP.

    Auto-populates selected_tools, selected_resources, and selected_prompts
    if they don't already exist for this server.

    Args:
        vmcp_id: VMCP identifier
        server_config: Server configuration
        storage: StorageBase instance
        update_vmcp_config_func: Function to update vMCP config
        load_vmcp_config_func: Function to load vMCP config

    Returns:
        True if successful, False otherwise
    """
    vmcp_config = load_vmcp_config_func(vmcp_id)
    server_id = server_config.server_id

    if vmcp_config:
        selected_servers = vmcp_config.vmcp_config.get('selected_servers', [])
        if selected_servers:
            for idx, server in enumerate(selected_servers):
                logger.info(f"🔍 Checking server: {server.get('server_id')} == {server_id}")
                server_config_dict = server_config.to_dict()
                logger.info(f"🔍 Server config dict: {server_config_dict.get('tools', [])}")

                if server.get('server_id') == server_id:
                    vmcp_config.vmcp_config['selected_servers'][idx] = server_config_dict

                    # Auto-populate tools, resources, prompts if not already present
                    selected_tools = vmcp_config.vmcp_config.get('selected_tools', {})
                    selected_resources = vmcp_config.vmcp_config.get('selected_resources', {})
                    selected_prompts = vmcp_config.vmcp_config.get('selected_prompts', {})

                    logger.info(f"🔍 Selected tools [current]: {selected_tools}")

                    if not selected_tools.get(server_id, []):
                        selected_tools[server_id] = server_config_dict.get('tools', [])
                        vmcp_config.vmcp_config['selected_tools'] = selected_tools
                        logger.info(f"🔍 Selected tools: {selected_tools}")
                        vmcp_config.total_tools = sum(len(x) for x in selected_tools.values())

                    if not selected_resources.get(server_id, []):
                        selected_resources[server_id] = server_config_dict.get('resources', []).copy()
                        vmcp_config.vmcp_config['selected_resources'] = selected_resources.copy()
                        vmcp_config.total_resources = sum(len(x) for x in selected_resources.values())

                    if not selected_prompts.get(server_id, []):
                        selected_prompts[server_id] = server_config_dict.get('prompts', []).copy()
                        vmcp_config.vmcp_config['selected_prompts'] = selected_prompts
                        vmcp_config.total_prompts = sum(len(x) for x in selected_prompts.values())

                    update_vmcp_config_func(vmcp_id, vmcp_config=vmcp_config.vmcp_config)
                    break

        return True

    return False
