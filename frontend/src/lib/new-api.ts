import { Prompt, Tool, Resource, EnvironmentVariable, VMCPConfig } from '../types/vmcp';
// New comprehensive API client for 1xN backend
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000/api';

// Types
export interface User {
  id: string;
  email: string;
  username?: string;
  first_name: string;
  last_name: string;
  full_name: string;
  is_active: boolean;
  is_verified: boolean;
  last_login: string | null;
  created_at: string;
  photo_url?: string; // Optional profile picture URL from OAuth providers
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  full_name?: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface MCPInstallRequest {
  name: string;
  mode: string;
  description?: string;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  url?: string;
  headers?: Record<string, string>;
  auth_type?: string;
  client_id?: string;
  client_secret?: string;
  auth_url?: string;
  token_url?: string;
  scope?: string;
  access_token?: string;
  auto_connect?: boolean;
  enabled?: boolean;
}

export interface MCPServer {
  server_id: string;
  name: string;
  description?: string;
  status: 'connected' | 'disconnected' | 'error' | 'auth_required';
  transport_type: string;
  url?: string;
  command?: string;
  headers?: Record<string, string>;
  last_connected?: string;
  last_error?: string;
  capabilities?: {
    tools_count: number;
    resources_count: number;
    prompts_count: number;
  };
  tools_list?: string[];
  resources_list?: string[];
  prompts_list?: string[];
  resource_templates_list?: string[];
  tool_details?: any[];
  resource_details?: any[];
  resource_template_details?: any[];
  prompt_details?: any[];
  auto_connect?: boolean;
  enabled?: boolean;
  auth_information?: string;
  created_at: string;
  updated_at: string;
  // Additional properties that may be present in server responses
  env_vars?: any;
  last_capabilities_update?: string | null;
  last_status_update?: string | null;
}

export interface MCPRegistryServer {
  id: string;
  name: string;
  description?: string;
  transport: string;
  url?: string;
  favicon_url?: string;
  category: string;
  icon: string;
  requiresAuth: boolean;
  env_vars?: string;
  note?: string;
  mcp_registry_config?: any;
  mcp_server_config?: any;
  stats?: any;
  created_at?: string;
  updated_at?: string;
}

export interface VMCPCreateRequest {
  name: string;
  description?: string;
  system_prompt?: any;
  vmcp_config?: any;
  custom_prompts?: Prompt[];
  custom_tools?: Tool[];
  custom_context?: string[];
  custom_resources?: Resource[];
  custom_resource_uris?: string[];
  environment_variables?: EnvironmentVariable[];
  uploaded_files?: Resource[];
}

export interface VMCPInfo {
  id: string;
  name: string;
  description?: string;
  created_at?: string;
  updated_at?: string;
  config?: any;
  // Sharing fields
  is_public?: boolean;
  public_tags?: string[];
  public_at?: string;
}

export interface VMCPCreateResponse {
  success: boolean;
  vMCP: VMCPConfig;
}

export interface AgentCreateRequest {
  name?: string;
  description?: string;
  active_vmcp?: string;
  list_of_vmcps?: string[];
  model?: string;
  host?: string;
}

export interface AgentConfig {
  id: string;
  user_id: string;
  client_id?: string;
  client_name?: string;
  name?: string;
  description?: string;
  active_vmcp?: string;
  list_of_vmcps?: string[];
  model?: string;
  host?: string;
  created_at: string;
  updated_at: string;
  created_by?: string;
}

export interface MCPToolCallRequest {
  server_id: string;
  tool_name: string;
  arguments: Record<string, any>;
}

export interface MCPResourceRequest {
  server_id: string;
  uri: string;
}

export interface MCPPromptRequest {
  server_id: string;
  prompt_name: string;
  arguments?: Record<string, any>;
}

export interface VMCPToolCallRequest {
  tool_name: string;
  arguments: Record<string, any>;
}

export interface VMCPResourceRequest {
  uri: string;
}

export interface VMCPPromptRequest {
  prompt_id: string;
  arguments?: Record<string, any>;
}

export interface AgentToolCallRequest {
  tool_id: string;
  arguments?: Record<string, any>;
}

export interface AgentResourceRequest {
  resource_id: string;
}

export interface AgentPromptRequest {
  prompt_id: string;
  arguments?: Record<string, any>;
}

export interface RenameServerRequest {
  new_name: string;
}

// Request deduplication cache
const pendingRequests = new Map<string, Promise<any>>();

export type VMCPShareState = 'private' | 'public' | 'shared';

export interface ChatStreamEvent {
  event: string;
  data: any;
  timestamp: string;
  message_id?: string;
}

export interface CostAnalytics {
  total_cost: number;
  total_conversations: number;
  average_cost_per_conversation: number;
  cost_by_day: Record<string, number>;
}

export interface AvailableModels {
  anthropic: string[];
  openai: string[];
  google: string[];
}

class NewApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private getRequestKey(endpoint: string, options: RequestInit = {}): string {
    const method = options.method || 'GET';
    const body = options.body ? JSON.stringify(options.body) : '';
    const headers = options.headers ? JSON.stringify(options.headers) : '';
    return `${method}:${endpoint}:${body}:${headers}`;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    const config: RequestInit = {
      headers,
      ...options,
    };

