
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useRouter } from '@/hooks/useRouter';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { FaviconIcon } from '@/components/ui/favicon-icon';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Separator } from '@/components/ui/separator';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { 
  Server as ServerIcon,
  TestTube,
  Trash2,
  Link as LinkIcon,
  AlertTriangle,
  CheckCircle,
  Activity,
  Terminal,
  RefreshCw,
  Power,
  PowerOff,
  Globe,
  Wifi,
  WifiOff,
  Lock,
  Container,
  Code,
  MessageSquare,
  FolderOpen,
  Database,
  X,
  KeyRound
} from 'lucide-react';
import { useAuth } from '@/contexts/auth-context';
import { 
  useServersList, 
  useServerStats, 
  useServersLoading, 
  useServersError, 
  useServersActions 
} from '@/contexts/servers-context';
import { useVMCPActions, useVMCPState } from '@/contexts/vmcp-context';
import { useToast } from '@/hooks/use-toast';
import { type MCPServer } from '@/lib/new-api';

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

// Helper function to get capability names
const getCapabilityNames = (server: MCPServer, type: 'tools' | 'resources' | 'prompts') => {
  switch (type) {
    case 'tools':
      if (server.tools_list && Array.isArray(server.tools_list)) {
        return server.tools_list.map((tool: any) => tool.name || tool).join(', ');
      }
      return 'No tools available';
    case 'resources':
      if (server.resources_list && Array.isArray(server.resources_list)) {
        return server.resources_list.map((resource: any) => resource.name || resource.uri || resource).join(', ');
      }
      return 'No resources available';
    case 'prompts':
      if (server.prompts_list && Array.isArray(server.prompts_list)) {
        return server.prompts_list.map((prompt: any) => prompt.name || prompt).join(', ');
      }
      return 'No prompts available';
    default:
      return '';
  }
};

// Helper function to detect if icon is URL or base64
const isIconUrl = (icon: string) => {
  return icon.startsWith('http://') || icon.startsWith('https://');
};

// Helper function to get icon source
const getIconSource = (vmcp: any) => {
  if (vmcp.metadata?.icon) {
    return isIconUrl(vmcp.metadata.icon) 
      ? vmcp.metadata.icon 
      : `data:image/png;base64,${vmcp.metadata.icon}`;
  }
  return null;
};

