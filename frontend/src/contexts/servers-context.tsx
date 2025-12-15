
import React, { createContext, useContext, useState, useCallback, useEffect, ReactNode, useRef, useMemo } from 'react';
import { apiClient} from '@/api/client';
import type { McpServerInfo as MCPServer, RegistryServerInfo as MCPRegistryServer } from '@/api/generated/types.gen';
import { useAuth } from './auth-context';
import { parseEnvVars, normalizeEnvVars } from '@/lib/app-utils';
import { EnvironmentVariablesModal } from '@/components/vmcp/EnvironmentVariablesModal';

interface ServerStats {
  total: number;
  connected: number;
  disconnected: number;
  auth_required: number;
  errors: number;
}

interface ServersState {
  servers: MCPServer[];
  mcpregistryservers: MCPRegistryServer[]; // MCP server registry
  serverStats: ServerStats;
  mcpregistryserverStats: ServerStats; // Stats for MCP registry servers
  loading: boolean;
  mcpregistryLoading: boolean; // Loading state for MCP registry servers
  error: string | null;
  lastUpdated: number | null;
  initialized: boolean;
  hasError: boolean;
}

interface ServersContextType extends ServersState {
  refreshServers: () => Promise<void>;
  refreshMCPRegistryServers: () => Promise<void>;
  connectServer: (serverId: string) => Promise<void>;
  disconnectServer: (serverId: string) => Promise<void>;
  clearCacheServer: (serverId: string) => Promise<void>;
  authorizeServer: (serverId: string) => Promise<void>;
  addServer: (serverTemplate: any) => Promise<void>;
  updateServer: (serverData: any) => Promise<void>;
  removeServer: (serverId: string) => Promise<void>;
  clearError: () => void;
  refreshServerCapabilities: (serverId: string) => Promise<void>;
  refreshAllCapabilities: () => Promise<void>;
  refreshServerStatus: (serverId: string) => Promise<void>;
  refreshAllStatus: () => Promise<void>;
  clearServerAuth: (serverId: string) => Promise<void>;
  installMCPRegistryServer: (serverData: MCPRegistryServer) => Promise<void>;
  updateServerEnvVars: (serverId: string, env: Record<string, string>) => Promise<void>;
}

// Create separate contexts for state and actions
const ServersStateContext = createContext<ServersState | undefined>(undefined);
const ServersActionsContext = createContext<Omit<ServersContextType, keyof ServersState> | undefined>(undefined);

interface ServersProviderProps {
  children: ReactNode;
}