    // Check if there's already a pending request for this exact call
    const requestKey = this.getRequestKey(endpoint, config);
    if (pendingRequests.has(requestKey)) {
      return pendingRequests.get(requestKey)!;
    }

    // Create new request promise
    const requestPromise = (async () => {
      try {
        const response = await fetch(url, config);
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || errorData.message || `HTTP error! status: ${response.status}`);
        }

        return await response.json();
      } catch (error) {
        if (error instanceof Error) {
          throw error;
        }
        throw new Error('Network error occurred');
      } finally {
        // Clean up the pending request after completion
        pendingRequests.delete(requestKey);
      }
    })();

    // Store the pending request
    pendingRequests.set(requestKey, requestPromise);
    return requestPromise;
  }

  private getAuthHeaders(token?: string): Record<string, string> {
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  private getJsonHeaders(token?: string): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  // Auth endpoints
  async login(request: LoginRequest): Promise<{ success: boolean; data?: LoginResponse; error?: string }> {
    try {
      const data = await this.request<LoginResponse>('/login', {
        method: 'POST',
        headers: this.getJsonHeaders(),
        body: JSON.stringify(request),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Login failed' 
      };
    }
  }

  async register(request: RegisterRequest): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request('/register', {
        method: 'POST',
        headers: this.getJsonHeaders(),
        body: JSON.stringify(request),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Registration failed' 
      };
    }
  }

    async getUserInfo(token: string): Promise<{ success: boolean; data?: User; error?: string }> {
    try {
      const data = await this.request<User>('/userinfo', {
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get user info'
      };
    }
  }

  async verifyToken(): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request('/auth/verify', {
        method: 'POST',
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Token verification failed' 
      };
    }
  }

  // MCP endpoints
  async getMCPHealth(): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request('/mcps/health');
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to get MCP health' 
      };
    }
  }

  async installMCPServer(request: MCPInstallRequest, token: string): Promise<{ success: boolean; server?: any; error?: string; message?: string }> {
    try {
      const response = await this.request<{ server: any; message: string }>('/mcps/install', {
        method: 'POST',
        headers: this.getJsonHeaders(token),
        body: JSON.stringify(request),
      });
      return { 
        success: true, 
        server: response.server,
        message: response.message
      };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to install MCP server' 
      };
    }
  }

  async listMCPServers(token: string): Promise<{ 
    success: boolean; 
    data?: MCPServer[]; 
    error?: string;
    total?: number;
    connected?: number;
    disconnected?: number;
    auth_required?: number;
    errors?: number;
  }> {
    try {
      const response = await this.request<{
        servers: MCPServer[];
        total: number;
        connected: number;
        disconnected: number;
        auth_required: number;
        errors: number;
      }>('/mcps/list', {
        headers: this.getAuthHeaders(token),
      });
      
      return { 
        success: true, 
        data: response.servers,
        total: response.total,
        connected: response.connected,
        disconnected: response.disconnected,
        auth_required: response.auth_required,
        errors: response.errors
      };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to list MCP servers' 
      };
    }
  }

  async getMCPServerById(serverId: string, token: string): Promise<{ success: boolean; data?: MCPServer; error?: string }> {
    try {
      const data = await this.request<MCPServer>(`/mcps/by-id/${serverId}`, {
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to get MCP server' 
      };
    }
  }

  async getServerByName(serverName: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/mcps/by-name/${serverName}`, {
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to get server by name' 
      };
    }
  }

  async updateServer(serverName: string, updateData: any, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/mcps/${serverName}/update`, {
        method: 'PUT',
        headers: this.getJsonHeaders(token),
        body: JSON.stringify(updateData),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to update server' 
      };
    }
  }

  async renameMCPServer(serverName: string, newName: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/mcps/${serverName}/rename`, {
        method: 'PUT',
        headers: this.getJsonHeaders(token),
        body: JSON.stringify({ new_name: newName }),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to rename MCP server' 
      };
    }
  }

  async uninstallMCPServer(serverId: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/mcps/${serverId}/uninstall`, {
        method: 'DELETE',
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to uninstall MCP server' 
      };
    }
  }

  async clearMCPServerAuth(serverId: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/mcps/${serverId}/clear-auth`, {
        method: 'POST',
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to clear MCP server auth' 
      };
    }
  }

  async connectMCPServer(serverId: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/mcps/${serverId}/connect`, {
        method: 'POST',
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to connect to MCP server' 
      };
    }
  }

  async disconnectMCPServer(serverId: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/mcps/${serverId}/disconnect`, {
        method: 'POST',
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to disconnect from MCP server' 
      };
    }
  }

  async clearCacheMCPServer(serverId: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/mcps/${serverId}/clear-cache`, {
        method: 'POST',
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to clear cache for MCP server' 
      };
    }
  }

  async pingMCPServer(serverId: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/mcps/${serverId}/ping`, {
        method: 'POST',
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to ping MCP server' 
      };
    }
  }

  async initiateMCPServerAuth(serverId: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/mcps/${serverId}/auth`, {
        method: 'POST',
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to initiate MCP server auth' 
      };
    }
  }

  async callMCPTool(request: MCPToolCallRequest, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      // Ensure arguments is always an object, even if empty
      const arguments_ = request.arguments || {};
      
      const data = await this.request(`/mcps/${request.server_id}/tools/call`, {
        method: 'POST',
        headers: this.getJsonHeaders(token),
        body: JSON.stringify({
          server_id: request.server_id,
          tool_name: request.tool_name,
          arguments: arguments_
        }),
      });
      return { success: true, data };
    } catch (error) {
      // Provide more detailed error information
      const errorMessage = error instanceof Error ? error.message : 'Failed to call MCP tool';
      return { 
        success: false, 
        error: `Tool '${request.tool_name}' failed: ${errorMessage}` 
      };
    }
  }

  async getMCPResource(request: MCPResourceRequest, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/mcps/${request.server_id}/resources/read`, {
        method: 'POST',
        headers: this.getJsonHeaders(token),
        body: JSON.stringify({
          server_id: request.server_id,
          uri: request.uri
        }),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to get MCP resource' 
      };
    }
  }

  async getMCPPrompt(request: MCPPromptRequest, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/mcps/${request.server_id}/prompts/get`, {
        method: 'POST',
        headers: this.getJsonHeaders(token),
        body: JSON.stringify({
          server_id: request.server_id,
          prompt_name: request.prompt_name,
          arguments: request.arguments
        }),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to get MCP prompt' 
      };
    }
  }

  async discoverMCPTools(token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request('/mcps/discover', {
        method: 'POST',
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to discover MCP tools' 
      };
    }
  }

  async listMCPServerTools(serverName: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/mcps/${serverName}/tools/list`, {
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to list MCP server tools' 
      };
    }
  }

  async listMCPServerResources(serverName: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/mcps/${serverName}/resources/list`, {
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to list MCP server resources' 
      };
    }
  }

  async listMCPServerPrompts(serverName: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/mcps/${serverName}/prompts/list`, {
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to list MCP server prompts' 
      };
    }
  }

  async getMCPStats(token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request('/mcps/stats', {
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to get MCP stats' 
      };
    }
  }

  async discoverMCPServerCapabilities(serverName: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/mcps/${serverName}/discover-capabilities`, {
        method: 'POST',
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to discover MCP server capabilities' 
      };
    }
  }

  // vMCP endpoints
    async getVMCPHealth(): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request('/vmcps/health');
      return { success: true, data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get vMCP health'
      };
    }
  }

    async createVMCP(request: VMCPCreateRequest, token: string): Promise<{ success: boolean; data?: VMCPCreateResponse; error?: string }> {
    try {
      const data = await this.request<VMCPCreateResponse>('/vmcps/create', {
        method: 'POST',
        headers: this.getJsonHeaders(token),
        body: JSON.stringify(request),
      });
      return { success: true, data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to create vMCP'
      };
    }
  }

  async installVMCP(vmcpId: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    console.log('🚀 installVMCP called with vmcpId:', vmcpId);
    try {
      const data = await this.request('/vmcps/install', {
        method: 'POST',
        headers: this.getJsonHeaders(token),
        body: JSON.stringify({ public_vmcp_id: vmcpId }),
      });
      console.log('🚀 installVMCP success:', data);
      return { success: true, data };
    } catch (error) {
      console.log('🚀 installVMCP error:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to install vMCP'
      };
    }
  }

  async shareVMCP(vmcpId: string, request: { state: VMCPShareState; tags: string[] }, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/vmcps/share`, {
        method: 'POST',
        headers: this.getJsonHeaders(token),
        body: JSON.stringify({vmcp_id: vmcpId, state: request.state, tags: request.tags}),
      });
      return { success: true, data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to share vMCP'
      };
    }
  }

  async listPublicVMCPS(token: string): Promise<{ success: boolean; data?: any[]; error?: string }> {
    try {
      const data = await this.request<any[]>('/vmcps/public/list', {
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to list public vMCPs'
      };
    }
  }

  async getPublicVMCPDetails(vmcpId: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/vmcps/public/${vmcpId}`, {
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get public vMCP details'
      };
    }
  }

  async listVMCPS(token: string): Promise<{ success: boolean; data?: VMCPConfig[]; error?: string }> {
    try {
      const data = await this.request<VMCPConfig[]>('/vmcps/list', {
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to list vMCPs' 
      };
    }
  }

  async getVMCPDetails(vmcpId: string, token: string): Promise<{ success: boolean; data?: VMCPConfig; error?: string }> {
    try {
      const data = await this.request<VMCPConfig>(`/vmcps/${vmcpId}`, {
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to get vMCP details' 
      };
    }
  }

  async updateVMCP(vmcpId: string, request: VMCPCreateRequest, token: string): Promise<{ success: boolean; data?: VMCPCreateResponse; error?: string }> {
    try {
      const data = await this.request<VMCPCreateResponse>(`/vmcps/${vmcpId}`, {
        method: 'PUT',
        headers: this.getJsonHeaders(token),
        body: JSON.stringify(request),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to update vMCP' 
      };
    }
  }

  async addServerToVMCP(vmcpId: string, serverData: any, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/vmcps/${vmcpId}/add-server`, {
        method: 'POST',
        headers: this.getJsonHeaders(token),
        body: JSON.stringify({ server_data: serverData }),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to add server to vMCP' 
      };
    }
  }

  async removeServerFromVMCP(vmcpId: string, serverId: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/vmcps/${vmcpId}/remove-server?server_id=${encodeURIComponent(serverId)}`, {
        method: 'DELETE',
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to remove server from vMCP' 
      };
    }
  }

  async deleteVMCP(vmcpId: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/vmcps/${vmcpId}`, {
        method: 'DELETE',
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to delete vMCP' 
      };
    }
  }

  async forkVMCP(vmcpId: string, token: string): Promise<{ success: boolean; data?: VMCPCreateResponse; error?: string }> {
    try {
      const data = await this.request<VMCPCreateResponse>(`/vmcps/${vmcpId}/fork`, {
        method: 'POST',
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to fork vMCP' 
      };
    }
  }

  async refreshVMCP(vmcpId: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/vmcps/${vmcpId}/refresh`, {
        method: 'POST',
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to refresh vMCP' 
      };
    }
  }

  async listVMCPTools(vmcpId: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const response = await this.request(`/vmcps/${vmcpId}/tools/list`, {
        method: 'POST',
        headers: this.getAuthHeaders(token),
        body: JSON.stringify({}),
      });
      // Extract tools array from nested response structure
      const responseData = response as any;
      const tools = responseData?.data?.tools || responseData?.tools || (Array.isArray(responseData?.data) ? responseData.data : []);
      return { success: true, data: tools };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to list vMCP tools' 
      };
    }
  }

  async listVMCPResources(vmcpId: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const response = await this.request<any>(`/vmcps/${vmcpId}/resources/list`, {
        method: 'POST',
        headers: this.getAuthHeaders(token),
        body: JSON.stringify({}),
      });
      // Extract resources array from nested response structure
      const responseData = response as any;
      const resources = responseData?.data?.resources || responseData?.resources || (Array.isArray(responseData?.data) ? responseData.data : []);
      return { success: true, data: resources };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to list vMCP resources' 
      };
    }
  }

  async listVMCPPrompts(vmcpId: string, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const response = await this.request(`/vmcps/${vmcpId}/prompts/list`, {
        method: 'POST',
        headers: this.getAuthHeaders(token),
        body: JSON.stringify({}),
      });
      // Extract prompts array from nested response structure
      const responseData = response as any;
      const prompts = responseData?.data?.prompts || responseData?.prompts || (Array.isArray(responseData?.data) ? responseData.data : []);
      return { success: true, data: prompts };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to list vMCP prompts' 
      };
    }
  }

  async callVMCPTool(vmcpId: string, request: VMCPToolCallRequest, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/vmcps/${vmcpId}/tools/call`, {
        method: 'POST',
        headers: this.getJsonHeaders(token),
        body: JSON.stringify(request),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to call vMCP tool' 
      };
    }
  }

  async getVMCPResource(vmcpId: string, request: VMCPResourceRequest, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/vmcps/${vmcpId}/resources/read`, {
        method: 'POST',
        headers: this.getJsonHeaders(token),
        body: JSON.stringify(request),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to get vMCP resource' 
      };
    }
  }

  async getVMCPPrompt(vmcpId: string, request: VMCPPromptRequest, token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/vmcps/${vmcpId}/prompts/get`, {
        method: 'POST',
        headers: this.getJsonHeaders(token),
        body: JSON.stringify(request),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to get vMCP prompt' 
      };
    }
  }

  async getVMCPSystemPrompt(vmcpId: string, args: Record<string, any>, token: string): Promise<{ success: boolean; data?: { system_prompt: string; description?: string }; error?: string }> {
    try {
      const response = await this.request<{ success: boolean; system_prompt: string; description?: string }>(
        `/vmcps/${vmcpId}/system-prompt/get`,
        {
          method: 'POST',
          headers: this.getJsonHeaders(token),
          body: JSON.stringify({ arguments: args })
        }
      );
      return { success: response.success, data: { system_prompt: response.system_prompt, description: response.description }, error: response.success ? undefined : 'Failed to get system prompt' };
    } catch (error) {
      return { success: false, error: error instanceof Error ? error.message : 'Failed to get VMCP system prompt' };
    }
  }

  async getVMCPSystemPromptVariables(vmcpId: string, token: string): Promise<{ success: boolean; data?: { variables: any[]; environment_variables: any[] }; error?: string }> {
    try {
      const response = await this.request<{ success: boolean; variables: any[]; environment_variables: any[] }>(
        `/vmcps/${vmcpId}/system-prompt/variables`,
        {
          method: 'GET',
          headers: this.getAuthHeaders(token)
        }
      );
      return { success: response.success, data: { variables: response.variables, environment_variables: response.environment_variables }, error: response.success ? undefined : 'Failed to get system prompt variables' };
    } catch (error) {
      return { success: false, error: error instanceof Error ? error.message : 'Failed to get VMCP system prompt variables' };
    }
  }

  async saveVMCPEnvironmentVariables(vmcpId: string, environmentVariables: any[], token: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/vmcps/${vmcpId}/environment-variables/save`, {
        method: 'POST',
        headers: this.getJsonHeaders(token),
        body: JSON.stringify({
          environment_variables: environmentVariables
        }),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to save environment variables' 
      };
    }
  }
  // OAuth Methods
  async getOAuthUrl(provider: 'google' | 'github', webClientUrl?: string, authMode: 'signin' | 'signup' = 'signin', username?: string, oauthParams?: URLSearchParams): Promise<{ success: boolean; data?: { auth_url: string; state: string }; error?: string }> {
    try {
      const params = new URLSearchParams();
      if (oauthParams) {
        oauthParams.forEach((value, key) => {
          params.append(key, value);
        });
      }
      
      if (webClientUrl) {
        params.append('web_client_url', webClientUrl);
      }
      params.append('auth_mode', authMode);
      if (username) {
        params.append('username', username);
      }

      const endpoint = `/oauth/${provider}/authorize${params.toString() ? `?${params.toString()}` : ''}`;
      const data = await this.request<{ auth_url: string; state: string }>(endpoint);
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to get OAuth URL' 
      };
    }
  }

  async refreshToken(refreshToken: string): Promise<{ success: boolean; data?: { access_token: string; expires_in: number }; error?: string }> {
    try {
      const data = await this.request<{ access_token: string; expires_in: number }>('/auth/refresh', {
        method: 'POST',
        headers: this.getJsonHeaders(),
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Token refresh failed' 
      };
    }
  }

  async logout(accessToken: string, logoutAll: boolean = false): Promise<{ success: boolean; error?: string }> {
    try {
      await this.request('/auth/logout', {
        method: 'POST',
        headers: this.getJsonHeaders(accessToken),
        body: JSON.stringify({ logout_all: logoutAll }),
      });

      return { success: true };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Logout failed' 
      };
    }
  }

  // Blob Storage Methods
  async uploadBlob(
    file: File, 
    token: string,
    vmcpId?: string
  ): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (vmcpId) {
        formData.append('vmcp_id', vmcpId);
      }

      const response = await this.request<any>('/blob/upload', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData
      });
      return { success: true, data: response };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Upload failed' 
      };
    }
  }

  async deleteBlob(
    blobId: string, 
    token: string,
    vmcpId?: string
  ): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      // Build URL with query parameters
      let url = `/blob/${blobId}`;
      if (vmcpId) {
        url += `?vmcp_id=${encodeURIComponent(vmcpId)}`;
      }

      const response = await this.request<{ message: string }>(url, {
        method: 'DELETE',
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data: response };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Delete failed' 
      };
    }
  }

  async renameBlob(
    blobId: string,
    newFilename: string,
    token: string,
    vmcpId?: string
  ): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const response = await this.request<any>(`/blob/${blobId}/rename`, {
        method: 'PATCH',
        headers: this.getJsonHeaders(token),
        body: JSON.stringify({ new_filename: newFilename, vmcp_id: vmcpId })
      });
      return { success: true, data: response };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Rename failed' 
      };
    }
  }

  async getBlob(
    blobId: string, 
    token: string,
    vmcpId?: string
  ): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const params = vmcpId ? `?vmcp_id=${vmcpId}` : '';
      const response = await this.request<any>(`/blob/content/${blobId}${params}`, {
        method: 'GET',
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data: response };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Get blob failed' 
      };
    }
  }

  async downloadBlob(
    blobId: string, 
    token: string,
    vmcpId?: string
  ): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const params = vmcpId ? `?vmcp_id=${vmcpId}` : '';
      const response = await fetch(`${this.baseUrl}/blob/blobs/${blobId}${params}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.message || `HTTP error! status: ${response.status}`);
      }
      
      // For binary data, return the blob
      const blob = await response.blob();
      return { success: true, data: blob };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Download blob failed' 
      };
    }
  }

  async listBlobs(
    token: string,
    vmcpId?: string
  ): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const params = vmcpId ? `?vmcp_id=${vmcpId}` : '';
      const response = await this.request<any>(`/blob/${params}`, {
        method: 'GET',
        headers: this.getAuthHeaders(token)
      });
      return { success: true, data: response };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'List blobs failed' 
      };
    }
  }

  // MCP Server Status Methods
  async getServerStatus(
    serverName: string, 
    token: string
  ): Promise<{ success: boolean; data?: { server_name: string; status: string; last_updated: string }; error?: string }> {
    try {
      const response = await this.request<{ server_name: string; status: string; last_updated: string }>(`/mcps/${serverName}/status`, {
        method: 'GET',
        headers: this.getAuthHeaders(token)
      });
      return { success: true, data: response };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to get server status' 
      };
    }
  }

  async getServerStatusById(
    serverId: string, 
    token: string
  ): Promise<{ success: boolean; data?: { server_name: string; server_id: string; status: string; last_updated: string }; error?: string }> {
    try {
      const response = await this.request<{ server_name: string; server_id: string; status: string; last_updated: string }>(`/mcps/by-id/${serverId}/status`, {
        method: 'GET',
        headers: this.getAuthHeaders(token)
      });
      return { success: true, data: response };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to get server status by ID' 
      };
    }
  }

  // Stats Methods
  async getStats(
    filters: {
      agent_name?: string;
      vmcp_name?: string;
      method?: string;
      search?: string;
      page?: number;
      limit?: number;
    },
    token: string
  ): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const response = await this.request<any>(`/vmcps/stats`, {
        method: 'POST',
        headers: this.getJsonHeaders(token),
        body: JSON.stringify(filters)
      });
      return { success: true, data: response };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to get stats' 
      };
    }
  }

  async getStatsSummary(
    token: string
  ): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const response = await this.request<any>(`/vmcps/stats/summary`, {
        method: 'GET',
        headers: this.getAuthHeaders(token)
      });
      return { success: true, data: response };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to get stats summary' 
      };
    }
  }

  // ******** OAuth Configuration Methods *******
  async getVMCPConfiguration(vmcpId: string, params: any): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/unified-backend/oauth/${vmcpId}/config`, {
        method: 'GET',
        headers: this.getJsonHeaders(),
        body: JSON.stringify(params),
      });
      return { success: true, data };
    } catch (error) {
      return { success: false, error: error instanceof Error ? error.message : 'Failed to get VMCP configuration' };
    }
  }

  async saveVMCPConfiguration(vmcpId: string, params: any): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/oauth/${vmcpId}/config/save`, {
        method: 'POST',
        headers: this.getJsonHeaders(),
        body: JSON.stringify(params),
      });
      return { success: true, data };
    } catch (error) {
      return { success: false, error: error instanceof Error ? error.message : 'Failed to save VMCP configuration' };
    }
  }
  // ******** OAuth Configuration Methods *******

  // ******** Global MCP Server Registry Methods *******
  async getGlobalMCPServers(
    filters?: {
      category?: string;
      search?: string;
      limit?: number;
      offset?: number;
    },
    token?: string
  ): Promise<{ success: boolean; data?: { servers: any[]; total: number; limit: number; offset: number }; error?: string }> {
    try {
      const params = new URLSearchParams();
      if (filters?.category) params.append('category', filters.category);
      if (filters?.search) params.append('search', filters.search);
      if (filters?.limit) params.append('limit', filters.limit.toString());
      if (filters?.offset) params.append('offset', filters.offset.toString());

      const endpoint = `/mcps/registry/servers${params.toString() ? `?${params.toString()}` : ''}`;
      const data = await this.request<{ servers: any[]; total: number; limit: number; offset: number }>(endpoint, {
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to get global MCP servers' 
      };
    }
  }

  async getGlobalMCPServer(serverId: string, token?: string): Promise<{ success: boolean; data?: { server: any }; error?: string }> {
    try {
      const data = await this.request<{ server: any }>(`/mcps/registry/servers/${serverId}`, {
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to get global MCP server' 
      };
    }
  }

  async getGlobalMCPCategories(token?: string): Promise<{ success: boolean; data?: { categories: any[] }; error?: string }> {
    try {
      const data = await this.request<{ categories: any[] }>('/mcps/registry/categories', {
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to get MCP categories' 
      };
    }
  }

  async installGlobalMCPServer(serverId: string, token?: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/mcps/registry/servers/${serverId}/install`, {
        method: 'POST',
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to install global MCP server' 
      };
    }
  }
  // ******** Global MCP Server Registry Methods *******

  async getToolLogsStats(token: string, timeRange: string = 'all-time'): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const data = await this.request(`/agents/tool_logs/stats?time_range=${timeRange}`, {
        headers: this.getAuthHeaders(token),
      });
      return { success: true, data };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to get tool logs stats' 
      };
    }
  }

}

export const newApi = new NewApiClient(BACKEND_URL); 