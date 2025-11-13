#!/usr/bin/env python3
"""
Agent Configuration Manager
===========================

This module manages agent configurations and modifies MCP server behavior
based on active agent settings. It reads agent JSON configs from ~/.1xn/agents/
and applies custom prompts, tools, context, and resources.
"""

import traceback
import os
import json
import logging
import ast
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from mcp.types import Tool, Resource, ResourceTemplate, Prompt, PromptArgument, TextContent, PromptMessage, GetPromptResult, \
    CallToolResult, ReadResourceResult, Result, TextResourceContents, BlobResourceContents, EmbeddedResource
from vmcp.vmcps.mcp_dependencies import get_http_request
from vmcp.config import settings
import jinja2
from jinja2 import Environment, DictLoader

# Add utilities to path for logging config
# Try different possible paths for Docker and local development
from vmcp.utilities.tracing import trace_method, add_event, log_to_span
import logging


from vmcp.vmcps.utilities import convert_openxml_to_csv, get_mime_type
from vmcp.storage.base import StorageBase
from vmcp.mcps.mcp_configmanager import MCPConfigManager
from vmcp.mcps.mcp_client import MCPClientManager
from vmcp.vmcps.models import VMCPConfig, VMCPToolCallRequest, VMCPResourceTemplateRequest
from vmcp.vmcps.default_prompts import get_all_default_prompts, handle_default_prompt
import re
from datetime import datetime
from vmcp.mcps.models import MCPServerConfig
import asyncio

from vmcp.utilities.logging import setup_logging

logger = setup_logging("1xN_vMCP_CONFIG_MANAGER")
@dataclass
class ReadResourceContents:
    """Contents returned from a read_resource call."""

    content: str | bytes
    mime_type: str | None = None

@dataclass(frozen=True)
class UIWidget:
    identifier: str
    title: str
    template_uri: str
    invoking: str
    invoked: str
    html: str
    response_text: str

MIME_TYPE = "text/html+skybridge"

def _resource_description(widget: UIWidget) -> str:
    return f"{widget.title} widget markup"


def _tool_meta(widget: UIWidget) -> Dict[str, Any]:
    return {
        "openai/outputTemplate": widget.template_uri,
        "openai/toolInvocation/invoking": widget.invoking,
        "openai/toolInvocation/invoked": widget.invoked,
        "openai/widgetAccessible": True,
        "openai/resultCanProduceWidget": True,
        "annotations": {
          "destructiveHint": False,
          "openWorldHint": False,
          "readOnlyHint": True,
        }
    }


def _embedded_widget_resource(widget: UIWidget) -> EmbeddedResource:
    return EmbeddedResource(
        type="resource",
        resource=TextResourceContents(
            uri=widget.template_uri,
            mimeType=MIME_TYPE,
            text=widget.html,
            title=widget.title,
        ),
    )