export function ServersProvider({ children }: ServersProviderProps) {
  const { isAuthenticated, user } = useAuth();
  const [state, setState] = useState<ServersState>({
    servers: [],
    mcpregistryservers: [],
    serverStats: {
      total: 0,
      connected: 0,
      disconnected: 0,
      auth_required: 0,
      errors: 0
    },
    mcpregistryserverStats: {
      total: 0,
      connected: 0,
      disconnected: 0,
      auth_required: 0,
      errors: 0
    },
    loading: true, // Start with loading true to prevent undefined access
    mcpregistryLoading: false,
    error: null,
    lastUpdated: null,
    initialized: false,
    hasError: false
  });

  // Add refs to prevent duplicate calls and track retry attempts
  const loadingRef = useRef(false);
  const retryCountRef = useRef(0);
  const hasErrorRef = useRef(false);
  const maxRetries = 3;
  const serversRef = useRef<MCPServer[]>([]);
  
  // Keep serversRef in sync with state
  useEffect(() => {
    serversRef.current = state.servers;
  }, [state.servers]);

  // Helper function to recalculate server stats based on current server statuses
  const recalculateStats = useCallback((servers: MCPServer[]) => {
    return {
      total: servers.length,
      connected: servers.filter(s => s.status === 'connected').length,
      disconnected: servers.filter(s => s.status === 'disconnected').length,
      auth_required: servers.filter(s => s.status === 'auth_required').length,
      errors: servers.filter(s => s.status === 'error').length
    };
  }, []);

  const refreshServerCapabilities = useCallback(async (serverId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }
  
      const result = await apiClient.discoverMCPServerCapabilities(serverId, accessToken);
        
      if (result.success && result.data) {
        // Extract capabilities from the response
        const capabilities = result.data;
        
        console.log(`🔧 Raw capabilities response for ${serverId}:`, result.data);
        console.log(`🔧 Processed capabilities for ${serverId}:`, {
          hasCapabilities: !!result.data.capabilities,
          toolsCount: capabilities.tools_count,
          resourcesCount: capabilities.resources_count,
          promptsCount: capabilities.prompts_count,
          toolsListLength: capabilities.tools_list?.length,
          toolDetailsLength: capabilities.tool_details?.length,
          toolsList: capabilities.tools_list,
          resourcesList: capabilities.resources_list,
          promptsList: capabilities.prompts_list
        });
        
        // Update the specific server with new capabilities
        setState(prevState => {
          const updatedServers = prevState.servers.map(server => {
            if (server.id === serverId) {
              const updatedServer = {
                ...server,
                capabilities: capabilities.capabilities || {},
                // Update the individual list fields that the UI expects
                tools_list: capabilities.tools_list || [],
                resources_list: capabilities.resources_list || [],
                prompts_list: capabilities.prompts_list || [],
                // Update the count fields
                tools_count: capabilities.capabilities.tools_count || 0,
                resources_count: capabilities.capabilities.resources_count || 0,
                prompts_count: capabilities.capabilities.prompts_count || 0,
                // Update detailed information
                tool_details: capabilities.tool_details || [],
                resource_details: capabilities.resource_details || [],
                resource_template_details: capabilities.resource_template_details || [],
                prompt_details: capabilities.prompt_details || [],
                last_capabilities_update: new Date().toISOString()
              };
              
              console.log(`🔧 Updated server ${serverId} with capabilities:`, {
                tools_list: updatedServer.tools_list,
                resources_list: updatedServer.resources_list,
                prompts_list: updatedServer.prompts_list,
                tools_count: updatedServer.tools_count,
                resources_count: updatedServer.resources_count,
                prompts_count: updatedServer.prompts_count
              });
              
              return updatedServer;
            }
            return server;
          });
          
          return {
            ...prevState,
            servers: updatedServers as MCPServer[],
            serverStats: recalculateStats(updatedServers as MCPServer[]),
            lastUpdated: Date.now()
          };
        });
      } else {
        console.error(`Failed to refresh capabilities for ${serverId}:`, result.error);
        setState(prevState => ({
          ...prevState,
          error: `Failed to refresh capabilities for ${serverId}: ${result.error}`,
          hasError: true
        }));
      }
    } catch (error) {
      console.error(`Error refreshing capabilities for ${serverId}:`, error);
      setState(prevState => ({
        ...prevState,
        error: `Error refreshing capabilities for ${serverId}: ${error instanceof Error ? error.message : 'Unknown error'}`,
        hasError: true
      }));
    }
  }, [recalculateStats]);

  const refreshAllCapabilities = useCallback(async () => {
    if (!state.servers.length) return;
    
    setState(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      const promises = state.servers.map(server => refreshServerCapabilities(server.id));
      await Promise.allSettled(promises);
      
      setState(prev => ({ ...prev, loading: false, lastUpdated: Date.now() }));
    } catch (error) {
      console.error('Error refreshing all capabilities:', error);
      setState(prev => ({ 
        ...prev, 
        loading: false, 
        error: 'Failed to refresh all capabilities',
        hasError: true
      }));
    }
  }, [state.servers, refreshServerCapabilities]);

  const refreshServerStatus = useCallback(async (serverId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }
  
      const result = await apiClient.getServerStatus(serverId, accessToken);
        
      if (result.success && result.data) {
        const statusData = result.data.status || result.data;
        // Extract status string from response, handling both object and string formats
        const status = typeof statusData === 'object' && statusData.status 
          ? statusData.status 
          : (typeof statusData === 'string' ? statusData : 'disconnected');
        
        // Ensure status is one of the expected values and cast to proper type
        const validStatus = (['connected', 'disconnected', 'auth_required', 'error'].includes(status) 
          ? status 
          : 'disconnected') as 'connected' | 'disconnected' | 'auth_required' | 'error';
        
        // Update the specific server with new status
        setState(prevState => {
          const updatedServers = prevState.servers.map(server => {
            if (server.id === serverId) {
              return {
                ...server,
                status: validStatus,
                last_status_update: new Date().toISOString()
              };
            }
            return server;
          });
          
          return {
            ...prevState,
            servers: updatedServers as MCPServer[],
            serverStats: recalculateStats(updatedServers as MCPServer[]),
            lastUpdated: Date.now()
          };
        });
      } else {
        console.error(`Failed to refresh status for ${serverId}:`, result.error);
      }
    } catch (error) {
      console.error(`Error refreshing status for ${serverId}:`, error);
    }
  }, [recalculateStats]);

  const refreshAllStatus = useCallback(async () => {
    if (!state.servers.length) return;
    
    setState(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      const promises = state.servers.map(server => refreshServerStatus(server.id));
      await Promise.allSettled(promises);
      
      setState(prev => ({ ...prev, loading: false, lastUpdated: Date.now() }));
    } catch (error) {
      console.error('Error refreshing all statuses:', error);
      setState(prev => ({ 
        ...prev, 
        loading: false, 
        error: 'Failed to refresh all statuses',
        hasError: true
      }));
    }
  }, [state.servers, refreshServerStatus]);

  const connectServer = useCallback(async (serverId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }
  
      const result = await apiClient.connectMCPServer(serverId, accessToken);
        
      if (result.success) {
        // Update server status based on response
        const status = result.data?.status || 'connected';
        setState(prevState => {
          const updatedServers = prevState.servers.map(server => {
            if (server.id === serverId) {
              return {
                ...server,
                status: status as 'connected' | 'disconnected' | 'auth_required' | 'error',
                last_status_update: new Date().toISOString()
              };
            }
            return server;
          });
          
          return {
            ...prevState,
            servers: updatedServers as MCPServer[],
            serverStats: recalculateStats(updatedServers as MCPServer[]),
            lastUpdated: Date.now()
          };
        });
      } else {
        console.error(`Failed to connect to ${serverId}:`, result.error);
        setState(prevState => ({
          ...prevState,
          error: `Failed to connect to ${serverId}: ${result.error}`,
          hasError: true
        }));
      }
    } catch (error) {
      console.error(`Error connecting to ${serverId}:`, error);
      setState(prevState => ({
        ...prevState,
        error: `Error connecting to ${serverId}: ${error instanceof Error ? error.message : 'Unknown error'}`,
        hasError: true
      }));
    }
  }, [recalculateStats]);

  const disconnectServer = useCallback(async (serverId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }
  
      const result = await apiClient.disconnectMCPServer(serverId, accessToken);
        
      if (result.success) {
        // Update server status to disconnected
        setState(prevState => {
          const updatedServers = prevState.servers.map(server => {
            if (server.id === serverId) {
              return {
                ...server,
                status: 'disconnected' as const,
                auth_information: 'absent',
                last_status_update: new Date().toISOString()
              };
            }
            return server;
          });
          
          return {
            ...prevState,
            servers: updatedServers as MCPServer[],
            serverStats: recalculateStats(updatedServers as MCPServer[]),
            lastUpdated: Date.now()
          };
        });
      } else {
        console.error(`Failed to disconnect from ${serverId}:`, result.error);
        setState(prevState => ({
          ...prevState,
          error: `Failed to disconnect from ${serverId}: ${result.error}`,
          hasError: true
        }));
      }
    } catch (error) {
      console.error(`Error disconnecting from ${serverId}:`, error);
      setState(prevState => ({
        ...prevState,
        error: `Error disconnecting from ${serverId}: ${error instanceof Error ? error.message : 'Unknown error'}`,
        hasError: true
      }));
    }
  }, [recalculateStats]);

  const clearCacheServer = useCallback(async (serverId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }
  
      const result = await apiClient.clearCacheMCPServer(serverId, accessToken);
        
      if (result.success) {
        // Update server status based on response
        const status = result.data?.status || 'disconnected';
        setState(prevState => {
          const updatedServers = prevState.servers.map(server => {
            if (server.id === serverId) {
              return {
                ...server,
                status: status as 'connected' | 'disconnected' | 'auth_required' | 'error',
                auth_information: 'absent',
                last_status_update: new Date().toISOString()
              };
            }
            return server;
          });
          
          return {
            ...prevState,
            servers: updatedServers as MCPServer[],
            serverStats: recalculateStats(updatedServers as MCPServer[]),
            lastUpdated: Date.now()
          };
        });
      } else {
        console.error(`Failed to clear cache for ${serverId}:`, result.error);
        setState(prevState => ({
          ...prevState,
          error: `Failed to clear cache for ${serverId}: ${result.error}`,
          hasError: true
        }));
      }
    } catch (error) {
      console.error(`Error clearing cache for ${serverId}:`, error);
      setState(prevState => ({
        ...prevState,
        error: `Error clearing cache for ${serverId}: ${error instanceof Error ? error.message : 'Unknown error'}`,
        hasError: true
      }));
    }
  }, [recalculateStats]);

  const authorizeServer = useCallback(async (serverId: string) => {
    try {
      // Get access token
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }

      // Call API directly to get authorization URL
      const result = await apiClient.initiateMCPServerAuth(serverId, accessToken);
      
      if (result.success && result.data?.authorization_url) {
        // Open the authorization URL directly in a new tab
        window.open(result.data.authorization_url, '_blank', 'noopener,noreferrer');
        console.log('Authorization URL opened:', result.data.authorization_url);
      } else {
        throw new Error(result.error || 'Failed to get authorization URL');
      }
    } catch (error) {
      console.error(`Error opening authorization for ${serverId}:`, error);
      setState(prevState => ({
        ...prevState,
        error: `Error opening authorization for ${serverId}: ${error instanceof Error ? error.message : 'Unknown error'}`,
        hasError: true
      }));
    }
  }, []);

  const addServer = useCallback(async (serverData: any) => {
    try {
      // Validate that serverData is actually a server object
      if (typeof serverData !== 'object' || !serverData.id) {
        console.error('Invalid server object received:', serverData);
        setState(prevState => ({
          ...prevState,
          error: 'Invalid server object received',
          hasError: true
        }));
        return;
      }
      
      // Transform the server object to match the MCPServer interface
      const newServer: MCPServer = serverData
      
      console.log('🔧 Adding new server to state:', newServer);
      
      setState(prevState => {
        console.log('🔧 Current servers state:', prevState.servers);
        
        // Check if server already exists to prevent duplicates
        const serverExists = prevState.servers.some(s => s.id === newServer.id);
        if (serverExists) {
          console.log('🔧 Server already exists, updating instead of adding:', newServer.id);
          const updatedServers = prevState.servers.map(s => 
            s.id === newServer.id ? newServer : s
          );
          return {
            ...prevState,
            servers: updatedServers,
            serverStats: recalculateStats(updatedServers),
            lastUpdated: Date.now(),
            error: null,
            hasError: false
          };
        }
        
        const updatedServers = [...prevState.servers, newServer];
        console.log('🔧 Updated servers array:', updatedServers);
        return {
          ...prevState,
          servers: updatedServers,
          serverStats: recalculateStats(updatedServers),
          lastUpdated: Date.now(),
          error: null,
          hasError: false
        };
      });
    } catch (error) {
      console.error('Error adding server:', error);
      setState(prevState => ({
        ...prevState,
        error: `Error adding server: ${error instanceof Error ? error.message : 'Unknown error'}`,
        hasError: true
      }));
    }
  }, [recalculateStats]);

  const updateServer = useCallback(async (serverData: any) => {
    try {
      // Validate that serverData is actually a server object
      if (typeof serverData !== 'object' || !serverData.id) {
        console.error('Invalid server object received for update:', serverData);
        setState(prevState => ({
          ...prevState,
          error: 'Invalid server object received for update',
          hasError: true
        }));
        return;
      }
      
      // Transform the server object to match the MCPServer interface
      const updatedServer: MCPServer = serverData
      
      console.log('🔧 Updating server in state:', updatedServer);
      
      setState(prevState => {
        console.log('🔧 Current servers state:', prevState.servers);
        
        // Check if server exists to update
        const serverExists = prevState.servers.some(s => s.id === updatedServer.id);
        if (!serverExists) {
          console.log('🔧 Server not found for update, adding instead:', updatedServer.id);
          const updatedServers = [...prevState.servers, updatedServer];
          return {
            ...prevState,
            servers: updatedServers,
            serverStats: recalculateStats(updatedServers),
            lastUpdated: Date.now(),
            error: null,
            hasError: false
          };
        }
        
        const updatedServers = prevState.servers.map(s => 
          s.id === updatedServer.id ? updatedServer : s
        );
        console.log('🔧 Updated servers array:', updatedServers);
        return {
          ...prevState,
          servers: updatedServers,
          serverStats: recalculateStats(updatedServers),
          lastUpdated: Date.now(),
          error: null,
          hasError: false
        };
      });
    } catch (error) {
      console.error('Error updating server:', error);
      setState(prevState => ({
        ...prevState,
        error: `Error updating server: ${error instanceof Error ? error.message : 'Unknown error'}`,
        hasError: true
      }));
    }
  }, [recalculateStats]);

  const removeServer = useCallback(async (serverId: string) => {
    try {
      console.log('🔧 Removing server from state:', serverId);
      
      setState(prevState => {
        console.log('🔧 Current servers state:', prevState.servers);
        
        const updatedServers = prevState.servers.filter(s => s.id !== serverId);
        console.log('🔧 Updated servers array after removal:', updatedServers);
        
        return {
          ...prevState,
          servers: updatedServers,
          serverStats: recalculateStats(updatedServers),
          lastUpdated: Date.now(),
          error: null,
          hasError: false
        };
      });
    } catch (error) {
      console.error('Error removing server:', error);
      setState(prevState => ({
        ...prevState,
        error: `Error removing server: ${error instanceof Error ? error.message : 'Unknown error'}`,
        hasError: true
      }));
    }
  }, [recalculateStats]);

  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null, hasError: false }));
  }, []);

  const refreshMCPRegistryServers = useCallback(async () => {
    if (!isAuthenticated || !user) {
      console.log('❌ Not authenticated, skipping MCP registry server refresh');
      return;
    }

    setState(prev => ({ ...prev, mcpregistryLoading: true, error: null }));

    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }

      console.log('🔄 Fetching MCP registry servers...');
      const result = await apiClient.getGlobalMCPServers({}, accessToken);
      
      if (result.success && result.data) {
        // Process servers to MCPRegistryServer format
        const processedServers: MCPRegistryServer[] = result.data.servers || [];
        // Calculate stats for registry servers
        const registryServerStats = {
          total: processedServers.length,
          connected: 0, // Registry servers are not connected by default
          disconnected: processedServers.length,
          auth_required: processedServers.filter(s => s.requiresAuth).length,
          errors: 0
        };
        
        setState(prev => ({
          ...prev,
          mcpregistryservers: processedServers,
          mcpregistryserverStats: registryServerStats,
          mcpregistryLoading: false,
          error: null,
          lastUpdated: Date.now(),
          hasError: false
        }));

        console.log(`✅ Successfully loaded ${processedServers.length} MCP registry servers`);
      } else {
        throw new Error(result.error || 'Failed to fetch MCP registry servers');
      }
    } catch (error) {
      console.error('❌ Error fetching MCP registry servers:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      
      setState(prev => ({
        ...prev,
        mcpregistryLoading: false,
        error: errorMessage,
        hasError: true
      }));
    }
  }, [isAuthenticated, user]);

  const [envVarsModalOpen, setEnvVarsModalOpen] = useState(false);
  const [pendingServerInstall, setPendingServerInstall] = useState<MCPRegistryServer | null>(null);
  const [isInstalling, setIsInstalling] = useState(false);

  const refreshServers = useCallback(async () => {
    if (loadingRef.current) {
      console.log('🔄 Refresh already in progress, skipping...');
      return;
    }

    if (!isAuthenticated || !user) {
      console.log('❌ Not authenticated, skipping server refresh');
      return;
    }

    loadingRef.current = true;
    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }

      console.log('🔄 Fetching servers...');
      const result = await apiClient.listMCPServers(accessToken);
      
      if (result.success && result.data) {
        const servers = Array.isArray(result.data) ? result.data : [result.data];
        
        // Process servers and add computed fields
        const processedServers = servers.map(server => ({
          ...server,
          env_vars: server.env_vars ? parseEnvVars(server.env_vars) : {},
          last_capabilities_update: server.last_capabilities_update || null,
          last_status_update: server.last_status_update || null,
          // Ensure status is one of the expected values
          status: ['connected', 'disconnected', 'auth_required', 'error'].includes(server.status) 
            ? server.status 
            : 'disconnected'
        }));

        // Extract stats from response data if available
        const responseData = result.data as any;
        // Stats might be in result.data.stats or at the top level of responseData
        const stats = (responseData && typeof responseData === 'object' && 'stats' in responseData) 
          ? responseData.stats 
          : (responseData?.total !== undefined ? responseData : null);
        // Use stats from backend response if available, otherwise recalculate
        const serverStats = {
          total: stats?.total || processedServers.length,
          connected: stats?.connected || 0,
          disconnected: stats?.disconnected || 0,
          auth_required: stats?.auth_required || 0,
          errors: stats?.errors || 0
        };
        
        setState(prev => ({
          ...prev,
          servers: processedServers,
          serverStats,
          loading: false,
          error: null,
          lastUpdated: Date.now(),
          initialized: true,
          hasError: false
        }));

        console.log(`✅ Successfully loaded ${processedServers.length} servers`);
        retryCountRef.current = 0; // Reset retry count on success
        hasErrorRef.current = false;
      } else {
        throw new Error(result.error || 'Failed to fetch servers');
      }
    } catch (error) {
      console.error('❌ Error fetching servers:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage,
        hasError: true
      }));

      hasErrorRef.current = true;
      
      // Implement retry logic
      if (retryCountRef.current < maxRetries) {
        retryCountRef.current++;
        console.log(`🔄 Retry attempt ${retryCountRef.current}/${maxRetries} in 5 seconds...`);
        
        setTimeout(() => {
          if (hasErrorRef.current) {
            refreshServers();
          }
        }, 5000);
      } else {
        console.log('❌ Max retries reached, giving up');
      }
    } finally {
      loadingRef.current = false;
    }
  }, [isAuthenticated, user, recalculateStats]);

  // Define performInstallWithRefresh after refreshServers is defined
  const performInstallWithRefresh = useCallback(async (
    serverData: MCPRegistryServer,
    env?: Record<string, string>,
    accessToken?: string
  ) => {
    try {
      const token = accessToken || localStorage.getItem('access_token');
      if (!token) {
        throw new Error('No access token available');
      }

      setIsInstalling(true);
      console.log('='.repeat(60));
      console.log(`🔄 [FRONTEND] Installing MCP registry server: ${serverData.id || serverData.name}`);
      console.log(`🔄 Has env vars:`, !!env);
      if (env) {
        console.log(`🔄 Env var keys:`, Object.keys(env));
        Object.entries(env).forEach(([key, value]) => {
          const masked = value && value.length > 24 
            ? `${value.substring(0, 20)}...${value.substring(value.length - 4)}`
            : value;
          console.log(`🔄   ${key} = ${masked} (length: ${value?.length || 0})`);
        });
      }
      console.log('='.repeat(60));
      
      const result = await apiClient.installGlobalMCPServer(serverData, env, token);
      
      if (result.success) {
        console.log(`✅ Successfully installed MCP registry server: ${serverData.id || serverData.name}`);
        // Refresh servers list
        loadingRef.current = false;
        await refreshServers();
      } else {
        throw new Error(result.error || 'Failed to install MCP registry server');
      }
    } catch (error) {
      console.error('❌ Error installing MCP registry server:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      
      setState(prev => ({
        ...prev,
        error: errorMessage,
        hasError: true
      }));
      
      throw error;
    } finally {
      setIsInstalling(false);
      setEnvVarsModalOpen(false);
      setPendingServerInstall(null);
    }
  }, [refreshServers]);

  // Define handleEnvVarsSubmit after performInstallWithRefresh is defined
  const handleEnvVarsSubmit = useCallback(async (env: Record<string, string>) => {
    if (!pendingServerInstall) return;
    await performInstallWithRefresh(pendingServerInstall, env);
  }, [pendingServerInstall, performInstallWithRefresh]);

  // Define installMCPRegistryServer after performInstallWithRefresh is defined
  const installMCPRegistryServer = useCallback(async (serverData: MCPRegistryServer) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }

      // Check if server has env_vars that need configuration
      // Check both env_vars (metadata) and mcp_registry_config.env (actual config)
      const envVars = serverData.mcp_registry_config?.env || serverData.env_vars;
      const hasEnvVars = envVars && (
        (typeof envVars === 'object' && envVars !== null && Object.keys(envVars).length > 0) ||
        (typeof envVars === 'string' && envVars.trim().length > 0)
      );

      console.log('🔍 Checking env vars for server:', serverData.name, {
        envVars,
        hasEnvVars,
        mcp_registry_config_env: serverData.mcp_registry_config?.env,
        env_vars: serverData.env_vars,
        envVarsType: typeof envVars,
        envVarsKeys: (typeof envVars === 'object' && envVars !== null) ? Object.keys(envVars) : null
      });

      if (hasEnvVars) {
        console.log('✅ Server has env vars, showing modal');
        // Show modal to configure env vars
        setPendingServerInstall(serverData);
        setEnvVarsModalOpen(true);
        return;
      } else {
        console.log('❌ Server has no env vars, installing directly');
      }

      // No env vars, install directly
      await performInstallWithRefresh(serverData, undefined, accessToken);
    } catch (error) {
      console.error('❌ Error installing MCP registry server:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      
      setState(prev => ({
        ...prev,
        error: errorMessage,
        hasError: true
      }));
      
      throw error;
    }
  }, [performInstallWithRefresh]);

  // Initialize servers on mount and when auth changes
  useEffect(() => {
    if (isAuthenticated && user && !state.initialized) {
      refreshServers();
      refreshMCPRegistryServers();
    }
  }, [isAuthenticated, user, state.initialized, refreshServers, refreshMCPRegistryServers]);

  const updateServerEnvVars = useCallback(async (serverId: string, env: Record<string, string>) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }

      // Get current server from ref (always has latest servers)
      const currentServer = serversRef.current.find(s => s.id === serverId || (s as any).server_id === serverId);

      if (!currentServer) {
        throw new Error(`Server ${serverId} not found`);
      }

      // Check if server is currently connected
      const wasConnected = currentServer.status === 'connected';
      
      // Disconnect if connected (env vars require reconnection)
      if (wasConnected) {
        console.log(`🔌 Disconnecting server ${serverId} before updating env vars`);
        await disconnectServer(serverId);
      }

      // Build update request with new env vars
      const updateRequest = {
        name: currentServer.name,
        mode: (currentServer as any).transport_type || currentServer.transport_type || 'stdio',
        description: currentServer.description || null,
        command: currentServer.command || null,
        args: currentServer.args || null,
        env: env,
        url: currentServer.url || null,
        headers: currentServer.headers || null,
        auth_type: 'none',
        auto_connect: currentServer.auto_connect ?? true,
        enabled: currentServer.enabled ?? true,
      };

      console.log(`🔄 Updating env vars for server ${serverId}`);
      const result = await apiClient.updateMCPServer(serverId, updateRequest, accessToken);
      
      if (result.success) {
        console.log(`✅ Successfully updated env vars for server ${serverId}`);
        
        // Refresh server list to get updated config
        await refreshServers();
        
        // Reconnect if it was connected before
        if (wasConnected) {
          console.log(`🔄 Reconnecting server ${serverId} after env vars update`);
          await connectServer(serverId);
        }
      } else {
        throw new Error(result.error || 'Failed to update server env vars');
      }
    } catch (error) {
      console.error('❌ Error updating server env vars:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      
      setState(prev => ({
        ...prev,
        error: errorMessage,
        hasError: true
      }));
      
      throw error;
    }
  }, [refreshServers, connectServer, disconnectServer]);

  const clearServerAuth = useCallback(async (serverId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }

      const result = await apiClient.clearMCPServerAuth(serverId, accessToken);
      
      if (result.success) {
        // Update server status to disconnected and clear auth info
        setState(prevState => {
          const updatedServers = prevState.servers.map(server => {
            if (server.id === serverId) {
              return {
                ...server,
                status: 'disconnected' as const,
                auth_information: 'absent',
                last_status_update: new Date().toISOString()
              };
            }
            return server;
          });
          
          return {
            ...prevState,
            servers: updatedServers as MCPServer[],
            serverStats: recalculateStats(updatedServers as MCPServer[]),
            lastUpdated: Date.now()
          };
        });
        
        console.log(`✅ Successfully cleared auth for server: ${serverId}`);
      } else {
        throw new Error(result.error || 'Failed to clear server auth');
      }
    } catch (error) {
      console.error('❌ Error clearing server auth:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      
      setState(prev => ({
        ...prev,
        error: errorMessage,
        hasError: true
      }));
      
      throw error;
    }
  }, []);

  // Memoize actions to prevent unnecessary re-renders
  const actions = useMemo(() => ({
    refreshServers,
    refreshMCPRegistryServers,
    connectServer,
    disconnectServer,
    clearCacheServer,
    authorizeServer,
    addServer,
    updateServer,
    removeServer,
    clearError,
    refreshServerCapabilities,
    refreshAllCapabilities,
    refreshServerStatus,
    refreshAllStatus,
    clearServerAuth,
    installMCPRegistryServer,
    updateServerEnvVars,
  }), [
    refreshServers,
    refreshMCPRegistryServers,
    connectServer,
    disconnectServer,
    clearCacheServer,
    authorizeServer,
    addServer,
    updateServer,
    removeServer,
    clearError,
    refreshServerCapabilities,
    refreshAllCapabilities,
    refreshServerStatus,
    refreshAllStatus,
    clearServerAuth,
    installMCPRegistryServer,
    updateServerEnvVars,
  ]);

  // Get initial env vars for modal
  const getInitialEnvVars = useCallback(() => {
    if (!pendingServerInstall) return undefined;
    
    // Try mcp_registry_config.env first, then env_vars
    if (pendingServerInstall.mcp_registry_config?.env) {
      return pendingServerInstall.mcp_registry_config.env;
    }
    if (pendingServerInstall.env_vars) {
      return normalizeEnvVars(pendingServerInstall.env_vars);
    }
    return undefined;
  }, [pendingServerInstall]);

  return (
    <ServersStateContext.Provider value={state}>
      <ServersActionsContext.Provider value={actions}>
        {children}
        <EnvironmentVariablesModal
          isOpen={envVarsModalOpen}
          onClose={() => {
            setEnvVarsModalOpen(false);
            setPendingServerInstall(null);
          }}
          onSubmit={handleEnvVarsSubmit}
          initialEnvVars={getInitialEnvVars()}
          serverName={pendingServerInstall?.name}
          isLoading={isInstalling}
        />
      </ServersActionsContext.Provider>
    </ServersStateContext.Provider>
  );
}

