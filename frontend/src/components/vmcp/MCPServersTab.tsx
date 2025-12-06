// components/MCPServersTab.tsx

import { useState, useMemo, useEffect } from 'react';
import { useRouter } from '@/hooks/useRouter';
import { CheckCircle, Server, Plus, Trash2, Globe } from 'lucide-react';
import {PromptIcon, ToolIcon, McpIcon, VmcpIcon, ResourceIcon} from '@/lib/vmcp';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

import { FaviconIcon } from '@/components/ui/favicon-icon';
import { VMCPConfig } from '@/types/vmcp';
import { getStatusDisplay } from '@/lib/vmcp';
import { cn } from '@/lib/utils';

import {
  useServersList,
  useServerStats,
  useServersLoading,
  useServersError,
  useServersActions
} from '@/contexts/servers-context';
import { useVMCPActions, useVMCPList, useVMCPState } from '@/contexts/vmcp-context';
import { useToast } from '@/hooks/use-toast';
// import { newApi } from '@/lib/new-api';
import { apiClient } from '@/api/client';
import type { RegistryServerInfo, McpServerInfo } from '@/api/generated/types.gen';
import { MCPServersDiscovery } from '@/components/discover/MCPServersDiscovery';
import { Modal } from '@/components/ui/modal';
import { ServerDetailsModal } from '@/components/vmcp/ServerDetailsModal';
import { CustomServerModal, type CustomServerFormData } from '@/components/vmcp/CustomServerModal';

// Validation functions for MCP server names
const validateServerName = (name: string): { isValid: boolean; errors: string[] } => {
  const errors: string[] = [];
  
  if (!name || name.trim() === '') {
    errors.push('Server name cannot be empty');
    return { isValid: false, errors };
  }
  
  const trimmedName = name.trim();
  
  // Check if name starts with a number/digit
  if (/^\d/.test(trimmedName)) {
    errors.push('Server name cannot start with a number');
  }
  
  // Check if name contains spaces
  if (/\s/.test(trimmedName)) {
    errors.push('Server name cannot contain spaces');
  }
  
  // Check if name contains special characters other than underscore
  if (!/^[a-zA-Z0-9_]+$/.test(trimmedName)) {
    errors.push('Server name can only contain letters, numbers, and underscores');
  }
  
  // Check if name is too short or too long
  if (trimmedName.length < 2) {
    errors.push('Server name must be at least 2 characters long');
  }
  
  if (trimmedName.length > 50) {
    errors.push('Server name cannot exceed 50 characters');
  }
  
  return {
    isValid: errors.length === 0,
    errors
  };
};

interface MCPServersTabProps {
  vmcpConfig: VMCPConfig;
  setVmcpConfig: (config: VMCPConfig | ((prev: VMCPConfig) => VMCPConfig)) => void;
  servers: any[];
  isRemoteVMCP?: boolean;
  loadVMCPConfig?: () => Promise<void>;
}

