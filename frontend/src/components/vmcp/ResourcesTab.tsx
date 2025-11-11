// components/ResourcesTab.tsx

import { useState } from 'react';
import { Upload, FileText, Trash2, Edit, Save, X, Server, FolderOpen, ChevronDown, Eye, Calendar, Type } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { VMCPConfig, Resource } from '@/types/vmcp';
import { cn } from '@/lib/utils';
// import { newApi } from '@/lib/new-api';
import { apiClient } from '@/api/client';
import ResourceViewerModal from './ResourceViewerModal';
import { useToast } from '@/hooks/use-toast';


interface ResourcesTabProps {
  vmcpConfig: VMCPConfig;
  servers: any[];
  //selectedResourcesByServer: { [serverId: string]: Set<string> };
  //setSelectedResourcesByServer: (resources: { [serverId: string]: Set<string> } | ((prev: { [serverId: string]: Set<string> }) => { [serverId: string]: Set<string> })) => void;
  expandedSections: Set<string>;
  setExpandedSections: (sections: Set<string> | ((prev: Set<string>) => Set<string>)) => void;
  handleFileUpload: (files: FileList) => Promise<void>;
  handleFileRemove: (blobId: string) => Promise<void>;
  handleFileRename: (blobId: string, newFilename: string) => Promise<void>;
  uploadingFiles: boolean;
  dragOver: boolean;
  setDragOver: (dragOver: boolean) => void;
  renamingFile: string | null;
  setRenamingFile: (blobId: string | null) => void;
  newFileName: string;
  setNewFileName: (name: string) => void;
  setVmcpConfig: (config: VMCPConfig | ((prev: VMCPConfig) => VMCPConfig)) => void;
  isRemoteVMCP?: boolean;
}

