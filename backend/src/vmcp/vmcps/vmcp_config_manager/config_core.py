#!/usr/bin/env python3
"""
VMCP Config Manager - Core Orchestrator
========================================

This is the MAIN orchestrator class that coordinates all vMCP subsystems.
It manages virtual MCP (vMCP) configurations that augment and customize MCP server behavior.

Key Responsibilities:
---------------------
1. Initialization and Configuration Management
   - Load/save vMCP configurations
   - Environment variable management
   - Configuration CRUD operations

2. vMCP Listing and Discovery
   - List user's private vMCPs
   - List public vMCPs available for installation
   - List well-known vMCPs
   - Get specific vMCP details

3. vMCP Installation and Server Management
   - Install public vMCPs with server conflict resolution
   - Create server configurations from vMCP data
   - Track server usage across vMCPs

4. Protocol Delegation
   - Delegates MCP protocol operations (tools_list, resources_list, etc.) to protocol_handler
   - Delegates execution operations (call_tool, get_prompt, etc.) to execution_core
   - Delegates resource management to resource_manager
   - Delegates server operations to server_manager

5. Template Processing
   - Jinja2 template detection and preprocessing
   - Template rendering with environment and parameter context

Architecture:
-------------
This class serves as the entry point and coordinator, delegating specific
functionality to specialized modules:
- protocol_handler: MCP protocol operations
- execution_core: Tool/prompt/resource template execution
- resource_manager: Resource CRUD operations
- server_manager: Server installation and configuration
- template_parser: Template parsing and variable substitution
- logger: Operation logging and tracing
- custom_tool_engines: Custom tool and prompt execution
"""

import os
import json
import logging
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime
from jinja2 import Environment, DictLoader

from mcp.types import (
    Tool, Resource, ResourceTemplate, Prompt, PromptArgument,
    CallToolResult, GetPromptResult, ReadResourceResult,
    TextContent, PromptMessage
)

from vmcp.config import settings
from vmcp.storage.base import StorageBase
from vmcp.mcps.mcp_configmanager import MCPConfigManager
from vmcp.mcps.mcp_client import MCPClientManager
from vmcp.vmcps.models import VMCPConfig, VMCPToolCallRequest, VMCPResourceTemplateRequest
from vmcp.utilities.tracing import trace_method, add_event, log_to_span

# Import our new typed models
from vmcp.shared.vmcp_content_models import (
    SystemPrompt, CustomPrompt, CustomTool, CustomResource, 
    CustomResourceTemplate, EnvironmentVariable, UploadedFile, VMCPConfigData
)

# Import extracted modules for delegation
from . import protocol_handler
from . import execution_core
from . import resource_manager
from . import server_manager
from . import template_parser
from . import logger as vmcp_logger
from .custom_tool_engines import prompt_tool, python_tool, http_tool

logger = logging.getLogger("1xN_vMCP_CONFIG_MANAGER")


