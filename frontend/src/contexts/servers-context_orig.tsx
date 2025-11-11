
import React, { createContext, useContext, useState, useCallback, useEffect, ReactNode, useRef, useMemo } from 'react';
import { newApi, MCPServer } from '@/lib/new-api';
import { useAuth } from './auth-context';
import { parseEnvVars } from '@/lib/app-utils';

interface ServerStats {
  total: number;
  connected: number;
  disconnected: number;
  auth_required: number;
  errors: number;
}

interface ServersState {
  servers: MCPServer[];
  serverStats: ServerStats;
  loading: boolean;
  error: string | null;
  lastUpdated: number | null;
  initialized: boolean;
  hasError: boolean;
}

interface ServersContextType extends ServersState {
  refreshServers: () => Promise<void>;
  connectServer: (serverId: string) => Promise<void>;
  authorizeServer: (serverId: string) => Promise<void>;
  addServer: (serverTemplate: any) => Promise<void>;
  clearError: () => void;
  refreshServerCapabilities: (serverId: string) => Promise<void>;
  refreshAllCapabilities: () => Promise<void>;
  refreshServerStatus: (serverId: string) => Promise<void>;
  refreshAllStatus: () => Promise<void>;
  clearServerAuth: (serverId: string) => Promise<void>;
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
    serverStats: {
      total: 0,
      connected: 0,
      disconnected: 0,
      auth_required: 0,
      errors: 0
    },
    loading: true, // Start with loading true to prevent undefined access
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
  
