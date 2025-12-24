// components/vmcp/ProgressiveDiscoveryTab.tsx

import { useState, useEffect, useRef } from 'react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ToolIcon, McpIcon, VmcpIcon } from '@/lib/vmcp';
import { VMCPConfig } from '@/types/vmcp';
import { apiClient } from '@/api/client';
import { useToast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';

interface ProgressiveDiscoveryTabProps {
  vmcpConfig: VMCPConfig;
  vmcpId: string;
  isRemoteVMCP?: boolean;
  onProgressiveDiscoveryStatusChange?: (enabled: boolean) => void;
  setVmcpConfig?: (config: VMCPConfig | ((prev: VMCPConfig) => VMCPConfig)) => void;
}

export default function ProgressiveDiscoveryTab({
  vmcpConfig,
  vmcpId,
  isRemoteVMCP = false,
  onProgressiveDiscoveryStatusChange,
  setVmcpConfig,
}: ProgressiveDiscoveryTabProps) {
  const [progressiveDiscoveryEnabled, setProgressiveDiscoveryEnabled] = useState(false);
  const [togglingProgressiveDiscovery, setTogglingProgressiveDiscovery] = useState(false);
  const { success: showSuccess, error: showError } = useToast();
  
  // Initialize pd_enabled_tools from config, default to empty object
  const [pdEnabledTools, setPdEnabledTools] = useState<Record<string, string[]>>(
    vmcpConfig.vmcp_config.pd_enabled_tools || {}
  );

  // Track the last config ID we synced from to avoid overwriting local changes
  const lastSyncedConfigId = useRef<string | null>(null);

  // Load progressive discovery status from config metadata (only on initial load or when vmcpId changes)
  useEffect(() => {
    if (!vmcpId || vmcpId === 'new') {
      setProgressiveDiscoveryEnabled(false);
      setPdEnabledTools({});
      lastSyncedConfigId.current = null;
      return;
    }

    // Only sync from config if this is a new config (initial load or vmcpId change)
    // This prevents overwriting local unsaved changes
    const currentConfigId = vmcpConfig.id || '';
    if (lastSyncedConfigId.current !== currentConfigId && currentConfigId) {
      // Read status from config metadata instead of making separate API call
      const metadata = vmcpConfig.metadata || {};
      const pdEnabled = metadata.progressive_discovery_enabled === true;
      setProgressiveDiscoveryEnabled(pdEnabled);
      
      // Initialize pd_enabled_tools from config (only on initial load)
      if (vmcpConfig.vmcp_config.pd_enabled_tools) {
        setPdEnabledTools(vmcpConfig.vmcp_config.pd_enabled_tools);
      } else {
        setPdEnabledTools({});
      }
      
      lastSyncedConfigId.current = currentConfigId;
    }
  }, [vmcpId, vmcpConfig.id]); // Only depend on vmcpId and config.id to sync when config is loaded

  const handleToggleProgressiveDiscovery = async (checked: boolean) => {
    try {
      setTogglingProgressiveDiscovery(true);
      const accessToken = localStorage.getItem('access_token') || 
        (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);

      if (checked) {
        const result = await apiClient.enableProgressiveDiscovery(vmcpId, accessToken);
        if (result.success) {
          // Initialize pd_enabled_tools to empty if not already set
          if (!vmcpConfig.vmcp_config.pd_enabled_tools) {
            const updatedPdEnabledTools = {};
            updatePdEnabledTools(updatedPdEnabledTools);
          }
          
          // Update local state and config metadata - user will save manually
          setProgressiveDiscoveryEnabled(true);
          if (setVmcpConfig) {
            setVmcpConfig(prev => ({
              ...prev,
              metadata: {
                ...prev.metadata,
                progressive_discovery_enabled: true
              }
            }));
          }
          
          if (onProgressiveDiscoveryStatusChange) {
            onProgressiveDiscoveryStatusChange(true);
          }
          showSuccess('Progressive discovery enabled successfully');
        } else {
          showError(result.error || 'Failed to enable progressive discovery');
        }
      } else {
        const result = await apiClient.disableProgressiveDiscovery(vmcpId, accessToken);
        if (result.success) {
          // Update local state and config metadata - user will save manually
          setProgressiveDiscoveryEnabled(false);
          if (setVmcpConfig) {
            setVmcpConfig(prev => ({
              ...prev,
              metadata: {
                ...prev.metadata,
                progressive_discovery_enabled: false
              }
            }));
          }
          
          if (onProgressiveDiscoveryStatusChange) {
            onProgressiveDiscoveryStatusChange(false);
          }
          showSuccess('Progressive discovery disabled successfully');
        } else {
          showError(result.error || 'Failed to disable progressive discovery');
        }
      }
    } catch (error) {
      console.error('Error toggling progressive discovery:', error);
      showError(`Failed to ${checked ? 'enable' : 'disable'} progressive discovery`);
    } finally {
      setTogglingProgressiveDiscovery(false);
    }
  };

  const updatePdEnabledTools = (newPdEnabledTools: Record<string, string[]>) => {
    // Update local state only - user will save manually via save button
    // This matches the UX pattern of other config changes (tools, prompts, etc.)
    setPdEnabledTools(newPdEnabledTools);
    
    // Update local config so it's included when user saves
    if (setVmcpConfig) {
      setVmcpConfig(prev => ({
        ...prev,
        vmcp_config: {
          ...prev.vmcp_config,
          pd_enabled_tools: newPdEnabledTools
        }
      }));
    }
  };

  const handleToggleTool = (toolName: string, serverId: string | 'custom') => {
    if (isRemoteVMCP) {
      showError('Selection disabled for community vMCPs', {
        description: 'Extend the vMCP to make changes'
      });
      return;
    }

    const currentTools = pdEnabledTools[serverId] || [];
    const newTools = new Set(currentTools);
    
    if (newTools.has(toolName)) {
      newTools.delete(toolName);
    } else {
      newTools.add(toolName);
    }

    const updatedPdEnabledTools = {
      ...pdEnabledTools,
      [serverId]: Array.from(newTools)
    };

    updatePdEnabledTools(updatedPdEnabledTools);
  };

  return (
    <div className="flex flex-col h-full min-h-0 flex-1 overflow-hidden bg-background">
      <div className="shrink-0 flex flex-col gap-3 p-4 border-b border-border bg-muted/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Switch
              id="progressive-discovery-toggle"
              checked={progressiveDiscoveryEnabled}
              onCheckedChange={handleToggleProgressiveDiscovery}
              disabled={isRemoteVMCP || togglingProgressiveDiscovery}
            />
            <Label htmlFor="progressive-discovery-toggle" className="text-sm font-medium">
              {progressiveDiscoveryEnabled ? 'Disable Progressive Discovery' : 'Enable Progressive Discovery'}
            </Label>
          </div>
        </div>
        
        {progressiveDiscoveryEnabled && (
          <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg">
            <h3 className="text-sm font-semibold text-blue-900 dark:text-blue-100 mb-2">
              Progressive Discovery Enabled
            </h3>
            <p className="text-xs text-blue-800 dark:text-blue-200">
              When Progressive Discovery is enabled, three discovery tools are always available:
            </p>
            <ul className="mt-2 text-xs text-blue-800 dark:text-blue-200 list-disc list-inside space-y-1">
              <li><strong>tools_list</strong> - List all available tools</li>
              <li><strong>tool_detail(tool_name)</strong> - Get detailed information about a specific tool</li>
              <li><strong>upload_prompt</strong> - Upload a new prompt to the vMCP</li>
            </ul>
            <p className="mt-2 text-xs text-blue-800 dark:text-blue-200">
              You can selectively enable specific MCP tools and custom tools below. By default, all tools are disabled.
            </p>
          </div>
        )}
      </div>
      
      {progressiveDiscoveryEnabled && (
        <div className="flex-1 overflow-hidden flex flex-col">
          <div className="p-4 border-b border-border">
            <h3 className="text-sm font-semibold mb-2">Select Tools to Enable</h3>
            <p className="text-xs text-muted-foreground">
              Choose which MCP tools and custom tools should be available in Progressive Discovery mode.
            </p>
          </div>
          
          <div className="flex-1 overflow-hidden">
            <Tabs defaultValue="custom-tools" className="w-full h-full flex flex-col">
              <TabsList className="w-full justify-start border-b border-border rounded-none bg-muted/50">
                <TabsTrigger
                  value="custom-tools"
                  className="data-[state=active]:bg-background data-[state=active]:border-accent data-[state=active]:border-b data-[state=active]:border-t-0 data-[state=active]:border-l-0 data-[state=active]:border-r-0 rounded-none"
                >
                              <VmcpIcon className="h-4 w-4 shrink-0" />
                  vMCP Tools
                  <Badge variant="outline" className="ml-2 text-xs">
                    {pdEnabledTools['custom']?.length || 0}/{vmcpConfig.custom_tools.length}
                  </Badge>
                </TabsTrigger>
                {vmcpConfig.vmcp_config.selected_servers.map((server) => {
                  const enabledTools = pdEnabledTools[server.server_id] || [];
                  const serverTools = server.tool_details || [];
                  
                  return (
                    <TabsTrigger
                      key={server.server_id}
                      value={`server-${server.server_id}`}
                      className="data-[state=active]:border-accent data-[state=active]:border-b data-[state=active]:border-t-0 data-[state=active]:border-l-0 data-[state=active]:border-r-0 rounded-none"
                    >
                      <div className="flex items-center gap-2">
                        <McpIcon className="h-4 w-4" />
                        MCP: {server.name}
                      </div>
                      <Badge variant="outline" className="ml-2 text-xs">
                        {enabledTools.length}/{serverTools.length}
                      </Badge>
                    </TabsTrigger>
                  );
                })}
              </TabsList>
              
              <TabsContent value="custom-tools" className="flex-1 overflow-y-auto p-4 mt-0">
                {vmcpConfig.custom_tools.length === 0 ? (
                  <div className="text-center text-muted-foreground py-8">
                    <p className="text-sm">No custom tools available</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {vmcpConfig.custom_tools.map((tool) => {
                      const enabledCustomTools = pdEnabledTools['custom'] || [];
                      const isEnabled = enabledCustomTools.includes(tool.name || '');
                      
                      return (
                        <div
                          key={tool.name}
                          className={cn(
                            "p-3 rounded-lg border transition-all duration-200 cursor-pointer",
                            isEnabled
                              ? "bg-muted/60 border-primary/50 hover:border-primary/80"
                              : "bg-muted/40 border-border/60 hover:bg-muted/60 hover:border-border/80"
                          )}
                          onClick={() => handleToggleTool(tool.name || '', 'custom')}
                        >
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex items-center gap-2 flex-1">
                              <ToolIcon className="h-4 w-4 text-primary shrink-0" />
                              <div className="flex flex-col flex-1 min-w-0">
                                <span className="text-sm font-medium truncate">{tool.name}</span>
                                {tool.tool_type && (
                                  <span className="text-xs text-muted-foreground capitalize">{tool.tool_type}</span>
                                )}
                              </div>
                            </div>
                              <Checkbox
                                checked={isEnabled}
                                onCheckedChange={() => handleToggleTool(tool.name || '', 'custom')}
                                onClick={(e) => e.stopPropagation()}
                                className="ml-2 shrink-0"
                              />
                          </div>
                          {tool.description && (
                            <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
                              {tool.description}
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </TabsContent>
              
              {vmcpConfig.vmcp_config.selected_servers.map((server) => {
                const serverTools = server.tool_details || [];
                const enabledTools = pdEnabledTools[server.server_id] || [];
                
                return (
                  <TabsContent
                    key={server.server_id}
                    value={`server-${server.server_id}`}
                    className="flex-1 overflow-y-auto p-4 mt-0"
                  >
                    {serverTools.length === 0 ? (
                      <div className="text-center text-muted-foreground py-8">
                        <p className="text-sm">No tools available for this server</p>
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                        {serverTools.map((tool: any) => {
                          const isEnabled = enabledTools.includes(tool.name);
                          
                          return (
                            <div
                              key={tool.name}
                              className={cn(
                                "p-3 rounded-lg border transition-all duration-200 cursor-pointer",
                                isEnabled
                                  ? "bg-muted/60 border-primary/50 hover:border-primary/80"
                                  : "bg-muted/40 border-border/60 hover:bg-muted/60 hover:border-border/80"
                              )}
                              onClick={() => handleToggleTool(tool.name, server.server_id)}
                            >
                              <div className="flex items-start justify-between mb-2">
                                <div className="flex items-center gap-2 flex-1">
                                  <ToolIcon className="h-4 w-4 text-primary shrink-0" />
                                  <div className="flex flex-col flex-1 min-w-0">
                                    <span className="text-sm font-medium truncate">{tool.name}</span>
                                  </div>
                                </div>
                                  <Checkbox
                                    checked={isEnabled}
                                    onCheckedChange={() => handleToggleTool(tool.name, server.server_id)}
                                    onClick={(e) => e.stopPropagation()}
                                    className="ml-2 shrink-0"
                                  />
                              </div>
                              {tool.description && (
                                <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
                                  {tool.description}
                                </p>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </TabsContent>
                );
              })}
            </Tabs>
          </div>
        </div>
      )}
    </div>
  );
}

