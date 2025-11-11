
import React, { useState, useEffect } from 'react';
import { useRouter } from '@/hooks/useRouter';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table';
import { SearchableMultiSelect } from '@/components/ui/searchable-select';
import { 
  ArrowLeft, 
  TrendingUp, 
  Zap, 
  Target, 
  RefreshCw,
  Clock,
  Bot,
  Server,
  FileText,
  ChevronLeft,
  ChevronRight,
  Search,
  Filter,
  ChartBar,
  Activity,
  Settings,
  Eye,
  EyeOff,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
// import { newApi } from '@/lib/new-api';
import { apiClient } from '@/api/client';
import { Modal } from '@/components/ui/modal';

// CollapsibleJSON Component for handling large JSON data
const CollapsibleJSON: React.FC<{
  data: any;
  label: string;
  maxChars: number;
}> = ({ data, label, maxChars }) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const jsonString = JSON.stringify(data, null, 2);
  const isTruncated = jsonString.length > maxChars;
  const displayText = isTruncated ? jsonString.substring(0, maxChars) + '...' : jsonString;

  return (
    <>
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-muted-foreground">{label}</span>
          {isTruncated && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsModalOpen(true)}
              className="h-6 px-2 text-xs hover:bg-muted"
            >
              Show More
            </Button>
          )}
        </div>
        <pre className="text-xs bg-muted p-2 rounded overflow-x-auto whitespace-pre-wrap border border-border">
          {displayText}
        </pre>
      </div>
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={label}
        size="xl"
      >
        <pre className="text-sm bg-muted p-4 rounded overflow-x-auto whitespace-pre-wrap border border-border max-h-[70vh] overflow-y-auto">
          {jsonString}
        </pre>
      </Modal>
    </>
  );
};

interface LogEntry {
  timestamp: string;
  method: string;
  agent_name: string;
  agent_id: string;
  user_id: number;
  client_id: string;
  operation_id: string;
  mcp_server?: string;
  mcp_method?: string;
  original_name?: string;
  arguments?: any;
  result?: any;
  vmcp_id?: string;
  vmcp_name?: string;
  total_tools?: number;
  total_resources?: number;
  total_resource_templates?: number;
  total_prompts?: number;
}

interface StatsData {
  logs: LogEntry[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
  };
  stats: {
    total_logs: number;
    total_agents: number;
    total_vmcps: number;
    total_tool_calls: number;
    total_resource_calls: number;
    total_prompt_calls: number;
    avg_tools_per_call: number;
    unique_methods: string[];
    agent_breakdown: Record<string, number>;
    vmcp_breakdown: Record<string, number>;
    method_breakdown: Record<string, number>;
  };
  filter_options: {
    agent_names: string[];
    vmcp_names: string[];
    methods: string[];
  };
}