class VMCPConfigManager:
    """
    Main orchestrator class for Virtual MCP (vMCP) configuration management.

    This class coordinates all vMCP subsystems and provides a unified interface
    for managing agent configurations, executing tools and prompts, managing
    resources, and coordinating with MCP servers.

    Attributes:
        storage (StorageBase): Storage backend for vMCP configurations
        user_id (str): Current user identifier
        vmcp_id (Optional[str]): Active vMCP identifier
        mcp_config_manager (MCPConfigManager): MCP server configuration manager
        mcp_client_manager (MCPClientManager): MCP client connection manager
        logging_config (Dict): Configuration for operation logging
        jinja_env (Environment): Jinja2 environment for template processing

    Example:
        >>> manager = VMCPConfigManager(user_id="user123", vmcp_id="vmcp456")
        >>> tools = await manager.tools_list()
        >>> result = await manager.call_tool("my_tool", {"arg": "value"})
    """

    def __init__(
        self,
        user_id: str,
        vmcp_id: Optional[str] = None,
        logging_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the VMCP Configuration Manager.

        Args:
            user_id: User identifier for storage and access control
            vmcp_id: Optional active vMCP identifier
            logging_config: Optional logging configuration dictionary
                          Defaults to web client configuration if not provided
        """
        self.storage = StorageBase(user_id)
        self.user_id = user_id
        self.vmcp_id = vmcp_id
        self.mcp_config_manager = MCPConfigManager(user_id)
        self.mcp_client_manager = MCPClientManager(self.mcp_config_manager)
        self.logging_config = logging_config or {
            "agent_name": "1xn_web_client",
            "agent_id": "1xn_web_client",
            "client_id": "1xn_web_client"
        }

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

        logger.info(f"Initialized VMCPConfigManager for user {user_id}, vMCP {vmcp_id}")

    # =========================================================================
    # Environment Variable Management
    # =========================================================================

    def _save_vmcp_environment(self, vmcp_id: str, environment_vars: Dict[str, str]) -> bool:
        """
        Save vMCP environment variables to storage.

        Args:
            vmcp_id: vMCP identifier
            environment_vars: Dictionary of environment variable key-value pairs

        Returns:
            True if save successful, False otherwise
        """
        return self.storage.save_vmcp_environment(vmcp_id, environment_vars)

    def _load_vmcp_environment(self, vmcp_id: str) -> Dict[str, str]:
        """
        Load vMCP environment variables from storage.

        Args:
            vmcp_id: vMCP identifier

        Returns:
            Dictionary of environment variable key-value pairs
        """
        return self.storage.load_vmcp_environment(vmcp_id)

    # =========================================================================
    # Configuration Loading and Saving
    # =========================================================================

    @trace_method("[VMCPConfigManager]: Load VMCP Config")
    def load_vmcp_config(self, specific_vmcp_id: Optional[str] = None) -> Optional[VMCPConfig]:
        """
        Load vMCP configuration from storage.

        Args:
            specific_vmcp_id: Optional specific vMCP ID to load.
                            If not provided, uses self.vmcp_id

        Returns:
            VMCPConfig object if found, None otherwise
        """
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
                result={
                    "success": True,
                    "vmcp_name": result.name,
                    "total_tools": getattr(result, 'total_tools', 0)
                },
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

    @trace_method("[VMCPConfigManager]: Save VMCP Config")
    def save_vmcp_config(self, vmcp_config: VMCPConfig) -> bool:
        """
        Save a vMCP configuration to storage.

        Args:
            vmcp_config: VMCPConfig object to save

        Returns:
            True if save successful, False otherwise
        """
        return self.storage.save_vmcp(vmcp_config.id, vmcp_config.to_dict())

    # =========================================================================
    # vMCP Listing and Discovery
    # =========================================================================

    @trace_method("[VMCPConfigManager]: List Available VMCPs")
    def list_available_vmcps(self) -> List[Dict[str, Any]]:
        """
        List all vMCP configurations available to the current user.

        Returns:
            List of vMCP configuration dictionaries
        """
        return self.storage.list_vmcps()

    @trace_method("[VMCPConfigManager]: List Public VMCPs")
    def list_public_vmcps(self) -> List[Dict[str, Any]]:
        """
        List all public vMCPs available for installation.

        Returns:
            List of public vMCP dictionaries
        """
        try:
            return self.storage.list_public_vmcps()
        except Exception as e:
            logger.error(f"Error listing public vMCPs: {e}")
            return []

    @staticmethod
    def list_public_vmcps_static() -> List[Dict[str, Any]]:
        """
        List all public vMCPs available for installation (static method).

        Note: OSS version does not implement public vMCP registry yet.

        Returns:
            Empty list in OSS version
        """
        logger.debug("Public vMCP registry not available in OSS version")
        return []

    def list_wellknown_vmcps(self) -> List[Dict[str, Any]]:
        """
        List all well-known vMCPs available for installation.

        Returns:
            List of well-known vMCP dictionaries
        """
        try:
            return self.storage.list_wellknown_vmcps()
        except Exception as e:
            logger.error(f"Error listing well-known vMCPs: {e}")
            return []

    def get_public_vmcp(self, vmcp_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details of a specific public vMCP.

        Args:
            vmcp_id: Public vMCP identifier

        Returns:
            Public vMCP dictionary if found, None otherwise
        """
        try:
            return self.storage.get_public_vmcp(vmcp_id)
        except Exception as e:
            logger.error(f"Error getting public vMCP: {e}")
            return None

    @staticmethod
    def get_public_vmcp_static(vmcp_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details of a specific public vMCP (static method).
        
        Queries the global_public_vmcp_registry table directly.

        Args:
            vmcp_id: Public vMCP identifier

        Returns:
            Public vMCP dictionary if found, None otherwise
        """
        try:
            # Create a temporary storage instance for global operations
            # Use default user_id=1 for OSS version
            storage_handler = StorageBase(user_id=1)
            return storage_handler.get_public_vmcp(vmcp_id)
        except Exception as e:
            logger.error(f"Error getting public vMCP {vmcp_id}: {e}")
            return None

    def get_wellknown_vmcp(self, vmcp_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details of a specific well-known vMCP.

        Args:
            vmcp_id: Well-known vMCP identifier

        Returns:
            Well-known vMCP dictionary if found, None otherwise
        """
        try:
            return self.storage.get_wellknown_vmcp(vmcp_id)
        except Exception as e:
            logger.error(f"Error getting well-known vMCP: {e}")
            return None

    @staticmethod
    def get_wellknown_vmcp_static(vmcp_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details of a specific well-known vMCP (static method).

        Note: OSS version does not implement well-known vMCP registry yet.

        Args:
            vmcp_id: Well-known vMCP identifier

        Returns:
            None in OSS version
        """
        logger.debug(f"Well-known vMCP registry not available in OSS version: {vmcp_id}")
        return None

    # =========================================================================
    # vMCP CRUD Operations
    # =========================================================================

    def create_vmcp_config(
        self,
        name: str,
        description: Optional[str] = None,
        system_prompt: Optional[SystemPrompt] = None,
        vmcp_config: Optional[VMCPConfigData] = None,
        custom_prompts: Optional[List[CustomPrompt]] = None,
        custom_tools: Optional[List[CustomTool]] = None,
        custom_context: Optional[List[str]] = None,
        custom_resources: Optional[List[CustomResource]] = None,
        custom_resource_templates: Optional[List[CustomResourceTemplate]] = None,
        custom_resource_uris: Optional[List[str]] = None,
        environment_variables: Optional[List[EnvironmentVariable]] = None,
        uploaded_files: Optional[List[UploadedFile]] = None
    ) -> Optional[str]:
        """
        Create a new vMCP configuration.

        Args:
            name: Display name for the vMCP
            description: Optional description of the vMCP's purpose
            system_prompt: Optional system prompt configuration (text + variables)
            vmcp_config: Optional vMCP configuration dictionary containing:
                - selected_servers: List of MCP servers to use
                - selected_tools: Dictionary of server -> tool list mappings
                - selected_resources: Dictionary of server -> resource list mappings
                - selected_resource_templates: Dictionary of server -> template list mappings
                - selected_prompts: Dictionary of server -> prompt list mappings
            custom_prompts: Optional list of custom prompt definitions
            custom_tools: Optional list of custom tool definitions
            custom_context: Optional list of context strings
            custom_resources: Optional list of custom resource definitions
            custom_resource_templates: Optional list of custom resource template definitions
            custom_resource_uris: Optional list of custom resource URIs
            environment_variables: Optional list of environment variable definitions
            uploaded_files: Optional list of uploaded file metadata

        Returns:
            Created vMCP ID if successful, None otherwise
        """
        try:
            # Convert Pydantic objects to dictionaries for compatibility
            if system_prompt and hasattr(system_prompt, 'dict'):
                system_prompt = system_prompt.dict()
            if vmcp_config and hasattr(vmcp_config, 'dict'):
                vmcp_config = vmcp_config.dict()
            if custom_prompts:
                custom_prompts = [prompt.dict() if hasattr(prompt, 'dict') else prompt for prompt in custom_prompts]
            if custom_tools:
                custom_tools = [tool.dict() if hasattr(tool, 'dict') else tool for tool in custom_tools]
            if custom_resources:
                custom_resources = [resource.dict() if hasattr(resource, 'dict') else resource for resource in custom_resources]
            if environment_variables:
                environment_variables = [env.dict() if hasattr(env, 'dict') else env for env in environment_variables]
            if uploaded_files:
                uploaded_files = [file.dict() if hasattr(file, 'dict') else file for file in uploaded_files]
            
            # Generate unique VMCP ID
            vmcp_id = str(uuid.uuid4())

            # Convert string system prompt to object format if needed
            if isinstance(system_prompt, str):
                system_prompt = {
                    "text": system_prompt,
                    "variables": []
                }

            # Use empty dict if vmcp_config is None
            vmcp_config = vmcp_config or {}

            # Get the total number of tools, resources, resource templates, and prompts
            total_tools = len(custom_tools or []) + sum(
                len(x) for x in vmcp_config.get('selected_tools', {}).values()
            )
            total_resources = len(custom_resources or []) + sum(
                len(x) for x in vmcp_config.get('selected_resources', {}).values()
            )
            total_resource_templates = len(custom_resource_templates or []) + sum(
                len(x) for x in vmcp_config.get('selected_resource_templates', {}).values()
            )
            total_prompts = len(custom_prompts or []) + sum(
                len(x) for x in vmcp_config.get('selected_prompts', {}).values()
            )

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
            else:
                logger.error(f"Failed to save VMCP config: {name}")

            # Update private vMCP registry
            update_data = {
                "vmcp_config": config.to_dict(),
                "vmcp_registry_config": config.to_vmcp_registry_config().to_dict()
            }
            self.storage.update_private_vmcp_registry(
                private_vmcp_id=vmcp_id,
                private_vmcp_registry_data=update_data,
                operation="add"
            )
            logger.info(f"Updated private vMCP registry: {vmcp_id}")
            return vmcp_id

        except Exception as e:
            logger.error(f"Error creating VMCP config: {e}")
            return None

    @trace_method("[VMCPConfigManager]: Update VMCP Config")
    def update_vmcp_config(
        self,
        vmcp_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        system_prompt: Optional[SystemPrompt] = None,
        vmcp_config: Optional[VMCPConfigData] = None,
        custom_prompts: Optional[List[CustomPrompt]] = None,
        custom_tools: Optional[List[CustomTool]] = None,
        custom_context: Optional[List[str]] = None,
        custom_resources: Optional[List[CustomResource]] = None,
        custom_resource_templates: Optional[List[CustomResourceTemplate]] = None,
        custom_resource_uris: Optional[List[str]] = None,
        environment_variables: Optional[List[EnvironmentVariable]] = None,
        uploaded_files: Optional[List[UploadedFile]] = None,
        is_public: Optional[bool] = None,
        public_tags: Optional[List[str]] = None,
        public_at: Optional[str] = None,
        creator_id: Optional[str] = None,
        creator_username: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update an existing vMCP configuration.

        Only provided fields will be updated; None values are ignored.

        Args:
            vmcp_id: vMCP identifier to update
            name: Optional new display name
            description: Optional new description
            system_prompt: Optional new system prompt configuration
            vmcp_config: Optional new vMCP configuration
            custom_prompts: Optional new custom prompts list
            custom_tools: Optional new custom tools list
            custom_context: Optional new context list
            custom_resources: Optional new custom resources list
            custom_resource_templates: Optional new custom resource templates list
            custom_resource_uris: Optional new custom resource URIs list
            environment_variables: Optional new environment variables list
            uploaded_files: Optional new uploaded files list
            is_public: Optional public sharing flag
            public_tags: Optional tags for public sharing
            public_at: Optional timestamp for public sharing
            creator_id: Optional creator user ID
            creator_username: Optional creator username
            metadata: Optional metadata dictionary

        Returns:
            True if update successful, False otherwise
        """
        try:
            # Convert Pydantic objects to dictionaries for compatibility
            if system_prompt and hasattr(system_prompt, 'dict'):
                system_prompt = system_prompt.dict()
            if vmcp_config and hasattr(vmcp_config, 'dict'):
                vmcp_config = vmcp_config.dict()
            if custom_prompts:
                custom_prompts = [prompt.dict() if hasattr(prompt, 'dict') else prompt for prompt in custom_prompts]
            if custom_tools:
                custom_tools = [tool.dict() if hasattr(tool, 'dict') else tool for tool in custom_tools]
            if custom_resources:
                custom_resources = [resource.dict() if hasattr(resource, 'dict') else resource for resource in custom_resources]
            if environment_variables:
                environment_variables = [env.dict() if hasattr(env, 'dict') else env for env in environment_variables]
            if uploaded_files:
                uploaded_files = [file.dict() if hasattr(file, 'dict') else file for file in uploaded_files]

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
                existing_config.vmcp_config = vmcp_config
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
                # Keep list format in the config (for API compatibility)
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
                metadata.pop("url", None)  # Prevent URL overwrite
                existing_config.metadata.update(metadata)
                logger.info(f"Updated metadata to: {metadata}")

            # Recalculate the total number of tools, resources, resource templates, and prompts
            existing_vmcp_config = existing_config.vmcp_config or {}
            logger.info(f"Using existing_vmcp_config: {type(existing_vmcp_config)}")

            # Convert Pydantic object to dict if needed
            if hasattr(existing_vmcp_config, 'dict'):
                existing_vmcp_config = existing_vmcp_config.dict()

            # Safely calculate totals with proper fallbacks
            selected_tools = existing_vmcp_config.get('selected_tools', {}) or {}
            selected_resources = existing_vmcp_config.get('selected_resources', {}) or {}
            selected_resource_templates = existing_vmcp_config.get('selected_resource_templates', {}) or {}
            selected_prompts = existing_vmcp_config.get('selected_prompts', {}) or {}

            logger.info(f"Selected tools: {selected_tools}, Selected resources: {selected_resources}")

            total_tools = len(existing_config.custom_tools or []) + sum(
                len(x) for x in selected_tools.values() if isinstance(x, list)
            )
            total_resources = len(existing_config.custom_resources or []) + sum(
                len(x) for x in selected_resources.values() if isinstance(x, list)
            )
            total_resource_templates = len(existing_config.custom_resource_templates or []) + sum(
                len(x) for x in selected_resource_templates.values() if isinstance(x, list)
            )
            total_prompts = len(existing_config.custom_prompts or []) + sum(
                len(x) for x in selected_prompts.values() if isinstance(x, list)
            )

            logger.info(
                f"Calculated totals - Tools: {total_tools}, Resources: {total_resources}, "
                f"Resource Templates: {total_resource_templates}, Prompts: {total_prompts}"
            )

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

                # Also save environment variables to separate table if provided
                if environment_variables is not None:
                    # Convert list format to dict format for VMCPEnvironment table
                    env_dict = {var["name"]: var["value"] for var in environment_variables if "name" in var and "value" in var}
                    save_result = self._save_vmcp_environment(vmcp_id, env_dict)
                    logger.info(f"Saved environment variables for vMCP {vmcp_id}: {list(env_dict.keys())}")
            else:
                logger.error(f"Failed to update VMCP config: {vmcp_id}")

            return success

        except Exception as e:
            logger.error(f"Error updating VMCP config {vmcp_id}: {e}")
            return False

    @trace_method("[VMCPConfigManager]: Delete VMCP")
    def delete_vmcp(self, vmcp_id: str) -> Dict[str, Any]:
        """
        Delete a vMCP configuration and handle all cleanup.

        Args:
            vmcp_id: vMCP identifier to delete

        Returns:
            Dictionary with success status and message
        """
        try:
            success = self.storage.delete_vmcp(vmcp_id)
            if success:
                return {
                    "success": True,
                    "message": f"Successfully deleted {vmcp_id}"
                }
            else:
                return {
                    "success": False,
                    "message": f"vMCP '{vmcp_id}' not found or could not be deleted"
                }

        except Exception as e:
            logger.error(f"Error deleting vMCP {vmcp_id}: {e}")
            return {
                "success": False,
                "message": f"Failed to delete vMCP: {str(e)}"
            }

    def _get_vmcp_type(self, vmcp_config: VMCPConfig) -> str:
        """
        Determine the type of vMCP for proper cleanup.

        Args:
            vmcp_config: VMCPConfig object to check

        Returns:
            "public", "wellknown", or "private"
        """
        if vmcp_config.is_public:
            return "public"
        elif vmcp_config.is_wellknown:
            return "wellknown"
        else:
            return "private"

    # =========================================================================
    # Jinja2 Template Processing
    # =========================================================================

    def _is_jinja_template(self, text: str) -> bool:
        """
        Check if text contains Jinja2 patterns (after @param variables have been substituted).

        Args:
            text: Text to check for Jinja2 patterns

        Returns:
            True if text contains valid Jinja2 template syntax, False otherwise
        """
        import re

        # Check for Jinja2 patterns
        jinja_patterns = [
            r'\{\{[^}]*\}\}',  # Variable: {{ var }}
            r'\{%[^%]*%\}',    # Statement: {% if %}
            r'\{#[^#]*#\}'     # Comment: {# comment #}
        ]

        has_jinja_patterns = any(re.search(pattern, text) for pattern in jinja_patterns)

        if not has_jinja_patterns:
            logger.info("No Jinja2 patterns found in text")
            return False

        # Validate Jinja2 syntax
        try:
            self.jinja_env.parse(text)
            logger.info("Valid Jinja2 template detected")
            return True
        except Exception as e:
            logger.info(f"Jinja2 syntax validation failed: {e}")
            return False

    def _preprocess_jinja_to_regex(
        self,
        text: str,
        arguments: Dict[str, Any],
        environment_variables: Dict[str, Any]
    ) -> str:
        """
        Convert Jinja2 templates to plain text for existing regex system.

        Renders Jinja2 templates with provided arguments and environment variables.
        Falls back to original text if rendering fails.

        Args:
            text: Text potentially containing Jinja2 templates
            arguments: Dictionary of argument values for template rendering
            environment_variables: Dictionary of environment variables for template rendering

        Returns:
            Rendered text if Jinja2 template, otherwise original text
        """
        if not self._is_jinja_template(text):
            logger.info("Not a Jinja2 template")
            return text

        try:
            # Create Jinja2 template
            template = self.jinja_env.from_string(text)

            # Prepare context with both direct access and namespaced access
            context = {
                **arguments,
                **environment_variables,
                'param': arguments,
                'config': environment_variables,
            }

            # Render the template to get final text
            rendered_text = template.render(**context)
            logger.info("Jinja2 template rendered successfully")
            return rendered_text

        except Exception as e:
            logger.warning(f"Jinja2 preprocessing failed, using original text: {e}")
            return text

    # =========================================================================
    # Protocol Delegation - MCP List Operations
    # =========================================================================

    @trace_method("[VMCPConfigManager]: List Tools")
    async def tools_list(self) -> List[Tool]:
        """
        List all tools available in the vMCP.

        Delegates to protocol_handler.tools_list() which aggregates:
        - Tools from selected MCP servers
        - Custom tools defined in the vMCP
        - Tool overrides and widget attachments

        Returns:
            List of Tool objects from all sources
        """
        return await protocol_handler.tools_list(
            storage=self.storage,
            vmcp_id=self.vmcp_id,
            user_id=self.user_id,
            mcp_config_manager=self.mcp_config_manager
        )

    @trace_method("[VMCPConfigManager]: List Resources")
    async def resources_list(self) -> List[Resource]:
        """
        List all resources available in the vMCP.

        Delegates to protocol_handler.resources_list() which aggregates:
        - Resources from selected MCP servers
        - Custom resources defined in the vMCP
        - Uploaded files as resources
        - Widget resources

        Returns:
            List of Resource objects from all sources
        """
        return await protocol_handler.resources_list(
            storage=self.storage,
            vmcp_id=self.vmcp_id,
            user_id=self.user_id,
            mcp_config_manager=self.mcp_config_manager
        )

    @trace_method("[VMCPConfigManager]: List Resource Templates")
    async def resource_templates_list(self) -> List[ResourceTemplate]:
        """
        List all resource templates available in the vMCP.

        Delegates to protocol_handler.resource_templates_list() which aggregates:
        - Resource templates from selected MCP servers
        - Custom resource templates defined in the vMCP

        Returns:
            List of ResourceTemplate objects from all sources
        """
        return await protocol_handler.resource_templates_list(
            storage=self.storage,
            vmcp_id=self.vmcp_id,
            user_id=self.user_id,
            mcp_config_manager=self.mcp_config_manager
        )

    @trace_method("[VMCPConfigManager]: List Prompts")
    async def prompts_list(self) -> List[Prompt]:
        """
        List all prompts available in the vMCP.

        Delegates to protocol_handler.prompts_list() which aggregates:
        - Prompts from selected MCP servers
        - Custom prompts defined in the vMCP
        - Default system prompts

        Returns:
            List of Prompt objects from all sources
        """
        return await protocol_handler.prompts_list(
            storage=self.storage,
            vmcp_id=self.vmcp_id,
            user_id=self.user_id,
            mcp_config_manager=self.mcp_config_manager
        )

    # =========================================================================
    # Execution Delegation - Tool, Prompt, and Resource Template Execution
    # =========================================================================

    @trace_method("[VMCPConfigManager]: Call Tool")
    async def call_tool(
        self,
        vmcp_tool_call_request: VMCPToolCallRequest,
        connect_if_needed: bool = True,
        return_metadata: bool = False
    ) -> Dict[str, Any]:
        """
        Execute a tool by name with provided arguments.

        Delegates to execution_core.call_tool() which handles:
        - Custom tools via custom_tool_engines
        - Server tools via MCP client connections
        - Widget support for UI rendering
        - Background logging of tool calls

        Args:
            vmcp_tool_call_request: VMCPToolCallRequest object containing tool name and arguments
            connect_if_needed: Whether to connect to MCP servers if needed
            return_metadata: Whether to return metadata along with result

        Returns:
            Dict[str, Any] with tool execution results
        """
        return await execution_core.call_tool(
            storage=self.storage,
            mcp_client_manager=self.mcp_client_manager,
            vmcp_id=self.vmcp_id,
            user_id=self.user_id,
            vmcp_tool_call_request=vmcp_tool_call_request,
            call_custom_tool_func=self.call_custom_tool,
            log_vmcp_operation_func=self.log_vmcp_operation,
            connect_if_needed=connect_if_needed,
            return_metadata=return_metadata
        )

    @trace_method("[VMCPConfigManager]: Get Prompt")
    async def get_prompt(
        self,
        prompt_id: str,
        arguments: Optional[Dict[str, Any]] = None,
        connect_if_needed: bool = True
    ) -> GetPromptResult:
        """
        Execute a prompt by ID with provided arguments.

        Delegates to execution_core.get_prompt() which handles:
        - Default system prompts
        - Server prompts via MCP client connections
        - Custom prompts via custom_tool_engines
        - Background logging of prompt requests

        Args:
            prompt_id: Prompt identifier
            arguments: Optional dictionary of prompt arguments

        Returns:
            GetPromptResult with rendered prompt messages
        """
        return await execution_core.get_prompt(
            storage=self.storage,
            mcp_client_manager=self.mcp_client_manager,
            vmcp_id=self.vmcp_id,
            user_id=self.user_id,
            prompt_id=prompt_id,
            get_custom_prompt_func=self.get_custom_prompt,
            call_custom_tool_func=self.call_custom_tool,
            log_vmcp_operation_func=self.log_vmcp_operation,
            arguments=arguments,
            connect_if_needed=connect_if_needed
        )

    @trace_method("[VMCPConfigManager]: Get System Prompt")
    async def get_system_prompt(
        self,
        system_prompt_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate system prompt with variable substitution.

        Delegates to execution_core.get_system_prompt() which handles:
        - Variable substitution from environment variables
        - Jinja2 template rendering
        - Fallback to default system prompt

        Args:
            system_prompt_config: Optional system prompt configuration
                                Contains 'text' and 'variables' keys

        Returns:
            Rendered system prompt string
        """
        return await execution_core.get_system_prompt(
            storage=self.storage,
            vmcp_id=self.vmcp_id,
            jinja_env=self.jinja_env,
            system_prompt_config=system_prompt_config
        )

    @trace_method("[VMCPConfigManager]: Get Resource Template")
    async def get_resource_template(
        self,
        uri: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> ReadResourceResult:
        """
        Execute a resource template by URI with provided arguments.

        Delegates to execution_core.get_resource_template() which handles:
        - Server resource templates via MCP client connections
        - Parameter interpolation
        - Background logging of resource template requests

        Args:
            uri: Resource template URI
            arguments: Optional dictionary of template arguments

        Returns:
            ReadResourceResult with resource template contents
        """
        return await execution_core.get_resource_template(
            storage=self.storage,
            vmcp_id=self.vmcp_id,
            user_id=self.user_id,
            mcp_client_manager=self.mcp_client_manager,
            logging_config=self.logging_config,
            jinja_env=self.jinja_env,
            uri=uri,
            arguments=arguments
        )

    # =========================================================================
    # Resource Management Delegation
    # =========================================================================

    @trace_method("[VMCPConfigManager]: Get Resource")
    async def get_resource(self, uri: str, connect_if_needed: bool = True) -> ReadResourceResult:
        """
        Fetch a resource by URI.

        Delegates to resource_manager.get_resource() which handles:
        - Server resources via MCP client connections
        - Custom uploaded file resources
        - Widget resources
        - Resource content type conversion

        Args:
            uri: Resource URI to fetch
            connect_if_needed: Whether to connect to MCP servers if needed

        Returns:
            ReadResourceResult with resource contents
        """
        return await resource_manager.get_resource(
            storage=self.storage,
            vmcp_id=self.vmcp_id,
            user_id=self.user_id,
            mcp_client_manager=self.mcp_client_manager,
            log_operation_func=self.log_vmcp_operation,
            resource_id=uri,
            connect_if_needed=connect_if_needed
        )

    @trace_method("[VMCPConfigManager]: Add Resource")
    def add_resource(self, vmcp_id: str, resource_data: Dict[str, Any]) -> bool:
        """
        Add a resource to the vMCP.

        Delegates to resource_manager.add_resource().

        Args:
            vmcp_id: vMCP identifier
            resource_data: Resource data dictionary containing:
                - id: Resource identifier
                - name: Resource name
                - uri: Resource URI
                - content: Resource content (for uploads)
                - mime_type: MIME type

        Returns:
            True if successful, False otherwise
        """
        return resource_manager.add_resource(
            storage=self.storage,
            vmcp_id=vmcp_id,
            resource_data=resource_data
        )

    @trace_method("[VMCPConfigManager]: Update Resource")
    def update_resource(self, vmcp_id: str, resource_data: Dict[str, Any]) -> bool:
        """
        Update a resource in the vMCP.

        Delegates to resource_manager.update_resource().

        Args:
            vmcp_id: vMCP identifier
            resource_data: Resource data dictionary with updated fields

        Returns:
            True if successful, False otherwise
        """
        return resource_manager.update_resource(
            storage=self.storage,
            vmcp_id=vmcp_id,
            resource_data=resource_data
        )

    @trace_method("[VMCPConfigManager]: Delete Resource")
    def delete_resource(self, vmcp_id: str, resource_data: Dict[str, Any]) -> bool:
        """
        Delete a resource from the vMCP.

        Delegates to resource_manager.delete_resource().

        Args:
            vmcp_id: vMCP identifier
            resource_data: Resource data dictionary containing resource ID

        Returns:
            True if successful, False otherwise
        """
        return resource_manager.delete_resource(
            storage=self.storage,
            vmcp_id=vmcp_id,
            resource_data=resource_data
        )

    # =========================================================================
    # Server Management Delegation
    # =========================================================================

    def install_public_vmcp(
        self,
        public_vmcp: Dict[str, Any],
        server_conflicts: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Install a public vMCP to the current user's account.

        Delegates to server_manager.install_public_vmcp() which handles:
        - Server conflict resolution
        - Server installation from vMCP config
        - vMCP creation with resolved server references
        - Install count tracking

        Args:
            public_vmcp: Public vMCP data dictionary
            server_conflicts: Dictionary mapping server names to resolution actions:
                - "use_existing": Use existing server with same name
                - "install_new": Install as new server with modified name

        Returns:
            Dictionary with installation result:
                - success: Boolean indicating success/failure
                - installed_vmcp_id: Created vMCP ID (if successful)
                - server_installations: List of server installation results
                - error: Error message (if failed)
        """
        return server_manager.install_public_vmcp(
            storage=self.storage,
            user_id=self.user_id,
            mcp_config_manager=self.mcp_config_manager,
            create_vmcp_config_func=self.create_vmcp_config,
            public_vmcp=public_vmcp,
            server_conflicts=server_conflicts
        )

    def update_vmcp_server(
        self,
        vmcp_id: str,
        server_config: 'MCPServerConfig',
        old_config: Dict[str, Any] = None,
        new_config: Dict[str, Any] = None
    ):
        """
        Update vMCP's server configuration.

        Can be called in two ways:
        1. update_vmcp_server(vmcp_id, server_config) - Updates a specific server's config within the vMCP
        2. update_vmcp_server(vmcp_id, None, old_config, new_config) - Tracks vMCP config changes

        Args:
            vmcp_id: vMCP identifier
            server_config: Server configuration to update (for mode 1)
            old_config: Previous vMCP configuration (for mode 2)
            new_config: New vMCP configuration (for mode 2)
        """
        # Mode 1: Update specific server config (original behavior from onefile)
        if server_config is not None:
            from vmcp.mcps.models import MCPServerConfig
            vmcp_config = self.load_vmcp_config(specific_vmcp_id=vmcp_id)
            server_id = server_config.server_id
            if vmcp_config:
                # Convert vmcp_config to dict if it's a Pydantic object
                vmcp_config_dict = vmcp_config.vmcp_config.dict() if hasattr(vmcp_config.vmcp_config, 'dict') else vmcp_config.vmcp_config
                selected_servers = vmcp_config_dict.get('selected_servers', [])
                for idx, server in enumerate(selected_servers):
                    if server.get('server_id') == server_id:
                        vmcp_config_dict['selected_servers'][idx] = server_config.to_dict()
                        
                        # BUGFIX: Save the complete vMCP configuration, not just vmcp_config part
                        # Get the complete vmcp_config as dict first
                        complete_vmcp_dict = vmcp_config.to_dict() if hasattr(vmcp_config, 'to_dict') else vmcp_config.__dict__
                        # Update only the vmcp_config part
                        complete_vmcp_dict['vmcp_config'] = vmcp_config_dict
                        # Save the complete configuration to preserve system_prompt, custom_prompts, custom_tools, etc.
                        self.storage.save_vmcp(vmcp_id, complete_vmcp_dict)
                        break
            return

        # Mode 2: Track vMCP config changes (refactored behavior)
        if old_config is not None and new_config is not None:
            server_manager.update_vmcp_server(
                storage=self.storage,
                mcp_config_manager=self.mcp_config_manager,
                vmcp_id=vmcp_id,
                old_config=old_config,
            new_config=new_config
        )

    # =========================================================================
    # Template Parser Delegation
    # =========================================================================

    async def _call_tool_wrapper(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Wrapper function to adapt call_tool signature for template parser.
        
        Template parser calls with (tool_name, arguments), but call_tool expects
        VMCPToolCallRequest object. This wrapper converts the arguments.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments dictionary
            
        Returns:
            Tool execution result
        """
        vmcp_tool_call_request = VMCPToolCallRequest(
            tool_name=tool_name,
            arguments=arguments
        )
        return await self.call_tool(vmcp_tool_call_request, connect_if_needed=True, return_metadata=False)

    async def _parse_vmcp_text(
        self,
        text: str,
        config_item: dict,
        arguments: Dict[str, Any],
        environment_variables: Dict[str, Any],
        is_prompt: bool = False
    ) -> Tuple[str, Optional[Any]]:
        """
        Parse vMCP text with variable substitution and special directives.

        Delegates to template_parser.parse_vmcp_text() which handles:
        - @config.VAR substitution (environment variables)
        - @param.VAR substitution (arguments)
        - @resource.server.name fetching
        - @tool.server.tool() execution
        - @prompt.server.prompt() execution
        - Jinja2 template rendering

        Args:
            text: Text containing vMCP directives and variables
            config_item: Configuration item containing the text
            arguments: Dictionary of argument values
            environment_variables: Dictionary of environment variables
            is_prompt: Whether this is a prompt (affects processing)

        Returns:
            Tuple of (parsed_text, resource_content)
        """
        result, resource_content = await template_parser.parse_vmcp_text(
            text=text,
            config_item=config_item,
            arguments=arguments,
            environment_variables=environment_variables,
            jinja_env=self.jinja_env,
            get_resource_func=self.get_resource,
            call_tool_func=self._call_tool_wrapper,
            get_prompt_func=self.get_prompt,
            is_prompt=is_prompt
        )
        return result, resource_content

    # =========================================================================
    # Logger Delegation
    # =========================================================================

    async def log_vmcp_operation(
        self,
        operation_type: str,
        operation_id: str,
        arguments: Optional[Dict[str, Any]],
        result: Optional[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]]
    ) -> None:
        """
        Log a vMCP operation for analytics and debugging.

        Delegates to logger.log_vmcp_operation() which handles background
        logging of operations including tool calls, resource requests, and
        prompt requests.

        Args:
            operation_type: Type of operation (e.g., "tool_call", "resource_request")
            operation_id: Unique identifier for the operation
            arguments: Optional dictionary of operation arguments
            result: Optional dictionary of operation results
            metadata: Optional dictionary of additional metadata
        """
        vmcp_config = self.storage.load_vmcp_config(self.vmcp_id)
        await vmcp_logger.log_vmcp_operation(
            storage=self.storage,
            vmcp_id=self.vmcp_id,
            vmcp_config=vmcp_config,
            user_id=self.user_id,
            logging_config=self.logging_config,
            operation_type=operation_type,
            operation_id=operation_id,
            arguments=arguments,
            result=result,
            metadata=metadata
        )

    # =========================================================================
    # Custom Tool Engine Delegation
    # =========================================================================

    async def get_custom_prompt(
        self,
        prompt_id: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> GetPromptResult:
        """
        Execute a custom prompt by ID.

        Delegates to custom_tool_engines.prompt_tool.get_custom_prompt()
        which handles execution of custom prompts defined in the vMCP.

        Args:
            prompt_id: Custom prompt identifier
            arguments: Optional dictionary of prompt arguments

        Returns:
            GetPromptResult with rendered prompt messages
        """
        return await prompt_tool.get_custom_prompt(
            prompt_id=prompt_id,
            storage=self.storage,
            vmcp_id=self.vmcp_id,
            parse_vmcp_text_func=self._parse_vmcp_text,
            arguments=arguments
        )

    async def call_custom_tool(
        self,
        tool_id: str,
        arguments: Optional[Dict[str, Any]] = None,
        tool_as_prompt: bool = False
    ) -> CallToolResult:
        """
        Execute a custom tool by ID.

        Delegates to custom_tool_engines.prompt_tool.call_custom_tool()
        which handles execution of custom tools defined in the vMCP.

        Args:
            tool_id: Custom tool identifier
            arguments: Optional dictionary of tool arguments
            tool_as_prompt: If True, treat tool as a prompt and return prompt-style result

        Returns:
            CallToolResult with tool execution results
        """
        return await prompt_tool.call_custom_tool(
            tool_id=tool_id,
            storage=self.storage,
            vmcp_id=self.vmcp_id,
            execute_python_tool_func=python_tool.execute_python_tool,
            execute_http_tool_func=http_tool.execute_http_tool,
            parse_vmcp_text_func=self._parse_vmcp_text,
            arguments=arguments,
            tool_as_prompt=tool_as_prompt
        )