// Custom hooks with selectors to prevent unnecessary re-renders
export function useServersState() {
  const context = useContext(ServersStateContext);
  if (context === undefined) {
    throw new Error('useServersState must be used within a ServersProvider');
  }
  return context;
}

export function useServersActions() {
  const context = useContext(ServersActionsContext);
  if (context === undefined) {
    throw new Error('useServersActions must be used within a ServersProvider');
  }
  return context;
}

// Legacy hook for backward compatibility
export function useServers() {
  const state = useServersState();
  const actions = useServersActions();
  return { ...state, ...actions };
}

// Selector hooks for specific data
export function useServersList() {
  const { servers } = useServersState();
  return servers || []; // Ensure we always return an array
}

export function useServerByName(serverId: string) {
  const { servers } = useServersState();
  return servers.find(server => server.id === serverId);
}

// Individual action hooks for convenience
export const useAddServer = () => {
  const { addServer } = useServersActions();
  return addServer;
};

export const useUpdateServer = () => {
  const { updateServer } = useServersActions();
  return updateServer;
};

export const useRemoveServer = () => {
  const { removeServer } = useServersActions();
  return removeServer;
};

export function useServerStats() {
  const { serverStats } = useServersState();
  return serverStats;
}

export function useServersLoading() {
  const { loading } = useServersState();
  return loading;
}

export function useServersError() {
  const { error, hasError } = useServersState();
  return { error, hasError };
}

// MCP Registry Server selector hooks
export function useMCPRegistryServersList() {
  const { mcpregistryservers } = useServersState();
  return mcpregistryservers || [];
}

export function useMCPRegistryServerStats() {
  const { mcpregistryserverStats } = useServersState();
  return mcpregistryserverStats;
}

export function useMCPRegistryServersLoading() {
  const { mcpregistryLoading } = useServersState();
  return mcpregistryLoading;
}

export function useMCPRegistryServerById(serverId: string) {
  const { mcpregistryservers } = useServersState();
  return mcpregistryservers.find(server => server.id === serverId);
}

// Action hooks for MCP registry servers
export const useRefreshMCPRegistryServers = () => {
  const { refreshMCPRegistryServers } = useServersActions();
  return refreshMCPRegistryServers;
};

export const useInstallMCPRegistryServer = () => {
  const { installMCPRegistryServer } = useServersActions();
  return installMCPRegistryServer;
}; 