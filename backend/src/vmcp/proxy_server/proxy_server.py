import asyncio
import os
import re
import traceback
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
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

from vmcp.config import settings
from vmcp.core.services import TokenInfo, get_jwt_service, get_user_context_class
from vmcp.mcps.oauth_handler import router as oauth_handler_router
from vmcp.mcps.router_typesafe import router as mcp_router
from vmcp.proxy_server.mcp_dependencies import get_http_request
from vmcp.proxy_server.middleware import register_middleware
from vmcp.proxy_server.tool_descriptions import CREATE_PROMPT_HELPER_TEXT, UPLOAD_PROMPT_DESCRIPTION
from vmcp.storage.blob_router import router as blob_router
from vmcp.utilities.logging import get_logger
from vmcp.utilities.tracing import add_tracing_middleware, trace_method
from vmcp.vmcps.models import VMCPToolCallRequest
from vmcp.vmcps.router_typesafe import router as vmcp_router
from vmcp.vmcps.stats_router import router as stats_router


@dataclass
class ReadResourceContents:
    """Contents returned from a read_resource call."""

    content: str | bytes
    mime_type: str | None = None
    meta: dict | None = None

# Setup centralized logging for proxy agent server with span correlation
logger = get_logger("vMCP Server")

class ProxyServer(FastMCP):
    def __init__(self, name: str):
        logger.info(f"🚀 Initializing ProxyServer: {name}")
        # Configure streamable HTTP path to be root so it works when mounted
        log_level_str = settings.log_level.upper()
        # Validate log level is one of the allowed values
        valid_log_levels: tuple[Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], ...] = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = log_level_str if log_level_str in valid_log_levels else 'INFO'  # type: ignore
        super().__init__(name, streamable_http_path="/mcp", instructions="1xn v(irtual)MCP server", log_level=log_level, debug=settings.debug)
        self._mcp_server.create_initialization_options(
            notification_options=NotificationOptions(prompts_changed=True, resources_changed=True, tools_changed=True),
            experimental_capabilities={"1xn": {"vmcp": True}})

        # Proxy server is completely stateless
        # All managers will be created per user request
        logger.info("✅ ProxyServer initialization complete (stateless)")

    async def get_user_context_proxy_server(self):
        """Build dependencies for the current request with user context"""
        try:
            # Get the current request context
            from vmcp.storage.base import StorageBase

            # Get services from registry
            jwt_service = get_jwt_service()
            UserContext = get_user_context_class()

            # Debug: Log all headers to see what's available
            request = get_http_request()
            logger.info(f"🔍 DEBUG: All headers during tool call: {dict(request.headers)}")
            auth_header = request.headers.get('Authorization', '')
            logger.info(f"🔍 DEBUG: Authorization header: '{auth_header}'")
            token = auth_header.replace('Bearer ', '').strip()
            logger.info(f"🔍 DEBUG: Extracted token: '{token[:20] if token else 'EMPTY'}...')")

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
                logger.warning(f"🔍 Invalid token info: {e}")
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
            agent_name = None
            session_id = get_http_request().headers.get('mcp-session-id')
            if session_id:
                user_storage = StorageBase(user_id=int(user_id))
                agent_name = user_storage.get_agent_name_from_session(session_id)
                if agent_name:
                    logger.info(f"🔍 Found agent name for session {session_id[:20]}...: {agent_name}")
                else:
                    logger.debug(f"🔍 No agent mapping found for session {session_id[:20]}...")
            else:
                logger.debug("🔍 No mcp-session-id in headers - agent name unavailable")

            user_context = UserContext(
                user_id=user_id,
                user_email=user_email,
                username=user_name,
                token=token,
                vmcp_name=vmcp_name
            )

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
                logger.info(f"✅ Updated vmcp_config_manager logging_config with agent_name: {agent_name}")

            # The UserContext now has vmcp_config_manager initialized
            return user_context
        except Exception as e:
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            logger.error(f"❌ Error building dependencies: {e}")
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
            deps = await self.get_user_context_proxy_server()
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
                logger.info(f"✅ Created custom prompt '{final_name}' in vMCP {active_vmcp_id}")
                return {
                    "status": "success",
                    "prompt_name": final_name,
                    "message": f"Custom prompt '{final_name}' created successfully"
                }
            else:
                return {"status": "error", "message": "Failed to save vMCP configuration"}

        except Exception as e:
            logger.error(f"❌ Error creating custom prompt: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {"status": "error", "message": f"Failed to create prompt: {str(e)}"}

    def _setup_handlers(self) -> None:
        """Set up core MCP protocol handlers."""
        logger.info("🔌 Setting up MCP protocol handlers...")

        self._mcp_server.list_tools()(self.proxy_list_tools)
        logger.debug("   ✅ list_tools handler registered")

        # Note: we disable the lowlevel server's input validation.
        # FastMCP does ad hoc conversion of incoming data before validating -
        # for now we preserve this for backwards compatibility.
        # self._mcp_server.call_tool(validate_input=False)(self.proxy_call_tool)
        self._mcp_server.request_handlers[CallToolRequest] = self.root_proxy_call_tool
        logger.debug("   ✅ call_tool handler registered")

        self._mcp_server.list_resources()(self.proxy_list_resources)
        logger.debug("   ✅ list_resources handler registered")

        self._mcp_server.request_handlers[ReadResourceRequest] = self.proxy_read_resource
        # self._mcp_server.read_resource()(self.proxy_read_resource)
        logger.debug("   ✅ read_resource handler registered")

        self._mcp_server.list_prompts()(self.proxy_list_prompts)
        logger.debug("   ✅ list_prompts handler registered")

        self._mcp_server.get_prompt()(self.proxy_get_prompt)
        logger.debug("   ✅ get_prompt handler registered")

        self._mcp_server.list_resource_templates()(self.proxy_list_resource_templates)
        logger.debug("   ✅ list_resource_templates handler registered")

        logger.info("🎉 All MCP protocol handlers registered successfully")

    @trace_method("[PROXY_SERVER]: List Tools")
    async def proxy_list_tools(self) -> List[Tool]:
        """Aggregate tools from all connected servers filtered by active agent or vMCP"""
        logger.info("=" * 60)
        logger.info("🔍 MCP: proxy_list_tools called")
        logger.info("=" * 60)

        # Build dependencies from current request
        deps = await self.get_user_context_proxy_server()
        if deps is None:
            logger.warning("🔍 No dependencies available (no valid token) - returning empty tools list")
            return []

        # Log user context
        user_id = getattr(deps, 'user_id', 'unknown')
        client_id = getattr(deps, 'client_id', 'unknown')
        agent_name = getattr(deps, 'agent_name', 'unknown')
        logger.info(f"🔍 MCP: Listing tools for user {user_id}, client {client_id}, agent {agent_name}")

        # Get vMCP tools
        if deps.vmcp_config_manager:
            tools = await deps.vmcp_config_manager.tools_list()
        else:
            tools = []
        logger.info(f"🔍 MCP: Found {len(tools)} vMCP tools")

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
        logger.info(f"🔍 MCP: Found {len(preset_tools)} preset tools")

        # Combine preset tools with vMCP tools
        all_tools = preset_tools + tools

        logger.info(f"🔍 MCP: Returning {len(all_tools)} total tools ({len(preset_tools)} preset + {len(tools)} vMCP)")
        # Tools are already Tool objects, no conversion needed
        logger.info(f"🔍 MCP: Returning {len(tools)} tools")
        logger.info("=" * 60)

        # Log tool details
        for i, tool in enumerate(all_tools):
            tool_type = "PRESET" if i < len(preset_tools) else "vMCP"
            logger.info(f"🔍 MCP: Tool {i+1} [{tool_type}]: {tool.name} - {tool.description[:50] if tool.description else 'No description'}...")

        return all_tools

    @trace_method("[PROXY_SERVER]: List Resources")
    async def proxy_list_resources(self) -> List[Resource]:
        """Aggregate resources from all connected servers filtered by active agent or vMCP"""
        logger.info("🔍 Listing resources from all connected servers...")

        # Build dependencies from current request
        deps = await self.get_user_context_proxy_server()
        if deps is None:
            logger.warning("🔍 No dependencies available - returning empty resources list")
            return []

        # Log user context
        user_id = getattr(deps, 'user_id', 'unknown')
        client_id = getattr(deps, 'client_id', 'unknown')
        agent_name = getattr(deps, 'agent_name', 'unknown')
        logger.info(f"🔍 MCP: Listing resources for user {user_id}, client {client_id}, agent {agent_name}")

        if deps.vmcp_config_manager:
            resources = await deps.vmcp_config_manager.resources_list()
        else:
            resources = []

        return resources

    @trace_method("[PROXY_SERVER]: List Resource Templates")
    async def proxy_list_resource_templates(self) -> List[ResourceTemplate]:
        """Aggregate resource templates from all connected servers filtered by active agent or vMCP"""
        logger.info("🔍 Listing resource templates from all connected servers...")

        # Build dependencies from current request
        deps = await self.get_user_context_proxy_server()
        if deps is None:
            logger.warning("🔍 No dependencies available - returning empty resource templates list")
            return []

        # Log user context
        user_id = getattr(deps, 'user_id', 'unknown')
        client_id = getattr(deps, 'client_id', 'unknown')
        agent_name = getattr(deps, 'agent_name', 'unknown')
        logger.info(f"🔍 MCP: Listing resource templates for user {user_id}, client {client_id}, agent {agent_name}")

        if deps.vmcp_config_manager:
            resource_templates = await deps.vmcp_config_manager.resource_templates_list()
        else:
            resource_templates = []

        # Log resource template details
        for i, template in enumerate(resource_templates):
            logger.info(f"🔍 MCP: Resource Template {i+1}: {template.name} - {template.description[:50] if template.description else 'No description'}...")

        return resource_templates

    @trace_method("[PROXY_SERVER]: List Prompts")
    async def proxy_list_prompts(self) -> List[Prompt]:
        """Aggregate prompts from all connected servers filtered by active agent or vMCP"""
        logger.info("🔍 Listing prompts from all connected servers...")

        # Build dependencies from current request
        deps = await self.get_user_context_proxy_server()
        if deps is None:
            logger.warning("🔍 No dependencies available - returning empty prompts list")
            return []

        # Log user context
        user_id = getattr(deps, 'user_id', 'unknown')
        client_id = getattr(deps, 'client_id', 'unknown')
        agent_name = getattr(deps, 'agent_name', 'unknown')
        logger.info(f"🔍 MCP: Listing prompts for user {user_id}, client {client_id}, agent {agent_name}")

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
            logger.info(f"🔍 MCP: Prompt {i+1}: {prompt.name} - {prompt.description[:50] if prompt.description else 'No description'}...")

        return prompts

    @trace_method("[PROXY_SERVER]: Root Tool Call")
    async def root_proxy_call_tool(self, req: CallToolRequest):
        tool_name = req.params.name
        arguments = req.params.arguments or {}
        logger.info(f"🔧 DEBUG root_proxy_call_tool: tool={tool_name}, arguments={arguments}, types={[(k, type(v).__name__) for k, v in arguments.items()]}")
        result = await self.proxy_call_tool(tool_name, arguments)
        return result

    @trace_method("[PROXY_SERVER]: Tool Call", operation="call_tool")
    async def proxy_call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Route tool calls to appropriate server"""
        logger.info("=" * 60)
        logger.info("🛠️  MCP: Tool call requested")
        logger.info("=" * 60)
        logger.info("📋 Tool Details:")
        logger.info(f"   Name: {name}")
        logger.info(f"   Arguments: {arguments}")

        # Build dependencies from current request
        deps = await self.get_user_context_proxy_server()
        if deps is None:
            logger.error("🔍 No dependencies available - cannot call tool without user context")
            raise Exception("Tool calls require user context")

        # Log user context
        user_id = getattr(deps, 'user_id', 'unknown')
        client_id = getattr(deps, 'client_id', 'unknown')
        agent_name = getattr(deps, 'agent_name', 'unknown')
        logger.info("📋 User Context:")
        logger.info(f"   User ID: {user_id}")
        logger.info(f"   Client ID: {client_id}")
        logger.info(f"   Agent Name: {agent_name}")

        logger.info(f"🛠️  MCP: Executing tool '{name}' for user {user_id}, client {client_id}, agent {agent_name}")

        # Track tool execution start (OSS - analytics disabled)
        # analytics.track_mcp_tool_call(
        #     user_id=user_id,
        #     tool_name=name,
        #     mcp_server="proxy_server",
        #     success=False,
        #     properties={"client_id": client_id, "agent_name": agent_name}
        # )

        try:
            # For now, check if this is the vmcp_create_prompt tool
            if name == "upload_prompt":
                logger.info(f"🔧 MCP: Executing PRESET tool '{name}'")
                # Execute the preset tool directly (manually for now)
                result = await self._execute_upload_prompt(arguments)
                logger.info(f"✅ MCP: Preset tool '{name}' executed successfully")
                logger.info(f"📋 Result type: {type(result)}")
                logger.info(f"📋 Result: {result}")
                logger.info("=" * 60)

                # Track successful tool execution
                # analytics.track_mcp_tool_call()  # OSS - analytics disabled

                # Return MCP-compatible CallToolResult format
                from mcp.types import CallToolResult
                return CallToolResult(
                    content=[TextContent(type="text", text=str(result))],
                    isError=False
                )
            else:
                logger.info(f"🔧 MCP: Executing vMCP tool '{name}'")
                if deps.vmcp_config_manager:
                    result = await deps.vmcp_config_manager.call_tool(
                        vmcp_tool_call_request=VMCPToolCallRequest(tool_name=name, arguments=arguments)
                    )
                else:
                    raise Exception("No vMCP manager available for tool execution")
                logger.info(f"✅ MCP: vMCP tool '{name}' executed successfully")
                logger.info(f"📋 Result type: {type(result)}")
                logger.info(f"📋 Result: {result}")
                if isinstance(result, list):
                    logger.info(f"📋 Result count: {len(result)}")
                logger.info("=" * 60)

                # Track successful vMCP tool execution
                # analytics.track_mcp_tool_call()  # OSS - analytics disabled

                return result
        except Exception as e:
            logger.error(f"❌ MCP: Tool '{name}' failed with error: {e}")
            # Add traceback to logger
            logger.error(f"Full traceback: {traceback.format_exc()}")
            logger.info("=" * 60)

            # Track failed tool execution
            # analytics.track_mcp_tool_call()  # OSS - analytics disabled

            raise

    @trace_method("[PROXY_SERVER]: Get Prompt")
    async def proxy_get_prompt(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Get prompt content from appropriate server or agent"""
        logger.info(f"📝 Prompt request: {name}")
        logger.debug(f"   📋 Arguments: {arguments}")

        # Build dependencies from current request
        deps = await self.get_user_context_proxy_server()
        if deps is None:
            logger.error("🔍 No dependencies available - cannot get prompt without user context")
            raise Exception("Prompt requests require user context")

        # Log user context
        user_id = getattr(deps, 'user_id', 'unknown')
        client_id = getattr(deps, 'client_id', 'unknown')
        agent_name = getattr(deps, 'agent_name', 'unknown')
        logger.info(f"📝 MCP: Getting prompt '{name}' for user {user_id}, client {client_id}, agent {agent_name}")

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
            logger.info(f"🔍 MCP: Prompt '{name}' is all uppercase, sending list changed notifications")
            await self.get_context().session.send_tool_list_changed()
            await self.get_context().session.send_resource_list_changed()
            await self.get_context().session.send_prompt_list_changed()
        return prompt

    @trace_method("[PROXY_SERVER]: Read Resource")
    async def proxy_read_resource(self, req: ReadResourceRequest) -> ServerResult:
        """Route resource reads to appropriate server"""
        uri = req.params.uri
        logger.info(f"📦 Resource read requested: {uri}")

        # Build dependencies from current request
        deps = await self.get_user_context_proxy_server()
        if deps is None:
            logger.error("🔍 No dependencies available - cannot read resource without user context")
            raise Exception("Resource read requests require user context")

        # Log user context
        user_id = getattr(deps, 'user_id', 'unknown')
        client_id = getattr(deps, 'client_id', 'unknown')
        agent_name = getattr(deps, 'agent_name', 'unknown')
        logger.info(f"📦 MCP: Reading resource '{uri}' for user {user_id}, client {client_id}, agent {agent_name}")


        # For other resources, use the vmcp_config_manager to handle them
        try:
            if deps.vmcp_config_manager:
                resource_result = await deps.vmcp_config_manager.get_resource(uri)
            else:
                raise Exception("No vMCP manager available for resource retrieval")
            if resource_result:
                logger.info(f"✅ Resource read successful: {uri}")
                logger.info(f"🔍 Proxy Server: Resource result type: {type(resource_result)}")
                logger.debug(f"🔍 Proxy Server: Resource result structure: {resource_result}")
                # if isinstance(resource_result, ReadResourceResult):
                    # return ServerResult(resource_result) #[ReadResourceContents(content=c.text, mime_type=c.mimeType, meta=c.meta) if hasattr(c, 'text') else ReadResourceContents(content=c.blob, mime_type=c.mimeType, meta=c.meta) for c in resource_result.contents]
                # else:
                    # return resource_result
                return ServerResult(resource_result)
            else:
                logger.warning(f"⚠️  Resource '{uri}' returned None or invalid result")
                raise ValueError(f"Resource '{uri}' not found")
        except Exception as e:
            logger.error(f"❌ Resource read failed for '{uri}': {e}")
            logger.error(f"   🔍 Exception type: {type(e).__name__}")
            raise

# Create an MCP server
logger.info("🎬 Creating ProxyServer instance...")
mcp = ProxyServer("1xN MCP Proxy")

# Create unified FastAPI server
# Create the FastMCP HTTP app first to get its lifespan
logger.info("🔧 Creating FastMCP streamable HTTP app...")
mcp_http_app = mcp.streamable_http_app()

# logger.info(f"🔍 MCP HTTP app routes: {mcp_http_app.routes}")

# Lifespan context manager for MCP session management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the MCP session manager lifecycle and database initialization"""
    logger.info("🚀 Starting application startup...")

    # Initialize database tables (creates missing tables, preserves existing data)
    try:
        from vmcp.storage.database import init_db

        logger.info("📊 Initializing database tables...")
        init_db()

        logger.info("👤 Ensuring user exists...")
        # User creation is handled by oss_providers.ensure_dummy_user() during registration
        from vmcp.core.services.oss_providers import ensure_dummy_user
        ensure_dummy_user()

        logger.info("✅ Database initialization complete")
    except Exception as e:
        logger.warning(f"⚠️ Database initialization warning: {e}")
        logger.info("    Continuing anyway (database may already be initialized)")

    logger.info("🚀 Starting MCP session manager...")

    # Create shutdown event
    shutdown_event = asyncio.Event()
    session_task = None

    async def run_session_manager():
        try:
            async with mcp.session_manager.run():
                # Wait for shutdown signal instead of blocking indefinitely
                await shutdown_event.wait()
        except asyncio.CancelledError:
            logger.info("🛑 MCP session manager cancelled")
        except Exception as e:
            logger.error(f"❌ MCP session manager error: {e}")

    # Start the session manager task
    session_task = asyncio.create_task(run_session_manager())

    try:
        logger.info("✅ MCP session manager started")
        yield
    finally:
        logger.info("🛑 Shutting down MCP session manager...")
        # Signal shutdown
        shutdown_event.set()

        if session_task:
            try:
                await asyncio.wait_for(session_task, timeout=3.0)
            except asyncio.TimeoutError:
                logger.warning("⚠️ MCP session manager shutdown timeout, forcing cancellation")
                session_task.cancel()
                try:
                    await asyncio.wait_for(session_task, timeout=1.0)
                except asyncio.CancelledError:
                    pass  # Expected
            except asyncio.CancelledError:
                pass  # Expected
        logger.info("✅ MCP session manager shutdown complete")

# Use custom lifespan management for MCP session
app = FastAPI(
    title="1xN MCP Proxy Server",
    description="MCP proxy server with management API",
    lifespan=lifespan,
    redirect_slashes=False  # Prevent automatic redirects that lose Authorization headers
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OSS version - no analytics middleware
logger.info("📊 Analytics disabled in OSS version")

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
        logger.info("📊 Traces API router not available")

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/api/proxystatic", StaticFiles(directory=str(static_dir)), name="static")

# Register middleware (routing first, then authentication)
register_middleware(app)

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


# Mount the API routes (OSS version - minimal routers)
logger.info("📌 Mounting API routes...")
app.include_router(mcp_router, prefix="/api")
app.include_router(vmcp_router, prefix="/api")
app.include_router(oauth_handler_router, prefix="/api")
app.include_router(blob_router, prefix="/api")
app.include_router(stats_router, prefix="/api")

# Mount the MCP server (now with shared lifespan)
logger.info("📌 Mounting MCP server with shared lifespan...")
app.mount("/vmcp/", mcp_http_app, name="1xn_mcp_server")
logger.debug(f"🔍 MCP HTTP app routes: {app.routes}")
logger.info("✅ MCP server mounted at /vmcp/mcp")

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
    logger.info(f"📁 Serving frontend from {frontend_dist}")

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

    logger.info("✅ Frontend served at /app with SPA routing")
else:
    logger.warning(f"⚠️ Frontend build directory not found at {frontend_dist}")

# ================================================
# Serve documentation from public/documentation
# First try: environment variable (for enterprise override)
# ================================================
def create_app():
    """Factory function to create FastAPI app instance."""
    return app
