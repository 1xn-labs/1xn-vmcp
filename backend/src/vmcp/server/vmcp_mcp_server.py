"""
VMCPServer - MCP Protocol Server Implementation
================================================

This module contains the VMCPServer class which handles MCP protocol operations.
It extends FastMCP and provides protocol handlers for tools, resources, prompts, etc.
"""

import re
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.lowlevel import NotificationOptions
from mcp.types import (
    CallToolRequest,
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    ReadResourceRequest,
    Resource,
    ResourceTemplate,
    ServerResult,
    TextContent,
    Tool,
)

from vmcp.vmcps.vmcp_config_manager import VMCPConfigManager
from vmcp.config import settings
from vmcp.core.services import TokenInfo, get_jwt_service, get_user_context_class
from vmcp.server.mcp_dependencies import get_http_request
from vmcp.server.tool_descriptions import CREATE_PROMPT_HELPER_TEXT, UPLOAD_PROMPT_DESCRIPTION
from vmcp.utilities.logging import get_logger
from vmcp.utilities.tracing import trace_method
from vmcp.vmcps.models import VMCPToolCallRequest



# Setup centralized logging for MCP server with span correlation
logger = get_logger("VMCPServer")


from vmcp.server.vmcp_session_manager import VMCPSessionManager


class VMCPServer(FastMCP):
    """
    MCP Protocol Server for vMCP.

    Handles MCP protocol operations including:
    - Tool listing and execution
    - Resource listing and reading
    - Prompt listing and retrieval
    - Resource template listing
    - Session management via VMCPSessionManager
    """

    def __init__(self, name: str):
        logger.info(f"[VMCPServer] Initializing: {name}")
        self._vmcp_session_manager: VMCPSessionManager

        # Configure streamable HTTP path to be root so it works when mounted
        log_level_str = settings.log_level.upper()
        # Validate log level is one of the allowed values
        valid_log_levels: tuple[Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], ...] = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = log_level_str if log_level_str in valid_log_levels else 'INFO'  # type: ignore
        #super().__init__(name, streamable_http_path="/mcp", instructions="1xn v(irtual)MCP server", log_level=log_level, debug=settings.debug)
        super().__init__(name, streamable_http_path="/mcp", instructions="1xn v(irtual)MCP server")

        self._mcp_server.create_initialization_options(
            notification_options=NotificationOptions(prompts_changed=True, resources_changed=True, tools_changed=True),
            experimental_capabilities={"1xn": {"vmcp": True}})

        # vmcp server is completely stateless
        # All managers will be created per user request
        logger.info("[VMCPServer] Initialization complete (stateless)")

    def streamable_http_app(self):
        """
        Override to use our custom VMCPSessionManager instead of the default one.
        This ensures proper stdio cleanup when sessions end.
        """
         # Create our custom session manager (lazy initialization)
        if self._session_manager is None:
            self._session_manager = VMCPSessionManager(
                app=self._mcp_server,
                event_store=self._event_store,
                json_response=self.settings.json_response,
                stateless=False,
            )
            logger.info("[VMCPServer] Created custom VMCPSessionManager with session-aware stdio cleanup")


        return super().streamable_http_app()


    async def get_user_context_vmcp_server(self):
        """Build dependencies for the current request with user context"""
        try:
            # Get services from registry
            jwt_service = get_jwt_service()
            UserContext = get_user_context_class()

            # Debug: Log all headers to see what's available
            request = get_http_request()
            logger.debug(f"[VMCPServer] DEBUG: All headers during tool call: {dict(request.headers)}")
            auth_header = request.headers.get('Authorization', '')
            logger.debug(f"[VMCPServer] DEBUG: Authorization header: '{auth_header}'")
            token = auth_header.replace('Bearer ', '').strip()
            logger.debug(f"[VMCPServer] DEBUG: Extracted token: '{token[:20] if token else 'EMPTY'}...')")

            # Extract and normalize token info
            try:
                raw_info = jwt_service.extract_token_info(token)
                token_info = TokenInfo(
                    user_id=raw_info.get('user_id', ''),
                    username=raw_info.get('username', ''),
                    email=raw_info.get('email'),
                    client_id=raw_info.get('client_id'),
                    client_name=raw_info.get('client_name'),
                    token=token
                )
            except (ValueError, KeyError) as e:
                logger.warning(f"[VMCPServer] Invalid token info: {e}")
                return None

            vmcp_name = get_http_request().headers.get('vmcp-name', 'unknown')
            vmcp_username = get_http_request().headers.get('vmcp-username', 'unknown')

            if vmcp_username == "private":
                vmcp_username = None

            # Extract normalized user information
            user_id = token_info.user_id
            user_name = token_info.username
            user_email = token_info.email
            client_id = token_info.client_id
            client_name = token_info.client_name

            # Get agent name from session mapping (session-based, not token-based)
            agent_name = self._mcp_server.request_context.session.client_params.clientInfo.name
            logger.debug(f"[VMCPServer] Client ctx: {agent_name}")

            session_id = get_http_request().headers.get('mcp-session-id')

            if session_id:
                # Create lightweight UserContext (pure identity, no manager)
                user_context = UserContext(
                    user_id=user_id,
                    user_email=user_email,
                    username=user_name,
                    token=token,
                    vmcp_name=vmcp_name,
                )

                # Delegate VMCPConfigManager creation/retrieval to session manager
                manager = self._session_manager.get_manager(session_id)
                if manager:
                    user_context.vmcp_config_manager = manager
                    logger.info(f"[VMCPServer] Re-using VMCPConfigManager for user_id: {user_id}, vmcp_name: {vmcp_name}")
                    logger.debug(f"[VMCPServer] Existing MCPClientManager ID: {id(user_context.vmcp_config_manager.mcp_client_manager)}")
                else:
                    # Create new manager via session manager
                    user_context.vmcp_config_manager = self._session_manager.create_manager(
                        session_id=session_id,
                        user_id=user_id,
                        vmcp_name=vmcp_name
                    )
                    logger.info(f"[VMCPServer] Created new VMCPConfigManager for user_id: {user_id}, vmcp_name: {vmcp_name}")

                # Set downstream session for notification forwarding
                # This allows upstream MCP notifications to be forwarded to the downstream client
                try:
                    server_session = self._mcp_server.request_context.session
                    if user_context.vmcp_config_manager and user_context.vmcp_config_manager.mcp_client_manager:
                        user_context.vmcp_config_manager.mcp_client_manager.set_downstream_session(server_session)
                        logger.debug(f"[VMCPServer] [NOTIFICATION] Set downstream session for notification forwarding")
                except Exception as e:
                    logger.debug(f"[VMCPServer] [NOTIFICATION] Could not set downstream session: {e}")

                if agent_name:
                    logger.debug(f"[VMCPServer] Found agent name for session {session_id[:20]}...: {agent_name}")
                else:
                    logger.debug(f"[VMCPServer] No agent mapping found for session {session_id[:20]}...")
            else:
                logger.debug("[VMCPServer] No mcp-session-id in headers - agent name unavailable")
                raise ValueError("No session ID provided in headers")

            # Add vMCP-specific attributes to the user context
            user_context.vmcp_name_header = vmcp_name
            user_context.vmcp_username_header = vmcp_username
            user_context.client_id = client_id
            user_context.client_name = client_name
            user_context.agent_name = agent_name

            # Update vmcp_config_manager logging_config if it exists
            # This ensures vmcp_stats table logs the correct agent name instead of default "1xn_web_client"
            if user_context.vmcp_config_manager and agent_name:
                user_context.vmcp_config_manager.logging_config = {
                    "agent_name": agent_name,
                    "agent_id": agent_name,
                    "client_id": client_id or "unknown"
                }
                logger.debug(f"[VMCPServer] Updated vmcp_config_manager logging_config with agent_name: {agent_name}")

            # The UserContext now has vmcp_config_manager initialized
            return user_context
        except Exception as e:
            logger.error(f"[VMCPServer] Traceback: {traceback.format_exc()}")
            logger.error(f"[VMCPServer] Error building dependencies: {e}")
            return None

    async def _execute_upload_prompt(self, arguments: dict) -> dict:
        """Create a custom prompt in the active vMCP. This tool allows users to create new custom prompts that will be available in their current vMCP configuration."""
        try:
            prompt_json = arguments.get("prompt_json")

            if not prompt_json:
                return {"status": "error", "message": "Missing required argument: prompt_json"}

            if not isinstance(prompt_json, dict):
                return {"status": "error", "message": "prompt_json must be a JSON object"}

            # Extract required fields from prompt_json
            name = prompt_json.get("name")
            description = prompt_json.get("description", "")  # Optional, default to empty string
            prompt_text = prompt_json.get("text")
            variables = prompt_json.get("variables", [])

            if not all([name, prompt_text]):
                return {"status": "error", "message": "prompt_json must contain name and text fields"}

            # Validate variables format if provided
            if variables and not isinstance(variables, list):
                return {"status": "error", "message": "Variables must be a list of objects"}

            for var in variables:
                if not isinstance(var, dict):
                    return {"status": "error", "message": "Each variable must be an object"}
                if not all(key in var for key in ["name", "description", "required"]):
                    return {"status": "error", "message": "Each variable must have name, description, and required fields"}
                if not isinstance(var["required"], bool):
                    return {"status": "error", "message": "Variable 'required' field must be a boolean"}

            # Get user context
            deps = await self.get_user_context_vmcp_server()
            if deps is None:
                return {"status": "error", "message": "No user context available"}

            # Get the active vMCP manager
            if deps.vmcp_config_manager:
                active_vmcp_id = deps.vmcp_config_manager.vmcp_id
                vmcp_manager = deps.vmcp_config_manager
            else:
                return {"status": "error", "message": "No vMCP manager available"}

            if not active_vmcp_id:
                return {"status": "error", "message": "No active vMCP found"}

            # Load current vMCP config
            vmcp_config = vmcp_manager.load_vmcp_config(active_vmcp_id)
            if not vmcp_config:
                return {"status": "error", "message": f"vMCP config not found for ID: {active_vmcp_id}"}

            # Validate prompt name and handle conflicts
            final_name = name
            existing_prompts = vmcp_config.custom_prompts or []
            existing_names = {p.get("name") for p in existing_prompts}

            counter = 1
            while final_name in existing_names:
                final_name = f"{name}_{counter}"
                counter += 1

            # Create the new prompt
            new_prompt = {
                "name": final_name,
                "description": description,
                "text": prompt_text,
                "variables": variables  # Use the provided variables
            }

            # Add to existing custom prompts
            updated_custom_prompts = list(existing_prompts)
            updated_custom_prompts.append(new_prompt)

            # Update the vMCP config with new custom prompts
            success = vmcp_manager.update_vmcp_config(
                vmcp_id=active_vmcp_id,
                custom_prompts=updated_custom_prompts
            )

            if success:
                logger.info(f"[VMCPServer] Created custom prompt '{final_name}' in vMCP {active_vmcp_id}")
                return {
                    "status": "success",
                    "prompt_name": final_name,
                    "message": f"Custom prompt '{final_name}' created successfully"
                }
            else:
                return {"status": "error", "message": "Failed to save vMCP configuration"}

        except Exception as e:
            logger.error(f"[VMCPServer] Error creating custom prompt: {e}")
            logger.error(f"[VMCPServer] Full traceback: {traceback.format_exc()}")
            return {"status": "error", "message": f"Failed to create prompt: {str(e)}"}

    def _setup_handlers(self) -> None:
        """Set up core MCP protocol handlers."""
        logger.debug("[VMCPServer] Setting up MCP protocol handlers...")

        self._mcp_server.list_tools()(self.proxy_list_tools)
        logger.debug("[VMCPServer] list_tools handler registered")

        # Note: we disable the lowlevel server's input validation.
        # FastMCP does ad hoc conversion of incoming data before validating -
        # for now we preserve this for backwards compatibility.
        #self._mcp_server.call_tool(validate_input=True)(self.proxy_call_tool)
        self._mcp_server.request_handlers[CallToolRequest] = self.root_proxy_call_tool
        logger.debug("[VMCPServer] call_tool handler registered")

        self._mcp_server.list_resources()(self.proxy_list_resources)
        logger.debug("[VMCPServer] list_resources handler registered")

        self._mcp_server.request_handlers[ReadResourceRequest] = self.proxy_read_resource
        # self._mcp_server.read_resource()(self.proxy_read_resource)
        logger.debug("[VMCPServer] read_resource handler registered")

        self._mcp_server.list_prompts()(self.proxy_list_prompts)
        logger.debug("[VMCPServer] list_prompts handler registered")

        self._mcp_server.get_prompt()(self.proxy_get_prompt)
        logger.debug("[VMCPServer] get_prompt handler registered")

        self._mcp_server.list_resource_templates()(self.proxy_list_resource_templates)
        logger.debug("[VMCPServer] list_resource_templates handler registered")

        logger.debug("[VMCPServer] All MCP protocol handlers registered successfully")

    @trace_method("[VMCPServer]: List Tools")
    async def proxy_list_tools(self) -> List[Tool]:
        """Aggregate tools from all connected servers filtered by active agent or vMCP"""
        logger.debug("=" * 60)
        logger.debug("[VMCPServer] proxy_list_tools called")
        logger.debug("=" * 60)

        # Build dependencies from current request
        deps = await self.get_user_context_vmcp_server()
        if deps is None:
            logger.warning("[VMCPServer] No dependencies available (no valid token) - returning empty tools list")
            return []

        # Log user context
        user_id = getattr(deps, 'user_id', 'unknown')
        client_id = getattr(deps, 'client_id', 'unknown')
        agent_name = getattr(deps, 'agent_name', 'unknown')
        logger.info(f"[VMCPServer] Listing tools for user {user_id}, client {client_id}, agent {agent_name}")

        # Get vMCP tools
        if deps.vmcp_config_manager:
            tools = await deps.vmcp_config_manager.tools_list()
        else:
            tools = []
        logger.info(f"[VMCPServer] Found {len(tools)} vMCP tools")

        # Create preset tools manually
        if not(deps.vmcp_username_header and deps.vmcp_username_header.startswith("@")):
            preset_tools = [
                Tool(
                    name="upload_prompt",
                    description=UPLOAD_PROMPT_DESCRIPTION,
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "prompt_json": {
                                "type": "object",
                                "description": "JSON object containing the prompt configuration",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Name for the new prompt"
                                    },
                                    "description": {
                                        "type": "string",
                                        "description": "Description of what the prompt does (optional)"
                                    },
                                    "text": {
                                        "type": "string",
                                        "description": "The actual prompt text content. Use {variableName} format to reference variables (e.g., {username})"
                                    },
                                    "variables": {
                                        "type": "array",
                                        "description": "Optional list of variables that can be used in the prompt text",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "name": {
                                                    "type": "string",
                                                    "description": "Variable name (referenced as @var.name in prompt text)"
                                                },
                                                "description": {
                                                    "type": "string",
                                                    "description": "Description of what this variable represents"
                                                },
                                                "required": {
                                                    "type": "boolean",
                                                    "description": "Whether this variable is required when using the prompt"
                                                }
                                            },
                                            "required": ["name", "description", "required"]
                                        }
                                    }
                                },
                                "required": ["name", "text"]
                            }
                        },
                        "required": ["prompt_json"]
                    }
                )
            ]
        else:
            preset_tools = []
        logger.info(f"[VMCPServer] Found {len(preset_tools)} preset tools")

        # Combine preset tools with vMCP tools
        all_tools = preset_tools + tools

        logger.info(f"[VMCPServer] Returning {len(all_tools)} total tools ({len(preset_tools)} preset + {len(tools)} vMCP)")
        # Tools are already Tool objects, no conversion needed
        logger.debug(f"[VMCPServer] Returning {len(tools)} tools")
        logger.debug("=" * 60)

        # Log tool details
        for i, tool in enumerate(all_tools):
            tool_type = "PRESET" if i < len(preset_tools) else "vMCP"
            logger.debug(f"[VMCPServer] Tool {i+1} [{tool_type}]: {tool.name} - {tool.description[:50] if tool.description else 'No description'}...")

        return all_tools

    @trace_method("[VMCPServer]: List Resources")
    async def proxy_list_resources(self) -> List[Resource]:
        """Aggregate resources from all connected servers filtered by active agent or vMCP"""
        logger.info("[VMCPServer] Listing resources from all connected servers...")

        # Build dependencies from current request
        deps = await self.get_user_context_vmcp_server()
        if deps is None:
            logger.warning("[VMCPServer] No dependencies available - returning empty resources list")
            return []

        # Log user context
        user_id = getattr(deps, 'user_id', 'unknown')
        client_id = getattr(deps, 'client_id', 'unknown')
        agent_name = getattr(deps, 'agent_name', 'unknown')
        logger.info(f"[VMCPServer] Listing resources for user {user_id}, client {client_id}, agent {agent_name}")

        if deps.vmcp_config_manager:
            resources = await deps.vmcp_config_manager.resources_list()
        else:
            resources = []

        return resources

    @trace_method("[VMCPServer]: List Resource Templates")
    async def proxy_list_resource_templates(self) -> List[ResourceTemplate]:
        """Aggregate resource templates from all connected servers filtered by active agent or vMCP"""
        logger.info("[VMCPServer] Listing resource templates from all connected servers...")

        # Build dependencies from current request
        deps = await self.get_user_context_vmcp_server()
        if deps is None:
            logger.warning("[VMCPServer] No dependencies available - returning empty resource templates list")
            return []

        # Log user context
        user_id = getattr(deps, 'user_id', 'unknown')
        client_id = getattr(deps, 'client_id', 'unknown')
        agent_name = getattr(deps, 'agent_name', 'unknown')
        logger.info(f"[VMCPServer] Listing resource templates for user {user_id}, client {client_id}, agent {agent_name}")

        if deps.vmcp_config_manager:
            resource_templates = await deps.vmcp_config_manager.resource_templates_list()
        else:
            resource_templates = []

        # Log resource template details
        for i, template in enumerate(resource_templates):
            logger.info(f"[VMCPServer] Resource Template {i+1}: {template.name} - {template.description[:50] if template.description else 'No description'}...")

        return resource_templates

    @trace_method("[VMCPServer]: List Prompts")
    async def proxy_list_prompts(self) -> List[Prompt]:
        """Aggregate prompts from all connected servers filtered by active agent or vMCP"""
        logger.debug("=" * 60)
        logger.debug("[VMCPServer] proxy_list_prompts called")
        logger.debug("=" * 60)
        logger.debug("[VMCPServer] Listing prompts from all connected servers...")

        # Build dependencies from current request
        deps = await self.get_user_context_vmcp_server()
        if deps is None:
            logger.warning("[VMCPServer] No dependencies available - returning empty prompts list")
            return []

        # Log user context
        user_id = getattr(deps, 'user_id', 'unknown')
        client_id = getattr(deps, 'client_id', 'unknown')
        agent_name = getattr(deps, 'agent_name', 'unknown')
        logger.info(f"[VMCPServer] Listing prompts for user {user_id}, client {client_id}, agent {agent_name}")

        if deps.vmcp_config_manager:
            prompts = await deps.vmcp_config_manager.prompts_list()
        else:
            prompts = []

        # Add upload_prompt_helper as a built-in prompt
        if not(deps.vmcp_username_header and deps.vmcp_username_header.startswith("@")):
            upload_prompt_helper_prompt = Prompt(
                name="upload_prompt_helper",
                description="Get helper text for creating custom prompts based on title and description",
                arguments=[
                    PromptArgument(
                        name="title",
                        description="Title for the prompt you want to create",
                        required=False
                    ),
                    PromptArgument(
                        name="description",
                        description="Description of what the prompt should do",
                        required=False
                    )
                ]
            )
            prompts.append(upload_prompt_helper_prompt)

        # Log prompt details
        for i, prompt in enumerate(prompts):
            logger.debug(f"[VMCPServer] Prompt {i+1}: {prompt.name} - {prompt.description[:50] if prompt.description else 'No description'}...")

        return prompts

    @trace_method("[VMCPServer]: Root Tool Call")
    async def root_proxy_call_tool(self, req: CallToolRequest):
        tool_name = req.params.name
        arguments = req.params.arguments or {}
        # Extract progress token from downstream client's request
        progress_token = None
        if req.params.meta and hasattr(req.params.meta, 'progressToken'):
            progress_token = req.params.meta.progressToken
        logger.debug(f"[VMCPServer] DEBUG root_proxy_call_tool: tool={tool_name}, arguments={arguments}, progress_token={progress_token}, types={[(k, type(v).__name__) for k, v in arguments.items()]}")
        result = await self.proxy_call_tool(tool_name, arguments, progress_token=progress_token)
        return result

    @trace_method("[VMCPServer]: Tool Call", operation="call_tool")
    async def proxy_call_tool(self, name: str, arguments: Dict[str, Any], progress_token: Optional[Any] = None) -> Any:
        """Route tool calls to appropriate server"""
        logger.debug("=" * 60)
        logger.debug("[VMCPServer] Tool call requested")
        logger.debug("=" * 60)
        logger.debug("[VMCPServer] Tool Details:")
        logger.debug(f"[VMCPServer]    Name: {name}")
        logger.debug(f"[VMCPServer]    Arguments: {arguments}")
        logger.debug(f"[VMCPServer]    Progress Token: {progress_token}")

        # Build dependencies from current request
        deps = await self.get_user_context_vmcp_server()
        if deps is None:
            logger.error("[VMCPServer] No dependencies available - cannot call tool without user context")
            raise Exception("Tool calls require user context")

        # Log user context
        user_id = getattr(deps, 'user_id', 'unknown')
        client_id = getattr(deps, 'client_id', 'unknown')
        agent_name = getattr(deps, 'agent_name', 'unknown')
        logger.debug("[VMCPServer] User Context:")
        logger.debug(f"[VMCPServer]    User ID: {user_id}")
        logger.debug(f"[VMCPServer]    Client ID: {client_id}")
        logger.debug(f"[VMCPServer]    Agent Name: {agent_name}")

        logger.info(f"[VMCPServer] Executing tool '{name}' for user {user_id}, client {client_id}, agent {agent_name}")

        try:
            # For now, check if this is the vmcp_create_prompt tool
            if name == "upload_prompt":
                logger.debug(f"[VMCPServer] Executing PRESET tool '{name}'")
                # Execute the preset tool directly (manually for now)
                result = await self._execute_upload_prompt(arguments)
                logger.info(f"[VMCPServer] Preset tool '{name}' executed successfully")
                logger.debug(f"[VMCPServer] Result type: {type(result)}")
                logger.debug(f"[VMCPServer] Result: {result}")
                logger.debug("=" * 60)

                # Return MCP-compatible CallToolResult format
                from mcp.types import CallToolResult
                return CallToolResult(
                    content=[TextContent(type="text", text=str(result))],
                    isError=False
                )
            else:
                logger.debug(f"[VMCPServer] Executing vMCP tool '{name}'")
                if deps.vmcp_config_manager:
                    result = await deps.vmcp_config_manager.call_tool(
                        vmcp_tool_call_request=VMCPToolCallRequest(tool_name=name, arguments=arguments, progress_token=progress_token)
                    )
                else:
                    raise Exception("No vMCP manager available for tool execution")
                logger.info(f"[VMCPServer] vMCP tool '{name}' executed successfully")
                logger.debug(f"[VMCPServer] Result type: {type(result)}")
                logger.debug(f"[VMCPServer] Result: {result}")
                if isinstance(result, list):
                    logger.debug(f"[VMCPServer] Result count: {len(result)}")
                logger.debug("=" * 60)

                return result
        except Exception as e:
            logger.error(f"[VMCPServer] Tool '{name}' failed with error: {e}")
            # Add traceback to logger
            logger.error(f"[VMCPServer] Full traceback: {traceback.format_exc()}")
            logger.debug("=" * 60)

            raise

    @trace_method("[VMCPServer]: Get Prompt")
    async def proxy_get_prompt(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Get prompt content from appropriate server or agent"""
        logger.info(f"[VMCPServer] Prompt request: {name}")
        logger.debug(f"[VMCPServer] Arguments: {arguments}")

        # Build dependencies from current request
        deps = await self.get_user_context_vmcp_server()
        if deps is None:
            logger.error("[VMCPServer] No dependencies available - cannot get prompt without user context")
            raise Exception("Prompt requests require user context")

        # Log user context
        user_id = getattr(deps, 'user_id', 'unknown')
        client_id = getattr(deps, 'client_id', 'unknown')
        agent_name = getattr(deps, 'agent_name', 'unknown')
        logger.info(f"[VMCPServer] Getting prompt '{name}' for user {user_id}, client {client_id}, agent {agent_name}")

        # Handle built-in prompts
        if name == "upload_prompt_helper":
            title = arguments.get("title", "") if arguments else ""
            description = arguments.get("description", "") if arguments else ""

            # Format the helper text with the provided title and description
            # Use replace() to avoid conflicts with other {variables} in the text
            formatted_text = CREATE_PROMPT_HELPER_TEXT.replace("{title}", title).replace("{description}", description)

            return GetPromptResult(
                description="Helper text for creating custom prompts",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(type="text", text=formatted_text)
                    )
                ]
            )

        if deps.vmcp_config_manager:
            prompt = await deps.vmcp_config_manager.get_prompt(name,arguments)
        else:
            raise Exception("No vMCP manager available for prompt retrieval")
        # if name.startswith("vMCP_"):
        # check name against the regex [A-Z0-9_]+
        if re.match(r"[A-Z0-9_]+", name):
            logger.info(f"[VMCPServer] Prompt '{name}' is all uppercase, sending list changed notifications")
            await self.get_context().session.send_tool_list_changed()
            await self.get_context().session.send_resource_list_changed()
            await self.get_context().session.send_prompt_list_changed()
        return prompt

    @trace_method("[VMCPServer]: Read Resource")
    async def proxy_read_resource(self, req: ReadResourceRequest) -> ServerResult:
        """Route resource reads to appropriate server"""
        uri = req.params.uri
        logger.info(f"[VMCPServer] Resource read requested: {uri}")

        # Build dependencies from current request
        deps = await self.get_user_context_vmcp_server()
        if deps is None:
            logger.error("[VMCPServer] No dependencies available - cannot read resource without user context")
            raise Exception("Resource read requests require user context")

        # Log user context
        user_id = getattr(deps, 'user_id', 'unknown')
        client_id = getattr(deps, 'client_id', 'unknown')
        agent_name = getattr(deps, 'agent_name', 'unknown')
        logger.info(f"[VMCPServer] Reading resource '{uri}' for user {user_id}, client {client_id}, agent {agent_name}")


        # For other resources, use the vmcp_config_manager to handle them
        try:
            if deps.vmcp_config_manager:
                resource_result = await deps.vmcp_config_manager.get_resource(uri)
            else:
                raise Exception("No vMCP manager available for resource retrieval")
            if resource_result:
                logger.info(f"[VMCPServer] Resource read successful: {uri}")
                logger.debug(f"[VMCPServer] Resource result type: {type(resource_result)}")
                logger.debug(f"[VMCPServer] Resource result structure: {resource_result}")
                return ServerResult(resource_result)
            else:
                logger.warning(f"[VMCPServer] Resource '{uri}' returned None or invalid result")
                raise ValueError(f"Resource '{uri}' not found")
        except Exception as e:
            logger.error(f"[VMCPServer] Resource read failed for '{uri}': {e}")
            logger.error(f"[VMCPServer] Exception type: {type(e).__name__}")
            raise
