import React, { useState } from 'react';
import { useRouter } from '@/hooks/useRouter';
import { Play, Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { FaviconIcon } from '@/components/ui/favicon-icon';
import { useToast } from '@/hooks/use-toast';
import { apiClient } from '@/api/client';
import { useVMCP } from '@/contexts/vmcp-context';

interface DemoVMCPSectionProps {
  publicVMCPS: any[];
}

export default function DemoVMCPSection({ publicVMCPS }: DemoVMCPSectionProps) {
  const router = useRouter();
  const { success, error: toastError } = useToast();
  const { forceRefreshVMCPData } = useVMCP();
  const [importing, setImporting] = useState<Record<string, boolean>>({});

  const handleImport = async (vmcp: any) => {
    const vmcpId = vmcp.id || vmcp.public_vmcp_id;
    
    if (importing[vmcpId]) return;
    
    setImporting(prev => ({ ...prev, [vmcpId]: true }));
    
    try {
      const accessToken = localStorage.getItem('access_token') || 
        (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);
      
      if (!accessToken) {
        toastError('Please log in to import vMCP configuration');
        return;
      }

      // Fetch the full VMCP config from the database
      const publicVMCPResult = await apiClient.getPublicVMCPDetails(vmcpId, accessToken);
      
      if (!publicVMCPResult.success || !publicVMCPResult.data) {
        toastError('Failed to fetch vMCP configuration');
        return;
      }

      // The data is already in VMCPConfig format, use it directly
      const importData = publicVMCPResult.data;

      // Validate the imported data
      if (!importData.name || !importData.vmcp_config) {
        toastError('Invalid vMCP configuration');
        return;
      }

      // Create a new vMCP with imported configuration
      // Add suffix to name to avoid conflicts
      const newName = `${importData.name}-${Date.now()}`;

      const createResponse = await apiClient.createVMCP({
        ...importData,
        name: newName
      }, accessToken);

      if (createResponse.success) {
        success(`vMCP "${newName}" imported successfully`);
        forceRefreshVMCPData();
        // Navigate to the new vMCP
        if (createResponse.data?.id) {
          router.push(`/vmcp/${createResponse.data.id}`);
        }
      } else {
        toastError(createResponse.error || 'Failed to import vMCP configuration');
      }
    } catch (error) {
      console.error('Import error:', error);
      toastError('Failed to import vMCP configuration. Please check the file format.');
    } finally {
      setImporting(prev => ({ ...prev, [vmcpId]: false }));
    }
  };


  const isIconUrl = (icon: string) => {
    return icon.startsWith('http://') || icon.startsWith('https://');
  };

  const getIconSource = (vmcp: any) => {
    if (vmcp.metadata?.icon) {
      return isIconUrl(vmcp.metadata.icon) 
        ? vmcp.metadata.icon 
        : `data:image/png;base64,${vmcp.metadata.icon}`;
    }
    return null;
  };

  const getVMCPStats = (vmcp: any) => {
    const serversCount = vmcp.vmcp_config?.selected_servers?.length || 0;
    
    // Calculate totals from config if not provided (only if undefined/null, not if 0)
    let toolsCount = vmcp.total_tools;
    let resourcesCount = vmcp.total_resources;
    let promptsCount = vmcp.total_prompts;
    
    if (toolsCount === undefined || toolsCount === null) {
      toolsCount = Object.values(vmcp.vmcp_config?.selected_tools || {}).reduce(
        (sum: number, tools: any) => sum + (Array.isArray(tools) ? tools.length : 0),
        0
      );
    }
    
    if (resourcesCount === undefined || resourcesCount === null) {
      resourcesCount = Object.values(vmcp.vmcp_config?.selected_resources || {}).reduce(
        (sum: number, resources: any) => sum + (Array.isArray(resources) ? resources.length : 0),
        0
      );
    }
    
    if (promptsCount === undefined || promptsCount === null) {
      promptsCount = Object.values(vmcp.vmcp_config?.selected_prompts || {}).reduce(
        (sum: number, prompts: any) => sum + (Array.isArray(prompts) ? prompts.length : 0),
        0
      );
    }

    return {
      serversCount,
      toolsCount: toolsCount ?? 0,
      resourcesCount: resourcesCount ?? 0,
      promptsCount: promptsCount ?? 0
    };
  };

  if (publicVMCPS.length === 0) {
    return (
      <Card className="text-center py-12 bg-gradient-to-br from-muted/20 to-muted/10 border-2 border-dashed border-muted-foreground/30">
        <CardContent>
          <div className="h-16 w-16 rounded-full bg-muted/50 flex items-center justify-center mx-auto mb-4">
            <Play className="h-8 w-8 text-muted-foreground" />
          </div>
          <CardTitle className="text-xl font-semibold mb-2">No Demo vMCPs Available</CardTitle>
          <CardDescription className="text-muted-foreground">
            Check back later for demo vMCPs to try out
          </CardDescription>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      {publicVMCPS.map((publicVMCP, index) => {
        const vmcpId = publicVMCP.id || publicVMCP.public_vmcp_id;
        const isImporting = importing[vmcpId] || false;
        const stats = getVMCPStats(publicVMCP);
        
        return (
          <div
            key={vmcpId}
            className="group relative rounded-xl border transition-all duration-200 shadow-sm hover:shadow-lg hover:border-primary/50 bg-card overflow-hidden h-72 flex flex-col"
            style={{
              animationDelay: `${index * 100}ms`
            }}
          >
            {/* Main Content */}
            <div className="p-4 pb-0 flex flex-col flex-1">
              {/* Header Section */}
              <div className="flex items-start gap-3 mb-4">
                <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary/20 to-primary/10 flex items-center justify-center overflow-hidden shadow-sm">
                  {getIconSource(publicVMCP) ? (
                    <img 
                      src={getIconSource(publicVMCP)} 
                      alt={publicVMCP.name}
                      className="h-6 w-6 object-contain"
                      onError={(e) => {
                        e.currentTarget.style.display = 'none';
                        e.currentTarget.nextElementSibling?.classList.remove('hidden');
                      }}
                    />
                  ) : null}
                  <Play className={`h-5 w-5 text-primary ${getIconSource(publicVMCP) ? 'hidden' : ''}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="mb-2">
                    {publicVMCP.name.startsWith('@') ? (
                      <div className="flex flex-col flex-1 min-w-0">
                        <span className="text-xs text-muted-foreground font-medium">
                          {publicVMCP.name.split('/')[0]}/
                        </span>
                        <h4 className="font-semibold text-foreground text-sm truncate">
                          {publicVMCP.name.split('/').slice(1).join('/')}
                        </h4>
                      </div>
                    ) : (
                      <h4 className="font-semibold text-foreground text-sm truncate">{publicVMCP.name}</h4>
                    )}
                  </div>     
                </div>
              </div>
              
              {/* Category Section */}
              <div className="mb-2">
                {publicVMCP.metadata?.category && (
                  <Badge variant="outline" className="text-[10px] text-muted-foreground bg-muted/60 px-2 py-1 rounded-md font-medium w-fit inline-block">
                    {typeof publicVMCP.metadata.category === 'string' 
                      ? publicVMCP.metadata.category 
                      : publicVMCP.metadata.category.secondary || 'Category'}
                  </Badge>
                )}
              </div>
              
              {/* Description Section */}
              {publicVMCP.description && (
                <p className="text-xs pb-2 text-muted-foreground leading-relaxed line-clamp-3 min-h-[3rem]">
                  {publicVMCP.description}
                </p>
              )}

              {/* MCP Servers Section */}
              <div className="mb-3 min-h-[32px]">
                {publicVMCP.vmcp_config?.selected_servers && publicVMCP.vmcp_config.selected_servers.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {publicVMCP.vmcp_config.selected_servers.slice(0, 3).map((server: any, serverIndex: number) => (
                      <div key={serverIndex} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-muted/40 hover:bg-muted/60 transition-colors">
                        <FaviconIcon
                          url={server.url}
                          faviconUrl={server.favicon_url}
                          className="h-3 w-3"
                          size={12}
                        />
                        <span className="text-xs font-medium truncate max-w-40">{server.name}</span>
                      </div>
                    ))}
                    {publicVMCP.vmcp_config.selected_servers.length > 3 && (
                      <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-muted/40">
                        <span className="text-xs font-medium text-muted-foreground">
                          +{publicVMCP.vmcp_config.selected_servers.length - 3}
                        </span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="min-h-[32px]"></div>
                )}
              </div>
            </div>
            
            {/* Stats and Actions Section */}
            <div className="px-4 py-4 border-t border-border/30 mt-auto">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-6">
                  <div className="flex items-center gap-1">
                    <span className="font-medium text-foreground text-xs">{stats.toolsCount}</span>
                    <span className="text-muted-foreground text-xs">tools</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="font-medium text-foreground text-xs">{stats.promptsCount}</span>
                    <span className="text-muted-foreground text-xs">prompts</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="font-medium text-foreground text-xs">{stats.resourcesCount}</span>
                    <span className="text-muted-foreground text-xs">resources</span>
                  </div>
                </div>
                {/* Import Icon Button */}
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleImport(publicVMCP);
                      }}
                      disabled={isImporting}
                      className="h-8 w-8 p-0 rounded-full"
                    >
                      {isImporting ? (
                        <div className="h-4 w-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <Download className="h-4 w-4" />
                      )}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p className='text-xs'>{isImporting ? 'Importing...' : 'Import vMCP'}</p>
                  </TooltipContent>
                </Tooltip>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

