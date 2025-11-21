// components/MCPServersTab.tsx

import { useState, useMemo, useEffect } from 'react';
import { useRouter } from '@/hooks/useRouter';
import { CheckCircle, Server, X, Plus, Trash2, RefreshCw, Wifi, WifiOff, Lock, LinkIcon, AlertTriangle, Activity, Terminal, Globe } from 'lucide-react';
import {PromptIcon, ToolIcon, McpIcon, VmcpIcon, ResourceIcon} from '@/lib/vmcp';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { FaviconIcon } from '@/components/ui/favicon-icon';
import { KeyValueInput } from '@/components/ui/key-value-input';
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
import { MCPServersDiscovery } from '@/components/discover/MCPServersDiscovery';
import { Modal } from '@/components/ui/modal';

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
  const [customServerForm, setCustomServerForm] = useState({
    name: '',
    description: '',
    transport: 'http' as 'stdio' | 'http' | 'sse',
    command: '',
    url: '',
    args: '',
    env: [] as Array<{key: string, value: string}>,
    headers: [] as Array<{key: string, value: string}>,
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
      const serverData = {
        name: customServerForm.name,
        mode: customServerForm.transport,
        description: customServerForm.description,
        command: customServerForm.transport === 'stdio' ? customServerForm.command : undefined,
        args: customServerForm.args ? customServerForm.args.split(',').map(arg => arg.trim()) : undefined,
        env: Object.keys(envObject).length > 0 ? envObject : undefined,
        url: (customServerForm.transport === 'http' || customServerForm.transport === 'sse') ? customServerForm.url : undefined,
        headers: Object.keys(headersObject).length > 0 ? headersObject : undefined,
        auto_connect: customServerForm.auto_connect,
        enabled: customServerForm.enabled
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

  // Helper function to get status display (similar to servers page)
  const getModalStatusDisplay = (server: any) => {
    const currentStatus = server?.status;
    const isLoading = modalLoading.refresh || false;
    
    if (isLoading) {
      return {
        label: 'Fetching...',
        color: 'bg-blue-500/20 border-blue-500/30 text-blue-400',
        icon: Activity,
        bgColor: 'bg-blue-500/10'
      };
    }
    
    switch (currentStatus) {
      case 'connected':
        return {
          label: 'Connected',
          color: 'bg-green-500/20 border-green-500/30 text-green-400',
          icon: CheckCircle,
          bgColor: 'bg-green-500/10'
        };
      case 'auth_required':
        return {
          label: 'Auth Required',
          color: 'bg-amber-500/20 border-amber-500/30 text-amber-400',
          icon: Lock,
          bgColor: 'bg-amber-500/10'
        };
      case 'error':
        return {
          label: 'Error',
          color: 'bg-red-500/20 border-red-500/30 text-red-400',
          icon: AlertTriangle,
          bgColor: 'bg-red-500/10'
        };
      default:
        return {
          label: 'Disconnected',
          color: 'bg-gray-500/20 border-gray-500/30 text-gray-400',
          icon: WifiOff,
          bgColor: 'bg-gray-500/10'
        };
    }
  };

  // Helper function to get transport icon
  const getTransportIcon = (transport: string) => {
    switch (transport) {
      case 'stdio':
        return Terminal;
      case 'http':
        return Globe;
      case 'sse':
        return Wifi;
      default:
        return Server;
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
  const renderServerCard = (server: any, isUsedInOtherVmcps: boolean) => {
    const isSelected = vmcpConfig.vmcp_config.selected_servers?.some(s => s.server_id === server.server_id);
    const status = getStatusDisplay(server);
    const StatusIcon = status.icon;
    
    return (
      <div key={server.server_id} className={cn(
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
                  selected_servers: prev.vmcp_config.selected_servers.filter(s => s.server_id !== server.server_id),
                  selected_tools: Object.fromEntries(
                    Object.entries(prev.vmcp_config.selected_tools).filter(([key]) => key !== server.server_id)
                  ),
                  selected_prompts: Object.fromEntries(
                    Object.entries(prev.vmcp_config.selected_prompts).filter(([key]) => key !== server.server_id)
                  ),
                  selected_resources: Object.fromEntries(
                    Object.entries(prev.vmcp_config.selected_resources).filter(([key]) => key !== server.server_id)
                  )
                }
              }));
              
            } else {
              // Add server using the new backend endpoint
              await addServerToVMCP(server);
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
              url={server.url}
              faviconUrl={server.favicon_url}
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
        let selectedModalServer = vmcpConfig.vmcp_config.selected_servers?.find(s => s.server_id === selectedModalServerId);
        
        // If not found in vMCP config, try to find it in the servers context
        if (!selectedModalServer) {
          selectedModalServer = servers.find(s => s.server_id === selectedModalServerId);
        }
        
        if (!selectedModalServer) return null;
        
        return (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-background border border-border rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-border">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center">
                  <Server className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-foreground font-mono">{selectedModalServer.name}</h2>
                  <div className="flex items-center gap-3 mt-1">
                    <p className="text-sm text-muted-foreground">Server Details</p>
                    {(() => {
                      const status = getModalStatusDisplay(selectedModalServer);
                      const StatusIcon = status.icon;
                      return (
                        <Badge
                          variant={selectedModalServer.status === 'connected' ? 'default' :
                            selectedModalServer.status === 'auth_required' ? 'secondary' :
                            selectedModalServer.status === 'error' ? 'destructive' : 'outline'}
                          className="text-xs"
                        >
                          <StatusIcon className="h-3 w-3 mr-1" />
                          {status.label}
                        </Badge>
                      );
                    })()}
                  </div>
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={closeServerModal}
                className="h-8 w-8 p-0"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            {/* Modal Content */}
            <div className="p-6 space-y-6">
              {/* Server Actions */}
              <div className="flex items-center justify-center">
                <div className="flex items-center gap-3">
                  {/* Connect/Authorize Button */}
                  {selectedModalServer.status === 'connected' ? (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={modalLoading.refresh || modalLoading.connect || modalLoading.auth}
                      className="flex items-center gap-2"
                    >
                      <WifiOff className="h-4 w-4" />
                      Disconnect
                    </Button>
                  ) : selectedModalServer.status === 'auth_required' ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleModalAuth}
                      disabled={modalLoading.refresh || modalLoading.connect || modalLoading.auth}
                      className="flex items-center gap-2"
                    >
                      <LinkIcon className="h-4 w-4" />
                      Authorize
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleModalConnect}
                      disabled={modalLoading.refresh || modalLoading.connect || modalLoading.auth}
                      className="flex items-center gap-2"
                    >
                      <Wifi className="h-4 w-4" />
                      Connect
                    </Button>
                  )}
                  
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleModalRefresh}
                    disabled={modalLoading.refresh || modalLoading.connect || modalLoading.auth}
                    className="flex items-center gap-2"
                  >
                    <RefreshCw className={`h-4 w-4 ${modalLoading.refresh ? 'animate-spin' : ''}`} />
                    Refresh
                  </Button>
                </div>
              </div>

              {/* Server Description */}
              {selectedModalServer.description && (
                <div>
                  <h3 className="text-sm font-medium text-foreground mb-2">Description</h3>
                  <p className="text-sm text-muted-foreground">{selectedModalServer.description}</p>
                </div>
              )}

              {/* Connection Details */}
              <div>
                <h3 className="text-sm font-medium text-foreground mb-2">Connection Details</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Transport:</span>
                    <Badge variant="outline" className="text-xs">
                      {(() => {
                        const TransportIcon = getTransportIcon(selectedModalServer.transport_type || 'unknown');
                        return (
                          <div className="flex items-center gap-1">
                            <TransportIcon className="h-3 w-3" />
                            {selectedModalServer.transport_type || 'unknown'}
                          </div>
                        );
                      })()}
                    </Badge>
                  </div>
                  {selectedModalServer.url && (
                    <div className="flex items-start gap-2">
                      <span className="text-sm text-muted-foreground shrink-0">URL:</span>
                      <code className="text-xs bg-muted px-2 py-1 rounded font-mono break-all">{selectedModalServer.url}</code>
                    </div>
                  )}
                </div>
              </div>

              {/* Capabilities Summary */}
              <div>
                <h3 className="text-sm font-medium text-foreground mb-3">Capabilities</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <Card>
                    <CardContent className="p-4 text-center">
                      <div className="flex items-center justify-center mb-2">
                        <ToolIcon className="h-8 w-8 text-primary" />
                      </div>
                      <div className="text-2xl font-bold text-foreground">
                        {(selectedModalServer.tool_details?.length || 0)}
                      </div>
                      <div className="text-sm text-muted-foreground">Tools Available</div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-4 text-center">
                      <div className="flex items-center justify-center mb-2">
                        <PromptIcon className="h-8 w-8 text-primary" />
                      </div>
                      <div className="text-2xl font-bold text-foreground">
                        {(selectedModalServer.prompt_details?.length || 0)}
                      </div>
                      <div className="text-sm text-muted-foreground">Prompts Available</div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-4 text-center">
                      <div className="flex items-center justify-center mb-2">
                        <ResourceIcon className="h-8 w-8 text-primary" />
                      </div>
                      <div className="text-2xl font-bold text-foreground">
                        {(selectedModalServer.resource_details?.length || 0)}
                      </div>
                      <div className="text-sm text-muted-foreground">Resources Available</div>
                    </CardContent>
                  </Card>
                </div>
              </div>

              {/* Last Connected Info */}
              {selectedModalServer.last_connected && (
                <div className="text-center py-4 border-t border-border">
                  <p className="text-sm text-muted-foreground">
                    Last connected: {new Date(selectedModalServer.last_connected).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' })} IST
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
        );
      })()}

      {/* Custom Server Modal */}
      {showCustomServerModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-background border border-border rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-border">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center">
                  <Plus className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-foreground">Add Custom Server</h2>
                  <p className="text-sm text-muted-foreground">Add a custom MCP server directly to this vMCP</p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowCustomServerModal(false)}
                className="h-8 w-8 p-0"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            {/* Modal Content */}
            <div className="p-6 space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {/* Server Name */}
                <div className="space-y-2 md:col-span-3">
                  <Label htmlFor="server-name">Server Name *</Label>
                  <Input
                    id="server-name"
                    value={customServerForm.name}
                    onChange={(e) => setCustomServerForm(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="my-custom-server"
                    className="font-mono"
                  />
                </div>

                {/* Transport Type */}
                <div className="space-y-2 md:col-span-1">
                  <Label htmlFor="transport">Transport Type *</Label>
                  <Select
                    value={customServerForm.transport}
                    onValueChange={(value: 'stdio' | 'http' | 'sse') => 
                      setCustomServerForm(prev => ({ ...prev, transport: value }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue/>
                    </SelectTrigger>
                    <SelectContent>
                      {<SelectItem value="stdio">
                        <div className="flex items-center gap-2">
                          <Terminal className="h-4 w-4" />
                          stdio
                        </div>
                      </SelectItem>}
                      <SelectItem value="http">
                        <div className="flex items-center gap-2">
                          <Globe className="h-4 w-4" />
                          http
                        </div>
                      </SelectItem>
                      <SelectItem value="sse">
                        <div className="flex items-center gap-2">
                          <Wifi className="h-4 w-4" />
                          sse
                        </div>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Description */}
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={customServerForm.description}
                  onChange={(e) => setCustomServerForm(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Brief description of what this server does..."
                  rows={3}
                />
              </div>

              {/* Transport-specific fields */}
              {customServerForm.transport === 'stdio' && (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="command">Command *</Label>
                    <Input
                      id="command"
                      value={customServerForm.command}
                      onChange={(e) => setCustomServerForm(prev => ({ ...prev, command: e.target.value }))}
                      placeholder="python -m my_mcp_server"
                      className="font-mono"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="args">Arguments (comma-separated)</Label>
                    <Input
                      id="args"
                      value={customServerForm.args}
                      onChange={(e) => setCustomServerForm(prev => ({ ...prev, args: e.target.value }))}
                      placeholder="--port,8080,--debug"
                      className="font-mono"
                    />
                  </div>
                </div>
              )}

              {(customServerForm.transport === 'http' || customServerForm.transport === 'sse') && (
                <div className="space-y-2">
                  <Label htmlFor="url">URL *</Label>
                  <Input
                    id="url"
                    value={customServerForm.url}
                    onChange={(e) => setCustomServerForm(prev => ({ ...prev, url: e.target.value }))}
                    placeholder="https://api.example.com/mcp"
                    className="font-mono"
                  />
                </div>
              )}

              {/* Environment Variables */}
              <KeyValueInput
                label="Environment Variables"
                placeholder="Add environment variables"
                keyPlaceholder="Variable name"
                valuePlaceholder="Variable value"
                pairs={customServerForm.env}
                onChange={(pairs) => setCustomServerForm(prev => ({ ...prev, env: pairs }))}
              />

              {/* Headers */}
              <KeyValueInput
                label="Headers"
                placeholder="Add custom headers"
                keyPlaceholder="Header name"
                valuePlaceholder="Header value"
                pairs={customServerForm.headers}
                onChange={(pairs) => setCustomServerForm(prev => ({ ...prev, headers: pairs }))}
              />

              {/* Options */}
              {/* <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="auto-connect"
                    checked={customServerForm.auto_connect}
                    onCheckedChange={(checked: boolean) => 
                      setCustomServerForm(prev => ({ ...prev, auto_connect: checked }))
                    }
                  />
                  <Label htmlFor="auto-connect">Auto-connect on startup</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="enabled"
                    checked={customServerForm.enabled}
                    onCheckedChange={(checked: boolean) => 
                      setCustomServerForm(prev => ({ ...prev, enabled: checked }))
                    }
                  />
                  <Label htmlFor="enabled">Enabled</Label>
                </div>
              </div> */}

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
                <Button
                  variant="outline"
                  onClick={() => setShowCustomServerModal(false)}
                  disabled={customServerLoading}
                >
                  Cancel
                </Button>
                <Button
                  onClick={addCustomServerToVMCP}
                  disabled={customServerLoading || !customServerForm.name.trim()}
                  className="flex items-center gap-2"
                >
                  {customServerLoading ? (
                    <>
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      Adding...
                    </>
                  ) : (
                    <>
                      <Plus className="h-4 w-4" />
                      Add to vMCP
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

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