export default function ResourcesTab({
  vmcpConfig,
  servers,
  //selectedResourcesByServer,
  //setSelectedResourcesByServer,
  expandedSections,
  setExpandedSections,
  handleFileUpload,
  handleFileRemove,
  handleFileRename,
  uploadingFiles,
  dragOver,
  setDragOver,
  renamingFile,
  setRenamingFile,
  newFileName,
  setNewFileName,
  setVmcpConfig,
  isRemoteVMCP = false,
}: ResourcesTabProps) {
  const [viewingResource, setViewingResource] = useState<any>(null);
  const [isViewerOpen, setIsViewerOpen] = useState(false);
  const { success, error } = useToast();


  // MCP Server test states
  const [mcpTestResourceModal, setMcpTestResourceModal] = useState<{
    isOpen: boolean;
    resource: any | null;
    serverId: string | null;
    testing: boolean;
    result: string | null;
    error: string | null;
  }>({
    isOpen: false,
    resource: null,
    serverId: null,
    testing: false,
    result: null,
    error: null,
  });

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return '';
    try {
      return new Date(dateString).toLocaleDateString();
    } catch {
      return dateString;
    }
  };

  const getContentTypeIcon = (contentType?: string) => {
    if (contentType?.startsWith('image/')) return <FileText className="h-4 w-4 text-blue-500" />;
    if (contentType?.startsWith('video/')) return <FileText className="h-4 w-4 text-purple-500" />;
    if (contentType?.startsWith('audio/')) return <FileText className="h-4 w-4 text-green-500" />;
    if (contentType === 'application/pdf') return <FileText className="h-4 w-4 text-red-500" />;
    if (contentType?.startsWith('text/')) return <FileText className="h-4 w-4 text-orange-500" />;
    return <FileText className="h-4 w-4 text-muted-foreground" />;
  };

  const handleViewResource = (resource: Resource) => {
    setViewingResource(resource);
    setIsViewerOpen(true);
  };

  // MCP Server test functions
  const openMcpTestResourceModal = (resource: any, serverId: string) => {
    console.log('Opening MCP test resource modal for:', resource.uri, 'server:', serverId);
    console.log('Setting resource modal state:', {
      isOpen: true,
      resource,
      serverId,
      testing: false,
    });
    
    setMcpTestResourceModal({
      isOpen: true,
      resource,
      serverId,
      testing: false,
      result: null,
      error: null,
    });
  };

  const closeMcpTestResourceModal = () => {
    setMcpTestResourceModal({
      isOpen: false,
      resource: null,
      serverId: null,
      testing: false,
      result: null,
      error: null,
    });
  };

  const executeMcpResource = async () => {
    if (!mcpTestResourceModal.resource || !mcpTestResourceModal.serverId) return;

    try {
      setMcpTestResourceModal(prev => ({ ...prev, testing: true }));

      // Get access token
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available. Please log in again.');
      }

      // Read the resource using newApi
      const resourceRequest = {
        server_id: mcpTestResourceModal.serverId,
        uri: mcpTestResourceModal.resource.uri
      };
      const result = await apiClient.getMCPResource(resourceRequest.server_id, resourceRequest, accessToken);

      if (!result.success) {
        throw new Error(result.error || 'Failed to read resource');
      }

      // Extract the result text from the response
      let resultText = '';
      if (result.data?.content) {
        if (typeof result.data.content === 'string') {
          resultText = result.data.content;
        } else if (Array.isArray(result.data.content)) {
          resultText = result.data.content.map((item: any) => 
            item.text || JSON.stringify(item)
          ).join('\n');
        } else {
          resultText = JSON.stringify(result.data.content, null, 2);
        }
      } else {
        resultText = JSON.stringify(result.data, null, 2);
      }

      // Store the result in the modal state instead of closing
      setMcpTestResourceModal(prev => ({
        ...prev,
        result: resultText,
        error: null,
        testing: false,
      }));

    } catch (error) {
      console.error('Error reading MCP resource:', error);
      setMcpTestResourceModal(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'An error occurred while reading the resource',
        testing: false,
      }));
    }
  };

  // Get the default tab value
  const getDefaultTabValue = () => {
    if (vmcpConfig.uploaded_files.length > 0) {
      return "custom-resources";
    } else if (vmcpConfig.vmcp_config.selected_servers.length > 0) {
      return `server-${vmcpConfig.vmcp_config.selected_servers[0].server_id}`;
    }
    return "custom-resources";
  };

  return (
    <div>
      <Tabs defaultValue={getDefaultTabValue()} className="w-full">
        <TabsList className="mb-4 bg-transparent p-0 h-auto justify-start w-full border-b-1">
          <TabsTrigger 
            value="custom-resources"
            className="data-[state=active]:bg-background data-[state=active]:border-accent data-[state=active]:border-b-1 data-[state=active]:border-t-0 data-[state=active]:border-l-0 data-[state=active]:border-r-0 rounded-none"
          >
            vMCP Resources
            <Badge variant="outline" className="ml-2 text-xs">
              {vmcpConfig.uploaded_files.length}
            </Badge>
          </TabsTrigger>
          {vmcpConfig.vmcp_config.selected_servers.map((server) => {
            const fullServer = servers.find(s => s.server_id === server.server_id);
            const selectedResources = vmcpConfig.vmcp_config.selected_resources[server.server_id] || [];
            
            return (
              <TabsTrigger 
                key={server.server_id} 
                value={`server-${server.server_id}`}
                className="data-[state=active]:border-accent data-[state=active]:border-b-1 data-[state=active]:border-t-0 data-[state=active]:border-l-0 data-[state=active]:border-r-0 rounded-none"
              >
                <div className="flex items-center gap-2">
                  <Server className="h-4 w-4" />
                  {server.name}
                </div>
                <Badge variant="outline" className="ml-2 text-xs">
                  {selectedResources.length}/{server?.resource_details?.length || 0}
                </Badge>
              </TabsTrigger>
            );
          })}
        </TabsList>
        
        <TabsContent value="custom-resources">
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-medium text-foreground mb-3">Uploaded Files</h3>
              <div
                className={cn(
                  "border-2 border-dashed rounded-lg p-8 text-center transition-colors",
                  dragOver ? "border-primary bg-primary/5" : "border-border",
                  uploadingFiles && "opacity-50 pointer-events-none",
                  isRemoteVMCP && "opacity-50 pointer-events-none"
                )}
                onDragOver={(e) => {
                  if (!isRemoteVMCP) {
                    e.preventDefault();
                    setDragOver(true);
                  }
                }}
                onDragLeave={() => !isRemoteVMCP && setDragOver(false)}
                onDrop={(e) => {
                  if (!isRemoteVMCP) {
                    e.preventDefault();
                    setDragOver(false);
                    if (e.dataTransfer.files) {
                      handleFileUpload(e.dataTransfer.files);
                    }
                  }
                }}
              >
                {uploadingFiles ? (
                  <div className="flex items-center justify-center gap-2">
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent"></div>
                    <span className="text-muted-foreground">Uploading files...</span>
                  </div>
                ) : isRemoteVMCP ? (
                  <div>
                    <Upload className="h-8 w-8 mx-auto mb-4 text-muted-foreground" />
                    <p className="text-muted-foreground mb-2">File upload disabled for remote vMCPs</p>
                    <Button
                      variant="outline"
                      disabled
                      title="File upload disabled for remote vMCPs"
                    >
                      Choose Files
                    </Button>
                  </div>
                ) : (
                  <div>
                    <Upload className="h-8 w-8 mx-auto mb-4 text-muted-foreground" />
                    <p className="text-muted-foreground mb-2">Drag files here or click to upload</p>
                    <Button
                      variant="outline"
                      onClick={() => {
                        const input = document.createElement('input');
                        input.type = 'file';
                        input.multiple = true;
                        input.onchange = (e) => {
                          const target = e.target as HTMLInputElement;
                          if (target.files) {
                            handleFileUpload(target.files);
                          }
                        };
                        input.click();
                      }}
                    >
                      Choose Files
                    </Button>
                  </div>
                )}
              </div>

              {/* Uploaded Files List */}
              {vmcpConfig.uploaded_files.length > 0 && (
                <div className="space-y-3 mt-4">
                  {vmcpConfig.uploaded_files.map((file) => (
                    <div key={file.id} className="p-4 rounded-lg border border-border bg-card hover:bg-muted/30 transition-colors">
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-3 flex-1 min-w-0">
                          {getContentTypeIcon(file.content_type)}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-medium text-foreground truncate">
                                {file.resource_name || file.original_filename}
                              </span>
                              {file.content_type && (
                                <Badge variant="secondary" className="text-xs">
                                  {file.content_type.split('/')[1]?.toUpperCase() || 'FILE'}
                                </Badge>
                              )}
                            </div>
                            
                            <div className="flex items-center gap-4 text-xs text-muted-foreground mb-2">
                              <span className="flex items-center gap-1">
                                <Type className="h-3 w-3" />
                                {file.original_filename}
                              </span>
                              <span className="flex items-center gap-1">
                                <FileText className="h-3 w-3" />
                                {formatFileSize(file.size)}
                              </span>
                              {file.created_at && (
                                <span className="flex items-center gap-1">
                                  <Calendar className="h-3 w-3" />
                                  {formatDate(file.created_at)}
                                </span>
                              )}
                            </div>

                            {file.filename && file.filename !== file.original_filename && (
                              <p className="text-xs text-muted-foreground">
                                Filename: {file.filename}
                              </p>
                            )}
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleViewResource(file)}
                            className="h-8 px-2"
                          >
                            <Eye className="h-3 w-3 mr-1" />
                            View
                          </Button>
                          {!isRemoteVMCP && (
                            <>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => {
                                  setRenamingFile(file.id);
                                  setNewFileName(file.original_filename);
                                }}
                                className="h-8 px-2 text-muted-foreground hover:text-foreground"
                              >
                                <Edit className="h-3 w-3" />
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => handleFileRemove(file.id)}
                                className="h-8 px-2 hover:text-destructive/80"
                              >
                                <Trash2 className="h-3 w-3" />
                              </Button>
                            </>
                            )} 
                        </div>
                      </div>

                      {/* Rename input row */}
                      {renamingFile === file.id && (
                        <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border">
                          <Input
                            type="text"
                            value={newFileName}
                            onChange={(e) => setNewFileName(e.target.value)}
                            className="h-8 text-sm"
                            autoFocus
                          />
                          <Button
                            size="sm"
                            onClick={() => handleFileRename(file.id, newFileName)}
                            className="h-8 px-3"
                          >
                            <Save className="h-3 w-3 mr-1" />
                            Save
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              setRenamingFile(null);
                              setNewFileName('');
                            }}
                            className="h-8 px-2"
                          >
                            <X className="h-3 w-3" />
                          </Button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </TabsContent>
        
        {vmcpConfig.vmcp_config.selected_servers.map((server) => {
          console.log('servers', servers);
          console.log('server', server);
          // First try to find the server in the vMCP configuration (it has the full server data)
          let fullServer = server;
          // If the server doesn't have resource_details, try to find it in the servers context
          if (!fullServer.resource_details && servers) {
            fullServer = servers.find(s => s.server_id === server.server_id) || server;
          }
          const serverResources = fullServer?.resource_details || [];
          const selectedResources = vmcpConfig.vmcp_config.selected_resources[server.server_id] || [];
          console.log('selectedResources', selectedResources);
          console.log('fullServer', fullServer);
          console.log('serverResources', serverResources);
          
          return (
            <TabsContent key={server.server_id} value={`server-${server.server_id}`}>
              <div className="space-y-4">

                <div className="flex w-full items-center place-content-end gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      const allResourceUris = serverResources.map((r: any) => r.uri);
                      setVmcpConfig(prev => ({
                        ...prev,
                        vmcp_config: {
                          ...prev.vmcp_config,
                          selected_resources: {
                            ...prev.vmcp_config.selected_resources,
                            [server.server_id]: allResourceUris
                          }
                        }
                      }));
                    }}
                    disabled={isRemoteVMCP}
                    title={isRemoteVMCP ? 'Selection disabled for remote vMCPs' : ''}
                    className="h-7 px-3 text-xs border-muted"
                  >
                    Select All
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setVmcpConfig(prev => ({
                        ...prev,
                        vmcp_config: {
                          ...prev.vmcp_config,
                          selected_resources: {
                            ...prev.vmcp_config.selected_resources,
                            [server.server_id]: []
                          }
                        }
                      }));
                    }}
                    disabled={isRemoteVMCP}
                    title={isRemoteVMCP ? 'Selection disabled for remote vMCPs' : ''}
                    className="h-7 px-3 text-xs border-muted"
                  >
                    Deselect All
                  </Button>
                </div>
                
                {serverResources.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mx-auto mb-3">
                      <FolderOpen className="h-6 w-6 text-muted-foreground" />
                    </div>
                    <h4 className="text-base font-medium text-foreground mb-1">No Resources Available</h4>
                    <p className="text-sm text-muted-foreground">This MCP server doesn't expose any resources.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {serverResources.map((resource: any) => (
                        <div
                          key={resource.uri}
                          className={cn(
                            "p-3 rounded-lg border transition-all duration-200 cursor-pointer",
                            selectedResources.includes(resource.uri)
                              ? "bg-muted/60 border-primary/50 hover:border-primary/30"
                              : "bg-muted/40 border-border/60 hover:bg-muted/60 hover:border-border/80"
                          )}
                          onClick={() => {
                            if (isRemoteVMCP) {
                              //Show error toast
                              error("Selection disabled for community vMCPs", {
                                        description: "Extend the vMCP to make changes"});
                              return; // Disable selection for remote vMCPs
                            }
                            const newSelected = new Set(selectedResources);
                            if (newSelected.has(resource.uri)) {
                              newSelected.delete(resource.uri);
                            } else {
                              newSelected.add(resource.uri);
                            }
                            setVmcpConfig(prev => ({
                              ...prev,
                              vmcp_config: {
                                ...prev.vmcp_config,
                                selected_resources: {
                                  ...prev.vmcp_config.selected_resources,
                                  [server.server_id]: Array.from(newSelected)
                                }
                              }
                            }));
                          }}
                        >
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <FolderOpen className="h-4 w-4 text-primary" />
                              <span className="font-medium text-sm font-mono truncate">{resource.uri}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={(e) => {
                                  console.log('Test button clicked for resource:', resource.uri);
                                  e.stopPropagation();
                                  openMcpTestResourceModal(resource, server.server_id);
                                }}
                                className="h-6 px-2 text-xs opacity-60 hover:opacity-100 transition-opacity"
                              >
                                <Eye className="h-3 w-3 mr-1" />
                                Test
                              </Button>
                              <div className={cn(
                                "w-4 h-4 rounded-full border-2 flex items-center justify-center flex-shrink-0",
                                selectedResources.includes(resource.uri)
                                  ? "bg-primary border-primary"
                                  : "border-border"
                              )}>
                                {selectedResources.includes(resource.uri) && (
                                  <div className="w-2 h-2 bg-primary-foreground rounded-full"></div>
                                )}
                              </div>
                            </div>
                          </div>
                          {resource.name && (
                            <p className="text-xs text-muted-foreground mb-1">{resource.name}</p>
                          )}
                          {resource.description && (
                            <p className="text-xs text-muted-foreground line-clamp-2 mb-2">{resource.description}</p>
                          )}
                          <div className="mt-2">
                            <Badge variant="secondary" className="text-xs">
                              MCP Resource
                            </Badge>
                          </div>
                        </div>
                    ))}
                  </div>
                )}
              </div>
            </TabsContent>
          );
        })}
        
        {/* Empty state when no servers are selected */}
        {vmcpConfig.vmcp_config.selected_servers.length === 0 && (
          <TabsContent value="no-servers">
            <div className="text-center py-8 text-muted-foreground">
              <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mx-auto mb-3">
                <Server className="h-6 w-6 text-muted-foreground" />
              </div>
              <h4 className="text-base font-medium text-foreground mb-1">No MCP Servers Selected</h4>
              <p className="text-sm text-muted-foreground">Add MCP servers in the MCP Servers tab to see their resources here.</p>
            </div>
          </TabsContent>
        )}
      </Tabs>

      {/* Resource Viewer Modal */}
      <ResourceViewerModal
        isOpen={isViewerOpen}
        onClose={() => {
          setIsViewerOpen(false);
          setViewingResource(null);
        }}
        resource={viewingResource}
      />

      {/* MCP Test Resource Modal */}
      {mcpTestResourceModal.isOpen && mcpTestResourceModal.resource && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-lg p-6 max-w-md w-full mx-4 shadow-lg">
            <h3 className="text-lg font-semibold text-foreground mb-4">
              Test MCP Resource
            </h3>
            
            <div className="space-y-4">
              <div className="text-sm text-muted-foreground mb-4">
                <strong>URI:</strong> {mcpTestResourceModal.resource.uri}
              </div>
              
              {mcpTestResourceModal.resource.name && (
                <div className="text-sm text-muted-foreground mb-4">
                  <strong>Name:</strong> {mcpTestResourceModal.resource.name}
                </div>
              )}
              
              {mcpTestResourceModal.resource.description && (
                <div className="text-sm text-muted-foreground mb-4">
                  <strong>Description:</strong> {mcpTestResourceModal.resource.description}
                </div>
              )}
              
              <div className="text-sm text-muted-foreground">
                This will read the resource content and display it in the viewer.
              </div>
            </div>
            
            {/* Result Display */}
            {mcpTestResourceModal.result && (
              <div className="mt-6">
                <h4 className="font-medium text-foreground mb-2">Result:</h4>
                <div className="bg-muted/50 border border-border rounded-lg p-4">
                  <pre className="text-sm text-foreground whitespace-pre-wrap overflow-x-auto">
                    {mcpTestResourceModal.result}
                  </pre>
                </div>
              </div>
            )}
            
            {mcpTestResourceModal.error && (
              <div className="mt-6">
                <h4 className="font-medium text-red-600 mb-2">Error:</h4>
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <p className="text-sm text-red-700">{mcpTestResourceModal.error}</p>
                </div>
              </div>
            )}
            
            <div className="flex gap-3 mt-6">
              <Button
                variant="outline"
                onClick={closeMcpTestResourceModal}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                onClick={executeMcpResource}
                disabled={mcpTestResourceModal.testing}
                className="flex-1"
              >
                {mcpTestResourceModal.testing ? (
                  <>
                    <div className="h-4 w-4 mr-2 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                    Testing...
                  </>
                ) : (
                  <>
                    <Eye className="h-4 w-4 mr-2" />
                    Test Resource
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}