      const result = await newApi.discoverMCPServerCapabilities(serverId, accessToken);
        
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
            if (server.server_id === serverId) {
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
      const promises = state.servers.map(server => refreshServerCapabilities(server.server_id));
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
  
      const result = await newApi.getServerStatus(serverId, accessToken);
        
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
            if (server.server_id === serverId) {
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
      const promises = state.servers.map(server => refreshServerStatus(server.server_id));
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
  
      const result = await newApi.connectMCPServer(serverId, accessToken);
        
      if (result.success) {
        // Update server status to connected
        setState(prevState => {
          const updatedServers = prevState.servers.map(server => {
            if (server.server_id === serverId) {
              return {
                ...server,
                status: 'connected' as const,
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

  const authorizeServer = useCallback(async (serverId: string) => {
    try {
      // Get access token
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }

      // Call API directly to get authorization URL
      const result = await newApi.initiateMCPServerAuth(serverId, accessToken);
      
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

  const addServer = useCallback(async (serverTemplate: any) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }
  
      const result = await newApi.installMCPServer(serverTemplate, accessToken);
        
      if (result.success && result.server) {
        // Validate that result.server is actually a server object and not the entire response
        if (typeof result.server !== 'object' || !result.server.server_id) {
          console.error('Invalid server object received:', result.server);
          setState(prevState => ({
            ...prevState,
            error: 'Invalid server object received from API',
            hasError: true
          }));
          return;
        }
        
        // Transform the server object to match the MCPServer interface
        const newServer: MCPServer = {
          server_id: result.server.server_id , // Use server_id if available, fallback to name
          name: result.server.name,
          description: result.server.description,
          status: result.server.status || 'disconnected',
          transport_type: result.server.transport_type,
          url: result.server.url,
          command: result.server.command,
          last_connected: result.server.last_connected,
          last_error: result.server.last_error,
          capabilities: result.server.capabilities,
          auto_connect: result.server.auto_connect,
          enabled: result.server.enabled,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          // Initialize empty arrays for capabilities
          tools_list: result.server.tools || [],
          resources_list: result.server.resources || [],
          prompts_list: result.server.prompts || [],
          resource_templates_list: [],
          tool_details: [],
          resource_details: [],
          resource_template_details: [],
          prompt_details: []
        };
        
        console.log('🔧 Adding new server to state:', newServer);
        
        setState(prevState => {
          console.log('🔧 Current servers state:', prevState.servers);
          
          // Check if server already exists to prevent duplicates
          const serverExists = prevState.servers.some(s => s.server_id === newServer.server_id);
          if (serverExists) {
            console.log('🔧 Server already exists, updating instead of adding:', newServer.server_id);
            const updatedServers = prevState.servers.map(s => 
              s.server_id === newServer.server_id ? newServer : s
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
        
        // Automatically try to connect and discover capabilities
        try {
          console.log('🔧 Auto-connecting to new server:', newServer.server_id);
          
          const accessToken = localStorage.getItem('access_token');
          if (!accessToken) {
            console.log('🔧 No access token available for auto-connection');
            return;
          }
          
          // Step 1: Connect to server
          console.log('🔧 Calling connect API...');
          const connectResult = await newApi.connectMCPServer(newServer.server_id, accessToken);
          
          if (connectResult.success) {
            console.log('🔧 Connect API successful, getting server status...');
            
            // Step 2: Get current server status
            const statusResult = await newApi.getServerStatus(newServer.server_id, accessToken);
            
            if (statusResult.success && statusResult.data) {
              const statusData = statusResult.data.status || statusResult.data;
              const currentStatus = typeof statusData === 'object' && statusData.status 
                ? statusData.status 
                : (typeof statusData === 'string' ? statusData : 'disconnected');
              
              console.log('🔧 Current server status:', currentStatus);
              
              // Step 3: If connected, discover capabilities
              let capabilities = null;
              if (currentStatus === 'connected') {
                console.log('🔧 Server connected, discovering capabilities...');
                try {
                  const capabilitiesResult = await newApi.discoverMCPServerCapabilities(newServer.server_id, accessToken);
                  if (capabilitiesResult.success && capabilitiesResult.data) {
                    capabilities = capabilitiesResult.data.capabilities || capabilitiesResult.data;
                    console.log('🔧 Capabilities discovered:', capabilities);
                  }
                } catch (capError) {
                  console.log('🔧 Capabilities discovery failed:', capError);
                }
              }
              
              // Step 4: Update state once with all information
              setState(prevState => {
                const updatedServers = prevState.servers.map(server => {
                  if (server.server_id === newServer.server_id) {
                    const updatedServer = {
                      ...server,
                      status: currentStatus as 'connected' | 'disconnected' | 'auth_required' | 'error',
                      last_status_update: new Date().toISOString(),
                      capabilities: capabilities,
                      // Update capabilities fields if available
                      tools_list: capabilities?.tools_list || capabilities?.tools || [],
                      resources_list: capabilities?.resources_list || capabilities?.resources || [],
                      prompts_list: capabilities?.prompts_list || capabilities?.prompts || [],
                      tools_count: capabilities?.tools_count || 0,
                      resources_count: capabilities?.resources_count || 0,
                      prompts_count: capabilities?.prompts_count || 0,
                      tool_details: capabilities?.tool_details || [],
                      resource_details: capabilities?.resource_details || [],
                      resource_template_details: capabilities?.resource_template_details || [],
                      prompt_details: capabilities?.prompt_details || [],
                      last_capabilities_update: capabilities ? new Date().toISOString() : null
                    };
                    
                    console.log('🔧 Updated server with status and capabilities:', updatedServer);
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
              console.log('🔧 Failed to get server status:', statusResult.error);
            }
          } else {
            console.log('🔧 Failed to connect to server:', connectResult.error);
          }
          
        } catch (error) {
          console.log('🔧 Auto-connection failed for server:', newServer.server_id, error);
          // Don't fail the add operation if auto-connection fails
        }
      } else {
        console.error('Failed to add server:', result.error);
        setState(prevState => ({
          ...prevState,
          error: `Failed to add server: ${result.error}`,
          hasError: true
        }));
      }
    } catch (error) {
      console.error('Error adding server:', error);
      setState(prevState => ({
        ...prevState,
        error: `Error adding server: ${error instanceof Error ? error.message : 'Unknown error'}`,
        hasError: true
      }));
    }
  }, [recalculateStats, connectServer, refreshServerStatus, refreshServerCapabilities, state.servers]);

  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null, hasError: false }));
  }, []);

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
      const result = await newApi.listMCPServers(accessToken);
      
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

        // Use stats from backend response if available, otherwise recalculate
        const serverStats = {
          total: result.total || processedServers.length,
          connected: result.connected || 0,
          disconnected: result.disconnected || 0,
          auth_required: result.auth_required || 0,
          errors: result.errors || 0
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

  // Initialize servers on mount and when auth changes
  useEffect(() => {
    if (isAuthenticated && user && !state.initialized) {
      refreshServers();
    }
  }, [isAuthenticated, user, state.initialized, refreshServers]);

  const clearServerAuth = useCallback(async (serverId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }

      const result = await newApi.clearMCPServerAuth(serverId, accessToken);
      
      if (result.success) {
        // Update server status to disconnected and clear auth info
        setState(prevState => {
          const updatedServers = prevState.servers.map(server => {
            if (server.server_id === serverId) {
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
    connectServer,
    authorizeServer,
    addServer,
    clearError,
    refreshServerCapabilities,
    refreshAllCapabilities,
    refreshServerStatus,
    refreshAllStatus,
    clearServerAuth,
  }), [
    refreshServers,
    connectServer,
    authorizeServer,
    addServer,
    clearError,
    refreshServerCapabilities,
    refreshAllCapabilities,
    refreshServerStatus,
    refreshAllStatus,
    clearServerAuth,
  ]);

  return (
    <ServersStateContext.Provider value={state}>
      <ServersActionsContext.Provider value={actions}>
        {children}
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
  return servers.find(server => server.server_id === serverId);
}

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