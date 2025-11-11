
import React, { useState, useMemo, useCallback, useEffect } from 'react';
import { useRouter } from '@/hooks/useRouter';
import { Server, Container, Globe, Download, Copy, Plus, Code, MessageSquare, FolderOpen, MoreVertical, Search, X, Clock, Play } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useCommunityVMCPs } from '@/contexts/community-vmcps-context';
import { useToast } from '@/hooks/use-toast';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { FaviconIcon } from '@/components/ui/favicon-icon';
import { Input } from '@/components/ui/input';
import { SearchableMultiSelect } from '@/components/ui/searchable-select';
import { Separator } from '@/components/ui/separator';
import CommunityTab from '@/components/discover/CommunityTab';
import DemoVMCPSection from '@/components/discover/DemoVMCPSection';

export default function DiscoverPage() {
  const router = useRouter();
  const { publicVMCPS, loading } = useCommunityVMCPs();
  const { success, error: toastError } = useToast();
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);

  // Filter and categorize publicVMCPS - OSS version: only vmcps and demos (no mcps)
  const { vmcps: allVmcps, demos: allDemos, categories: availableCategories } = useMemo(() => {
    const vmcps: any[] = [];
    const demos: any[] = [];
    const categorySet = new Set<string>();

    publicVMCPS?.forEach(item => {
      // Extract category once
      const category = item.metadata?.category
        ? (typeof item.metadata.category === 'string'
          ? item.metadata.category
          : item.metadata.category.secondary || item.metadata.category.primary)
        : null;

      // Add to category set if exists
      if (category) categorySet.add(category);

      // Filter by type - only vmcps and demos for OSS
      const type = item.metadata?.type;
      if (!type || type === 'vmcp') {
        vmcps.push(item);
      } else if (type === 'demo') {
        demos.push(item);
      }
      // Skip 'mcp' type - not shown in OSS
    });

    return {
      vmcps,
      demos,
      categories: Array.from(categorySet).sort()
    };
  }, [publicVMCPS]);

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery);
    }, 300); // 300ms delay

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Handle install vMCP
  const handleInstall = async (vmcpId: string, vmcpType: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        toastError('Please log in to install vMCPs');
        return;
      }

      // Navigate to install page with the vMCP ID
      const installUrl = `/vmcp/install/${vmcpId}/${vmcpType}`;
      router.push(installUrl);
    } catch (error) {
      toastError('Failed to start installation');
    }
  };

  // Search and filter function
  const searchAndFilterVMCP = (vmcp: any, query: string, categories: string[]) => {
    // Category filtering
    if (categories.length > 0) {
      const vmcpCategory = vmcp.metadata?.category 
        ? (typeof vmcp.metadata.category === 'string' 
          ? vmcp.metadata.category 
          : vmcp.metadata.category.secondary || vmcp.metadata.category.primary)
        : null;
      
      if (!vmcpCategory || !categories.includes(vmcpCategory)) {
        return false;
      }
    }

    // Search filtering
    if (!query.trim()) return true;
    
    const searchTerm = query.toLowerCase();
    
    // Search in name
    if (vmcp.name?.toLowerCase().includes(searchTerm)) return true;
    
    // Search in description
    if (vmcp.description?.toLowerCase().includes(searchTerm)) return true;
    
    // Search in category
    if (vmcp.metadata?.category) {
      const category = typeof vmcp.metadata.category === 'string' 
        ? vmcp.metadata.category 
        : vmcp.metadata.category.secondary || vmcp.metadata.category.primary;
      if (category?.toLowerCase().includes(searchTerm)) return true;
    }
    
    // Search in MCP servers
    if (vmcp.vmcp_config?.selected_servers) {
      const serverNames = vmcp.vmcp_config.selected_servers
        .map((server: any) => server.name?.toLowerCase())
        .filter(Boolean);
      if (serverNames.some((name: string) => name.includes(searchTerm))) return true;
    }
    
    return false;
  };

  // Generate search suggestions
  const searchSuggestions = useMemo(() => {
    if (!searchQuery.trim() || searchQuery.length < 2) return [];
    
    const suggestions = new Set<string>();
    const query = searchQuery.toLowerCase();
    
    // Add vMCP names
    allVmcps.forEach(vmcp => {
      if (vmcp.name?.toLowerCase().includes(query)) {
        suggestions.add(vmcp.name);
      }
    });
    
    // Add Demo names
    allDemos.forEach(demo => {
      if (demo.name?.toLowerCase().includes(query)) {
        suggestions.add(demo.name);
      }
    });
    
    // Add categories
    [...allVmcps, ...allDemos].forEach(item => {
      if (item.metadata?.category) {
        const category = typeof item.metadata.category === 'string' 
          ? item.metadata.category 
          : item.metadata.category.secondary || item.metadata.category.primary;
        if (category?.toLowerCase().includes(query)) {
          suggestions.add(category);
        }
      }
    });
    
    // Add server names
    [...allVmcps, ...allDemos].forEach(item => {
      if (item.vmcp_config?.selected_servers) {
        item.vmcp_config.selected_servers.forEach((server: any) => {
          if (server.name?.toLowerCase().includes(query)) {
            suggestions.add(server.name);
          }
        });
      }
    });
    
    return Array.from(suggestions).slice(0, 8); // Limit to 8 suggestions
  }, [searchQuery, allVmcps, allDemos]);

  // Filter vMCPs and Demos based on debounced search query and selected categories
  const vmcps = useMemo(() => 
    allVmcps.filter(vmcp => searchAndFilterVMCP(vmcp, debouncedQuery, selectedCategories)), 
    [allVmcps, debouncedQuery, selectedCategories]
  );
  
  const demos = useMemo(() => 
    allDemos.filter(demo => searchAndFilterVMCP(demo, debouncedQuery, selectedCategories)), 
    [allDemos, debouncedQuery, selectedCategories]
  );

  if (loading) {
    return (
      <div className="min-h-screen text-foreground flex items-center justify-center">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading discovery content...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-12 w-12 rounded-lg bg-primary/20 flex items-center justify-center">
              <Globe className="h-8 w-8 text-primary" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-foreground">
                Discover
              </h1>
              <p className="text-muted-foreground">Explore vMCPs from the community</p>
            </div>
          </div>
        </div>
      </div>

      {/* Search and Filter Section */}
      <div className="mb-6">
        <div className="flex flex-col sm:flex-row gap-4">
          {/* Search Input */}
          <div className="relative flex-1 max-w-md">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Search vMCPs, categories, descriptions, or servers..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setIsSearchOpen(e.target.value.length >= 2);
                }}
                onFocus={() => setIsSearchOpen(searchQuery.length >= 2)}
                onBlur={() => {
                  // Delay closing to allow clicking on suggestions
                  setTimeout(() => setIsSearchOpen(false), 200);
                }}
                className="pl-10 pr-10 h-11"
              />
              {searchQuery && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSearchQuery('');
                    setIsSearchOpen(false);
                  }}
                  className="absolute right-1 top-1/2 transform -translate-y-1/2 h-8 w-8 p-0 hover:bg-muted"
                >
                  <X className="h-4 w-4" />
                </Button>
              )}
            </div>
            
            {/* Autosuggestion Dropdown */}
            {isSearchOpen && searchSuggestions.length > 0 && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-card border border-border rounded-md shadow-lg z-50 max-h-60 overflow-y-auto">
                <div className="p-2">
                  <div className="text-xs font-medium text-muted-foreground mb-2 px-2">Suggestions</div>
                  {searchSuggestions.map((suggestion, index) => (
                    <div
                      key={index}
                      onClick={() => {
                        setSearchQuery(suggestion);
                        setIsSearchOpen(false);
                      }}
                      className="flex items-center gap-2 px-2 py-2 rounded-sm hover:bg-muted cursor-pointer transition-colors"
                    >
                      <Clock className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm truncate">{suggestion}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Category Filter */}
          <div className="flex-1 max-w-md">
            <SearchableMultiSelect
              options={availableCategories}
              value={selectedCategories}
              onValueChange={setSelectedCategories}
              placeholder="Filter by categories..."
              searchPlaceholder="Search categories..."
              emptyText="No categories found."
              className="h-11"
            />
          </div>
        </div>
        
        {/* Results Summary */}
        {(debouncedQuery || selectedCategories.length > 0) && (
          <div className="mt-3 space-y-2">
            <div className="text-sm text-muted-foreground">
              {vmcps.length + demos.length} result{(vmcps.length + demos.length) !== 1 ? 's' : ''} found
            </div>
            {selectedCategories.length > 0 && (
              <div className="space-y-2">
                <div className="text-sm text-muted-foreground">
                  in {selectedCategories.length} categor{selectedCategories.length === 1 ? 'y' : 'ies'}:
                </div>
                <div className="flex flex-wrap gap-1 max-w-full overflow-hidden">
                  {selectedCategories.slice(0, 5).map((category) => (
                    <Badge key={category} variant="outline" className="text-[10px] px-1.5 py-0.5 flex-shrink-0">
                      {category}
                    </Badge>
                  ))}
                  {selectedCategories.length > 5 && (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Badge 
                          variant="outline" 
                          className="text-[10px] px-1.5 py-0.5 cursor-pointer hover:bg-muted/50 flex-shrink-0"
                        >
                          +{selectedCategories.length - 5} more
                        </Badge>
                      </TooltipTrigger>
                      <TooltipContent>
                        <div className="max-w-xs">
                          <p className="font-medium mb-1 text-xs">All selected categories:</p>
                          <p className="text-[10px] break-words">{selectedCategories.join(', ')}</p>
                        </div>
                      </TooltipContent>
                    </Tooltip>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

        {/* Discovery Content */}
        <Tabs defaultValue="vmcps" className="min-h-[600px]">
          <TabsList className="mb-4">
            <TabsTrigger value="vmcps" className="flex items-center gap-2">
              <Container className="h-4 w-4" />
              Community
              <Badge variant="outline" className="ml-2 text-xs">
                {vmcps.length}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="demos" className="flex items-center gap-2">
              <Play className="h-4 w-4" />
              Demo
              <Badge variant="outline" className="ml-2 text-xs">
                {demos.length}
              </Badge>
            </TabsTrigger>
          </TabsList>

          <Separator className="mb-4" />

          <TabsContent value="vmcps" className="space-y-6">
            <CommunityTab
              vmcps={vmcps}
              searchQuery={searchQuery}
              debouncedQuery={debouncedQuery}
              onInstall={handleInstall}
            />
          </TabsContent>

          <TabsContent value="demos" className="space-y-6">
            {/* Demo vMCPs */}
            {demos && demos.length > 0 && (
              <div>
                <DemoVMCPSection publicVMCPS={demos} />
              </div>
            )}

            {/* Empty state for Demos */}
            {(!demos || demos.length === 0) && (
              <Card className="text-center py-12 bg-gradient-to-br from-muted/20 to-muted/10 border-2 border-dashed border-muted-foreground/30">
                <CardContent>
                  <div className="h-16 w-16 rounded-full bg-muted/50 flex items-center justify-center mx-auto mb-4">
                    {debouncedQuery ? (
                      <Search className="h-8 w-8 text-muted-foreground" />
                    ) : (
                      <Play className="h-8 w-8 text-muted-foreground" />
                    )}
                  </div>
                  <CardTitle className="text-xl font-semibold mb-2">
                    {debouncedQuery ? 'No Demos Found' : 'No Demos Available'}
                  </CardTitle>
                  <CardDescription className="text-muted-foreground">
                    {debouncedQuery 
                      ? `No demos match "${debouncedQuery}". Try a different search term.`
                      : 'Check back later for demo vMCPs to try out'
                    }
                  </CardDescription>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        </Tabs>
      </div>
  );
}


// Public vMCPs Section Component
function PublicVMCPSection({ publicVMCPS, vmcp_type }: { publicVMCPS: any[], vmcp_type: string }) {
  const { success, error: toastError } = useToast();
  const router = useRouter();
  const handleInstall = async (vmcpId: string,vmcp_type: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        toastError('Please log in to install vMCPs');
        return;
      }

      // Navigate to install page with the vMCP ID
      const installUrl = `/vmcp/install/${vmcpId}/${vmcp_type}`;
      console.log('🔍 Router pushing to install URL:', installUrl);
      console.log('🔍 vMCP ID:', vmcpId);
      console.log('🔍 vMCP type:', vmcp_type);
      // window.location.href = installUrl;
      router.push(installUrl);
    } catch (error) {
      toastError('Failed to start installation');
    }
  };

  const handleCopyShareUrl = async (vmcp: any) => {
    try {
      // Use metadata.url if available, otherwise fallback to share URL
      const urlToCopy = vmcp.metadata?.url || `${window.location.origin}/vmcp/share/${vmcp.id}`;
      await navigator.clipboard.writeText(urlToCopy);
      success('URL copied to clipboard!');
    } catch (error) {
      toastError('Failed to copy URL');
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

  // Helper function to get stats for a specific vMCP
  const getVMCPStats = (vmcp: any) => {
    const serversCount = vmcp.vmcp_config?.selected_servers?.length || 0;
    const toolsCount = vmcp.total_tools || 0;
    const resourcesCount = vmcp.total_resources || 0;
    const promptsCount = vmcp.total_prompts || 0;

    // Debug logging
    console.log('VMCP Stats Debug:', {
      name: vmcp.name,
      total_tools: vmcp.total_tools,
      total_resources: vmcp.total_resources,
      total_prompts: vmcp.total_prompts,
      computed: { toolsCount, resourcesCount, promptsCount }
    });

    return {
      serversCount,
      toolsCount,
      resourcesCount,
      promptsCount
    };
  };

  if (publicVMCPS.length === 0) {
    return (
      <Card className="text-center py-12 bg-gradient-to-br from-muted/20 to-muted/10 border-2 border-dashed border-muted-foreground/30">
        <CardContent>
          <div className="h-16 w-16 rounded-full bg-muted/50 flex items-center justify-center mx-auto mb-4">
            <Globe className="h-8 w-8 text-muted-foreground" />
          </div>
          <CardTitle className="text-xl font-semibold mb-2">No Public vMCPs Available</CardTitle>
          <CardDescription className="text-muted-foreground">
            Check back later for vMCPs shared by the community
          </CardDescription>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      {publicVMCPS.map((publicVMCP, index) => (
        <div
          key={publicVMCP.id}
          className="group relative rounded-xl border transition-all duration-200 shadow-sm cursor-pointer hover:shadow-lg hover:border-primary/50 bg-card overflow-hidden h-72 flex flex-col"
          onClick={() => handleInstall(publicVMCP.id, vmcp_type)}
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
                      // Fallback to default icon if image fails to load
                      e.currentTarget.style.display = 'none';
                      e.currentTarget.nextElementSibling?.classList.remove('hidden');
                    }}
                  />
                ) : null}
                {vmcp_type === 'mcp' ? (
                  <Server className={`h-5 w-5 text-primary ${getIconSource(publicVMCP) ? 'hidden' : ''}`} />
                ) : vmcp_type === 'demo' ? (
                  <Play className={`h-5 w-5 text-primary ${getIconSource(publicVMCP) ? 'hidden' : ''}`} />
                ) : (
                  <Container className={`h-5 w-5 text-primary ${getIconSource(publicVMCP) ? 'hidden' : ''}`} />
                )}
              </div>
              <div className="flex-1 min-w-0">
                {/* Name Section */}
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
             {/* Category Section - Dedicated section below name */}
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
              <p className="text-xs pb-2 text-muted-foreground leading-relaxed line-clamp-3 min-h-[3rem]">{publicVMCP.description}</p>
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
          
          {/* Stats Section - Dedicated bottom section */}
          <div className="px-4 py-4 border-t border-border/30 mt-auto">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-1">
                  <span className="font-medium text-foreground text-xs">{getVMCPStats(publicVMCP).toolsCount}</span>
                  <span className="text-muted-foreground text-xs">tools</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="font-medium text-foreground text-xs">{getVMCPStats(publicVMCP).promptsCount}</span>
                  <span className="text-muted-foreground text-xs">prompts</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="font-medium text-foreground text-xs">{getVMCPStats(publicVMCP).resourcesCount}</span>
                  <span className="text-muted-foreground text-xs">resources</span>
                </div>
              </div>
              {/* Copy Button */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleCopyShareUrl(publicVMCP);
                    }}
                    className="h-8 w-8 p-0 rounded-full transition-all duration-200"
                    title={publicVMCP.metadata?.url ? "Copy URL" : "No URL to copy"}
                    disabled={!publicVMCP.metadata?.url}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p className='text-xs'> {(publicVMCP.metadata?.url ? "Copy MCP URL" : "Error: no MCP URL to copy")}</p>
                </TooltipContent>
              </Tooltip>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}