// Component to display vMCPs using this server
const VMCPUsageDisplay = ({ serverId, vmcps, server }: { serverId: string; vmcps: any[]; server: any }) => {
  const getVMCPSUsingServer = useCallback((serverId: string, server: any, vmcps: any[]) => {
    // First check if server has vmcps_using_server field
    if (server.vmcps_using_server && Array.isArray(server.vmcps_using_server)) {
      return vmcps.filter(vmcp => 
        server.vmcps_using_server.includes(vmcp.id)
      );
    }
    
    // Fallback to checking selected_servers array
    return vmcps.filter(vmcp => {
      return vmcp.config?.vmcp_config?.selected_servers?.some((srv: any) => 
        srv.id === serverId || srv.server_id === serverId
      );
    });
  }, []);

  const usingVMCPS = getVMCPSUsingServer(serverId, server, vmcps);
  
  const maxVisible = 3;
  const visibleVMCPS = usingVMCPS.slice(0, maxVisible);
  const remainingCount = usingVMCPS.length - maxVisible;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground">vMCPs ({usingVMCPS.length})</span>
      </div>
      
      <div className="flex flex-wrap gap-1.5">
        {usingVMCPS.length === 0 ? (
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-muted/40">
            <div className="h-3 w-3 rounded bg-gradient-to-br from-muted-foreground/20 to-muted-foreground/10 flex items-center justify-center">
              <Container className="h-1.5 w-1.5 text-muted-foreground" />
            </div>
            <span className="text-xs font-medium text-muted-foreground">No vMCPs using this server</span>
          </div>
        ) : (
          <>
            {visibleVMCPS.map((vmcp) => (
              <div
                key={vmcp.id}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-muted/40 hover:bg-muted/60 transition-colors"
              >
                <div className="h-3 w-3 rounded bg-gradient-to-br from-primary/20 to-primary/10 flex items-center justify-center overflow-hidden flex-shrink-0">
                  {getIconSource(vmcp) ? (
                    <img 
                      src={getIconSource(vmcp)} 
                      alt={vmcp.name}
                      className="h-2 w-2 object-contain"
                      onError={(e) => {
                        e.currentTarget.style.display = 'none';
                        e.currentTarget.nextElementSibling?.classList.remove('hidden');
                      }}
                    />
                  ) : null}
                  <Container className={`h-1.5 w-1.5 text-primary ${getIconSource(vmcp) ? 'hidden' : ''}`} />
                </div>
                <span className="text-xs font-medium truncate max-w-20" title={vmcp.name}>
                  {vmcp.name}
                </span>
              </div>
            ))}
            
            {remainingCount > 0 && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-muted/40 hover:bg-muted/60 transition-colors cursor-help">
                    <span className="text-xs font-medium text-muted-foreground">
                      +{remainingCount}
                    </span>
                  </div>
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-xs">
                  <div className="text-xs">
                    <strong>Additional vMCPs:</strong>
                    <ul className="mt-1 space-y-1">
                      {usingVMCPS.slice(maxVisible).map((vmcp) => (
                        <li key={vmcp.id} className="flex items-center gap-2">
                          <div className="h-3 w-3 rounded bg-gradient-to-br from-primary/20 to-primary/10 flex items-center justify-center">
                            {getIconSource(vmcp) ? (
                              <img 
                                src={getIconSource(vmcp)} 
                                alt={vmcp.name}
                                className="h-1.5 w-1.5 object-contain"
                              />
                            ) : (
                              <Container className="h-1.5 w-1.5 text-primary" />
                            )}
                          </div>
                          <span className="text-foreground">{vmcp.name}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </TooltipContent>
              </Tooltip>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default function ServersPage() {
  const router = useRouter();
  const { user, loading: authLoading, isAuthenticated } = useAuth();
  const { success, error: toastError } = useToast();
  const servers = useServersList();
  const serverStats = useServerStats();
  const loading = useServersLoading();
  const { error, hasError } = useServersError();
  const { vmcps } = useVMCPState();
  const allVmcps = useMemo(() => [...vmcps.private, ...vmcps.public], [vmcps]);
  const { refreshVMCPData } = useVMCPActions();

  // Debug logging
  useEffect(() => {
    console.log('🔍 ServersPage Debug:', {
      servers,
      serversLength: servers?.length,
      loading,
      hasError,
      error,
      serverStats
    });
  }, [servers, loading, hasError, error, serverStats]);
  const { 
    refreshServers, 
    connectServer,
    disconnectServer,
    clearCacheServer,
    authorizeServer,
    refreshServerCapabilities,
    refreshAllCapabilities,
    addServer,
    clearError,
    refreshServerStatus,
    refreshAllStatus,
    clearServerAuth
  } = useServersActions();
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [serverStatuses, setServerStatuses] = useState<Record<string, { status: string; loading: boolean; lastUpdated?: string }>>({});
  const [serverCapabilities, setServerCapabilities] = useState<Record<string, { capabilities: Record<string, number>; loading: boolean; lastUpdated?: string }>>({});
  const [batchStatusLoading, setBatchStatusLoading] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [serverToDelete, setServerToDelete] = useState<any>(null);
  const [deleting, setDeleting] = useState(false);
  const [headersModalOpen, setHeadersModalOpen] = useState(false);
  const [serverForHeaders, setServerForHeaders] = useState<any>(null);
  const [headersData, setHeadersData] = useState<Record<string, string>>({});
  const [updatingHeaders, setUpdatingHeaders] = useState(false);

  // Initialize server statuses when servers load
  useEffect(() => {
    if (servers && servers.length > 0) {
      const initialStatuses: Record<string, { status: string; loading: boolean; lastUpdated?: string }> = {};
      servers.forEach(server => {
        initialStatuses[server.server_id] = {
          status: server.status,
          loading: false, // Start with not loading state
          lastUpdated: undefined
        };
      });
      setServerStatuses(initialStatuses);
    }
  }, [servers]);


  const handleAuth = async (serverId: string) => {
    setActionLoading(serverId);
    try {
      await authorizeServer(serverId);
      // No success message needed as user will be redirected to authorization page
    } catch (err) {
      console.error('Error authorizing server:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to authorize server';
      toastError(errorMessage);
      setActionLoading(null);
    }
  };

  const handleClearAuth = async (serverId: string) => {
    setActionLoading(serverId);
    try {
      await clearServerAuth(serverId);
      success('Authentication information cleared successfully');
      
      // Refresh both server and vMCP contexts
      await Promise.all([
        refreshServers(),
        refreshVMCPData()
      ]);
    } catch (err) {
      console.error('Error clearing server auth:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to clear server auth';
      toastError(errorMessage);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteClick = (server: any) => {
    setServerToDelete(server);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!serverToDelete) return;

    setDeleting(true);
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        toastError('Please log in to delete servers');
        return;
      }

      const response = await fetch(`/api/mcps/${serverToDelete.server_id}/uninstall`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        success(`MCP server "${serverToDelete.name}" deleted successfully`);
        // Refresh both server and vMCP contexts
        await Promise.all([
          refreshServers(),
          refreshVMCPData()
        ]);
      } else {
        const errorData = await response.json();
        toastError(errorData.detail || 'Failed to delete server');
      }
    } catch (error) {
      console.error('Error deleting server:', error);
      toastError('Failed to delete server');
    } finally {
      setDeleting(false);
      setDeleteDialogOpen(false);
      setServerToDelete(null);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setServerToDelete(null);
  };

  const handleHeadersClick = (server: any) => {
    setServerForHeaders(server);
    // Initialize headers data from server config
    const currentHeaders = server.headers || {};
    setHeadersData({ ...currentHeaders });
    setHeadersModalOpen(true);
  };

  const handleHeadersCancel = () => {
    setHeadersModalOpen(false);
    setServerForHeaders(null);
    setHeadersData({});
  };

  const handleHeadersUpdate = async () => {
    if (!serverForHeaders) return;

    setUpdatingHeaders(true);
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        toastError('Please log in to update server headers');
        return;
      }

      // Prepare update data with current server config plus new headers
      const updateData = {
        name: serverForHeaders.name,
        mode: serverForHeaders.transport_type || 'http',
        description: serverForHeaders.description,
        url: serverForHeaders.url,
        headers: headersData,
        auto_connect: serverForHeaders.auto_connect !== false,
        enabled: serverForHeaders.enabled !== false
      };

      const response = await fetch(`/api/mcps/${serverForHeaders.server_id}/update`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updateData),
      });

      if (response.ok) {
        success('Server headers updated successfully');
        setHeadersModalOpen(false);
        setServerForHeaders(null);
        setHeadersData({});
        
        // Refresh servers list
        await refreshServers();
      } else {
        const errorData = await response.json();
        toastError(errorData.detail || 'Failed to update server headers');
      }
    } catch (error) {
      console.error('Error updating server headers:', error);
      toastError('Failed to update server headers');
    } finally {
      setUpdatingHeaders(false);
    }
  };


  const removeHeaderRow = (key: string) => {
    setHeadersData(prev => {
      const newData = { ...prev };
      delete newData[key];
      return newData;
    });
  };

  const updateHeaderKey = (oldKey: string, newKey: string) => {
    if (oldKey === newKey) return;
    
    setHeadersData(prev => {
      const newData = { ...prev };
      const value = newData[oldKey];
      delete newData[oldKey];
      newData[newKey] = value;
      return newData;
    });
  };

  const updateHeaderValue = (key: string, value: string) => {
    setHeadersData(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const handleConnect = async (serverId: string) => {
    setActionLoading(serverId);
    try {
      await connectServer(serverId);
      success('Server connected successfully');
      
      // Refresh both server and vMCP contexts
      await Promise.all([
        refreshServers(),
        refreshVMCPData()
      ]);
    } catch (err) {
      console.error('Error connecting server:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to connect server';
      toastError(errorMessage);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDisconnect = async (serverId: string) => {
    setActionLoading(serverId);
    try {
      await disconnectServer(serverId);
      success('Server disconnected successfully');
      
      // Refresh both server and vMCP contexts
      await Promise.all([
        refreshServers(),
        refreshVMCPData()
      ]);
    } catch (err) {
      console.error('Error disconnecting server:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to disconnect server';
      toastError(errorMessage);
    } finally {
      setActionLoading(null);
    }
  };

  const handleClearCache = async (serverId: string) => {
    setActionLoading(serverId);
    try {
      await clearCacheServer(serverId);
      success('Cache cleared and server reconnected successfully');
      
      // Refresh both server and vMCP contexts
      await Promise.all([
        refreshServers(),
        refreshVMCPData()
      ]);
    } catch (err) {
      console.error('Error clearing cache:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to clear cache';
      toastError(errorMessage);
    } finally {
      setActionLoading(null);
    }
  };

  const getStatusDisplay = (server: MCPServer, serverStatus?: { status: string; loading: boolean; lastUpdated?: string }) => {
    // Use real-time status if available, otherwise fall back to stored status
    const currentStatus = serverStatus?.status || server.status;
    const isLoading = serverStatus?.loading || false;
    
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

  const getTransportIcon = (transport: string) => {
    switch (transport) {
      case 'stdio':
        return Terminal;
      case 'http':
        return Globe;
      case 'sse':
        return Wifi;
      default:
        return ServerIcon;
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading MCP Servers...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen mx-auto p-4">
      <div className="min-h-screen">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-12 w-12 rounded-lg bg-primary/20 flex items-center justify-center">
                <ServerIcon className="h-8 w-8 text-primary" />
              </div>
              <div>
              <h1 className="text-3xl font-bold text-foreground">
                Server Connections
              </h1>
              <p className="text-muted-foreground">Manage your Model Context Protocol server connections</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {/* <Button 
                onClick={refreshAllStatus}
                disabled={loading || batchStatusLoading}
                variant="outline"
              >
                <RefreshCw className={`h-4 w-4 mr-2 ${batchStatusLoading ? 'animate-spin' : ''}`} />
                Refresh All Status
              </Button>
              <Button 
                onClick={refreshAllCapabilities}
                disabled={loading}
                variant="outline"
              >
                <RefreshCw className={`h-4 w-4 mr-2`} />
                Refresh All Capabilities
              </Button> */}
              <Button 
                onClick={refreshServers}
                disabled={loading}
                variant="outline"
              >
                <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                Refresh List
              </Button>
              {/* <Button 
                variant={'default'}
                onClick={() => router.push('/servers/add')}
                className="flex items-center gap-2"
              >
                <Plus/>Custom Server
              </Button> */}
            </div>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription className="flex items-center justify-between">
              <span>{error}</span>
              <div className="flex items-center gap-2 ml-4">
                <Button
                  onClick={clearError}
                  variant="outline"
                  size="sm"
                >
                  Clear
                </Button>
                <Button
                  onClick={refreshServers}
                  variant="outline"
                  size="sm"
                >
                  Retry
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        )}

        {/* Loading Indicator */}
        {loading && (
          <Alert className="mb-6">
            <Activity className="h-4 w-4 animate-spin" />
            <AlertDescription>Loading servers...</AlertDescription>
          </Alert>
        )}


        {/* Servers Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          {servers && Array.isArray(servers) && servers.map((server) => {
            // Skip rendering if server is invalid or missing required properties
            const serverId = server.server_id || (server as any).id || (server as any).server_id;
            if (!server || typeof server !== 'object' || !serverId) {
              console.warn('Skipping invalid server object:', server);
              return null;
            }
            
            try {
              const serverStatus = serverStatuses[serverId];
              const serverCapability = serverCapabilities[serverId];
              const status = getStatusDisplay(server, serverStatus);
              const StatusIcon = status.icon;
              const TransportIcon = getTransportIcon(server.transport_type || 'unknown');
              const isLoading = actionLoading === server.name;

              // Get VMcPs using this server for delete button visibility
              const getVMCPSUsingServer = (serverId: string, server: any, vmcps: any[]) => {
                if (server.vmcps_using_server && Array.isArray(server.vmcps_using_server)) {
                  return vmcps.filter(vmcp => 
                    server.vmcps_using_server.includes(vmcp.id)
                  );
                }
                return vmcps.filter(vmcp => {
                  return vmcp.config?.vmcp_config?.selected_servers?.some((srv: any) => 
                    srv.id === serverId || srv.server_id === serverId
                  );
                });
              };
              const usingVMCPS = getVMCPSUsingServer(serverId, server, allVmcps);

              return (
                <div key={server.name} className="group relative p-4 rounded-lg border transition-all duration-200 shadow-sm hover:shadow-md hover:border-primary/50 flex flex-col h-full">
                  {/* Action Buttons - Top Right */}
                  <div className="absolute top-3 right-3 flex gap-1 z-10">
                    {/* Headers Button - Show only for servers with existing headers */}
                    {server.headers && Object.keys(server.headers).length > 0 ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleHeadersClick(server);
                        }}
                        className="h-8 w-8 p-0 rounded-full transition-all duration-200 bg-background/80 backdrop-blur-sm hover:bg-primary/10 text-muted-foreground hover:text-primary shadow-sm"
                        title="Manage headers"
                      >
                        <KeyRound className="h-4 w-4" />
                      </Button>
                    ) : null}
                    
                    {/* Delete Button - Only show when no VMcPs are using this server */}
                    {usingVMCPS.length === 0 && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteClick(server);
                        }}
                        className="h-8 w-8 p-0 rounded-full transition-all duration-200 bg-background/80 backdrop-blur-sm hover:bg-destructive/10 text-muted-foreground hover:text-destructive shadow-sm"
                        title="Delete server"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>

                  {/* Main Content Area */}
                  <div className="flex-1">
                    {/* Server Info */}
                    <div className="space-y-3">
                      {/* Header Section - Fixed height */}
                      <div className="h-20">
                        <div className="flex items-start gap-2">
                          {(server as any).favicon_url ? (
                            <FaviconIcon
                              url={server.url}
                              faviconUrl={(server as any).favicon_url}
                              className="h-8 w-8"
                              size={32}
                            />
                          ) : (
                            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-primary/15 to-primary/25 flex items-center justify-center border border-primary/20 group-hover:border-primary/30 transition-colors flex-shrink-0">
                              <TransportIcon className="h-4 w-4 text-primary" />
                            </div>
                          )}
                          <div className="flex-1 min-w-0">
                            <h4 className="font-medium text-foreground text-sm mb-1 truncate font-mono">{server.name || 'Unnamed Server'}</h4>
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
                      </div>
                      
                      {/* Server Stats Section - Fixed height */}
                      <div className="h-6">
                        <div className="flex items-center gap-4 text-xs text-muted-foreground">
                          <div className="flex items-center gap-1">
                            <Code className="h-3 w-3" />
                            <span>{(server.tool_details?.length || server.capabilities?.tools_count || 0)} tools</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <MessageSquare className="h-3 w-3" />
                            <span>{(server.prompt_details?.length || server.capabilities?.prompts_count || 0)} prompts</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <FolderOpen className="h-3 w-3" />
                            <span>{(server.resource_details?.length || server.capabilities?.resources_count || 0)} resources</span>
                          </div>
                        </div>
                      </div>

                      {/* vMCP Usage Section - Fixed height */}
                      <div className="h-16">
                        <VMCPUsageDisplay serverId={serverId} vmcps={allVmcps} server={server} />
                      </div>

                      {/* Last Connected Section - Fixed height */}
                      <div className="h-6">
                        {server.last_connected && (
                          <div className="text-xs text-muted-foreground">
                            Last connected: {new Date(server.last_connected).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' })} IST
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Fixed Bottom Actions Section */}
                  <div className="mt-auto">
                    <div className="flex items-center justify-center gap-1 pt-3 border-t border-muted-foreground/10">
                      <div className="flex items-center gap-1 flex-wrap justify-center">
                        {/* Connect/Disconnect button based on status */}
                        {server.status === 'connected' ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDisconnect(serverId)}
                            disabled={isLoading}
                            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                          >
                            <PowerOff className="h-3 w-3" />
                            Disconnect
                          </Button>
                        ) : server.status === 'auth_required' ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleAuth(serverId)}
                            disabled={isLoading}
                            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                          >
                            <LinkIcon className="h-3 w-3" />
                            Authorize
                          </Button>
                        ) : (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleConnect(serverId)}
                            disabled={isLoading}
                            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                          >
                            <Power className="h-3 w-3" />
                            Connect
                          </Button>
                        )}
                        
                        {/* Clear Cache button */}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleClearCache(serverId)}
                          disabled={isLoading}
                          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                        >
                          <Database className="h-3 w-3" />
                          Clear Cache
                        </Button>
                        
                        {/* Test button */}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => { console.log('server.name', server.name); console.log('server.server_id', serverId); router.push(`/servers/${server.name}/${serverId}/test`)}}
                          disabled={isLoading}
                          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                        >
                          <TestTube className="h-3 w-3" />
                          Test
                        </Button>
                      </div>
                    </div>
                  </div>

                  {/* Loading Overlay */}
                  {isLoading && (
                    <div className="absolute inset-0 bg-background/50 backdrop-blur-sm rounded-lg flex items-center justify-center">
                      <RefreshCw className="h-6 w-6 animate-spin" />
                    </div>
                  )}
                </div>
              );
            } catch (error) {
              console.error('Error rendering server:', server.server_id, error);
              return null;
            }
          })}
        </div>

        {/* Empty State */}
        {!loading && (!servers || servers.length === 0) && (
          <Card className="text-center py-12">
            <CardContent>
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                <ServerIcon className="h-8 w-8 text-muted-foreground" />
              </div>
              <CardTitle className="mb-2">No MCP Servers</CardTitle>
              <p className="text-muted-foreground mb-6">
                You haven't added any MCP servers to your vMCPs yet. Enchance your vMCPs by adding MCP servers to them.
              </p>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      {deleteDialogOpen && serverToDelete && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-lg shadow-xl max-w-md w-full mx-4">
            <div className="flex items-center justify-between p-4 border-b border-border">
              <div className="flex items-center space-x-2">
                <AlertTriangle className="w-5 h-5 text-destructive" />
                <h3 className="text-lg font-semibold text-foreground">Confirm Deletion</h3>
              </div>
            </div>
            
            <div className="p-4 space-y-4">
              <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-3">
                <p className="text-sm text-destructive-foreground">
                  <strong>Warning:</strong> Deleting this MCP connection may make dependent vMCPs not function properly.
                </p>
              </div>
              
              <p className="text-sm text-foreground">
                Are you sure you want to delete MCP server <strong>"{serverToDelete.name}"</strong>?
              </p>
              
              <p className="text-xs text-muted-foreground">
                This action cannot be undone. All server configuration and connection data will be permanently removed.
              </p>
            </div>
            
            <div className="flex space-x-3 p-4 border-t border-border">
              <Button 
                variant="outline" 
                onClick={handleDeleteCancel} 
                disabled={deleting}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button 
                variant="destructive" 
                onClick={handleDeleteConfirm} 
                disabled={deleting}
                className="flex-1"
              >
                {deleting ? (
                  <div className="flex items-center space-x-2">
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></div>
                    <span>Deleting...</span>
                  </div>
                ) : (
                  <div className="flex items-center space-x-2">
                    <Trash2 className="h-4 w-4" />
                    <span>Delete Server</span>
                  </div>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Headers Management Modal */}
      {headersModalOpen && serverForHeaders && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-border">
              <div className="flex items-center space-x-2">
                <KeyRound className="w-5 h-5 text-primary" />
                <h3 className="text-lg font-semibold text-foreground">Edit Headers</h3>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleHeadersCancel}
                className="h-8 w-8 p-0"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
            
            <div className="p-4 space-y-4 overflow-y-auto max-h-[60vh]">
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">
                  Edit existing HTTP headers for <strong>{serverForHeaders.name}</strong>
                </p>
                
                <div className="space-y-3">
                  {Object.entries(headersData).map(([key, value], index) => (
                    <div key={index} className="flex items-center gap-2">
                      <Input
                        placeholder="Header name (e.g., Authorization)"
                        value={key}
                        onChange={(e) => updateHeaderKey(key, e.target.value)}
                        className="flex-1"
                      />
                      <span className="text-muted-foreground">:</span>
                      <Input
                        placeholder="Header value"
                        value={value}
                        onChange={(e) => updateHeaderValue(key, e.target.value)}
                        className="flex-1"
                        type={key.toLowerCase().includes('password') || key.toLowerCase().includes('secret') || key.toLowerCase().includes('token') ? 'password' : 'text'}
                      />
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeHeaderRow(key)}
                        className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            
            <div className="flex space-x-3 p-4 border-t border-border">
              <Button 
                variant="outline" 
                onClick={handleHeadersCancel} 
                disabled={updatingHeaders}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button 
                onClick={handleHeadersUpdate} 
                disabled={updatingHeaders}
                className="flex-1"
              >
                {updatingHeaders ? (
                  <div className="flex items-center space-x-2">
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></div>
                    <span>Updating...</span>
                  </div>
                ) : (
                  <div className="flex items-center space-x-2">
                    <KeyRound className="h-4 w-4" />
                    <span>Save Changes</span>
                  </div>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
} 