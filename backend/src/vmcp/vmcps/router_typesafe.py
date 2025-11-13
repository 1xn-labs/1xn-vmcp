"""
Type-Safe vMCP Router with Proper Request/Response Models

This router provides type-safe endpoints for managing vMCPs (Virtual Model Context Protocol).
All endpoints now use proper Pydantic request and response models for full type safety.
"""

import json
import logging
import random
import re
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from vmcp.mcps.mcp_client import AuthenticationError, MCPClientManager
from vmcp.mcps.mcp_configmanager import MCPConfigManager
from vmcp.mcps.models import MCPConnectionStatus, MCPServerConfig, MCPTransportType

# Import shared models
from vmcp.shared.models import BaseResponse, ErrorResponse, PromptInfo, ServerInfo
from vmcp.storage.base import StorageBase

# Import dependencies
from vmcp.storage.database import SessionLocal, get_db
from vmcp.storage.dummy_user import UserContext, get_user_context
from vmcp.storage.models import VMCP, VMCPStats

# Import type-safe models
from vmcp.vmcps.models import (
    LogEntry,
    StatsFilterRequest,
    # Legacy compatibility
    StatsResponse,
    StatsSummary,
    VMCPAddServerData,
    VMCPAddServerRequest,
    VMCPAddServerResponse,
    VMCPConfig,
    # Request models
    VMCPCreateRequest,
    # Response models
    VMCPCreateResponse,
    VMCPDeleteResponse,
    VMCPDetailsResponse,
    VMCPEnvironmentVariablesData,
    VMCPEnvironmentVariablesRequest,
    VMCPEnvironmentVariablesResponse,
    VMCPForkRequest,
    # Base models
    VMCPInfo,
    VMCPInstallRequest,
    VMCPInstallResponse,
    VMCPListData,
    VMCPListPromptsRequest,
    VMCPListResourcesRequest,
    VMCPListResponse,
    VMCPListToolsRequest,
    VMCPPromptListData,
    VMCPPromptRequest,
    VMCPPromptResponse,
    VMCPRefreshRequest,
    VMCPRefreshResponse,
    VMCPRemoveServerRequest,
    VMCPRemoveServerResponse,
    VMCPResourceRequest,
    VMCPResourceResponse,
    VMCPShareRequest,
    VMCPShareResponse,
    VMCPShareState,
    VMCPToolCallRequest,
    VMCPToolCallResponse,
    VMCPUdateRequest,
    VMCPUpdateResponse,
)
from vmcp.vmcps.vmcp_config_manger import VMCPConfigManager
from vmcp.utilities.logging import setup_logging

router = APIRouter(prefix="/vmcps", tags=["vMCPs"])

logger = setup_logging(__name__)

# ============================================================================
# PYTHON TOOL GENERATION MODELS (Keep existing functionality)
# ============================================================================

class CollectionVariable(BaseModel):
    key: str
    value: str
    description: Optional[str] = None
    type: Optional[str] = "string"

class PythonFunctionParameter(BaseModel):
    name: str
    description: str
    required: bool
    type: str
    default_value: Optional[Any] = None

class PythonFunctionInfo(BaseModel):
    name: str
    parameters: List[PythonFunctionParameter]
    returnType: Optional[str] = None
    docstring: Optional[str] = None

class ParsePythonFunctionRequest(BaseModel):
    code: str

class ParsePythonFunctionResponse(BaseModel):
    functions: List[PythonFunctionInfo]

class CollectionMetadata(BaseModel):
    name: str
    description: Optional[str] = None
    variables: List[CollectionVariable] = []
    baseUrl: Optional[str] = None

class GeneratePythonToolsRequest(BaseModel):
    collection: Dict[str, Any]
    collectionType: str = "postman"
    selectedIndices: List[str] = []

class GeneratedTool(BaseModel):
    name: str
    method: str
    url: str
    description: str
    code: str
    parameters: Dict[str, Any]
    collectionMetadata: CollectionMetadata

class GeneratePythonToolsResponse(BaseModel):
    success: bool
    tools: List[GeneratedTool]
    collectionMetadata: CollectionMetadata
    message: Optional[str] = None

# ============================================================================
# HELPER FUNCTIONS (Keep existing functionality)
# ============================================================================

def slugify_to_name(input_str: str) -> str:
    """Convert text to snake_case"""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', input_str)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower().replace(' ', '_').replace('-', '_')

def detect_api_key_from_headers(headers: Dict[str, str]) -> Optional[Dict[str, str]]:
    """Detect API key from headers"""
    for key, value in headers.items():
        lower = key.lower()
        if lower == 'authorization' and re.search(r'bearer|api[-_ ]?key|token', value or '', re.I):
            return {"headerName": key, "varName": "API_TOKEN", "location": "header"}
        if re.search(r'api[-_ ]?key|x-api-key|apikey', lower):
            return {"headerName": key, "varName": "API_KEY", "location": "header"}
    return None

