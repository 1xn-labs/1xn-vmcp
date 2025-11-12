
import React, { useState, useRef } from 'react';
import { useRouter } from '@/hooks/useRouter';
import { Plus, Trash2, Container, Edit, Share2, Globe, Lock, MoreVertical, RefreshCw, AlertTriangle, ExternalLink, HelpCircle, Server, ServerIcon, Code, MessageSquare, FolderOpen, Download, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Modal } from '@/components/ui/modal';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useVMCP, useVMCPState } from '@/contexts/vmcp-context';
import { useCreateVMCPModal } from '@/contexts/create-vmcp-modal-context';
// import { newApi } from '@/lib/new-api';
import { apiClient } from '@/api/client';
import { useToast } from '@/hooks/use-toast';
import { VMCPShareDialog } from '@/components/vmcp/VMCPShareDialog';
import { FaviconIcon } from '@/components/ui/favicon-icon';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import VMCPCardActionsMenu from '@/components/vmcp/VMCPCardActionsMenu';

export default function VMCPPage() {
  const router = useRouter();
  const { loading, error, forceRefreshVMCPData, initialized, deleteVMCP } = useVMCP();
  const { vmcps } = useVMCPState();
  const { success, error: toastError } = useToast();
  const { openModal } = useCreateVMCPModal();
  const [sharingStates, setSharingStates] = useState<Record<string, boolean>>({});
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [vmcpToDelete, setVmcpToDelete] = useState<any>(null);
  const [deleting, setDeleting] = useState(false);
  const [shareDialogOpen, setShareDialogOpen] = useState(false);
  const [vmcpToShare, setVmcpToShare] = useState<any>(null);
  const [helpDialogOpen, setHelpDialogOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [importing, setImporting] = useState(false);

  // Helper function to get stats for a specific vMCP from the context data
  const getVMCPStats = (vmcp: any) => {
    // Use the pre-calculated totals from the API response
    const serversCount = vmcp.vmcp_config?.selected_servers?.length || 0;
    const toolsCount = vmcp.total_tools || 0;
    const resourcesCount = vmcp.total_resources || 0;
    const promptsCount = vmcp.total_prompts || 0;

    return {
      serversCount,
      toolsCount,
      resourcesCount,
      promptsCount
    };
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

  // Handle share functionality
  const handleShare = async (vmcpId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        toastError('Please log in to share vMCPs');
        return;
      }

      // Call the shareVMCP endpoint to make the vMCP public
      setSharingStates(prev => ({ ...prev, [vmcpId]: true }));

      const response = await apiClient.shareVMCP(vmcpId, {
        state: 'shared',
        tags: []
      }, accessToken);

      if (response.success) {
        success('vMCP is now public and ready to share!');
        // Refresh the vMCP data to get the updated state
        forceRefreshVMCPData();

        // Find the vMCP to share and open the dialog
        const allVmcps = [...vmcps.private, ...vmcps.public];
        const vmcp = allVmcps.find(v => v.id === vmcpId);
        if (vmcp) {
          setVmcpToShare(vmcp);
          setShareDialogOpen(true);
        }
      } else {
        toastError(response.error || 'Failed to make vMCP public');
      }
    } catch (error) {
      toastError('Failed to share vMCP');
    } finally {
      setSharingStates(prev => ({ ...prev, [vmcpId]: false }));
    }
  };

  // Handle make public/private functionality
  const handleTogglePublic = async (vmcpId: string, isPublic: boolean) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        toastError('Please log in to manage vMCP visibility');
        return;
      }

      setSharingStates(prev => ({ ...prev, [vmcpId]: true }));

      const response = await apiClient.shareVMCP(vmcpId, {
        state: isPublic ? 'public' : 'private',
        tags: []
      }, accessToken);

      if (response.success) {
        success(isPublic ? 'vMCP is now public!' : 'vMCP is now private');
        // Refresh both user vMCPs and public vMCPs to get the updated state
        forceRefreshVMCPData();
      } else {
        toastError(response.error || 'Failed to update vMCP visibility');
      }
    } catch (error) {
      toastError('Failed to update vMCP visibility');
    } finally {
      setSharingStates(prev => ({ ...prev, [vmcpId]: false }));
    }
  };

  // Handle delete functionality
  const handleDeleteClick = (vmcp: any) => {
    setVmcpToDelete(vmcp);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!vmcpToDelete) return;

    setDeleting(true);
    try {
      const deleteSuccess = await deleteVMCP(vmcpToDelete.id);
      if (deleteSuccess) {
        success(`vMCP "${vmcpToDelete.name}" deleted successfully`);
        // Refresh the vMCP data
        forceRefreshVMCPData();
      } else {
        toastError('Failed to delete vMCP');
      }
    } catch (error) {
      toastError('Failed to delete vMCP');
    } finally {
      setDeleting(false);
      setDeleteDialogOpen(false);
      setVmcpToDelete(null);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setVmcpToDelete(null);
  };

  const handleShareClose = () => {
    setShareDialogOpen(false);
    setVmcpToShare(null);
  };

  // Handle export vMCP config
  const handleExportConfig = async (vmcp: any) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        toastError('Please log in to export vMCP configuration');
        return;
      }

      // Fetch the full vMCP configuration using getVMCPDetails
      const response = await apiClient.getVMCPDetails(vmcp.id, accessToken);
      if (!response.success || !response.data) {
        toastError('Failed to fetch vMCP configuration');
        return;
      }

      // Create a clean export object (remove id, created_at, updated_at, user_id, etc.)
      const exportData = {
        name: response.data.name,
        description: response.data.description,
        vmcp_config: response.data.vmcp_config,
        custom_prompts: response.data.custom_prompts || [],
        custom_tools: response.data.custom_tools || [],
        custom_resources: response.data.custom_resources || [],
        environment_variables: response.data.environment_variables || [],
        system_prompt: response.data.system_prompt,
        metadata: response.data.metadata || {}
      };

      // Convert to JSON and create download
      const jsonString = JSON.stringify(exportData, null, 2);
      const blob = new Blob([jsonString], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${vmcp.name.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_config.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      success('vMCP configuration exported successfully');
    } catch (error) {
      console.error('Export error:', error);
      toastError('Failed to export vMCP configuration');
    }
  };

  // Handle import vMCP config
  const handleImportConfig = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setImporting(true);
    try {
      const accessToken = localStorage.getItem('access_token') || (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);
      if (!accessToken) {
        toastError('Please log in to import vMCP configuration');
        return;
      }

      // Read the file
      const fileContent = await file.text();
      const importData = JSON.parse(fileContent);

      // Validate the imported data
      if (!importData.name || !importData.vmcp_config) {
        toastError('Invalid vMCP configuration file');
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
      setImporting(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  // Use the new data structure
  const myVMCPS = vmcps.private || [];
  const publicVMCPS = vmcps.public || []; // These are user's public VMCPs, not community VMCPs

  // Check if Community tab should be shown (Enterprise only, not OSS)
  const showCommunityTab = import.meta.env.VITE_VMCP_OSS_BUILD !== 'true';

  if (loading && !initialized) {
    return (
      <div className="min-h-screen text-foreground flex items-center justify-center">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading vMCP containers...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen text-foreground flex items-center justify-center">
        <div className="text-center">
          <p className="text-destructive">Error: {error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen  text-foreground">
      <div className="relative mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-12 w-12 rounded-xl bg-primary/20 flex items-center justify-center">
                <Container className="h-8 w-8 text-primary" />
              </div>
              <div>
                <h1 className="text-3xl font-bold text-foreground">
                  vMCPs
                </h1>
                <p className="text-muted-foreground">Manage your virtual Model Context Protocol configurations</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <input
                ref={fileInputRef}
                type="file"
                accept=".json"
                onChange={handleImportConfig}
                className="hidden"
              />
              <Button
                onClick={handleImportClick}
                disabled={importing}
                variant="outline"
                size="sm"
              >
                {importing ? (
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Upload className="h-4 w-4 mr-2" />
                )}
                Import vMCP
              </Button>
              <Button
                onClick={() => setHelpDialogOpen(true)}
                variant="outline"
                size="sm"
              >
                <HelpCircle className="h-4 w-4 mr-2" />
                Help
              </Button>
              <Button
                onClick={forceRefreshVMCPData}
                disabled={loading}
                variant="outline"
              >
                <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <Tabs defaultValue="myvmcps" className="min-h-[600px]">
          <TabsList className="mb-6">
            <TabsTrigger value="myvmcps" className="flex items-center gap-2">
              <Container className="h-4 w-4" />
              Private
              <Badge variant="outline" className="ml-2 text-xs">
                {myVMCPS.length}
              </Badge>
            </TabsTrigger>
            {showCommunityTab && (
              <TabsTrigger value="publicvmcps" className="flex items-center gap-2">
                <Globe className="h-4 w-4" />
                Community
                <Badge variant="outline" className="ml-2 text-xs">
                  {publicVMCPS.length}
                </Badge>
              </TabsTrigger>
            )}
          </TabsList>

          <TabsContent value="myvmcps" className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {/* Create New vMCP Card */}
              {myVMCPS.length !== 0 && (<div
                className="group relative p-4 rounded-lg border-2 border-dashed border-muted-foreground/30 transition-all duration-200 shadow-sm cursor-pointer hover:shadow-md hover:border-primary/50 flex flex-col"
                onClick={() => openModal()}
              >
                <div className="flex flex-col h-full items-center justify-center text-center">
                  <div className="h-8 w-8 rounded-lg bg-muted/50 flex items-center justify-center mb-3 group-hover:bg-primary/20 transition-colors">
                    <Plus className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
                  </div>
                  <h4 className="font-medium text-foreground text-sm mb-1">Create New vMCP</h4>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Build a new virtual MCP container
                  </p>
                </div>
              </div>)}

              {/* My vMCP Containers */}
              {myVMCPS.map((vmcp, index) => (
                <div
                  key={vmcp.id}
                  className="group relative rounded-xl border transition-all duration-200 shadow-sm cursor-pointer hover:shadow-lg hover:border-primary/50 bg-card overflow-hidden h-48 flex flex-col"
                  onClick={() => router.push(`/vmcp/${vmcp.id}`)}
                  style={{
                    animationDelay: `${index * 100}ms`
                  }}
                >
                  {/* Three-dot Menu */}
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={(e) => e.stopPropagation()}
                        className="absolute top-3 right-3 h-8 w-8 p-0 rounded-full transition-all duration-200 bg-background/80 backdrop-blur-sm hover:bg-background text-muted-foreground opacity-0 group-hover:opacity-100 z-10 shadow-sm"
                        title="More actions"
                      >
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <VMCPCardActionsMenu
                      vmcp={vmcp}
                      onEdit={(id) => router.push(`/vmcp/${id}`)}
                      onDelete={handleDeleteClick}
                      onExport={handleExportConfig}
                      onShare={handleShare}
                      onTogglePublic={handleTogglePublic}
                      sharingStates={sharingStates}
                      isPublic={vmcp.is_public}
                    />
                  </DropdownMenu>

                  {/* Main Content */}
                  <div className="p-4 pb-0 flex flex-col flex-1">
                    {/* Header Section */}
                    <div className="flex items-start gap-3 mb-3">
                      <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary/20 to-primary/10 flex items-center justify-center overflow-hidden shadow-sm">
                        {getIconSource(vmcp) ? (
                          <img
                            src={getIconSource(vmcp)}
                            alt={vmcp.name}
                            className="h-6 w-6 object-contain"
                            onError={(e) => {
                              // Fallback to default icon if image fails to load
                              e.currentTarget.style.display = 'none';
                              e.currentTarget.nextElementSibling?.classList.remove('hidden');
                            }}
                          />
                        ) : null}
                        <Container className={`h-5 w-5 text-primary ${getIconSource(vmcp) ? 'hidden' : ''}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          <h4 className="font-semibold text-foreground text-sm truncate">{vmcp.name}</h4>
                          {vmcp.is_public && (
                            <Badge
                              variant="secondary"
                              className="text-[10px] px-2 py-1 rounded-md font-medium"
                            >
                              <Globe className="h-2.5 w-2.5 mr-1" />
                              Shared
                            </Badge>
                          )}
                        </div>
                        {vmcp.description && (
                          <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2 min-h-[2.5rem]">{vmcp.description}</p>
                        )}
                      </div>
                    </div>

                    {/* MCP Servers Section */}
                    <div className="mb-2 min-h-[28px]">
                      {vmcp.vmcp_config?.selected_servers && vmcp.vmcp_config.selected_servers.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {vmcp.vmcp_config.selected_servers.slice(0, 3).map((server: any, serverIndex: number) => (
                            <div key={serverIndex} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-muted/40 hover:bg-muted/60 transition-colors">
                              <FaviconIcon
                                url={server.url}
                                faviconUrl={server.favicon_url}
                                className="h-3 w-3"
                                size={12}
                              />
                              <span className="text-xs font-medium truncate max-w-20">{server.name}</span>
                            </div>
                          ))}
                          {vmcp.vmcp_config.selected_servers.length > 3 && (
                            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-muted/40">
                              <span className="text-xs font-medium text-muted-foreground">
                                +{vmcp.vmcp_config.selected_servers.length - 3}
                              </span>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="min-h-[28px] flex items-center">
                          <span className="text-xs text-muted-foreground">No MCP servers added</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Stats Section - Dedicated bottom section */}
                  <div className="px-4 py-3 border-t border-border/30 mt-auto">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-6">
                        <div className="flex items-center gap-1">
                          <span className="font-medium text-foreground text-xs">{getVMCPStats(vmcp).toolsCount}</span>
                          <span className="text-muted-foreground text-xs">tools</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <span className="font-medium text-foreground text-xs">{getVMCPStats(vmcp).promptsCount}</span>
                          <span className="text-muted-foreground text-xs">prompts</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <span className="font-medium text-foreground text-xs">{getVMCPStats(vmcp).resourcesCount}</span>
                          <span className="text-muted-foreground text-xs">resources</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}

              {/* Empty State for My vMCPs */}
              {myVMCPS.length === 0 && (
                <div className="col-span-full text-center py-16 mt-8 bg-gradient-to-br from-muted/20 to-muted/10 border-2 border-dashed border-muted-foreground/30 rounded-lg">
                  {/* Architecture Diagram */}
                  <div className="mb-8">
                    <img
                      src={`/app/1xn-arch.png`}
                      alt="1xN vMCP Architecture"
                      className="mx-auto max-w-full h-auto max-h-72 mb-6"
                    />
                  </div>

                  {/* Hero Content */}
                  <div className="max-w-2xl mx-auto mb-8">
                    <h3 className="text-3xl font-bold mb-2 bg-gradient-to-r from-primary to-accent text-transparent bg-clip-text">
                      Welcome to 1xN
                    </h3>
                    <p className="text-sm mb-2 text-muted-foreground font-mono">
                      "One MCP to rule them all...and in the context bind them"
                    </p>

                    <div className="bg-primary/10 border border-primary/20 rounded-lg p-6 mb-8 text-left">
                      <h4 className="font-semibold text-foreground mb-3 text-center">Context Engineering Made Simple</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                        <div className="flex items-start gap-2">
                          <div className="h-2 w-2 bg-primary rounded-full mt-2"></div>
                          <span className="text-muted-foreground">Build virtual MCP (vMCPs) in minutes</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <div className="h-2 w-2 bg-primary rounded-full mt-2"></div>
                          <span className="text-muted-foreground">Turn off dangerous or unused tools</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <div className="h-2 w-2 bg-primary rounded-full mt-2"></div>
                          <span className="text-muted-foreground">Secure your AI workflows and agents</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <div className="h-2 w-2 bg-primary rounded-full mt-2"></div>
                          <span className="text-muted-foreground">Mix multiple MCPs seamlessly</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
                    <Button
                      onClick={() => openModal()}
                      variant="default"
                    >
                      <Plus className="h-5 w-5" />
                      Create Your First vMCP
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => router.push('/discover')}
                    >
                      <Globe className="h-5 w-5" />
                      Explore Community
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setHelpDialogOpen(true)}
                    >
                      <HelpCircle className="h-3 w-3" />
                      Learn More
                    </Button>
                  </div>

                </div>
              )}
            </div>
          </TabsContent>

          {showCommunityTab && (
            <TabsContent value="publicvmcps" className="space-y-6">
            <div className="text-left py-2 text-muted-foreground">
              <p className="text-sm">Below are the list of public vMCPs you have added to your collection. These are read-only vMCPs. To modify capabilities, fork them / make a copy and start extending the vMCPs.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {/* Public vMCP Containers */}
              {publicVMCPS.map((vmcp, index) => (
                <div
                  key={vmcp.id}
                  className="group relative rounded-xl border transition-all duration-200 shadow-sm cursor-pointer hover:shadow-lg hover:border-primary/50 bg-card overflow-hidden h-48 flex flex-col"
                  onClick={() => router.push(`/vmcp/${vmcp.id}`)}
                  style={{
                    animationDelay: `${index * 100}ms`
                  }}
                >
                  {/* Three-dot Menu */}
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={(e) => e.stopPropagation()}
                        className="absolute top-3 right-3 h-8 w-8 p-0 rounded-full transition-all duration-200 bg-background/80 backdrop-blur-sm hover:bg-background text-muted-foreground opacity-0 group-hover:opacity-100 z-10 shadow-sm"
                        title="More actions"
                      >
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-48">
                      {/* Manage Action */}
                      <DropdownMenuItem
                        onClick={(e) => {
                          e.stopPropagation();
                          router.push(`/vmcp/${vmcp.id}`);
                        }}
                        className="flex items-center gap-2"
                      >
                        <Edit className="h-4 w-4" />
                        Manage
                      </DropdownMenuItem>

                      {/* Export Action */}
                      <DropdownMenuItem
                        onClick={(e) => {
                          e.stopPropagation();
                          handleExportConfig(vmcp);
                        }}
                        className="flex items-center gap-2"
                      >
                        <Download className="h-4 w-4" />
                        Export Config
                      </DropdownMenuItem>

                      <DropdownMenuSeparator />

                      {/* Delete Action */}
                      <DropdownMenuItem
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteClick(vmcp);
                        }}
                        className="flex items-center gap-2 text-destructive focus:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>

                  {/* Main Content */}
                  <div className="p-4 pb-0 flex flex-col flex-1">
                    {/* Header Section */}
                    <div className="flex items-start gap-3 mb-3">
                      <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary/20 to-primary/10 flex items-center justify-center overflow-hidden shadow-sm">
                        {getIconSource(vmcp) ? (
                          <img
                            src={getIconSource(vmcp)}
                            alt={vmcp.name}
                            className="h-6 w-6 object-contain"
                            onError={(e) => {
                              // Fallback to default icon if image fails to load
                              e.currentTarget.style.display = 'none';
                              e.currentTarget.nextElementSibling?.classList.remove('hidden');
                            }}
                          />
                        ) : null}
                        <Container className={`h-5 w-5 text-primary ${getIconSource(vmcp) ? 'hidden' : ''}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          {vmcp.name.startsWith('@') ? (
                            <div className="flex flex-col flex-1 min-w-0">
                              <span className="text-xs text-muted-foreground font-medium">
                                {vmcp.name.split('/')[0]}/
                              </span>
                              <div className="flex items-center gap-2">
                                <h4 className="font-semibold text-foreground text-sm truncate">
                                  {vmcp.name.split('/').slice(1).join('/')}
                                </h4>
                              </div>
                            </div>
                          ) : (
                            <div className="flex items-center gap-2 flex-1 min-w-0">
                              <h4 className="font-semibold text-foreground text-sm truncate">{vmcp.name}</h4>
                            </div>
                          )}
                        </div>
                        {vmcp.description && (
                          <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2 min-h-[2.5rem]">{vmcp.description}</p>
                        )}
                      </div>
                    </div>

                    {/* MCP Servers Section */}
                    <div className="mb-2 min-h-[28px]">
                      {vmcp.vmcp_config?.selected_servers && vmcp.vmcp_config.selected_servers.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {vmcp.vmcp_config.selected_servers.slice(0, 3).map((server: any, serverIndex: number) => (
                            <div key={serverIndex} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-muted/40 hover:bg-muted/60 transition-colors">
                              <FaviconIcon
                                url={server.url}
                                faviconUrl={server.favicon_url}
                                className="h-3 w-3"
                                size={12}
                              />
                              <span className="text-xs font-medium truncate max-w-20">{server.name}</span>
                            </div>
                          ))}
                          {vmcp.vmcp_config.selected_servers.length > 3 && (
                            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-muted/40">
                              <span className="text-xs font-medium text-muted-foreground">
                                +{vmcp.vmcp_config.selected_servers.length - 3}
                              </span>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="min-h-[28px] flex items-center">
                          <span className="text-xs text-muted-foreground">No MCP servers</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Stats Section - Dedicated bottom section */}
                  <div className="px-4 py-3 border-t border-border/30 mt-auto">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-6">
                        <div className="flex items-center gap-1">
                          <span className="font-medium text-foreground text-xs">{getVMCPStats(vmcp).toolsCount}</span>
                          <span className="text-muted-foreground text-xs">tools</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <span className="font-medium text-foreground text-xs">{getVMCPStats(vmcp).promptsCount}</span>
                          <span className="text-muted-foreground text-xs">prompts</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <span className="font-medium text-foreground text-xs">{getVMCPStats(vmcp).resourcesCount}</span>
                          <span className="text-muted-foreground text-xs">resources</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}

              {/* Empty State for Public vMCPs */}
              {publicVMCPS.length === 0 && (
                <div className="col-span-full text-center py-16 mt-8 bg-gradient-to-br from-muted/20 to-muted/10 border-2 border-dashed border-muted-foreground/30 rounded-lg">
                  <div className="h-16 w-16 rounded-full bg-gradient-to-br from-primary/20 to-primary/10 flex items-center justify-center mx-auto mb-6">
                    <Globe className="h-8 w-8 text-primary" />
                  </div>
                  <h3 className="text-2xl font-semibold mb-3">No Community vMCPs Yet</h3>
                  <div className="max-w-md mx-auto space-y-4">
                    <p className="text-muted-foreground">
                      Discover and add vMCPs shared by the 1xN community to expand your toolkit.
                    </p>
                    <div className="bg-muted/30 border border-border rounded-lg p-4">
                      <p className="text-sm text-muted-foreground">
                        💡 <strong>Pro tip:</strong> Share your own vMCPs to help others and build the community library!
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-col sm:flex-row p-4 gap-4 justify-center items-center">
                    <Button
                      onClick={() => openModal()}
                      variant="default"
                    >
                      <Plus className="h-5 w-5" />
                      Create Your First vMCP
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => router.push('/discover')}
                    >
                      <Globe className="h-5 w-5" />
                      Explore Community
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setHelpDialogOpen(true)}
                    >
                      <HelpCircle className="h-3 w-3" />
                      Learn More
                    </Button>
                  </div>
                </div>)}
            </div>
          </TabsContent>
          )}
        </Tabs>

        {/* Discover Call-to-action for users with existing vMCPs */}
        {(vmcps.private.length > 0 || vmcps.public.length > 0) && (
          <div className="text-center py-12 mt-16 bg-gradient-to-br from-primary/5 to-primary/10 border-2 border-primary/20 rounded-lg">
            <div className="h-16 w-16 rounded-full bg-primary/20 flex items-center justify-center mx-auto mb-4">
              <Globe className="h-8 w-8 text-primary" />
            </div>
            <h3 className="text-xl font-semibold mb-2">Discover More</h3>
            <p className="text-muted-foreground mb-6">
              Explore community vMCPs and MCP servers to extend your capabilities
            </p>
            <Button
              onClick={() => router.push('/discover')}
              className="flex items-center gap-2 mx-auto"
            >
              <ExternalLink className="h-4 w-4" />
              Explore Community
            </Button>
          </div>
        )}

      </div>

      {/* Delete Confirmation Dialog */}
      {deleteDialogOpen && vmcpToDelete && (
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
                  <strong>Warning:</strong> This action cannot be undone!
                </p>
              </div>

              <p className="text-sm text-foreground">
                Are you sure you want to delete vMCP <strong>"{vmcpToDelete.name}"</strong>?
              </p>

              <p className="text-xs text-muted-foreground">
                All configuration, tools, resources, and prompts associated with this vMCP will be permanently removed.
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
                    <span>Delete vMCP</span>
                  </div>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Share Dialog */}
      {shareDialogOpen && vmcpToShare && (
        <VMCPShareDialog
          isOpen={shareDialogOpen}
          onClose={handleShareClose}
          vmcp={vmcpToShare}
        />
      )}

      {/* Help Dialog */}
      <Modal
        isOpen={helpDialogOpen}
        onClose={() => setHelpDialogOpen(false)}
        title="vMCP Help & Overview"
        size="xl"
      >
        <div className="space-y-6 max-h-[70vh] overflow-y-auto">
          {/* Hero Section */}
          <div className="text-center border-b border-border pb-6">
            <img
              src={`/app/1xn-arch.png`}
              alt="1xN vMCP Architecture"
              className="mx-auto max-w-full h-auto mb-4 rounded-lg shadow-sm"
            />
            <div className="space-y-1">
              <p className="text-muted-foreground italic text-lg">
                "...and in the context bind them"
              </p>
              <p className="text-xs text-muted-foreground">
                A management layer for MCPs - The right way to use MCPs in your clients and agents
              </p>
            </div>
          </div>

          {/* Introduction */}
          <div className="space-y-6">
            <div>
              <h4 className="text-lg font-semibold text-foreground mb-3 flex items-center gap-2">
                <Container className="h-5 w-5 text-primary" />
                What is 1xN?
              </h4>
              <div className="bg-gradient-to-r from-primary/5 to-primary/10 border border-primary/20 rounded-lg p-4">
                <p className="text-muted-foreground mb-2">
                  Build and deploy virtual MCPs (vMCPs) in minutes. It's like <strong>Lego for MCPs and agents!</strong>
                </p>
                <ul className="text-sm text-muted-foreground space-y-1">
                  <li>• <strong>Context Engineering:</strong> Personalise, compose and extend MCPs with vMCPs</li>
                  <li>• <strong>One setup, use everywhere:</strong> Claude, Claude Code, VS Code, Gemini, Cursor, any MCP client</li>
                  <li>• <strong>Use privately or share</strong> your vMCP creations with others</li>
                </ul>
              </div>
            </div>

            <div>
              <h4 className="text-lg font-semibold text-foreground mb-3 flex items-center gap-2">
                <Code className="h-5 w-5 text-primary" />
                What the vMCP?
              </h4>
              <div className="bg-muted/30 border border-border rounded-lg p-4">
                <p className="text-muted-foreground mb-3">
                  vMCPs are <strong>virtual, logical, secure MCP containers</strong> for every usecase. Context engineering is really important!
                </p>
                <div className="grid grid-cols-1 gap-2 text-sm">
                  <div className="flex items-start gap-2">
                    <div className="h-1.5 w-1.5 bg-destructive rounded-full mt-2"></div>
                    <span className="text-muted-foreground">Turn off dangerous or unused tools from any MCP. <strong>No more context rot and tool confusion</strong></span>
                  </div>
                  <div className="flex items-start gap-2">
                    <div className="h-1.5 w-1.5 bg-green-500 rounded-full mt-2"></div>
                    <span className="text-muted-foreground">Secure your AI workflows and agents. <strong>No unintended tool calls and no unforseen injection attacks</strong></span>
                  </div>
                  <div className="flex items-start gap-2">
                    <div className="h-1.5 w-1.5 bg-blue-500 rounded-full mt-2"></div>
                    <span className="text-muted-foreground">Mix multiple MCPs and take full advantage of the MCP protocol - <strong>above and beyond official MCP</strong></span>
                  </div>
                </div>
              </div>
            </div>

            <div>
              <h4 className="text-lg font-semibold text-foreground mb-3 flex items-center gap-2">
                <Server className="h-5 w-5 text-primary" />
                Powerful Features
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="bg-muted/20 border border-border rounded-lg p-3 hover:bg-muted/30 transition-colors">
                  <div className="flex items-center gap-2 mb-1">
                    <FolderOpen className="h-4 w-4 text-primary" />
                    <h5 className="font-medium text-foreground">Tool & Resource Curation</h5>
                  </div>
                  <p className="text-sm text-muted-foreground">Select specific tools and resources from any MCP server</p>
                </div>
                <div className="bg-muted/20 border border-border rounded-lg p-3 hover:bg-muted/30 transition-colors">
                  <div className="flex items-center gap-2 mb-1">
                    <Plus className="h-4 w-4 text-primary" />
                    <h5 className="font-medium text-foreground">Custom Components</h5>
                  </div>
                  <p className="text-sm text-muted-foreground">Add your own tools, prompts, and resources</p>
                </div>
                <div className="bg-muted/20 border border-border rounded-lg p-3 hover:bg-muted/30 transition-colors">
                  <div className="flex items-center gap-2 mb-1">
                    <MessageSquare className="h-4 w-4 text-primary" />
                    <h5 className="font-medium text-foreground">Prompt as Tools</h5>
                  </div>
                  <p className="text-sm text-muted-foreground">Expose prompts as MCP tools for automatic client execution</p>
                </div>
                <div className="bg-muted/20 border border-border rounded-lg p-3 hover:bg-muted/30 transition-colors">
                  <div className="flex items-center gap-2 mb-1">
                    <Code className="h-4 w-4 text-primary" />
                    <h5 className="font-medium text-foreground">System Prompts</h5>
                  </div>
                  <p className="text-sm text-muted-foreground">Configure system prompts on vMCPs for custom agents</p>
                </div>
                <div className="bg-muted/20 border border-border rounded-lg p-3 hover:bg-muted/30 transition-colors">
                  <div className="flex items-center gap-2 mb-1">
                    <FolderOpen className="h-4 w-4 text-primary" />
                    <h5 className="font-medium text-foreground">File Resources</h5>
                  </div>
                  <p className="text-sm text-muted-foreground">Add files as MCP resources directly in your vMCP</p>
                </div>
                <div className="bg-muted/20 border border-border rounded-lg p-3 hover:bg-muted/30 transition-colors">
                  <div className="flex items-center gap-2 mb-1">
                    <RefreshCw className="h-4 w-4 text-primary" />
                    <h5 className="font-medium text-foreground">Full Observability</h5>
                  </div>
                  <p className="text-sm text-muted-foreground">Complete visibility of all MCP activity at protocol level</p>
                </div>
              </div>
            </div>

            <div>
              <h4 className="text-lg font-semibold text-foreground mb-3 flex items-center gap-2">
                <Globe className="h-5 w-5 text-primary" />
                Universal Compatibility
              </h4>
              <div className="bg-primary/10 border border-primary/20 rounded-lg p-4">
                <p className="text-muted-foreground mb-3 text-center">
                  <strong>One setup, use everywhere</strong> - Connect any MCP-compatible client:
                </p>
                <div className="flex flex-wrap gap-2 justify-center">
                  <Badge variant="secondary" className="bg-primary/10 text-primary border-primary/20">Claude Desktop</Badge>
                  <Badge variant="secondary" className="bg-primary/10 text-primary border-primary/20">Claude Code</Badge>
                  <Badge variant="secondary" className="bg-primary/10 text-primary border-primary/20">VS Code</Badge>
                  <Badge variant="secondary" className="bg-primary/10 text-primary border-primary/20">Cursor</Badge>
                  <Badge variant="secondary" className="bg-primary/10 text-primary border-primary/20">Gemini</Badge>
                  <Badge variant="secondary" className="bg-primary/10 text-primary border-primary/20">Custom Agents</Badge>
                </div>
              </div>
            </div>

            <div>
              <h4 className="text-lg font-semibold text-foreground mb-3 flex items-center gap-2">
                <MessageSquare className="h-5 w-5 text-primary" />
                Perfect For
              </h4>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex items-center gap-2 text-sm text-muted-foreground p-2 bg-muted/20 rounded-lg">
                  <div className="h-2 w-2 bg-blue-500 rounded-full"></div>
                  Code development & Testing
                </div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground p-2 bg-muted/20 rounded-lg">
                  <div className="h-2 w-2 bg-green-500 rounded-full"></div>
                  Writing blogs & PRDs
                </div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground p-2 bg-muted/20 rounded-lg">
                  <div className="h-2 w-2 bg-purple-500 rounded-full"></div>
                  Agentic workflows
                </div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground p-2 bg-muted/20 rounded-lg">
                  <div className="h-2 w-2 bg-orange-500 rounded-full"></div>
                  Testing & prototyping
                </div>
              </div>
            </div>

            <div>
              <h4 className="text-lg font-semibold text-foreground mb-3 flex items-center gap-2">
                <Plus className="h-5 w-5 text-primary" />
                Quick Start Guide
              </h4>
              <div className="space-y-3">
                <div className="flex items-start gap-3 p-3 bg-muted/20 rounded-lg hover:bg-muted/30 transition-colors">
                  <div className="h-7 w-7 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-bold shrink-0">1</div>
                  <div>
                    <p className="text-sm font-medium text-foreground">Create your first vMCP</p>
                    <p className="text-xs text-muted-foreground">Click "Create Your First vMCP" to get started</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 bg-muted/20 rounded-lg hover:bg-muted/30 transition-colors">
                  <div className="h-7 w-7 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-bold shrink-0">2</div>
                  <div>
                    <p className="text-sm font-medium text-foreground">Add MCP servers</p>
                    <p className="text-xs text-muted-foreground">Visit "Servers" page or browse the "Discover" marketplace</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 bg-muted/20 rounded-lg hover:bg-muted/30 transition-colors">
                  <div className="h-7 w-7 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-bold shrink-0">3</div>
                  <div>
                    <p className="text-sm font-medium text-foreground">Configure your vMCP</p>
                    <p className="text-xs text-muted-foreground">Curate tools, resources, and add custom prompts</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 bg-muted/20 rounded-lg hover:bg-muted/30 transition-colors">
                  <div className="h-7 w-7 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-bold shrink-0">4</div>
                  <div>
                    <p className="text-sm font-medium text-foreground">Connect your client</p>
                    <p className="text-xs text-muted-foreground">Use your vMCP with any MCP-compatible client</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="pt-4 border-t border-border">
              <div className="flex flex-col sm:flex-row gap-3 justify-center">
                <Button
                  onClick={() => {
                    setHelpDialogOpen(false);
                    openModal();
                  }}
                  className="flex items-center gap-2"
                >
                  <Plus className="h-4 w-4" />
                  Create Your First vMCP
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    setHelpDialogOpen(false);
                    router.push('/discover');
                  }}
                  className="flex items-center gap-2"
                >
                  <ExternalLink className="h-4 w-4" />
                  Explore Community
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    setHelpDialogOpen(false);
                    router.push('/servers');
                  }}
                  className="flex items-center gap-2"
                >
                  <Server className="h-4 w-4" />
                  Add Servers
                </Button>
              </div>
            </div>
          </div>
        </div>
      </Modal>

    </div>
  );
}

