/**
 * API Client v2 - Generated from OpenAPI spec with custom wrapper
 *
 * This file wraps the auto-generated API client from @hey-api/openapi-ts
 * and provides backward compatibility with the existing API interface.
 */

import { client } from './generated/client.gen';
import * as sdk from './generated/sdk.gen';
import type {
  McpInstallRequest,
  McpToolCallRequest,
  McpResourceRequest,
  McpPromptRequest,
  McpUpdateRequest,
  VmcpCreateRequest,
  VmcpUdateRequest,
  VmcpToolCallRequest,
  VmcpResourceRequest,
  VmcpConfig,
} from './generated/types.gen';

// Type aliases for backward compatibility (old ALL_CAPS style)
export type MCPInstallRequest = McpInstallRequest;
export type MCPToolCallRequest = McpToolCallRequest;
export type MCPResourceRequest = McpResourceRequest;
export type MCPPromptRequest = McpPromptRequest;
export type MCPUpdateRequest = McpUpdateRequest;
export type CreateVMCPRequest = VmcpCreateRequest;
export type UpdateVMCPRequest = VmcpUdateRequest;
export type VMCPToolCallRequest = VmcpToolCallRequest;
export type VMCPResourceRequest = VmcpResourceRequest;

// Re-export types for backward compatibility
export type {
  McpInstallRequest,
  McpToolCallRequest,
  McpResourceRequest,
  McpPromptRequest,
  McpUpdateRequest,
  VmcpCreateRequest,
  VmcpUdateRequest as UpdateVmcpRequest,
  VmcpToolCallRequest,
  VmcpResourceRequest,
};

// Additional types not in generated API
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
  photo_url?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

// Standard API response wrapper
interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

/**
 * API Client wrapper class
 * Provides a consistent interface around the generated API client
 */
class ApiClient {
  constructor(baseUrl: string) {
    client.setConfig({
      baseUrl: baseUrl,
    });
  }

  /**
   * Set authentication token for API requests
   */
  setToken(token: string | undefined) {
    client.setConfig({
      headers: {
        Authorization: token ? `Bearer ${token}` : undefined,
      },
    });
  }

  /**
   * Get current authentication token
   */
  getToken(): string | undefined {
    const headers = client.getConfig().headers as Record<string, string> | undefined;
    const authHeader = headers?.['Authorization'];
    return authHeader?.replace('Bearer ', '');
  }

  // ==================== MCP Server Methods ====================

