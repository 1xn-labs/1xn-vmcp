
import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useRouter } from '@/hooks/useRouter';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Modal } from '@/components/ui/modal';
import { useToast } from '@/hooks/use-toast';
import { ArrowLeft, TestTube, Play, Settings, RefreshCw, ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ServerTestProvider, useServerTest, ServerTool, ServerResource, ServerPrompt, TestResult } from '@/contexts/server-test-context';
import { JsonViewer } from '@/components/ui/json-viewer';

type Tab = 'tools' | 'resources' | 'prompts';

interface ToolTestFormData {
  [key: string]: any;
}

interface PromptTestFormData {
  [key: string]: any;
}

function TestInterfaceContent() {
  const params = useParams();
  const router = useRouter();
  const { success, error } = useToast();
  const serverId = params.id as string;
  const serverName = params.name as string;

  const {
    tools,
    resources,
    prompts,
    testResults,
    loading,
    loadedTabs,
    loadServer,
    loadTabData,
    testTool,
    testResource,
    testPrompt,
    clearTestResults,
  } = useServerTest();

  const [activeTab, setActiveTab] = useState<Tab>('tools');

  // Tool testing modal state
  const [toolTestModal, setToolTestModal] = useState<{
    isOpen: boolean;
    tool: ServerTool | null;
    formData: ToolTestFormData;
    testing: boolean;
  }>({
    isOpen: false,
    tool: null,
    formData: {},
    testing: false,
  });

  // Prompt testing modal state
  const [promptTestModal, setPromptTestModal] = useState<{
    isOpen: boolean;
    prompt: ServerPrompt | null;
    formData: PromptTestFormData;
    testing: boolean;
  }>({
    isOpen: false,
    prompt: null,
    formData: {},
    testing: false,
  });

  useEffect(() => {
    if (serverId) {
      loadServer(serverId);
    }
  }, [serverId, loadServer]);

  useEffect(() => {
    if (serverId && !loadedTabs.has(activeTab)) {
      loadTabData(activeTab);
    }
  }, [activeTab, serverId, loadedTabs, loadTabData]);

  // Utility functions
  const getDefaultValue = (property: any): any => {
    if (property.default !== undefined) {
      return property.default;
    }

    switch (property.type) {
      case 'string':
        return '';
      case 'number':
      case 'integer':
        return 0;
      case 'boolean':
        return false;
      case 'array':
        return [];
      case 'object':
        return {};
      default:
        return '';
    }
  };

  // Tool testing functions
  const openToolTestModal = (tool: ServerTool) => {
    const initialFormData: ToolTestFormData = {};

    // Initialize form data based on input schema
    if (tool.inputSchema?.properties) {
      Object.keys(tool.inputSchema.properties).forEach(key => {
        const property = tool.inputSchema.properties[key];
        initialFormData[key] = getDefaultValue(property);
      });
    }

    setToolTestModal({
      isOpen: true,
      tool,
      formData: initialFormData,
      testing: false,
    });
  };

  const closeToolTestModal = () => {
    setToolTestModal({
      isOpen: false,
      tool: null,
      formData: {},
      testing: false,
    });
  };

  const handleToolFormChange = (key: string, value: any) => {
    setToolTestModal(prev => ({
      ...prev,
      formData: {
        ...prev.formData,
        [key]: value,
      },
    }));
  };

  const executeTool = async () => {
    if (!toolTestModal.tool) return;

    try {
      setToolTestModal(prev => ({ ...prev, testing: true }));

      await testTool(toolTestModal.tool.name, toolTestModal.formData);
      success(`Tool "${toolTestModal.tool.name}" executed successfully`);
      closeToolTestModal();
    } catch (err) {
      error(`Tool execution failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setToolTestModal(prev => ({ ...prev, testing: false }));
    }
  };

  // Prompt testing functions
  const openPromptTestModal = (prompt: ServerPrompt) => {
    console.log('Opening prompt modal for:', prompt.name);
    console.log('Prompt arguments:', prompt.arguments);

    const initialFormData: PromptTestFormData = {};

    // Initialize form data based on prompt arguments
    // Handle nested arguments structure
    const argumentsArray = Array.isArray(prompt.arguments)
      ? prompt.arguments
      : (prompt.arguments?.arguments && Array.isArray(prompt.arguments.arguments)
        ? prompt.arguments.arguments
        : []);

    if (argumentsArray.length > 0) {
      argumentsArray.forEach((arg: any) => {
        // Handle both object format and simple string format
        const argName = typeof arg === 'object' ? arg.name : arg;
        const defaultValue = typeof arg === 'object' && arg.default !== undefined ? arg.default : '';
        initialFormData[argName] = defaultValue;
        console.log('Added argument:', argName, 'with default:', defaultValue);
      });
    }

    console.log('Initial form data:', initialFormData);

    console.log('Setting prompt modal with:', {
      isOpen: true,
      prompt: prompt,
      formData: initialFormData,
      testing: false,
    });

    setPromptTestModal({
      isOpen: true,
      prompt,
      formData: initialFormData,
      testing: false,
    });
  };

  const closePromptTestModal = () => {
    setPromptTestModal({
      isOpen: false,
      prompt: null,
      formData: {},
      testing: false,
    });
  };

  const handlePromptFormChange = (key: string, value: any) => {
    setPromptTestModal(prev => ({
      ...prev,
      formData: {
        ...prev.formData,
        [key]: value,
      },
    }));
  };

  const executePrompt = async () => {
    if (!promptTestModal.prompt) return;

    try {
      setPromptTestModal(prev => ({ ...prev, testing: true }));

      await testPrompt(promptTestModal.prompt.name, promptTestModal.formData);
      success(`Prompt "${promptTestModal.prompt.name}" executed successfully`);
      closePromptTestModal();
    } catch (err) {
      error(`Prompt execution failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setPromptTestModal(prev => ({ ...prev, testing: false }));
    }
  };

  // Resource testing function
  const handleResourceTest = async (resource: ServerResource) => {
    try {
      await testResource(resource.uri);
      success(`Resource "${resource.uri}" read successfully`);
    } catch (err) {
      error(`Failed to read resource: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  const handleTabChange = (tab: Tab) => {
    setActiveTab(tab);
    clearTestResults();
  };

  if (loading.server) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading server...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Main Content */}
      <div className="h-screen overflow-y-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="mb-8">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <Button
                  onClick={() => router.push('/servers')}
                  variant="outline"
                >
                  <ArrowLeft className="h-4 w-4 mr-2" />
                </Button>
                <div>
                  <h1 className="text-3xl font-bold text-foreground mb-2">Test Interface: {serverName}</h1>
                  <p className="text-muted-foreground">Test tools, resources, and prompts for this MCP server</p>
                </div>
              </div>
            </div>
          </div>

          <div className="border-b border-border mb-8">
            <nav className="flex space-x-8 px-6">
              {(['tools', 'resources', 'prompts'] as Tab[]).map((tab) => (
                <button
                  key={tab}
                  onClick={() => handleTabChange(tab)}
                  className={`py-4 px-1 border-b-2 font-medium text-sm capitalize transition-colors ${activeTab === tab
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
                    }`}
                >
                  {tab === 'tools' && <TestTube className="inline mr-2 h-4 w-4" />}
                  {tab === 'resources' && <Settings className="inline mr-2 h-4 w-4" />}
                  {tab === 'prompts' && <Settings className="inline mr-2 h-4 w-4" />}
                  {tab}
                </button>
              ))}
            </nav>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left Column - Items List */}
            <Card className="p-6 max-h-[50vh] overflow-y-auto">
              <h2 className="text-lg font-semibold text-foreground mb-4">
                Available {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}
              </h2>

              {loading[activeTab] ? (
                <div className="flex items-center justify-center py-8">
                  <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                </div>
              ) : (
                <div className="space-y-3">
                  {activeTab === 'tools' && (
                    <ToolsList
                      tools={tools}
                      onTest={openToolTestModal}
                      testResults={testResults}
                    />
                  )}
                  {activeTab === 'resources' && (
                    <ResourcesList
                      resources={resources}
                      onTest={handleResourceTest}
                      testResults={testResults}
                    />
                  )}
                  {activeTab === 'prompts' && (
                    <PromptsList
                      prompts={prompts}
                      onTest={openPromptTestModal}
                      testResults={testResults}
                    />
                  )}
                </div>
              )}
            </Card>

            {/* Right Column - Test Results */}
            <Card className="p-6 max-h-[70vh] overflow-y-auto">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-foreground">Test Results</h2>
                {Object.keys(testResults).length > 0 && (
                  <Button
                    onClick={clearTestResults}
                    variant="outline"
                    size="sm"
                  >
                    Clear All
                  </Button>
                )}
              </div>

              {Object.keys(testResults).length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <TestTube className="h-12 w-12 mx-auto mb-4 text-muted-foreground/50" />
                  <p>No test results yet</p>
                  <p className="text-sm">Run a test to see results here</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {Object.entries(testResults).map(([key, result]) => (
                    <TestResultDisplay key={key} resultKey={key} result={result} />
                  ))}
                </div>
              )}
            </Card>
          </div>
        </div>
      </div>

      {/* Tool Test Modal */}
      <Modal
        isOpen={toolTestModal.isOpen}
        onClose={closeToolTestModal}
        title={`Test Tool: ${toolTestModal.tool?.name || ''}`}
        size="lg"
      >
        <div className="space-y-4 px-6 pt-6 pb-6 bg-background">
          {toolTestModal.tool && (
            <>
              <Card className="bg-card text-foreground">
                <CardContent className="p-4">
                  <p className="text-xs">
                    <strong>Description:</strong> {toolTestModal.tool.description || 'No description available'}
                  </p>
                  {toolTestModal.tool.inputSchema && (
                    <p className="text-xs mt-2">
                      <strong>Input Schema:</strong> {JSON.stringify(toolTestModal.tool.inputSchema, null, 2)}
                    </p>
                  )}
                </CardContent>
              </Card>

              <div className="space-y-4">
                {toolTestModal.tool.inputSchema?.properties &&
                  Object.entries(toolTestModal.tool.inputSchema.properties).map(([key, property]: [string, any]) => (
                    <div key={key}>
                      <label className="block text-sm font-medium text-foreground mb-2">
                        {key} {property.required && <span className="text-destructive">*</span>}
                      </label>
                      {property.type === 'string' && property.format === 'multiline' ? (
                        <Textarea
                          value={toolTestModal.formData[key] || ''}
                          onChange={(e) => handleToolFormChange(key, e.target.value)}
                          placeholder={property.description || `Enter ${key}`}
                          rows={3}
                        />
                      ) : property.type === 'boolean' ? (
                        <select
                          value={toolTestModal.formData[key] || ''}
                          onChange={(e) => handleToolFormChange(key, e.target.value === 'true')}
                          className="bg-background border-border text-foreground rounded px-3 py-2 w-full"
                        >
                          <option value="">Select...</option>
                          <option value="true">True</option>
                          <option value="false">False</option>
                        </select>
                      ) : (
                        <Input
                          type={property.type === 'number' ? 'number' : 'text'}
                          value={toolTestModal.formData[key] || ''}
                          onChange={(e) => handleToolFormChange(key, property.type === 'number' ? Number(e.target.value) : e.target.value)}
                          placeholder={property.description || `Enter ${key}`}
                        />
                      )}
                      {property.description && (
                        <p className="mt-1 text-xs text-muted-foreground">{property.description}</p>
                      )}
                    </div>
                  ))
                }

                <div className="flex gap-4 pt-6 pb-2">
                  <Button
                    onClick={closeToolTestModal}
                    variant="outline"
                    className="flex-1"
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={executeTool}
                    disabled={toolTestModal.testing}
                    className="flex-1"
                  >
                    {toolTestModal.testing ? (
                      <>
                        <RefreshCw className="h-4 w-4 animate-spin mr-2" />
                        Testing...
                      </>
                    ) : (
                      <>
                        <TestTube className="h-4 w-4 mr-2" />
                        Test Tool
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </>
          )}
        </div>
      </Modal>

      {/* Prompt Test Modal */}
      <Modal
        isOpen={promptTestModal.isOpen}
        onClose={closePromptTestModal}
        title={`Test Prompt: ${promptTestModal.prompt?.name || ''}`}
        size="lg"
      >
        <div className="space-y-4 px-6 pt-6 pb-6">
          {promptTestModal.prompt && (
            <>
              <Card className="bg-purple-500/5 border-purple-500/20">
                <CardContent className="p-4">
                  <p className="text-xs">
                    <strong>Description:</strong> {promptTestModal.prompt.description || 'No description available'}
                  </p>
                  {promptTestModal.prompt.arguments && (
                    <p className="text-xs">
                      <strong>Arguments:</strong> {JSON.stringify(promptTestModal.prompt.arguments, null, 2)}
                    </p>
                  )}
                </CardContent>
              </Card>

              <div className="space-y-4">
                {promptTestModal.prompt.arguments?.properties &&
                  Object.entries(promptTestModal.prompt.arguments.properties).map(([key, property]: [string, any]) => (
                    <div key={key}>
                      <label className="block text-sm font-medium text-foreground mb-2">
                        {key} {property.required && <span className="text-destructive">*</span>}
                      </label>
                      {property.type === 'string' && property.format === 'multiline' ? (
                        <Textarea
                          value={promptTestModal.formData[key] || ''}
                          onChange={(e) => handlePromptFormChange(key, e.target.value)}
                          placeholder={property.description || `Enter ${key}`}
                          rows={3}
                        />
                      ) : (
                        <Input
                          type={property.type === 'number' ? 'number' : 'text'}
                          value={promptTestModal.formData[key] || ''}
                          onChange={(e) => handlePromptFormChange(key, property.type === 'number' ? Number(e.target.value) : e.target.value)}
                          placeholder={property.description || `Enter ${key}`}
                        />
                      )}
                      {property.description && (
                        <p className="mt-1 text-xs text-muted-foreground">{property.description}</p>
                      )}
                    </div>
                  ))
                }

                <div className="flex gap-4 pt-6 pb-2">
                  <Button
                    onClick={closePromptTestModal}
                    variant="outline"
                    className="flex-1"
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={executePrompt}
                    disabled={promptTestModal.testing}
                    className="flex-1"
                  >
                    {promptTestModal.testing ? (
                      <>
                        <RefreshCw className="h-4 w-4 animate-spin mr-2" />
                        Testing...
                      </>
                    ) : (
                      <>
                        <TestTube className="h-4 w-4 mr-2" />
                        Test Prompt
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </>
          )}
        </div>
      </Modal>
    </div>
  );
}

// Component for tools list
function ToolsList({
  tools,
  onTest,
  testResults
}: {
  tools: ServerTool[],
  onTest: (tool: ServerTool) => void,
  testResults: Record<string, TestResult>
}) {
  const [expandedSchemas, setExpandedSchemas] = useState<Set<string>>(new Set());

  const toggleSchema = (toolName: string) => {
    setExpandedSchemas(prev => {
      const newSet = new Set(prev);
      if (newSet.has(toolName)) {
        newSet.delete(toolName);
      } else {
        newSet.add(toolName);
      }
      return newSet;
    });
  };

  if (tools.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <TestTube className="h-8 w-8 mx-auto mb-3 opacity-50" />
        <p>No tools available</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {tools.map((tool) => {
        const hasResult = testResults[`tool_${tool.name}`];
        const hasSchema = tool.inputSchema?.properties && Object.keys(tool.inputSchema.properties).length > 0;
        const isExpanded = expandedSchemas.has(tool.name);

        return (
          <div key={tool.name} className="border border-border rounded-lg p-4">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h3 className="font-medium text-foreground">{tool.name}</h3>
                {tool.description && (
                  <p className="text-sm text-muted-foreground mt-1">{tool.description}</p>
                )}
                {hasSchema && (
                  <div className="mt-2 space-y-2">
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary" className="text-xs">
                        Has Parameters
                      </Badge>
                      <button
                        onClick={() => toggleSchema(tool.name)}
                        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                      >
                        {isExpanded ? (
                          <>
                            <ChevronDown className="h-3 w-3" />
                            Hide Schema
                          </>
                        ) : (
                          <>
                            <ChevronRight className="h-3 w-3" />
                            Show Schema
                          </>
                        )}
                      </button>
                    </div>
                    {isExpanded && (
                      <div className="bg-muted p-3 rounded-md">
                        <div className="text-xs font-medium text-foreground mb-1">Input Schema:</div>
                        <pre className="text-xs text-muted-foreground whitespace-pre-wrap">
                          {JSON.stringify(tool.inputSchema, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2">
                {hasResult && (
                  <div className={cn(
                    'h-2 w-2 rounded-full',
                    hasResult.success ? 'bg-green-500' : 'bg-red-500'
                  )} />
                )}
                <Button
                  size="sm"
                  onClick={() => onTest(tool)}
                >
                  <Play className="h-3 w-3 mr-1" />
                  Test
                </Button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Component for resources list
function ResourcesList({
  resources,
  onTest,
  testResults
}: {
  resources: ServerResource[],
  onTest: (resource: ServerResource) => void,
  testResults: Record<string, TestResult>
}) {
  if (resources.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <Settings className="h-8 w-8 mx-auto mb-3 opacity-50" />
        <p>No resources available</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {resources.map((resource, index) => {
        const hasResult = testResults[`resource_${resource.uri}`];

        return (
          <div key={resource.uri || index} className="border border-border rounded-lg p-4 hover:bg-secondary/50 transition-colors">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h3 className="font-medium text-foreground font-mono text-sm">{resource.uri}</h3>
                {resource.name && (
                  <p className="text-sm text-muted-foreground mt-1">{resource.name}</p>
                )}
                {resource.description && (
                  <p className="text-sm text-muted-foreground mt-1">{resource.description}</p>
                )}
              </div>
              <div className="flex items-center gap-2">
                {hasResult && (
                  <div className={cn(
                    'h-2 w-2 rounded-full',
                    hasResult.success ? 'bg-green-500' : 'bg-red-500'
                  )} />
                )}
                <Button
                  size="sm"
                  onClick={() => onTest(resource)}
                >
                  <Settings className="h-3 w-3 mr-1" />
                  View
                </Button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Component for prompts list
function PromptsList({
  prompts,
  onTest,
  testResults
}: {
  prompts: ServerPrompt[],
  onTest: (prompt: ServerPrompt) => void,
  testResults: Record<string, TestResult>
}) {
  if (prompts.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <Settings className="h-8 w-8 mx-auto mb-3 opacity-50" />
        <p>No prompts available</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {prompts.map((prompt, index) => {
        const hasResult = testResults[`prompt_${prompt.name}`];

        return (
          <div key={prompt.name || `prompt-${index}`} className="border border-border rounded-lg p-4 hover:bg-secondary/50 transition-colors">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h3 className="font-medium text-foreground">{prompt.name}</h3>
                {prompt.description && (
                  <p className="text-sm text-muted-foreground mt-1">{prompt.description}</p>
                )}
              </div>
              <div className="flex items-center gap-2">
                {hasResult && (
                  <div className={cn(
                    'h-2 w-2 rounded-full',
                    hasResult.success ? 'bg-green-500' : 'bg-red-500'
                  )} />
                )}
                <Button
                  size="sm"
                  onClick={() => onTest(prompt)}
                >
                  <Settings className="h-3 w-3 mr-1" />
                  Test
                </Button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Component for displaying test results
function TestResultDisplay({ resultKey, result }: { resultKey: string, result: TestResult }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const getResultTitle = (key: string): string => {
    const parts = key.split('_');
    const type = parts[0];
    const name = parts.slice(1).join('_');

    switch (type) {
      case 'tool':
        return `Tool: ${name.replace(/_/g, ' ')}`;
      case 'resource':
        return `Resource: ${name}`;
      case 'prompt':
        return `Prompt: ${name.replace(/_/g, ' ')}`;
      default:
        return key.replace(/_/g, ' ');
    }
  };

  const formatResult = (result: any): string => {
    if (typeof result === 'string') {
      return result;
    }
    if (typeof result === 'object') {
      return JSON.stringify(result, null, 2);
    }
    return String(result);
  };

  const getContentPreview = (content: any): string => {
    const formatted = formatResult(content);
    const maxLength = 200;
    if (formatted.length > maxLength) {
      return formatted.substring(0, maxLength) + '...';
    }
    return formatted;
  };

  const shouldShowExpandButton = (content: any): boolean => {
    const formatted = formatResult(content);
    return formatted.length > 200;
  };

  return (
    <Card className="overflow-hidden">
      {/* Header */}
      <div className={cn(
        'flex items-center justify-between p-3 border-b',
        result.success ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'
      )}>
        <div className="flex items-center gap-2">
          <div className={cn(
            'h-2 w-2 rounded-full',
            result.success ? 'bg-green-500' : 'bg-red-500'
          )} />
          <span className="text-sm font-medium text-foreground">
            {getResultTitle(resultKey)}
          </span>
          <Badge
            variant={result.success ? 'default' : 'destructive'}
            className="text-xs"
          >
            {result.success ? 'Success' : 'Error'}
          </Badge>
        </div>
        <div className="text-xs text-muted-foreground">
          {new Date(result.timestamp).toLocaleString()}
        </div>
      </div>

      {/* Content */}
      <CardContent className="p-3">
        {result.success ? (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-foreground">Result:</span>
              {shouldShowExpandButton(result.result) && (
                <button
                  onClick={() => setIsExpanded(!isExpanded)}
                  className="flex items-center gap-1 text-xs text-primary hover:text-primary/80"
                >
                  {isExpanded ? (
                    <>
                      <ChevronDown className="h-3 w-3" />
                      Show less
                    </>
                  ) : (
                    <>
                      <ChevronRight className="h-3 w-3" />
                      Show more
                    </>
                  )}
                </button>
              )}
            </div>

            <div className="bg-muted rounded p-3 overflow-hidden">
              {isExpanded || !shouldShowExpandButton(result.result) ? (
                <div className="max-h-96 overflow-y-auto">
                  <JsonViewer
                    data={result.result}
                    defaultExpanded={true}
                    className="text-xs"
                  />
                </div>
              ) : (
                <div className="text-xs text-foreground">
                  <div className="whitespace-pre-wrap">
                    {getContentPreview(result.result)}
                  </div>
                  {shouldShowExpandButton(result.result) && (
                    <div className="mt-2 text-primary cursor-pointer" onClick={() => setIsExpanded(true)}>
                      Click to view full content
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <span className="text-xs font-medium text-destructive">Error:</span>
            <div className="bg-destructive/10 border border-destructive/30 rounded p-3">
              <div className="text-xs text-destructive whitespace-pre-wrap">
                {result.error}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function ServerTestPage() {
  return (
    <ServerTestProvider>
      <TestInterfaceContent />
    </ServerTestProvider>
  );
} 