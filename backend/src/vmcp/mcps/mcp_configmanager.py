"""
MCP Configuration Management System
Handles MCP server configuration persistence and management
"""
import logging
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

from mcp.types import Prompt, Resource, ResourceTemplate, Tool

from vmcp.mcps.models import AuthenticationError, MCPConnectionStatus, MCPServerConfig
from vmcp.storage.base import StorageBase
from vmcp.utilities.tracing import trace_method

# Setup centralized logging for config module with span correlation
from vmcp.utilities.logging import setup_logging

logger = setup_logging("1xN_MCP_CONFIG")

class MCPConfigManager:
    """Manages MCP server configurations"""

    def __init__(self, user_id: str):
        self._servers: Dict[str, MCPServerConfig] = {}
        try:
            self.user_id = int(user_id)
        except ValueError:
            logger.error(f"user_id '{user_id}' is not convertible to int, cannot initialize StorageBase.")
            raise
        self.storage = StorageBase(self.user_id)
        self.load_mcp_servers()

        # OSS - no analytics tracking

    @trace_method("[MCPConfigManager]: Load Servers")
    def load_mcp_servers(self) -> None:
        servers_data = self.storage.get_mcp_servers()
        # Convert dictionaries back to MCPServerConfig objects
        self._servers = {}
        for id_, server_data in servers_data.items():
            try:
                # logger.info(f"Loading server config for {id_}: {server_data}")
                self._servers[id_] = MCPServerConfig.from_dict(server_data)
                logger.debug(f"Loaded server config for {id_}: {self._servers[id_].name} : {self._servers[id_].headers}")
            except Exception as e:
                logger.error(f"❌ Traceback: {traceback.format_exc()}")
                logger.warning(f"⚠️  Failed to load server config for {id_}: {e}")
                continue
        logger.debug(f"Loaded {len(self._servers)} MCP servers {self._servers.keys()}")
    
    def save_mcp_servers(self):
        # Convert MCPServerConfig objects to dictionaries for JSON serialization
        # servers_dict = {name: server.to_dict() for name, server in self._servers.items()}
        return self.storage.save_mcp_servers([x.to_dict() for x in list(self._servers.values())])

    @trace_method("[MCPConfigManager]: Add Server")
    def add_server(self, config: MCPServerConfig) -> bool:
        self._servers[config.server_id] = config
        # # Convert MCPServerConfig objects to dictionaries for JSON serialization
        # servers_dict = {name: server.to_dict() for name, server in self._servers.items()}
        # logger.info(f"Saving servers to storage: {servers_dict}")
        success = self.storage.save_mcp_servers([config.to_dict()])

        # Update AllServers_vMCP after adding server
        # if success:
        #     self._update_all_servers_vmcp()
        
        return success
    
    def add_server_from_dict(self, server_dict: Dict[str, Any]) -> bool:
        """Add a server from a dictionary configuration"""
        try:
            # Convert dictionary to MCPServerConfig object
            config = MCPServerConfig.from_dict(server_dict)
            return self.add_server(config)
        except Exception as e:
            logger.error(f"❌ Failed to add server from dict: {e}")
            return False
    
    def remove_server(self, id_: str) -> bool:
        if id_ in self._servers:
            del self._servers[id_]
            # Convert MCPServerConfig objects to dictionaries for JSON serialization
            # servers_dict = {name: server.to_dict() for name, server in self._servers.items()}
            success = self.storage.delete_mcp_server(id_)
            
            # Update AllServers_vMCP after removing server
            # if success:
            #     self._update_all_servers_vmcp()
            
            return success
        else:
            logger.warning(f"⚠️  Cannot remove unknown server: {id_}")
            return False
    
    def add_vmcp_to_server(self, server_id: str, vmcp_id: str) -> bool:
        """Add a vMCP ID to a server's usage list"""
        server = self.get_server(server_id)
        if not server:
            logger.warning(f"⚠️  Cannot add vMCP to unknown server: {server_id}")
            return False
        
        if vmcp_id not in server.vmcps_using_server:
            server.vmcps_using_server.append(vmcp_id)
            # Save the updated server configuration
            return self.storage.save_mcp_servers([server.to_dict()])
        
        return True  # Already exists, no need to save
    
    def remove_vmcp_from_server(self, server_id: str, vmcp_id: str) -> bool:
        """Remove a vMCP ID from a server's usage list"""
        server = self.get_server(server_id)
        if not server:
            logger.warning(f"⚠️  Cannot remove vMCP from unknown server: {server_id}")
            return False
        
        if vmcp_id in server.vmcps_using_server:
            server.vmcps_using_server.remove(vmcp_id)
            
            # If no vMCPs are using this server, remove it entirely
            if len(server.vmcps_using_server) == 0:
                logger.info(f"🗑️  No vMCPs using server {server_id}, removing server")
                return self.remove_server(server_id)
            else:
                # Save the updated server configuration
                return self.storage.save_mcp_servers([server.to_dict()])
        
        return True  # vMCP not in list, no need to save
    
    def get_servers_by_vmcp(self, vmcp_id: str) -> List[MCPServerConfig]:
        """Get all servers that are being used by a specific vMCP"""
        return [server for server in self._servers.values() if vmcp_id in server.vmcps_using_server]
    
    def rename_server(self, old_id_: str, new_name: str) -> bool:
        """Rename a server while preserving its configuration and ID"""
        if old_id_ not in self._servers:
            logger.warning(f"⚠️  Cannot rename unknown server: {old_id_}")
            return False
        
        if new_name in self._servers:
            logger.warning(f"⚠️  Cannot rename to existing server name: {new_name}")
            return False
        
        # Get the server config and update its name
        server_config = self._servers[old_id_]
        server_config.name = new_name
        
        # Remove old entry and add new one
        del self._servers[old_id_]
        self._servers[new_name] = server_config
        
        # Save to storage
        # servers_dict = {name: server.to_dict() for name, server in self._servers.items()}
        success = self.storage.save_mcp_servers([x.to_dict() for x in list(self._servers.values())])
        
        if success:
            logger.info(f"✅ Successfully renamed server from '{old_id_}' to '{new_name}' (ID: {server_config.server_id})")
        else:
            logger.error(f"❌ Failed to save renamed server configuration")
        
        return success
    
    @trace_method("[MCPConfigManager]: Get Server")
    def get_server(self, id_: str) -> Optional[MCPServerConfig]:
        config = self._servers.get(id_)
        return config
    
    def get_server_by_name(self, name: str) -> Optional[MCPServerConfig]:
        """Get a server configuration by its name"""
        for server_config in self._servers.values():
            if server_config.name == name:
                return server_config
        return None
    
    def get_server_by_id(self, server_id: str,from_db=False) -> Optional[MCPServerConfig]:
        """Get a server configuration by its unique ID"""
        if from_db:
            logger.info(f"   🔍 Getting server from db: {server_id}")
            server_data = self.storage.get_mcp_server(server_id)
            if server_data:
                _config = MCPServerConfig.from_dict(server_data["mcp_server_config"])
                self._servers[server_id] = _config
                return _config
            return None
        for server in self._servers.values():
            if server.server_id == server_id:
                return server
        return None
    
    def list_servers(self) -> List[MCPServerConfig]:
        """Return a list of all server configurations"""
        return list(self._servers.values())
    
    def update_server_status(self, id_: str, status: MCPConnectionStatus, 
                           error: Optional[str] = None) -> bool:    
        if id_ in self._servers:
            old_status = self._servers[id_].status
            self._servers[id_].status = status
            if error:
                self._servers[id_].last_error = error
            if status == MCPConnectionStatus.CONNECTED:
                self._servers[id_].last_connected = datetime.now()
                logger.info(f"🟢 {id_} connected successfully")
            
            # Log status changes
            if old_status != status:
                old_status_str = old_status.value if hasattr(old_status, 'value') else str(old_status)
                new_status_str = status.value if hasattr(status, 'value') else str(status)
                logger.info(f"📊 Status change for {id_}: {old_status_str} → {new_status_str}")
            
            # Convert MCPServerConfig objects to dictionaries for JSON serialization
            # servers_dict = {name: server.to_dict() for name, server in self._servers.items()}
            return self.storage.save_mcp_servers([x.to_dict() for x in list(self._servers.values())])
        else:
            logger.warning(f"⚠️  Cannot update status for unknown server: {id_}")
            return False
    
    def update_server_config(self, id_: str, config: MCPServerConfig) -> bool:
        if id_ in self._servers:
            logger.info(f"""
                           📊 Updating server config for {id_} {config.name}: 
                           Tools: {len(config.tools)}
                           Resources: {len(config.resources)}
                           Prompts: {len(config.prompts)}""")
            self._servers[id_] = config
            # self.save_mcp_server_config()
            # servers_dict = {name: server.to_dict() for name, server in self._servers.items()}
            return self.storage.save_mcp_servers([config.to_dict()])
        else:
            logger.warning(f"⚠️  Cannot update config for unknown server: {id_}")
            return False
        
    def update_server_capabilities(self, id_: str, capabilities: Dict[str, Any],
                                 tools: Optional[List[str]] = None,
                                 tool_details: Optional[List[Tool]] = None,
                                 resources: Optional[List[str]] = None,
                                 resource_details: Optional[List[Resource]] = None,
                                 resource_templates: Optional[List[str]] = None,
                                 resource_template_details: Optional[List[ResourceTemplate]] = None,
                                 prompts: Optional[List[str]] = None,
                                 prompt_details: Optional[List[Prompt]] = None) -> None:
        if id_ in self._servers:
            server = self._servers[id_]
            server.capabilities = capabilities
            server.tools = tools or []
            server.tool_details = tool_details or []
            server.resources = resources or []
            server.resource_details = resource_details or []
            server.resource_templates = resource_templates or []
            server.resource_template_details = resource_template_details or []
            server.prompts = prompts or []
            server.prompt_details = prompt_details or []
            
            # Log detailed capabilities
            if tools:
                logger.info(f"   🎯 Available tools: {', '.join(tools)}")
            if resources:
                logger.info(f"   📦 Available resources: {', '.join(resources)}")
            if resource_templates:
                logger.info(f"   📋 Available resource templates: {', '.join(resource_templates)}")
            if prompts:
                logger.info(f"   📝 Available prompts: {', '.join(prompts)}")
            
            # Convert MCPServerConfig objects to dictionaries for JSON serialization
            # servers_dict = {name: server.to_dict() for name, server in self._servers.items()}
            self.storage.save_mcp_servers([x.to_dict() for x in list(self._servers.values())])
        else:
            logger.warning(f"⚠️  Cannot update capabilities for unknown server: {id_}")

    async def ping_server(self, server_id: str,client_manager):
        """Ping an MCP server"""

        # Ping the server to get current status
        current_status = MCPConnectionStatus.UNKNOWN
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
        if current_status != self._servers[server_id].status:
            logger.info(f"   🔄 Updating {server_id} status: {self._servers[server_id].status.value} → {current_status.value}")
        self.update_server_status(server_id, current_status)

        return current_status
    
    async def discover_capabilities(self, server_id: str,client_manager):
        """Ping an MCP server"""

        server_config = self.get_server(server_id)
        capabilities={}
        try:
            capabilities = await client_manager.discover_capabilities(server_id)
                
            if capabilities:
                # Update server config with discovered capabilities
                if capabilities.get('tools',[]):
                    server_config.tools = capabilities.get('tools', [])
                if capabilities.get('resources',[]):
                    server_config.resources = capabilities.get('resources', [])
                if capabilities.get('prompts',[]):
                    server_config.prompts = capabilities.get('prompts', [])
                if capabilities.get('tool_details',[]):
                    server_config.tool_details = capabilities.get('tool_details', [])
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
            self.update_server_config(server_id, server_config)
        except Exception as e:
            logger.error(f"   ❌ Traceback: {traceback.format_exc()}")
            logger.error(f"   ❌ Error discovering capabilities for server {server_id}: {e}")
        
        return capabilities


    @trace_method("[MCPConfigManager]: List Tools")
    def tools_list(self, id_: str) -> List[Tool]:
        return self._servers[id_].tool_details or []
    
    @trace_method("[MCPConfigManager]: List Prompts")
    def prompts_list(self, id_: str) -> List[Prompt]:
        return self._servers[id_].prompt_details or []

    @trace_method("[MCPConfigManager]: List Resources")
    def resources_list(self, id_: str) -> List[Resource]:
        return self._servers[id_].resource_details or []

    @trace_method("[MCPConfigManager]: List Resource Templates")
    def resource_templates_list(self, id_: str) -> List[ResourceTemplate]:
        return self._servers[id_].resource_template_details or []

    @trace_method("[MCPConfigManager]: Tool Call")
    def tool_call(self, id_: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return self._servers[id_].tool_call(arguments)

    @trace_method("[MCPConfigManager]: Get Resource")
    def get_resource(self, id_: str, uri: str) -> Dict[str, Any]:
        return self._servers[id_].get_resource(uri, connect_if_needed=True)

    @trace_method("[MCPConfigManager]: Get Prompt")
    def get_prompt(self, id_: str, prompt_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._servers[id_].get_prompt(prompt_name, arguments, connect_if_needed=True)