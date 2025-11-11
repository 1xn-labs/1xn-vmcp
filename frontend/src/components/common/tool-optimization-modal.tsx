
import React, { useState, useEffect } from 'react';
import { Modal } from '@/components/ui/modal';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { 
  ChevronDown, 
  ChevronRight, 
  Server, 
  Wrench, 
  Calendar,
  Clock,
  Target,
  Save
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
// import { newApi } from '@/lib/new-api';
import { apiClient } from '@/api/client';
import { useServersList } from '@/contexts/servers-context';

interface ToolStats {
  tool_name: string;
  server_name: string;
  total_count: number;
  latest_used: string | null;
  description?: string;
  available?: boolean;
  from_context?: boolean;
}

interface ToolStatsResponse {
  tool_stats: Record<string, ToolStats>;
  time_range: string;
  total_tools: number;
}

interface ServerInfo {
  server_id: string;
  name: string;
  description?: string;
  tools: ToolStats[];
}

interface ToolOptimizationModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function ToolOptimizationModal({ isOpen, onClose }: ToolOptimizationModalProps) {
  const { success, error } = useToast();
  const servers = useServersList(); // Get servers from context
  const [loading, setLoading] = useState(false);
  const [toolStats, setToolStats] = useState<ToolStatsResponse | null>(null);
  const [mergedServers, setMergedServers] = useState<ServerInfo[]>([]);
  const [selectedTools, setSelectedTools] = useState<Set<string>>(new Set());
  const [expandedServers, setExpandedServers] = useState<Set<string>>(new Set());
  const [timeRange, setTimeRange] = useState<string>('all-time');

  // Fetch tool usage statistics from backend
  const fetchToolStats = async (range: string) => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      if (!token) {
        error("Please log in to view tool statistics");
        return;
      }

      const result = await apiClient.getToolLogsStats(token, range);
      
      if (result.success && result.data) {
        setToolStats(result.data);
        mergeServerDataWithUsageStats(result.data.tool_stats);
      } else {
        error(result.error || "Failed to fetch tool statistics");
      }
    } catch (err) {
      console.error('Error fetching tool statistics:', err);
      error("Failed to fetch tool statistics");
    } finally {
      setLoading(false);
    }
  };

  // Merge server context data with usage statistics
  const mergeServerDataWithUsageStats = (usageStats: Record<string, ToolStats>) => {
    const serverMap = new Map<string, ServerInfo>();
    
    // Start with all servers from context
    servers.forEach(server => {
      const serverInfo: ServerInfo = {
        server_id: server.server_id,
        name: server.name,
        description: server.description || `Server with ${server.tools_list?.length || 0} tools`,
        tools: []
      };
      
      // Add all tools from server context
      if (server.tools_list && Array.isArray(server.tools_list)) {
        server.tools_list.forEach(toolName => {
          const toolKey = `${toolName}:${server.name}`;
          const usageStat = usageStats[toolKey];
          
          const toolInfo: ToolStats = {
            tool_name: toolName,
            server_name: server.name,
            total_count: usageStat ? usageStat.total_count : 0,
            latest_used: usageStat ? usageStat.latest_used : null,
            description: usageStat ? usageStat.description : "",
            available: true,
            from_context: true
          };
          
          serverInfo.tools.push(toolInfo);
        });
      }
      
      serverMap.set(server.name, serverInfo);
    });
    
    // Add custom tools from usage stats (not in server context)
    Object.values(usageStats).forEach(usageStat => {
      if (usageStat.server_name === "custom_tool") {
        const serverName = "custom_tool";
        if (!serverMap.has(serverName)) {
          serverMap.set(serverName, {
            server_id: serverName,
            name: serverName,
            description: "Custom tools",
            tools: []
          });
        }
        
        const customTool: ToolStats = {
          ...usageStat,
          from_context: false
        };
        
        serverMap.get(serverName)!.tools.push(customTool);
      }
    });
    
    // Sort servers by name and tools by usage count
    const sortedServers = Array.from(serverMap.values()).sort((a, b) => a.name.localeCompare(b.name));
    sortedServers.forEach(server => {
      server.tools.sort((a, b) => b.total_count - a.total_count);
    });
    
    setMergedServers(sortedServers);
    
    // Auto-select used tools (tools with total_count > 0)
    const usedToolKeys = Object.keys(usageStats).filter(key => usageStats[key].total_count > 0);
    setSelectedTools(new Set(usedToolKeys));
  };

  // Handle time range change
  const handleTimeRangeChange = (range: string) => {
    setTimeRange(range);
    fetchToolStats(range);
  };

  // Toggle server expansion
  const toggleServer = (serverId: string) => {
    const newExpanded = new Set(expandedServers);
    if (newExpanded.has(serverId)) {
      newExpanded.delete(serverId);
    } else {
      newExpanded.add(serverId);
    }
    setExpandedServers(newExpanded);
  };

  // Toggle tool selection
  const toggleToolSelection = (toolKey: string) => {
    const newSelected = new Set(selectedTools);
    if (newSelected.has(toolKey)) {
      newSelected.delete(toolKey);
    } else {
      newSelected.add(toolKey);
    }
    setSelectedTools(newSelected);
  };

  // Select all tools in a time range
  const selectToolsByTimeRange = (range: string) => {
    setTimeRange(range);
    fetchToolStats(range);
    // Auto-selection will happen in mergeServerDataWithUsageStats after data is fetched
  };

  // Save curated tools
  const saveCuratedTools = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      if (!token) {
        error("Please log in to save curated tools");
        return;
      }

      // Group selected tools by server
      const toolsByServer: Record<string, string[]> = {};
      selectedTools.forEach(toolKey => {
        const [toolName, serverName] = toolKey.split(':');
        if (!toolsByServer[serverName]) {
          toolsByServer[serverName] = [];
        }
        toolsByServer[serverName].push(toolName);
      });

      // TODO: Implement API call to save curated tools to server configs
      console.log('Saving curated tools:', toolsByServer);
      
      success(`Saved ${selectedTools.size} curated tools across ${Object.keys(toolsByServer).length} servers`);
      onClose();
    } catch (err) {
      console.error('Error saving curated tools:', err);
      error("Failed to save curated tools");
    } finally {
      setLoading(false);
    }
  };

  // Format date
  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never used';
    try {
      return new Date(dateString).toLocaleDateString();
    } catch {
      return 'Invalid date';
    }
  };

  useEffect(() => {
    if (isOpen && servers.length > 0) {
      fetchToolStats(timeRange);
    }
  }, [isOpen, servers, timeRange]);

  return (
    <Modal 
      isOpen={isOpen} 
      onClose={onClose}
      title="Tool Optimization"
      size="xl"
    >
      <div className="flex flex-col h-full p-6">
        {/* Quick Actions */}
        <div className="flex flex-wrap gap-2 mb-4 p-4 bg-muted rounded-lg">
          <Button
            variant={timeRange === 'all-time' ? 'default' : 'outline'}
            size="sm"
            onClick={() => handleTimeRangeChange('all-time')}
          >
            All Time
          </Button>
          <Button
            variant={timeRange === 'past-30-days' ? 'default' : 'outline'}
            size="sm"
            onClick={() => selectToolsByTimeRange('past-30-days')}
          >
            Past 30 Days
          </Button>
          <Button
            variant={timeRange === 'past-7-days' ? 'default' : 'outline'}
            size="sm"
            onClick={() => selectToolsByTimeRange('past-7-days')}
          >
            Past 7 Days
          </Button>
        </div>

        {/* Statistics Summary */}
        {toolStats && (
          <div className="flex gap-4 mb-4 p-4 bg-muted rounded-lg">
            <div className="flex items-center gap-2">
              <Wrench className="h-4 w-4" />
              <span className="text-sm font-medium">
                {toolStats.total_tools} tools
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Server className="h-4 w-4" />
              <span className="text-sm font-medium">
                {mergedServers.length} servers
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Target className="h-4 w-4" />
              <span className="text-sm font-medium">
                {Object.values(toolStats.tool_stats).filter(t => t.total_count > 0).length} used
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4" />
              <span className="text-sm font-medium">
                {Object.values(toolStats.tool_stats).filter(t => t.total_count === 0).length} unused
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Server className="h-4 w-4" />
              <span className="text-sm font-medium">
                {mergedServers.filter(s => s.name !== 'custom_tool').reduce((sum, s) => sum + s.tools.length, 0)} server tools
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Wrench className="h-4 w-4" />
              <span className="text-sm font-medium">
                {mergedServers.find(s => s.name === 'custom_tool')?.tools.length || 0} custom tools
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Target className="h-4 w-4" />
              <span className="text-sm font-medium">
                {selectedTools.size} selected
              </span>
            </div>
          </div>
        )}

        {/* Servers and Tools */}
        <div className="flex-1 overflow-y-auto space-y-3">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="flex items-center space-x-2">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
                <span>Loading tool statistics...</span>
              </div>
            </div>
          ) : (
            mergedServers.map((server) => (
              <Card key={server.server_id} className="border-border">
                <CardHeader 
                  className="cursor-pointer hover:bg-muted/50 transition-colors"
                  onClick={() => toggleServer(server.server_id)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {expandedServers.has(server.server_id) ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                      <Server className="h-5 w-5 text-primary" />
                      <div>
                        <CardTitle className="text-lg">{server.name}</CardTitle>
                        <p className="text-sm text-muted-foreground">{server.description}</p>
                      </div>
                    </div>
                    <Badge variant="secondary">
                      {server.tools.length} tools
                    </Badge>
                  </div>
                </CardHeader>
                
                {expandedServers.has(server.server_id) && (
                  <CardContent className="pt-0">
                    <div className="space-y-2">
                      {server.tools.map((tool, index) => {
                        const toolKey = `${tool.tool_name}:${tool.server_name}`;
                        const isSelected = selectedTools.has(toolKey);
                        const isUnused = tool.total_count === 0;
                        const isCustomTool = tool.server_name === "custom_tool";
                        
                        return (
                          <div
                            key={index}
                            className={`flex items-center gap-3 p-3 rounded-lg border transition-colors ${
                              isUnused 
                                ? 'border-dashed border-muted-foreground/30 bg-muted/20' 
                                : 'border-border hover:bg-muted/30'
                            }`}
                          >
                            <Checkbox
                              checked={isSelected}
                              onCheckedChange={() => toggleToolSelection(toolKey)}
                            />
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <Wrench className={`h-4 w-4 ${
                                  isUnused ? 'text-muted-foreground/50' : 'text-muted-foreground'
                                }`} />
                                <span className={`font-medium ${
                                  isUnused ? 'text-muted-foreground/70' : 'text-foreground'
                                }`}>
                                  {tool.tool_name}
                                </span>
                                {isUnused && (
                                  <Badge variant="outline" className="text-xs">
                                    Unused
                                  </Badge>
                                )}
                                {isCustomTool && (
                                  <Badge variant="secondary" className="text-xs">
                                    Custom
                                  </Badge>
                                )}
                                {!isCustomTool && tool.from_context && (
                                  <Badge variant="outline" className="text-xs">
                                    Server
                                  </Badge>
                                )}
                              </div>
                              {tool.description && (
                                <p className="text-xs text-muted-foreground mb-2">
                                  {tool.description}
                                </p>
                              )}
                              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                                <div className="flex items-center gap-1">
                                  <Target className="h-3 w-3" />
                                  <span>{tool.total_count} calls</span>
                                </div>
                                <div className="flex items-center gap-1">
                                  <Clock className="h-3 w-3" />
                                  <span>Last: {formatDate(tool.latest_used)}</span>
                                </div>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                )}
              </Card>
            ))
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-between pt-4 border-t border-border">
          <div className="text-sm text-muted-foreground">
            {selectedTools.size > 0 ? (
              <span>{selectedTools.size} tools selected for curation</span>
            ) : (
              <span>No tools selected</span>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button 
              onClick={saveCuratedTools}
              disabled={selectedTools.size === 0 || loading}
              className="flex items-center gap-2"
            >
              <Save className="h-4 w-4" />
              Save Curated Tools
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
