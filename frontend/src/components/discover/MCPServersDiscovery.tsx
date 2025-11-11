
import React, { useState, useEffect } from 'react';
import { Server, Search, Plus, Copy, ExternalLink, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { useToast } from '@/hooks/use-toast';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useMCPRegistryServersList, useMCPRegistryServersLoading, useInstallMCPRegistryServer } from '@/contexts/servers-context';
import { MCPRegistryServer } from '@/lib/new-api';

interface MCPServersDiscoveryProps {
  onAddServer?: (serverData: any) => Promise<void> | void;
  showSearch?: boolean;
  className?: string;
  searchPlaceholder?: string;
  buttonText?: string;
}

export function MCPServersDiscovery({ 
  onAddServer, 
  showSearch = true, 
  className = "",
  searchPlaceholder = "Search MCP servers...",
  buttonText = "Extend"
}: MCPServersDiscoveryProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const { success, error: toastError } = useToast();
  
  // Use servers context instead of local state
  const servers = useMCPRegistryServersList();
  const loading = useMCPRegistryServersLoading();
  const installMCPRegistryServer = useInstallMCPRegistryServer();

  // Filter servers based on search input (client-side filtering as backup)
  const filteredServers = servers.filter((server: MCPRegistryServer) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      server.name.toLowerCase().includes(query) ||
      (server.description && server.description.toLowerCase().includes(query)) ||
      (server.category && server.category.toLowerCase().includes(query))
    );
  });

  const handleAddMCPServer = async (serverData: MCPRegistryServer) => {
    try {
      if (onAddServer) {
        await onAddServer(serverData);
      } else {
        // Use the install function from servers context
        await installMCPRegistryServer(serverData.id);
        success(`Successfully installed ${serverData.name}`);
      }
    } catch (error) {
      toastError('Failed to add MCP server');
    }
  };

  const handleCopyServerUrl = async (serverData: MCPRegistryServer) => {
    try {
      // Create a shareable URL for the MCP server
      const serverUrl = `${window.location.origin}/servers?add=${encodeURIComponent(JSON.stringify(serverData))}`;
      await navigator.clipboard.writeText(serverUrl);
      success('Server URL copied to clipboard!');
    } catch (error) {
      toastError('Failed to copy server URL');
    }
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {showSearch && (
        <div className="flex items-center gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
            <Input
              placeholder={searchPlaceholder}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <Card className="text-center py-12 bg-gradient-to-br from-muted/20 to-muted/10 border-2 border-dashed border-muted-foreground/30">
          <CardContent>
            <div className="h-16 w-16 rounded-full bg-muted/50 flex items-center justify-center mx-auto mb-4">
              <Loader2 className="h-8 w-8 text-muted-foreground animate-spin" />
            </div>
            <CardTitle className="text-xl font-semibold mb-2">Loading MCP Servers</CardTitle>
            <CardDescription className="text-muted-foreground">
              Fetching available MCP servers from the registry...
            </CardDescription>
          </CardContent>
        </Card>
      )}

      {/* Servers Grid */}
      {!loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-6">
        {filteredServers.map((server, index) => (
          <div
            key={server.id}
            className="group relative p-4 rounded-lg border transition-all duration-200 shadow-sm hover:shadow-md hover:border-primary/50 h-40 flex flex-col"
            style={{
              animationDelay: `${index * 100}ms`
            }}
          >

            {/* Server Info */}
            <div className="flex flex-col h-full">
              {/* Content Section - Flexible height */}
              <div className="flex-1 flex flex-col min-h-0">
                {/* Header Section */}
                <div className="flex items-start gap-2 mb-3">
                  <div className="h-8 w-8 rounded-lg bg-primary/20 flex items-center justify-center">
                    {server.favicon_url ? (
                      <img 
                        src={server.favicon_url} 
                        alt={server.name}
                        className="h-6 w-6 rounded"
                        onError={(e) => {
                          e.currentTarget.style.display = 'none';
                          e.currentTarget.nextElementSibling?.classList.remove('hidden');
                        }}
                      />
                    ) : null}
                    <span className={`text-lg ${server.favicon_url ? 'hidden' : ''}`}>
                      {server.icon || '🔧'}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="font-medium text-foreground text-sm truncate">{server.name}</h4>
                      <Badge 
                        variant="outline"
                        className="text-[10px] px-1.5 py-0.5"
                      >
                        {server.transport?.toUpperCase() || 'HTTP'}
                      </Badge>
                    </div>
                    {server.description && (
                      <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">{server.description}</p>
                    )}
                  </div>
                </div>
                
                {/* Category Section */}
                <div className="mb-3">
                  {server.category && (
                    <div className="flex flex-wrap gap-1">
                      <Badge 
                        variant="outline"
                        className="text-[10px] px-1.5 py-0.5"
                      >
                        {server.category}
                      </Badge>
                    </div>
                  )}
                </div>
              </div>
              
              {/* Dedicated Button Section - Fixed height at bottom */}
              <div className="h-6 flex items-center justify-end pr-2 pb-1">
                  {/* <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCopyServerUrl(server);
                        }}
                        className="h-8 w-8 p-0 rounded-full bg-muted/20 hover:bg-muted/30 text-muted-foreground"
                        title="Copy server URL"
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>Copy URL to add in your favourite client</p>
                    </TooltipContent>
                  </Tooltip> */}

                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleAddMCPServer(server);
                        }}
                        className="h-8 w-8 p-0 rounded-full transition-all duration-200"
                      >
                        <Plus className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent >
                      <p>Add MCP to vMCP</p>
                    </TooltipContent>
                  </Tooltip>
              </div>
            </div>
          </div>
        ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && filteredServers.length === 0 && (
        <Card className="text-center py-12 bg-gradient-to-br from-muted/20 to-muted/10 border-2 border-dashed border-muted-foreground/30">
          <CardContent>
            <div className="h-16 w-16 rounded-full bg-muted/50 flex items-center justify-center mx-auto mb-4">
              <Server className="h-8 w-8 text-muted-foreground" />
            </div>
            <CardTitle className="text-xl font-semibold mb-2">No MCP Servers Found</CardTitle>
            <CardDescription className="text-muted-foreground">
              {searchQuery ? 'Try adjusting your search terms' : 'No MCP servers available at the moment'}
            </CardDescription>
          </CardContent>
        </Card>
      )}
    </div>
  );
}