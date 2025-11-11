
import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';
import { 
  Server, 
  Zap, 
  Link as LinkIcon,
  Lock,
  CheckCircle,
  MessageSquare,
  ChevronDown,
  ChevronRight,
  Code,
  FolderOpen,
  Settings,
  Terminal,
  Globe,
  Wifi,
  FileText,
  Type,
  X
} from 'lucide-react';
import { FaviconIcon } from '@/components/ui/favicon-icon';

interface VMCPDetailsDisplayProps {
  vmcpData: any;
  vmcpType: string;
  isRemoteVMCP?: boolean;
  showExpandableLists?: boolean;
  onToolClick?: (serverId: string, toolName: string) => void;
  onPromptClick?: (serverId: string, promptName: string) => void;
}

export default function VMCPDetailsDisplay({
  vmcpData,
  vmcpType,
  isRemoteVMCP = false,
  showExpandableLists = true,
  onToolClick,
  onPromptClick
}: VMCPDetailsDisplayProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [expandedTools, setExpandedTools] = useState<Set<string>>(new Set());
  const [expandedPrompts, setExpandedPrompts] = useState<Set<string>>(new Set());
  const [showToolDetails, setShowToolDetails] = useState<string | null>(null);
  const [showPromptDetails, setShowPromptDetails] = useState<string | null>(null);

  // Helper functions
  const toggleSection = (section: string) => {
    setExpandedSections(prev => {
      const newSet = new Set(prev);
      if (newSet.has(section)) {
        newSet.delete(section);
      } else {
        newSet.add(section);
      }
      return newSet;
    });
  };

  const toggleExpandedTools = (serverId: string) => {
    setExpandedTools(prev => {
      const newSet = new Set(prev);
      if (newSet.has(serverId)) {
        newSet.delete(serverId);
      } else {
        newSet.add(serverId);
      }
      return newSet;
    });
  };

  const toggleExpandedPrompts = (serverId: string) => {
    setExpandedPrompts(prev => {
      const newSet = new Set(prev);
      if (newSet.has(serverId)) {
        newSet.delete(serverId);
      } else {
        newSet.add(serverId);
      }
      return newSet;
    });
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
        return Server;
    }
  };

  const handleToolClick = (serverId: string, toolName: string) => {
    if (onToolClick) {
      onToolClick(serverId, toolName);
    } else {
      setShowToolDetails(`${serverId}-${toolName}`);
    }
  };

  const handlePromptClick = (serverId: string, promptName: string) => {
    if (onPromptClick) {
      onPromptClick(serverId, promptName);
    } else {
      setShowPromptDetails(`${serverId}-${promptName}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* MCP Servers Section */}
      <Card>
        <Collapsible 
          open={expandedSections.has('servers')} 
          onOpenChange={() => toggleSection('servers')}
        >
          <CollapsibleTrigger asChild>
            <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Server className="h-5 w-5 text-primary" />
                  <CardTitle className="text-xl">MCP Servers</CardTitle>
                  <Badge variant="outline" className="text-sm">
                    {vmcpData.vmcp_config?.selected_servers?.length || 0}
                  </Badge>
                </div>
                {expandedSections.has('servers') ? (
                  <ChevronDown className="h-5 w-5 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-5 w-5 text-muted-foreground" />
                )}
              </div>
            </CardHeader>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                {vmcpData.vmcp_config?.selected_servers?.map((server: any, index: number) => {
                  const TransportIcon = getTransportIcon(server.transport_type);
                  return (
                    <div key={index} className="p-4 bg-muted/30 rounded-lg border min-w-0">
                      <div className="flex items-start gap-3">
                        <FaviconIcon
                          url={server.url}
                          faviconUrl={server.favicon_url}
                          className="h-8 w-8 flex-shrink-0"
                          size={32}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-2">
                            <h5 className="font-medium text-sm font-mono truncate">{server.name}</h5>
                            <Badge variant="secondary" className="text-xs flex-shrink-0">
                              <TransportIcon className="h-3 w-3 mr-1" />
                              {server.transport_type}
                            </Badge>
                          </div>
                          {server.description && (
                            <p className="text-xs text-muted-foreground line-clamp-2">{server.description}</p>
                          )}
                          <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground flex-wrap">
                            <div className="flex items-center gap-1">
                              <Code className="h-3 w-3" />
                              <span>{server.tool_details?.length || 0} tools</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <MessageSquare className="h-3 w-3" />
                              <span>{server.prompt_details?.length || 0} prompts</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <FolderOpen className="h-3 w-3" />
                              <span>{server.resource_details?.length || 0} resources</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </CollapsibleContent>
        </Collapsible>
      </Card>

      {/* Tools Section */}
      <Card>
        <Collapsible 
          open={expandedSections.has('tools')} 
          onOpenChange={() => toggleSection('tools')}
        >
          <CollapsibleTrigger asChild>
            <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Zap className="h-5 w-5 text-primary" />
                  <CardTitle className="text-xl">Tools</CardTitle>
                  <Badge variant="outline" className="text-sm">
                    {vmcpData.total_tools || 0}
                  </Badge>
                </div>
                {expandedSections.has('tools') ? (
                  <ChevronDown className="h-5 w-5 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-5 w-5 text-muted-foreground" />
                )}
              </div>
            </CardHeader>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <CardContent>
              <div className="space-y-4">
                {/* Server Tools */}
                {vmcpData.vmcp_config?.selected_servers?.map((server: any) => {
                  const selectedTools = vmcpData.vmcp_config?.selected_tools?.[server.server_id] || [];
                  const totalTools = server.tool_details?.length || 0;
                  const isExpanded = expandedTools.has(server.server_id);
                  
                  // Only show servers that have selected tools
                  if (selectedTools.length === 0) return null;
                  
                  // Filter to only show selected tools
                  const selectedToolDetails = server.tool_details?.filter((tool: any) => 
                    selectedTools.includes(tool.name)
                  ) || [];
                  
                  return (
                    <div key={server.server_id} className="border rounded-lg p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <FaviconIcon
                          url={server.url}
                          faviconUrl={server.favicon_url}
                          className="h-6 w-6"
                          size={24}
                        />
                        <h4 className="font-medium">{server.name}</h4>
                        <Badge variant="outline" className="text-xs">
                          {selectedTools.length} selected
                        </Badge>
                        {showExpandableLists && selectedToolDetails.length > 6 && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => toggleExpandedTools(server.server_id)}
                            className="ml-auto h-6 px-2 text-xs"
                          >
                            {isExpanded ? 'Show Less' : `+${selectedToolDetails.length - 6} more tools`}
                            {isExpanded ? (
                              <ChevronDown className="h-3 w-3 ml-1" />
                            ) : (
                              <ChevronRight className="h-3 w-3 ml-1" />
                            )}
                          </Button>
                        )}
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {(showExpandableLists && isExpanded ? selectedToolDetails : selectedToolDetails?.slice(0, 6)).map((tool: any, index: number) => (
                          <div 
                            key={index} 
                            className="p-3 rounded-lg text-sm cursor-pointer transition-colors hover:bg-muted/50 bg-primary/10 border border-primary/20"
                            onClick={() => handleToolClick(server.server_id, tool.name)}
                          >
                            <div className="flex items-center gap-2 mb-2">
                              <Code className="h-3 w-3" />
                              <span className="font-mono text-xs font-medium">{tool.name}</span>
                              <CheckCircle className="h-3 w-3 text-primary" />
                            </div>
                            {tool.description && (
                              <p className="text-xs text-muted-foreground line-clamp-2">
                                {tool.description}
                              </p>
                            )}
                            {tool.inputSchema && (
                              <div className="mt-2">
                                <p className="text-xs text-muted-foreground mb-1">Parameters:</p>
                                <div className="flex flex-wrap gap-1">
                                  {Object.keys(tool.inputSchema.properties || {}).slice(0, 3).map((param: string) => (
                                    <Badge key={param} variant="outline" className="text-xs">
                                      {param}
                                    </Badge>
                                  ))}
                                  {Object.keys(tool.inputSchema.properties || {}).length > 3 && (
                                    <Badge variant="outline" className="text-xs">
                                      +{Object.keys(tool.inputSchema.properties || {}).length - 3} more
                                    </Badge>
                                  )}
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
                
                {/* Custom Tools */}
                {vmcpData.custom_tools && vmcpData.custom_tools.length > 0 && (
                  <div className="border rounded-lg p-4">
                    <h4 className="font-medium mb-3 flex items-center gap-2">
                      <Settings className="h-4 w-4" />
                      Custom Tools ({vmcpData.custom_tools.length})
                    </h4>
                    <div className="space-y-2">
                      {vmcpData.custom_tools.map((tool: any, index: number) => (
                        <div key={index} className="p-3 bg-muted/30 rounded-lg">
                          <div className="flex items-center gap-2 mb-1">
                            <Code className="h-4 w-4 text-primary" />
                            <span className="font-medium text-sm font-mono">{tool.name}</span>
                          </div>
                          {tool.description && (
                            <p className="text-xs text-muted-foreground">{tool.description}</p>
                          )}
                          {tool.variables && tool.variables.length > 0 && (
                            <div className="mt-2">
                              <p className="text-xs text-muted-foreground mb-1">Variables:</p>
                              <div className="flex flex-wrap gap-1">
                                {tool.variables.map((variable: any, varIndex: number) => (
                                  <Badge key={varIndex} variant="outline" className="text-xs">
                                    {variable.name}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </CollapsibleContent>
        </Collapsible>
      </Card>

      {/* Prompts Section */}
      <Card>
        <Collapsible 
          open={expandedSections.has('prompts')} 
          onOpenChange={() => toggleSection('prompts')}
        >
          <CollapsibleTrigger asChild>
            <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <MessageSquare className="h-5 w-5 text-primary" />
                  <CardTitle className="text-xl">Prompts</CardTitle>
                  <Badge variant="outline" className="text-sm">
                    {vmcpData.total_prompts || 0}
                  </Badge>
                </div>
                {expandedSections.has('prompts') ? (
                  <ChevronDown className="h-5 w-5 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-5 w-5 text-muted-foreground" />
                )}
              </div>
            </CardHeader>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <CardContent>
              <div className="space-y-4">
                {/* Server Prompts */}
                {vmcpData.vmcp_config?.selected_servers?.map((server: any) => {
                  const selectedPrompts = vmcpData.vmcp_config?.selected_prompts?.[server.server_id] || [];
                  const totalPrompts = server.prompt_details?.length || 0;
                  const isExpanded = expandedPrompts.has(server.server_id);
                  
                  // Only show servers that have selected prompts
                  if (selectedPrompts.length === 0) return null;
                  
                  // Filter to only show selected prompts
                  const selectedPromptDetails = server.prompt_details?.filter((prompt: any) => 
                    selectedPrompts.includes(prompt.name)
                  ) || [];
                  
                  return (
                    <div key={server.server_id} className="border rounded-lg p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <FaviconIcon
                          url={server.url}
                          faviconUrl={server.favicon_url}
                          className="h-6 w-6"
                          size={24}
                        />
                        <h4 className="font-medium">{server.name}</h4>
                        <Badge variant="outline" className="text-xs">
                          {selectedPrompts.length} selected
                        </Badge>
                        {showExpandableLists && selectedPromptDetails.length > 6 && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => toggleExpandedPrompts(server.server_id)}
                            className="ml-auto h-6 px-2 text-xs"
                          >
                            {isExpanded ? 'Show Less' : `+${selectedPromptDetails.length - 6} more prompts`}
                            {isExpanded ? (
                              <ChevronDown className="h-3 w-3 ml-1" />
                            ) : (
                              <ChevronRight className="h-3 w-3 ml-1" />
                            )}
                          </Button>
                        )}
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {(showExpandableLists && isExpanded ? selectedPromptDetails : selectedPromptDetails?.slice(0, 6)).map((prompt: any, index: number) => (
                          <div 
                            key={index} 
                            className="p-3 rounded-lg text-sm cursor-pointer transition-colors hover:bg-muted/50 bg-primary/10 border border-primary/20"
                            onClick={() => handlePromptClick(server.server_id, prompt.name)}
                          >
                            <div className="flex items-center gap-2 mb-2">
                              <MessageSquare className="h-3 w-3" />
                              <span className="font-mono text-xs font-medium">{prompt.name}</span>
                              <CheckCircle className="h-3 w-3 text-primary" />
                            </div>
                            {prompt.description && (
                              <p className="text-xs text-muted-foreground line-clamp-2">
                                {prompt.description}
                              </p>
                            )}
                            {prompt.arguments && prompt.arguments.length > 0 && (
                              <div className="mt-2">
                                <p className="text-xs text-muted-foreground mb-1">Parameters:</p>
                                <div className="flex flex-wrap gap-1">
                                  {prompt.arguments.slice(0, 3).map((arg: any, argIndex: number) => (
                                    <Badge key={argIndex} variant="outline" className="text-xs">
                                      {arg.name}
                                    </Badge>
                                  ))}
                                  {prompt.arguments.length > 3 && (
                                    <Badge variant="outline" className="text-xs">
                                      +{prompt.arguments.length - 3} more
                                    </Badge>
                                  )}
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
                
                {/* Custom Prompts */}
                {vmcpData.custom_prompts && vmcpData.custom_prompts.length > 0 && (
                  <div className="border rounded-lg p-4">
                    <h4 className="font-medium mb-3 flex items-center gap-2">
                      <Type className="h-4 w-4" />
                      Custom Prompts ({vmcpData.custom_prompts.length})
                    </h4>
                    <div className="space-y-3">
                      {vmcpData.custom_prompts.map((prompt: any, index: number) => (
                        <div key={index} className="p-3 bg-muted/30 rounded-lg">
                          <div className="flex items-center gap-2 mb-2">
                            <MessageSquare className="h-4 w-4 text-primary" />
                            <span className="font-medium text-sm font-mono">{prompt.name}</span>
                          </div>
                          {prompt.description && (
                            <p className="text-xs text-muted-foreground mb-2">{prompt.description}</p>
                          )}
                          {prompt.variables && prompt.variables.length > 0 && (
                            <div className="mb-2">
                              <p className="text-xs text-muted-foreground mb-1">Variables:</p>
                              <div className="flex flex-wrap gap-1">
                                {prompt.variables.map((variable: any, varIndex: number) => (
                                  <Badge key={varIndex} variant="outline" className="text-xs">
                                    {variable.name}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          )}
                          <div className="text-xs text-muted-foreground">
                            <p className="line-clamp-2">{prompt.text}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </CollapsibleContent>
        </Collapsible>
      </Card>

      {/* Resources Section */}
      <Card>
        <Collapsible 
          open={expandedSections.has('resources')} 
          onOpenChange={() => toggleSection('resources')}
        >
          <CollapsibleTrigger asChild>
            <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <LinkIcon className="h-5 w-5 text-primary" />
                  <CardTitle className="text-xl">Resources</CardTitle>
                  <Badge variant="outline" className="text-sm">
                    {vmcpData.total_resources || 0}
                  </Badge>
                </div>
                {expandedSections.has('resources') ? (
                  <ChevronDown className="h-5 w-5 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-5 w-5 text-muted-foreground" />
                )}
              </div>
            </CardHeader>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <CardContent>
              <div className="space-y-4">
                {/* Server Resources */}
                {vmcpData.vmcp_config?.selected_servers?.map((server: any) => {
                  const selectedResources = vmcpData.vmcp_config?.selected_resources?.[server.server_id] || [];
                  const totalResources = server.resource_details?.length || 0;
                  
                  // Only show servers that have selected resources
                  if (selectedResources.length === 0) return null;
                  
                  // Filter to only show selected resources
                  const selectedResourceDetails = server.resource_details?.filter((resource: any) => 
                    selectedResources.includes(resource.name)
                  ) || [];
                  
                  return (
                    <div key={server.server_id} className="border rounded-lg p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <FaviconIcon
                          url={server.url}
                          faviconUrl={server.favicon_url}
                          className="h-6 w-6"
                          size={24}
                        />
                        <h4 className="font-medium">{server.name}</h4>
                        <Badge variant="outline" className="text-xs">
                          {selectedResources.length} selected
                        </Badge>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {selectedResourceDetails?.slice(0, 6).map((resource: any, index: number) => (
                          <div key={index} className="p-2 rounded text-sm bg-primary/10 border border-primary/20">
                            <div className="flex items-center gap-2">
                              <FolderOpen className="h-3 w-3" />
                              <span className="font-mono text-xs">{resource.name}</span>
                              <CheckCircle className="h-3 w-3 text-primary" />
                            </div>
                            {resource.description && (
                              <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
                                {resource.description}
                              </p>
                            )}
                          </div>
                        ))}
                        {selectedResourceDetails?.length > 6 && (
                          <div className="p-2 rounded text-sm bg-muted/20 text-center">
                            <span className="text-xs text-muted-foreground">
                              +{selectedResourceDetails.length - 6} more resources
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
                
                {/* Custom Resources */}
                {vmcpData.custom_resources && vmcpData.custom_resources.length > 0 && (
                  <div className="border rounded-lg p-4">
                    <h4 className="font-medium mb-3 flex items-center gap-2">
                      <FileText className="h-4 w-4" />
                      Custom Resources ({vmcpData.custom_resources.length})
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {vmcpData.custom_resources.map((resource: any, index: number) => (
                        <div key={index} className="p-3 bg-muted/30 rounded-lg">
                          <div className="flex items-center gap-2 mb-1">
                            <FileText className="h-4 w-4 text-primary" />
                            <span className="font-medium text-sm font-mono">{resource.filename || resource.name}</span>
                          </div>
                          {resource.content_type && (
                            <p className="text-xs text-muted-foreground">{resource.content_type}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </CollapsibleContent>
        </Collapsible>
      </Card>

      {/* Environment Variables Section */}
      {vmcpData.environment_variables && vmcpData.environment_variables.length > 0 && (
        <Card>
          <Collapsible 
            open={expandedSections.has('env_vars')} 
            onOpenChange={() => toggleSection('env_vars')}
          >
            <CollapsibleTrigger asChild>
              <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Lock className="h-5 w-5 text-primary" />
                    <CardTitle className="text-xl">Environment Variables</CardTitle>
                    <Badge variant="outline" className="text-sm">
                      {vmcpData.environment_variables.length}
                    </Badge>
                  </div>
                  {expandedSections.has('env_vars') ? (
                    <ChevronDown className="h-5 w-5 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-5 w-5 text-muted-foreground" />
                  )}
                </div>
              </CardHeader>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {vmcpData.environment_variables.map((envVar: any, index: number) => (
                    <div key={index} className="p-3 bg-muted/30 rounded-lg border">
                      <div className="flex items-center justify-between mb-2">
                        <h5 className="font-medium text-sm font-mono">{envVar.name}</h5>
                        <Badge variant="outline" className="text-xs">
                          {envVar.required ? 'Required' : 'Optional'}
                        </Badge>
                      </div>
                      {envVar.description && (
                        <p className="text-xs text-muted-foreground mb-2">{envVar.description}</p>
                      )}
                      <div className="text-xs text-muted-foreground">
                        <span className="font-medium">Value: </span>
                        {envVar.value || <span className="italic">Not set</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </CollapsibleContent>
          </Collapsible>
        </Card>
      )}

      {/* Tool Details Modal */}
      {showToolDetails && (() => {
        const [serverId, toolName] = showToolDetails.split('-');
        const server = vmcpData.vmcp_config?.selected_servers?.find((s: any) => s.server_id === serverId);
        const tool = server?.tool_details?.find((t: any) => t.name === toolName);
        
        if (!tool) return null;
        
        return (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-background border border-border rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between p-6 border-b border-border">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center">
                    <Code className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-foreground font-mono">{tool.name}</h2>
                    <p className="text-sm text-muted-foreground">Tool Details</p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowToolDetails(null)}
                  className="h-8 w-8 p-0"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <div className="p-6 space-y-6">
                {/* Description */}
                {tool.description && (
                  <div>
                    <h3 className="text-sm font-medium text-foreground mb-2">Description</h3>
                    <p className="text-sm text-muted-foreground">{tool.description}</p>
                  </div>
                )}

                {/* Input Schema */}
                {tool.inputSchema && (
                  <div>
                    <h3 className="text-sm font-medium text-foreground mb-3">Parameters</h3>
                    <div className="space-y-4">
                      {Object.entries(tool.inputSchema.properties || {}).map(([paramName, paramSchema]: [string, any]) => (
                        <div key={paramName} className="p-4 bg-muted/30 rounded-lg">
                          <div className="flex items-center gap-2 mb-2">
                            <h4 className="font-medium text-sm font-mono">{paramName}</h4>
                            {tool.inputSchema.required?.includes(paramName) && (
                              <Badge variant="destructive" className="text-xs">Required</Badge>
                            )}
                            <Badge variant="outline" className="text-xs">{paramSchema.type || 'string'}</Badge>
                          </div>
                          {paramSchema.description && (
                            <p className="text-xs text-muted-foreground mb-2">{paramSchema.description}</p>
                          )}
                          {paramSchema.enum && (
                            <div className="mt-2">
                              <p className="text-xs text-muted-foreground mb-1">Allowed values:</p>
                              <div className="flex flex-wrap gap-1">
                                {paramSchema.enum.map((value: string, index: number) => (
                                  <Badge key={index} variant="secondary" className="text-xs">
                                    {value}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })()}

      {/* Prompt Details Modal */}
      {showPromptDetails && (() => {
        const [serverId, promptName] = showPromptDetails.split('-');
        const server = vmcpData.vmcp_config?.selected_servers?.find((s: any) => s.server_id === serverId);
        const prompt = server?.prompt_details?.find((p: any) => p.name === promptName);
        
        if (!prompt) return null;
        
        return (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-background border border-border rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between p-6 border-b border-border">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center">
                    <MessageSquare className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-foreground font-mono">{prompt.name}</h2>
                    <p className="text-sm text-muted-foreground">Prompt Details</p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowPromptDetails(null)}
                  className="h-8 w-8 p-0"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <div className="p-6 space-y-6">
                {/* Description */}
                {prompt.description && (
                  <div>
                    <h3 className="text-sm font-medium text-foreground mb-2">Description</h3>
                    <p className="text-sm text-muted-foreground">{prompt.description}</p>
                  </div>
                )}

                {/* Arguments */}
                {prompt.arguments && prompt.arguments.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-foreground mb-3">Parameters</h3>
                    <div className="space-y-4">
                      {prompt.arguments.map((arg: any, index: number) => (
                        <div key={index} className="p-4 bg-muted/30 rounded-lg">
                          <div className="flex items-center gap-2 mb-2">
                            <h4 className="font-medium text-sm font-mono">{arg.name}</h4>
                            {arg.required && (
                              <Badge variant="destructive" className="text-xs">Required</Badge>
                            )}
                            <Badge variant="outline" className="text-xs">{arg.type || 'string'}</Badge>
                          </div>
                          {arg.description && (
                            <p className="text-xs text-muted-foreground">{arg.description}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Prompt Text */}
                {prompt.text && (
                  <div>
                    <h3 className="text-sm font-medium text-foreground mb-2">Prompt Text</h3>
                    <div className="p-4 bg-muted/30 rounded-lg">
                      <pre className="text-sm text-foreground whitespace-pre-wrap overflow-x-auto">
                        {prompt.text}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