export default function StatsPage() {
  const router = useRouter();
  const { success, error } = useToast();
  const [statsData, setStatsData] = useState<StatsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [logsLimit] = useState(20);
  
  // Filters
  const [clientNameFilter, setClientNameFilter] = useState<string[]>([]);
  const [vmcpNameFilter, setVmcpNameFilter] = useState<string[]>([]);
  const [methodFilter, setMethodFilter] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState('');

  // Column visibility
  const [columnVisibility, setColumnVisibility] = useState({
    index: true,
    client: true,
    timestamp: true,
    method: true,
    vmcp: true,
    mcpServer: true,
    operationId: true,
    arguments: true,
    result: true,
    activeConfig: true
  });

  // Section collapse states
  const [filtersCollapsed, setFiltersCollapsed] = useState(true);
  const [columnsCollapsed, setColumnsCollapsed] = useState(true);

  // Table scroll state
  const [tableScrollPosition, setTableScrollPosition] = useState(0);

  const fetchStats = async (page: number = 1, filters: any = {}) => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      if (!token) {
        error("Please log in to view stats");
        return;
      }

      const result = await apiClient.getStats({
        page,
        limit: logsLimit,
        ...filters
      }, token);
      
      if (result.success && result.data) {
        // Map backend response to frontend interface (pages -> total_pages)
        const mappedData = {
          ...result.data,
          pagination: {
            ...result.data.pagination,
            total_pages: result.data.pagination.pages ?? result.data.pagination.total_pages
          },
          logs: result.data.logs.sort((a: LogEntry, b: LogEntry) => 
            new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
          )
        };
        setStatsData(mappedData);
        setCurrentPage(page);
      } else {
        error(result.error || "Failed to fetch stats");
      }
    } catch (err) {
      console.error('Error fetching stats:', err);
      error("Failed to fetch stats");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleRefresh = () => {
    setRefreshing(true);
    const filters = {
      agent_name: clientNameFilter.length > 0 ? clientNameFilter.join(',') : undefined,
      vmcp_name: vmcpNameFilter.length > 0 ? vmcpNameFilter.join(',') : undefined,
      method: methodFilter.length > 0 ? methodFilter.join(',') : undefined,
      search: searchQuery || undefined
    };
    fetchStats(currentPage, filters);
  };

  const handleFilterChange = () => {
    const filters = {
      agent_name: clientNameFilter.length > 0 ? clientNameFilter.join(',') : undefined,
      vmcp_name: vmcpNameFilter.length > 0 ? vmcpNameFilter.join(',') : undefined,
      method: methodFilter.length > 0 ? methodFilter.join(',') : undefined,
      search: searchQuery || undefined
    };
    fetchStats(1, filters);
  };

  const handlePageChange = (newPage: number) => {
    if (!statsData) return;
    if (newPage !== currentPage && newPage >= 1 && newPage <= statsData.pagination.total_pages) {
      const filters = {
        agent_name: clientNameFilter.length > 0 ? clientNameFilter.join(',') : undefined,
        vmcp_name: vmcpNameFilter.length > 0 ? vmcpNameFilter.join(',') : undefined,
        method: methodFilter.length > 0 ? methodFilter.join(',') : undefined,
        search: searchQuery || undefined
      };
      fetchStats(newPage, filters);
    }
  };

  const handleSearch = () => {
    const filters = {
      agent_name: clientNameFilter.length > 0 ? clientNameFilter.join(',') : undefined,
      vmcp_name: vmcpNameFilter.length > 0 ? vmcpNameFilter.join(',') : undefined,
      method: methodFilter.length > 0 ? methodFilter.join(',') : undefined,
      search: searchQuery || undefined
    };
    fetchStats(1, filters);
  };

  const clearFilters = () => {
    setClientNameFilter([]);
    setVmcpNameFilter([]);
    setMethodFilter([]);
    setSearchQuery('');
    fetchStats(1, {});
  };

  useEffect(() => {
    fetchStats(1, {});
  }, []);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const getAgentIcon = (agentName: string) => {
    const name = agentName.toLowerCase();
    
    if (name.includes('claude')) {
      return <Bot className="h-4 w-4 text-orange-600" />;
    }
    
    if (name.includes('visual studio') || name.includes('vscode') || name.includes('vs code')) {
      return <Bot className="h-4 w-4 text-blue-600" />;
    }
    
    if (name.includes('cursor')) {
      return <Bot className="h-4 w-4 text-purple-600" />;
    }
    
    if (name.includes('gemini')) {
      return <Bot className="h-4 w-4 text-yellow-600" />;
    }
    
    // Default icon
    return <Bot className="h-4 w-4 text-blue-600" />;
  };

  const getMethodColor = (method: string) => {
    if (method.includes('tool')) return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300';
    if (method.includes('resource')) return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300';
    if (method.includes('prompt')) return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300';
    return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300';
  };

  const toggleColumnVisibility = (column: string) => {
    setColumnVisibility(prev => ({
      ...prev,
      [column]: !prev[column as keyof typeof prev]
    }));
  };

  const scrollTable = (direction: 'left' | 'right') => {
    const tableContainer = document.getElementById('logs-table-container');
    if (tableContainer) {
      const scrollAmount = 300; // pixels to scroll
      const currentScroll = tableContainer.scrollLeft;
      const newPosition = direction === 'left' 
        ? Math.max(0, currentScroll - scrollAmount)
        : currentScroll + scrollAmount;
      
      tableContainer.scrollTo({
        left: newPosition,
        behavior: 'smooth'
      });
    }
  };

  const columnConfig = [
    { key: 'index', label: '#' },
    { key: 'client', label: 'Client' },
    { key: 'timestamp', label: 'Timestamp' },
    { key: 'method', label: 'Method' },
    { key: 'vmcp', label: 'vMCP' },
    { key: 'mcpServer', label: 'MCP Server' },
    { key: 'operationId', label: 'Operation ID' },
    { key: 'arguments', label: 'Arguments' },
    { key: 'result', label: 'Result' },
    { key: 'activeConfig', label: 'Active Config' }
  ];

  if (loading) {
    return (
      <div className="min-h-screen text-foreground flex items-center justify-center">
        <div className="flex items-center space-x-2">
          <RefreshCw className="h-6 w-6 animate-spin" />
          <span>Loading stats...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen mx-auto p-4">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-primary/20 flex items-center justify-center">
              <ChartBar className="h-6 w-6 text-primary" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-foreground">
                Statistics
              </h1>
              <p className="text-sm text-muted-foreground">Comprehensive analytics and logs overview</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button 
              onClick={handleRefresh} 
              disabled={refreshing}
              variant="outline"
              size="sm"
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>
      </div>

        {/* Statistics Cards */}
        {statsData && (
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-2 mb-4">
            <Card>
              <CardContent className="p-3">
                <div className="flex items-center gap-2">
                  <div className="h-6 w-6 rounded bg-blue-100 dark:bg-blue-900 flex items-center justify-center">
                    <Activity className="h-3 w-3 text-blue-600 dark:text-blue-400" />
                  </div>
                  <div className="flex-1">
                    <p className="text-xs font-medium text-muted-foreground truncate">Total Logs</p>
                    <p className="text-sm font-bold text-foreground">{statsData.stats.total_logs.toLocaleString()}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-3">
                <div className="flex items-center gap-2">
                  <div className="h-6 w-6 rounded bg-green-100 dark:bg-green-900 flex items-center justify-center">
                    <Bot className="h-3 w-3 text-green-600 dark:text-green-400" />
                  </div>
                  <div className="flex-1">
                    <p className="text-xs font-medium text-muted-foreground truncate">Active Clients</p>
                    <p className="text-sm font-bold text-foreground">{statsData.stats.total_agents}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-3">
                <div className="flex items-center gap-2">
                  <div className="h-6 w-6 rounded bg-purple-100 dark:bg-purple-900 flex items-center justify-center">
                    <Server className="h-3 w-3 text-purple-600 dark:text-purple-400" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-muted-foreground truncate">vMCPs</p>
                    <p className="text-sm font-bold text-foreground">{statsData.stats.total_vmcps}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-3">
                <div className="flex items-center gap-2">
                  <div className="h-6 w-6 rounded bg-orange-100 dark:bg-orange-900 flex items-center justify-center">
                    <Zap className="h-3 w-3 text-orange-600 dark:text-orange-400" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-muted-foreground truncate">Tool Calls</p>
                    <p className="text-sm font-bold text-foreground">{statsData.stats.total_tool_calls.toLocaleString()}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-3">
                <div className="flex items-center gap-2">
                  <div className="h-6 w-6 rounded bg-cyan-100 dark:bg-cyan-900 flex items-center justify-center">
                    <Target className="h-3 w-3 text-cyan-600 dark:text-cyan-400" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-muted-foreground truncate">Avg Tools/Call</p>
                    <p className="text-sm font-bold text-foreground">{statsData.stats.avg_tools_per_call}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Filters */}
        <Card className="mb-4">
          <CardHeader 
            className="cursor-pointer hover:bg-muted/50 transition-colors"
            onClick={() => setFiltersCollapsed(!filtersCollapsed)}
          >
            <CardTitle className="text-foreground flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Filter className="h-5 w-5" />
                Filters & Search
              </div>
              {filtersCollapsed ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronUp className="h-4 w-4" />
              )}
            </CardTitle>
            <CardDescription className="text-muted-foreground">
              Filter logs by client, vMCP, method, or search across all fields
            </CardDescription>
          </CardHeader>
          {!filtersCollapsed && (
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground mb-2 block">vMCP Name</label>
                  <SearchableMultiSelect
                    options={statsData?.filter_options?.vmcp_names || []}
                    value={vmcpNameFilter}
                    onValueChange={setVmcpNameFilter}
                    placeholder="Select vMCPs..."
                    searchPlaceholder="Search vMCPs..."
                    emptyText="No vMCPs found"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground mb-2 block">Client Name</label>
                  <SearchableMultiSelect
                    options={statsData?.filter_options?.agent_names || []}
                    value={clientNameFilter}
                    onValueChange={setClientNameFilter}
                    placeholder="Select clients..."
                    searchPlaceholder="Search clients..."
                    emptyText="No clients found"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground mb-2 block">Method</label>
                  <SearchableMultiSelect
                    options={statsData?.filter_options?.methods || []}
                    value={methodFilter}
                    onValueChange={setMethodFilter}
                    placeholder="Select methods..."
                    searchPlaceholder="Search methods..."
                    emptyText="No methods found"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground mb-2 block">Search</label>
                  <div className="flex gap-2">
                    <Input
                      placeholder="Search logs..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="bg-background border-border text-foreground"
                    />
                    <Button onClick={handleSearch} size="sm">
                      <Search className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                <Button onClick={handleFilterChange} className="flex items-center gap-2">
                  <Filter className="h-4 w-4" />
                  Apply Filters
                </Button>
                <Button onClick={clearFilters} variant="outline" className="flex items-center gap-2">
                  Clear Filters
                </Button>
              </div>
            </CardContent>
          )}
        </Card>

        {/* Column Configuration */}
        <Card className="mb-4">
          <CardHeader 
            className="cursor-pointer hover:bg-muted/50 transition-colors"
            onClick={() => setColumnsCollapsed(!columnsCollapsed)}
          >
            <CardTitle className="text-foreground flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Settings className="h-5 w-5" />
                Column Visibility
              </div>
              {columnsCollapsed ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronUp className="h-4 w-4" />
              )}
            </CardTitle>
            <CardDescription className="text-muted-foreground">
              Select which columns to display in the logs table
            </CardDescription>
          </CardHeader>
          {!columnsCollapsed && (
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                {columnConfig.map((column) => (
                  <div key={column.key} className="flex items-center space-x-2">
                    <Checkbox
                      id={column.key}
                      checked={columnVisibility[column.key as keyof typeof columnVisibility]}
                      onCheckedChange={() => toggleColumnVisibility(column.key)}
                    />
                    <label
                      htmlFor={column.key}
                      className="text-sm font-medium text-foreground cursor-pointer"
                    >
                      {column.label}
                    </label>
                  </div>
                ))}
              </div>
            </CardContent>
          )}
        </Card>

        {/* Logs Table */}
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground">System Logs</CardTitle>
            <CardDescription className="text-muted-foreground">
              Detailed view of all system activities with filtering and pagination
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="w-full overflow-hidden">
              {/* Fixed Header */}
              <div className="sticky top-0 bg-background z-30 border-b border-border">
                <Table className="min-w-full">
                  <TableHeader>
                    <TableRow className="border-border">
                      {columnVisibility.index && (
                        <TableHead className="text-muted-foreground w-[2%] bg-background">#</TableHead>
                      )}
                      {columnVisibility.client && (
                        <TableHead className="text-muted-foreground w-[8%] bg-background">Client</TableHead>
                      )}
                      {columnVisibility.timestamp && (
                        <TableHead className="text-muted-foreground w-[12%] bg-background">Timestamp</TableHead>
                      )}
                      {columnVisibility.method && (
                        <TableHead className="text-muted-foreground w-[10%] bg-background">Method</TableHead>
                      )}
                      {columnVisibility.vmcp && (
                        <TableHead className="text-muted-foreground w-[12%] bg-background">vMCP</TableHead>
                      )}
                      {columnVisibility.mcpServer && (
                        <TableHead className="text-muted-foreground w-[10%] bg-background">MCP Server</TableHead>
                      )}
                      {columnVisibility.operationId && (
                        <TableHead className="text-muted-foreground w-[13%] bg-background">Operation ID</TableHead>
                      )}
                      {columnVisibility.arguments && (
                        <TableHead className="text-muted-foreground w-[15%] bg-background">Arguments</TableHead>
                      )}
                      {columnVisibility.result && (
                        <TableHead className="text-muted-foreground w-[15%] bg-background">Result</TableHead>
                      )}
                      {columnVisibility.activeConfig && (
                        <TableHead className="text-muted-foreground w-[10%] bg-background">Active Config</TableHead>
                      )}
                    </TableRow>
                  </TableHeader>
                </Table>
              </div>
              
              {/* Scrollable Body */}
              <div 
                id="logs-table-container"
                className="h-[700px] overflow-auto"
              >
                <Table className="min-w-full">
                  <TableBody>
                    {statsData && statsData.logs && statsData.logs.length > 0 ? (
                      statsData.logs.map((log, index) => (
                        <TableRow key={index} className="border-border hover:bg-muted/50">
                          {columnVisibility.index && (
                            <TableCell className="text-foreground font-medium text-center w-[5%]">
                              {((currentPage - 1) * logsLimit) + index + 1}
                            </TableCell>
                          )}
                          {columnVisibility.client && (
                            <TableCell className="text-foreground w-[8%]">
                              <div className="flex items-center space-x-2">
                                {getAgentIcon(log.agent_name)}
                                <span className="text-sm font-medium truncate">
                                  {log.agent_name}
                                </span>
                              </div>
                            </TableCell>
                          )}
                          {columnVisibility.timestamp && (
                            <TableCell className="text-foreground w-[12%]">
                              <div className="flex items-center space-x-1">
                                <Clock className="h-3 w-3 text-muted-foreground" />
                                <span className="text-sm truncate">{formatDate(log.timestamp)}</span>
                              </div>
                            </TableCell>
                          )}
                          {columnVisibility.method && (
                            <TableCell className="text-foreground w-[10%]">
                              <Badge className={`text-xs ${getMethodColor(log.method)}`}>
                                {log.method}
                              </Badge>
                            </TableCell>
                          )}
                          {columnVisibility.vmcp && (
                            <TableCell className="text-foreground w-[12%]">
                              <div className="truncate">
                                {log.vmcp_name ? (
                                  <div className="flex items-center space-x-2">
                                    <Server className="h-3 w-3 text-primary flex-shrink-0" />
                                    <span className="text-sm font-mono truncate">
                                      {log.vmcp_name}
                                    </span>
                                  </div>
                                ) : (
                                  <span className="text-muted-foreground">N/A</span>
                                )}
                              </div>
                            </TableCell>
                          )}
                          {columnVisibility.mcpServer && (
                            <TableCell className="text-foreground w-[10%]">
                              <div className="truncate">
                                {log.mcp_server ? (
                                  <Badge variant="secondary" className="bg-muted text-foreground truncate max-w-full">
                                    {log.mcp_server}
                                  </Badge>
                                ) : (
                                  <span className="text-muted-foreground">N/A</span>
                                )}
                              </div>
                            </TableCell>
                          )}
                          {columnVisibility.operationId && (
                            <TableCell className="text-foreground w-[13%]">
                              <span className="text-sm font-mono truncate block">
                                {log.operation_id || 'N/A'}
                              </span>
                            </TableCell>
                          )}
                          {columnVisibility.arguments && (
                            <TableCell className="text-foreground w-[15%]">
                              <div className="truncate">
                                {log.arguments ? (
                                  <CollapsibleJSON
                                    data={log.arguments}
                                    label="Arguments"
                                    maxChars={100}
                                  />
                                ) : (
                                  <span className="text-muted-foreground">No arguments</span>
                                )}
                              </div>
                            </TableCell>
                          )}
                          {columnVisibility.result && (
                            <TableCell className="text-foreground w-[15%]">
                              <div className="truncate">
                                {log.result ? (
                                  <CollapsibleJSON
                                    data={log.result}
                                    label="Result"
                                    maxChars={100}
                                  />
                                ) : (
                                  <span className="text-muted-foreground">No result</span>
                                )}
                              </div>
                            </TableCell>
                          )}
                          {columnVisibility.activeConfig && (
                            <TableCell className="text-foreground w-[10%]">
                              <div className="text-xs text-muted-foreground space-y-1">
                                <div>{log.total_tools || 0} tools</div>
                                <div>{log.total_prompts || 0} prompts</div>
                                <div>{log.total_resources || 0} resources</div>
                              </div>
                            </TableCell>
                          )}
                        </TableRow>
                      ))
                    ) : (
                      <TableRow>
                        <TableCell colSpan={Object.values(columnVisibility).filter(Boolean).length} className="text-center py-8">
                          <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                          <h3 className="text-lg font-medium text-foreground mb-2">
                            No logs found
                          </h3>
                          <p className="text-muted-foreground">
                            Logs will appear here when agents make requests.
                          </p>
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            </div>

            {/* Pagination Controls */}
            {statsData && statsData.pagination.total > 0 && (
              <div className="flex items-center justify-between mt-6">
                <div className="text-sm text-muted-foreground">
                  Showing {((currentPage - 1) * logsLimit) + 1} to {Math.min(currentPage * logsLimit, statsData.pagination.total)} of {statsData.pagination.total} logs
                </div>
                <div className="flex items-center space-x-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handlePageChange(currentPage - 1)}
                    disabled={currentPage === 1}
                    className="border-border bg-card text-foreground hover:bg-muted disabled:opacity-50"
                  >
                    <ChevronLeft className="h-4 w-4 mr-1" />
                    Previous
                  </Button>
                  <span className="text-sm text-muted-foreground px-3">
                    Page {currentPage} of {statsData.pagination.total_pages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handlePageChange(currentPage + 1)}
                    disabled={currentPage >= statsData.pagination.total_pages}
                    className="border-border bg-card text-foreground hover:bg-muted disabled:opacity-50"
                  >
                    Next
                    <ChevronRight className="h-4 w-4 ml-1" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
  );
}