  async getMCPHealth(): Promise<ApiResponse<any>> {
    try {
      const response = await sdk.healthCheckApiMcpsHealthGet();
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get MCP health',
      };
    }
  }

  async installMCPServer(request: MCPInstallRequest, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.installMcpServerApiMcpsInstallPost({
        body: request,
        ...(headers && { headers }),
      });
      const responseData = response.data as any;
      // Return the server data, preserving any message in the data object
      const result: ApiResponse<any> = { 
        success: true, 
        data: responseData?.server || responseData,
      };
      return result;
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to install MCP server',
      };
    }
  }


  async getMCPServerInfo(serverId: string): Promise<ApiResponse<any>> {
    try {
      const response = await sdk.getServerStatusApiMcpsServerIdStatusGet({
        path: { server_id: serverId },
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get MCP server info',
      };
    }
  }


  async uninstallMCPServer(serverId: string): Promise<ApiResponse<any>> {
    try {
      const response = await sdk.uninstallMcpServerApiMcpsServerIdUninstallDelete({
        path: { server_id: serverId },
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to uninstall MCP server',
      };
    }
  }

  async updateMCPServer(serverId: string, updateData: MCPUpdateRequest, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.updateMcpServerApiMcpsServerIdUpdatePut({
        path: { server_id: serverId },
        body: updateData,
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to update MCP server',
      };
    }
  }

  async getServerByName(serverName: string, token?: string): Promise<ApiResponse<any>> {
    try {
      // Use listMCPServers and filter by name
      const result = await this.listMCPServers(token);
      if (result.success && result.data) {
        const server = (result.data as any[]).find((s: any) => s.name === serverName || s.server_id === serverName);
        if (server) {
          return { success: true, data: server };
        }
      }
      return { success: false, error: 'Server not found' };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get server by name',
      };
    }
  }

  // Auth endpoints (may not be in generated SDK, using direct requests)
  async login(request: { username: string; password: string }): Promise<ApiResponse<any>> {
    try {
      const configBaseUrl = client.getConfig().baseUrl || 'http://localhost:8000';
      const baseUrl = configBaseUrl.endsWith('/') ? configBaseUrl.slice(0, -1) : configBaseUrl;
      const response = await fetch(`${baseUrl}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.message || `HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      return { success: true, data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Login failed',
      };
    }
  }

  async register(request: { username: string; email: string; password: string; full_name?: string }): Promise<ApiResponse<any>> {
    try {
      const configBaseUrl = client.getConfig().baseUrl || 'http://localhost:8000';
      const baseUrl = configBaseUrl.endsWith('/') ? configBaseUrl.slice(0, -1) : configBaseUrl;
      const response = await fetch(`${baseUrl}/api/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.message || `HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      return { success: true, data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Registration failed',
      };
    }
  }

  async getUserInfo(token: string): Promise<ApiResponse<any>> {
    try {
      const configBaseUrl = client.getConfig().baseUrl || 'http://localhost:8000';
      const baseUrl = configBaseUrl.endsWith('/') ? configBaseUrl.slice(0, -1) : configBaseUrl;
      const response = await fetch(`${baseUrl}/api/userinfo`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.message || `HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      return { success: true, data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get user info',
      };
    }
  }

  async getStats(filters?: { page?: number; limit?: number; [key: string]: any }, token?: string): Promise<ApiResponse<any>> {
    try {
      // Build request body with defaults matching StatsFilterRequest model
      const requestBody: any = {
        page: filters?.page ?? 1,
        limit: filters?.limit ?? 50,
      };
      
      // Add optional filters if provided
      if (filters?.agent_name) requestBody.agent_name = filters.agent_name;
      if (filters?.vmcp_name) requestBody.vmcp_name = filters.vmcp_name;
      if (filters?.method) requestBody.method = filters.method;
      if (filters?.search) requestBody.search = filters.search;
      
      const configBaseUrl = client.getConfig().baseUrl || 'http://localhost:8000';
      const baseUrl = configBaseUrl.endsWith('/') ? configBaseUrl.slice(0, -1) : configBaseUrl;
      const url = `${baseUrl}/api/stats`;
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { 'Authorization': `Bearer ${token}` }),
        },
        body: JSON.stringify(requestBody),
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.message || `HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      return { success: true, data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get stats',
      };
    }
  }

  async getOAuthUrl(provider: string, webClientUrl: string, authMode: string, username?: string, oauthParams?: any, token?: string): Promise<ApiResponse<any>> {
    try {
      const configBaseUrl = client.getConfig().baseUrl || 'http://localhost:8000';
      const baseUrl = configBaseUrl.endsWith('/') ? configBaseUrl.slice(0, -1) : configBaseUrl;

      // Build query parameters
      const params = new URLSearchParams({
        web_client_url: webClientUrl,
        auth_mode: authMode,
        client_id: 'web',
      });

      if (username) {
        params.append('username', username);
      }

      // Add any additional OAuth parameters
      if (oauthParams) {
        Object.entries(oauthParams).forEach(([key, value]) => {
          if (value !== undefined && value !== null) {
            params.append(key, String(value));
          }
        });
      }

      const response = await fetch(`${baseUrl}/api/oauth/${provider}/authorize?${params.toString()}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { 'Authorization': `Bearer ${token}` }),
        },
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.message || `HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      return { success: true, data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get OAuth URL',
      };
    }
  }

  async getToolLogsStats(token: string, range?: string): Promise<ApiResponse<any>> {
    try {
      const configBaseUrl = client.getConfig().baseUrl || 'http://localhost:8000';
      const baseUrl = configBaseUrl.endsWith('/') ? configBaseUrl.slice(0, -1) : configBaseUrl;
      const params = range ? `?range=${encodeURIComponent(range)}` : '';
      const response = await fetch(`${baseUrl}/api/tool-logs/stats${params}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.message || `HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      return { success: true, data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get tool logs stats',
      };
    }
  }

  async getVMCPConfiguration(vmcpName: string, options?: { server_id?: string; [key: string]: any }, token?: string): Promise<ApiResponse<any>> {
    try {
      const params = new URLSearchParams();
      if (options) {
        Object.entries(options).forEach(([key, value]) => {
          if (value !== undefined && value !== null) {
            params.append(key, String(value));
          }
        });
      }
      const configBaseUrl = client.getConfig().baseUrl || 'http://localhost:8000';
      const baseUrl = configBaseUrl.endsWith('/') ? configBaseUrl.slice(0, -1) : configBaseUrl;
      const url = `${baseUrl}/api/vmcps/${vmcpName}/oauth/config${params.toString() ? `?${params.toString()}` : ''}`;
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          ...(token && { 'Authorization': `Bearer ${token}` }),
        },
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.message || `HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      return { success: true, data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get VMCP configuration',
      };
    }
  }

  async saveVMCPConfiguration(vmcpName: string, config: any, token?: string): Promise<ApiResponse<any>> {
    try {
      const configBaseUrl = client.getConfig().baseUrl || 'http://localhost:8000';
      const baseUrl = configBaseUrl.endsWith('/') ? configBaseUrl.slice(0, -1) : configBaseUrl;
      const response = await fetch(`${baseUrl}/api/vmcps/${vmcpName}/oauth/config`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { 'Authorization': `Bearer ${token}` }),
        },
        body: JSON.stringify(config),
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.message || `HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      return { success: true, data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to save VMCP configuration',
      };
    }
  }

  async callMCPTool(serverId: string, request: MCPToolCallRequest | { tool_name: string; arguments: Record<string, any> }, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.callMcpToolApiMcpsServerIdToolsCallPost({
        path: { server_id: serverId },
        body: request,
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to call MCP tool',
      };
    }
  }

  async getMCPResource(serverId: string, request: MCPResourceRequest, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.getMcpResourceApiMcpsServerIdResourcesReadPost({
        path: { server_id: serverId },
        body: request,
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get MCP resource',
      };
    }
  }


  async listMCPServerTools(serverId: string, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.listServerToolsApiMcpsServerIdToolsListGet({
        path: { server_id: serverId },
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to list MCP server tools',
      };
    }
  }

  async listMCPServerResources(serverId: string, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.listServerResourcesApiMcpsServerIdResourcesListGet({
        path: { server_id: serverId },
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to list MCP server resources',
      };
    }
  }

  async listMCPServerPrompts(serverId: string, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.listServerPromptsApiMcpsServerIdPromptsListGet({
        path: { server_id: serverId },
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to list MCP server prompts',
      };
    }
  }

  // Note: discoverMCPServerCapabilities is not in the new API, removed for now

  // ==================== vMCP Methods ====================

  async getVMCPHealth(): Promise<ApiResponse<any>> {
    try {
      const response = await sdk.healthCheckApiVmcpsHealthGet();
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get vMCP health',
      };
    }
  }

  async createVMCP(request: CreateVMCPRequest, token?: string): Promise<ApiResponse<VmcpConfig>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.createVmcpApiVmcpsCreatePost({
        body: request,
        ...(headers && { headers }),
      });
      const responseData = response.data as any;
      const vmcp = responseData?.vMCP || responseData;
      return { success: true, data: vmcp as unknown as VmcpConfig };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to create vMCP',
      };
    }
  }

  async listVMCPS(token?: string): Promise<ApiResponse<{ private: any[]; public: any[] }>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.listVmcpsApiVmcpsListGet({
        ...(headers && { headers }),
      });
      const responseData = response.data as any;
      
      // The backend returns { private: [...], public: [...] }
      // Ensure we always return an object with both arrays
      let vmcpsData: { private: any[]; public: any[] };
      
      if (responseData && typeof responseData === 'object') {
        // Check if it already has the correct structure
        if ('private' in responseData || 'public' in responseData) {
          vmcpsData = {
            private: Array.isArray(responseData.private) ? responseData.private : [],
            public: Array.isArray(responseData.public) ? responseData.public : [],
          };
        } else if (Array.isArray(responseData)) {
          // If it's just an array, treat it as private vMCPs
          vmcpsData = {
            private: responseData,
            public: [],
          };
        } else {
          // Default to empty arrays
          vmcpsData = {
            private: [],
            public: [],
          };
        }
      } else {
        // Fallback to empty structure
        vmcpsData = {
          private: [],
          public: [],
        };
      }
      
      return { success: true, data: vmcpsData };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to list vMCPs',
      };
    }
  }

  async getVMCPDetails(vmcpId: string, token?: string): Promise<ApiResponse<VmcpConfig>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.getVmcpDetailsApiVmcpsVmcpIdGet({
        path: { vmcp_id: vmcpId },
        ...(headers && { headers }),
      });
      const responseData = response.data as any;
      const vmcp = responseData?.vMCP || responseData;
      return { success: true, data: vmcp as unknown as VmcpConfig };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get vMCP details',
      };
    }
  }

  async updateVMCP(vmcpId: string, request: UpdateVMCPRequest, token?: string): Promise<ApiResponse<VmcpConfig>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.updateVmcpApiVmcpsVmcpIdPut({
        path: { vmcp_id: vmcpId },
        body: request,
        ...(headers && { headers }),
      });
      const responseData = response.data as any;
      const vmcp = responseData?.vMCP || responseData;
      return { success: true, data: vmcp as unknown as VmcpConfig };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to update vMCP',
      };
    }
  }

  async deleteVMCP(vmcpId: string, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.deleteVmcpApiVmcpsVmcpIdDelete({
        path: { vmcp_id: vmcpId },
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to delete vMCP',
      };
    }
  }

  async callVMCPTool(vmcpId: string, request: VMCPToolCallRequest, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.callVmcpToolApiVmcpsVmcpIdToolsCallPost({
        path: { vmcp_id: vmcpId },
        body: request,
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to call vMCP tool',
      };
    }
  }

  async getVMCPResource(vmcpId: string, request: VMCPResourceRequest, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.readVmcpResourceApiVmcpsVmcpIdResourcesReadPost({
        path: { vmcp_id: vmcpId },
        body: request,
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get vMCP resource',
      };
    }
  }

  async getVMCPPrompt(vmcpId: string, request: any, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.getVmcpPromptApiVmcpsVmcpIdPromptsGetPost({
        path: { vmcp_id: vmcpId },
        body: request,
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get vMCP prompt',
      };
    }
  }

  async getMCPPrompt(serverId: string, request: any, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.getMcpPromptApiMcpsServerIdPromptsGetPost({
        path: { server_id: serverId },
        body: request,
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get MCP prompt',
      };
    }
  }

  async listVMCPTools(vmcpId: string, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.listVmcpToolsApiVmcpsVmcpIdToolsListPost({
        path: { vmcp_id: vmcpId },
        body: {} as any,
        ...(headers && { headers }),
      });
      // Return the full response data which contains { tools: [...], total_tools: N }
      const responseData = response.data as any;
      // The backend returns { success, message, data: { vmcp_id, tools, total_tools } }
      const data = responseData?.data || responseData;
      return { success: true, data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to list vMCP tools',
      };
    }
  }

  async listVMCPResources(vmcpId: string, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.listVmcpResourcesApiVmcpsVmcpIdResourcesListPost({
        path: { vmcp_id: vmcpId },
        body: {} as any,
        ...(headers && { headers }),
      });
      // Extract resources array from nested response: response.data.data.resources
      const responseData = response.data as any;
      const resources = responseData?.data?.resources || responseData?.resources || (Array.isArray(responseData?.data) ? responseData.data : []);
      return { success: true, data: resources };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to list vMCP resources',
      };
    }
  }

  async listVMCPPrompts(vmcpId: string, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.listVmcpPromptsApiVmcpsVmcpIdPromptsListPost({
        path: { vmcp_id: vmcpId },
        body: {} as any,
        ...(headers && { headers }),
      });
      // Extract prompts array from nested response: response.data.data.prompts
      const responseData = response.data as any;
      const prompts = responseData?.data?.prompts || responseData?.prompts || (Array.isArray(responseData?.data) ? responseData.data : []);
      return { success: true, data: prompts };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to list vMCP prompts',
      };
    }
  }

  async shareVMCP(vmcpId: string, request: { state: 'private' | 'public' | 'shared'; tags: string[] }, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.shareVmcpApiVmcpsSharePost({
        body: { vmcp_id: vmcpId, state: request.state as 'private' | 'public' | 'shared', tags: request.tags },
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to share vMCP',
      };
    }
  }

  async installVMCP(vmcpId: string, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.installVmcpFromRemoteApiVmcpsInstallPost({
        body: { public_vmcp_id: vmcpId },
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to install vMCP',
      };
    }
  }

  async listPublicVMCPS(token?: string): Promise<ApiResponse<any[]>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.listPublicVmcpsApiVmcpsPublicListGet({
        ...(headers && { headers }),
      });
      const responseData = response.data as any;
      const vmcps = Array.isArray(responseData) ? responseData : (responseData?.vmcps || []);
      return { success: true, data: vmcps };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to list public vMCPs',
      };
    }
  }

  async getPublicVMCPDetails(vmcpId: string, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.getPublicVmcpApiVmcpsPublicVmcpIdGet({
        path: { vmcp_id: vmcpId },
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get public vMCP details',
      };
    }
  }

  async forkVMCP(vmcpId: string, token?: string): Promise<ApiResponse<VmcpConfig>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.forkVmcpApiVmcpsVmcpIdForkPost({
        path: { vmcp_id: vmcpId },
        ...(headers && { headers }),
      });
      const responseData = response.data as any;
      const vmcp = responseData?.vMCP || responseData;
      return { success: true, data: vmcp as unknown as VmcpConfig };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to fork vMCP',
      };
    }
  }

  async refreshVMCP(vmcpId: string, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.refreshVmcpApiVmcpsVmcpIdRefreshPost({
        path: { vmcp_id: vmcpId },
        body: {} as any, // Empty body for refresh
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to refresh vMCP',
      };
    }
  }

  async uploadBlob(file: File, token: string, vmcpId?: string): Promise<ApiResponse<any>> {
    try {
      // The SDK's formDataBodySerializer will automatically convert this to FormData
      const response = await sdk.uploadFileApiBlobUploadPost({
        body: {
          file: file,  // Pass the File object directly, not FormData
          vmcp_id: vmcpId || null,
        },
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Upload failed',
      };
    }
  }

  async deleteBlob(blobId: string, token: string, vmcpId?: string): Promise<ApiResponse<any>> {
    try {
      const params = vmcpId ? `?vmcp_id=${encodeURIComponent(vmcpId)}` : '';
      const response = await sdk.deleteFileApiBlobBlobIdDelete({
        path: { blob_id: blobId },
        headers: {
          Authorization: `Bearer ${token}`,
        },
        ...(params && { query: { vmcp_id: vmcpId } }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Delete failed',
      };
    }
  }

  async renameBlob(blobId: string, newFilename: string, token: string, vmcpId?: string): Promise<ApiResponse<any>> {
    try {
      const response = await sdk.renameFileApiBlobBlobIdRenamePatch({
        path: { blob_id: blobId },
        body: { new_filename: newFilename, ...(vmcpId && { vmcp_id: vmcpId }) },
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Rename failed',
      };
    }
  }

  async getBlob(blobId: string, token: string, vmcpId?: string): Promise<ApiResponse<any>> {
    try {
      const params = vmcpId ? { vmcp_id: vmcpId } : undefined;
      const response = await sdk.getBlobContentApiBlobContentBlobIdGet({
        path: { blob_id: blobId },
        headers: {
          Authorization: `Bearer ${token}`,
        },
        ...(params && { query: params }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Get blob failed',
      };
    }
  }

  async downloadBlob(blobId: string, token: string, vmcpId?: string): Promise<ApiResponse<any>> {
    try {
      const params = vmcpId ? { vmcp_id: vmcpId } : undefined;
      const response = await sdk.downloadBlobApiBlobBlobsBlobIdGet({
        path: { blob_id: blobId },
        headers: {
          Authorization: `Bearer ${token}`,
        },
        ...(params && { query: params }),
      });
      // For binary data, handle appropriately
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Download blob failed',
      };
    }
  }

  async saveVMCPEnvironmentVariables(vmcpId: string, environmentVariables: any[], token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.saveVmcpEnvironmentVariablesApiVmcpsVmcpIdEnvironmentVariablesSavePost({
        path: { vmcp_id: vmcpId },
        body: { environment_variables: environmentVariables },
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to save environment variables',
      };
    }
  }

  async addServerToVMCP(vmcpId: string, serverData: any, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.addServerToVmcpApiVmcpsVmcpIdAddServerPost({
        path: { vmcp_id: vmcpId },
        body: { server_data: serverData },
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to add server to vMCP',
      };
    }
  }

  async removeServerFromVMCP(vmcpId: string, serverId: string, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.removeServerFromVmcpApiVmcpsVmcpIdRemoveServerDelete({
        path: { vmcp_id: vmcpId },
        query: { server_id: serverId },
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to remove server from vMCP',
      };
    }
  }

  async initiateMCPServerAuth(serverId: string, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.initiateAuthApiMcpsServerIdAuthPost({
        path: { server_id: serverId },
        ...(headers && { headers }),
      });
      
      // The SDK returns the full BaseResponse object in response.data
      // We need to extract the nested data field
      const responseData = response.data as any;
      
      // Handle both response structures:
      // 1. If response.data is the BaseResponse with nested data field
      // 2. If response.data is already the data payload
      const data = responseData?.data ?? responseData;
      
      console.log('Auth response structure:', {
        responseData,
        nestedData: responseData?.data,
        extractedData: data,
        hasAuthorizationUrl: !!data?.authorization_url
      });
      
      return { success: true, data };
    } catch (error) {
      console.error('Error in initiateMCPServerAuth:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to initiate MCP server auth',
      };
    }
  }

  async discoverMCPServerCapabilities(serverId: string, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.discoverServerCapabilitiesApiMcpsServerIdDiscoverCapabilitiesPost({
        path: { server_id: serverId },
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to discover MCP server capabilities',
      };
    }
  }

  async getServerStatus(serverId: string, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.getServerStatusApiMcpsServerIdStatusGet({
        path: { server_id: serverId },
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get server status',
      };
    }
  }

  async clearCacheMCPServer(serverId: string, token?: string): Promise<ApiResponse<any>> {
    try {
      // Note: clearCache endpoint may not exist in generated SDK, using disconnect as fallback
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.disconnectMcpServerApiMcpsServerIdDisconnectPost({
        path: { server_id: serverId },
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to clear cache for MCP server',
      };
    }
  }

  async getGlobalMCPServers(filters?: { category?: string; search?: string; limit?: number; offset?: number }, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const query = filters ? {
        ...(filters.category && { category: filters.category }),
        ...(filters.search && { search: filters.search }),
        ...(filters.limit && { limit: filters.limit }),
        ...(filters.offset && { offset: filters.offset }),
      } : undefined;
      const response = await sdk.listGlobalMcpServersApiMcpsRegistryServersGet({
        ...(query && { query }),
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get global MCP servers',
      };
    }
  }

  async installGlobalMCPServer(serverId: string, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      // Note: installGlobalMCPServer may use a different endpoint in generated SDK
      const response = await sdk.installMcpServerApiMcpsInstallPost({
        body: { server_id: serverId } as any,
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to install global MCP server',
      };
    }
  }

  async clearMCPServerAuth(serverId: string, token?: string): Promise<ApiResponse<any>> {
    try {
      // Note: clearAuth endpoint may not exist, using disconnect as fallback
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.disconnectMcpServerApiMcpsServerIdDisconnectPost({
        path: { server_id: serverId },
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to clear MCP server auth',
      };
    }
  }

  async listMCPServers(token?: string): Promise<ApiResponse<any[]>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.listMcpServersApiMcpsListGet({
        ...(headers && { headers }),
      });
      const responseData = response.data as any;
      // API returns: { success: true, data: [...servers...], pagination: {...} }
      const servers = responseData?.data || responseData?.servers || (Array.isArray(responseData) ? responseData : []);
      return { success: true, data: servers };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to list MCP servers',
      };
    }
  }

  async connectMCPServer(serverId: string, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.connectMcpServerWithCapabilitiesApiMcpsServerIdConnectPost({
        path: { server_id: serverId },
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to connect MCP server',
      };
    }
  }

  async disconnectMCPServer(serverId: string, token?: string): Promise<ApiResponse<any>> {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await sdk.disconnectMcpServerApiMcpsServerIdDisconnectPost({
        path: { server_id: serverId },
        ...(headers && { headers }),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to disconnect MCP server',
      };
    }
  }
  // Note: refreshVMCP and getSummaryVMCP are not in the new API, removed for now
}

// Get backend URL from environment variables
// The generated SDK endpoints already include /api/, so base URL should not include it
const BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL?.replace(/\/api\/?$/, '') ||
  'http://localhost:8000';

// Create and export API client instance
export const apiClient = new ApiClient(BACKEND_URL);

// Configure authentication token from localStorage
const authDisabled = import.meta.env.VITE_VMCP_OSS_BUILD === 'true';
if (authDisabled) {
  // In OSS mode, use the local-token
  apiClient.setToken('local-token');
} else {
  // In regular mode, use token from localStorage
  const token = localStorage.getItem('access_token');
  if (token) {
    apiClient.setToken(token);
  }
}

// Export a helper to update the token
export function updateApiToken(token: string | undefined) {
  apiClient.setToken(token);
}

// Default export
export default apiClient;