class VMCPConfigManager:
    """Manages agent configurations for MCP server"""
    
    def __init__(self, user_id: str, vmcp_id: Optional[str] = None, logging_config:Optional[Dict[str, Any]] = {"agent_name": "1xn_web_client", "agent_id": "1xn_web_client", "client_id": "1xn_web_client"}):
        self.storage = StorageBase(user_id)
        self.user_id = user_id
        self.vmcp_id = vmcp_id
        self.mcp_config_manager = MCPConfigManager(user_id)
        self.mcp_client_manager = MCPClientManager(self.mcp_config_manager)
        self.logging_config = logging_config
        
        # Initialize Jinja2 environment for template preprocessing
        self.jinja_env = Environment(
            loader=DictLoader({}),
            variable_start_string='{{',
            variable_end_string='}}',
            block_start_string='{%',
            block_end_string='%}',
            comment_start_string='{#',
            comment_end_string='#}'
        )
        
        # OSS: Analytics removed
    
    def _save_vmcp_environment(self, vmcp_id: str, environment_vars: Dict[str, str]):
        """Save vMCP environment variables to a file"""
        return self.storage.save_vmcp_environment(vmcp_id, environment_vars)
    
    def _load_vmcp_environment(self, vmcp_id: str) -> Dict[str, str]:
        """Load vMCP environment variables from file"""
        return self.storage.load_vmcp_environment(vmcp_id)
    
    @trace_method("[VMCPConfigManager]: Load VMCP Config")
    def load_vmcp_config(self,specific_vmcp_id: Optional[str] = None) -> Optional[VMCPConfig]:
        """Load vMCP configuration from file"""
        vmcp_id_to_load = specific_vmcp_id or self.vmcp_id
        
        # Log the operation to span
        log_to_span(
            f"Loading vMCP config for {vmcp_id_to_load}",
            operation_type="config_load",
            operation_id=f"load_vmcp_config_{vmcp_id_to_load}",
            arguments={"vmcp_id": vmcp_id_to_load},
            metadata={"operation": "load_vmcp_config", "vmcp_id": vmcp_id_to_load}
        )
        
        if specific_vmcp_id:
            result = self.storage.load_vmcp_config(specific_vmcp_id)
        else:
            result = self.storage.load_vmcp_config(self.vmcp_id)
        
        # Log the result
        if result:
            log_to_span(
                f"Successfully loaded vMCP config for {vmcp_id_to_load}",
                operation_type="config_load",
                operation_id=f"load_vmcp_config_{vmcp_id_to_load}",
                result={"success": True, "vmcp_name": result.name, "total_tools": getattr(result, 'total_tools', 0)},
                level="info"
            )
        else:
            log_to_span(
                f"Failed to load vMCP config for {vmcp_id_to_load}",
                operation_type="config_load",
                operation_id=f"load_vmcp_config_{vmcp_id_to_load}",
                result={"success": False, "error": "Config not found"},
                level="warning"
            )
        
        return result
    
    @trace_method("[VMCPConfigManager]: List Available VMCPs")
    def list_available_vmcps(self) -> List[Dict[str, Any]]:
        """List all available VMCP configurations"""
        return self.storage.list_vmcps()

    @trace_method("[VMCPConfigManager]: Save VMCP Config")
    def save_vmcp_config(self, vmcp_config: VMCPConfig) -> bool:
        """Save a vMCP configuration"""
        return self.storage.save_vmcp(vmcp_config.id, vmcp_config.to_dict())

    @trace_method("[VMCPConfigManager]: List Public VMCPs")
    def list_public_vmcps(self) -> List[Dict[str, Any]]:
        """List all public vMCPs available for installation"""
        try:
            return self.storage.list_public_vmcps()
        except Exception as e:
            logger.error(f"Error listing public vMCPs: {e}")
            return []
    
    @staticmethod
    def list_public_vmcps_static() -> List[Dict[str, Any]]:
        """List all public vMCPs available for installation (static method)"""
        # OSS: Public vMCP registry not implemented yet
        logger.debug("Public vMCP registry not available in OSS version")
        return []
        
    def list_wellknown_vmcps(self) -> List[Dict[str, Any]]:
        """List all public vMCPs available for installation"""
        try:
            return self.storage.list_wellknown_vmcps()
        except Exception as e:
            logger.error(f"Error listing public vMCPs: {e}")
            return []

    def get_public_vmcp(self, vmcp_id: str) -> Optional[Dict[str, Any]]:
        """Get details of a specific public vMCP"""
        try:
            return self.storage.get_public_vmcp(vmcp_id)
        except Exception as e:
            logger.error(f"Error getting public vMCP: {e}")
            return None
    
    @staticmethod
    def get_public_vmcp_static(vmcp_id: str) -> Optional[Dict[str, Any]]:
        """Get details of a specific public vMCP (static method)"""
        # OSS: Public vMCP registry not implemented yet
        logger.debug(f"Public vMCP registry not available in OSS version: {vmcp_id}")
        return None

    def get_wellknown_vmcp(self, vmcp_id: str) -> Optional[Dict[str, Any]]:
        """Get details of a specific well-known vMCP"""
        try:
            return self.storage.get_wellknown_vmcp(vmcp_id)
        except Exception as e:
            logger.error(f"Error getting well-known vMCP: {e}")
            return None
    
    @staticmethod
    def get_wellknown_vmcp_static(vmcp_id: str) -> Optional[Dict[str, Any]]:
        """Get details of a specific well-known vMCP (static method)"""
        # OSS: Well-known vMCP registry not implemented yet
        logger.debug(f"Well-known vMCP registry not available in OSS version: {vmcp_id}")
        return None

    def install_public_vmcp(self, public_vmcp: Dict[str, Any], server_conflicts: Dict[str, str]) -> Dict[str, Any]:
        """Install a public vMCP to the current user's account"""
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
                            new_server_name = f"{server_name}_{self.user_id[:8]}"
                            server["name"] = new_server_name
                            
                            # Install the server configuration
                            server_install_result = self._install_server_from_config(server)
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
            vmcp_id = self.create_vmcp_config(
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
                self.storage.increment_public_vmcp_install_count(public_vmcp['id'])
                
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

    def _install_server_from_config(self, server_config: Dict[str, Any]) -> bool:
        """Install a server from vMCP configuration"""
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
            return self.mcp_config_manager.add_server_from_dict(mcp_config)
            
        except Exception as e:
            logger.error(f"Error installing server from config: {e}")
            return False

    def _get_username_by_id(self, user_id: str) -> str:
        """Get username by user ID"""
        try:
            # This would typically query a user service
            # For now, return a placeholder
            return f"user_{user_id[:8]}"
        except Exception as e:
            logger.error(f"Error getting username: {e}")
            return f"user_{user_id[:8]}"
    
    def _is_jinja_template(self, text: str) -> bool:
        """Check if text contains Jinja2 patterns (after @param variables have been substituted)"""
        import re
        
        # Check for Jinja2 patterns
        jinja_patterns = [
            r'\{\{[^}]*\}\}',
            r'\{%[^%]*%\}', 
            r'\{#[^#]*#\}'
        ]
        
        has_jinja_patterns = any(re.search(pattern, text) for pattern in jinja_patterns)
        
        if not has_jinja_patterns:
            logger.info(f"🔍 No Jinja2 patterns found in text")
            return False
        
        # Validate Jinja2 syntax
        try:
            self.jinja_env.parse(text)
            logger.info(f"✅ Valid Jinja2 template detected")
            return True
        except Exception as e:
            logger.info(f"❌ Jinja2 syntax validation failed: {e}")
            return False
    
    def _preprocess_jinja_to_regex(self, text: str, arguments: Dict[str, Any], 
                                  environment_variables: Dict[str, Any]) -> str:
        """Convert Jinja2 templates to plain text for existing regex system"""
        if not self._is_jinja_template(text):
            logger.info(f"✅ Not a Jinja2 template")
            return text
        
        try:
            # Create Jinja2 template
            template = self.jinja_env.from_string(text)
            
            # Prepare context
            context = {
                **arguments,
                **environment_variables,
                'param': arguments,
                'config': environment_variables,
            }
            
            # Render the template to get final text
            rendered_text = template.render(**context)
            logger.info(f"✅ Jinja2 template rendered successfully")
            return rendered_text
            
        except Exception as e:
            logger.warning(f"Jinja2 preprocessing failed, using original text: {e}")
            return text

    def _handle_server_usage_changes(self, vmcp_id: str, old_config: Dict[str, Any], new_config: Dict[str, Any]):
        """Handle server usage tracking when vMCP configuration changes"""
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
                    existing_server = self.mcp_config_manager.get_server(server_id)
                    if not existing_server:
                        # Server doesn't exist, create it from the vMCP config
                        server_data = next((s for s in new_servers if s.get('server_id') == server_id), None)
                        if server_data:
                            self._create_server_from_vmcp_config(server_data, vmcp_id)
                    else:
                        # Server exists, just add vMCP to its usage list
                        self.mcp_config_manager.add_vmcp_to_server(server_id, vmcp_id)
                        logger.info(f"✅ Added vMCP {vmcp_id} to existing server {server_id}")
            
            # Remove vMCP from removed servers
            for server_id in removed_servers:
                if server_id:
                    self.mcp_config_manager.remove_vmcp_from_server(server_id, vmcp_id)
                    logger.info(f"✅ Removed vMCP {vmcp_id} from server {server_id}")
                    
        except Exception as e:
            logger.error(f"❌ Error handling server usage changes for vMCP {vmcp_id}: {e}")
    
    def _create_server_from_vmcp_config(self, server_data: Dict[str, Any], vmcp_id: str):
        """Create a new server from vMCP configuration data"""
        try:
            from vmcp.mcps.models import MCPServerConfig, MCPTransportType, MCPConnectionStatus
            
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
            success = self.mcp_config_manager.add_server(server_config)
            if success:
                logger.info(f"✅ Created new server {server_id} ({server_config.name}) for vMCP {vmcp_id}")
            else:
                logger.error(f"❌ Failed to create server {server_id} for vMCP {vmcp_id}")
                
        except Exception as e:
            logger.error(f"❌ Error creating server from vMCP config: {e}")

    def get_all_servers_vmcp_id(self) -> Optional[str]:
        """Get the ID of the AllServers_vMCP"""
        try:
            existing_vmcps = self.list_available_vmcps()
            for vmcp in existing_vmcps:
                if vmcp.get('name') == 'AllServers_vMCP':
                    return vmcp.get('id')
            return None
        except Exception as e:
            logger.error(f"Error getting AllServers_vMCP ID for user {self.user_id}: {e}")
            return None

    def _get_agent_activation_variables(self, agent_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get variables needed for agent activation"""
        variables = []
        
        # Add system prompt variables
        system_prompt = agent_data.get('system_prompt', {})
        if isinstance(system_prompt, dict):
            system_variables = system_prompt.get('variables', [])
            variables.extend(system_variables)
            
            # Add system prompt environment variables
            system_env_variables = system_prompt.get('environment_variables', [])
            for env_var in system_env_variables:
                env_name = env_var.get('name')
                if env_name:
                    variables.append({
                        'name': env_name,
                        'required': env_var.get('required', False),
                        'description': env_var.get('description', f"Environment variable: {env_name}")
                    })
        
        # Add environment variables from agent configuration
        env_variables = agent_data.get('environment_variables', [])
        for env_var in env_variables:
            env_name = env_var.get('name')
            if env_name:
                # Check if this environment variable is already in the list
                if not any(v.get('name') == env_name for v in variables):
                    variables.append({
                        'name': env_name,
                        'required': env_var.get('required', False),
                        'description': f"Environment variable: {env_name}"
                    })
        
        return variables
    
    def _read_agent_file_content(self, file_data: Dict[str, Any]) -> Optional[str]:
        """Read content from an agent file via blob service"""
        try:
            blob_id = file_data.get('blob_id')
            if not blob_id:
                return None
            
            # Fetch file content from blob service
            import httpx
            
            blob_url = f"http://1xn_blob_storage:9014/blob/{blob_id}"
            with httpx.Client(timeout=10.0) as client:
                response = client.get(blob_url)
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch blob {blob_id} from service: {response.status_code}")
                return None
            
            content = response.content
            
            # Get proper MIME type and determine if it's text
            filename = file_data.get('original_name', 'unknown')
            content_type = get_mime_type(filename)
            
            # Check if this is an OpenXML file that should be converted to CSV
            if content_type and 'openxmlformats' in content_type:
                csv_content, csv_mime_type = convert_openxml_to_csv(content, filename)
                return csv_content
            
            is_text = content_type.startswith('text/') or content_type in ['application/json', 'application/xml', 'application/yaml', 'application/javascript', 'text/markdown', 'text/csv']
            
            if is_text:
                try:
                    # Try UTF-8 first
                    text_content = content.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        # Try other encodings
                        text_content = content.decode('latin-1')
                    except UnicodeDecodeError:
                        # If all else fails, return as base64
                        import base64
                        text_content = base64.b64encode(content).decode('ascii')
                
                return text_content
            else:
                # For binary files, return base64 encoded content (without prefix)
                import base64
                encoded_content = base64.b64encode(content).decode('ascii')
                return encoded_content
            
        except Exception as e:
            logger.error(f"Error reading agent file content from blob service: {e}")
            return None
  
    def create_vmcp_config(self, name: str, description: Optional[str] = None,
                          system_prompt: Optional[Dict[str, Any]] = None,
                          vmcp_config: Optional[Dict[str, Any]] = None,
                          custom_prompts: Optional[List[Dict[str, Any]]] = None,
                          custom_tools: Optional[List[Dict[str, Any]]] = None,
                          custom_context: Optional[List[str]] = None,
                          custom_resources: Optional[List[Dict[str, Any]]] = None,
                          custom_resource_templates: Optional[List[Dict[str, Any]]] = None,
                          custom_resource_uris: Optional[List[str]] = None,
                          environment_variables: Optional[List[Dict[str, Any]]] = None,
                          uploaded_files: Optional[List[Dict[str, Any]]] = None) -> Optional[str]:
        """Create a new VMCP configuration"""
        try:
            # Generate unique VMCP ID
            import uuid
            vmcp_id = str(uuid.uuid4())
            
            # Convert string system prompt to object format if needed
            if isinstance(system_prompt, str):
                system_prompt = {
                    "text": system_prompt,
                    "variables": []
                }
            
            # Get the total number of tools, resources, resource templates, and prompts
            total_tools = len(custom_tools or []) + sum(len(x) for x in vmcp_config.get('selected_tools', {}).values())
            total_resources = len(custom_resources or []) + sum(len(x) for x in vmcp_config.get('selected_resources', {}).values())
            total_resource_templates = len(custom_resource_templates or []) + sum(len(x) for x in vmcp_config.get('selected_resource_templates', {}).values())
            total_prompts = len(custom_prompts or []) + sum(len(x) for x in vmcp_config.get('selected_prompts', {}).values())

            # Create VMCP configuration
            config = VMCPConfig(
                id=vmcp_id,
                name=name,
                user_id=self.user_id,
                description=description,
                system_prompt=system_prompt,
                vmcp_config=vmcp_config,
                custom_prompts=custom_prompts or [],
                custom_tools=custom_tools or [],
                custom_context=custom_context or [],
                custom_resources=custom_resources or [],
                custom_resource_templates=custom_resource_templates or [],
                environment_variables=environment_variables or [],
                uploaded_files=uploaded_files or [],
                custom_resource_uris=custom_resource_uris or [],
                total_tools=total_tools,
                total_resources=total_resources,
                total_resource_templates=total_resource_templates,
                total_prompts=total_prompts,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                creator_id=self.user_id,
                creator_username=self.user_id,
                metadata={"url": f"{settings.base_url}/private/{name}/vmcp", "type": "vmcp"}
            )
            
            # Save to storage
            success = self.storage.save_vmcp(vmcp_id, config.to_dict())
            if success:
                logger.info(f"Created VMCP config: {name} (ID: {vmcp_id})")
                # return vmcp_id
            else:
                logger.error(f"Failed to save VMCP config: {name}")
                # return None
            
            update_data = {
                "vmcp_config": config.to_dict(),
                "vmcp_registry_config": config.to_vmcp_registry_config().to_dict()
            }
            self.storage.update_private_vmcp_registry(private_vmcp_id=vmcp_id, private_vmcp_registry_data=update_data, operation="add")
            logger.info(f"Updated private vMCP registry: {vmcp_id}")
            return vmcp_id
            
        except Exception as e:
            logger.error(f"Error creating VMCP config: {e}")
            return None

    @trace_method("[VMCPConfigManager]: Update VMCP Config")
    def update_vmcp_config(self, vmcp_id: str, name: Optional[str] = None,
                          description: Optional[str] = None,
                          system_prompt: Optional[Dict[str, Any]] = None,
                          vmcp_config: Optional[Dict[str, Any]] = None,
                          custom_prompts: Optional[List[Dict[str, Any]]] = None,
                          custom_tools: Optional[List[Dict[str, Any]]] = None,
                          custom_context: Optional[List[str]] = None,
                          custom_resources: Optional[List[Dict[str, Any]]] = None,
                          custom_resource_templates: Optional[List[Dict[str, Any]]] = None,
                          custom_resource_uris: Optional[List[str]] = None,
                          environment_variables: Optional[List[Dict[str, Any]]] = None,
                          uploaded_files: Optional[List[Dict[str, Any]]] = None,
                          is_public: Optional[bool] = None,
                          public_tags: Optional[List[str]] = None,
                          public_at: Optional[str] = None,
                          creator_id: Optional[str] = None,
                          creator_username: Optional[str] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Update an existing VMCP configuration"""
        try:
            # Load existing config
            existing_config = self.storage.load_vmcp_config(vmcp_id)
            if not existing_config:
                logger.error(f"VMCP config not found: {vmcp_id}")
                return False
            
            # Update fields if provided
            if name is not None:
                existing_config.name = name
                existing_config.metadata["url"] = f"{settings.base_url}/private/{name}/vmcp"
            if description is not None:
                existing_config.description = description
            if system_prompt is not None:
                existing_config.system_prompt = system_prompt
            if vmcp_config is not None:
                # Track server usage changes when vmcp_config is updated
                # self._handle_server_usage_changes(vmcp_id, existing_config.vmcp_config, vmcp_config)
                existing_config.vmcp_config = vmcp_config
                # logger.info(f"Updated vmcp_config {vmcp_id} to: {vmcp_config}")
            if custom_prompts is not None:
                existing_config.custom_prompts = custom_prompts
            if custom_tools is not None:
                existing_config.custom_tools = custom_tools
            if custom_context is not None:
                existing_config.custom_context = custom_context
            if custom_resources is not None:
                existing_config.custom_resources = custom_resources
            if custom_resource_templates is not None:
                existing_config.custom_resource_templates = custom_resource_templates
            if custom_resource_uris is not None:
                existing_config.custom_resource_uris = custom_resource_uris
            if environment_variables is not None:
                existing_config.environment_variables = environment_variables
            if uploaded_files is not None:
                existing_config.uploaded_files = uploaded_files
            if creator_id is not None:
                existing_config.creator_id = creator_id
            if creator_username is not None:
                existing_config.creator_username = creator_username
            # Update sharing fields if provided
            if is_public is not None:
                existing_config.is_public = is_public
                logger.info(f"Updated is_public to: {is_public}")
            if public_tags is not None:
                existing_config.public_tags = public_tags
                logger.info(f"Updated public_tags to: {public_tags}")
            if public_at is not None:
                existing_config.public_at = public_at
                logger.info(f"Updated public_at to: {public_at}")
            if metadata is not None:
                existing_config.metadata = metadata
                logger.info(f"Updated metadata to: {metadata}")
            # Recalculate the total number of tools, resources, resource templates, and prompts
            # Use existing_config.vmcp_config instead of the parameter vmcp_config
            existing_vmcp_config = existing_config.vmcp_config or {}
            logger.info(f"Using existing_vmcp_config: {type(existing_vmcp_config)}")
            
            # Safely calculate totals with proper fallbacks
            selected_tools = existing_vmcp_config.get('selected_tools', {}) or {}
            selected_resources = existing_vmcp_config.get('selected_resources', {}) or {}
            selected_resource_templates = existing_vmcp_config.get('selected_resource_templates', {}) or {}
            selected_prompts = existing_vmcp_config.get('selected_prompts', {}) or {}
            
            logger.info(f"Selected tools: {selected_tools}, Selected resources: {selected_resources}")
            
            total_tools = len(existing_config.custom_tools or []) + sum(len(x) for x in selected_tools.values() if isinstance(x, list))
            total_resources = len(existing_config.custom_resources or []) + sum(len(x) for x in selected_resources.values() if isinstance(x, list))
            total_resource_templates = len(existing_config.custom_resource_templates or []) + sum(len(x) for x in selected_resource_templates.values() if isinstance(x, list))
            total_prompts = len(existing_config.custom_prompts or []) + sum(len(x) for x in selected_prompts.values() if isinstance(x, list))
            
            logger.info(f"Calculated totals - Tools: {total_tools}, Resources: {total_resources}, Resource Templates: {total_resource_templates}, Prompts: {total_prompts}")
            
            existing_config.total_tools = total_tools
            existing_config.total_resources = total_resources
            existing_config.total_resource_templates = total_resource_templates
            existing_config.total_prompts = total_prompts

            # Update timestamp
            existing_config.updated_at = datetime.utcnow()

            # Save updated config
            success = self.storage.update_vmcp(existing_config)
            if success:
                logger.info(f"Updated VMCP config: {existing_config.name} (ID: {vmcp_id})")
            else:
                logger.error(f"Failed to update VMCP config: {vmcp_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating VMCP config {vmcp_id}: {e}")
            return False
    
    @trace_method("[VMCPConfigManager]: Delete VMCP")
    def delete_vmcp(self, vmcp_id: str) -> Dict[str, Any]:
        """Delete a vMCP configuration and handle all cleanup"""
        try:
            self.storage.delete_vmcp(vmcp_id)
            return {
                "success": True,
                "message": f"Successfully deleted {vmcp_id}"
            }
            
        except Exception as e:
            logger.error(f"❌ Error deleting vMCP {vmcp_id}: {e}")
            return {
                "success": False,
                "message": f"Failed to delete vMCP: {str(e)}"
            }
    
    def _get_vmcp_type(self, vmcp_config: VMCPConfig) -> str:
        """Determine the type of vMCP for proper cleanup"""
        if vmcp_config.is_public:
            return "public"
        elif vmcp_config.is_wellknown:
            return "wellknown"
        else:
            return "private"

    @trace_method("[VMCPConfigManager]: Add Resource")
    def add_resource(self, vmcp_id: str, resource_data: Dict[str, Any]) -> bool:
        """Add a resource to the vMCP"""
        logger.info(f"Adding resource to vMCP: {vmcp_id} with data: {resource_data}")
        try:
            vmcp_config = self.storage.load_vmcp_config(vmcp_id)
            if not vmcp_config:
                return False
            
            vmcp_config.uploaded_files.append(resource_data)
            vmcp_config.custom_resources.append(resource_data)
            vmcp_config.updated_at = datetime.now()
            logger.info(f"Updated VMCP config: {vmcp_config.custom_resources} (ID: {vmcp_id})")
            return self.storage.update_vmcp(vmcp_config)
        except Exception as e:
            logger.error(f"Error adding resource to vMCP {vmcp_id}: {e}")
            return False

    @trace_method("[VMCPConfigManager]: Update Resource")
    def update_resource(self, vmcp_id: str, resource_data: Dict[str, Any]) -> bool:
        """Add a resource to the vMCP"""
        logger.info(f"Adding resource to vMCP: {vmcp_id} with data: {resource_data}")
        try:
            vmcp_config = self.storage.load_vmcp_config(vmcp_id)
            if not vmcp_config:
                return False
            
            vmcp_config.uploaded_files = [resource for resource in vmcp_config.uploaded_files if resource.get('id') != resource_data.get('id')]
            vmcp_config.custom_resources = [resource for resource in vmcp_config.custom_resources if resource.get('id') != resource_data.get('id')]
            vmcp_config.uploaded_files += [resource_data]
            vmcp_config.custom_resources += [resource_data]
            vmcp_config.updated_at = datetime.now()
            logger.info(f"Updated VMCP config: {vmcp_config.custom_resources} (ID: {vmcp_id})")
            logger.info(f"VMCP config dict: {vmcp_config.to_dict()}")
            return self.storage.update_vmcp(vmcp_config)
        except Exception as e:
            logger.error(f"Error adding resource to vMCP {vmcp_id}: {e}")
            return False

    @trace_method("[VMCPConfigManager]: Delete Resource")
    def delete_resource(self, vmcp_id: str, resource_data: Dict[str, Any]) -> bool:
        """Delete a resource from the vMCP"""
        logger.info(f"Deleting resource from vMCP: {vmcp_id} with data: {resource_data}")
        try:
            vmcp_config = self.storage.load_vmcp_config(vmcp_id)
            if not vmcp_config:
                return False
            
            vmcp_config.uploaded_files = [resource for resource in vmcp_config.uploaded_files if resource.get('id') != resource_data.get('id')]
            vmcp_config.custom_resources = [resource for resource in vmcp_config.custom_resources if resource.get('id') != resource_data.get('id')]
            vmcp_config.updated_at = datetime.now()
            logger.info(f"Updated VMCP config: {vmcp_config.custom_resources} (ID: {vmcp_id})")
            return self.storage.update_vmcp(vmcp_config)
        except Exception as e:
            logger.error(f"Error deleting resource from vMCP {vmcp_id}: {e}")
            return False

    @trace_method("[VMCPConfigManager]: List Tools")
    async def tools_list(self) -> List[Tool]:
        """List all tools from the vMCP's selected servers"""
        if not self.vmcp_id:
            log_to_span(
                "No vmcp_id provided for tools_list",
                operation_type="tools_list",
                operation_id="tools_list_no_vmcp_id",
                result={"success": False, "error": "No vmcp_id provided"},
                level="warning"
            )
            return []
        
        vmcp_config = self.storage.load_vmcp_config(self.vmcp_id)
        if not vmcp_config:
            log_to_span(
                f"VMCP config not found for {self.vmcp_id}",
                operation_type="tools_list",
                operation_id=f"tools_list_{self.vmcp_id}",
                result={"success": False, "error": "VMCP config not found"},
                level="warning"
            )
            return []
        
        vmcp_servers = vmcp_config.vmcp_config.get('selected_servers', [])
        vmcp_selected_tools = vmcp_config.vmcp_config.get('selected_tools', {})
        vmcp_selected_tool_overrides = vmcp_config.vmcp_config.get('selected_tool_overrides', {})
        all_tools = []

        for server in vmcp_servers:
            server_id = server.get('server_id')
            server_name = server.get('name')
            server_tools = self.mcp_config_manager.tools_list(server_id)
            if server_id in vmcp_selected_tools:
                selected_tools = vmcp_selected_tools.get(server_id, [])
                server_tools = [tool for tool in server_tools if tool.name in selected_tools]

            selected_tool_overrides = {}
            if server_id in vmcp_selected_tool_overrides:
                selected_tool_overrides = vmcp_selected_tool_overrides.get(server_id, {})
            
            for tool in server_tools:
                # Create a new Tool object with vMCP-specific naming
                tool_override = selected_tool_overrides.get(tool.name, {})
                _tool_name = tool_override.get("name", tool.name)
                _tool_description = tool_override.get("description", tool.description)

                # Build tool meta including widget information if attached
                tool_meta = {
                    **(tool.meta or {}),
                    "original_name": tool.name,
                    "server": server_name,
                    "vmcp_id": self.vmcp_id,
                    "server_id": server_id
                }
                widget_meta = {}
                # Add widget URI if widget is attached to this tool
                if "widget_id" in tool_override and tool_override["widget_id"]:
                    widget_id = tool_override["widget_id"]


                    # Fetch widget details from db
                    # Load widgets from database
                    from vmcp.storage.database import get_db
                    from vmcp.storage.models import Widget,Blob
                    db = next(get_db())
                    try:
                        widgets = db.query(Widget).filter(
                            Widget.widget_id == widget_id
                        ).all()
                        widget = [widget.to_dict() for widget in widgets]
                        if widget:
                            widget=widget[0]
                        
                        invoking_message="Loading"
                        invoked_message="Loaded"
                        widget_metadata = tool_override["widget_metadata"]
                        if widget_metadata.get("invoking_message"):
                            invoking_message = widget_metadata["invoking_message"]
                        if widget_metadata.get("invoked_message"):
                            invoked_message = widget_metadata["invoked_message"]

                        blob=""
                        # built_files=widget.get("widget_data",{}).get("built_files",None)
                        # if built_files:
                        #     if built_files.get("html"):
                        #         blobs=db.query(Blob).filter(
                        #             Blob.blob_id==built_files.get("html")
                        #         ).all()
                        #         blob = [blob.to_dict() for blob in blobs]
                        #         if blob:
                        #             blob=blob[0]

                        #         blob=blob.get("file_data")
                        uiwidget = UIWidget(
                            identifier=widget.get("name"),
                            title=widget.get("name"),
                            template_uri=widget.get("template_uri"),
                            invoking=invoking_message,
                            invoked=invoked_message,
                            html=blob,
                            response_text=f"Rendered a widget for tool.name",
                        )
                        widget_meta = _tool_meta(uiwidget)
                        logger.info(f"🎨 Loaded {len(widgets)} widgets for vMCP: {self.vmcp_id}")
                    except Exception as e:
                        logger.error(f"Failed to load widgets: {e}")
                        vmcp_config.custom_widgets = []
                    finally:
                        db.close()
                        
                tool_meta.update(widget_meta)
                vmcp_tool = Tool(
                    name=f"{server_name.replace('_','')}_{_tool_name}",
                    description=_tool_description,
                    inputSchema=tool.inputSchema,
                    outputSchema=tool.outputSchema,
                    annotations=tool.annotations,
                    meta=tool_meta
                )
                all_tools.append(vmcp_tool)
        
        for custom_tool in vmcp_config.custom_tools:
            tool_type = custom_tool.get('tool_type', 'prompt')
            
            if tool_type == 'python':
                # For Python tools, parse the function to extract parameters
                tool_input_schema = self._parse_python_function_schema(custom_tool)
            else:
                # For prompt and HTTP tools, use the existing logic
                tool_input_variables = custom_tool.get("variables", [])
                tool_input_schema = {
                    "type": "object",
                    "properties": {
                        var.get("name"): {
                            "type": "string",
                            "description": var.get("description")
                        }
                        for var in tool_input_variables
                    },
                    "required": [var.get("name") for var in tool_input_variables if var.get("required")],
                    "additionalProperties": False,
                    "$schema": "http://json-schema.org/draft-07/schema#"
                }
            
            # Get keywords from custom tool config and append to description
            keywords = custom_tool.get("keywords", [])
            description = custom_tool.get("description", "")
            
            # Append keywords to description if they exist
            if keywords:
                keywords_str = ", ".join(keywords) if isinstance(keywords, list) else str(keywords)
                description = f"{description} [Keywords: {keywords_str}]"

            # logger.info(f"----> Adding custom tool: {custom_tool.get('name')} with keywords: {keywords}")
            title = custom_tool.get('name')

            custom_tool_obj = Tool(
                name=custom_tool.get("name"),
                description=description,
                inputSchema=tool_input_schema,
                title=title,
                meta={
                    "type": "custom",
                    "tool_type": tool_type,
                    "vmcp_id": self.vmcp_id
                }
            )
            all_tools.append(custom_tool_obj)

        if self.user_id:
            # Fire and forget - don't await, just call and let it run
            asyncio.create_task(
                self.log_vmcp_operation(
                    operation_type="tool_list",
                    operation_id=self.vmcp_id,
                    arguments=None,
                    result=all_tools,
                    metadata={"server": "vmcp", "tool": "all_tools", "server_id": self.vmcp_id}
                )
            )

        # Log success to span
        log_to_span(
            f"Successfully listed {len(all_tools)} tools for vMCP {self.vmcp_id}",
            operation_type="tools_list",
            operation_id=f"tools_list_{self.vmcp_id}",
            result={"success": True, "tool_count": len(all_tools), "tools": [tool.name for tool in all_tools[:5]]},  # Log first 5 tool names
            level="info"
        )

        return all_tools

    @trace_method("[VMCPConfigManager]: List Resources")
    async def resources_list(self) -> List[Resource]:
        """List all resources from the vMCP's selected servers"""
        if not self.vmcp_id:
            return []

        logger.info(f"Fetching resources for vMCP: {self.vmcp_id}")
        vmcp_config = self.storage.load_vmcp_config(self.vmcp_id)
        vmcp_name = vmcp_config.name
        if not vmcp_config:
            return []

        # Load widgets from database for this vMCP
        from vmcp.storage.database import get_db
        from vmcp.storage.models import Widget
        db = next(get_db())
        try:
            widgets = db.query(Widget).filter(
                Widget.user_id == self.user_id,
                Widget.vmcp_id == self.vmcp_id
            ).all()
            vmcp_config.custom_widgets = [widget.to_dict() for widget in widgets]
            logger.info(f"🎨 Loaded {len(widgets)} widgets for vMCP: {self.vmcp_id}")
        except Exception as e:
            logger.error(f"Failed to load widgets: {e}")
            vmcp_config.custom_widgets = []
        finally:
            db.close()

        vmcp_servers = vmcp_config.vmcp_config.get('selected_servers', [])
        vmcp_selected_resources = vmcp_config.vmcp_config.get('selected_resources', {})
        logger.info(f"🔍 VMCP Config Manager: Selected resources: {vmcp_selected_resources}")
        all_resources = []

        for server in vmcp_servers:
            server_name = server.get('name')
            server_id = server.get('server_id')
            server_resources = self.mcp_config_manager.resources_list(server_id)
            logger.info(f"🔍 VMCP Config Manager: Server resources: {server_resources}")
            if server_id in vmcp_selected_resources:
                selected_resources = vmcp_selected_resources.get(server_id, [])
                server_resources = [resource for resource in server_resources if str(resource.uri) in selected_resources]
            logger.info(f"🔍 VMCP Config Manager: Server resources: {server_resources}")
            for resource in server_resources:
                # Check if this resource is selected for this vMCP
                vmcp_resource = Resource(
                    name=f"{server_name.replace('_','')}_{resource.name}",
                    uri=f"{server_name.replace('_','')}:{resource.uri}",
                    description=resource.description,
                    mimeType=resource.mimeType,
                    size=resource.size,
                    annotations=resource.annotations,
                    meta={
                        **(resource.meta or {}),
                        "original_name": resource.name,
                        "server": server_name,
                        "vmcp_id": self.vmcp_id,
                        "server_id": server_id
                    }
                )
                all_resources.append(vmcp_resource)

        # Add custom resources
        # For custom resources, we need to create a Resource from every uploaded file
        custom_resources = vmcp_config.custom_resources
        for file in custom_resources:

            # Create a valid URI by using a proper scheme and URL-encoding the filename
            import urllib.parse
            # Use original_filename instead of 'name' field which doesn't exist
            original_filename = file.get('original_filename', 'unknown_file')
            encoded_filename = urllib.parse.quote(original_filename, safe='')
            vmcp_scheme = f"vmcp-{vmcp_name.replace('_', '-')}"

            vmcp_resource = Resource(
                name=original_filename,
                title=original_filename,
                uri=f"custom:{vmcp_scheme}://{encoded_filename}",
                mimeType=file.get('content_type'),  # Use content_type instead of mime_type
                size=file.get('size'),
                meta={
                    "original_name": original_filename,
                    "server": "vmcp",
                    "vmcp_id": self.vmcp_id
                }
            )
            all_resources.append(vmcp_resource)

        # Add widget resources
        custom_widgets = vmcp_config.custom_widgets or []
        for widget in custom_widgets:
            # Only include built widgets
            if widget.get('build_status') == 'built':
                widget_id = widget.get('id')
                widget_name = widget.get('name', 'Unnamed Widget')
                widget_description = widget.get('description', '')
                template_uri = widget.get('template_uri', f'ui://widget/{widget_id}')

                # Widget serving URLs (use base_url from settings)
                widget_js_uri = f"{settings.base_url}/api/widgets/{widget_id}/serve/js"
                widget_css_uri = f"{settings.base_url}/api/widgets/{widget_id}/serve/css"

                vmcp_resource = Resource(
                    name=widget_name,
                    title=widget_name,
                    uri=template_uri,  # Use template_uri instead of widget_id
                    description=widget_description,
                    mimeType="text/html+skybridge",
                    meta={
                        "original_name": widget_name,
                        "server": "vmcp",
                        "vmcp_id": self.vmcp_id,
                        "widget_id": widget_id,
                        "widget_js_uri": widget_js_uri,
                        "widget_css_uri": widget_css_uri,
                        "template_uri": template_uri,
                        "resource_type": "widget"
                    }
                )
                all_resources.append(vmcp_resource)

        if self.user_id:
            # Fire and forget - don't await, just call and let it run
            asyncio.create_task(
                self.log_vmcp_operation(
                    operation_type="resource_list",
                    operation_id=self.vmcp_id,
                    arguments=None,
                    result=all_resources,
                    metadata={"server": "vmcp", "resource": "all_resources", "server_id": self.vmcp_id}
                )
            )

        return all_resources
    
    @trace_method("[VMCPConfigManager]: List Resource Templates")
    async def resource_templates_list(self) -> List[ResourceTemplate]:
        """List all resource templates from the vMCP's selected servers"""
        if not self.vmcp_id:
            return []
        
        vmcp_config = self.storage.load_vmcp_config(self.vmcp_id)
        if not vmcp_config:
            return []
        
        vmcp_servers = vmcp_config.vmcp_config.get('selected_servers', [])
        vmcp_selected_resource_templates = vmcp_config.vmcp_config.get('selected_resource_templates', {})
        all_resource_templates = []

        for server in vmcp_servers:
            server_name = server.get('name')
            server_id = server.get('server_id')
            server_resource_templates = self.mcp_config_manager.resource_templates_list(server_id)
            if server_id in vmcp_selected_resource_templates:
                selected_resource_templates = vmcp_selected_resource_templates.get(server_id, [])
                server_resource_templates = [template for template in server_resource_templates if template.name in selected_resource_templates]
            
            for template in server_resource_templates:
                # Create a new ResourceTemplate object with vMCP-specific naming
                vmcp_template = ResourceTemplate(
                    name=f"{server_name.replace('_','')}_{template.name}",
                    uriTemplate=template.uriTemplate,
                    description=template.description,
                    mimeType=template.mimeType,
                    annotations=template.annotations,
                    meta={
                        **(template.meta or {}),
                        "original_name": template.name,
                        "server": server_name,
                        "vmcp_id": self.vmcp_id,
                        "server_id": server_id
                    }
                )
                all_resource_templates.append(vmcp_template)

        if self.user_id:
            # Fire and forget - don't await, just call and let it run
            asyncio.create_task(
                self.log_vmcp_operation(
                    operation_type="resource_template_list",
                    operation_id=self.vmcp_id,
                    arguments=None,
                    result=all_resource_templates,
                    metadata={"server": "vmcp", "resource_template": "all_resource_templates", "server_id": self.vmcp_id}
                )
            )

        return all_resource_templates
    
    @trace_method("[VMCPConfigManager]: List Prompts")
    async def prompts_list(self) -> List[Prompt]:
        """List all prompts from the vMCP's selected servers and custom prompts"""
        if not self.vmcp_id:
            # Return default system prompts even without vMCP
            return get_all_default_prompts()
        
        vmcp_config = self.storage.load_vmcp_config(self.vmcp_id)
        if not vmcp_config:
            return []
        
        vmcp_servers = vmcp_config.vmcp_config.get('selected_servers', [])
        vmcp_selected_prompts = vmcp_config.vmcp_config.get('selected_prompts', {})
        all_prompts = []
        
        logger.info(f"Collecting prompts from {len(vmcp_servers)} servers...")
        
        # Add prompts from attached servers
        for server in vmcp_servers:
            server_name = server.get('name')
            server_id = server.get('server_id')
            server_prompts = self.mcp_config_manager.prompts_list(server_id)
            if server_id in vmcp_selected_prompts:
                selected_prompts = vmcp_selected_prompts.get(server_id, [])
                server_prompts = [prompt for prompt in server_prompts if prompt.name in selected_prompts]
            logger.info(f"Collected {len(server_prompts)} prompts from {server_name}...")
            
            for prompt in server_prompts:
                # Create a new Prompt object with vMCP-specific naming
                vmcp_prompt = Prompt(
                    name=f"{server_name.replace('_','')}_{prompt.name}",
                    title=f"#{server_name.replace('_','')}_{prompt.name}",
                    description=prompt.description,
                    arguments=prompt.arguments,
                    meta={
                        **(prompt.meta or {}),
                        "original_name": prompt.name,
                        "server": server_name,
                        "vmcp_id": self.vmcp_id,
                        "server_id": server_id
                    }
                )
                all_prompts.append(vmcp_prompt)

        # Add custom prompts from vMCP config
        for custom_prompt in vmcp_config.custom_prompts:
            # Convert custom prompt variables to PromptArgument objects
            prompt_arguments = []
            
            # Add variables from custom prompt
            if custom_prompt.get('variables'):
                for var in custom_prompt['variables']:
                    prompt_arg = PromptArgument(
                        name=var.get('name'),
                        description=var.get('description', f"Variable: {var.get('name')}"),
                        required=var.get('required', False)
                    )
                    prompt_arguments.append(prompt_arg)
            
            # Add environment variables from custom prompt
            # if custom_prompt.get('environment_variables'):
            #     for env_var in custom_prompt['environment_variables']:
            #         env_name = env_var.get('name')
            #         if env_name:
            #             prompt_arg = PromptArgument(
            #                 name=env_name,
            #                 description=env_var.get('description', f"Environment variable: {env_name}"),
            #                 required=env_var.get('required', False)
            #             )
            #             prompt_arguments.append(prompt_arg)
            
            # Create a new Prompt object for custom prompt
            custom_prompt_obj = Prompt(
                name=f"{custom_prompt.get('name')}",
                title=f"#{custom_prompt.get('name')}",

                #name=custom_prompt.get("name"),
                description=custom_prompt.get("description", ""),
                arguments=prompt_arguments,
                meta={
                    "type": "custom",
                    "vmcp_id": self.vmcp_id,
                    "custom_prompt_id": custom_prompt.get("id")
                }
            )
            all_prompts.append(custom_prompt_obj)

        # Add custom tools as prompts too
        for custom_tool in vmcp_config.custom_tools:
            # Convert custom prompt variables to PromptArgument objects
            prompt_arguments = []
            
            # Add variables from custom tool
            if custom_tool.get('variables'):
                for var in custom_tool['variables']:
                    prompt_arg = PromptArgument(
                        name=var.get('name'),
                        description=var.get('description', f"Variable: {var.get('name')}"),
                        required=var.get('required', False)
                    )
                    prompt_arguments.append(prompt_arg)
            
            # Create a new Prompt object for custom tool
            custom_prompt_obj = Prompt(
                name=f"{custom_tool.get('name')}",
                title=f"#{custom_tool.get('name')}",
                #name=custom_tool.get("name"),
                description=custom_tool.get("description", ""),
                arguments=prompt_arguments,
                meta={
                    "type": "custom",
                    "vmcp_id": self.vmcp_id,
                    "custom_tool_id": custom_tool.get("id")
                }
            )
            all_prompts.append(custom_prompt_obj)

        # Add default system prompts
        default_prompts = get_all_default_prompts(self.vmcp_id)
        all_prompts.extend(default_prompts)

        if self.user_id:
            # Fire and forget - don't await, just call and let it run
            asyncio.create_task(
                self.log_vmcp_operation(
                    operation_type="prompt_list",
                    operation_id=self.vmcp_id,
                    arguments=None,
                    result=all_prompts,
                    metadata={"server": "vmcp", "prompt": "all_prompts", "server_id": self.vmcp_id}
                )
            )

        return all_prompts

    @trace_method("[VMCPConfigManager]: Call Tool")
    async def call_tool(self, vmcp_tool_call_request: VMCPToolCallRequest, 
                        connect_if_needed: bool = True,
                        return_metadata: bool = False) -> Dict[str, Any]:        
        logger.info(f"🔍 VMCP Config Manager: call_tool called for '{vmcp_tool_call_request.tool_name}'")
        add_event(f"🔍 VMCP Config Manager: call_tool called for '{vmcp_tool_call_request.tool_name}'",metadata={"server": "vmcp", "tool": vmcp_tool_call_request.tool_name, "server_id": self.vmcp_id})

        # OSS - no analytics tracking

        vmcp_config=self.storage.load_vmcp_config(self.vmcp_id)
        if not vmcp_config:
            raise ValueError(f"vMCP config not found: {self.vmcp_id}")
        
        custom_tools = vmcp_config.custom_tools
        for tool in custom_tools:
            if tool.get('name') == vmcp_tool_call_request.tool_name:
                result = await self.call_custom_tool(vmcp_tool_call_request.tool_name, vmcp_tool_call_request.arguments)
                if return_metadata:
                    return result,{"server": "custom_tool", "tool": vmcp_tool_call_request.tool_name}
                else:
                    return result

        tool_server_name=vmcp_tool_call_request.tool_name.split('_')[0]
        tool_original_name="_".join(vmcp_tool_call_request.tool_name.split('_')[1:])
        
        logger.info(f"🔍 VMCP Config Manager: Parsed tool name - server: '{tool_server_name}', original: '{tool_original_name}'")
        
        vmcp_servers = vmcp_config.vmcp_config.get('selected_servers', [])
        vmcp_selected_tool_overrides = vmcp_config.vmcp_config.get('selected_tool_overrides', {})
        logger.info(f"🔍 VMCP Config Manager: Found {len(vmcp_servers)} servers in vMCP config")
        logger.info(f"🔍 VMCP Config Manager: Server details: {[(s.get('name'), s.get('name', '').replace('_', '')) for s in vmcp_servers]}")
        
        for server in vmcp_servers:
            server_name = server.get('name')
            server_id = server.get('server_id')
            server_name_clean = server_name.replace('_','')
            
            logger.info(f"🔍 VMCP Config Manager: Checking server '{server_name}' (clean: '{server_name_clean}') against '{tool_server_name}'")
            
            if server_name_clean == tool_server_name:
                logger.info(f"✅ VMCP Config Manager: Found matching server '{server_name}' for tool '{vmcp_tool_call_request.tool_name}'")
                logger.info(f"🔍 VMCP Config Manager: Calling tool '{tool_original_name}' on server '{server_name}'")
                logger.info(f"🔍 VMCP Config Manager: Tool overrides: {vmcp_selected_tool_overrides.get(server_id, {})}")

                # Initialize widget_meta to None for all code paths
                widget_meta = None

                if vmcp_selected_tool_overrides.get(server_id, {}):
                    server_tool_overrides = vmcp_selected_tool_overrides.get(server_id, {})
                    for _original_tool in server_tool_overrides:
                        if server_tool_overrides.get(_original_tool).get("name") == tool_original_name:
                            tool_original_name = _original_tool
                            break

                    tool_override_data=server_tool_overrides[tool_original_name]
                    if "widget_id" in tool_override_data and tool_override_data["widget_id"]:
                        logger.info(f"Widget tool override {tool_override_data}")
                        widget_id = tool_override_data["widget_id"]

                        from vmcp.storage.database import get_db
                        from vmcp.storage.models import Widget,Blob
                        db = next(get_db())
                        try:
                            widgets = db.query(Widget).filter(
                                Widget.widget_id == widget_id
                            ).all()
                            widget = [widget.to_dict() for widget in widgets]
                            if widget:
                                widget=widget[0]
                            
                            invoking_message="Loading"
                            invoked_message="Loaded"
                            widget_metadata = tool_override_data["widget_metadata"]
                            if widget_metadata.get("invoking_message"):
                                invoking_message = widget_metadata["invoking_message"]
                            if widget_metadata.get("invoked_message"):
                                invoked_message = widget_metadata["invoked_message"]

                            blob=""
                            built_files=widget.get("built_files",None)
                            logger.info(f"Built files {built_files} {widget}")
                            if built_files:
                                if built_files.get("html"):
                                    logger.info(f"Fetch {built_files.get('html')}")
                                    blob_obj=db.query(Blob).filter(
                                        Blob.blob_id==built_files.get("html")
                                    ).first()

                                    if blob_obj and blob_obj.file_data:
                                        # file_data is stored as bytes (BYTEA), decode to string
                                        if isinstance(blob_obj.file_data, bytes):
                                            blob = blob_obj.file_data.decode('utf-8')
                                        else:
                                            blob = str(blob_obj.file_data)
                                        logger.info(f"✅ Fetched blob HTML data, length: {len(blob)}")

                            # Ensure blob is never None
                            if not blob:
                                blob = ""
                                logger.warning("⚠️ No HTML data found for widget, using empty string")

                            uiwidget = UIWidget(
                                identifier=widget.get("name"),
                                title=widget.get("name"),
                                template_uri=widget.get("template_uri"),
                                invoking=invoking_message,
                                invoked=invoked_message,
                                html=blob,
                                response_text=f"Rendered a widget for tool.name",
                            )
                            widget_resource = _embedded_widget_resource(uiwidget)
                            widget_meta: Dict[str, Any] = {
                                "openai.com/widget": widget_resource.model_dump(mode="json"),
                                "openai/outputTemplate": uiwidget.template_uri,
                                "openai/toolInvocation/invoking": uiwidget.invoking,
                                "openai/toolInvocation/invoked": uiwidget.invoked,
                                "openai/widgetAccessible": True,
                                "openai/resultCanProduceWidget": True,
                            }
                            logger.info(f"🎨 Loaded {len(widgets)} widgets for vMCP: {self.vmcp_id}")
                        except Exception as e:
                            logger.error(f"Failed to load widgets: {e}")
                            vmcp_config.custom_widgets = []
                        finally:
                            db.close()      
                    else:
                        logger.info(f"🔍 VMCP Config Manager: No tool overrides found for server '{server_name}'")

                result = await self.mcp_client_manager.call_tool(
                    server_id,
                    tool_original_name, vmcp_tool_call_request.arguments)

                logger.info(f"✅ VMCP Config Manager: Tool call successful, result type: {type(result)}")

                # Add background task to log the tool call
                logger.info(f"[BACKGROUND TASK LOGGING] Adding background task to log tool call for vMCP {self.vmcp_id}")
                if self.user_id:
                    # Fire and forget - don't await, just call and let it run
                    asyncio.create_task(
                        self.log_vmcp_operation(
                            operation_type="tool_call",
                            operation_id=vmcp_tool_call_request.tool_name,
                            arguments=vmcp_tool_call_request.arguments,
                            result=result,
                            metadata={"server": server_name, "tool": tool_original_name, "server_id": server_id}
                        )
                    )

                if widget_meta:
                    result = CallToolResult(
                        content=result.content,
                        structuredContent=result.structuredContent,
                        _meta=widget_meta,
                    )
                if return_metadata:
                    return result,{"server": server_name, "tool": tool_original_name, "server_id": server_id}
                else:
                    return result
        
        # If we get here, the tool was not found in any server
        logger.error(f"❌ VMCP Config Manager: Tool '{vmcp_tool_call_request.tool_name}' not found in any server")
        logger.error(f"❌ VMCP Config Manager: Searched servers: {[s.get('name') for s in vmcp_servers]}")
        raise ValueError(f"Tool {vmcp_tool_call_request.tool_name} not found in vMCP {self.vmcp_id}")
    
    @trace_method("[VMCPConfigManager]: Get Resource")
    async def get_resource(self, resource_id: str, connect_if_needed: bool = True):
        """Get a specific resource"""
        # Convert resource_id to string if it's a Pydantic AnyUrl or other object
        resource_id_str = str(resource_id)
        logger.info(f"🔍 VMCP Config Manager: Searching for resource '{resource_id_str}' in vMCP '{self.vmcp_id}'")

        
        vmcp_config=self.storage.load_vmcp_config(self.vmcp_id)
        if not vmcp_config:
            raise ValueError(f"vMCP config not found: {self.vmcp_id}")
        
        custom_resources = vmcp_config.custom_resources
        
        # Check if this is a custom resource URI (starts with "custom:")
        if resource_id_str.startswith('custom:'):
            logger.info(f"🔍 VMCP Config Manager: Detected custom resource URI: '{resource_id_str}'")
            
            # Parse the custom URI to extract the filename
            # Format: custom:vmcp-scheme://encoded_filename
            try:
                uri_parts = resource_id_str.split('://', 1)
                if len(uri_parts) == 2:
                    scheme_part = uri_parts[0]  # custom:vmcp-scheme
                    encoded_filename = uri_parts[1]  # encoded_filename
                    
                    # Decode the filename
                    import urllib.parse
                    original_filename = urllib.parse.unquote(encoded_filename)
                    
                    logger.info(f"🔍 VMCP Config Manager: Decoded filename: '{original_filename}'")
                    
                    # Find the custom resource by original_filename
                    for resource in custom_resources:
                        logger.info(f"🔍 VMCP Config Manager: Checking custom resource: '{resource.get('original_filename')}' against '{original_filename}'")
                        if resource.get('resource_name') == original_filename:
                            logger.info(f"✅ VMCP Config Manager: Found matching custom resource for '{original_filename}'")
                            result = await self.call_custom_resource(resource_id_str)
                            return result
                    
                    logger.warning(f"⚠️ VMCP Config Manager: Custom resource with filename '{original_filename}' not found in custom_resources")
                else:
                    logger.warning(f"⚠️ VMCP Config Manager: Invalid custom resource URI format: '{resource_id_str}'")
            except Exception as e:
                logger.error(f"❌ VMCP Config Manager: Error parsing custom resource URI '{resource_id_str}': {e}")
        
        # Legacy check for resource_name matching (for backward compatibility)
        for resource in custom_resources:
            logger.info(f"🔍 VMCP Config Manager: Checking custom resource resource_name: '{resource.get('resource_name')}' against '{resource_id_str}'")
            if resource.get('resource_name') == resource_id_str:
                result = await self.call_custom_resource(resource_id_str)
                return result

        # Check if this is a widget resource URI (ui://widget/...)
        if resource_id_str.startswith('ui://widget/'):
            logger.info(f"🔍 VMCP Config Manager: Detected widget resource URI: '{resource_id_str}'")

            # Load widgets from database and match by template_uri
            from vmcp.storage.database import get_db
            from vmcp.storage.models import Widget
            db = next(get_db())
            try:
                widget = db.query(Widget).filter(
                    Widget.user_id == self.user_id,
                    Widget.vmcp_id == self.vmcp_id,
                    Widget.template_uri == resource_id_str
                ).first()

                if widget and widget.build_status == 'built':
                    logger.info(f"✅ VMCP Config Manager: Found widget '{widget.name}' with template_uri '{resource_id_str}'")

                    widget_data = widget.widget_data or {}

                    # Get the built HTML from blob storage
                    widget_html = ""
                    built_files = widget_data.get('built_files', {})
                    html_blob_id = built_files.get('html')

                    if html_blob_id:
                        logger.info(f"Fetching HTML blob: {html_blob_id}")
                        from vmcp.storage.models import Blob
                        html_blob = db.query(Blob).filter(Blob.blob_id == html_blob_id).first()

                        if html_blob and html_blob.file_data:
                            # Decode bytes to string
                            if isinstance(html_blob.file_data, bytes):
                                widget_html = html_blob.file_data.decode('utf-8')
                            else:
                                widget_html = str(html_blob.file_data)
                            logger.info(f"✅ Fetched HTML blob, size: {len(widget_html)} bytes")
                        else:
                            logger.warning("⚠️ HTML blob not found, falling back to reference HTML")

                    # Fallback: create reference HTML if no built HTML exists
                    if not widget_html:
                        css_url = f"{settings.base_url}/api/widgets/{widget.widget_id}/serve/css"
                        js_url = f"{settings.base_url}/api/widgets/{widget.widget_id}/serve/js"
                        root_id = widget_data.get('root_id', f'{widget.name.lower().replace(" ", "-")}-root')
                        widget_html = f'<link rel="stylesheet" href="{css_url}">\n<div id="{root_id}"></div>\n<script type="module" src="{js_url}"></script>'
                        logger.info("Using fallback reference HTML")

                    # Return widget resource in MCP format following OpenAI Apps SDK spec
                    from mcp.types import TextResourceContents, ReadResourceResult

                    # Build metadata following OpenAI format
                    invoking_msg = widget_data.get('invoking_message', f'Loading {widget.name}...')
                    invoked_msg = widget_data.get('invoked_message', f'{widget.name} ready')

                    content = TextResourceContents(
                        uri=resource_id_str,
                        mimeType="text/html+skybridge",
                        text=widget_html,
                        _meta={
                            "openai/outputTemplate": resource_id_str,
                            "openai/toolInvocation/invoking": invoking_msg,
                            "openai/toolInvocation/invoked": invoked_msg,
                            "openai/widgetAccessible": True,
                            "openai/resultCanProduceWidget": True,
                            "annotations": {
                                "destructiveHint": False,
                                "openWorldHint": False,
                                "readOnlyHint": True
                            }
                        }
                    )
                    return ReadResourceResult(contents=[content])
                else:
                    logger.error(f"❌ VMCP Config Manager: Widget with template_uri '{resource_id_str}' not found or not built")
            except Exception as e:
                logger.error(f"❌ VMCP Config Manager: Error loading widget with template_uri '{resource_id_str}': {e}")
            finally:
                db.close()

        resource_server_name=resource_id_str.split(':')[0]
        resource_original_name=":".join(resource_id_str.split(':')[1:])
        
        logger.info(f"🔍 VMCP Config Manager: Parsed tool name - server: '{resource_server_name}', original: '{resource_original_name}'")
        
        vmcp_servers = vmcp_config.vmcp_config.get('selected_servers', [])
        logger.info(f"🔍 VMCP Config Manager: Found {len(vmcp_servers)} servers in vMCP config")
        logger.info(f"🔍 VMCP Config Manager: Server details: {[(s.get('name'), s.get('name', '').replace('_', '')) for s in vmcp_servers]}")
        
        for server in vmcp_servers:
            server_name = server.get('name')
            server_id = server.get('server_id')
            server_name_clean = server_name.replace('_','')
            
            logger.info(f"🔍 VMCP Config Manager: Checking server '{server_name}' (clean: '{server_name_clean}') against '{resource_server_name}'")
            
            if server_name_clean.lower() == resource_server_name.lower():
                logger.info(f"✅ VMCP Config Manager: Found matching server '{server_name}' for resource '{resource_id_str}'")
                logger.info(f"🔍 VMCP Config Manager: Calling resource '{resource_original_name}' on server '{server_name}'")
                
                result = await self.mcp_client_manager.read_resource(
                    server_id, 
                    resource_original_name)
                
                logger.info(f"✅ VMCP Config Manager: Resource read successful, result type: {type(result)}")
                logger.info(f"[BACKGROUND TASK LOGGING] Adding background task to log tool call for vMCP {self.vmcp_id}")
                if self.user_id:
                    # Fire and forget - don't await, just call and let it run
                    asyncio.create_task(
                        self.log_vmcp_operation(
                            operation_type="resource_get",
                            operation_id=resource_id_str,
                            arguments=resource_original_name,
                            result=result,
                            metadata={"server": server_name, "resource": resource_original_name, "server_id": server_id}
                        )
                    )
                
                # if isinstance(result, ReadResourceResult):
                #     class ReadResourceResultCustom(Result):
                #         """The server's response to a resources/read request from the client."""
                #         content: list[TextResourceContents | BlobResourceContents]

                #     return ReadResourceResultCustom(content=result.contents)
                # else:
                return result
                
        
        logger.error(f"❌ VMCP Config Manager: Resource '{resource_id_str}' not found in any server")
        logger.error(f"❌ VMCP Config Manager: Searched servers: {[s.get('name') for s in vmcp_servers]}")
        raise ValueError(f"Resource {resource_id_str} not found in vMCP {self.vmcp_id}")

    @trace_method("[VMCPConfigManager]: Call Custom Resource")
    async def call_custom_resource(self, resource_id: str, connect_if_needed: bool = True):
        """Call a custom resource"""
        logger.info(f"🔍 VMCP Config Manager: Calling custom resource '{resource_id}'")
        vmcp_config=self.storage.load_vmcp_config(self.vmcp_id)
        if not vmcp_config:
            raise ValueError(f"vMCP config not found: {self.vmcp_id}")

        # Find the custom resource
        custom_resource = None
        
        # Check if this is a custom resource URI (starts with "custom:")
        if resource_id.startswith('custom:'):
            logger.info(f"🔍 VMCP Config Manager: Detected custom resource URI in call_custom_resource: '{resource_id}'")
            
            # Parse the custom URI to extract the filename
            # Format: custom:vmcp-scheme://encoded_filename
            try:
                uri_parts = resource_id.split('://', 1)
                if len(uri_parts) == 2:
                    scheme_part = uri_parts[0]  # custom:vmcp-scheme
                    encoded_filename = uri_parts[1]  # encoded_filename
                    
                    # Decode the filename
                    import urllib.parse
                    original_filename = urllib.parse.unquote(encoded_filename)
                    
                    logger.info(f"🔍 VMCP Config Manager: Decoded filename in call_custom_resource: '{original_filename}'")
                    
                    # Find the custom resource by original_filename
                    for resource in vmcp_config.custom_resources:
                        logger.info(f"🔍 VMCP Config Manager: Checking custom resource in call_custom_resource: '{resource.get('original_filename')}' against '{original_filename}'")
                        if resource.get('original_filename') == original_filename:
                            logger.info(f"✅ VMCP Config Manager: Found matching custom resource in call_custom_resource for '{original_filename}'")
                            custom_resource = resource
                            break
                    
                    if not custom_resource:
                        logger.warning(f"⚠️ VMCP Config Manager: Custom resource with filename '{original_filename}' not found in custom_resources in call_custom_resource")
                else:
                    logger.warning(f"⚠️ VMCP Config Manager: Invalid custom resource URI format in call_custom_resource: '{resource_id}'")
            except Exception as e:
                logger.error(f"❌ VMCP Config Manager: Error parsing custom resource URI in call_custom_resource '{resource_id}': {e}")
        
        # Legacy check for resource_name matching (for backward compatibility)
        if not custom_resource:
            for resource in vmcp_config.custom_resources:
                logger.info(f"🔍 VMCP Config Manager: Checking custom resource resource_name in call_custom_resource: '{resource.get('resource_name')}' against '{resource_id}'")
                if resource.get('resource_name') == resource_id:
                    custom_resource = resource
                    break

        if not custom_resource:
            raise ValueError(f"Custom resource '{resource_id}' not found in vMCP {self.vmcp_id}")
        
        # Direct database fetch for resource content
        from vmcp.storage.models import Blob
        from vmcp.storage.database import get_db
        
        db = next(get_db())
        try:
            if self.vmcp_id and self.vmcp_id.startswith("@"):
                blob = db.query(Blob).filter(
                    Blob.blob_id == custom_resource.get('id')
                ).first()
            else:
                blob = db.query(Blob).filter(
                    Blob.blob_id == custom_resource.get('id'),
                    Blob.user_id == self.user_id,
                    Blob.vmcp_id == self.vmcp_id
                ).first()
            
            if not blob:
                raise ValueError(f"Resource blob '{custom_resource.get('id')}' not found in database")
            
            # Handle content based on content type
            content_type = custom_resource.get('content_type') or blob.content_type
            
            # For text files, decode the binary data to string
            if content_type and content_type.startswith('text/'):
                try:
                    if isinstance(blob.file_data, bytes):
                        resource_content = blob.file_data.decode('utf-8')
                    else:
                        resource_content = str(blob.file_data)
                except UnicodeDecodeError:
                    # If UTF-8 decoding fails, fall back to base64 encoding
                    import base64
                    if isinstance(blob.file_data, bytes):
                        resource_content = base64.b64encode(blob.file_data).decode('ascii')
                    else:
                        resource_content = str(blob.file_data)
            else:
                # For binary files, return as-is or base64 encode if needed
                resource_content = blob.file_data
            
            contents=[]
            match resource_content:
                case str() as resource_content:
                    contents=[TextResourceContents(
                        uri=resource_id,
                        text=resource_content,
                        mimeType=content_type or "text/plain",
                    )]
                case bytes() as resource_content:
                    import base64
                    contents=[BlobResourceContents(
                        uri=resource_id,
                        blob=resource_content,
                        mimeType=content_type or "application/octet-stream",
                    )]
            
            # contents= [ReadResourceContents(content=resource_content, 
            #                             mime_type=content_type)]
            return ReadResourceResult(contents = contents)
        finally:
            db.close()
  
    @trace_method("[VMCPConfigManager]: Get Prompt")
    async def get_prompt(self, prompt_id: str, 
                         arguments: Optional[Dict[str, Any]] = None,
                         connect_if_needed: bool = True) -> Dict[str, Any]:
        """Get a specific prompt"""
        logger.info(f"🔍 VMCP Config Manager: Searching for prompt '{prompt_id}' in vMCP '{self.vmcp_id}'")
        
        # Check for default system prompts first
        original_prompt_id = prompt_id
        prompt_id = prompt_id[1:] if prompt_id.startswith("#") else prompt_id
        
        # Handle default prompts (these work without vMCP)
        default_prompt_names = ["vmcp_feedback"]  # Add more as needed
        if prompt_id in default_prompt_names:
            logger.info(f"✅ VMCP Config Manager: Found default prompt '{prompt_id}'")
            return await handle_default_prompt(original_prompt_id, self.user_id, self.vmcp_id, arguments)
        
        if not self.vmcp_id:
            raise ValueError("No vMCP ID specified")
        
        vmcp_config = self.storage.load_vmcp_config(self.vmcp_id)
        if not vmcp_config:
            raise ValueError(f"vMCP config not found: {self.vmcp_id}")
        
        vmcp_servers = vmcp_config.vmcp_config.get('selected_servers', [])
        logger.info(f"🔍 VMCP Config Manager: Found {len(vmcp_servers)} servers in vMCP config")
        vmcp_selected_prompts = vmcp_config.vmcp_config.get('selected_prompts', {})
        # Try to find the prompt in the servers
        for server in vmcp_servers:
            server_name = server.get('name')
            server_id = server.get('server_id')
            server_prompts = vmcp_selected_prompts.get(server_id, [])
            
            logger.info(f"🔍 VMCP Config Manager: Checking server '{server_name}' with {len(server_prompts)} prompts: {server_prompts}")
            
            # Check if this is a prefixed prompt name (server_promptname)
            expected_prefix = f"{server_name.replace('_','')}_"
            logger.info(f"🔍 VMCP Config Manager: Expected prefix for server '{server_name}': '{expected_prefix}'")
            
            if prompt_id.startswith(expected_prefix):
                # Extract the original prompt name by removing the server prefix
                original_prompt_name = prompt_id[len(expected_prefix):]
                logger.info(f"🔍 VMCP Config Manager: Detected prefixed prompt. Original name: '{original_prompt_name}'")
                
                # Check if the original prompt name exists in the server's prompts
                if original_prompt_name in server_prompts:
                    logger.info(f"✅ VMCP Config Manager: Found prompt '{original_prompt_name}' in server '{server_name}'")
                    try:
                        result = await self.mcp_client_manager.get_prompt(server_id, original_prompt_name, arguments, connect_if_needed=connect_if_needed)
                        logger.info(f"[BACKGROUND TASK LOGGING] Adding background task to log tool call for vMCP {self.vmcp_id}")
                        if self.user_id:
                            # Fire and forget - don't await, just call and let it run
                            asyncio.create_task(
                                self.log_vmcp_operation(
                                    operation_type="prompt_get",
                                    operation_id=original_prompt_name,
                                    arguments=arguments,
                                    result=result,
                                    metadata={"server": server_name, "prompt": original_prompt_name, "server_id": server_id}
                                )
                            )
                        
                        return result
                    except Exception as e:
                        logger.error(f"❌ VMCP Config Manager: Failed to get prompt {original_prompt_name} from server {server_name}: {e}")
                        logger.error(f"❌ VMCP Config Manager: Server ID: {server_id}")
                        continue
                else:
                    logger.warning(f"⚠️ VMCP Config Manager: Original prompt name '{original_prompt_name}' not found in server '{server_name}' prompts list")
            else:
                logger.info(f"🔍 VMCP Config Manager: Prompt '{prompt_id}' does not start with expected prefix '{expected_prefix}' for server '{server_name}'")
        
        # Check custom prompts
        logger.info(f"🔍 VMCP Config Manager: Checking {len(vmcp_config.custom_prompts)} custom prompts")
        for prompt in vmcp_config.custom_prompts:
            custom_prompt_name = prompt.get('name')
            logger.info(f"🔍 VMCP Config Manager: Checking custom prompt: '{custom_prompt_name}'")
            if custom_prompt_name == prompt_id:
                logger.info(f"✅ VMCP Config Manager: Found custom prompt '{prompt_id}'")
                result = await self.get_custom_prompt(prompt_id, arguments)
                logger.info(f"[BACKGROUND TASK LOGGING] Adding background task to log tool call for vMCP {self.vmcp_id}")
                if self.user_id:
                    # Fire and forget - don't await, just call and let it run
                    asyncio.create_task(
                        self.log_vmcp_operation(
                            operation_type="prompt_get",
                            operation_id=prompt_id,
                            arguments=arguments,
                            result=result,
                            metadata={"server": "custom_prompt", "prompt": prompt_id, "server_id": "custom_prompt"}
                        )
                    )
                
                return result
            
        for tool in vmcp_config.custom_tools:
            custom_tool_name = tool.get('name')
            logger.info(f"🔍 VMCP Config Manager: Checking custom tool: '{custom_tool_name}'")
            if custom_tool_name == prompt_id:
                logger.info(f"✅ VMCP Config Manager: Found custom tool '{prompt_id}'")
                result = await self.call_custom_tool(prompt_id, arguments, tool_as_prompt=True)
                logger.info(f"[BACKGROUND TASK LOGGING] Adding background task to log tool call for vMCP {self.vmcp_id}")
                if self.user_id:
                    # Fire and forget - don't await, just call and let it run
                    asyncio.create_task(
                        self.log_vmcp_operation(
                            operation_type="prompt_get",
                            operation_id=prompt_id,
                            arguments=arguments,
                            result=result,
                            metadata={"server": "custom_tool", "tool": prompt_id, "server_id": "custom_tool"}
                        )
                    )
                return result
        
        logger.error(f"❌ VMCP Config Manager: Prompt '{prompt_id}' not found in vMCP '{self.vmcp_id}'")
        logger.error(f"❌ VMCP Config Manager: Searched through {len(vmcp_servers)} servers and {len(vmcp_config.custom_prompts)} custom prompts")
        raise ValueError(f"Prompt {prompt_id} not found in vMCP {self.vmcp_id}")

    @trace_method("[VMCPConfigManager]: Get System Prompt")
    async def get_system_prompt(self, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get a custom prompt with variable substitution and tool call execution"""
        
        vmcp_config = self.storage.load_vmcp_config(self.vmcp_id)
        if not vmcp_config:
            raise ValueError(f"vMCP config not found: {self.vmcp_id}")
        
        system_prompt = vmcp_config.system_prompt
        
        if not system_prompt:
            raise ValueError(f"System prompt not found in vMCP {self.vmcp_id}")
        
        # Get the prompt text
        prompt_text = system_prompt.get('text', '')

        # Read the corresponding environment variable file for the vmcp_id from storage if available
        environment_variables = self.storage.load_vmcp_environment(self.vmcp_id)

        # We also need to save the environment variables which are also part of argument
        # Check for each environment variable if the  key is present in the arguments
        # We need to store these values in the vmcp environment file so that future  use we can use them
        for env_var in environment_variables:
            if env_var in arguments:
                environment_variables[env_var] = arguments[env_var]
        self.storage.save_vmcp_environment(self.vmcp_id, environment_variables)

        # Parse and substitute using regex patterns
        prompt_text,_resource_content = await self._parse_vmcp_text(
            prompt_text,
            system_prompt,
            arguments,
            environment_variables,
            is_prompt=True
        )

        # Create the TextContent
        text_content = TextContent(
            type="text",
            text=prompt_text,
            annotations=None,
            meta=None
        )
        
        # Create the PromptMessage
        prompt_message = PromptMessage(
            role="user",
            content=text_content
        )
        
        # Create the GetPromptResult
        prompt_result = GetPromptResult(
            description=system_prompt.get('description'),
            messages=[prompt_message]
        )
        
        return prompt_result
    
    @trace_method("[VMCPConfigManager]: Get Resource Template")
    async def get_resource_template(self, vmcp_template_request: VMCPResourceTemplateRequest) -> Dict[str, Any]:
        """Get a specific resource template"""
        if not self.vmcp_id:
            raise ValueError("No vMCP ID specified")
        
        vmcp_config = self.storage.load_vmcp_config(self.vmcp_id)
        if not vmcp_config:
            raise ValueError(f"vMCP config not found: {self.vmcp_id}")
        
        template_name = vmcp_template_request.template_name
        parameters = vmcp_template_request.parameters or {}
        
        vmcp_servers = vmcp_config.vmcp_config.get('selected_servers', [])
        vmcp_selected_resource_templates = vmcp_config.vmcp_config.get('selected_resource_templates', {})
        # Try to find the resource template in the servers
        for server in vmcp_servers:
            if template_name in vmcp_selected_resource_templates.get(server.get('name'), []):
                try:
                    # Get the resource template details
                    template_detail = await self.mcp_client_manager.get_resource_template_detail(
                        server.get('name'), template_name, connect_if_needed=True
                    )
                    if template_detail:
                        # Process the URI template with parameters
                        uri_template = template_detail.uriTemplate
                        processed_uri = uri_template
                        for param_name, param_value in parameters.items():
                            placeholder = f"{{{param_name}}}"
                            processed_uri = processed_uri.replace(placeholder, str(param_value))
                        
                        # Create a resource from the template
                        resource = Resource(
                            uri=processed_uri,
                            name=template_name,
                            description=template_detail.description,
                            mimeType=template_detail.mimeType,
                            annotations=template_detail.annotations
                        )
                        
                        return resource
                except Exception as e:
                    logger.error(f"Failed to get resource template {template_name} from server {server.get('name')}: {e}")
                    continue
        
        # Check custom resource templates
        for template in vmcp_config.custom_resource_templates:
            if template.get('name') == template_name:
                # Process custom resource template
                uri_template = template.get('uri_template', '')
                processed_uri = uri_template
                for param_name, param_value in parameters.items():
                    placeholder = f"{{{param_name}}}"
                    processed_uri = processed_uri.replace(placeholder, str(param_value))
                
                # Create a resource from the custom template
                resource = Resource(
                    uri=processed_uri,
                    name=template_name,
                    description=template.get('description', f"Custom resource template: {template_name}"),
                    mimeType=template.get('mime_type'),
                    annotations=template.get('annotations')
                )
                
                return resource
        
        raise ValueError(f"Resource template {template_name} not found in vMCP {self.vmcp_id}")
        
    @trace_method("[VMCPConfigManager]: Get Custom Prompt")
    async def get_custom_prompt(self, prompt_id: str, arguments: Optional[Dict[str, Any]] = None):
        """Get a custom prompt with variable substitution and tool call execution using regex parsing"""
        
        vmcp_config = self.storage.load_vmcp_config(self.vmcp_id)
        if not vmcp_config:
            raise ValueError(f"vMCP config not found: {self.vmcp_id}")
        
        # Find the custom prompt
        custom_prompt = None
        for prompt in vmcp_config.custom_prompts:
            if prompt.get('name') == prompt_id:
                custom_prompt = prompt
                break
        
        if not custom_prompt:
            raise ValueError(f"Custom prompt {prompt_id} not found in vMCP {self.vmcp_id}")
        
        # Get the prompt text
        prompt_text = custom_prompt.get('text', '')
        if arguments is None:
            arguments = {}
        
        # Read the corresponding environment variable file for the vmcp_id from storage if available
        environment_variables = self.storage.load_vmcp_environment(self.vmcp_id)
        if not environment_variables:
            environment_variables = {}
        
        # Parse and substitute using regex patterns
        prompt_text, _resource_content = await self._parse_vmcp_text(
            prompt_text, 
            custom_prompt, 
            arguments, 
            environment_variables,
            is_prompt=True
        )
        # logger.info(f"🔍 Prompt text: {prompt_text}")

        # Create the TextContent
        text_content = TextContent(
            type="text",
            text=prompt_text,
            annotations=None,
            meta=None
        )
        
        # Create the PromptMessage
        prompt_message = PromptMessage(
            role="user",
            content=text_content
        )
        
        # Create the GetPromptResult
        prompt_result = GetPromptResult(
            description=custom_prompt.get('description'),
            messages=[prompt_message]
        )
        
        return prompt_result

    @trace_method("[VMCPConfigManager]: Call Custom Tool")
    async def call_custom_tool(self, tool_id: str, arguments: Optional[Dict[str, Any]] = None, tool_as_prompt: bool = False):
        """Get a custom tool with variable substitution and tool call execution using regex parsing"""
        
        vmcp_config = self.storage.load_vmcp_config(self.vmcp_id)
        if not vmcp_config:
            raise ValueError(f"vMCP config not found: {self.vmcp_id}")
        
        # Find the custom tool
        custom_tool = None
        for tool in vmcp_config.custom_tools:
            if tool.get('name') == tool_id:
                custom_tool = tool
                break
        
        if not custom_tool:
            raise ValueError(f"Custom tool {tool_id} not found in vMCP {self.vmcp_id}")
        
        if arguments is None:
            arguments = {}
        
        # Read the corresponding environment variable file for the vmcp_id from storage if available
        environment_variables = self.storage.load_vmcp_environment(self.vmcp_id)
        if not environment_variables:
            environment_variables = {}

        # Handle different tool types
        tool_type = custom_tool.get('tool_type', 'prompt')
        
        if tool_type == 'python':
            return await self._execute_python_tool(custom_tool, arguments, environment_variables, tool_as_prompt)
        elif tool_type == 'http':
            return await self._execute_http_tool(custom_tool, arguments, environment_variables, tool_as_prompt)
        else:  # prompt tool (default)
            return await self._execute_prompt_tool(custom_tool, arguments, environment_variables, tool_as_prompt)

    async def _execute_prompt_tool(self, custom_tool: dict, arguments: Dict[str, Any], environment_variables: Dict[str, Any], tool_as_prompt: bool = False):
        """Execute a prompt-based tool"""
        # Get the tool text
        tool_text = custom_tool.get('text', '')
        
        # Parse and substitute using regex patterns
        tool_text, _resource_content = await self._parse_vmcp_text(
            tool_text, 
            custom_tool, 
            arguments, 
            environment_variables,
            is_prompt=tool_as_prompt
        )
        logger.info(f"🔍 Tool text: {tool_text}")
        if tool_as_prompt:
            tool_text, _resource_content = tool_text
            logger.info(f"🔍 Tool as prompt: {tool_text}")
        
        # Create the TextContent
        text_content = TextContent(
            type="text",
            text=tool_text,
            annotations=None,
            meta=None
        )
        
        if tool_as_prompt:
            # Create the PromptMessage
            prompt_message = PromptMessage(
                role="user",
                content=text_content
            )
            
            # Create the GetPromptResult
            prompt_result = GetPromptResult(
                description="Tool call result",
                messages=[prompt_message]
            )
            return prompt_result

        # Create the CallToolResult
        tool_result = CallToolResult(
            content=[text_content], 
            structuredContent=None,
            isError=False
        )
        
        return tool_result

    def _convert_arguments_to_types(self, arguments: Dict[str, Any], variables: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Convert string arguments to their correct types based on variable definitions"""
        converted = {}
        
        for var in variables:
            var_name = var.get('name')
            var_type = var.get('type', 'str')
            var_default = var.get('default_value')
            
            if var_name in arguments:
                value = arguments[var_name]
                
                # Handle null values
                if value is None or value == 'null' or value == '':
                    if var_default is not None:
                        converted[var_name] = var_default
                    else:
                        converted[var_name] = None
                    continue
                
                try:
                    if var_type == 'int':
                        converted[var_name] = int(value)
                    elif var_type == 'float':
                        converted[var_name] = float(value)
                    elif var_type == 'bool':
                        if isinstance(value, str):
                            converted[var_name] = value.lower() in ('true', '1', 'yes', 'on')
                        else:
                            converted[var_name] = bool(value)
                    elif var_type == 'list':
                        if isinstance(value, str):
                            # Try to parse as JSON array
                            try:
                                import json
                                converted[var_name] = json.loads(value)
                            except:
                                # Fallback to splitting by comma
                                converted[var_name] = [item.strip() for item in value.split(',')]
                        else:
                            converted[var_name] = value
                    elif var_type == 'dict':
                        if isinstance(value, str):
                            try:
                                import json
                                converted[var_name] = json.loads(value)
                            except:
                                converted[var_name] = value
                        else:
                            converted[var_name] = value
                    else:  # str or unknown type
                        converted[var_name] = str(value)
                except (ValueError, TypeError) as e:
                    # If conversion fails, use default value or keep as string
                    if var_default is not None:
                        converted[var_name] = var_default
                        logger.warning(f"Failed to convert argument '{var_name}' to type '{var_type}', using default: {e}")
                    else:
                        converted[var_name] = str(value)
                        logger.warning(f"Failed to convert argument '{var_name}' to type '{var_type}': {e}")
            else:
                # If argument not provided, use default value if available
                if var_default is not None:
                    converted[var_name] = var_default
                elif var.get('required', True):
                    logger.warning(f"Required argument '{var_name}' not provided")
                    converted[var_name] = None
                else:
                    converted[var_name] = None
        
        return converted

    async def _execute_python_tool(self, custom_tool: dict, arguments: Dict[str, Any], environment_variables: Dict[str, Any], tool_as_prompt: bool = False):
        """Execute a Python tool with secure sandboxing"""
        import subprocess
        import tempfile
        import os
        import json
        import sys
        
        # Get the Python code
        python_code = custom_tool.get('code', '')
        if not python_code:
            error_content = TextContent(
                type="text",
                text="No Python code provided for this tool",
                annotations=None,
                meta=None
            )
            return CallToolResult(
                content=[error_content],
                structuredContent=None,
                isError=True
            )
        
        # Convert arguments to correct types based on tool variables
        converted_arguments = self._convert_arguments_to_types(arguments, custom_tool.get('variables', []))
        
        # Create a secure execution environment
        try:
            # Create a temporary file for the Python code
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                # Prepare the execution environment
                execution_code = f"""
import sys
import json
import os
import subprocess
import tempfile
import shutil
import signal
import time
from contextlib import contextmanager

# Security: Disable dangerous modules
DANGEROUS_MODULES = [
    'os', 'subprocess', 'shutil', 'tempfile', 'signal', 'sys', 'importlib',
    'eval', 'exec', 'compile', '__import__', 'open', 'file', 'input', 'raw_input',
    'reload', 'vars', 'globals', 'locals', 'dir', 'hasattr', 'getattr', 'setattr',
    'delattr', 'callable', 'isinstance', 'issubclass', 'type', 'super'
]

# Override dangerous functions
def secure_exec(code, globals_dict, locals_dict):
    # Check for dangerous patterns
    dangerous_patterns = [
        'import os', 'import subprocess', 'import shutil', 'import tempfile',
        'import signal', 'import sys', 'import importlib',
        'eval(', 'exec(', 'compile(', '__import__(',
        'open(', 'file(', 'input(', 'raw_input(',
        'reload(', 'vars(', 'globals(', 'locals(',
        'dir(', 'hasattr(', 'getattr(', 'setattr(',
        'delattr(', 'callable(', 'isinstance(', 'issubclass(',
        'type(', 'super('
    ]
    
    for pattern in dangerous_patterns:
        if pattern in code:
            raise SecurityError(f"Dangerous pattern detected: {{pattern}}")
    
    # Execute the code
    exec(code, globals_dict, locals_dict)

class SecurityError(Exception):
    pass

# Arguments passed from the tool call
arguments = {json.dumps(converted_arguments)}

# Environment variables
environment_variables = {json.dumps(environment_variables)}

# User's Python code
{python_code}

# Execute the main function if it exists
if 'main' in locals() and callable(main):
    try:
        # Get function signature to properly map arguments
        import inspect
        sig = inspect.signature(main)
        param_names = list(sig.parameters.keys())
        
        # Filter arguments to only include those that match function parameters
        filtered_args = {{}}
        for param_name in param_names:
            if param_name in arguments:
                filtered_args[param_name] = arguments[param_name]
        
        result = main(**filtered_args)
        print(json.dumps({{"success": True, "result": result}}))
    except Exception as e:
        print(json.dumps({{"success": False, "error": str(e)}}))
else:
    print(json.dumps({{"success": False, "error": "No 'main' function found in the code"}}))
"""
                f.write(execution_code)
                temp_file = f.name
            
            # Execute the Python code in a secure environment
            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
                cwd=tempfile.gettempdir()  # Run in temp directory
            )
            
            # Clean up the temporary file
            os.unlink(temp_file)
            
            # Parse the result
            try:
                result_data = json.loads(result.stdout.strip())
                if result_data.get('success', False):
                    result_text = json.dumps(result_data.get('result', ''), indent=2)
                else:
                    result_text = f"Error: {result_data.get('error', 'Unknown error')}"
            except json.JSONDecodeError:
                result_text = result.stdout if result.stdout else result.stderr
            
            # Create the TextContent
            text_content = TextContent(
                type="text",
                text=result_text,
                annotations=None,
                meta=None
            )
            
            if tool_as_prompt:
                # Create the PromptMessage
                prompt_message = PromptMessage(
                    role="user",
                    content=text_content
                )
                
                # Create the GetPromptResult
                prompt_result = GetPromptResult(
                    description="Python tool execution result",
                    messages=[prompt_message]
                )
                return prompt_result

            # Create the CallToolResult
            tool_result = CallToolResult(
                content=[text_content],
                structuredContent=None,
                isError=not result_data.get('success', False) if 'result_data' in locals() else False
            )
            
            return tool_result
            
        except subprocess.TimeoutExpired:
            error_content = TextContent(
                type="text",
                text="Python tool execution timed out (30 seconds)",
                annotations=None,
                meta=None
            )
            return CallToolResult(
                content=[error_content],
                structuredContent=None,
                isError=True
            )
        except Exception as e:
            error_content = TextContent(
                type="text",
                text=f"Error executing Python tool: {str(e)}",
                annotations=None,
                meta=None
            )
            return CallToolResult(
                content=[error_content],
                structuredContent=None,
                isError=True
            )

    async def _execute_http_tool(self, custom_tool: dict, arguments: Dict[str, Any], environment_variables: Dict[str, Any], tool_as_prompt: bool = False):
        """Execute an HTTP tool with full parameter substitution and authentication support"""
        import aiohttp
        import json
        import urllib.parse
        import re
        
        # Get the API configuration
        api_config = custom_tool.get('api_config', {})
        if not api_config.get('url'):
            error_content = TextContent(
                type="text",
                text="No URL configured for this HTTP tool",
                annotations=None,
                meta=None
            )
            return CallToolResult(
                content=[error_content],
                structuredContent=None,
                isError=True
            )
        
        try:
            # Prepare the request
            method = api_config.get('method', 'GET').upper()
            url = api_config.get('url', '')
            headers = api_config.get('headers', {})
            body = api_config.get('body')
            body_parsed = api_config.get('body_parsed')
            query_params = api_config.get('query_params', {})
            auth = api_config.get('auth', {})
            
            logger.info(f"🔍 HTTP Tool Execution: {custom_tool.get('name')}")
            logger.info(f"🔍 Method: {method}, URL: {url}")
            logger.info(f"🔍 Arguments: {arguments}")
            logger.info(f"🔍 Environment variables: {environment_variables}")
            
            # Step 1: Substitute variables in URL (both {{variable}} and :pathParam patterns)
            url = self._substitute_url_variables(url, arguments, environment_variables)
            logger.info(f"🔍 Processed URL: {url}")
            
            # Step 2: Process headers with variable substitution
            processed_headers = {}
            for key, value in headers.items():
                processed_headers[key] = self._substitute_variables(str(value), arguments, environment_variables)
            
            # Step 3: Add authentication headers if configured
            if auth and auth.get('type') != 'none':
                auth_headers = self._get_auth_headers(auth, arguments, environment_variables)
                processed_headers.update(auth_headers)
                logger.info(f"🔍 Added auth headers: {list(auth_headers.keys())}")
            
            # Step 4: Process query parameters with variable substitution
            processed_query_params = {}
            for key, value in query_params.items():
                processed_value = self._substitute_variables(str(value), arguments, environment_variables)
                # Only add non-empty values
                if processed_value and processed_value not in ['<string>', '<long>', '<boolean>', '<number>', '']:
                    processed_query_params[key] = processed_value
            
            # Add query parameters to URL
            if processed_query_params:
                query_string = urllib.parse.urlencode(processed_query_params)
                url = f"{url}?{query_string}" if '?' not in url else f"{url}&{query_string}"
                logger.info(f"🔍 Final URL with query params: {url}")
            
            # Step 5: Prepare request body for POST/PUT/PATCH requests
            request_data = None
            if method in ['POST', 'PUT', 'PATCH', 'DELETE'] and (body or body_parsed):
                if body_parsed:
                    # Use the parsed body with @param substitutions
                    processed_body = self._substitute_body_variables(body_parsed, arguments, environment_variables)
                    request_data = json.dumps(processed_body, indent=2)
                    processed_headers.setdefault('Content-Type', 'application/json')
                    logger.info(f"🔍 Using body_parsed: {processed_body}")
                elif body:
                    # Use the raw body with variable substitution
                    if isinstance(body, dict):
                        processed_body = self._substitute_body_variables(body, arguments, environment_variables)
                        request_data = json.dumps(processed_body, indent=2)
                        processed_headers.setdefault('Content-Type', 'application/json')
                    else:
                        request_data = self._substitute_variables(str(body), arguments, environment_variables)
                        processed_headers.setdefault('Content-Type', 'application/json')
                    logger.info(f"🔍 Using raw body: {request_data}")
            
            # Step 6: Make the HTTP request
            logger.info(f"🔍 Making {method} request to: {url}")
            logger.info(f"🔍 Headers: {processed_headers}")
            
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=processed_headers,
                    data=request_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response_text = await response.text()
                    
                    # Try to parse JSON response for better formatting
                    try:
                        response_json = json.loads(response_text)
                        formatted_response = json.dumps(response_json, indent=2)
                    except json.JSONDecodeError:
                        formatted_response = response_text
                    
                    # Create result text
                    result_text = f"Status: {response.status}\n"
                    result_text += f"Status Text: {response.reason}\n"
                    result_text += f"Headers: {dict(response.headers)}\n"
                    result_text += f"Response:\n{formatted_response}"
                    
                    # Create the TextContent
                    text_content = TextContent(
                        type="text",
                        text=result_text,
                        annotations=None,
                        meta=None
                    )
                    
                    if tool_as_prompt:
                        # Create the PromptMessage
                        prompt_message = PromptMessage(
                            role="user",
                            content=text_content
                        )
                        
                        # Create the GetPromptResult
                        prompt_result = GetPromptResult(
                            description="HTTP tool execution result",
                            messages=[prompt_message]
                        )
                        return prompt_result

                    # Create the CallToolResult
                    tool_result = CallToolResult(
                        content=[text_content],
                        structuredContent=None,
                        isError=response.status >= 400
                    )
                    
                    logger.info(f"✅ HTTP tool execution completed with status: {response.status}")
                    return tool_result
                    
        except Exception as e:
            logger.error(f"❌ Error executing HTTP tool: {str(e)}")
            error_content = TextContent(
                type="text",
                text=f"Error executing HTTP tool: {str(e)}",
                annotations=None,
                meta=None
            )
            return CallToolResult(
                content=[error_content],
                structuredContent=None,
                isError=True
            )

    def _substitute_variables(self, text: str, arguments: Dict[str, Any], environment_variables: Dict[str, Any]) -> str:
        """Substitute @param and @config variables in text"""
        import re
        
        # Substitute @param variables
        param_pattern = r'@param\.(\w+)'
        def replace_param(match):
            param_name = match.group(1)
            return str(arguments.get(param_name, f"[{param_name} not found]"))
        
        text = re.sub(param_pattern, replace_param, text)
        
        # Substitute @config variables
        config_pattern = r'@config\.(\w+)'
        def replace_config(match):
            config_name = match.group(1)
            return str(environment_variables.get(config_name, f"[{config_name} not found]"))
        
        text = re.sub(config_pattern, replace_config, text)
        
        return text

    def _substitute_url_variables(self, url: str, arguments: Dict[str, Any], environment_variables: Dict[str, Any]) -> str:
        """Substitute variables in URL (both {{variable}} and :pathParam patterns)"""
        import re
        
        # First substitute @param and @config variables
        url = self._substitute_variables(url, arguments, environment_variables)
        
        # Then substitute {{variable}} patterns
        curly_pattern = r'\{\{([^}]+)\}\}'
        def replace_curly(match):
            var_name = match.group(1)
            return str(arguments.get(var_name, environment_variables.get(var_name, f"[{var_name} not found]")))
        
        url = re.sub(curly_pattern, replace_curly, url)
        
        # Finally substitute :pathParam patterns
        path_param_pattern = r':([a-zA-Z_][a-zA-Z0-9_]*)'
        def replace_path_param(match):
            param_name = match.group(1)
            return str(arguments.get(param_name, environment_variables.get(param_name, f"[{param_name} not found]")))
        
        url = re.sub(path_param_pattern, replace_path_param, url)
        
        return url

    def _substitute_body_variables(self, body: Any, arguments: Dict[str, Any], environment_variables: Dict[str, Any]) -> Any:
        """Recursively substitute variables in request body"""
        if isinstance(body, dict):
            return {key: self._substitute_body_variables(value, arguments, environment_variables) for key, value in body.items()}
        elif isinstance(body, list):
            return [self._substitute_body_variables(item, arguments, environment_variables) for item in body]
        elif isinstance(body, str):
            return self._substitute_variables(body, arguments, environment_variables)
        else:
            return body

    def _get_auth_headers(self, auth: Dict[str, Any], arguments: Dict[str, Any], environment_variables: Dict[str, Any]) -> Dict[str, str]:
        """Generate authentication headers based on auth configuration"""
        auth_type = auth.get('type', 'none').lower()
        headers = {}
        
        if auth_type == 'bearer':
            token = auth.get('token', '')
            if token:
                # Substitute variables in token
                processed_token = self._substitute_variables(token, arguments, environment_variables)
                headers['Authorization'] = f"Bearer {processed_token}"
        
        elif auth_type == 'apikey':
            api_key = auth.get('apiKey', '')
            key_name = auth.get('keyName', 'X-API-Key')
            if api_key:
                # Substitute variables in API key
                processed_key = self._substitute_variables(api_key, arguments, environment_variables)
                headers[key_name] = processed_key
        
        elif auth_type == 'basic':
            username = auth.get('username', '')
            password = auth.get('password', '')
            if username and password:
                # Substitute variables in credentials
                processed_username = self._substitute_variables(username, arguments, environment_variables)
                processed_password = self._substitute_variables(password, arguments, environment_variables)
                
                # Create basic auth header
                import base64
                credentials = f"{processed_username}:{processed_password}"
                encoded_credentials = base64.b64encode(credentials.encode()).decode()
                headers['Authorization'] = f"Basic {encoded_credentials}"
        
        elif auth_type == 'custom':
            # Handle custom headers
            custom_headers = auth.get('headers', {})
            for key, value in custom_headers.items():
                processed_value = self._substitute_variables(str(value), arguments, environment_variables)
                headers[key] = processed_value
        
        return headers

    def _parse_python_function_schema(self, custom_tool: dict) -> dict:
        """Parse Python function to extract parameters and create input schema using pre-parsed variables"""
        
        # Use the pre-parsed variables from the tool
        variables = custom_tool.get('variables', [])
        
        if not variables:
            return {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
                "$schema": "http://json-schema.org/draft-07/schema#"
            }
        
        # Map internal types to JSON schema types
        def map_to_json_schema_type(internal_type: str) -> str:
            type_mapping = {
                'str': 'string',
                'int': 'integer', 
                'float': 'number',
                'bool': 'boolean',
                'list': 'array',
                'dict': 'object'
            }
            return type_mapping.get(internal_type, 'string')
        
        # Build properties from parsed variables
        properties = {}
        required = []
        
        for var in variables:
            var_name = var.get('name')
            var_type = var.get('type', 'str')
            var_description = var.get('description', f"Parameter: {var_name}")
            var_required = var.get('required', True)
            var_default = var.get('default_value')
            
            if var_name:
                property_schema = {
                    "type": map_to_json_schema_type(var_type),
                    "description": var_description
                }
                
                # Add default value if present
                if var_default is not None:
                    property_schema["default"] = var_default
                
                properties[var_name] = property_schema
                
                if var_required:
                    required.append(var_name)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
            "$schema": "http://json-schema.org/draft-07/schema#"
        }

    @trace_method("[VMCPConfigManager]: Parse VMCP Text")
    async def _parse_vmcp_text(self, text: str, config_item: dict, arguments: Dict[str, Any], 
                            environment_variables: Dict[str, Any], is_prompt: bool = False) -> str:
        """Parse VMCP text: first substitute @param variables, then process Jinja2 if detected"""
        resource_content = None
        
        logger.info(f"🔍 Parsing VMCP text: {text}")
        logger.info(f"🔍 Environment variables: {environment_variables}")
        logger.info(f"🔍 Arguments: {arguments}")
        logger.info(f"🔍 Is prompt: {is_prompt}")
        
        # Step 1: First substitute @param and @config variables using existing regex system
        processed_text = text
        
        # 1. Parse and substitute environment variables: @config.VAR_NAME
        env_pattern = r'@config\.(\w+)'
        def replace_env(match):
            env_name = match.group(1)
            env_value = environment_variables.get(env_name, arguments.get(env_name, f"[{env_name} not found]"))
            logger.info(f"🔄 Substituting @config.{env_name} with: {env_value}")
            return str(env_value)
        
        processed_text = re.sub(env_pattern, replace_env, processed_text)
        
        # 2. Parse and substitute local variables: @param.variable_name
        var_pattern = r'@param\.(\w+)'
        def replace_var(match):
            var_name = match.group(1)
            var_value = arguments.get(var_name, f"[{var_name} not found]")
            logger.info(f"🔄 Substituting @param.{var_name} with: {var_value}")
            return str(var_value)
        
        processed_text = re.sub(var_pattern, replace_var, processed_text)
        
        # 3. Parse and handle resource references: @resource.server.resource_name
        resource_pattern = r'@resource\.(\w+)\.([\w\/\:\.\-]+)'
        resources_to_fetch = []
        
        def collect_resource(match):
            server_name = match.group(1)
            resource_name = match.group(2)
            resources_to_fetch.append((server_name, resource_name, match.group(0)))
            return match.group(0)  # Keep original for now, will replace after fetching
        
        processed_text = re.sub(resource_pattern, collect_resource, processed_text)
        
        # Fetch resources and substitute
        for server_name, resource_name, original_match in resources_to_fetch:
            try:
                logger.info(f"🔍 Fetching resource: {server_name}.{resource_name}")
                
                # Create the resource name with server prefix
                if server_name=="vmcp":
                    prefixed_resource_name = f"{resource_name}"
                else:
                    prefixed_resource_name = f"{server_name.replace('_', '')}:{resource_name}"
                
                # Fetch the resource
                from vmcps.models import VMCPResourceRequest
                resource_request = VMCPResourceRequest(uri=prefixed_resource_name)
                resource_result = await self.get_resource(resource_request.uri,connect_if_needed=True)
                logger.info(f"🔍 Resource result: {resource_result}")
                # Convert result to string
                if hasattr(resource_result, 'contents') and resource_result.contents:
                    if len(resource_result.contents) > 1:
                        resource_str = json.dumps(resource_result.contents, indent=2, default=str)
                    else:
                        resource_str = resource_result.contents[0].text if hasattr(resource_result.contents[0], 'text') else str(resource_result.contents[0])
                else:
                    resource_str = str(resource_result)
                
                # For prompts, resources should be attached as separate user messages
                # For tools, just substitute inline
                if is_prompt:
                    # TODO: Handle resource attachment as separate message
                    processed_text = processed_text.replace(original_match, resource_str)
                else:
                    processed_text = processed_text.replace(original_match, resource_str)
                    
                logger.info(f"✅ Successfully fetched and substituted resource {server_name}.{resource_name}")
                
            except Exception as e:
                logger.error(f"❌ Failed to fetch resource {server_name}.{resource_name}: {e}")
                processed_text = processed_text.replace(original_match, f"[Resource fetch failed: {str(e)}]")
        
        # 4. Parse and handle tool calls: @tool.server.tool_name(param1="value", param2="value")
        tool_pattern = r'@tool\.(\w+)\.(\w+)\(([^)]*)\)'
        
        async def replace_tool(match):
            server_name = match.group(1)
            tool_name = match.group(2)
            params_str = match.group(3).strip()
            
            try:
                logger.info(f"🔍 Executing tool call: {server_name}.{tool_name}")
                
                # Parse parameters
                tool_arguments = {}
                if params_str:
                    logger.info(f"🔍 Parsing tool parameters: {params_str}")
                    tool_arguments = self._parse_parameters(params_str, arguments, environment_variables)

                logger.info(f"🔍 Tool arguments: {tool_arguments}")
                
                if server_name=="vmcp":
                    prefixed_tool_name = f"{tool_name}"
                else:
                    # Create the tool name with server prefix
                    prefixed_tool_name = f"{server_name.replace('_', '')}_{tool_name}"
                

                # Create VMCPToolCallRequest
                from vmcps.models import VMCPToolCallRequest
                tool_request = VMCPToolCallRequest(
                    tool_name=prefixed_tool_name,
                    arguments=tool_arguments
                )
                
                # Execute the tool call
                tool_result = await self.call_tool(tool_request)
                
                # Extract result text
                try:
                    tool_result_str = ""
                    if len(tool_result.content) > 1:
                        tool_result_str = json.dumps(tool_result.content, indent=2, default=str)
                    else:
                        tool_result_str = str(tool_result.content[0].text)
                    
                except Exception as e:
                    if isinstance(tool_result, dict):
                        tool_result_str = json.dumps(tool_result, indent=2, default=str)
                    else:
                        tool_result_str = str(tool_result)
                
                logger.info(f"✅ Successfully executed tool call {server_name}.{tool_name}")
                return tool_result_str
                
            except Exception as e:
                logger.error(f"❌ Failed to execute tool call {server_name}.{tool_name}: {e}")
                return f"[Tool call failed: {str(e)}]"
        
        # Process tool calls sequentially (since they're async)
        while True:
            match = re.search(tool_pattern, processed_text)
            if not match:
                break
            
            replacement = await replace_tool(match)
            processed_text = processed_text[:match.start()] + replacement + processed_text[match.end():]
        
        # 5. Parse and handle prompt calls: @prompt.server.prompt_name(param1="value")
        prompt_pattern = r'@prompt\.(\w+)\.(\w+)\(([^)]*)\)'
        
        async def replace_prompt(match):
            server_name = match.group(1)
            prompt_name = match.group(2)
            params_str = match.group(3).strip()
            
            try:
                logger.info(f"🔍 Executing prompt call: {server_name}.{prompt_name}")
                
                # Parse parameters
                prompt_arguments = {}
                if params_str:
                    prompt_arguments = self._parse_parameters(params_str, arguments, environment_variables)
                
                # Create the prompt name with server prefix
                if server_name == "vmcp":
                    prefixed_prompt_name = f"{prompt_name}"
                else:
                    prefixed_prompt_name = f"{server_name.replace('_', '')}_{prompt_name}"
                
                # Create VMCPPromptRequest
                from vmcps.models import VMCPPromptRequest
                prompt_request = VMCPPromptRequest(
                    prompt_id=prefixed_prompt_name,
                    arguments=prompt_arguments
                )
                
                # Execute the prompt call
                prompt_result = await self.get_prompt(prompt_request.prompt_id, prompt_request.arguments)
                
                # Extract result text (assuming first message content)
                try:
                    if hasattr(prompt_result, 'messages') and prompt_result.messages:
                        prompt_result_str = prompt_result.messages[0].content.text
                    else:
                        prompt_result_str = str(prompt_result)
                except Exception as e:
                    if isinstance(prompt_result, dict):
                        prompt_result_str = json.dumps(prompt_result, indent=2, default=str)
                    else:
                        prompt_result_str = str(prompt_result)
                
                logger.info(f"✅ Successfully executed prompt call {server_name}.{prompt_name}")
                return prompt_result_str
                
            except Exception as e:
                logger.error(f"❌ Failed to execute prompt call {server_name}.{prompt_name}: {e}")
                return f"[Prompt call failed: {str(e)}]"
        
        # Process prompt calls sequentially (since they're async)
        while True:
            match = re.search(prompt_pattern, processed_text)
            if not match:
                break
            
            replacement = await replace_prompt(match)
            processed_text = processed_text[:match.start()] + replacement + processed_text[match.end():]
        
        # Final step: Check if the fully processed text is a Jinja2 template and process it
        if self._is_jinja_template(processed_text):
            logger.info(f"🔍 Detected Jinja2 template after all substitutions")
            # Pass original context in case there are other variables not substituted by regex
            processed_text = self._preprocess_jinja_to_regex(processed_text, arguments, environment_variables)
        
        return processed_text, resource_content

    @trace_method("[VMCPConfigManager]: Parse Parameters")
    def _parse_parameters(self, params_str: str, arguments: Dict[str, Any], environment_variables: Dict[str, Any]) -> Dict[str, Any]:
        """Parse parameter string using Python AST to handle function-like syntax with type annotations"""
        params = {}
        if not params_str.strip():
            return params
        
        try:
            # Preprocess the parameter string to handle @var and @env references
            processed_params_str = self._preprocess_parameter_string(params_str, arguments, environment_variables)
            
            # Use Python's AST parser to parse the parameter string
            # We'll create a mock function definition to parse the parameters
            function_def = f"def mock_function({processed_params_str}): pass"
            
            # Parse the function definition
            tree = ast.parse(function_def)
            func_def = tree.body[0]
            
            # Extract parameters from the function definition
            for arg in func_def.args.args:
                param_name = arg.arg
                param_type = None
                default_value = None
                
                # Get type annotation if present
                if arg.annotation:
                    param_type = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else self._ast_to_string(arg.annotation)
                
                # Get default value if present
                # We need to find the corresponding default value by position
                arg_index = func_def.args.args.index(arg)
                if arg_index < len(func_def.args.defaults):
                    default_ast = func_def.args.defaults[arg_index]
                    default_value = self._evaluate_ast_node(default_ast, arguments, environment_variables)
                
                # If no default value from AST, try to get from arguments
                if default_value is None and param_name in arguments:
                    default_value = arguments[param_name]
                
                # Type cast the value if type annotation is present
                if param_type and default_value is not None:
                    default_value = self._cast_value_to_type(default_value, param_type)
                
                params[param_name] = default_value
                
        except Exception as e:
            logger.warning(f"Failed to parse parameters with AST, falling back to regex: {e}")
            # Fallback to the original regex-based parsing
            return self._parse_parameters_regex(params_str, arguments, environment_variables)
        
        return params
    
    @trace_method("[VMCPConfigManager]: Preprocess Parameter String")
    def _preprocess_parameter_string(self, params_str: str, arguments: Dict[str, Any], environment_variables: Dict[str, Any]) -> str:
        """Preprocess parameter string to replace @var and @env references with actual values"""
        # Replace @var.name references
        var_pattern = r'@param\.(\w+)'
        def replace_var(match):
            var_name = match.group(1)
            var_value = arguments.get(var_name, f"[{var_name} not found]")
            # If it's a string, wrap in quotes
            if isinstance(var_value, str) and not (var_value.startswith('"') and var_value.endswith('"')):
                return f'"{var_value}"'
            return str(var_value)
        
        processed_str = re.sub(var_pattern, replace_var, params_str)
        
        # Replace @env.name references
        env_pattern = r'@config\.(\w+)'
        def replace_env(match):
            env_name = match.group(1)
            env_value = environment_variables.get(env_name, f"[{env_name} not found]")
            # If it's a string, wrap in quotes
            if isinstance(env_value, str) and not (env_value.startswith('"') and env_value.endswith('"')):
                return f'"{env_value}"'
            return str(env_value)
        
        processed_str = re.sub(env_pattern, replace_env, processed_str)
        
        return processed_str
    
    @trace_method("[VMCPConfigManager]: Parse Parameters Regex")
    def _parse_parameters_regex(self, params_str: str, arguments: Dict[str, Any], environment_variables: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback regex-based parameter parsing for compatibility"""
        params = {}
        if not params_str.strip():
            return params
        
        # Simple parameter parsing - handles param="value" format
        param_pattern = r'(\w+)\s*=\s*([^,]+?)(?=\s*,\s*\w+\s*=|$)'
        
        for match in re.finditer(param_pattern, params_str):
            param_name = match.group(1)
            param_value = match.group(2)
            if param_value.startswith('"') and param_value.endswith('"'):
                param_value = param_value[1:-1]
            # Substitute any @var.name or @env.name references in the parameter value
            param_value = re.sub(r'@param\.(\w+)', lambda m: str(arguments.get(m.group(1), f"[{m.group(1)} not found]")), param_value)
            param_value = re.sub(r'@config\.(\w+)', lambda m: str(environment_variables.get(m.group(1), f"[{m.group(1)} not found]")), param_value)
            
            params[param_name] = param_value
        
        return params
    
    @trace_method("[VMCPConfigManager]: AST to String")
    def _ast_to_string(self, node: ast.AST) -> str:
        """Convert AST node to string representation"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Str):  # Python < 3.8 compatibility
            return node.s
        elif isinstance(node, ast.Num):  # Python < 3.8 compatibility
            return str(node.n)
        elif isinstance(node, ast.NameConstant):  # Python < 3.8 compatibility
            return str(node.value)
        else:
            return str(node)
    
    @trace_method("[VMCPConfigManager]: Evaluate AST Node")
    def _evaluate_ast_node(self, node: ast.AST, arguments: Dict[str, Any], environment_variables: Dict[str, Any]) -> Any:
        """Evaluate an AST node to get its value"""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Str):  # Python < 3.8 compatibility
            return node.s
        elif isinstance(node, ast.Num):  # Python < 3.8 compatibility
            return node.n
        elif isinstance(node, ast.NameConstant):  # Python < 3.8 compatibility
            return node.value
        elif isinstance(node, ast.Name):
            # Check if it's a variable reference
            var_name = node.id
            if var_name in arguments:
                return arguments[var_name]
            elif var_name in environment_variables:
                return environment_variables[var_name]
            else:
                return f"[{var_name} not found]"
        elif isinstance(node, ast.Str):  # String literal
            return node.s
        elif isinstance(node, ast.Num):  # Numeric literal
            return node.n
        elif isinstance(node, ast.NameConstant):  # Boolean/None literals
            return node.value
        else:
            # For complex expressions, try to evaluate safely
            try:
                # This is a simplified evaluation - in production you might want more robust handling
                return ast.literal_eval(node)
            except:
                return str(node)
    
    @trace_method("[VMCPConfigManager]: Cast Value to Type")
    def _cast_value_to_type(self, value: Any, type_str: str) -> Any:
        """Cast a value to the specified type"""
        try:
            # Handle common type annotations
            if type_str == "str":
                return str(value)
            elif type_str == "int":
                return int(value)
            elif type_str == "float":
                return float(value)
            elif type_str == "bool":
                if isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes', 'on')
                return bool(value)
            elif type_str == "list":
                if isinstance(value, str):
                    # Try to parse as JSON list
                    try:
                        import json
                        return json.loads(value)
                    except:
                        return [value]
                return list(value) if hasattr(value, '__iter__') else [value]
            elif type_str == "dict":
                if isinstance(value, str):
                    # Try to parse as JSON dict
                    try:
                        import json
                        return json.loads(value)
                    except:
                        return {"value": value}
                return dict(value) if hasattr(value, 'items') else {"value": value}
            else:
                # For custom types or unknown types, return as-is
                logger.warning(f"Unknown type annotation: {type_str}, returning value as-is")
                return value
        except Exception as e:
            logger.warning(f"Failed to cast {value} to {type_str}: {e}")
            return value
    
    # Background task function for logging agent operations
    async def log_vmcp_operation(
        self,
        operation_type: str,
        operation_id: str, 
        arguments: Optional[Dict[str, Any]],
        result: Optional[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Background task to log agent operations (tool calls, resource requests, prompt requests, etc.)"""
        try:
            vmcp_id = self.vmcp_id
            vmcp_config = self.load_vmcp_config(vmcp_id)

            # OSS - log_vmcp_operation_to_span disabled

            # ORIGINAL: Keep file logging as fallback/backup
            total_tools = vmcp_config.total_tools if vmcp_config else 0
            total_resources = vmcp_config.total_resources if vmcp_config else 0
            total_resource_templates = vmcp_config.total_resource_templates if vmcp_config else 0
            total_prompts = vmcp_config.total_prompts if vmcp_config else 0
                
            # Log the operation
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "method": operation_type,
                "agent_name": self.logging_config.get("agent_name", "unknown"),
                "agent_id": self.logging_config.get("agent_id", "unknown"),
                "user_id": self.user_id,
                "client_id": self.logging_config.get("client_id", "unknown"),
                "operation_id": operation_id,
                "mcp_server": metadata.get("server"),
                "mcp_method": operation_type,
                "original_name": metadata.get("tool") if operation_type in ["tool_call"] else metadata.get("prompt") if operation_type in ["prompt_get"] else metadata.get("resource") if operation_type in ["resource_read"] else operation_type,
                "arguments": arguments,
                "result": result.to_dict() if hasattr(result, 'to_dict') else str(result),
                "vmcp_id": vmcp_id,
                "vmcp_name": vmcp_config.name if vmcp_config else None,
                "total_tools": total_tools,
                "total_resources": total_resources,
                "total_resource_templates": total_resource_templates,
                "total_prompts": total_prompts
            }
            
            # Save to the appropriate log file with suffix
            self.storage.save_user_vmcp_logs(log_entry)
            logger.info(f"[BACKGROUND TASK LOGGING] Successfully logged {operation_type} for user {self.user_id} ({self.user_id})")
        except Exception as e:
            # Silently fail for logging - don't affect the main request
            logger.error(f"[BACKGROUND TASK LOGGING] Traceback: {traceback.format_exc()}")
            logger.error(f"[BACKGROUND TASK LOGGING] Could not log {operation_type} for user {self.user_id}: {e}")

    def update_vmcp_server(self, vmcp_id: str, server_config: MCPServerConfig) -> bool:
        """Update the server ID for a vMCP"""
        vmcp_config = self.load_vmcp_config(vmcp_id)
        server_id = server_config.server_id
        # logger.info(f"🔍 Updating vMCP server: {vmcp_id} with server config: {server_config.to_dict()}")
        if vmcp_config:
            selected_servers = vmcp_config.vmcp_config.get('selected_servers', [])
            if selected_servers:
                for idx, server in enumerate(selected_servers):
                    logger.info(f"🔍 Checking server: {server.get('server_id')} == {server_id}")
                    server_config_dict = server_config.to_dict()
                    logger.info(f"🔍 Server config dict: {server_config_dict.get('tools', [])}")
                    if server.get('server_id') == server_id:
                        vmcp_config.vmcp_config['selected_servers'][idx] = server_config_dict
                        selected_tools = vmcp_config.vmcp_config.get('selected_tools', {})
                        selected_resources = vmcp_config.vmcp_config.get('selected_resources', {})
                        selected_prompts = vmcp_config.vmcp_config.get('selected_prompts', {})
                        logger.info(f"🔍 Selected tools [current]: {selected_tools}")
                        if  not selected_tools.get(server_id, []):
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
                        


                        self.update_vmcp_config(vmcp_id, vmcp_config=vmcp_config.vmcp_config)
                        break