export default function MCPServersTab({
  vmcpConfig,
  setVmcpConfig,
  servers,
  isRemoteVMCP = false,
  loadVMCPConfig,
}: MCPServersTabProps) {
  const router = useRouter();
  const { success, error: toastError } = useToast();
  const { connectServer, refreshServerStatus, refreshServerCapabilities, addServer, updateServer, removeServer, refreshServers } = useServersActions();
  const { refreshVMCPData } = useVMCPActions();
  const { vmcps } = useVMCPState();
  const [activeTab, setActiveTab] = useState<'myvmcp' | 'public'>('myvmcp');
  const [serverSearchQuery, setServerSearchQuery] = useState('');
  const [selectedModalServerId, setSelectedModalServerId] = useState<string | null>(null);
  const [modalLoading, setModalLoading] = useState<{refresh?: boolean, connect?: boolean, auth?: boolean}>({});
  const [showCustomServerModal, setShowCustomServerModal] = useState(false);
  const [customServerForm, setCustomServerForm] = useState<CustomServerFormData>({
    name: '',
    description: '',
    transport: 'http',
    command: '',
    url: '',
    args: '',
    env: [],
    headers: [],
    auto_connect: true,
    enabled: true
  });
  const [customServerLoading, setCustomServerLoading] = useState(false);
  const [showDiscoveryModal, setShowDiscoveryModal] = useState(false);


  // Add a server to vMCP using the new backend endpoint
  const addServerToVMCP = async (serverData: any) => {
    console.log('🔧 Adding server to vMCP:', serverData);
    
    // Validate server name before proceeding
    const validation = validateServerName(serverData.name);
    if (!validation.isValid) {
      const errorMessage = `Invalid server name: ${validation.errors.join(', ')}`;
      toastError(errorMessage);
      return;
    }
    
    // Check if server is already added to vMCP
    const isAlreadyAdded = vmcpConfig.vmcp_config.selected_servers?.some(
      s => s.name === serverData.name || s.server_id === serverData.server_id
    );
    
    if (isAlreadyAdded) {
      toastError(`${serverData.name} is already added to this vMCP`);
      return;
    }
    
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        toastError('Please log in to add servers');
        return;
      }

      // Call the new backend endpoint
      if (!vmcpConfig.id) {
        toastError('vMCP ID is required');
        return;
      }
      
      const result = await apiClient.addServerToVMCP(vmcpConfig.id, serverData, accessToken);
      
      if (result.success && result.data) {
        console.log('🔧 result.data:', result.data);
        // Update the entire vMCP config with the response
        setVmcpConfig(result.data.vmcp_config);
        
         // Add server to server context if it's a new server
         if (result.data.server) {
           console.log('🔧 Server data from API:', result.data.server);
           
           // Generate a server_id if not provided
           const serverId = result.data.server.server_id
           console.log('🔧 received server_id:', serverId);
           
           const serverForContext = {
             name: result.data.server.name,
             server_id: serverId,
             transport_type: result.data.server.transport_type,
             description: result.data.server.description || '',
             url: result.data.server.url,
             status: result.data.server.status,
             last_connected: null,
             last_error: null,
             capabilities: result.data.server.capabilities || {},
             tools: result.data.server.tool_details || [],
             resources: result.data.server.resource_details || [],
             prompts: result.data.server.prompt_details || [],
             tool_details: result.data.server.tool_details || [],
             resource_details: result.data.server.resource_details || [],
             resource_template_details: [],
             prompt_details: result.data.server.prompt_details || [],
             auto_connect: result.data.server.auto_connect,
             enabled: result.data.server.enabled
           };
           
           // Add to server context using the servers pattern
           await addServer(serverForContext);
           
           // Force a refresh of the servers context to ensure the server is visible
           // This ensures the server appears in the UI immediately
          //  setTimeout(async () => {
          //    try {
          //      await refreshServers();
          //    } catch (error) {
          //      console.error('Error refreshing servers after adding to vMCP:', error);
          //    }
          //  }, 100); // Small delay to ensure the server is persisted
         }
        
        success(`Added ${serverData.name} to vMCP successfully!`);
        
        // No need to refresh vMCP data - the backend already returned the updated config
        
      } else {
        throw new Error(result.error || 'Failed to add server to vMCP');
      }
      
    } catch (error) {
      console.error('Failed to add server to vMCP:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to add server to vMCP';
      toastError(errorMessage);
    }
  };

  // Add custom server directly to vMCP
  const addCustomServerToVMCP = async () => {
    console.log('🔧 Adding custom server to vMCP:', customServerForm);
    
    // Validate server name before proceeding
    const validation = validateServerName(customServerForm.name);
    if (!validation.isValid) {
      const errorMessage = `Invalid server name: ${validation.errors.join(', ')}`;
      toastError(errorMessage);
      return;
    }
    
    // Check if server is already added to vMCP
    const isAlreadyAdded = vmcpConfig.vmcp_config.selected_servers?.some(
      s => s.name === customServerForm.name
    );
    
    if (isAlreadyAdded) {
      toastError(`${customServerForm.name} is already added to this vMCP`);
      return;
    }
    
    setCustomServerLoading(true);
    
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        toastError('Please log in to add servers');
        return;
      }

      // Call the new backend endpoint
      if (!vmcpConfig.id) {
        toastError('vMCP ID is required');
        return;
      }
      
      // Convert key-value arrays to objects
      const envObject = customServerForm.env.reduce((acc, pair) => {
        if (pair.key.trim()) {
          acc[pair.key.trim()] = pair.value.trim();
        }
        return acc;
      }, {} as Record<string, string>);

      const headersObject = customServerForm.headers.reduce((acc, pair) => {
        if (pair.key.trim()) {
          acc[pair.key.trim()] = pair.value.trim();
        }
        return acc;
      }, {} as Record<string, string>);

      // Prepare the server data for the API
      const serverData: RegistryServerInfo = {
        name: customServerForm.name,
        transport: customServerForm.transport,
        description: customServerForm.description,
        command: customServerForm.transport === 'stdio' ? customServerForm.command : undefined,
        args: customServerForm.args ? customServerForm.args.split(',').map(arg => arg.trim()) : undefined,
        env: Object.keys(envObject).length > 0 ? envObject : undefined,
        url: (customServerForm.transport === 'http' || customServerForm.transport === 'sse') ? customServerForm.url : undefined,
        headers: Object.keys(headersObject).length > 0 ? headersObject : undefined,      
      };
      
      const result = await apiClient.addServerToVMCP(vmcpConfig.id, serverData, accessToken);
      
      if (result.success && result.data) {
        console.log('🔧 result.data:', result.data);
        // Update the entire vMCP config with the response
        setVmcpConfig(result.data.vmcp_config);
        
        // Add server to server context if it's a new server
        if (result.data.server) {
          console.log('🔧 Server data from API:', result.data.server);
          
          const serverId = result.data.server.server_id;
          console.log('🔧 received server_id:', serverId);
          
          const serverForContext = {
            name: result.data.server.name,
            server_id: serverId,
            transport_type: result.data.server.transport_type,
            description: result.data.server.description || '',
            url: result.data.server.url,
            status: result.data.server.status,
            last_connected: null,
            last_error: null,
            capabilities: result.data.server.capabilities || {},
            tools: result.data.server.tool_details || [],
            resources: result.data.server.resource_details || [],
            prompts: result.data.server.prompt_details || [],
            tool_details: result.data.server.tool_details || [],
            resource_details: result.data.server.resource_details || [],
            resource_template_details: [],
            prompt_details: result.data.server.prompt_details || [],
            auto_connect: result.data.server.auto_connect,
            enabled: result.data.server.enabled
          };
          
          // Add to server context using the servers pattern
          await addServer(serverForContext);
        }
        
        success(`Added ${customServerForm.name} to vMCP successfully!`);
        
        // Reset form and close modal
        setCustomServerForm({
          name: '',
          description: '',
          transport: 'http',
          command: '',
          url: '',
          args: '',
          env: [],
          headers: [],
          auto_connect: true,
          enabled: true
        });
        setShowCustomServerModal(false);
        
      } else {
        throw new Error(result.error || 'Failed to add server to vMCP');
      }
      
    } catch (error) {
      console.error('Failed to add custom server to vMCP:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to add custom server to vMCP';
      toastError(errorMessage);
    } finally {
      setCustomServerLoading(false);
    }
  };

  // Remove a server from vMCP
  const removeServerFromVMCP = async (serverId: string) => {
    console.log('🔧 Removing server from vMCP:', serverId);
    
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        toastError('Please log in to remove servers');
        return;
      }

      // Call the backend endpoint
      if (!vmcpConfig.id) {
        toastError('vMCP ID is required');
        return;
      }
      
      const result = await apiClient.removeServerFromVMCP(vmcpConfig.id, serverId, accessToken);
      
      if (result.success && result.data) {
        // Update the entire vMCP config with the response
        setVmcpConfig(result.data.vmcp_config);
        
        // Handle server context updates based on response
        if (result.data.server === null) {
          // Server's vMCP list is empty, remove from server context
          console.log('🔧 Server has no vMCPs, removing from context:', serverId);
          await removeServer(serverId);
        } else if (result.data.server) {
          // Server still has vMCPs, update the server context
          console.log('🔧 Server still has vMCPs, updating context:', result.data.server);
          await updateServer(result.data.server);
        }
        
        success(`Removed server from vMCP successfully!`);
        
      } else {
        throw new Error(result.error || 'Failed to remove server from vMCP');
      }
      
    } catch (error) {
      console.error('Failed to remove server from vMCP:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to remove server from vMCP';
      toastError(errorMessage);
    }
  };

  // Handle modal server actions
  const handleModalRefresh = async () => {
    if (!selectedModalServerId) return;
    
    setModalLoading(prev => ({ ...prev, refresh: true }));
    
    try {
      // Call the context function to connect (which does both status and capabilities refresh)
      await connectServer(selectedModalServerId);
      
      // Refresh both server and vMCP contexts
      await Promise.all([
        refreshServers(),
        refreshVMCPData()
      ]);
      
      // Also reload the VMCP config to get the latest server data
      if (loadVMCPConfig) {
        await loadVMCPConfig();
      }
      
      success('Server refreshed successfully');
    } catch (error) {
      console.error('Error refreshing server:', error);
      toastError('Failed to refresh server');
    } finally {
      setModalLoading(prev => ({ ...prev, refresh: false }));
    }
  };

  const handleModalConnect = async () => {
    if (!selectedModalServerId) return;
    
    setModalLoading(prev => ({ ...prev, connect: true }));
    
    try {
      // Call the context function to connect
      await connectServer(selectedModalServerId);
      success(`Successfully connected to ${selectedModalServerId}`);
      
      // Update the vMCP config to reflect the new connection status
      setVmcpConfig(prev => ({
        ...prev,
        vmcp_config: {
          ...prev.vmcp_config,
          selected_servers: prev.vmcp_config.selected_servers.map(server => 
            server.server_id === selectedModalServerId 
              ? { ...server, status: 'connected' }
              : server
          )
        }
      }));
      
      // Refresh the server data after connection
      await handleModalRefresh();
      
    } catch (err) {
      console.error('Error connecting to server:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to connect to server';
      toastError(errorMessage);
    } finally {
      setModalLoading(prev => ({ ...prev, connect: false }));
    }
  };

  const handleModalAuth = async () => {
    if (!selectedModalServerId) return;
    
    setModalLoading(prev => ({ ...prev, auth: true }));
    
    try {
      // Get access token
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }

      // Call API directly to get authorization URL
      const result = await apiClient.initiateMCPServerAuth(selectedModalServerId, accessToken);
      
      if (result.success && result.data?.authorization_url) {
        // Open the authorization URL directly in a new tab
        window.open(result.data.authorization_url, '_blank', 'noopener,noreferrer');
        
        // Show success message or handle completion
        // You might want to add a callback mechanism here to check when auth is complete
        console.log('Authorization URL opened:', result.data.authorization_url);
      } else {
        throw new Error(result.error || 'Failed to get authorization URL');
      }
      
    } catch (err) {
      console.error('Error opening authorization for server:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to open authorization';
      toastError(errorMessage);
    } finally {
      setModalLoading(prev => ({ ...prev, auth: false }));
    }
  };

  const openServerModal = (server: any) => {
    setSelectedModalServerId(server.server_id);
  };

  const closeServerModal = () => {
    setSelectedModalServerId(null);
    setModalLoading({});
  };

  // Server Card Component
  const renderServerCard = (server: McpServerInfo, isUsedInOtherVmcps: boolean) => {
    const isSelected = vmcpConfig.vmcp_config.selected_servers?.some(s => s.server_id === server.id);
    const status = getStatusDisplay(server);
    const StatusIcon = status.icon;
    
    return (
      <div key={server.id} className={cn(
        "group relative p-4 rounded-lg border transition-all duration-200",
        "border-border/60 hover:border-border/80"
      )}>
        {/* Add/Remove Button */}
        <Button
          size="sm"
          variant="ghost"
          className={cn(
            "absolute top-2 right-2 h-8 w-8 p-0 rounded-full transition-all duration-200",
            isSelected 
              ? "bg-primary/20 hover:bg-primary/30 text-primary" 
              : "bg-muted/50 hover:bg-muted/70 text-muted-foreground hover:text-foreground"
          )}
          onClick={async () => {
            if (isSelected) {
              // Remove server
              setVmcpConfig(prev => ({
                ...prev,
                vmcp_config: {
                  ...prev.vmcp_config,
                  selected_servers: prev.vmcp_config.selected_servers.filter(s => s.server_id !== server.id),
                  selected_tools: Object.fromEntries(
                    Object.entries(prev.vmcp_config.selected_tools).filter(([key]) => key !== server.id)
                  ),
                  selected_prompts: Object.fromEntries(
                    Object.entries(prev.vmcp_config.selected_prompts).filter(([key]) => key !== server.id)
                  ),
                  selected_resources: Object.fromEntries(
                    Object.entries(prev.vmcp_config.selected_resources).filter(([key]) => key !== server.id)
                  )
                }
              }));
              
            } else {
              let serverData: RegistryServerInfo;
              // Prepare server data to add for vMCP
              if (server.transport_type === 'stdio') {
                serverData = {                
                  id: server.id, 
                  name: server.name,
                  transport: server.transport_type,
                  description: server.description,
                  command: server.command,
                  args: server.args,
                  env: server.env,
                };
              } else {
                serverData = {                
                  id: server.id,
                  name: server.name,
                  transport: server.transport_type,
                  description: server.description,
                  url: server.url,
                };
              }
              // Add server to vMCP
              await addServerToVMCP(serverData);
            }
          }}
        >
          {isSelected ? (
            <CheckCircle className="h-4 w-4" />
          ) : (
            <Plus className="h-4 w-4" />
          )}
        </Button>

        {/* Server Info */}
        <div>
          <div className="flex items-start gap-2 mb-3">
          <FaviconIcon
              url={server.url || undefined}
              className="h-8 w-8"
              size={32}
          />
            <div className="flex-1 min-w-0">
              <h4 className="font-medium text-foreground text-sm mb-1 truncate font-mono">{server.name}</h4>
              {/* <div className="flex items-center gap-2 mb-1">
                <Badge
                  variant={server.status === 'connected' ? 'default' :
                    server.status === 'auth_required' ? 'destructive' :
                    server.status === 'error' ? 'destructive' : 'outline'}
                  className="text-xs"
                >
                  <StatusIcon className="h-3 w-3 mr-1" />
                  {status.label}
                </Badge>
                {isUsedInOtherVmcps && (
                  <Badge variant="secondary" className="text-xs text-amber-600">
                    Used in Other vMCPs
                  </Badge>
                )} 
              </div> */}
              {server.description && (
                <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">{server.description}</p>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Selected Servers Summary */}
      {vmcpConfig.vmcp_config.selected_servers?.length > 0 && (
        <div>
          <h2 className="text-xl font-semibold text-foreground mb-4 flex items-center gap-2">
            <CheckCircle className="h-5 w-5 text-primary" />
            MCP Servers added to vMCP ({vmcpConfig.vmcp_config.selected_servers?.length || 0})
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {vmcpConfig.vmcp_config.selected_servers?.map((server, index) => {
              // Use the server data directly from vMCP config since it has the complete data
              // Fall back to servers context only for status if needed
              const fullServer = server; // vMCP config already has the full server data
              const status = getStatusDisplay(server);
              const StatusIcon = status.icon;

              return (
                <div key={server.server_id} className="group relative p-4 rounded-lg border transition-all duration-200 shadow-sm cursor-pointer hover:shadow-md hover:border-primary/50" onClick={() => openServerModal(server)}>
                  {/* Remove Button */}
                  <Button
                    size="sm"
                    variant="ghost"
                    className="absolute top-2 right-2 h-8 w-8 p-0 rounded-full transition-all duration-200 bg-destructive/20 hover:bg-destructive/30 text-destructive opacity-0 group-hover:opacity-100 z-10"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeServerFromVMCP(server.server_id);
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>

                  {/* Server Info */}
                  <div>
                    <div className="flex items-start gap-2 mb-3">
                      <FaviconIcon
                        url={server.url}
                        faviconUrl={server.favicon_url}
                        className="h-8 w-8"
                        size={32}
                      />
                      <div className="flex-1 min-w-0">
                        <h4 className="font-medium text-foreground text-sm mb-1 truncate font-mono">{server.name}</h4>
                        <div className="flex items-center gap-2 mb-1">
                          <Badge
                            variant={server.status === 'connected' ? 'default' :
                              server.status === 'auth_required' ? 'destructive' :
                              server.status === 'error' ? 'destructive' : 'outline'}
                            className="text-xs"
                          >
                            <StatusIcon className="h-3 w-3 mr-1" />
                            {status.label}
                          </Badge>
                        </div>
                        {server.description && (
                          <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">{server.description}</p>
                        )}
                      </div>
                    </div>
                    
                    {/* Server Stats */}
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <ToolIcon className="h-3 w-3" />
                        <span>{(server.tool_details?.length || 0)} tools</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <PromptIcon className="h-3 w-3" />
                        <span>{(server.prompt_details?.length || 0)} prompts</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <ResourceIcon className="h-3 w-3" />
                      <span>{(server.resource_details?.length || 0)} resources</span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Empty State for Selected Servers */}
      {vmcpConfig.vmcp_config.selected_servers?.length === 0 && (
        <div className="border-2 border-dashed border-border/60 rounded-lg p-8 text-center">
          <div className="flex flex-col items-center gap-4">
            <div className="h-16 w-16 rounded-full bg-muted/40 flex items-center justify-center">
              <Server className="h-8 w-8 text-muted-foreground" />
            </div>
            <div className="space-y-2">
              <h3 className="text-lg font-medium text-foreground">No MCP Servers Added</h3>
              <p className="text-muted-foreground max-w-md">
                {servers.length > 0 
                  ? "Add MCP servers from your current list of managed MCP servers to get started with vMCP configuration."
                  : "You haven't added any MCP servers to your account yet. Go to the MCP Servers tab to get started and explore available servers."
                }
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Server Discovery Section */}
      <div id="mcp-servers-section" className="mt-12 p-4 bg-muted/70 rounded-lg">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-foreground flex items-center gap-2">
            <Server className="h-5 w-5 text-primary" />
            Server Discovery
          </h2>
          <div className="flex items-center gap-2">
            <Button
              onClick={() => setShowDiscoveryModal(true)}
              variant="default"
              size="sm"
              className="flex items-center gap-2"
              disabled={isRemoteVMCP}
              title={isRemoteVMCP ? 'Server discovery disabled for remote vMCPs' : ''}
            >
              <Globe className="h-4 w-4" />
              Add MCP Connector
            </Button>
            <Button
              onClick={() => setShowCustomServerModal(true)}
              variant="outline"
              size="sm"
              className="flex items-center gap-2"
              disabled={isRemoteVMCP}
              title={isRemoteVMCP ? 'Adding custom servers disabled for remote vMCPs' : ''}
            >
              <Plus className="h-4 w-4" />
              Add Custom Server
            </Button>
          </div>
        </div>


        {/* Combined Server List */}
        <div className="space-y-6">
          {/* Servers from servers context (used in other vMCPs) */}
          {(() => {
            const serversFromContext = servers.filter(server => {
              // Filter out servers that are already added to this vMCP
              const isAlreadyInVMCP = vmcpConfig.vmcp_config.selected_servers?.some(
                selectedServer => selectedServer.server_id === server.server_id
              );
              return !isAlreadyInVMCP; // Only show servers not already in this vMCP
            });
            
            if (serversFromContext.length > 0) {
              return (
                <div>
                  <h3 className="text-foreground mb-4 flex items-center gap-2">
                    <CheckCircle className="h-4 w-4 text-amber-500" />
                    Your Connections
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                    {serversFromContext
                      .filter((server) => {
                        if (!serverSearchQuery.trim()) return true;
                        const query = serverSearchQuery.toLowerCase();
                        return (
                          server.name.toLowerCase().includes(query) ||
                          (server.description && server.description.toLowerCase().includes(query)) ||
                          (server.transport_type && server.transport_type.toLowerCase().includes(query))
                        );
                      })
                      .map((server) => renderServerCard(server, true))}
                  </div>
                </div>
              );
            }
            return null;
          })()}
         

        </div>
      </div>

      {/* Server Details Modal */}
      {selectedModalServerId && (() => {
        // First try to find the server in the vMCP configuration (it has the full server data)
        const vmcpServer = vmcpConfig.vmcp_config.selected_servers?.find(s => s.server_id === selectedModalServerId);

        // If not found in vMCP config, try to find it in the servers context
        const serverFromContext = servers.find(s => (s.server_id || s.id) === selectedModalServerId);
        
        const selectedModalServer = vmcpServer || serverFromContext;

        if (!selectedModalServer) return null;

        const serverForModal: McpServerInfo = {
          ...selectedModalServer,
          id: selectedModalServer.server_id || selectedModalServer.id,
        } as unknown as McpServerInfo;

        return (
          <ServerDetailsModal
            server={serverForModal}
            isOpen={true}
            onClose={closeServerModal}
            onRefresh={handleModalRefresh}
            onConnect={handleModalConnect}
            onAuth={handleModalAuth}
            isLoading={modalLoading}
          />
        );
      })()}

      {/* Custom Server Modal */}
      <CustomServerModal
        isOpen={showCustomServerModal}
        onClose={() => setShowCustomServerModal(false)}
        onSubmit={addCustomServerToVMCP}
        formData={customServerForm}
        setFormData={setCustomServerForm}
        isLoading={customServerLoading}
      />

      {/* Discovery Modal */}
      <Modal
        isOpen={showDiscoveryModal}
        onClose={() => setShowDiscoveryModal(false)}
        title="Extend your vMCP"
        size="xl"
      >
        <div className="space-y-4">
          <div className="text-left py-2 text-muted-foreground">
            <p className="text-sm">Browse available MCP servers and add them to your vMCP</p>
          </div>
          
          <MCPServersDiscovery 
            onAddServer={addServerToVMCP}
            buttonText="Add to vMCP"
            searchPlaceholder="Search MCP servers to add..."
            className="[&_.grid]:grid-cols-1 [&_.grid]:md:grid-cols-2 [&_.grid]:lg:grid-cols-2 [&_.grid]:xl:grid-cols-3"
          />
        </div>
      </Modal>
    </div>
  );
}