def detect_api_key_from_postman_auth(auth: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Detect API key from Postman auth"""
    if not auth or not auth.get('type'):
        return None
    
    auth_type = auth['type']
    
    def get_value(arr: List[Dict], key: str) -> Optional[str]:
        if not isinstance(arr, list):
            return None
        found = next((e for e in arr if e.get('key') == key), None)
        return found.get('value') if found else None
    
    if auth_type == 'apikey' and auth.get('apikey'):
        key = get_value(auth['apikey'], 'key') or 'X-API-Key'
        value = get_value(auth['apikey'], 'value') or '{{API_KEY}}'
        location = get_value(auth['apikey'], 'in') or 'header'
        return {"headerName": key, "varName": "API_KEY", "location": location}
    
    if auth_type == 'bearer' and auth.get('bearer'):
        token = get_value(auth['bearer'], 'token') or '{{API_TOKEN}}'
        return {"headerName": "Authorization", "varName": "API_TOKEN", "location": "header"}
    
    return None

def generate_python_function(endpoint: Dict[str, Any], collection_metadata: CollectionMetadata) -> str:
    """Generate Python function code for an endpoint"""
    func_name = slugify_to_name(endpoint.get('name', 'unnamed_endpoint'))
    method = endpoint.get('method', 'GET')
    url = endpoint.get('url', '')
    description = endpoint.get('description', f'Function to {method} {endpoint.get("name", "")}')
    
    # Extract parameters
    path_params = endpoint.get('pathParams', [])
    query_params = endpoint.get('queryParamsMeta', [])
    body_params = endpoint.get('body', {})
    
    # Build function parameters
    all_params = []
    for param in path_params:
        all_params.append(f"{param['name']}: str")
    
    for param in query_params:
        param_def = f"{param['name']}: str"
        if param.get('default') is not None:
            param_def += f' = "{param["default"]}"'
        elif not param.get('required', False):
            param_def += " = None"
        all_params.append(param_def)
    
    if body_params and isinstance(body_params, dict):
        all_params.append("body: dict = None")
    
    params_str = ", ".join(all_params)
    
    # Build docstring
    docstring_params = []
    for param in path_params:
        param_name = param['name']
        param_desc = param.get('description', f'Path parameter: {param_name}')
        docstring_params.append(f"     * @param {{string}} {param_name} - {param_desc}")
    
    for param in query_params:
        param_name = param['name']
        param_desc = param.get('description', f'Query parameter: {param_name}')
        docstring_params.append(f"     * @param {{string}} {param_name} - {param_desc}")
    
    if body_params and isinstance(body_params, dict):
        docstring_params.append("     * @param {Object} body - Request body parameters")
    
    docstring_params_str = "\n".join(docstring_params)
    
    # Build URL construction
    base_url = collection_metadata.baseUrl or ""
    if base_url:
        # Replace collection variables
        for variable in collection_metadata.variables:
            if variable.key != 'baseUrl':
                base_url = base_url.replace(f"{{{{{variable.key}}}}}", variable.value)
    
    # Replace path parameters
    path = url
    if path.startswith(base_url):
        path = path[len(base_url):]
    
    for param in path_params:
        param_name = param['name']
        path = path.replace(f":{param_name}", f"{{{param_name}}}")
    
    url_construction = f'    base_url = "{base_url}"\n'
    url_construction += f'    url = base_url + "{path}"\n'
    
    # Build query parameters
    query_code = ""
    if query_params:
        query_code = "    params = {}\n"
        for param in query_params:
            query_code += f"    if {param['name']} is not None:\n"
            query_code += f"        params[\"{param['name']}\"] = {param['name']}\n"
        query_code += "    if params:\n"
        query_code += '        query_string = "&".join([f"{k}={v}" for k, v in params.items()])\n'
        query_code += '        url += "?" + query_string\n'
    
    # Build headers
    headers_code = "    headers = {\n"
    headers_code += '        "Content-Type": "application/json"\n'
    headers_code += "    }\n"
    
    # Build request body
    body_code = ""
    if body_params and isinstance(body_params, dict):
        body_code = "    if body is not None:\n"
        body_code += "        data = json.dumps(body)\n"
        body_code += "    else:\n"
        body_code += "        data = None\n"
    
    # Build the complete function
    function_code = f'''def {func_name}({params_str}):
    """
    {description}
    
{docstring_params_str}
    
    Returns:
        dict: Response from the API
    """
    import requests
    import json
    
{url_construction}{query_code}{headers_code}{body_code}
    
    try:
        response = requests.{method.lower()}(url, headers=headers{f', data=data' if body_code else ''})
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {{"error": str(e)}}
'''
    
    return function_code

# ============================================================================
# HEALTH AND UTILITY ENDPOINTS
# ============================================================================

@router.get("/health", response_model=BaseResponse[Dict[str, str]])
async def health_check() -> BaseResponse[Dict[str, str]]:
    """Health check endpoint for the unified backend server management"""
    return BaseResponse(
        success=True,
        message="vMCP service is healthy",
        data={
            "status": "healthy",
            "service": "1xN Unified Backend - vMCP Management"
        }
    )

# ============================================================================
# PYTHON TOOL GENERATION ENDPOINTS
# ============================================================================

@router.post("/generate-python-tools", response_model=GeneratePythonToolsResponse)
async def generate_python_tools(request: GeneratePythonToolsRequest) -> GeneratePythonToolsResponse:
    """Generate Python tools from Postman collection with type-safe request/response models."""
    try:
        collection = request.collection
        collection_type = request.collectionType
        selected_indices = request.selectedIndices
        
        # Extract collection metadata
        collection_metadata = CollectionMetadata(
            name=collection.get('info', {}).get('name', 'Unknown Collection'),
            description=collection.get('info', {}).get('description', ''),
            baseUrl=collection.get('info', {}).get('baseUrl', ''),
            variables=[]
        )
        
        # Extract variables
        if 'variable' in collection:
            for var in collection['variable']:
                collection_metadata.variables.append(CollectionVariable(
                    key=var.get('key', ''),
                    value=var.get('value', ''),
                    description=var.get('description', ''),
                    type=var.get('type', 'string')
                ))
        
        # Extract endpoints
        endpoints = []
        if 'item' in collection:
            for item in collection['item']:
                if 'request' in item:
                    endpoint = {
                        'name': item.get('name', 'Unnamed'),
                        'method': item['request'].get('method', 'GET'),
                        'url': item['request'].get('url', {}).get('raw', ''),
                        'description': item.get('description', ''),
                        'pathParams': item['request'].get('url', {}).get('variable', []),
                        'queryParamsMeta': item['request'].get('url', {}).get('query', []),
                        'body': item['request'].get('body', {})
                    }
                    endpoints.append(endpoint)
        
        # Filter endpoints if indices are specified
        if selected_indices:
            filtered_endpoints = []
            for idx in selected_indices:
                try:
                    idx_int = int(idx)
                    if 0 <= idx_int < len(endpoints):
                        filtered_endpoints.append(endpoints[idx_int])
                except ValueError:
                    continue
            endpoints = filtered_endpoints
        
        # Generate tools
        generated_tools = []
        for endpoint in endpoints:
            # Detect API key
            api_key_info = None
            if 'headers' in endpoint.get('request', {}):
                api_key_info = detect_api_key_from_headers(endpoint['request']['headers'])
            
            if not api_key_info and 'auth' in endpoint.get('request', {}):
                api_key_info = detect_api_key_from_postman_auth(endpoint['request']['auth'])
            
            # Generate function code
            function_code = generate_python_function(endpoint, collection_metadata)
            
            # Extract parameters
            parameters = {
                'pathParams': endpoint.get('pathParams', []),
                'queryParams': endpoint.get('queryParamsMeta', []),
                'bodyParams': endpoint.get('body', {}),
                'apiKey': api_key_info
            }
            
            tool = GeneratedTool(
                name=slugify_to_name(endpoint['name']),
                method=endpoint['method'],
                url=endpoint['url'],
                description=endpoint['description'],
                code=function_code,
                parameters=parameters,
                collectionMetadata=collection_metadata
            )
            generated_tools.append(tool)
        
        return GeneratePythonToolsResponse(
            success=True,
            tools=generated_tools,
            collectionMetadata=collection_metadata,
            message=f"Generated {len(generated_tools)} Python tools successfully"
        )
        
    except Exception as e:
        logger.error(f"Error generating Python tools: {e}")
        return GeneratePythonToolsResponse(
            success=False,
            tools=[],
            collectionMetadata=CollectionMetadata(name="Error", description="", variables=[], baseUrl=""),
            message=f"Failed to generate Python tools: {str(e)}"
        )

# ============================================================================
# vMCP MANAGEMENT ENDPOINTS
# ============================================================================

@router.post("/create", response_model=VMCPCreateResponse)
async def create_vmcp(
    request: VMCPCreateRequest,
    user_context: UserContext = Depends(get_user_context)
) -> VMCPCreateResponse:
    """Create a new vMCP configuration for the current user"""
    logger.info("📋 Create vMCP endpoint called")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")
    
    try:
        # Get managers from global connection manager
        config_manager = MCPConfigManager(user_context.user_id)
        client_manager = MCPClientManager(config_manager)
        user_vmcp_manager = VMCPConfigManager(user_context.user_id)
        
        # Parse Python functions and update their variables
        updated_custom_tools = []
        for tool in request.custom_tools:
            # Convert Pydantic model to dict if needed (handle both v1 and v2)
            if isinstance(tool, dict):
                tool_dict = tool
            elif hasattr(tool, 'model_dump'):  # Pydantic v2
                tool_dict = tool.model_dump()
            elif hasattr(tool, 'dict'):  # Pydantic v1
                tool_dict = tool.dict()
            else:
                # Fallback: try to convert to dict
                tool_dict = dict(tool) if hasattr(tool, '__dict__') else {}
            
            # Access tool_type and code from dict
            tool_type = tool_dict.get('tool_type')
            tool_code = tool_dict.get('code')
            
            if tool_type == 'python' and tool_code:
                try:
                    # Parse Python function to extract variables with types
                    import ast
                    from typing import get_origin
                    
                    def map_python_type(type_annotation) -> str:
                        if type_annotation is None:
                            return 'str'
                        
                        if isinstance(type_annotation, str):
                            type_map = {
                                'str': 'str', 'string': 'str',
                                'int': 'int', 'integer': 'int',
                                'float': 'float', 'number': 'float',
                                'bool': 'bool', 'boolean': 'bool',
                                'list': 'list', 'array': 'list',
                                'dict': 'dict', 'object': 'dict',
                                'tuple': 'list', 'set': 'list',
                            }
                            return type_map.get(type_annotation.lower(), 'str')
                        
                        if hasattr(type_annotation, '__name__'):
                            type_map = {
                                'str': 'str', 'int': 'int', 'float': 'float',
                                'bool': 'bool', 'list': 'list', 'dict': 'dict',
                                'tuple': 'list', 'set': 'list',
                            }
                            return type_map.get(type_annotation.__name__, 'str')
                        
                        origin = get_origin(type_annotation)
                        if origin is not None:
                            if origin is list or origin is tuple or origin is set:
                                return 'list'
                            elif origin is dict:
                                return 'dict'
                        
                        return 'str'
                    
                    # Parse the Python code
                    tree = ast.parse(tool_code)
                    variables = []
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            # Extract parameters
                            for arg in node.args.args:
                                if arg.arg == 'self':
                                    continue
                                    
                                type_annotation = None
                                if arg.annotation:
                                    if isinstance(arg.annotation, ast.Name):
                                        type_annotation = arg.annotation.id
                                    elif isinstance(arg.annotation, ast.Constant):
                                        type_annotation = arg.annotation.value
                                    elif isinstance(arg.annotation, ast.Subscript):
                                        # Handle generic types like list[int], dict[str, str]
                                        if isinstance(arg.annotation.value, ast.Name):
                                            type_annotation = arg.annotation.value.id

                                has_default = (len(node.args.defaults) > 0 and
                                             node.args.args.index(arg) >= len(node.args.args) - len(node.args.defaults))
                                
                                # Extract default value if present
                                default_value = None
                                if has_default:
                                    default_index = node.args.args.index(arg) - (len(node.args.args) - len(node.args.defaults))
                                    if default_index < len(node.args.defaults):
                                        default_ast = node.args.defaults[default_index]
                                        if isinstance(default_ast, ast.Constant):
                                            default_value = default_ast.value
                                        elif isinstance(default_ast, ast.Str):  # Python < 3.8
                                            default_value = default_ast.s
                                        elif isinstance(default_ast, ast.Num):  # Python < 3.8
                                            default_value = default_ast.n
                                        elif isinstance(default_ast, ast.NameConstant):  # Python < 3.8
                                            default_value = default_ast.value
                                        elif isinstance(default_ast, ast.Name):
                                            # Handle variable references (e.g., default=some_var)
                                            default_value = f"@{default_ast.id}"
                                
                                variables.append({
                                    'name': arg.arg,
                                    'description': f"Parameter: {arg.arg}",
                                    'required': not has_default,
                                    'type': map_python_type(type_annotation),
                                    'default_value': default_value
                                })
                            break  # Only process the first function
                    
                    # Update the tool with parsed variables
                    updated_tool = tool_dict.copy()
                    updated_tool['variables'] = variables
                    updated_custom_tools.append(updated_tool)
                    
                except Exception as e:
                    tool_name = tool_dict.get('name', 'unknown')
                    logger.warning(f"Error parsing Python function in tool '{tool_name}': {e}")
                    updated_custom_tools.append(tool_dict)
            else:
                updated_custom_tools.append(tool_dict)
        
        # Create vMCP configuration
        vmcp_id = user_vmcp_manager.create_vmcp_config(
            name=request.name,
            description=request.description,
            system_prompt=request.system_prompt,
            vmcp_config=request.vmcp_config,
            custom_prompts=request.custom_prompts,
            custom_tools=updated_custom_tools,
            custom_context=request.custom_context,
            custom_resources=request.custom_resources,
            custom_resource_uris=request.custom_resource_uris,
            environment_variables=request.environment_variables,
            uploaded_files=request.uploaded_files
        )
        
        if not vmcp_id:
            raise HTTPException(status_code=400, detail="Failed to create vMCP")
        
        # Get the created vMCP details
        vmcp_manager_with_id = VMCPConfigManager(user_context.user_id, vmcp_id)
        vmcp_config = vmcp_manager_with_id.load_vmcp_config()
        
        if not vmcp_config:
            logger.error(f"❌ Failed to load created vMCP: {vmcp_id}")
            raise HTTPException(status_code=500, detail=f"Failed to load created vMCP: {vmcp_id}")
        
        logger.info(f"✅ Created vMCP: {vmcp_id} ({request.name})")
        
        # Process servers from imported VMCP config if present
        processed_servers = []
        if vmcp_config.vmcp_config and vmcp_config.vmcp_config.get('selected_servers'):
            selected_servers = vmcp_config.vmcp_config.get('selected_servers', [])
            if selected_servers:
                logger.info(f"   🔍 Processing {len(selected_servers)} servers from imported vMCP config")
                try:
                    processed_servers = await _process_servers_for_vmcp_import(
                        vmcp_id=vmcp_id,
                        selected_servers=selected_servers,
                        config_manager=config_manager,
                        client_manager=client_manager
                    )
                    
                    # Update VMCP config with processed servers
                    if vmcp_config.vmcp_config:
                        vmcp_config.vmcp_config['selected_servers'] = processed_servers
                    else:
                        vmcp_config.vmcp_config = {'selected_servers': processed_servers}
                    
                    # Save updated VMCP config
                    vmcp_manager_with_id.save_vmcp_config(vmcp_config)
                    logger.info("   ✅ Updated vMCP config with processed servers")
                    
                    # Count server statuses
                    server_status_counts = {}
                    for server in processed_servers:
                        status = server.get('status', 'unknown')
                        server_status_counts[status] = server_status_counts.get(status, 0) + 1
                    logger.info(f"   📊 Server status summary: {server_status_counts}")
                    
                except Exception as e:
                    logger.error(f"   ❌ Error processing servers for vMCP {vmcp_id}: {e}")
                    logger.error(f"   ❌ Traceback: {traceback.format_exc()}")
                    # Continue without failing - VMCP is created, servers just couldn't be processed
        
        # Convert to type-safe response model
        # Ensure all lists are not None and handle all required fields
        vmcp_info = VMCPInfo(
            id=vmcp_config.id,
            name=vmcp_config.name,
            description=vmcp_config.description or None,
            status="active",  # Default status
            user_id=str(user_context.user_id),
            system_prompt=vmcp_config.system_prompt,
            vmcp_config=vmcp_config.vmcp_config or {},
            custom_prompts=vmcp_config.custom_prompts or [],
            custom_tools=vmcp_config.custom_tools or [],
            custom_context=vmcp_config.custom_context or [],
            custom_resources=vmcp_config.custom_resources or [],
            custom_resource_templates=getattr(vmcp_config, 'custom_resource_templates', None) or [],
            custom_widgets=getattr(vmcp_config, 'custom_widgets', None) or [],
            custom_resource_uris=getattr(vmcp_config, 'custom_resource_uris', None) or [],
            environment_variables=vmcp_config.environment_variables or [],
            uploaded_files=vmcp_config.uploaded_files or [],
            created_at=vmcp_config.created_at,
            updated_at=vmcp_config.updated_at
        )
        
        return VMCPCreateResponse(
            success=True,
            vMCP=vmcp_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error creating vMCP: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to create vMCP: {str(e)}")

# ============================================================================
# HELPER FUNCTIONS FOR VMCP IMPORT SERVER PROCESSING
# ============================================================================

def _has_discovered_capabilities(server_config: MCPServerConfig) -> bool:
    """
    Check if a server has discovered capabilities.
    
    Capabilities are considered "discovered" if any of the detail fields
    (tool_details, resource_details, prompt_details) contain actual data.
    
    Args:
        server_config: MCPServerConfig to check
        
    Returns:
        True if capabilities have been discovered, False otherwise
    """
    return bool(
        (server_config.tool_details and len(server_config.tool_details) > 0) or
        (server_config.resource_details and len(server_config.resource_details) > 0) or
        (server_config.prompt_details and len(server_config.prompt_details) > 0)
    )


def _merge_server_capabilities(
    existing_server: MCPServerConfig,
    imported_server_data: Dict[str, Any]
) -> MCPServerConfig:
    """
    Intelligently merge capabilities from imported VMCP with existing server capabilities.
    
    Rules:
    - If existing server has discovered capabilities: keep ours, ignore imported
    - If existing server doesn't have discovered capabilities and imported has them: use imported
    
    Args:
        existing_server: Existing server configuration
        imported_server_data: Server data from imported VMCP (as dictionary)
        
    Returns:
        Updated server config with merged capabilities
    """
    has_discovered = _has_discovered_capabilities(existing_server)
    
    if has_discovered:
        # We have discovered capabilities, keep ours
        logger.info(f"   ✅ Server {existing_server.server_id} has discovered capabilities, keeping ours")
        return existing_server
    
    # Check if imported has capabilities
    imported_has_capabilities = bool(
        (imported_server_data.get('tool_details') and len(imported_server_data.get('tool_details', [])) > 0) or
        (imported_server_data.get('resource_details') and len(imported_server_data.get('resource_details', [])) > 0) or
        (imported_server_data.get('prompt_details') and len(imported_server_data.get('prompt_details', [])) > 0)
    )
    
    if imported_has_capabilities:
        logger.info(f"   📥 Server {existing_server.server_id} has no discovered capabilities, using imported")
        # Merge capabilities from imported
        if imported_server_data.get('tools'):
            existing_server.tools = imported_server_data.get('tools', [])
        if imported_server_data.get('resources'):
            existing_server.resources = imported_server_data.get('resources', [])
        if imported_server_data.get('prompts'):
            existing_server.prompts = imported_server_data.get('prompts', [])
        if imported_server_data.get('tool_details'):
            existing_server.tool_details = imported_server_data.get('tool_details', [])
        if imported_server_data.get('resource_details'):
            existing_server.resource_details = imported_server_data.get('resource_details', [])
        if imported_server_data.get('prompt_details'):
            existing_server.prompt_details = imported_server_data.get('prompt_details', [])
        if imported_server_data.get('resource_templates'):
            existing_server.resource_templates = imported_server_data.get('resource_templates', [])
        if imported_server_data.get('resource_template_details'):
            existing_server.resource_template_details = imported_server_data.get('resource_template_details', [])
        
        # Update capabilities dict
        existing_server.capabilities = {
            "tools": bool(existing_server.tools and len(existing_server.tools) > 0),
            "resources": bool(existing_server.resources and len(existing_server.resources) > 0),
            "prompts": bool(existing_server.prompts and len(existing_server.prompts) > 0)
        }
    
    return existing_server


async def _process_servers_for_vmcp_import(
    vmcp_id: str,
    selected_servers: List[Any],
    config_manager: MCPConfigManager,
    client_manager: MCPClientManager
) -> List[Dict[str, Any]]:
    """
    Process servers from imported VMCP config.
    
    For each server:
    - If exists: check capabilities, merge if needed, ping for status, update vmcps_using_server
    - If doesn't exist: create server, reset sensitive fields, ping for status, discover capabilities
    
    Args:
        vmcp_id: ID of the VMCP being imported
        selected_servers: List of servers from imported VMCP config
        config_manager: MCPConfigManager instance
        client_manager: MCPClientManager instance
        
    Returns:
        List of processed server dictionaries with updated statuses
    """
    processed_servers = []
    
    if not selected_servers:
        logger.info(f"   ℹ️  No servers to process for vMCP {vmcp_id}")
        return processed_servers
    
    logger.info(f"   🔍 Processing {len(selected_servers)} servers from imported vMCP config for vMCP {vmcp_id}")
    
    for server in selected_servers:
        # Convert server to dict if it's an object
        if hasattr(server, 'to_dict'):
            server_dict = server.to_dict()
        elif hasattr(server, 'dict'):
            server_dict = server.dict()
        elif hasattr(server, 'model_dump'):
            server_dict = server.model_dump()
        else:
            server_dict = dict(server) if isinstance(server, dict) else {}
        
        server_id = server_dict.get('server_id')
        server_name = server_dict.get('name')
        
        # Skip servers without valid ID or name
        if not server_id and not server_name:
            logger.warning(f"   ⚠️  Skipping server with no ID or name: {server_dict}")
            continue
        
        # Check if server exists
        existing_server = config_manager.get_server(server_id) if server_id else None
        
        if existing_server:
            # Server exists - merge capabilities and update status
            logger.info(f"   🔍 Found existing server: {server_name} ({server_id})")
            
            try:
                # Merge capabilities intelligently
                existing_server = _merge_server_capabilities(existing_server, server_dict)
                
                # Ping server to get actual connection status (ignore imported status)
                try:
                    ping_status = await config_manager.ping_server(server_id, client_manager)
                    logger.info(f"   📡 Server {server_name} ping result: {ping_status.value}")
                    config_manager.update_server_status(server_id, ping_status)
                    existing_server.status = ping_status
                except AuthenticationError as e:
                    logger.debug(f"   ❌ Authentication error for server {server_name}: {e}")
                    ping_status = MCPConnectionStatus.AUTH_REQUIRED
                    config_manager.update_server_status(server_id, ping_status)
                    existing_server.status = ping_status
                except Exception as e:
                    logger.error(f"   ❌ Error pinging server {server_name}: {e}")
                    ping_status = MCPConnectionStatus.UNKNOWN
                    config_manager.update_server_status(server_id, ping_status)
                    existing_server.status = ping_status
                
                # Update vmcps_using_server to include new vmcp_id
                vmcps_using_server = existing_server.vmcps_using_server or []
                if vmcp_id not in vmcps_using_server:
                    vmcps_using_server.append(vmcp_id)
                    existing_server.vmcps_using_server = list(set(vmcps_using_server))
                
                # Save updated server config
                config_manager.update_server_config(server_id, existing_server)
                
                # Create server copy for response
                server_copy = server_dict.copy()
                server_copy['status'] = existing_server.status.value
                server_copy['vmcps_using_server'] = existing_server.vmcps_using_server
                # Don't include auth/session_id in response
                server_copy['auth'] = None
                server_copy['session_id'] = None
                
                processed_servers.append(server_copy)
                
            except Exception as e:
                logger.error(f"   ❌ Error processing existing server {server_name}: {e}")
                logger.error(f"   ❌ Traceback: {traceback.format_exc()}")
                # Add server with error status
                server_copy = server_dict.copy()
                server_copy['status'] = 'error'
                processed_servers.append(server_copy)
        else:
            # Server doesn't exist - create it from imported config
            logger.info(f"   🔧 Creating new server from imported vMCP config: {server_name}")
            
            try:
                # Create a copy of the server dict and reset sensitive fields
                server_data = server_dict.copy()
                
                # Reset sensitive fields
                server_data['auth'] = None
                server_data['session_id'] = None
                server_data['vmcps_using_server'] = [vmcp_id]
                server_data['status'] = MCPConnectionStatus.DISCONNECTED.value
                
                # Create server config from the dictionary
                server_config = MCPServerConfig.from_dict(server_data)
                
                # Add server to config
                success = config_manager.add_server(server_config)
                if not success:
                    logger.error(f"   ❌ Failed to create server {server_name}")
                    # Add server with error status
                    server_copy = server_dict.copy()
                    server_copy['status'] = 'error'
                    processed_servers.append(server_copy)
                    continue
                
                logger.info(f"   ✅ Created server {server_name} with ID: {server_config.server_id}")
                
                # Try to ping the new server to get actual status
                try:
                    ping_status = await config_manager.ping_server(server_config.server_id, client_manager)
                    logger.info(f"   📡 New server {server_name} ping result: {ping_status.value}")
                    config_manager.update_server_status(server_config.server_id, ping_status)
                    server_config.status = ping_status
                    
                    # If ping succeeded and server is connected, try to discover capabilities
                    if ping_status == MCPConnectionStatus.CONNECTED:
                        try:
                            capabilities = await client_manager.discover_capabilities(server_config.server_id)
                            if capabilities:
                                logger.info(f"   🔍 Discovered capabilities for new server {server_name}")
                                # Update server config with discovered capabilities
                                if capabilities.get('tools', []):
                                    server_config.tools = capabilities.get('tools', [])
                                if capabilities.get('resources', []):
                                    server_config.resources = capabilities.get('resources', [])
                                if capabilities.get('prompts', []):
                                    server_config.prompts = capabilities.get('prompts', [])
                                if capabilities.get('tool_details', []):
                                    server_config.tool_details = capabilities.get('tool_details', [])
                                if capabilities.get('resource_details', []):
                                    server_config.resource_details = capabilities.get('resource_details', [])
                                if capabilities.get('prompt_details', []):
                                    server_config.prompt_details = capabilities.get('prompt_details', [])
                                if capabilities.get('resource_templates', []):
                                    server_config.resource_templates = capabilities.get('resource_templates', [])
                                if capabilities.get('resource_template_details', []):
                                    server_config.resource_template_details = capabilities.get('resource_template_details', [])
                                
                                server_config.capabilities = {
                                    "tools": bool(server_config.tools and len(server_config.tools) > 0),
                                    "resources": bool(server_config.resources and len(server_config.resources) > 0),
                                    "prompts": bool(server_config.prompts and len(server_config.prompts) > 0)
                                }
                                
                                # Save updated config
                                config_manager.update_server_config(server_config.server_id, server_config)
                        except Exception as e:
                            logger.warning(f"   ⚠️  Could not discover capabilities for new server {server_name}: {e}")
                            # If discovery fails but imported has capabilities, use imported
                            if (server_dict.get('tool_details') or server_dict.get('resource_details') or 
                                server_dict.get('prompt_details')):
                                logger.info(f"   📥 Using imported capabilities for server {server_name}")
                                if server_dict.get('tools'):
                                    server_config.tools = server_dict.get('tools', [])
                                if server_dict.get('resources'):
                                    server_config.resources = server_dict.get('resources', [])
                                if server_dict.get('prompts'):
                                    server_config.prompts = server_dict.get('prompts', [])
                                if server_dict.get('tool_details'):
                                    server_config.tool_details = server_dict.get('tool_details', [])
                                if server_dict.get('resource_details'):
                                    server_config.resource_details = server_dict.get('resource_details', [])
                                if server_dict.get('prompt_details'):
                                    server_config.prompt_details = server_dict.get('prompt_details', [])
                                if server_dict.get('resource_templates'):
                                    server_config.resource_templates = server_dict.get('resource_templates', [])
                                if server_dict.get('resource_template_details'):
                                    server_config.resource_template_details = server_dict.get('resource_template_details', [])
                                
                                server_config.capabilities = {
                                    "tools": bool(server_config.tools and len(server_config.tools) > 0),
                                    "resources": bool(server_config.resources and len(server_config.resources) > 0),
                                    "prompts": bool(server_config.prompts and len(server_config.prompts) > 0)
                                }
                                
                                config_manager.update_server_config(server_config.server_id, server_config)
                    
                except AuthenticationError as e:
                    logger.debug(f"   ❌ Authentication error for new server {server_name}: {e}")
                    ping_status = MCPConnectionStatus.AUTH_REQUIRED
                    config_manager.update_server_status(server_config.server_id, ping_status)
                    server_config.status = ping_status
                    config_manager.update_server_config(server_config.server_id, server_config)
                except Exception as e:
                    logger.error(f"   ❌ Error pinging new server {server_name}: {e}")
                    ping_status = MCPConnectionStatus.UNKNOWN
                    config_manager.update_server_status(server_config.server_id, ping_status)
                    server_config.status = ping_status
                    config_manager.update_server_config(server_config.server_id, server_config)
                
                # Create server copy for response
                server_copy = server_dict.copy()
                server_copy['status'] = server_config.status.value
                server_copy['vmcps_using_server'] = server_config.vmcps_using_server
                server_copy['auth'] = None
                server_copy['session_id'] = None
                
                processed_servers.append(server_copy)
                
            except Exception as e:
                logger.error(f"   ❌ Error creating server {server_name}: {e}")
                logger.error(f"   ❌ Traceback: {traceback.format_exc()}")
                # Add server with error status
                server_copy = server_dict.copy()
                server_copy['status'] = 'error'
                processed_servers.append(server_copy)
    
    return processed_servers


def _merge_vmcp_capabilities(
    processed_servers: List[Dict[str, Any]],
    public_vmcp_config: Dict[str, Any],
    config_manager: MCPConfigManager
) -> Dict[str, Dict[str, List[str]]]:
    """
    Intelligently merge tools, resources, and prompts from public vMCP and user's existing servers.
    
    For each server:
    - If server exists in user's config AND has complete details (tools/resources/prompts), use user's details
    - If server exists but missing details, use public vMCP's details
    - If server doesn't exist, use public vMCP's details
    
    Returns:
        Dict with keys: 'selected_tools', 'selected_resources', 'selected_prompts'
    """
    result = {
        'selected_tools': {},
        'selected_resources': {},
        'selected_prompts': {}
    }
    
    # Get public vMCP's selected items
    public_selected_tools = public_vmcp_config.get('selected_tools', {})
    public_selected_resources = public_vmcp_config.get('selected_resources', {})
    public_selected_prompts = public_vmcp_config.get('selected_prompts', {})
    
    for server in processed_servers:
        server_id = server.get('server_id')
        if not server_id:
            continue
        
        # Check if server exists in user's config
        existing_server = config_manager.get_server(server_id)
        
        if existing_server:
            # Server exists - check if it has complete details
            has_tools = existing_server.tools and len(existing_server.tools) > 0
            has_resources = existing_server.resources and len(existing_server.resources) > 0
            has_prompts = existing_server.prompts and len(existing_server.prompts) > 0
            
            # Use user's details if available, otherwise fall back to public vMCP
            if has_tools:
                result['selected_tools'][server_id] = existing_server.tools.copy()
            elif server_id in public_selected_tools:
                result['selected_tools'][server_id] = public_selected_tools[server_id].copy()
            
            if has_resources:
                result['selected_resources'][server_id] = existing_server.resources.copy()
            elif server_id in public_selected_resources:
                result['selected_resources'][server_id] = public_selected_resources[server_id].copy()
            
            if has_prompts:
                result['selected_prompts'][server_id] = existing_server.prompts.copy()
            elif server_id in public_selected_prompts:
                result['selected_prompts'][server_id] = public_selected_prompts[server_id].copy()
        else:
            # Server doesn't exist - use public vMCP's details
            if server_id in public_selected_tools:
                result['selected_tools'][server_id] = public_selected_tools[server_id].copy()
            if server_id in public_selected_resources:
                result['selected_resources'][server_id] = public_selected_resources[server_id].copy()
            if server_id in public_selected_prompts:
                result['selected_prompts'][server_id] = public_selected_prompts[server_id].copy()
    
    return result


@router.post("/install", response_model=VMCPInstallResponse)
async def install_vmcp_from_remote(
    request: VMCPInstallRequest, 
    user_context: UserContext = Depends(get_user_context)
) -> VMCPInstallResponse:
    """Install a vMCP from remote source (public or well-known) by copying JSON as-is and adding remote tag
    
    Enterprise-only endpoint. Returns 403 in OSS mode.
    """
    # Check if enterprise mode (feature gate check)
    try:
        from feature_gates import features
        if not features.is_enterprise:
            raise HTTPException(status_code=403, detail="Install endpoint is only available in Enterprise edition")
    except ImportError:
        # If feature_gates module doesn't exist, we're in OSS mode
        raise HTTPException(status_code=403, detail="Install endpoint is only available in Enterprise edition")
    
    from urllib.parse import unquote
    public_vmcp_id = unquote(request.public_vmcp_id)
    logger.info(f"📋 Install  a public vMCP {public_vmcp_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")
    
    try:
        # Get managers from global connection manager
        config_manager = MCPConfigManager(user_context.user_id)
        client_manager = MCPClientManager(config_manager)
        user_vmcp_manager = VMCPConfigManager(user_context.user_id)
        
        """
        Read the public vMCP details and convert to VMCPConfig
        """
        try:
            public_vmcp_dict = user_vmcp_manager.get_public_vmcp(public_vmcp_id)
            if not public_vmcp_dict:
                raise HTTPException(status_code=404, detail=f"Public vMCP '{public_vmcp_id}' not found")
            # Store original dict before converting to VMCPConfig (needed for copying tools/resources/prompts)
            original_public_vmcp_dict = public_vmcp_dict.copy()
            public_vmcp = VMCPConfig.from_dict(public_vmcp_dict)
        except Exception as e:
            logger.error(f"Error getting public vMCP: {traceback.format_exc()}")
            logger.error(f"Error converting public vMCP to VMCPConfig: {e}")
            raise HTTPException(status_code=404, detail=f"Error converting public vMCP to VMCPConfig: {e}")
        
        logger.info(f"Public vMCP {public_vmcp.id}: {public_vmcp.to_dict().keys()}")
        """
        Create a registry vMCP config from the public vMCP
        """
        # try:
        #     registry_vmcp = public_vmcp.to_vmcp_registry_config()
        #     public_vmcp_registry_data = {
        #         "vmcp_registry_config": registry_vmcp.to_dict(),
        #         "vmcp_config": public_vmcp.to_dict()
        #     }
        # except Exception as e:
        #     logger.error(f"Error converting public vMCP to VMCPRegistryConfig: {traceback.format_exc()}")
        #     logger.error(f"Error converting public vMCP to VMCPRegistryConfig: {e}")
        #     raise HTTPException(status_code=404, detail=f"Error converting public vMCP to VMCPRegistryConfig: {e}")
        
        # """
        # Update users public vmcp registry with the new registry vMCP
        # """
        # try:
        #     user_vmcp_manager.storage.update_public_vmcp_registry(public_vmcp.id, public_vmcp_registry_data, "add")
        # except Exception as e:
        #     logger.error(f"Error updating users public vmcp registry: {traceback.format_exc()}")
        #     logger.error(f"Error updating users public vmcp registry: {e}")
        #     raise HTTPException(status_code=404, detail=f"Error updating users public vmcp registry: {e}")

        # logger.info(f"Updated user public vMCP registry for Public vMCP {public_vmcp.id}: {public_vmcp.to_dict().keys()}")

        # Extract vmcp_config before processing servers (has complete tool details from vmcp_config column)
        original_vmcp_config = original_public_vmcp_dict.get('vmcp_config', {})
        
        # Process servers using shared function (same as import flow)
        # Use selected_servers from vmcp_config column (has complete tool details) instead of registry config
        selected_servers = original_vmcp_config.get('selected_servers', []) if original_vmcp_config else []
        processed_servers = await _process_servers_for_vmcp_import(
            vmcp_id=public_vmcp.id,
            selected_servers=selected_servers,
            config_manager=config_manager,
            client_manager=client_manager
        )
        
        # Update the vMCP config with processed servers (with actual statuses)
        public_vmcp.vmcp_config['selected_servers'] = processed_servers
        
        # Intelligently merge tools, resources, and prompts from public vMCP and user's existing servers
        # original_vmcp_config is already extracted above
        if original_vmcp_config:
            merged_capabilities = _merge_vmcp_capabilities(
                processed_servers=processed_servers,
                public_vmcp_config=original_vmcp_config,
                config_manager=config_manager
            )
            
            # Apply merged capabilities to vMCP config
            if merged_capabilities['selected_tools']:
                public_vmcp.vmcp_config['selected_tools'] = merged_capabilities['selected_tools']
                logger.info(f"   📋 Merged tools for {len(merged_capabilities['selected_tools'])} servers")
            
            if merged_capabilities['selected_resources']:
                public_vmcp.vmcp_config['selected_resources'] = merged_capabilities['selected_resources']
                logger.info(f"   📋 Merged resources for {len(merged_capabilities['selected_resources'])} servers")
            
            if merged_capabilities['selected_prompts']:
                public_vmcp.vmcp_config['selected_prompts'] = merged_capabilities['selected_prompts']
                logger.info(f"   📋 Merged prompts for {len(merged_capabilities['selected_prompts'])} servers")
            
            # Update total counts
            if 'selected_tools' in public_vmcp.vmcp_config:
                public_vmcp.total_tools = sum(len(tools) for tools in public_vmcp.vmcp_config['selected_tools'].values())
            if 'selected_resources' in public_vmcp.vmcp_config:
                public_vmcp.total_resources = sum(len(resources) for resources in public_vmcp.vmcp_config['selected_resources'].values())
            if 'selected_prompts' in public_vmcp.vmcp_config:
                public_vmcp.total_prompts = sum(len(prompts) for prompts in public_vmcp.vmcp_config['selected_prompts'].values())
        
        # Save the processed vMCP to UserPublicVMCPRegistry (enterprise only)
        # This happens AFTER server processing so we have the complete processed config
        try:
            # OLD CODE 
            #user_vmcp_manager.save_vmcp_config(public_vmcp)
            #logger.info(f"   ✅ Saved vMCP to database with processed servers")
            # NEW CODE
            registry_vmcp = public_vmcp.to_vmcp_registry_config()
            public_vmcp_registry_data = {
                "vmcp_registry_config": registry_vmcp.to_dict(),
                "vmcp_config": public_vmcp.to_dict()  # This now contains processed servers
            }
            user_vmcp_manager.storage.update_public_vmcp_registry(public_vmcp.id, public_vmcp_registry_data, "add")
            logger.info(f"   ✅ Saved processed vMCP to UserPublicVMCPRegistry")
        except Exception as e:
            logger.error(f"   ❌ Error saving vMCP to UserPublicVMCPRegistry: {e}")
            logger.error(f"   ❌ Traceback: {traceback.format_exc()}")
            # Don't fail the install - servers are processed, just log the error
        
        # Count server statuses
        server_status_counts = {}
        for server in processed_servers:
            status = server.get('status', 'unknown')
            server_status_counts[status] = server_status_counts.get(status, 0) + 1
        
        logger.info(f"✅ Installed vMCP from remote: {public_vmcp.id} ({public_vmcp.name})")
        logger.info(f"   📊 Server status summary: {server_status_counts}")
        
        # Convert to type-safe response model
        # Update vmcp_config with processed servers before creating response
        vmcp_config_dict = public_vmcp.vmcp_config.copy() if public_vmcp.vmcp_config else {}
        vmcp_config_dict['selected_servers'] = processed_servers
        
        vmcp_info = VMCPInfo(
            id=public_vmcp.id,
            name=public_vmcp.name,
            description=public_vmcp.description or None,
            status="active",  # Default status
            user_id=str(user_context.user_id),
            system_prompt=public_vmcp.system_prompt,
            vmcp_config=vmcp_config_dict,
            custom_prompts=public_vmcp.custom_prompts or [],
            custom_tools=public_vmcp.custom_tools or [],
            custom_context=public_vmcp.custom_context or [],
            custom_resources=public_vmcp.custom_resources or [],
            custom_resource_templates=getattr(public_vmcp, 'custom_resource_templates', None) or [],
            custom_widgets=getattr(public_vmcp, 'custom_widgets', None) or [],
            custom_resource_uris=getattr(public_vmcp, 'custom_resource_uris', None) or [],
            environment_variables=public_vmcp.environment_variables or [],
            uploaded_files=getattr(public_vmcp, 'uploaded_files', None) or [],
            created_at=public_vmcp.created_at,
            updated_at=public_vmcp.updated_at,
            total_tools=getattr(public_vmcp, 'total_tools', None),
            total_resources=getattr(public_vmcp, 'total_resources', None),
            total_resource_templates=getattr(public_vmcp, 'total_resource_templates', None),
            total_prompts=getattr(public_vmcp, 'total_prompts', None),
            creator_id=getattr(public_vmcp, 'creator_id', None),
            creator_username=getattr(public_vmcp, 'creator_username', None),
            is_public=getattr(public_vmcp, 'is_public', False),
            public_tags=getattr(public_vmcp, 'public_tags', []) or [],
            public_at=getattr(public_vmcp, 'public_at', None),
            is_wellknown=getattr(public_vmcp, 'is_wellknown', False),
            metadata=getattr(public_vmcp, 'metadata', {}) or {}
        )
        
        return VMCPInstallResponse(
            success=True,
            message=f"vMCP '{public_vmcp.name}' installed successfully",
            data=vmcp_info,
            servers_processed=len(processed_servers),
            server_status_summary=server_status_counts
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error installing vMCP from remote: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to install vMCP from remote: {str(e)}")

@router.get("/list", response_model=VMCPListResponse)
async def list_vmcps(user_context: UserContext = Depends(get_user_context)) -> VMCPListResponse:
    """List all available vMCP configurations for the current user with full configuration data"""
    logger.info("📋 List vMCPs endpoint called")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")
    
    try:
        # Get managers from global connection manager
        config_manager = MCPConfigManager(user_context.user_id)
        client_manager = MCPClientManager(config_manager)
        user_vmcp_manager = VMCPConfigManager(user_context.user_id)
        vmcps = user_vmcp_manager.list_available_vmcps()
        logger.info(f"   📊 Found {len(vmcps)} vMCPs")
        # # Return full vMCP configuration data instead of just VMCPInfo
        # full_vmcp_data = []
        # vmcp_manager = VMCPConfigManager(user_context.user_id)
        # for vmcp in tqdm(vmcps, desc="Loading vMCPs"):
        #     try:
        #         # Load the full configuration for each vMCP
                
        #         full_config = vmcp_manager.load_vmcp_config(specific_vmcp_id=vmcp['id'])
        #             # Create the full vMCP data object
        #         vmcp_data = full_config.for_vmcp_listing()
        #         full_vmcp_data.append(vmcp_data)
                    
        #     except Exception as e:
        #         logger.warn(f"   ⚠️ Failed to load full config for vMCP {vmcp.get('id', 'unknown')}: {e}")
        #         # Fallback to basic info if full config fails to load
        #         full_vmcp_data.append(vmcp)
        
        # Normalize vMCPs to ensure they have required fields for VMCPListSummary
        normalized_vmcps = []
        for vmcp in vmcps:
            normalized_vmcp = {
                "id": vmcp.get("id") or vmcp.get("vmcp_id", ""),
                "name": vmcp.get("name", "Unnamed vMCP"),
                "description": vmcp.get("description"),
                "status": vmcp.get("status", "active"),  # Default to "active" if not present
                "user_id": vmcp.get("user_id") or str(user_context.user_id) if user_context else None,
                "created_at": vmcp.get("created_at"),
                "updated_at": vmcp.get("updated_at"),
                "total_tools": vmcp.get("total_tools", 0),
                "total_resources": vmcp.get("total_resources", 0),
                "total_prompts": vmcp.get("total_prompts", 0),
            }
            normalized_vmcps.append(normalized_vmcp)
        ### NEW CODE
        # Query installed public vMCPs (enterprise only)
        public_vmcps = []
        try:
            # Check if enterprise mode by trying to import enterprise model
            from models.user_public_vmcp_registry import UserPublicVMCPRegistry
            from vmcp.storage.database import get_db
            
            # Get database session
            db = next(get_db())
            try:
                # Query UserPublicVMCPRegistry for this user
                installed_public_vmcps = db.query(UserPublicVMCPRegistry).filter(
                    UserPublicVMCPRegistry.user_id == user_context.user_id
                ).all()
                
                # Convert to VMCPListSummary format
                for installed_vmcp in installed_public_vmcps:
                    vmcp_config = installed_vmcp.vmcp_config or {}
                    public_vmcp = {
                        "id": installed_vmcp.public_vmcp_id,
                        "name": installed_vmcp.name,
                        "description": installed_vmcp.description,
                        "status": "active",  # Default status
                        "user_id": str(installed_vmcp.user_id),
                        "created_at": installed_vmcp.created_at.isoformat() if installed_vmcp.created_at else None,
                        "updated_at": installed_vmcp.updated_at.isoformat() if installed_vmcp.updated_at else None,
                        "total_tools": sum(len(tools) for tools in vmcp_config.get('selected_tools', {}).values()) if isinstance(vmcp_config.get('selected_tools'), dict) else 0,
                        "total_resources": sum(len(resources) for resources in vmcp_config.get('selected_resources', {}).values()) if isinstance(vmcp_config.get('selected_resources'), dict) else 0,
                        "total_prompts": sum(len(prompts) for prompts in vmcp_config.get('selected_prompts', {}).values()) if isinstance(vmcp_config.get('selected_prompts'), dict) else 0,
                    }
                    public_vmcps.append(public_vmcp)
                
                logger.info(f"   📊 Found {len(public_vmcps)} installed public vMCPs")
            finally:
                db.close()
        except ImportError:
            # OSS mode - UserPublicVMCPRegistry not available, return empty list
            logger.debug("Enterprise UserPublicVMCPRegistry not available (OSS mode), returning empty public list")
        except Exception as e:
            # Log error but don't fail the request
            logger.warning(f"   ⚠️ Error querying UserPublicVMCPRegistry: {e}")
        #### ======================
        # Convert to type-safe response model (keeping exact same data structure)
        return VMCPListResponse(
            private=normalized_vmcps,
            public=public_vmcps
        )
        
    except Exception as e:
        logger.error(f"   ❌ Error listing vMCPs: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to list vMCPs: {str(e)}")

# ============================================================================
# vMCP OPERATION ENDPOINTS
# ============================================================================

@router.post("/{vmcp_id}/refresh", response_model=VMCPRefreshResponse)
async def refresh_vmcp(
    vmcp_id: str,
    request: Optional[VMCPRefreshRequest] = None,
    user_context: UserContext = Depends(get_user_context)
) -> VMCPRefreshResponse:
    """Refresh a vMCP configuration for the current user - checks servers and updates status/capabilities"""
    logger.info(f"📋 Refresh vMCP endpoint called for vmcp_id: {vmcp_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")
    
    try:
        # Get managers from global connection manager
        config_manager = MCPConfigManager(user_context.user_id)
        client_manager = MCPClientManager(config_manager)
        user_vmcp_manager = VMCPConfigManager(user_context.user_id, vmcp_id)
        
        # Load the vMCP configuration
        vmcp_config = user_vmcp_manager.load_vmcp_config()
        if not vmcp_config:
            raise HTTPException(status_code=404, detail=f"vMCP '{vmcp_id}' not found")
        
        # Process servers in the vMCP config
        processed_servers = []
        selected_servers = vmcp_config.vmcp_config.get('selected_servers', [])
        logger.info(f"   🔍 Processing {len(selected_servers)} servers from vMCP config for vMCP {vmcp_id}")
        
        for server in selected_servers:
            server_id = server.get('server_id')
            server_name = server.get('name')
            server_data = server
            
            # Check if server already exists in server list
            existing_server = config_manager.get_server_by_id(server_id)
            
            mcp_server = None
            
            if existing_server:
                # Server exists, use it
                logger.info(f"   ✅ Found existing server: {existing_server.name} ({existing_server.server_id})")
                mcp_server = existing_server
                server_name  = mcp_server.name
                server_id = mcp_server.server_id
            else:
                user_vmcp_manager._create_server_from_vmcp_config(server_data, vmcp_id)
                mcp_server = config_manager.get_server_by_id(server_id,from_db=True)
                logger.info(f"   ✅ Fetched new server from db: {mcp_server.name if mcp_server else 'None'} ({mcp_server.server_id if mcp_server else 'None'})")
            
            # Try to connect and discover capabilities and upate server config
            try:
                logger.info(f"   🔗 Attempting to connect to server: {server_name}")
                if mcp_server:
                    # Ping the server to get current status
                    try:
                        current_status = await client_manager.ping_server(mcp_server.server_id)
                        logger.info(f"   🔍 Server {mcp_server.name}: ping result = {current_status.value}")
                    except AuthenticationError as e:
                        logger.error(f"   ❌ Traceback: {traceback.format_exc()}")
                        logger.debug(f"   ❌ Authentication error for server {mcp_server.name}: {e}")
                        current_status = MCPConnectionStatus.AUTH_REQUIRED
                    except Exception as e:
                        logger.error(f"   ❌ Traceback: {traceback.format_exc()}")
                        logger.error(f"   ❌ Error pinging server {mcp_server.name}: {mcp_server.server_id}: {e}")
                        current_status = MCPConnectionStatus.UNKNOWN

                    mcp_server.status = current_status
                    
                    # Discover capabilities
                    try:
                        capabilities = await client_manager.discover_capabilities(mcp_server.server_id)
                    except Exception as e:
                        logger.error(f"   ❌ Error discovering capabilities for server {mcp_server.name}: {mcp_server.server_id}: {e}")
                        logger.error(f"   ❌ Traceback: {traceback.format_exc()}")
                        capabilities = None

                
                    if capabilities:
                        # Update server config with discovered capabilities
                        if capabilities.get('tools',[]):
                            mcp_server.tools = capabilities.get('tools', [])
                        if capabilities.get('resources',[]):
                            mcp_server.resources = capabilities.get('resources', [])
                        if capabilities.get('prompts',[]):
                            mcp_server.prompts = capabilities.get('prompts', [])
                        if capabilities.get('tool_details',[]):
                            mcp_server.tool_details = capabilities.get('tool_details', [])
                        if capabilities.get('resource_details',[]):
                            mcp_server.resource_details = capabilities.get('resource_details', [])
                        if capabilities.get('resource_templates',[]):
                            mcp_server.resource_templates = capabilities.get('resource_templates', [])
                        if capabilities.get('resource_template_details',[]):
                            mcp_server.resource_template_details = capabilities.get('resource_template_details', [])
                        if capabilities.get('prompt_details',[]):
                            mcp_server.prompt_details = capabilities.get('prompt_details', [])
                        
                        mcp_server.capabilities = {
                            "tools": bool(mcp_server.tools and len(mcp_server.tools) > 0),
                            "resources": bool(mcp_server.resources and len(mcp_server.resources) > 0),
                            "prompts": bool(mcp_server.prompts and len(mcp_server.prompts) > 0)
                        }

                    vmcps_using_server = mcp_server.vmcps_using_server
                    if vmcps_using_server:
                        logger.info(f"   🔄 vMCPs using server {mcp_server.server_id}: {vmcps_using_server}")
                        # Add vmcp id to vmcps_using_server
                        vmcps_using_server.append(vmcp_id)
                        mcp_server.vmcps_using_server = list(set(vmcps_using_server))
                    else:
                        mcp_server.vmcps_using_server = [vmcp_id]
                    
                    logger.info(f"   ✅ Successfully tried to discover capabilities for server '{mcp_server.server_id} Current status {mcp_server.status.value}'")
                    
                    # Save updated server config
                    config_manager.update_server_config(mcp_server.server_id, mcp_server)
                    
            except Exception as e:
                logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
                logger.warning(f"   ⚠️ Failed to connect/discover capabilities for server {mcp_server.name}: {mcp_server.server_id}: {e}")
                # Continue anyway - server will be added but not connected
            
            processed_servers.append(mcp_server.server_id)
            mcp_server = config_manager.get_server_by_id(mcp_server.server_id)
            logger.info(f"   📊 Server to add: {mcp_server.status.value}")
            # Add server to vMCP configuration
            server_for_vmcp = mcp_server.to_dict_for_vmcp()
            
            # Update vMCP config
            updated_vmcp_config = vmcp_config.vmcp_config.copy() if vmcp_config.vmcp_config else {}
            
            # Add server to selected_servers
            selected_servers = updated_vmcp_config.get('selected_servers', [])
            if not any(s.get('server_id') == server_for_vmcp.get('server_id') for s in selected_servers):
                selected_servers.append(server_for_vmcp)
                updated_vmcp_config['selected_servers'] = selected_servers
            

        #==============================================
        # Convert to type-safe response model
        return VMCPRefreshResponse(
            success=True,
            message=f"vMCP '{vmcp_config.name}' refreshed successfully",
            data={
                "vmcp_id": vmcp_id,
                "servers_processed": len(processed_servers),
                "servers": processed_servers
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error refreshing vMCP '{vmcp_id}': {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh vMCP: {str(e)}")

@router.get("/{vmcp_id}", response_model=VMCPDetailsResponse)
async def get_vmcp_details(
    vmcp_id: str,
    user_context: UserContext = Depends(get_user_context)
) -> VMCPDetailsResponse:
    """Get detailed information about a specific vMCP with type-safe response model."""
    logger.info(f"📋 Get vMCP details endpoint called for: {vmcp_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")
    
    try:
        # Get managers
        vmcp_config_manager = VMCPConfigManager(user_context.user_id)
        
        # Get vMCP config
        vmcp_config = vmcp_config_manager.load_vmcp_config(vmcp_id)
        if not vmcp_config:
            raise HTTPException(status_code=404, detail=f"vMCP '{vmcp_id}' not found")
        
        # Convert to type-safe response model
        vmcp_dict = vmcp_config.to_dict()
        return VMCPDetailsResponse(**vmcp_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error getting vMCP details: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get vMCP details: {str(e)}")

@router.put("/{vmcp_id}", response_model=VMCPUpdateResponse)
async def update_vmcp(
    vmcp_id: str, 
    request: VMCPUdateRequest, 
    user_context: UserContext = Depends(get_user_context)
) -> VMCPUpdateResponse:
    """Update a vMCP configuration with type-safe request/response models."""
    logger.info(f"📋 Update vMCP endpoint called for: {vmcp_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")
    
    try:
        # Get managers
        vmcp_config_manager = VMCPConfigManager(user_context.user_id)
        user_vmcp_manager = VMCPConfigManager(user_context.user_id, vmcp_id)
        
        # Get existing vMCP config
        vmcp_config = vmcp_config_manager.load_vmcp_config(vmcp_id)
        if not vmcp_config:
            raise HTTPException(status_code=404, detail=f"vMCP '{vmcp_id}' not found")
        
        # Check if name is being changed
        new_name = request.name
        if new_name != vmcp_config.name:
            # Check if new name already exists
            existing_vmcp_id = vmcp_config_manager.storage.find_vmcp_name_in_private_registry(new_name)
            if existing_vmcp_id:
                raise HTTPException(status_code=409, detail=f"vMCP with name '{new_name}' already exists")
            logger.info(f"   🔄 vMCP name will be changed from '{vmcp_config.name}' to '{new_name}'")
        
        # Update vMCP configuration using the exact same logic as original router
        success = user_vmcp_manager.update_vmcp_config(
            vmcp_id=vmcp_id,
            name=request.name,
            description=request.description,
            system_prompt=request.system_prompt,
            vmcp_config=request.vmcp_config,
            custom_prompts=request.custom_prompts,
            custom_tools=request.custom_tools,
            custom_context=request.custom_context,
            custom_resources=request.custom_resources,
            custom_resource_uris=request.custom_resource_uris,
            environment_variables=request.environment_variables,
            uploaded_files=request.uploaded_files,
            metadata=request.metadata
        )
        
        if not success:
            raise HTTPException(status_code=404, detail=f"vMCP '{vmcp_id}' not found")
        
        # Get the updated vMCP details
        updated_vmcp = user_vmcp_manager.load_vmcp_config()
        
        logger.info(f"✅ Updated vMCP: {vmcp_id}")
        
        # Convert to VMCPInfo for type-safe response
        vmcp_info = VMCPInfo(
            id=updated_vmcp.id,
            name=updated_vmcp.name,
            description=updated_vmcp.description or None,
            status="active",  # Default status
            user_id=str(user_context.user_id),
            system_prompt=updated_vmcp.system_prompt,
            vmcp_config=updated_vmcp.vmcp_config or {},
            custom_prompts=updated_vmcp.custom_prompts or [],
            custom_tools=updated_vmcp.custom_tools or [],
            custom_context=updated_vmcp.custom_context or [],
            custom_resources=updated_vmcp.custom_resources or [],
            custom_resource_templates=getattr(updated_vmcp, 'custom_resource_templates', None) or [],
            custom_widgets=getattr(updated_vmcp, 'custom_widgets', None) or [],
            custom_resource_uris=getattr(updated_vmcp, 'custom_resource_uris', None) or [],
            environment_variables=updated_vmcp.environment_variables or [],
            uploaded_files=updated_vmcp.uploaded_files or [],
            total_tools=updated_vmcp.total_tools,
            total_resources=updated_vmcp.total_resources,
            total_resource_templates=updated_vmcp.total_resource_templates,
            total_prompts=updated_vmcp.total_prompts,
            creator_id=str(updated_vmcp.creator_id) if updated_vmcp.creator_id else None,
            creator_username=str(updated_vmcp.creator_username) if updated_vmcp.creator_username else None,
            is_public=getattr(updated_vmcp, 'is_public', False),
            public_tags=getattr(updated_vmcp, 'public_tags', None) or [],
            public_at=getattr(updated_vmcp, 'public_at', None),
            is_wellknown=getattr(updated_vmcp, 'is_wellknown', False),
            metadata=getattr(updated_vmcp, 'metadata', None) or {},
            created_at=updated_vmcp.created_at,
            updated_at=updated_vmcp.updated_at
        )
        
        return VMCPUpdateResponse(
            success=True,
            vMCP=vmcp_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error updating vMCP: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to update vMCP: {str(e)}")

@router.delete("/{vmcp_id}", response_model=VMCPDeleteResponse)
async def delete_vmcp(
    vmcp_id: str,
    user_context: UserContext = Depends(get_user_context)
) -> VMCPDeleteResponse:
    """Delete a vMCP with type-safe response model."""
    logger.info(f"📋 Delete vMCP endpoint called for: {vmcp_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")
    
    try:
        # Get managers
        vmcp_config_manager = VMCPConfigManager(user_context.user_id)
        
        # Get vMCP config
        vmcp_config = vmcp_config_manager.load_vmcp_config(vmcp_id)
        if not vmcp_config:
            raise HTTPException(status_code=404, detail=f"vMCP '{vmcp_id}' not found")
        
        # Delete vMCP
        result = vmcp_config_manager.delete_vmcp(vmcp_id)
        if not result.get("success", False):
            raise HTTPException(status_code=404 if "not found" in result.get("message", "").lower() else 500, 
                              detail=result.get("message", "Failed to delete vMCP"))
        
        logger.info(f"   ✅ Successfully deleted vMCP '{vmcp_id}'")
        
        return VMCPDeleteResponse(
            success=True,
            message=f"vMCP '{vmcp_id}' deleted successfully",
            data={
                "vmcp_id": vmcp_id,
                "vmcp_name": vmcp_config.name
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error deleting vMCP: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to delete vMCP: {str(e)}")

# ============================================================================
# SHARING AND FORKING ENDPOINTS
# ============================================================================

@router.post("/share", response_model=VMCPShareResponse)
async def share_vmcp(
    request: VMCPShareRequest,
    user_context: UserContext = Depends(get_user_context)
) -> VMCPShareResponse:
    """Share a vMCP publicly with type-safe request/response models."""
    logger.info(f"📋 Share vMCP endpoint called for: {request.vmcp_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")
    
    try:
        # Get managers
        vmcp_config_manager = VMCPConfigManager(user_context.user_id)
        
        # Get vMCP config
        vmcp_config = vmcp_config_manager.load_vmcp_config(request.vmcp_id)
        if not vmcp_config:
            raise HTTPException(status_code=404, detail=f"vMCP '{request.vmcp_id}' not found")
        
        # Update vMCP to be public (following old router pattern)
        success = vmcp_config_manager.update_vmcp_config(
            request.vmcp_id,
            is_public=True,
            public_tags=[request.state.value],
            public_at=datetime.utcnow().isoformat(),
            creator_username=f"user_{user_context.user_id}"
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update vMCP configuration")
        
        logger.info(f"   ✅ Successfully shared vMCP '{request.vmcp_id}'")
        
        return VMCPShareResponse(
            success=True,
            message=f"vMCP '{request.vmcp_id}' shared successfully",
            data={
                "vmcp_id": request.vmcp_id,
                "share_token": f"share_{random.randint(100000, 999999)}",
                "shared_at": datetime.utcnow().isoformat(),
                "public_url": f"/api/vmcps/public/{request.vmcp_id}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error sharing vMCP: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to share vMCP: {str(e)}")

@router.get("/public/list", response_model=List[VMCPConfig])
async def list_public_vmcps(
    user_context: UserContext = Depends(get_user_context)
) -> List[VMCPConfig]:
    """List all publicly shared vMCPs with type-safe response model."""
    logger.info("📋 List public vMCPs endpoint called")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")
    
    try:
        # Get managers using user context (works for both OSS and enterprise)
        vmcp_config_manager = VMCPConfigManager(user_context.user_id)
        
        # Get all public vMCPs (returns List[Dict[str, Any]])
        public_vmcps_dicts = vmcp_config_manager.list_public_vmcps()
        
        # Convert dicts to VMCPConfig objects
        public_vmcps = []
        for vmcp_dict in public_vmcps_dicts:
            try:
                vmcp_config = VMCPConfig.from_dict(vmcp_dict)
                public_vmcps.append(vmcp_config)
            except Exception as e:
                logger.warning(f"   ⚠️  Skipping invalid vMCP dict: {e}")
                continue
        
        logger.info(f"   ✅ Successfully listed {len(public_vmcps)} public vMCPs")
        
        return public_vmcps
        
    except Exception as e:
        logger.error(f"   ❌ Error listing public vMCPs: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to list public vMCPs: {str(e)}")

@router.get("/public/{vmcp_id}", response_model=VMCPDetailsResponse)
async def get_public_vmcp(
    vmcp_id: str,
    user_context: UserContext = Depends(get_user_context)
) -> VMCPDetailsResponse:
    """Get a publicly shared vMCP with type-safe response model."""
    logger.info(f"📋 Get public vMCP endpoint called for: {vmcp_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")
    
    try:
        # Get managers using user context (works for both OSS and enterprise)
        vmcp_config_manager = VMCPConfigManager(user_context.user_id)
        
        # Get public vMCP config (returns Optional[Dict[str, Any]])
        vmcp_config_dict = vmcp_config_manager.get_public_vmcp(vmcp_id)
        if not vmcp_config_dict:
            raise HTTPException(status_code=404, detail=f"Public vMCP '{vmcp_id}' not found")
        
        # Convert dict to VMCPConfig object to ensure proper structure
        try:
            vmcp_config = VMCPConfig.from_dict(vmcp_config_dict)
        except Exception as e:
            logger.error(f"   ❌ Error converting public vMCP to VMCPConfig: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to parse public vMCP data: {str(e)}")
        
        # Convert VMCPConfig to dict and ensure all required fields are present
        vmcp_dict = vmcp_config.to_dict()
        
        # Ensure required fields for VMCPDetailsResponse
        if 'id' not in vmcp_dict or not vmcp_dict['id']:
            vmcp_dict['id'] = vmcp_id
        if 'name' not in vmcp_dict or not vmcp_dict['name']:
            vmcp_dict['name'] = vmcp_config.name or 'Unnamed vMCP'
        if 'user_id' not in vmcp_dict:
            vmcp_dict['user_id'] = user_context.user_id
        if 'created_at' not in vmcp_dict:
            vmcp_dict['created_at'] = vmcp_config.created_at.isoformat() if vmcp_config.created_at else datetime.utcnow().isoformat()
        elif isinstance(vmcp_dict['created_at'], datetime):
            vmcp_dict['created_at'] = vmcp_dict['created_at'].isoformat()
        if 'updated_at' not in vmcp_dict:
            vmcp_dict['updated_at'] = vmcp_config.updated_at.isoformat() if vmcp_config.updated_at else datetime.utcnow().isoformat()
        elif isinstance(vmcp_dict['updated_at'], datetime):
            vmcp_dict['updated_at'] = vmcp_dict['updated_at'].isoformat()
        
        logger.info(f"   ✅ Successfully retrieved public vMCP '{vmcp_id}'")
        
        # Return VMCPDetailsResponse with vMCP data directly (same pattern as private endpoint)
        return VMCPDetailsResponse(**vmcp_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error getting public vMCP: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get public vMCP: {str(e)}")

@router.post("/{vmcp_id}/fork", response_model=VMCPCreateResponse)
async def fork_vmcp(
    vmcp_id: str,
    request: Optional[VMCPForkRequest] = None,
    user_context: UserContext = Depends(get_user_context)
) -> VMCPCreateResponse:
    """Fork a vMCP to create a personal copy with type-safe response model."""
    logger.info(f"📋 Fork vMCP endpoint called for: {vmcp_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")
    
    try:
        # Get managers
        vmcp_config_manager = VMCPConfigManager(user_context.user_id)
        
        # Get original vMCP config
        original_vmcp = vmcp_config_manager.load_vmcp_config(vmcp_id)
        if not original_vmcp:
            raise HTTPException(status_code=404, detail=f"vMCP '{vmcp_id}' not found")
        
        # Create forked vMCP config
        fork_name = request.name if request and request.name else f"{original_vmcp.name} (Fork)"
        fork_description = request.description if request and request.description else f"Forked from {original_vmcp.name}: {original_vmcp.description}"
        forked_vmcp = VMCPConfig(
            name=fork_name,
            description=fork_description,
            servers=original_vmcp.servers.copy(),
            tools=original_vmcp.tools.copy(),
            resources=original_vmcp.resources.copy(),
            prompts=original_vmcp.prompts.copy(),
            environment_variables=original_vmcp.environment_variables.copy(),
            auto_connect=original_vmcp.auto_connect,
            enabled=original_vmcp.enabled,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Generate new vMCP ID
        forked_vmcp_id = forked_vmcp.generate_vmcp_id()
        forked_vmcp.id = forked_vmcp_id
        
        # Save forked vMCP
        success = vmcp_config_manager.save_vmcp_config(forked_vmcp)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save forked vMCP configuration")
        
        logger.info(f"   ✅ Successfully forked vMCP '{vmcp_id}' to '{forked_vmcp_id}'")
        
        # Create response with proper type-safe model
        vmcp_info = VMCPInfo(
            id=forked_vmcp.id,
            name=forked_vmcp.name,
            description=forked_vmcp.description,
            servers=forked_vmcp.servers,
            tools=forked_vmcp.tools,
            resources=forked_vmcp.resources,
            prompts=forked_vmcp.prompts,
            environment_variables=forked_vmcp.environment_variables,
            auto_connect=forked_vmcp.auto_connect,
            enabled=forked_vmcp.enabled,
            created_at=forked_vmcp.created_at,
            updated_at=forked_vmcp.updated_at
        )
        
        return VMCPCreateResponse(
            success=True,
            message=f"vMCP '{vmcp_id}' forked successfully",
            data={
                "original_vmcp_id": vmcp_id,
                "forked_vmcp": vmcp_info
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error forking vMCP: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to fork vMCP: {str(e)}")

# ============================================================================
# CAPABILITIES LISTING ENDPOINTS
# ============================================================================

async def parse_list_tools_request(request: Request) -> VMCPListToolsRequest:
    """Custom dependency to parse list tools request, handling empty bodies."""
    try:
        body = await request.body()
        if not body:
            return VMCPListToolsRequest()
        
        body_dict = json.loads(body) if body else {}
        if not body_dict:
            return VMCPListToolsRequest()
        
        return VMCPListToolsRequest(**body_dict)
    except (json.JSONDecodeError, ValueError):
        return VMCPListToolsRequest()

@router.post("/{vmcp_id}/tools/list", response_model=VMCPToolCallResponse)
async def list_vmcp_tools(
    vmcp_id: str,
    request_model: VMCPListToolsRequest = Depends(parse_list_tools_request),
    user_context: UserContext = Depends(get_user_context)
) -> VMCPToolCallResponse:
    """List all tools available in a vMCP matching original router logic exactly."""
    logger.info(f"📋 List vMCP tools endpoint called for: {vmcp_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")
    
    try:
        # Match original router logic exactly
        user_vmcp_manager = VMCPConfigManager(user_context.user_id, vmcp_id)    
        tools_list = await user_vmcp_manager.tools_list()
        
        # Handle request filters if provided
        filter_by_server = request_model.filter_by_server
        search = request_model.search
        
        logger.info(f"   ✅ Successfully listed {len(tools_list)} tools for vMCP '{vmcp_id}'")

        # Convert Tool objects to dictionaries for Pydantic serialization
        tools_dict_list = [tool.model_dump() if hasattr(tool, 'model_dump') else tool for tool in tools_list]

        return VMCPToolCallResponse(
            success=True,
            message=f"Tools listed successfully for vMCP '{vmcp_id}'",
            data={
                "vmcp_id": vmcp_id,
                "tools": tools_dict_list,
                "total_tools": len(tools_dict_list)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error listing vMCP tools: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to list vMCP tools: {str(e)}")

async def parse_list_resources_request(request: Request) -> VMCPListResourcesRequest:
    """Custom dependency to parse list resources request, handling empty bodies."""
    try:
        body = await request.body()
        if not body:
            return VMCPListResourcesRequest()
        
        body_dict = json.loads(body) if body else {}
        if not body_dict:
            return VMCPListResourcesRequest()
        
        return VMCPListResourcesRequest(**body_dict)
    except (json.JSONDecodeError, ValueError):
        return VMCPListResourcesRequest()

@router.post("/{vmcp_id}/resources/list", response_model=VMCPResourceResponse)
async def list_vmcp_resources(
    vmcp_id: str,
    request_model: VMCPListResourcesRequest = Depends(parse_list_resources_request),
    user_context: UserContext = Depends(get_user_context)
) -> VMCPResourceResponse:
    """List all resources available in a vMCP with type-safe response model."""
    logger.info(f"📋 List vMCP resources endpoint called for: {vmcp_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")
    
    try:
        # Get managers
        vmcp_config_manager = VMCPConfigManager(user_context.user_id)
        
        # Get vMCP config
        vmcp_config = vmcp_config_manager.load_vmcp_config(vmcp_id)
        if not vmcp_config:
            raise HTTPException(status_code=404, detail=f"vMCP '{vmcp_id}' not found")
        
        # Get resources from vMCP config
        resources = vmcp_config.resources or []
        
        logger.info(f"   ✅ Successfully listed {len(resources)} resources for vMCP '{vmcp_id}'")
        
        return VMCPResourceResponse(
            success=True,
            message=f"Resources listed successfully for vMCP '{vmcp_id}'",
            data={
                "vmcp_id": vmcp_id,
                "resources": resources,
                "total_resources": len(resources)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error listing vMCP resources: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to list vMCP resources: {str(e)}")

async def parse_list_prompts_request(request: Request) -> VMCPListPromptsRequest:
    """Custom dependency to parse list prompts request, handling empty bodies."""
    try:
        body = await request.body()
        if not body:
            return VMCPListPromptsRequest()
        
        body_dict = json.loads(body) if body else {}
        # Empty dict or dict with no matching fields - return default
        if not body_dict:
            return VMCPListPromptsRequest()
        
        return VMCPListPromptsRequest(**body_dict)
    except (json.JSONDecodeError, ValueError):
        # If parsing fails, return default
        return VMCPListPromptsRequest()

@router.post("/{vmcp_id}/prompts/list", response_model=VMCPPromptResponse)
async def list_vmcp_prompts(
    vmcp_id: str,
    request_model: VMCPListPromptsRequest = Depends(parse_list_prompts_request),
    user_context: UserContext = Depends(get_user_context)
) -> VMCPPromptResponse:
    """List all prompts available in a vMCP matching original router logic exactly."""
    logger.info(f"📋 List vMCP prompts endpoint called for: {vmcp_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")
    
    try:
        # Match original router logic exactly
        user_vmcp_manager = VMCPConfigManager(user_context.user_id, vmcp_id,
            logging_config={"agent_name": "1xn-test", "client_id": user_context.client_id})
        prompts_list = await user_vmcp_manager.prompts_list()
        
        # Handle request filters if provided
        filter_by_server = request_model.filter_by_server
        search = request_model.search
        
        logger.info(f"   ✅ Successfully listed {len(prompts_list)} prompts for vMCP '{vmcp_id}'")
        
        # Convert Prompt objects to PromptInfo objects
        prompt_infos = []
        for prompt in prompts_list:
            # Handle both dict and Prompt object formats
            if isinstance(prompt, dict):
                prompt_info = PromptInfo(
                    name=prompt.get('name', ''),
                    description=prompt.get('description'),
                    arguments=prompt.get('arguments')
                )
            else:
                # Prompt object from mcp.types
                prompt_info = PromptInfo(
                    name=prompt.name,
                    description=prompt.description,
                    arguments=prompt.arguments.model_dump() if hasattr(prompt.arguments, 'model_dump') else 
                              prompt.arguments if isinstance(prompt.arguments, dict) else None
                )
            prompt_infos.append(prompt_info)
        
        # Create proper response data model
        response_data = VMCPPromptListData(
            vmcp_id=vmcp_id,
            prompts=prompt_infos,
            total_prompts=len(prompt_infos)
        )
        
        return VMCPPromptResponse(
            success=True,
            message=f"Prompts listed successfully for vMCP '{vmcp_id}'",
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error listing vMCP prompts: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to list vMCP prompts: {str(e)}")

# ============================================================================
# EXECUTION ENDPOINTS
# ============================================================================

@router.post("/{vmcp_id}/tools/call", response_model=VMCPToolCallResponse)
async def call_vmcp_tool(
    vmcp_id: str,
    request: VMCPToolCallRequest,
    user_context: UserContext = Depends(get_user_context)
) -> VMCPToolCallResponse:
    """Call a tool in a vMCP with type-safe request/response models."""
    logger.info(f"📋 Call vMCP tool endpoint called for: {vmcp_id}, tool: {request.tool_name}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")
    
    try:
        # Get managers
        vmcp_config_manager = VMCPConfigManager(user_context.user_id, vmcp_id=vmcp_id)
        
        # Verify vMCP exists
        vmcp_config = vmcp_config_manager.load_vmcp_config(vmcp_id)
        if not vmcp_config:
            raise HTTPException(status_code=404, detail=f"vMCP '{vmcp_id}' not found")
        
        # Call the tool using VMCPConfigManager which handles both custom tools and server tools
        try:
            result = await vmcp_config_manager.call_tool(
                request,
                connect_if_needed=True,
                return_metadata=False
            )
        except ValueError as ve:
            # ValueError typically means tool not found
            logger.error(f"   ❌ Tool not found: {ve}")
            raise HTTPException(status_code=404, detail=str(ve))
        except Exception as tool_error:
            logger.error(f"   ❌ Tool call failed: {tool_error}")
            logger.error(f"   ❌ Exception type: {type(tool_error).__name__}")
            logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Failed to call tool '{request.tool_name}': {str(tool_error)}")
        
        if result is None:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to call tool '{request.tool_name}' - no result returned"
            )
        
        logger.info(f"   ✅ Successfully called tool '{request.tool_name}'")
        
        # Extract result data - handle both dict and CallToolResult (Pydantic model) formats
        if isinstance(result, dict):
            result_data = result
        else:
            # Convert Pydantic model (CallToolResult) to dict for proper serialization
            # Try model_dump() first (Pydantic v2), fallback to dict() (Pydantic v1)
            if hasattr(result, 'model_dump'):
                result_dict = result.model_dump()
            elif hasattr(result, 'dict'):
                result_dict = result.dict()
            else:
                # Fallback: try to convert to dict
                try:
                    result_dict = dict(result) if hasattr(result, '__dict__') else {"content": str(result)}
                except:
                    result_dict = {"content": str(result)}
            
            result_data = {"result": result_dict}
        
        return VMCPToolCallResponse(
            success=True,
            message=f"Tool '{request.tool_name}' executed successfully",
            data={
                "vmcp_id": vmcp_id,
                "tool": request.tool_name,
                **result_data
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error calling vMCP tool: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to call vMCP tool: {str(e)}")

@router.post("/{vmcp_id}/resources/read", response_model=VMCPResourceResponse)
async def read_vmcp_resource(
    vmcp_id: str,
    request: VMCPResourceRequest,
    user_context: UserContext = Depends(get_user_context)
) -> VMCPResourceResponse:
    """Read a resource from a vMCP with type-safe request/response models."""
    logger.info(f"📋 Read vMCP resource endpoint called for: {vmcp_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")
    
    try:
        # Get managers
        vmcp_config_manager = VMCPConfigManager(user_context.user_id)
        mcp_config_manager = MCPConfigManager(user_context.user_id)
        mcp_client_manager = MCPClientManager(mcp_config_manager)
        
        # Get vMCP config
        vmcp_config = vmcp_config_manager.load_vmcp_config(vmcp_id)
        if not vmcp_config:
            raise HTTPException(status_code=404, detail=f"vMCP '{vmcp_id}' not found")
        
        # Find which server has this resource
        resource_server = None
        for server_id in vmcp_config.servers:
            server_config = mcp_config_manager.get_server(server_id)
            if server_config and server_config.resources and request.uri in server_config.resources:
                resource_server = server_id
                break
        
        if not resource_server:
            raise HTTPException(status_code=404, detail=f"Resource '{request.uri}' not found in any connected server")
        
        # Read the resource
        try:
            contents = await mcp_client_manager.read_resource(resource_server, request.uri)
        except Exception as e:
            logger.error(f"   ❌ Exception in client_manager.read_resource: {e}")
            raise e
        
        if contents is None:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to read resource '{request.uri}' from server '{resource_server}'"
            )
        
        logger.info(f"   ✅ Successfully read resource '{request.uri}' from server '{resource_server}'")
        
        return VMCPResourceResponse(
            success=True,
            message=f"Resource '{request.uri}' read successfully",
            data={
                "vmcp_id": vmcp_id,
                "server": resource_server,
                "uri": request.uri,
                "contents": contents
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error reading vMCP resource: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to read vMCP resource: {str(e)}")

@router.post("/{vmcp_id}/prompts/get")
async def get_vmcp_prompt(
    vmcp_id: str,
    request: VMCPPromptRequest,
    user_context: UserContext = Depends(get_user_context)
):
    """Get a prompt from a vMCP with type-safe request/response models."""
    logger.info(f"📋 Get vMCP prompt endpoint called for: {vmcp_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")
    
    try:
        # Get managers
        vmcp_config_manager = VMCPConfigManager(user_context.user_id)
        mcp_config_manager = MCPConfigManager(user_context.user_id)
        mcp_client_manager = MCPClientManager(mcp_config_manager)
        
        # Get vMCP config
        vmcp_config = vmcp_config_manager.load_vmcp_config(vmcp_id)
        if not vmcp_config:
            raise HTTPException(status_code=404, detail=f"vMCP '{vmcp_id}' not found")
        
        # Handle prompt_id: can be custom prompt (starts with '#') or server prompt name
        prompt_id = request.prompt_id
        is_custom_prompt = prompt_id.startswith('#')
        
        prompt_name = prompt_id[1:] if is_custom_prompt else prompt_id
        
        # Find which server has this prompt or check custom prompts
        prompt_server = None
        if is_custom_prompt:
            # Check custom prompts in vMCP config
            custom_prompts = vmcp_config.custom_prompts or []
            custom_prompt = next((p for p in custom_prompts if p.get('name') == prompt_name or p.get('id') == prompt_name), None)
            if not custom_prompt:
                raise HTTPException(status_code=404, detail=f"Custom prompt '{prompt_id}' not found in vMCP '{vmcp_id}'")
            
            # For custom prompts, properly handle parameter substitution
            logger.info(f"   ✅ Found custom prompt '{prompt_id}' in vMCP '{vmcp_id}'")
            
            # Use the VMCPConfigManager to properly get the prompt with parameter substitution
            # This matches the implementation in router.py line 1659
            try:
                user_vmcp_manager = VMCPConfigManager(
                    user_context.user_id,
                    vmcp_id,
                    logging_config={"agent_name": "1xn-test", "client_id": user_context.client_id}
                )
                prompt_response = await user_vmcp_manager.get_prompt(
                    prompt_id,
                    request.arguments or {},
                    connect_if_needed=True
                )
                
                logger.info(f"   ✅ Successfully processed custom prompt '{prompt_id}' with parameter substitution")
                
                # Return the prompt_response directly, matching router.py implementation
                return prompt_response
            except Exception as e:
                logger.error(f"   ❌ Error processing custom prompt '{prompt_id}': {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to process custom prompt '{prompt_id}': {str(e)}"
                )
        else:
            # Look for server prompt
            for server_id in vmcp_config.servers:
                server_config = mcp_config_manager.get_server(server_id)
                if server_config and server_config.prompts and prompt_name in server_config.prompts:
                    prompt_server = server_id
                    break
            
            if not prompt_server:
                raise HTTPException(status_code=404, detail=f"Prompt '{prompt_name}' not found in any connected server")
            
            # Get the prompt from server
            try:
                messages = await mcp_client_manager.get_prompt(
                    prompt_server,
                    prompt_name,
                    request.arguments or {},
                    connect_if_needed=True
                )
            except Exception as e:
                logger.error(f"   ❌ Exception in client_manager.get_prompt: {e}")
                raise e
            
            if messages is None:
                logger.error(f"   ❌ get_prompt returned None for prompt '{prompt_name}' from server '{prompt_server}'")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to get prompt '{prompt_name}' from server '{prompt_server}'"
                )
            
            logger.info(f"   ✅ Successfully got prompt '{prompt_name}' from server '{prompt_server}'")
            
            return VMCPPromptResponse(
                success=True,
                message=f"Prompt '{prompt_name}' retrieved successfully",
                data={
                    "vmcp_id": vmcp_id,
                    "server": prompt_server,
                    "prompt": prompt_name,
                    "prompt_id": prompt_id,
                    "messages": messages
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error getting vMCP prompt: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        
        # If it's a validation error, return 422 with details
        if hasattr(e, 'status_code') and e.status_code == 422:
            logger.error(f"   ❌ Validation error details: {getattr(e, 'detail', 'No details')}")
            raise HTTPException(status_code=422, detail=f"Validation error: {str(e)}")
        
        raise HTTPException(status_code=500, detail=f"Failed to get vMCP prompt: {str(e)}")

# ============================================================================
# MISSING ENDPOINTS - ADDED FOR TYPE SAFETY
# ============================================================================

@router.post("/{vmcp_id}/environment-variables/save", response_model=VMCPEnvironmentVariablesResponse)
async def save_vmcp_environment_variables(
    vmcp_id: str, 
    request: VMCPEnvironmentVariablesRequest, 
    user_context: UserContext = Depends(get_user_context)
) -> VMCPEnvironmentVariablesResponse:
    """Save environment variables for a vMCP (primarily for remote vMCPs)"""
    logger.info(f"📋 Save vMCP environment variables endpoint called for vmcp_id: {vmcp_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")
    
    try:
        user_vmcp_manager = VMCPConfigManager(user_context.user_id, vmcp_id,
            logging_config={"agent_name": "1xn-test", "client_id": user_context.client_id})
        
        # Load current vMCP config
        vmcp_config = user_vmcp_manager.load_vmcp_config()
        if not vmcp_config:
            raise HTTPException(status_code=404, detail=f"vMCP '{vmcp_id}' not found")
        
        # Update environment variables
        success = user_vmcp_manager.update_vmcp_config(
            vmcp_id=vmcp_id,
            environment_variables=request.environment_variables
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save environment variables")
        
        # Reload updated config
        updated_vmcp = user_vmcp_manager.load_vmcp_config()
        
        logger.info(f"✅ Successfully saved environment variables for vMCP: {vmcp_id}")
        
        # Create proper data model
        env_vars = updated_vmcp.environment_variables or []
        response_data = VMCPEnvironmentVariablesData(
            vmcp_id=vmcp_id,
            variables_count=len(env_vars),
            variables=env_vars
        )
        
        return VMCPEnvironmentVariablesResponse(
            success=True,
            message="Environment variables saved successfully",
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error saving environment variables for vMCP '{vmcp_id}': {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to save environment variables: {str(e)}")

@router.post("/{vmcp_id}/add-server", response_model=VMCPAddServerResponse)
async def add_server_to_vmcp(
    vmcp_id: str,
    request: VMCPAddServerRequest,
    user_context: UserContext = Depends(get_user_context)
) -> VMCPAddServerResponse:
    """Add a server to a vMCP configuration"""
    logger.info(f"📋 Add server to vMCP endpoint called for vmcp_id: {vmcp_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")
    # logger.info(f"   📝 Request data: {request}")
    
    try:
        # Get managers
        config_manager = MCPConfigManager(user_context.user_id)
        client_manager = MCPClientManager(config_manager)
        user_vmcp_manager = VMCPConfigManager(user_context.user_id, vmcp_id)
        
        # Load vMCP config
        vmcp_config = user_vmcp_manager.load_vmcp_config()
        if not vmcp_config:
            raise HTTPException(status_code=404, detail=f"vMCP '{vmcp_id}' not found")
        
        server_data = request.server_data
        
        # Convert server_data to dict if it's a VMCPAddServerData instance
        if isinstance(server_data, VMCPAddServerData):
            server_data_dict = server_data.model_dump(exclude_unset=True, exclude_none=False)
        else:
            # It's already a dict (backward compatibility)
            server_data_dict = server_data
        
        # Handle wrapped mcp_server_config format (shouldn't happen after normalization, but keep for safety)
        if isinstance(server_data_dict, dict) and "mcp_server_config" in server_data_dict:
            server_data_dict = server_data_dict.get("mcp_server_config")
        
        server_id = server_data_dict.get('server_id')
        server_name = server_data_dict.get('name')
        
        if not server_id and not server_name:
            raise HTTPException(status_code=400, detail="Either server id or server name is required")
        
        # Check if server already exists in server list
        existing_server = config_manager.get_server_by_id(server_id) if server_id else None
        
        server_to_add = None
        
        if existing_server:
            # Server exists, use it
            logger.info(f"   ✅ Found existing server: {existing_server.name} ({existing_server.server_id})")
            server_to_add = existing_server
            server_name  = server_to_add.name
            server_id = server_to_add.server_id
        else:
            # Server doesn't exist, create it from server_data
            logger.info(f"   🔧 Creating new server from data: {server_name}")
            
            # Map transport type - use mode or transport field
            transport_value = server_data_dict.get('mode') or server_data_dict.get('transport', 'http')
            transport_type = MCPTransportType(transport_value)
            
            # Create server config
            server_config = MCPServerConfig(
                name=server_data_dict.get('name', ''),
                transport_type=transport_type,
                description=server_data_dict.get('description', ''),
                url=server_data_dict.get('url'),
                command=server_data_dict.get('command'),
                args=server_data_dict.get('args'),
                env=server_data_dict.get('env'),
                headers=server_data_dict.get('headers'),
                auto_connect=server_data_dict.get('auto_connect', True),
                enabled=server_data_dict.get('enabled', True),
                status=MCPConnectionStatus.DISCONNECTED,
                favicon_url=server_data_dict.get('favicon_url')
            )
            
            # Generate server ID
            server_id = server_config.ensure_server_id()
            server_name  = server_config.name
            server_id = server_config.server_id
            
            # Add server to backend
            success = config_manager.add_server(server_config)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to create server")
            
            # Assign the created server config to server_to_add
            server_to_add = server_config
            
            logger.info(f"   ✅ Created new server: {server_config.name} ({server_id})")
        
        # Try to connect and discover capabilities and upate server config
        try:
            logger.info(f"   🔗 Attempting to connect to server: {server_name}")
            mcp_server = config_manager.get_server(server_id)
            if mcp_server:
                # Ping the server to get current status
                try:
                    current_status = await client_manager.ping_server(mcp_server.server_id)
                    logger.info(f"   🔍 Server {mcp_server.server_id}: ping result = {current_status.value}")
                except AuthenticationError as e:
                    logger.debug(f"   ❌ Traceback: {traceback.format_exc()}")
                    logger.debug(f"   ❌ Authentication error for server {mcp_server.server_id}: {e}")
                    current_status = MCPConnectionStatus.AUTH_REQUIRED
                except Exception as e:
                    logger.error(f"   ❌ Traceback: {traceback.format_exc()}")
                    logger.error(f"   ❌ Error pinging server {mcp_server.server_id}: {e}")
                    current_status = MCPConnectionStatus.UNKNOWN

                mcp_server.status = current_status
                
                # Discover capabilities
                try:
                    capabilities = await client_manager.discover_capabilities(mcp_server.server_id)
                except Exception as e:
                    logger.error(f"   ❌ Traceback: {traceback.format_exc()}")
                    logger.error(f"   ❌ Error discovering capabilities for server {mcp_server.server_id}: {e}")
                    capabilities = None

                if capabilities:
                    logger.info(f"   🔍 Server {mcp_server.server_id}: capabilities discovered")
                    # Update server config with discovered capabilities (matching original router exactly)
                    if capabilities.get('tools',[]):
                        mcp_server.tools = capabilities.get('tools', [])
                    if capabilities.get('resources',[]):
                        mcp_server.resources = capabilities.get('resources', [])
                    if capabilities.get('prompts',[]):
                        mcp_server.prompts = capabilities.get('prompts', [])
                    if capabilities.get('tool_details',[]):
                        mcp_server.tool_details = capabilities.get('tool_details', [])
                    if capabilities.get('resource_details',[]):
                        mcp_server.resource_details = capabilities.get('resource_details', [])
                    if capabilities.get('resource_templates',[]):
                        mcp_server.resource_templates = capabilities.get('resource_templates', [])
                    if capabilities.get('resource_template_details',[]):
                        mcp_server.resource_template_details = capabilities.get('resource_template_details', [])
                    if capabilities.get('prompt_details',[]):
                        mcp_server.prompt_details = capabilities.get('prompt_details', [])
                    
                    mcp_server.capabilities = {
                        "tools": bool(mcp_server.tools and len(mcp_server.tools) > 0),
                        "resources": bool(mcp_server.resources and len(mcp_server.resources) > 0),
                        "prompts": bool(mcp_server.prompts and len(mcp_server.prompts) > 0)
                    }

                vmcps_using_server = mcp_server.vmcps_using_server
                if vmcps_using_server:
                    logger.info(f"   🔄 vMCPs using server {mcp_server.server_id}: {vmcps_using_server}")
                    # Add vmcp id to vmcps_using_server
                    vmcps_using_server.append(vmcp_id)
                    mcp_server.vmcps_using_server = list(set(vmcps_using_server))
                else:
                    mcp_server.vmcps_using_server = [vmcp_id]
                
                logger.info(f"   ✅ Successfully tried to discover capabilities for server '{mcp_server.server_id} Current status {mcp_server.status.value}'")
                
                # Save updated server config
                config_manager.update_server_config(mcp_server.server_id, mcp_server)
            else:
                logger.warning(f"   ⚠️ Server {mcp_server.server_id}: no capabilities discovered")
        except Exception as e:
            logger.error(f"   ❌ Traceback: {traceback.format_exc()}")
            logger.error(f"   ❌ Error connecting to server {server_id}: {e}")
            # Continue without failing - server might be offline

        # Add server to vMCP configuration (matching original router logic exactly)
        server_for_vmcp = server_to_add.to_dict_for_vmcp()
        
        # Update vMCP config
        updated_vmcp_config = vmcp_config.vmcp_config.copy() if vmcp_config.vmcp_config else {}
        
        # Add server to selected_servers
        selected_servers = updated_vmcp_config.get('selected_servers', [])
        if not any(s.get('server_id') == server_for_vmcp.get('server_id') for s in selected_servers):
            selected_servers.append(server_for_vmcp)
            updated_vmcp_config['selected_servers'] = selected_servers
        
        # Auto-select all tools, prompts, and resources
        selected_tools = updated_vmcp_config.get('selected_tools', {})
        selected_prompts = updated_vmcp_config.get('selected_prompts', {})
        selected_resources = updated_vmcp_config.get('selected_resources', {})
        
        # Get all tool names, prompt names, and resource URIs
        # Handle both dict and Pydantic model objects
        tool_details = server_for_vmcp.get('tool_details', [])
        all_tool_names = [
            tool.name if hasattr(tool, 'name') else tool.get('name') 
            for tool in tool_details
        ]
        
        prompt_details = server_for_vmcp.get('prompt_details', [])
        all_prompt_names = [
            prompt.name if hasattr(prompt, 'name') else prompt.get('name') 
            for prompt in prompt_details
        ]
        
        resource_details = server_for_vmcp.get('resource_details', [])
        all_resource_uris = []
        for resource in resource_details:
            if hasattr(resource, 'uri'):
                # Convert AnyUrl to string
                uri = resource.uri
                all_resource_uris.append(str(uri) if hasattr(uri, '__class__') and uri.__class__.__name__ == 'AnyUrl' else uri)
            else:
                all_resource_uris.append(resource.get('uri'))
        
        selected_tools[server_for_vmcp.get('server_id')] = all_tool_names
        selected_prompts[server_for_vmcp.get('server_id')] = all_prompt_names
        selected_resources[server_for_vmcp.get('server_id')] = all_resource_uris
        
        updated_vmcp_config['selected_tools'] = selected_tools
        updated_vmcp_config['selected_prompts'] = selected_prompts
        updated_vmcp_config['selected_resources'] = selected_resources
        
        # Save updated vMCP config
        save_success = user_vmcp_manager.update_vmcp_config(
            vmcp_id=vmcp_id,
            vmcp_config=updated_vmcp_config
        )
        
        if not save_success:
            raise HTTPException(status_code=500, detail="Failed to update vMCP configuration")
        
        # Reload updated vMCP config
        updated_vmcp = user_vmcp_manager.load_vmcp_config()
        
        logger.info(f"✅ Successfully added server {server_to_add.name} to vMCP {vmcp_id}")
        
        # Convert to VMCPInfo for type-safe response
        # Ensure all required fields are present and properly typed
        vmcp_info = VMCPInfo(
            id=updated_vmcp.id,
            name=updated_vmcp.name,
            description=updated_vmcp.description or None,
            status="active",  # Default status
            user_id=str(user_context.user_id),
            system_prompt=updated_vmcp.system_prompt,
            vmcp_config=updated_vmcp.vmcp_config or {},
            custom_prompts=updated_vmcp.custom_prompts or [],
            custom_tools=updated_vmcp.custom_tools or [],
            custom_context=updated_vmcp.custom_context or [],
            custom_resources=updated_vmcp.custom_resources or [],
            custom_resource_templates=getattr(updated_vmcp, 'custom_resource_templates', None) or [],
            custom_widgets=getattr(updated_vmcp, 'custom_widgets', None) or [],
            custom_resource_uris=getattr(updated_vmcp, 'custom_resource_uris', None) or [],
            environment_variables=updated_vmcp.environment_variables or [],
            uploaded_files=updated_vmcp.uploaded_files or [],
            total_tools=updated_vmcp.total_tools,
            total_resources=updated_vmcp.total_resources,
            total_resource_templates=updated_vmcp.total_resource_templates,
            total_prompts=updated_vmcp.total_prompts,
            creator_id=str(updated_vmcp.creator_id) if updated_vmcp.creator_id else None,
            creator_username=str(updated_vmcp.creator_username) if updated_vmcp.creator_username else None,
            is_public=getattr(updated_vmcp, 'is_public', False),
            public_tags=getattr(updated_vmcp, 'public_tags', None) or [],
            public_at=getattr(updated_vmcp, 'public_at', None),
            is_wellknown=getattr(updated_vmcp, 'is_wellknown', False),
            metadata=getattr(updated_vmcp, 'metadata', None) or {},
            created_at=updated_vmcp.created_at,
            updated_at=updated_vmcp.updated_at
        )
        
        return VMCPAddServerResponse(
            success=True,
            message=f"Server '{server_to_add.name}' added to vMCP successfully",
            vmcp_config=vmcp_info,
            server=server_for_vmcp
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error adding server to vMCP '{vmcp_id}': {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to add server to vMCP: {str(e)}")

@router.delete("/{vmcp_id}/remove-server", response_model=VMCPRemoveServerResponse)
async def remove_server_from_vmcp(
    vmcp_id: str,
    server_id: str,  # Accept server_id as query parameter for DELETE request
    user_context: UserContext = Depends(get_user_context)
) -> VMCPRemoveServerResponse:
    """Remove a server from a vMCP configuration"""
    logger.info(f"📋 Remove server from vMCP endpoint called for vmcp_id: {vmcp_id}")
    logger.info(f"   👤 User context: {user_context.user_id if user_context else 'None'}")
    
    try:
        user_vmcp_manager = VMCPConfigManager(user_context.user_id, vmcp_id)
        
        # Load vMCP config
        vmcp_config = user_vmcp_manager.load_vmcp_config()
        if not vmcp_config:
            raise HTTPException(status_code=404, detail=f"vMCP '{vmcp_id}' not found")
        
        # Validate server_id if provided
        if not server_id:
            raise HTTPException(status_code=400, detail="server_id query parameter is required")
        
        # Remove specific server from vMCP config
        # Get current selected servers
        current_config = vmcp_config.vmcp_config or {}
        selected_servers = current_config.get('selected_servers', [])
        
        # Filter out the server to remove
        updated_servers = [
            s for s in selected_servers 
            if isinstance(s, dict) and s.get('server_id') != server_id and s.get('id') != server_id
        ]
        
        # Update selected_servers in config
        updated_config = current_config.copy()
        updated_config['selected_servers'] = updated_servers
        
        # Also update selected_tools and selected_resources to remove references to this server
        selected_tools = updated_config.get('selected_tools', {})
        selected_resources = updated_config.get('selected_resources', {})
        selected_resource_templates = updated_config.get('selected_resource_templates', {})
        selected_prompts = updated_config.get('selected_prompts', {})
        
        # Remove server from all selections
        if server_id in selected_tools:
            del selected_tools[server_id]
        if server_id in selected_resources:
            del selected_resources[server_id]
        if server_id in selected_resource_templates:
            del selected_resource_templates[server_id]
        if server_id in selected_prompts:
            del selected_prompts[server_id]
        
        updated_config['selected_tools'] = selected_tools
        updated_config['selected_resources'] = selected_resources
        updated_config['selected_resource_templates'] = selected_resource_templates
        updated_config['selected_prompts'] = selected_prompts
        
        # Update vMCP config
        save_success = user_vmcp_manager.update_vmcp_config(
            vmcp_id=vmcp_id,
            vmcp_config=updated_config
        )
        
        if not save_success:
            raise HTTPException(status_code=500, detail="Failed to update vMCP configuration")
        
        # Reload updated vMCP config
        updated_vmcp = user_vmcp_manager.load_vmcp_config()
        
        logger.info(f"✅ Successfully removed server {server_id} from vMCP {vmcp_id}")
        
        # Convert to VMCPInfo for type-safe response
        vmcp_info = VMCPInfo(
            id=updated_vmcp.id,
            name=updated_vmcp.name,
            description=updated_vmcp.description or None,
            status="active",  # Default status
            user_id=str(user_context.user_id),
            system_prompt=updated_vmcp.system_prompt,
            vmcp_config=updated_vmcp.vmcp_config or {},
            custom_prompts=updated_vmcp.custom_prompts or [],
            custom_tools=updated_vmcp.custom_tools or [],
            custom_context=updated_vmcp.custom_context or [],
            custom_resources=updated_vmcp.custom_resources or [],
            custom_resource_templates=getattr(updated_vmcp, 'custom_resource_templates', None) or [],
            custom_widgets=getattr(updated_vmcp, 'custom_widgets', None) or [],
            custom_resource_uris=getattr(updated_vmcp, 'custom_resource_uris', None) or [],
            environment_variables=updated_vmcp.environment_variables or [],
            uploaded_files=updated_vmcp.uploaded_files or [],
            total_tools=updated_vmcp.total_tools,
            total_resources=updated_vmcp.total_resources,
            total_resource_templates=updated_vmcp.total_resource_templates,
            total_prompts=updated_vmcp.total_prompts,
            creator_id=str(updated_vmcp.creator_id) if updated_vmcp.creator_id else None,
            creator_username=str(updated_vmcp.creator_username) if updated_vmcp.creator_username else None,
            is_public=getattr(updated_vmcp, 'is_public', False),
            public_tags=getattr(updated_vmcp, 'public_tags', None) or [],
            public_at=getattr(updated_vmcp, 'public_at', None),
            is_wellknown=getattr(updated_vmcp, 'is_wellknown', False),
            metadata=getattr(updated_vmcp, 'metadata', None) or {},
            created_at=updated_vmcp.created_at,
            updated_at=updated_vmcp.updated_at
        )
        
        return VMCPRemoveServerResponse(
            success=True,
            message=f"Server {server_id} removed from vMCP successfully",
            vmcp_config=vmcp_info,
            server=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ❌ Error removing server from vMCP '{vmcp_id}': {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to remove server from vMCP: {str(e)}")

